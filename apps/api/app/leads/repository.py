"""Customers, consent, leads and messages — the customer data vault."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from app.core import db


async def tenant_id_for_slug(slug: str) -> UUID:
    tid = await db.fetchval("SELECT id FROM tenants WHERE slug = $1", slug)
    if not tid:
        raise RuntimeError(f"tenant '{slug}' not found; run db/seed/seed.sql")
    return tid


async def get_or_create_customer(tenant_id: UUID, wa_id: str, name: str | None = None) -> dict:
    row = await db.fetchrow(
        """INSERT INTO customers (tenant_id, wa_id, phone, full_name) VALUES ($1,$2,$3,$4)
           ON CONFLICT (tenant_id, wa_id) DO UPDATE SET last_seen_at = now(), full_name = COALESCE(customers.full_name, EXCLUDED.full_name)
           RETURNING *""",
        tenant_id, wa_id, "+" + wa_id, name,
    )
    return dict(row)


async def has_consent(customer_id: UUID, purpose: str = "communication") -> bool:
    return bool(await db.fetchval(
        "SELECT granted FROM consents WHERE customer_id = $1 AND purpose = $2::consent_purpose AND revoked_at IS NULL", customer_id, purpose))


async def record_consent(tenant_id: UUID, customer_id: UUID, purpose: str, granted: bool, evidence: dict) -> None:
    await db.execute(
        """INSERT INTO consents (tenant_id, customer_id, purpose, granted, evidence)
           VALUES ($1,$2,$3::consent_purpose,$4,$5)
           ON CONFLICT (customer_id, purpose) DO UPDATE SET granted = EXCLUDED.granted, evidence = EXCLUDED.evidence,
             granted_at = now(), revoked_at = CASE WHEN EXCLUDED.granted THEN NULL ELSE now() END""",
        tenant_id, customer_id, purpose, granted, evidence,
    )


async def get_or_create_open_lead(tenant_id: UUID, customer_id: UUID, source: str = "whatsapp") -> dict:
    row = await db.fetchrow(
        """SELECT * FROM leads WHERE tenant_id = $1 AND customer_id = $2 AND stage NOT IN ('completed','lost')
           ORDER BY created_at DESC LIMIT 1""",
        tenant_id, customer_id,
    )
    if row:
        return dict(row)
    row = await db.fetchrow(
        "INSERT INTO leads (tenant_id, customer_id, source) VALUES ($1,$2,$3::lead_source) RETURNING *", tenant_id, customer_id, source)
    await audit(tenant_id, "agent", None, "lead.created", "lead", str(row["id"]), None, {"source": source})
    return dict(row)


async def get_lead(lead_id: UUID) -> dict | None:
    row = await db.fetchrow("SELECT * FROM leads WHERE id = $1", lead_id)
    return dict(row) if row else None


async def update_lead_fields(lead_id: UUID, fields: dict[str, Any], qualification: dict | None = None) -> dict:
    allowed = {"occasion", "event_date", "event_time", "guest_count", "diet", "venue_name", "venue_area", "venue_address",
               "budget_min_per_plate", "budget_max_per_plate", "stage", "conversion_probability", "handoff_active", "lost_reason"}
    sets, args = [], []
    for k, v in fields.items():
        if k not in allowed or v is None:
            continue
        args.append(v)
        cast = "::lead_stage" if k == "stage" else "::diet_pref" if k == "diet" else ""
        sets.append(f"{k} = ${len(args)}{cast}")
    if qualification is not None:
        args.append(qualification)
        sets.append(f"qualification = ${len(args)}")
    if not sets:
        return await get_lead(lead_id) or {}
    args.append(lead_id)
    row = await db.fetchrow(f"UPDATE leads SET {', '.join(sets)} WHERE id = ${len(args)} RETURNING *", *args)
    return dict(row)


async def set_stage(tenant_id: UUID, lead_id: UUID, stage: str, actor: str = "agent") -> None:
    before = await db.fetchval("SELECT stage::text FROM leads WHERE id = $1", lead_id)
    if before == stage:
        return
    await db.execute("UPDATE leads SET stage = $2::lead_stage WHERE id = $1", lead_id, stage)
    await audit(tenant_id, actor, None, "lead.stage_changed", "lead", str(lead_id), {"stage": before}, {"stage": stage})


async def store_message(tenant_id: UUID, lead_id: UUID, role: str, content: str | None, *, kind: str = "text", external_id: str | None = None,
                        media: dict | None = None, tool_calls: list | None = None, rag_query_id: UUID | None = None,
                        tokens_in: int = 0, tokens_out: int = 0, latency_ms: int | None = None, transcript: str | None = None) -> UUID:
    return await db.fetchval(
        """INSERT INTO messages (tenant_id, lead_id, role, kind, external_id, content, transcript, media, tool_calls, rag_query_id, tokens_in, tokens_out, latency_ms)
           VALUES ($1,$2,$3::message_role,$4::message_kind,$5,$6,$7,$8,$9,$10,$11,$12,$13)
           ON CONFLICT (tenant_id, external_id) DO UPDATE SET status = messages.status RETURNING id""",
        tenant_id, lead_id, role, kind, external_id, content, transcript, media, tool_calls, rag_query_id, tokens_in, tokens_out, latency_ms,
    )


async def recent_messages(lead_id: UUID, limit: int = 20) -> list[dict]:
    rows = await db.fetch(
        "SELECT role::text AS role, content, transcript, created_at FROM messages WHERE lead_id = $1 ORDER BY created_at DESC LIMIT $2", lead_id, limit)
    return [dict(r) for r in reversed(rows)]


async def audit(tenant_id: UUID, actor_type: str, actor_id: str | None, action: str, entity_type: str, entity_id: str, before: dict | None, after: dict | None) -> None:
    await db.execute(
        "INSERT INTO audit_log (tenant_id, actor_type, actor_id, action, entity_type, entity_id, before, after) VALUES ($1,$2,$3,$4,$5,$6,$7,$8)",
        tenant_id, actor_type, actor_id, action, entity_type, entity_id, before, after,
    )


async def create_escalation(tenant_id: UUID, lead_id: UUID, reason: str, summary: str, priority: str = "normal") -> UUID:
    eid = await db.fetchval(
        "INSERT INTO escalations (tenant_id, lead_id, reason, summary, priority) VALUES ($1,$2,$3,$4,$5) RETURNING id",
        tenant_id, lead_id, reason, summary, priority)
    await db.execute("UPDATE leads SET handoff_active = true WHERE id = $1", lead_id)
    return eid


async def erase_customer(tenant_id: UUID, customer_id: UUID) -> None:
    """DPDP erasure: anonymise PII, keep financial rows."""
    await db.execute(
        """UPDATE customers SET full_name = NULL, email = NULL, address = NULL, phone = 'erased', wa_id = 'erased:' || id::text,
           deleted_at = now() WHERE id = $1 AND tenant_id = $2""", customer_id, tenant_id)
    await db.execute("UPDATE messages SET content = '[erased]', transcript = NULL, media = NULL WHERE lead_id IN (SELECT id FROM leads WHERE customer_id = $1)", customer_id)
    await audit(tenant_id, "system", None, "customer.erased", "customer", str(customer_id), None, None)
