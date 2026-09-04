"""Tool belt for the agent. Schemas are provider-neutral JSON; the executor is the only place
that touches the pricing engine, discount engine and persistence. Every rupee the customer
sees is produced here."""
from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.agent.handoff import notify_owner, notify_owner_order
from app.core.config import get_settings
from app.festivals.repository import load_rules
from app.festivals.rules import QuoteContext, best_offers
from app.leads import lifecycle
from app.leads import quotes as qrepo
from app.leads import repository as leads
from app.payments import upi
from app.pricing.engine import GuestLimitExceeded, price_package
from app.pricing.market import market_snapshot
from app.pricing.packages import apply_diet, build_tiers, modify_items, rounded_display
from app.pricing.repository import kitchen_load, load_catalog, load_policy, load_prices, load_templates

TOOLS: list[dict] = [
    {
        "name": "save_lead_field",
        "description": "Save qualification details the customer just shared (any subset). Also records consent when the customer agrees.",
        "parameters": {"type": "object", "properties": {
            "consent": {"type": "boolean", "description": "true when the customer agreed to be contacted / data stored"},
            "full_name": {"type": "string"}, "email": {"type": "string", "description": "customer email, when they share one — quotes and confirmations are sent there"},
            "event_date": {"type": "string", "description": "ISO date YYYY-MM-DD"},
            "guest_count": {"type": "integer"}, "diet": {"type": "string", "enum": ["veg", "non_veg", "mixed", "jain"]},
            "venue_area": {"type": "string"}, "venue_name": {"type": "string"},
            "budget_min_per_plate": {"type": "number"}, "budget_max_per_plate": {"type": "number"}, "occasion": {"type": "string"},
        }},
    },
    {
        "name": "price_package",
        "description": "Generate Classic/Signature/Royal packages with live per-plate and total prices for the lead. Checks kitchen capacity for the date. Call whenever the customer asks for options, prices, or a quote.",
        "parameters": {"type": "object", "properties": {
            "guest_count": {"type": "integer"}, "diet": {"type": "string", "enum": ["veg", "non_veg", "mixed", "jain"]},
            "event_date": {"type": "string"}, "occasion": {"type": "string"},
            "budget_min_per_plate": {"type": "number"}, "budget_max_per_plate": {"type": "number"},
        }},
    },
    {
        "name": "modify_quote",
        "description": "Modify the current quote: change guests, change diet (e.g. Jain), add or remove menu items by slug or name, or switch tier. Returns the reprised quote and a list of changes.",
        "parameters": {"type": "object", "properties": {
            "tier": {"type": "string", "enum": ["classic", "signature", "royal"]},
            "guest_count": {"type": "integer"}, "diet": {"type": "string", "enum": ["veg", "non_veg", "mixed", "jain"]},
            "add_items": {"type": "array", "items": {"type": "string"}, "description": "menu item slugs or names to add"},
            "remove_items": {"type": "array", "items": {"type": "string"}, "description": "menu item slugs, names or tags (e.g. 'mutton') to remove"},
        }},
    },
    {
        "name": "festival_offers",
        "description": "Find the best eligible festival / early-bird / volume discount for the current quote. Only offers that protect our margin are returned. Apply=true re-prices the quote with the offer.",
        "parameters": {"type": "object", "properties": {"apply": {"type": "boolean", "default": False}}},
    },
    {
        "name": "market_snapshot",
        "description": "Today's Hyderabad market price for key ingredients vs our price per plate, for transparency when the customer asks why prices are what they are.",
        "parameters": {"type": "object", "properties": {"ingredients": {"type": "array", "items": {"type": "string"}}}},
    },
    {
        "name": "lock_price",
        "description": "Lock the current quote's price until the event date and issue a price-lock certificate.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "record_advance",
        "description": "Create the advance payment request (30% by default) and return the payment link.",
        "parameters": {"type": "object", "properties": {"pct": {"type": "number"}}},
    },
    {
        "name": "suggest_upsell",
        "description": "Predictive upsell: what clients with similar bookings usually add (e.g. live mocktail or chaat counter).",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "escalate_to_human",
        "description": "Hand the conversation to a human with a full summary. Use only for truly custom requests, disputes, or explicit requests for a person.",
        "parameters": {"type": "object", "properties": {"reason": {"type": "string"}, "summary": {"type": "string"}, "priority": {"type": "string", "enum": ["normal", "high"]}}, "required": ["reason", "summary"]},
    },
]


