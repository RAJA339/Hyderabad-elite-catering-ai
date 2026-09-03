"""Conversation orchestrator: one inbound message → one grounded, guard-railed reply.

Pipeline: consent gate → qualification extraction → RAG retrieval (knowledge intents only)
→ LLM tool loop (≤ 4 rounds) → guardrails → persistence. Without an LLM key the orchestrator
falls back to a deterministic scripted flow so the system stays demoable end-to-end."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date
from uuid import UUID

from app.agent import qualification as qual
from app.agent.guardrails import check_reply
from app.agent.llm import LLMResponse, get_llm
from app.agent.system_prompt import build_system_prompt
from app.agent.tools import TOOLS, ToolExecutor
from app.core.config import get_settings
from app.core.logging import get_logger
from app.festivals.calendar import festivals_around
from app.leads import quotes as qrepo
from app.leads import repository as leads
from app.pricing.repository import kitchen_load
from app.rag.retrieval import retrieve

log = get_logger("agent")
MAX_TOOL_ROUNDS = 4
CONSENT_TEXT = ("Namaste andi! I'm Anvi from Hyderabad Elite Catering 🌿 To plan your menu and send quotes here on WhatsApp, "
                "may I save your name and number? Reply YES to continue (you can say STOP anytime).")


@dataclass
class AgentReply:
    text: str
    buttons: list[tuple[str, str]] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)
    escalated: bool = False
    violations: list[str] = field(default_factory=list)
    latency_ms: int = 0


async def handle_inbound(*, tenant_id: UUID, wa_id: str, text: str, profile_name: str | None = None, external_id: str | None = None,
                         channel: str = "whatsapp", kind: str = "text", media: dict | None = None) -> AgentReply:
    t0 = time.perf_counter()
    customer = await leads.get_or_create_customer(tenant_id, wa_id, profile_name)
    lead = await leads.get_or_create_open_lead(tenant_id, customer["id"], source="whatsapp" if channel == "whatsapp" else "web_chat")
    await leads.store_message(tenant_id, lead["id"], "customer", text, kind=kind, external_id=external_id, media=media)

    # ── Consent gate (DPDP) ──────────────────────────────────────────────────
    consented = await leads.has_consent(customer["id"])
    low = text.strip().lower()
    if not consented:
        if low in ("yes", "y", "ok", "okay", "sure", "haan", "avunu", "sare", "consent_yes") or low.startswith("yes"):
            await leads.record_consent(tenant_id, customer["id"], "communication", True, {"message_id": external_id, "text": text})
            await leads.record_consent(tenant_id, customer["id"], "data_storage", True, {"message_id": external_id, "text": text})
            consented = True
            text = "Hi, I'd like to plan a catering event."  # continue naturally
        else:
            reply = AgentReply(CONSENT_TEXT, buttons=[("consent_yes", "Yes, continue"), ("consent_no", "No thanks")])
            await leads.store_message(tenant_id, lead["id"], "agent", reply.text)
            return reply
    if low in ("stop", "unsubscribe", "consent_no"):
        await leads.record_consent(tenant_id, customer["id"], "communication", False, {"message_id": external_id, "text": text})
        reply = AgentReply("Done — I won't message you further. If you ever need catering in Hyderabad, just say hi. 🙏")
        await leads.store_message(tenant_id, lead["id"], "agent", reply.text)
        return reply

    if lead.get("handoff_active"):
        reply = AgentReply("Our events lead has your conversation and will reply here shortly. Anything else you'd like me to note for them?")
        await leads.store_message(tenant_id, lead["id"], "agent", reply.text)
        return reply

    # ── Qualification extraction (deterministic safety net) ─────────────────
    q = qual.Qualification.from_dict(lead.get("qualification"))
    q = qual.extract(text, q, max_guests=get_settings().max_guests)
    fields = {k: q.fields[k] for k in ("event_date", "guest_count", "diet", "venue_area", "occasion") if k in q.fields}
    if "budget" in q.fields:
        fields["budget_min_per_plate"] = q.fields["budget"]["min_per_plate"]
        fields["budget_max_per_plate"] = q.fields["budget"]["max_per_plate"]
    if "event_date" in fields:
        fields["event_date"] = date.fromisoformat(fields["event_date"])
    lead = await leads.update_lead_fields(lead["id"], fields, qualification=q.to_dict())
    if lead["stage"] == "new":
        await leads.set_stage(tenant_id, lead["id"], "qualifying")
    if q.is_qualified and lead["stage"] == "qualifying":
        await leads.set_stage(tenant_id, lead["id"], "qualified")

    # ── Session state + RAG ─────────────────────────────────────────────────
    quote = await qrepo.latest_quote(lead["id"])
    ev = lead.get("event_date")
    state = {
        "customer": {"name": customer.get("full_name"), "wa_id": wa_id, "bookings_before": customer.get("bookings_count", 0)},
        "lead": {k: str(v) if v is not None else None for k, v in lead.items() if k in ("id", "stage", "occasion", "event_date", "guest_count", "diet", "venue_area", "budget_min_per_plate", "budget_max_per_plate")},
        "qualification": q.to_dict(),
        "consent": {"communication": True},
        "quote": _quote_state(quote, await qrepo.quote_items(quote["id"])) if quote else None,
        "festival_context": [{"key": f.key, "name": f.name, "starts_on": f.starts_on.isoformat()} for f in festivals_around(ev)] if ev else [],
        "kitchen_load_on_date": await kitchen_load(tenant_id, ev) if ev else None,
        "max_guests": get_settings().max_guests,
        "today": date.today().isoformat(),
    }
    rag = await retrieve(tenant_id=tenant_id, query=text, lead_id=lead["id"], event_date=ev, diet=lead.get("diet"), guest_count=lead.get("guest_count"))
    system = build_system_prompt(session_state=state, knowledge_blocks=rag.context_blocks, live_enrichment=rag.enrichment)

    executor = ToolExecutor(tenant_id, lead, customer)
    llm = get_llm()
    tokens_in = tokens_out = 0
    if llm is None:
        reply_text = await _scripted_reply(text, q, executor, rag.plan.intent)
    else:
        try:
            reply_text, tokens_in, tokens_out = await _llm_loop(llm, system, lead, text, executor)
        except Exception as e:  # noqa: BLE001 - a model outage must not lose the lead
            log.exception("llm_loop_failed", lead_id=str(lead["id"]), error=type(e).__name__)
            reply_text = await _scripted_reply(text, q, executor, rag.plan.intent)

    reply_text, violations = check_reply(reply_text, executor.results, state, max_guests=get_settings().max_guests)
    escalated = any(r["name"] == "escalate_to_human" for r in executor.results)
    latency = int((time.perf_counter() - t0) * 1000)
    await leads.store_message(tenant_id, lead["id"], "agent", reply_text, tool_calls=executor.results, rag_query_id=rag.query_id,
                              tokens_in=tokens_in, tokens_out=tokens_out, latency_ms=latency)
    if violations:
        log.warning("guardrail_violations", lead_id=str(lead["id"]), violations=violations)
    buttons = _buttons_for(executor.results)
    return AgentReply(reply_text, buttons=buttons, tool_calls=executor.results, escalated=escalated, violations=violations, latency_ms=latency)


async def _llm_loop(llm, system: str, lead: dict, text: str, executor: ToolExecutor) -> tuple[str, int, int]:
    s = get_settings()
    history = await leads.recent_messages(lead["id"], limit=16)
    messages: list = []
    for m in history[:-1]:  # last one is the current customer message
        role = "user" if m["role"] == "customer" else "assistant"
        content = m["transcript"] or m["content"]
        if not content or (messages and messages[-1]["role"] == role):
            continue
        messages.append({"role": role, "content": content})
    if messages and messages[0]["role"] != "user":
        messages = messages[1:]
    messages.append({"role": "user", "content": text})
    tin = tout = 0
    resp: LLMResponse | None = None
    for _ in range(MAX_TOOL_ROUNDS):
        resp = await llm.chat(system=system, messages=messages, tools=TOOLS, max_tokens=s.llm_max_tokens)
        tin, tout = tin + resp.tokens_in, tout + resp.tokens_out
        if resp.stop_reason == "refusal":
            log.warning("llm_refusal", lead_id=str(lead["id"]), category=resp.refusal_category)
            await executor.run("escalate_to_human", {"reason": "model declined to answer", "summary": text[:500]})
            return ("Let me get one of our team to answer that properly — they'll reply here shortly.", tin, tout)
        if not resp.tool_calls:
            break
        results = []
        for call in resp.tool_calls:
            results.append((call, await executor.run(call.name, call.arguments)))
        messages.append(llm.assistant_turn(resp))
        tr = llm.tool_results_turn(results)
        messages.extend(tr if isinstance(tr, list) else [tr])
    text_out = (resp.text if resp else "") or "Let me check that with our kitchen team and come back to you in a moment."
    return text_out, tin, tout


async def _scripted_reply(text: str, q: qual.Qualification, executor: ToolExecutor, intent: str) -> str:
    """Deterministic fallback when no LLM key is configured (dev/demo)."""
    if q.over_limit:
        return ("Congratulations on the big event! Our kitchen serves up to 500 guests per sitting with the quality we promise. "
                "For more, we can do two sittings or two dates — which works better for you?")
    if intent == "escalation":
        await executor.run("escalate_to_human", {"reason": "customer requested human", "summary": text})
        return "Of course — I've passed this to our events lead with your details. They'll reply here within 2 hours."
    if not q.is_qualified:
        qs = qual.next_questions(q)
        known = ", ".join(f"{k.replace('_', ' ')}: {v}" for k, v in q.fields.items() if k != "budget")
        prefix = f"Got it ({known}). " if known else "Lovely! "
        return prefix + "Two quick things: " + " and ".join(qs) + "?"
    if intent in ("modification",):
        return "Tell me exactly what to change (e.g. 'add 40 guests', 'remove mutton', 'make it Jain') and I'll re-price instantly."
    res = await executor.run("price_package", {})
    if "error" in res:
        return f"I need one more detail before pricing: {res.get('need') or res.get('message') or res['error']}."
    lines = []
    for p in res["packages"]:
        lines.append(f"• {p['tier'].title()} — ₹{p['per_plate']}/plate (₹{p['grand_total']} incl. GST): " + ", ".join(i["name"] for i in p["items"][:5]) + "…")
    return (f"Here are three options for {res['guest_count']} guests ({res['diet']}):\n" + "\n".join(lines) +
            f"\nSignature is our crowd favourite. View & tweak live: {res['working_quote']['portal_url']}\nShall I check festival offers?")


def _quote_state(quote: dict, items: list[dict]) -> dict:
    return {"quote_number": quote["quote_number"], "version": quote["version"], "tier": quote["tier"], "status": quote["status"],
            "guest_count": quote["guest_count"], "diet": quote["diet"], "event_date": str(quote["event_date"]),
            "per_plate": str(quote["per_plate"]), "subtotal": str(quote["subtotal"]), "discount_total": str(quote["discount_total"]),
            "grand_total": str(quote["grand_total"]), "items": [{"slug": i["slug"], "name": i["name"], "category": i["category_key"]} for i in items],
            "portal_url": f"{get_settings().public_web_url}/portal/{quote['portal_token']}"}


def _buttons_for(results: list[dict]) -> list[tuple[str, str]]:
    names = [r["name"] for r in results]
    if "price_package" in names:
        return [("pick_classic", "Classic"), ("pick_signature", "Signature"), ("pick_royal", "Royal")]
    if "festival_offers" in names and not any(r["result"].get("applied") for r in results if r["name"] == "festival_offers"):
        return [("apply_offer", "Apply offer"), ("lock_price", "Lock price")]
    if "lock_price" in names:
        return [("pay_advance", "Pay advance"), ("share_quote", "Share quote")]
    return []


INTERACTIVE_INTENTS = {
    "pick_classic": "Let's go with the Classic package", "pick_signature": "Let's go with the Signature package", "pick_royal": "Let's go with the Royal package",
    "apply_offer": "Please apply the festival offer", "lock_price": "Please lock this price", "pay_advance": "Send me the advance payment link",
    "share_quote": "Share this quote link with my family", "consent_yes": "yes", "consent_no": "stop",
}
