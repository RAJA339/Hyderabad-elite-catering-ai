from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from app.core import db
from app.festivals.rules import DiscountRule


async def load_rules(tenant_id: UUID) -> list[DiscountRule]:
    rows = await db.fetch("SELECT * FROM discount_rules WHERE tenant_id = $1 AND is_active ORDER BY priority", tenant_id)
    return [
        DiscountRule(
            key=r["key"], name=r["name"], kind=r["kind"], value=Decimal(r["value"]),
            explanation_template=r["explanation_template"], festival_key=r["festival_key"],
            booking_window_days_before_festival=r["booking_window_days_before_festival"],
            guest_min=r["guest_min"], guest_max=r["guest_max"], diet=r["diet"],
            occasions=tuple(r["occasions"] or ()), tiers=tuple(r["tiers"] or ()),
            min_margin_pct=Decimal(r["min_margin_pct"]) if r["min_margin_pct"] is not None else None,
            stackable=r["stackable"], priority=r["priority"], free_item_slug=r["free_item_slug"],
            valid_from=r["valid_from"], valid_to=r["valid_to"], is_active=r["is_active"],
        )
        for r in rows
    ]


async def sync_calendar(tenant_id: UUID | None = None) -> int:
    """Upsert the static calendar into `festivals` (global rows when tenant_id is None)."""
    from app.festivals.calendar import FESTIVALS

    n = 0
    async with db.transaction() as conn:
        for f in FESTIVALS:
            await conn.execute(
                """
                INSERT INTO festivals (tenant_id, key, name, region, starts_on, ends_on, demand_multiplier, tags)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
                ON CONFLICT (tenant_id, key) DO UPDATE SET starts_on=EXCLUDED.starts_on, ends_on=EXCLUDED.ends_on,
                  demand_multiplier=EXCLUDED.demand_multiplier, tags=EXCLUDED.tags
                """,
                tenant_id, f.key, f.name, f.region, f.starts_on, f.ends_on, f.demand_multiplier, list(f.tags),
            )
            n += 1
    return n