class ToolExecutor:
    def __init__(self, tenant_id: UUID, lead: dict, customer: dict):
        self.tenant_id, self.lead, self.customer = tenant_id, lead, customer
        self.results: list[dict] = []

    async def run(self, name: str, args: dict) -> Any:
        fn = getattr(self, f"t_{name}", None)
        if fn is None:
            return {"error": f"unknown tool {name}"}
        try:
            out = await fn(**{k: v for k, v in args.items() if v is not None})
        except GuestLimitExceeded as e:
            out = {"error": "guest_limit", "message": str(e), "max_guests": get_settings().max_guests,
                   "suggestion": "Offer two sittings or two dates; escalate if the customer insists."}
        except Exception as e:  # noqa: BLE001
            out = {"error": type(e).__name__, "message": str(e)[:300]}
        self.results.append({"name": name, "args": args, "result": out})
        return out

    # ── helpers ────────────────────────────────────────────────────────────────
    def _event_date(self, override: str | None = None) -> date:
        d = override or self.lead.get("event_date")
        if isinstance(d, date):
            return d
        if d:
            return date.fromisoformat(str(d))
        raise ValueError("event date not known yet — ask the customer first")

    def _portal_url(self, quote: dict) -> str:
        return f"{get_settings().public_web_url}/portal/{quote['portal_token']}"

    async def _price_from_slugs(self, tier: str, slugs: list[str], guest_count: int, diet: str, discounts=()) -> tuple[Any, dict, dict]:
        catalog, prices, policy = await load_catalog(self.tenant_id), await load_prices(self.tenant_id), await load_policy(self.tenant_id)
        items = [catalog[s] for s in slugs if s in catalog]
        items, notes = apply_diet(items, diet, catalog)
        pkg = price_package(tier=tier, items=items, prices=prices, guest_count=guest_count, diet=diet, policy=policy, discounts=discounts)
        pkg.notes = notes + pkg.notes
        return pkg, catalog, prices

    # ── tools ──────────────────────────────────────────────────────────────────
    async def t_save_lead_field(self, **fields) -> dict:
        consent = fields.pop("consent", None)
        if consent is not None:
            await leads.record_consent(self.tenant_id, self.customer["id"], "communication", bool(consent), {"via": "agent_tool"})
            await leads.record_consent(self.tenant_id, self.customer["id"], "data_storage", bool(consent), {"via": "agent_tool"})
        name = fields.pop("full_name", None)
        if name:
            from app.core import db
            await db.execute("UPDATE customers SET full_name = $2 WHERE id = $1", self.customer["id"], name)
            self.customer["full_name"] = name
        email = (fields.pop("email", None) or "").strip().lower()
        if email and "@" in email:
            from app.core import db
            await db.execute("UPDATE customers SET email = $2 WHERE id = $1", self.customer["id"], email)
            self.customer["email"] = email
        if "guest_count" in fields and int(fields["guest_count"]) > get_settings().max_guests:
            requested = fields.pop("guest_count")
            return {"error": "guest_limit", "requested": requested, "max_guests": get_settings().max_guests}
        if "event_date" in fields:
            fields["event_date"] = date.fromisoformat(fields["event_date"])
        if fields:
            self.lead = await leads.update_lead_fields(self.lead["id"], fields)
            if self.lead.get("stage") == "new":
                await leads.set_stage(self.tenant_id, self.lead["id"], "qualifying")
                self.lead["stage"] = "qualifying"
        return {"saved": {k: str(v) for k, v in fields.items()}, "consent": consent}

    async def t_price_package(self, guest_count: int | None = None, diet: str | None = None, event_date: str | None = None,
                              occasion: str | None = None, budget_min_per_plate=None, budget_max_per_plate=None) -> dict:
        guest_count = int(guest_count or self.lead.get("guest_count") or 0)
        diet = diet or self.lead.get("diet")
        if not guest_count or not diet:
            return {"error": "missing_fields", "need": [f for f, v in (("guest_count", guest_count), ("diet", diet)) if not v]}
        ev = self._event_date(event_date)
        occasion = occasion or self.lead.get("occasion")
        policy = await load_policy(self.tenant_id)
        load = await kitchen_load(self.tenant_id, ev)
        capacity_left = policy.max_guests - load
        if guest_count > capacity_left:
            return {"error": "kitchen_capacity", "date": ev.isoformat(), "capacity_left": max(capacity_left, 0),
                    "suggestion": "Offer the previous or next day, or a second sitting."}
        pkgs = build_tiers(templates=await load_templates(self.tenant_id), catalog=await load_catalog(self.tenant_id), prices=await load_prices(self.tenant_id),
                           guest_count=guest_count, diet=diet, policy=policy, occasion=occasion)
        # Persist the middle tier as the working quote (customer can switch via modify_quote)
        chosen = next((p for p in pkgs if p.tier == "signature"), pkgs[0] if pkgs else None)
        saved = None
        if chosen:
            snap = market_snapshot(chosen, await load_prices(self.tenant_id))
            saved = await qrepo.save_quote(self.tenant_id, self.lead["id"], chosen, ev, market_snapshot=snap)
            await lifecycle.on_quote_saved(self.tenant_id, self.lead, saved, changed=False, change_summary=None, portal_url=self._portal_url(saved))
        fit = None
        if budget_max_per_plate or self.lead.get("budget_max_per_plate"):
            bmax = Decimal(str(budget_max_per_plate or self.lead["budget_max_per_plate"]))
            fit = [p.tier for p in pkgs if p.per_plate <= bmax]
        return {"event_date": ev.isoformat(), "guest_count": guest_count, "diet": diet, "kitchen_capacity_left": capacity_left,
                "packages": [rounded_display(p) for p in pkgs], "within_budget": fit,
                "working_quote": {"quote_number": saved["quote_number"], "tier": saved["tier"], "portal_url": self._portal_url(saved)} if saved else None}

    async def t_modify_quote(self, tier: str | None = None, guest_count: int | None = None, diet: str | None = None,
                             add_items: list[str] | None = None, remove_items: list[str] | None = None) -> dict:
        prev = await qrepo.latest_quote(self.lead["id"])
        if not prev:
            return {"error": "no_quote", "message": "Call price_package first."}
        guest_count = int(guest_count or prev["guest_count"])
        diet = diet or prev["diet"]
        catalog = await load_catalog(self.tenant_id)
        if tier and tier != prev["tier"]:
            tpl = next((t for t in await load_templates(self.tenant_id) if t.tier == tier and t.diet == ("veg" if diet in ("veg", "jain") else diet)), None)
            slugs = list(tpl.item_slugs) if tpl else [i["slug"] for i in await qrepo.quote_items(prev["id"])]
        else:
            slugs = [i["slug"] for i in await qrepo.quote_items(prev["id"])]
        items = [catalog[s] for s in slugs if s in catalog]
        add = [_resolve_slug(x, catalog) for x in (add_items or [])]
        rem = [_resolve_slug(x, catalog, allow_tag=True) for x in (remove_items or [])]
        items, notes = modify_items(items, add=[a for a in add if a], remove=[r for r in rem if r], catalog=catalog)
        pkg, _, prices = await self._price_from_slugs(tier or prev["tier"], [i.slug for i in items], guest_count, diet)
        pkg.notes = notes + pkg.notes
        snap = market_snapshot(pkg, prices)
        # pkg.notes already carries the diet substitutions/removals, so a Jain switch that drops an
        # item the customer just asked for is reported instead of silently disappearing.
        changes = list(pkg.notes) + ([f"guests {prev['guest_count']} → {guest_count}"] if guest_count != prev["guest_count"] else []) + \
                  ([f"diet {prev['diet']} → {diet}"] if diet != prev["diet"] else [])
        ev_type = "guests_changed" if guest_count != prev["guest_count"] else "diet_changed" if diet != prev["diet"] else "item_added" if add else "item_removed"
        saved = await qrepo.save_quote(self.tenant_id, self.lead["id"], pkg, prev["event_date"], market_snapshot=snap, previous=prev,
                                       event_type=ev_type, event_payload={"changes": changes})
        await leads.update_lead_fields(self.lead["id"], {"guest_count": guest_count, "diet": diet})
        await lifecycle.on_quote_saved(self.tenant_id, self.lead, saved, changed=True, change_summary="; ".join(changes), portal_url=self._portal_url(saved))
        return {"quote_number": saved["quote_number"], "version": saved["version"], "changes": changes, "before_per_plate": str(prev["per_plate"]),
                **rounded_display(pkg), "portal_url": self._portal_url(saved)}

    async def t_festival_offers(self, apply: bool = False) -> dict:
        prev = await qrepo.latest_quote(self.lead["id"])
        if not prev:
            return {"error": "no_quote"}
        policy = await load_policy(self.tenant_id)
        ctx = QuoteContext(event_date=prev["event_date"], booking_date=date.today(), guest_count=prev["guest_count"], diet=prev["diet"], tier=prev["tier"] or "signature",
                           occasion=self.lead.get("occasion"), subtotal=Decimal(prev["subtotal"]) + Decimal(prev["surcharge_total"]),
                           cost_total=Decimal(prev["cost_total"]), per_plate=Decimal(prev["per_plate"]))
        offers = best_offers(await load_rules(self.tenant_id), ctx, policy.min_margin_pct)
        out = {"offers": [{"key": o.rule.key, "name": o.rule.name, "saves": str(o.amount), "explanation": o.explanation,
                           "festival": o.festival.name if o.festival else None, "margin_after_pct": str(o.margin_after_pct)} for o in offers],
               "before_total": str(prev["grand_total"]), "before_per_plate": str(prev["per_plate"])}
        if apply and offers:
            slugs = [i["slug"] for i in await qrepo.quote_items(prev["id"])]
            pkg, _, prices = await self._price_from_slugs(prev["tier"] or "signature", slugs, prev["guest_count"], prev["diet"], discounts=[o.as_applied() for o in offers])
            saved = await qrepo.save_quote(self.tenant_id, self.lead["id"], pkg, prev["event_date"], market_snapshot=market_snapshot(pkg, prices), previous=prev,
                                           event_type="discount_applied", event_payload={"offers": out["offers"]})
            out.update({"applied": True, "after_total": str(saved["grand_total"]), "after_per_plate": str(saved["per_plate"]),
                        "discount_total": str(saved["discount_total"]), "quote_number": saved["quote_number"], "version": saved["version"]})
        return out

    async def t_market_snapshot(self, ingredients: list[str] | None = None) -> dict:
        prev = await qrepo.latest_quote(self.lead["id"])
        prices = await load_prices(self.tenant_id)
        if prev and prev.get("market_snapshot"):
            snap = dict(prev["market_snapshot"])
            if ingredients:
                snap["ingredients"] = [{"key": p.key, "name": p.name, "unit": p.unit, "wholesale": str(p.wholesale), "retail": str(p.retail) if p.retail else None,
                                        "change_7d_pct": str(p.change_7d_pct)} for k in ingredients if (p := prices.get(k.lower()))]
            snap["as_of"] = datetime.now(UTC).date().isoformat()
            return snap
        keys = [k.lower() for k in (ingredients or ["chicken", "mutton", "paneer", "onion", "tomato", "rice"])]
        return {"as_of": date.today().isoformat(), "ingredients": [
            {"key": p.key, "name": p.name, "unit": p.unit, "wholesale": str(p.wholesale), "retail": str(p.retail) if p.retail else None, "change_7d_pct": str(p.change_7d_pct)}
            for k in keys if (p := prices.get(k))]}

    async def t_lock_price(self) -> dict:
        prev = await qrepo.latest_quote(self.lead["id"])
        if not prev:
            return {"error": "no_quote"}
        valid_until = datetime.combine(prev["event_date"], datetime.max.time(), tzinfo=UTC)
        lock = await qrepo.lock_quote(self.tenant_id, prev, valid_until)
        await lifecycle.on_price_locked(self.tenant_id, self.lead, prev, lock, self._portal_url(prev))
        await notify_owner_order("price_locked", lead=self.lead, customer=self.customer, quote=prev,
                                 per_plate=str(lock["locked_per_plate"]), total=str(lock["locked_total"]), valid_until=valid_until.date().isoformat())
        return {"locked": True, "quote_number": prev["quote_number"], "per_plate": str(lock["locked_per_plate"]), "total": str(lock["locked_total"]),
                "valid_until": valid_until.date().isoformat(), "certificate": lock["certificate_hash"][:12].upper(), "portal_url": self._portal_url(prev)}

    async def t_record_advance(self, pct: float | None = None) -> dict:
        prev = await qrepo.latest_quote(self.lead["id"])
        if not prev:
            return {"error": "no_quote"}
        pay = await qrepo.create_advance_payment(self.tenant_id, prev, pct or get_settings().advance_pct)
        await lifecycle.on_advance_requested(self.tenant_id, self.lead, prev, pay)
        await notify_owner_order("advance_requested", lead=self.lead, customer=self.customer, quote=prev, amount=str(pay["amount"]))
        out = {"amount": str(pay["amount"]), "payment_link": pay.get("payment_link") or f"{self._portal_url(prev)}#pay", "quote_number": prev["quote_number"],
               "cancellation_policy": "Full refund of advance up to 15 days before the event; 50% within 7 days; non-refundable within 72 hours."}
        card = None if pay.get("payment_link") else upi.payment_card(amount=pay["amount"], quote_number=prev["quote_number"], payment_id=str(pay["id"]), portal_token=prev.get("portal_token"))
        if card:
            out["upi"] = card
            out["how_to_pay"] = (f"A pay-by-UPI card with the exact amount (₹{out['amount']}) appears right under your message: one tap opens PhonePe, "
                                 f"Google Pay or any UPI app; on a laptop they scan the QR. "
                                 + (f"They can also pay directly to {card['phone']}. " if card.get("phone") else "")
                                 + "Ask them to reply with the 12-digit UTR from their app once paid, so we can confirm the date.")
        return out

    async def t_suggest_upsell(self) -> dict:
        from app.core import db
        prev = await qrepo.latest_quote(self.lead["id"])
        guests = prev["guest_count"] if prev else self.lead.get("guest_count") or 0
        rows = await db.fetch(
            """SELECT u.suggest_item_slug, u.attach_rate, u.message, mi.name, mc.suggested_price_per_guest
               FROM upsell_rules u JOIN menu_items mi ON mi.slug = u.suggest_item_slug AND mi.tenant_id = u.tenant_id
               LEFT JOIN menu_item_costs mc ON mc.menu_item_id = mi.id
               WHERE u.tenant_id = $1 AND u.is_active AND (u.guest_min IS NULL OR u.guest_min <= $2) AND (u.guest_max IS NULL OR u.guest_max >= $2)
                 AND (u.occasion IS NULL OR u.occasion = $3) AND (u.diet IS NULL OR u.diet::text = $4)
               ORDER BY u.attach_rate DESC LIMIT 3""",
            self.tenant_id, guests, self.lead.get("occasion"), (prev["diet"] if prev else self.lead.get("diet")) or "mixed")
        have = {i["slug"] for i in (await qrepo.quote_items(prev["id"]) if prev else [])}
        return {"suggestions": [{"slug": r["suggest_item_slug"], "name": r["name"], "attach_rate_pct": str(round(float(r["attach_rate"]) * 100)),
                                 "message": r["message"], "add_per_plate": str(r["suggested_price_per_guest"]) if r["suggested_price_per_guest"] else None}
                                for r in rows if r["suggest_item_slug"] not in have]}

    async def t_escalate_to_human(self, reason: str, summary: str, priority: str = "normal") -> dict:
        eid = await leads.create_escalation(self.tenant_id, self.lead["id"], reason, summary, priority)
        alerted = await notify_owner(lead=self.lead, customer=self.customer, reason=reason, summary=summary, priority=priority)
        return {"escalated": True, "escalation_id": str(eid), "owner_alerted": alerted, "eta": "within 2 hours (9am–9pm IST)"}


def _resolve_slug(x: str, catalog: dict, allow_tag: bool = False) -> str | None:
    x = x.strip().lower().replace(" ", "_")
    if x in catalog:
        return x
    for slug, item in catalog.items():
        if x.replace("_", " ") in item.name.lower():
            return slug
    if allow_tag:
        return x  # modify_items also matches tags (e.g. 'mutton')
    return None
