from __future__ import annotations

import csv
import io
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core import db
from app.core.security import Principal
from app.leads import repository as leads
from app.routers.deps import manager, owner, staff, tenant_from_principal

router = APIRouter(prefix="/leads", tags=["leads"])


@router.get("", dependencies=[Depends(staff)])
async def list_leads(stage: str | None = None, limit: int = 100, tenant_id=Depends(tenant_from_principal)):
    rows = await db.fetch(
        """SELECT l.id, l.stage::text AS stage, l.source::text AS source, l.occasion, l.event_date, l.guest_count, l.diet::text AS diet, l.venue_area,
                  l.conversion_probability, l.handoff_active, l.created_at, l.updated_at, c.full_name, c.phone,
                  (SELECT grand_total FROM quotes q WHERE q.lead_id = l.id ORDER BY version DESC LIMIT 1) AS latest_total,
                  (SELECT per_plate FROM quotes q WHERE q.lead_id = l.id ORDER BY version DESC LIMIT 1) AS latest_per_plate
           FROM leads l JOIN customers c ON c.id = l.customer_id
           WHERE l.tenant_id = $1 AND ($2::text IS NULL OR l.stage::text = $2) ORDER BY l.updated_at DESC LIMIT $3""", tenant_id, stage, limit)
    return {"leads": [dict(r) for r in rows]}


@router.get("/{lead_id}", dependencies=[Depends(staff)])
async def get_lead(lead_id: UUID, tenant_id=Depends(tenant_from_principal)):
    lead = await db.fetchrow("SELECT l.*, c.full_name, c.phone, c.wa_id FROM leads l JOIN customers c ON c.id=l.customer_id WHERE l.id=$1 AND l.tenant_id=$2", lead_id, tenant_id)
    if not lead:
        raise HTTPException(404)
    msgs = await db.fetch("SELECT id, role::text AS role, kind::text AS kind, content, transcript, tool_calls, created_at FROM messages WHERE lead_id=$1 ORDER BY created_at", lead_id)
    quotes = await db.fetch("SELECT id, quote_number, version, tier, status::text AS status, guest_count, per_plate, grand_total, margin_pct, created_at FROM quotes WHERE lead_id=$1 ORDER BY version DESC", lead_id)
    events = await db.fetch("SELECT e.type::text AS type, e.actor_type, e.payload, e.per_plate_before, e.per_plate_after, e.created_at FROM quote_events e JOIN quotes q ON q.id=e.quote_id WHERE q.lead_id=$1 ORDER BY e.created_at", lead_id)
    return {"lead": dict(lead), "messages": [dict(m) for m in msgs], "quotes": [dict(q) for q in quotes], "events": [dict(e) for e in events]}


class StageIn(BaseModel):
    stage: str
    lost_reason: str | None = None


@router.post("/{lead_id}/stage")
async def set_stage(lead_id: UUID, body: StageIn, p: Principal = Depends(staff)):
    await leads.set_stage(UUID(p.tenant_id), lead_id, body.stage, actor="human")
    if body.lost_reason:
        await db.execute("UPDATE leads SET lost_reason=$2 WHERE id=$1", lead_id, body.lost_reason)
    return {"ok": True}


class HumanReplyIn(BaseModel):
    text: str
    return_to_ai: bool = False


@router.post("/{lead_id}/reply")
async def human_reply(lead_id: UUID, body: HumanReplyIn, p: Principal = Depends(staff)):
    from app.whatsapp.client import WhatsAppClient

    row = await db.fetchrow("SELECT c.wa_id FROM leads l JOIN customers c ON c.id=l.customer_id WHERE l.id=$1 AND l.tenant_id=$2", lead_id, UUID(p.tenant_id))
    if not row:
        raise HTTPException(404)
    res = await WhatsAppClient().send_text(row["wa_id"], body.text)
    await leads.store_message(UUID(p.tenant_id), lead_id, "human", body.text, external_id=res.get("id"))
    if body.return_to_ai:
        await db.execute("UPDATE leads SET handoff_active=false WHERE id=$1", lead_id)
        await db.execute("UPDATE escalations SET status='resolved', resolved_at=now() WHERE lead_id=$1 AND status<>'resolved'", lead_id)
    return {"ok": True, "message_id": res.get("id")}


@router.get("/export/customers.csv", dependencies=[Depends(manager)])
async def export_customers(tenant_id=Depends(tenant_from_principal)):
    rows = await db.fetch(
        """SELECT c.full_name, c.phone, c.area, c.lifetime_value, c.bookings_count, c.first_seen_at, c.last_seen_at,
                  bool_or(k.granted) FILTER (WHERE k.purpose='marketing') AS marketing_consent
           FROM customers c LEFT JOIN consents k ON k.customer_id=c.id WHERE c.tenant_id=$1 AND c.deleted_at IS NULL GROUP BY c.id ORDER BY c.lifetime_value DESC""", tenant_id)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["name", "phone", "area", "lifetime_value", "bookings", "first_seen", "last_seen", "marketing_consent"])
    for r in rows:
        w.writerow([r["full_name"], r["phone"], r["area"], r["lifetime_value"], r["bookings_count"], r["first_seen_at"], r["last_seen_at"], r["marketing_consent"]])
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=customers.csv"})


@router.delete("/customers/{customer_id}", dependencies=[Depends(owner)])
async def erase(customer_id: UUID, tenant_id=Depends(tenant_from_principal)):
    await leads.erase_customer(tenant_id, customer_id)
    return {"erased": True}
