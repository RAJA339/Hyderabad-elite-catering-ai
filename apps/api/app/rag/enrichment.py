"""Live enrichment: attach current per-plate costs / prices and festival context to retrieved
chunks. Vector store never holds these numbers."""
from __future__ import annotations

import re
from datetime import date
from uuid import UUID

from app.core import db
from app.festivals.calendar import festivals_around
from app.rag.store import Hit

_SLUG = re.compile(r"\(slug:\s*([a-z0-9_\-]+)\)")


async def enrich(tenant_id: UUID, hits: list[Hit], event_date: date | None) -> dict:
    slugs: set[str] = set()
    for h in hits:
        slugs.update(_SLUG.findall(h.content))
        for s in h.metadata.get("item_slugs", []) or []:
            slugs.add(s)
    prices: dict[str, dict] = {}
    if slugs:
        rows = await db.fetch(
            """SELECT mi.slug, mc.total_cost_per_guest, mc.suggested_price_per_guest, mc.cost_change_7d_pct, mc.computed_at
               FROM menu_item_costs mc JOIN menu_items mi ON mi.id = mc.menu_item_id
               WHERE mc.tenant_id = $1 AND mi.slug = ANY($2::text[])""",
            tenant_id, list(slugs),
        )
        prices = {r["slug"]: {"price_per_guest": str(r["suggested_price_per_guest"]), "change_7d_pct": str(r["cost_change_7d_pct"]),
                              "as_of": r["computed_at"].isoformat()} for r in rows}
    margin = await db.fetchrow("SELECT target_margin_pct, min_margin_pct FROM tenants WHERE id = $1", tenant_id)
    fests = festivals_around(event_date) if event_date else []
    return {
        "live_item_prices": prices,
        "margin_policy": {"target_pct": str(margin["target_margin_pct"]), "min_pct": str(margin["min_margin_pct"])} if margin else {},
        "festivals_near_event": [{"key": f.key, "name": f.name, "starts_on": f.starts_on.isoformat(), "ends_on": f.ends_on.isoformat()} for f in fests],
    }
