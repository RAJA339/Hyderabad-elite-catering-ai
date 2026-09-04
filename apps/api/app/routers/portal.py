"""Client portal: magic-link / WhatsApp-OTP access to a live quote."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.agent.handoff import notify_owner_order
from app.agent.orchestrator import handle_inbound
from app.core import db
from app.core.cache import rate_limit
from app.core.security import constant_time_eq, new_opaque_token, new_otp, token_hash
from app.leads import quotes as qrepo
from app.payments import upi
from app.routers.deps import default_tenant
from app.whatsapp.client import WhatsAppClient

router = APIRouter(prefix="/portal", tags=["portal"])


async def _quote_bundle(quote: dict) -> dict:
    items = await qrepo.quote_items(quote["id"])
    lead = await db.fetchrow("SELECT l.occasion, l.venue_area, l.guest_count, c.full_name FROM leads l JOIN customers c ON c.id=l.customer_id WHERE l.id=$1", quote["lead_id"])
    events = await db.fetch("SELECT type::text AS type, payload, per_plate_before, per_plate_after, created_at FROM quote_events WHERE quote_id IN (SELECT id FROM quotes WHERE quote_number=$1 AND tenant_id=$2) ORDER BY created_at DESC LIMIT 20", quote["quote_number"], quote["tenant_id"])
    payments = await db.fetch("SELECT id, kind, amount, status::text AS status, provider, provider_ref, payment_link, paid_at FROM payments WHERE quote_id IN (SELECT id FROM quotes WHERE quote_number=$1 AND tenant_id=$2) ORDER BY created_at", quote["quote_number"], quote["tenant_id"])
    # The pay-by-UPI card for the advance still owed, so the portal can collect it without any
    # payment gateway. A claimed UTR rides along so the card shows "we're confirming".
    pending = next((p for p in payments if p["kind"] == "advance" and p["status"] == "pending" and not p["payment_link"]), None)
    card = upi.payment_card(amount=pending["amount"], quote_number=quote["quote_number"], payment_id=str(pending["id"]), portal_token=quote.get("portal_token")) if pending else None
    if card:
        card["claimed_utr"] = pending["provider_ref"] if pending["provider"] == "upi" else None
    lock = await db.fetchrow("SELECT locked_per_plate, valid_until, certificate_hash FROM price_locks WHERE quote_id=$1", quote["id"])
    msgs = await db.fetch("SELECT role::text AS role, content, created_at FROM messages WHERE lead_id=$1 AND role IN ('customer','agent','human') ORDER BY created_at DESC LIMIT 40", quote["lead_id"])
    return {
        "quote": {k: v for k, v in quote.items() if k not in ("pricing_trace", "portal_token")},
        "items": [{"slug": i["slug"], "name": i["name"], "category": i["category_key"], "unit_price": i["unit_price"]} for i in items],
        "lead": dict(lead) if lead else {}, "events": [dict(e) for e in events], "payments": [dict(p) for p in payments],
        "lock": dict(lock) if lock else None, "chat": [dict(m) for m in reversed(msgs)], "upi": card,
    }


class UpiClaimIn(BaseModel):
    utr: str = Field(min_length=12, max_length=20)
    payment_id: str


@router.post("/{token}/upi-claim")
async def upi_claim(token: str, body: UpiClaimIn, tenant_id=Depends(default_tenant)):
    """The customer paid by UPI and typed the UTR their app showed. Record it against the
    advance and tell the owner to look for it; the owner confirms from the lead page."""
    if not await rate_limit(f"rl:upi:{token}", 5, 600):
        raise HTTPException(429, "too many attempts — please wait a few minutes")
    utr = upi.valid_utr(body.utr)
    if not utr:
        raise HTTPException(422, "A UTR is the 12-digit number your UPI app shows on the payment. Please check and try again.")
    quote = await qrepo.quote_by_portal_token(token)
    if not quote:
        raise HTTPException(404, "quote not found")
    pay = await db.fetchrow("UPDATE payments SET provider='upi', provider_ref=$3 WHERE id=$1::uuid AND quote_id=$2 AND status='pending' RETURNING *", body.payment_id, quote["id"], utr)
    if not pay:
        raise HTTPException(409, "this payment is already confirmed or does not belong to this quote")
    lead = await db.fetchrow("SELECT * FROM leads WHERE id=$1", quote["lead_id"])
    customer = await db.fetchrow("SELECT * FROM customers WHERE id=$1", lead["customer_id"])
    await notify_owner_order("upi_claimed", lead=dict(lead), customer=dict(customer), quote=dict(quote), amount=str(pay["amount"]), utr=utr)
    return {"ok": True, "status": "claimed", "utr": utr}


@router.get("/{token}")
async def get_quote(token: str):
    quote = await qrepo.quote_by_portal_token(token)
    if not quote:
        raise HTTPException(404, "quote not found")
    return await _quote_bundle(quote)


class ChangeIn(BaseModel):
    request: str = Field(min_length=3, max_length=500)


@router.post("/{token}/change")
async def request_change(token: str, body: ChangeIn, tenant_id=Depends(default_tenant)):
    quote = await qrepo.quote_by_portal_token(token)
    if not quote:
        raise HTTPException(404)
    if quote["status"] in ("locked", "accepted"):
        raise HTTPException(409, "price is locked; contact us on WhatsApp to modify")
    wa_id = await db.fetchval("SELECT c.wa_id FROM leads l JOIN customers c ON c.id=l.customer_id WHERE l.id=$1", quote["lead_id"])
    await db.execute("INSERT INTO quote_events (tenant_id, quote_id, type, actor_type, payload) VALUES ($1,$2,'change_requested','customer',$3)", tenant_id, quote["id"], {"request": body.request})
    r = await handle_inbound(tenant_id=tenant_id, wa_id=wa_id, text=body.request, channel="portal")
    fresh = await qrepo.latest_quote(quote["lead_id"])
    return {"reply": r.text, **(await _quote_bundle(fresh))}


class OtpRequest(BaseModel):
    phone: str = Field(min_length=10, max_length=15)


@router.post("/otp/request")
async def otp_request(body: OtpRequest, tenant_id=Depends(default_tenant)):
    wa_id = body.phone.lstrip("+")
    if not await rate_limit(f"rl:otp:{wa_id}", 3, 600):
        raise HTTPException(429, "too many requests")
    code = new_otp()
    await db.execute("INSERT INTO otp_codes (tenant_id, wa_id, code_hash, expires_at) VALUES ($1,$2,$3,$4)", tenant_id, wa_id, token_hash(code), datetime.now(UTC) + timedelta(minutes=10))
    await WhatsAppClient().send_text(wa_id, f"Your Hyderabad Elite Catering portal code is {code}. Valid 10 minutes.")
    return {"sent": True}


class OtpVerify(BaseModel):
    phone: str
    code: str


@router.post("/otp/verify")
async def otp_verify(body: OtpVerify, tenant_id=Depends(default_tenant)):
    wa_id = body.phone.lstrip("+")
    row = await db.fetchrow("SELECT id, code_hash, attempts FROM otp_codes WHERE tenant_id=$1 AND wa_id=$2 AND consumed_at IS NULL AND expires_at > now() ORDER BY expires_at DESC LIMIT 1", tenant_id, wa_id)
    if not row or row["attempts"] >= 5 or not constant_time_eq(row["code_hash"], token_hash(body.code)):
        if row:
            await db.execute("UPDATE otp_codes SET attempts = attempts + 1 WHERE id=$1", row["id"])
        raise HTTPException(401, "invalid code")
    await db.execute("UPDATE otp_codes SET consumed_at = now() WHERE id=$1", row["id"])
    cust = await db.fetchrow("SELECT id FROM customers WHERE tenant_id=$1 AND wa_id=$2", tenant_id, wa_id)
    if not cust:
        raise HTTPException(404, "no quotes for this number")
    quote = await db.fetchrow("SELECT q.portal_token FROM quotes q JOIN leads l ON l.id=q.lead_id WHERE l.customer_id=$1 ORDER BY q.created_at DESC LIMIT 1", cust["id"])
    session = new_opaque_token()
    await db.execute("INSERT INTO portal_sessions (tenant_id, customer_id, token_hash, method, expires_at) VALUES ($1,$2,$3,'wa_otp',$4)", tenant_id, cust["id"], token_hash(session), datetime.now(UTC) + timedelta(days=30))
    return {"session": session, "portal_token": quote["portal_token"] if quote else None}


@router.post("/{token}/share")
async def share(token: str, tenant_id=Depends(default_tenant)):
    quote = await qrepo.quote_by_portal_token(token)
    if not quote:
        raise HTTPException(404)
    slug = new_opaque_token(8)
    await db.execute("INSERT INTO share_links (tenant_id, quote_id, slug) VALUES ($1,$2,$3)", tenant_id, quote["id"], slug)
    from app.core.config import get_settings
    return {"url": f"{get_settings().public_web_url}/s/{slug}", "whatsapp_share": f"https://wa.me/?text=Check%20our%20catering%20quote%3A%20{get_settings().public_web_url}/s/{slug}"}


@router.get("/shared/{slug}")
async def shared(slug: str):
    row = await db.fetchrow("UPDATE share_links SET views = views + 1, last_viewed_at = now() WHERE slug=$1 RETURNING quote_id", slug)
    if not row:
        raise HTTPException(404)
    quote = await db.fetchrow("SELECT * FROM quotes WHERE id=$1", row["quote_id"])
    bundle = await _quote_bundle(dict(quote))
    bundle.pop("chat", None)
    bundle.pop("payments", None)
    return bundle
