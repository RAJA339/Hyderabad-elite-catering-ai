"""Unauthenticated marketing surface: the live market ticker shown on the landing page.

Wholesale rates are the public claim the whole product rests on, so they are served without
auth. Costs, margins and prices stay behind the staff endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core import db
from app.routers.deps import default_tenant

router = APIRouter(prefix="/public", tags=["public"])

TICKER_KEYS = ("chicken", "mutton", "paneer", "onion", "tomato", "rice", "oil", "milk", "potato", "fish")


@router.get("/market-ticker")
async def market_ticker(tenant_id=Depends(default_tenant)):
    rows = await db.fetch(
        """WITH cur AS (
             SELECT ingredient_id, key, name, unit, price_per_unit, observed_at
             FROM ingredient_current_prices WHERE tenant_id = $1 AND market = 'wholesale'
           ), prev AS (
             SELECT DISTINCT ON (ingredient_id) ingredient_id, price_per_unit
             FROM ingredient_prices
             WHERE tenant_id = $1 AND market = 'wholesale' AND observed_at <= now() - interval '7 days'
             ORDER BY ingredient_id, observed_at DESC
           )
           SELECT cur.key, cur.name, cur.unit, cur.price_per_unit AS price, cur.observed_at,
                  COALESCE(round((cur.price_per_unit - prev.price_per_unit) / NULLIF(prev.price_per_unit, 0) * 100, 1), 0) AS change_7d
           FROM cur LEFT JOIN prev USING (ingredient_id)
           WHERE cur.key = ANY($2::text[])
           ORDER BY array_position($2::text[], cur.key)""",
        tenant_id, list(TICKER_KEYS),
    )
    return {
        "as_of": rows[0]["observed_at"].isoformat() if rows else None,
        "source": "Bowenpally wholesale",
        "prices": [
            {"key": r["key"], "name": r["name"], "unit": r["unit"], "price": str(r["price"]), "change_7d": float(r["change_7d"])}
            for r in rows
        ],
    }
