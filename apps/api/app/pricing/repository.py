"""Loads catalog, prices and templates from Postgres into the pure pricing models."""
from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from app.core import db
from app.pricing.models import IngredientPrice, MenuItem, RecipeLine
from app.pricing.packages import PackageTemplate

D = Decimal


async def load_prices(tenant_id: UUID) -> dict[str, IngredientPrice]:
    rows = await db.fetch(
        """
        WITH latest AS (
          SELECT * FROM ingredient_current_prices WHERE tenant_id = $1
        ),
        week_ago AS (
          SELECT DISTINCT ON (ingredient_id) ingredient_id, price_per_unit
          FROM ingredient_prices
          WHERE tenant_id = $1 AND market = 'wholesale' AND observed_at <= now() - interval '7 days'
          ORDER BY ingredient_id, observed_at DESC
        )
        SELECT i.key, i.name, i.unit, i.is_volatile,
               w.price_per_unit AS wholesale, r.price_per_unit AS retail, w.observed_at,
               CASE WHEN wa.price_per_unit IS NULL OR wa.price_per_unit = 0 THEN 0
                    ELSE round((w.price_per_unit - wa.price_per_unit) / wa.price_per_unit * 100, 2) END AS change_7d
        FROM ingredients i
        JOIN latest w ON w.ingredient_id = i.id AND w.market = 'wholesale'
        LEFT JOIN latest r ON r.ingredient_id = i.id AND r.market = 'retail'
        LEFT JOIN week_ago wa ON wa.ingredient_id = i.id
        WHERE i.tenant_id = $1
        """,
        tenant_id,
    )
    return {
        r["key"]: IngredientPrice(
            key=r["key"], name=r["name"], unit=r["unit"], wholesale=D(r["wholesale"]),
            retail=D(r["retail"]) if r["retail"] is not None else None,
            change_7d_pct=D(r["change_7d"] or 0), is_volatile=r["is_volatile"],
        )
        for r in rows
    }


async def load_catalog(tenant_id: UUID) -> dict[str, MenuItem]:
    items = await db.fetch(
        """
        SELECT mi.id, mi.slug, mi.name, c.key AS category_key, mi.diet::text AS diet, mi.labour_cost_per_guest,
               mi.overhead_pct, mi.fixed_setup_cost, mi.is_live_counter, mi.is_jain_ok, mi.contains,
               mi.popularity, mi.tags
        FROM menu_items mi JOIN menu_categories c ON c.id = mi.category_id
        WHERE mi.tenant_id = $1 AND mi.is_active
        """,
        tenant_id,
    )
    recipes = await db.fetch(
        """
        SELECT mii.menu_item_id, i.key, mii.qty_per_guest, mii.waste_pct
        FROM menu_item_ingredients mii JOIN ingredients i ON i.id = mii.ingredient_id
        WHERE i.tenant_id = $1
        """,
        tenant_id,
    )
    by_item: dict[UUID, list[RecipeLine]] = {}
    for r in recipes:
        by_item.setdefault(r["menu_item_id"], []).append(RecipeLine(r["key"], D(r["qty_per_guest"]), D(r["waste_pct"])))
    return {
        r["slug"]: MenuItem(
            slug=r["slug"], name=r["name"], category_key=r["category_key"], diet=r["diet"],
            recipe=tuple(by_item.get(r["id"], [])), labour_cost_per_guest=D(r["labour_cost_per_guest"]),
            overhead_pct=D(r["overhead_pct"]), fixed_setup_cost=D(r["fixed_setup_cost"]),
            is_live_counter=r["is_live_counter"], is_jain_ok=r["is_jain_ok"], contains=tuple(r["contains"] or ()),
            popularity=r["popularity"], tags=tuple(r["tags"] or ()),
        )
        for r in items
    }


async def load_templates(tenant_id: UUID) -> list[PackageTemplate]:
    rows = await db.fetch(
        """
        SELECT pt.key, pt.tier, pt.diet::text AS diet, pt.guest_min, pt.guest_max, pt.occasions, pt.description,
               array_agg(mi.slug ORDER BY mi.slug) AS slugs
        FROM package_templates pt
        JOIN package_template_items pti ON pti.package_template_id = pt.id
        JOIN menu_items mi ON mi.id = pti.menu_item_id
        WHERE pt.tenant_id = $1 AND pt.is_active
        GROUP BY pt.id
        """,
        tenant_id,
    )
    return [
        PackageTemplate(
            key=r["key"], tier=r["tier"], diet=r["diet"], item_slugs=tuple(r["slugs"]), guest_min=r["guest_min"],
            guest_max=r["guest_max"], occasions=tuple(r["occasions"] or ()), description=r["description"] or "",
        )
        for r in rows
    ]


async def load_policy(tenant_id: UUID):
    from app.core.config import get_settings
    from app.pricing.engine import MarginPolicy

    row = await db.fetchrow("SELECT target_margin_pct, min_margin_pct, max_guests FROM tenants WHERE id = $1", tenant_id)
    s = get_settings()
    if not row:
        return MarginPolicy(D(str(s.target_margin_pct)), D(str(s.min_margin_pct)), D(str(s.gst_pct)), s.max_guests)
    return MarginPolicy(D(row["target_margin_pct"]), D(row["min_margin_pct"]), D(str(s.gst_pct)), min(row["max_guests"], 500))


async def kitchen_load(tenant_id: UUID, event_date) -> int:
    v = await db.fetchval("SELECT committed_guests FROM kitchen_load WHERE tenant_id = $1 AND event_date = $2", tenant_id, event_date)
    return int(v or 0)


async def refresh_item_costs(tenant_id: UUID) -> int:
    """Recompute cached menu_item_costs after a price ingestion. Returns rows written."""
    from app.pricing.costing import cost_item
    from app.pricing.engine import unit_price_for

    prices = await load_prices(tenant_id)
    catalog = await load_catalog(tenant_id)
    policy = await load_policy(tenant_id)
    n = 0
    async with db.transaction() as conn:
        for slug, item in catalog.items():
            try:
                c = cost_item(item, prices, 100)
            except KeyError:
                continue
            await conn.execute(
                """
                INSERT INTO menu_item_costs (menu_item_id, tenant_id, food_cost_per_guest, total_cost_per_guest,
                    suggested_price_per_guest, market_retail_equiv_per_guest, cost_change_7d_pct, computed_at)
                SELECT id, $1, $3, $4, $5, $6, $7, now() FROM menu_items WHERE tenant_id = $1 AND slug = $2
                ON CONFLICT (menu_item_id) DO UPDATE SET food_cost_per_guest = EXCLUDED.food_cost_per_guest,
                    total_cost_per_guest = EXCLUDED.total_cost_per_guest,
                    suggested_price_per_guest = EXCLUDED.suggested_price_per_guest,
                    market_retail_equiv_per_guest = EXCLUDED.market_retail_equiv_per_guest,
                    cost_change_7d_pct = EXCLUDED.cost_change_7d_pct, computed_at = now()
                """,
                tenant_id, slug, c.food_cost_per_guest, c.total_cost_per_guest,
                unit_price_for(c.total_cost_per_guest, policy), c.market_retail_equiv_per_guest, c.cost_change_7d_pct,
            )
            n += 1
    return n
