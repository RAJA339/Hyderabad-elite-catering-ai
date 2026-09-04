"""Quote persistence: immutable versions, events, locks, payments, portal tokens."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from app.core import db
from app.core.security import new_opaque_token
from app.pricing.models import PackagePrice


async def next_quote_number(tenant_id: UUID) -> str:
    n = await db.fetchval("SELECT count(DISTINCT quote_number) FROM quotes WHERE tenant_id = $1", tenant_id)
    return f"HEC-{date.today():%y%m}-{int(n) + 1:04d}"


async def save_quote(tenant_id: UUID, lead_id: UUID, pkg: PackagePrice, event_date: date, *, market_snapshot: dict | None,
                     previous: dict | None = None, event_type: str = "created", event_payload: dict | None = None, actor: str = "agent") -> dict:
    quote_number = previous["quote_number"] if previous else await next_quote_number(tenant_id)
    version = (previous["version"] + 1) if previous else 1
    async with db.transaction() as conn:
        if previous:
            await conn.execute("UPDATE quotes SET status = 'modified' WHERE id = $1 AND status IN ('draft','sent')", previous["id"])
        row = await conn.fetchrow(
            """INSERT INTO quotes (tenant_id, lead_id, quote_number, version, tier, guest_count, diet, event_date, status,
                 food_cost_total, cost_total, subtotal, discount_total, surcharge_total, tax_pct, tax_total, grand_total, per_plate, margin_pct,
                 market_snapshot, pricing_trace, portal_token, valid_until, created_by)
               VALUES ($1,$2,$3,$4,$5,$6,$7::diet_pref,$8,'sent',$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23) RETURNING *""",
            tenant_id, lead_id, quote_number, version, pkg.tier, pkg.guest_count, pkg.diet, event_date,
            pkg.food_cost_total, pkg.cost_total, pkg.subtotal, pkg.discount_total, pkg.surcharge_total, pkg.tax_pct, pkg.tax_total,
            pkg.grand_total, pkg.per_plate, pkg.margin_pct, market_snapshot, pkg.trace,
            previous["portal_token"] if previous and previous.get("portal_token") else new_opaque_token(24),
            datetime.now(UTC) + timedelta(days=7), actor,
        )
        for line in pkg.lines:
            await conn.execute(
                """INSERT INTO quote_items (quote_id, menu_item_id, category_key, name, qty_guests, unit_cost, unit_price, line_total, is_substitution, notes)
                   SELECT $1, id, $3, $4, $5, $6, $7, $8, $9, $10 FROM menu_items WHERE tenant_id = $11 AND slug = $2""",
                row["id"], line.slug, line.category_key, line.name, pkg.guest_count, line.unit_cost, line.unit_price, line.line_total, line.is_substitution, line.note, tenant_id,
            )
        for d in pkg.trace.get("discounts_applied", []):
            await conn.execute(
                """INSERT INTO discount_applications (tenant_id, quote_id, discount_rule_id, amount, margin_after_pct, explanation)
                   SELECT $1, $2, id, $4, $5, $6 FROM discount_rules WHERE tenant_id = $1 AND key = $3""",
                tenant_id, row["id"], d["key"], Decimal(d["amount"]), Decimal(d["margin_after_pct"]), d["explanation"],
            )
        await conn.execute(
            """INSERT INTO quote_events (tenant_id, quote_id, type, actor_type, payload, per_plate_before, per_plate_after)
               VALUES ($1,$2,$3::quote_event_type,$4,$5,$6,$7)""",
            tenant_id, row["id"], event_type, actor, event_payload or {"notes": pkg.notes},
            Decimal(previous["per_plate"]) if previous else None, pkg.per_plate,
        )
        await conn.execute("UPDATE leads SET stage = CASE WHEN stage IN ('new','qualifying','qualified') THEN 'quoted'::lead_stage ELSE stage END WHERE id = $1", lead_id)
    return dict(row)


async def latest_quote(lead_id: UUID) -> dict | None:
    row = await db.fetchrow("SELECT * FROM quotes WHERE lead_id = $1 ORDER BY version DESC LIMIT 1", lead_id)
    return dict(row) if row else None


async def quote_items(quote_id: UUID) -> list[dict]:
    rows = await db.fetch(
        "SELECT qi.*, mi.slug FROM quote_items qi JOIN menu_items mi ON mi.id = qi.menu_item_id WHERE quote_id = $1 ORDER BY category_key", quote_id)
    return [dict(r) for r in rows]


async def quote_by_portal_token(token: str) -> dict | None:
    row = await db.fetchrow("SELECT * FROM quotes WHERE portal_token = $1 ORDER BY version DESC LIMIT 1", token)
    return dict(row) if row else None


async def lock_quote(tenant_id: UUID, quote: dict, valid_until: datetime) -> dict:
    import hashlib

    cert = hashlib.sha256(f"{quote['id']}|{quote['per_plate']}|{quote['grand_total']}|{valid_until.isoformat()}".encode()).hexdigest()
    async with db.transaction() as conn:
        await conn.execute("UPDATE quotes SET status = 'locked', valid_until = $2 WHERE id = $1", quote["id"], valid_until)
        lock = await conn.fetchrow(
            """INSERT INTO price_locks (tenant_id, quote_id, locked_per_plate, locked_total, valid_until, certificate_hash)
               VALUES ($1,$2,$3,$4,$5,$6) RETURNING *""",
            tenant_id, quote["id"], quote["per_plate"], quote["grand_total"], valid_until, cert,
        )
        await conn.execute(
            "INSERT INTO quote_events (tenant_id, quote_id, type, actor_type, payload) VALUES ($1,$2,'locked','agent',$3)",
            tenant_id, quote["id"], {"valid_until": valid_until.isoformat(), "certificate_hash": cert},
        )
        await conn.execute("UPDATE leads SET stage = 'locked' WHERE id = $1", quote["lead_id"])
    return dict(lock)


async def create_advance_payment(tenant_id: UUID, quote: dict, pct: float) -> dict:
    amount = (Decimal(quote["grand_total"]) * Decimal(str(pct)) / Decimal("100")).quantize(Decimal("1"))
    link = await _razorpay_link(amount, quote)
    from app.payments import upi

    provider = "razorpay" if link else ("upi" if upi.configured() else "razorpay")
    row = await db.fetchrow(
        "INSERT INTO payments (tenant_id, quote_id, kind, amount, payment_link, provider) VALUES ($1,$2,'advance',$3,$4,$5) RETURNING *",
        tenant_id, quote["id"], amount, link, provider)
    return dict(row)


async def _razorpay_link(amount: Decimal, quote: dict) -> str | None:
    from app.core.config import get_settings

    s = get_settings()
    if not (s.razorpay_key_id and s.razorpay_key_secret):
        return None
    import httpx

    async with httpx.AsyncClient(auth=(s.razorpay_key_id, s.razorpay_key_secret), timeout=15) as client:
        r = await client.post("https://api.razorpay.com/v1/payment_links", json={
            "amount": int(amount * 100), "currency": "INR", "description": f"Advance for {quote['quote_number']}",
            "notes": {"quote_id": str(quote["id"])}, "reminder_enable": True,
        })
        r.raise_for_status()
        return r.json().get("short_url")


async def mark_payment_paid(provider_ref: str, quote_id: UUID, amount: Decimal) -> None:
    async with db.transaction() as conn:
        await conn.execute("UPDATE payments SET status='paid', paid_at=now(), provider_ref=$1 WHERE quote_id=$2 AND status='pending' AND kind='advance'", provider_ref, quote_id)
        await conn.execute("UPDATE quotes SET status='accepted' WHERE id=$1", quote_id)
        await conn.execute("""UPDATE leads SET stage='advance_paid' WHERE id = (SELECT lead_id FROM quotes WHERE id=$1)""", quote_id)
        await conn.execute("""UPDATE customers SET lifetime_value = lifetime_value + $2, bookings_count = bookings_count + 1
                              WHERE id = (SELECT l.customer_id FROM quotes q JOIN leads l ON l.id=q.lead_id WHERE q.id=$1)""", quote_id, amount)
