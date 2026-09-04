"""Razorpay webhook → mark advance paid → lifecycle."""
from __future__ import annotations

import hashlib
import hmac
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request

from app.agent.handoff import notify_owner_order
from app.core import db
from app.core.config import get_settings
from app.leads import lifecycle
from app.leads import quotes as qrepo

router = APIRouter(prefix="/webhooks/razorpay", tags=["payments"])


@router.post("")
async def razorpay(request: Request):
    body = await request.body()
    s = get_settings()
    if s.razorpay_key_secret:
        sig = request.headers.get("x-razorpay-signature", "")
        if not hmac.compare_digest(hmac.new(s.razorpay_key_secret.encode(), body, hashlib.sha256).hexdigest(), sig):
            raise HTTPException(401, "bad signature")
    payload = await request.json()
    if payload.get("event") != "payment_link.paid":
        return {"ignored": True}
    link = payload["payload"]["payment_link"]["entity"]
    quote_id = UUID(link["notes"]["quote_id"])
    await db.execute("INSERT INTO webhook_events (provider, external_id, payload, processed_at) VALUES ('razorpay',$1,$2,now()) ON CONFLICT DO NOTHING", link["id"], payload)
    await qrepo.mark_payment_paid(link["id"], quote_id, Decimal(link["amount_paid"]) / 100)
    quote = await db.fetchrow("SELECT * FROM quotes WHERE id=$1", quote_id)
    lead = await db.fetchrow("SELECT * FROM leads WHERE id=$1", quote["lead_id"])
    await lifecycle.on_event_completed(quote["tenant_id"], dict(lead), dict(quote))
    customer = await db.fetchrow("SELECT * FROM customers WHERE id=$1", lead["customer_id"])
    await notify_owner_order("advance_paid", lead=dict(lead), customer=dict(customer or {}), quote=dict(quote), amount=str(Decimal(link["amount_paid"]) / 100))
    return {"ok": True}
