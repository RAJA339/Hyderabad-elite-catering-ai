from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core import db
from app.pricing.ingestion import ManualCsvSource, ingest
from app.pricing.market import market_snapshot
from app.pricing.packages import build_tiers, rounded_display
from app.pricing.repository import load_catalog, load_policy, load_prices, load_templates
from app.routers.deps import manager, staff, tenant_from_principal

router = APIRouter(prefix="/pricing", tags=["pricing"])


class QuoteIn(BaseModel):
    guest_count: int = Field(gt=0, le=500)
    diet: Literal["veg", "non_veg", "mixed", "jain"]
    occasion: str | None = None
    event_date: date | None = None


@router.post("/quote", dependencies=[Depends(staff)])
async def quote(body: QuoteIn, tenant_id=Depends(tenant_from_principal)):
    prices = await load_prices(tenant_id)
    pkgs = build_tiers(templates=await load_templates(tenant_id), catalog=await load_catalog(tenant_id), prices=prices,
                       guest_count=body.guest_count, diet=body.diet, policy=await load_policy(tenant_id), occasion=body.occasion)
    return {"packages": [{**rounded_display(p), "market": market_snapshot(p, prices), "trace": p.trace} for p in pkgs]}


@router.get("/market", dependencies=[Depends(staff)])
async def market(tenant_id=Depends(tenant_from_principal)):
    rows = await db.fetch("SELECT key, name, unit, market, price_per_unit, observed_at, source FROM ingredient_current_prices WHERE tenant_id = $1 ORDER BY name, market", tenant_id)
    return {"prices": [dict(r) for r in rows]}


@router.get("/costs", dependencies=[Depends(staff)])
async def costs(tenant_id=Depends(tenant_from_principal)):
    rows = await db.fetch(
        """SELECT mi.slug, mi.name, c.key AS category, mi.diet::text AS diet, mc.food_cost_per_guest, mc.total_cost_per_guest, mc.suggested_price_per_guest,
                  mc.market_retail_equiv_per_guest, mc.cost_change_7d_pct, mc.computed_at
           FROM menu_item_costs mc JOIN menu_items mi ON mi.id = mc.menu_item_id JOIN menu_categories c ON c.id = mi.category_id
           WHERE mc.tenant_id = $1 ORDER BY c.sort_order, mi.name""", tenant_id)
    return {"items": [dict(r) for r in rows]}


class IngestIn(BaseModel):
    csv: str
    source_label: str = "manual"


@router.post("/ingest", dependencies=[Depends(manager)])
async def ingest_prices(body: IngestIn, tenant_id=Depends(tenant_from_principal)):
    return await ingest(tenant_id, [ManualCsvSource(body.csv, body.source_label)])


@router.get("/alerts", dependencies=[Depends(staff)])
async def alerts(tenant_id=Depends(tenant_from_principal)):
    rows = await db.fetch(
        """WITH cur AS (SELECT * FROM ingredient_current_prices WHERE tenant_id = $1 AND market = 'wholesale'),
                prev AS (SELECT DISTINCT ON (ingredient_id) ingredient_id, price_per_unit FROM ingredient_prices
                         WHERE tenant_id = $1 AND market='wholesale' AND observed_at <= now() - interval '7 days' ORDER BY ingredient_id, observed_at DESC)
           SELECT cur.key, cur.name, cur.unit, cur.price_per_unit AS now, prev.price_per_unit AS week_ago,
                  round((cur.price_per_unit - prev.price_per_unit) / NULLIF(prev.price_per_unit,0) * 100, 1) AS move_pct, i.alert_threshold_pct
           FROM cur JOIN prev ON prev.ingredient_id = cur.ingredient_id JOIN ingredients i ON i.id = cur.ingredient_id
           WHERE abs((cur.price_per_unit - prev.price_per_unit) / NULLIF(prev.price_per_unit,0) * 100) >= i.alert_threshold_pct
           ORDER BY abs(cur.price_per_unit - prev.price_per_unit) / NULLIF(prev.price_per_unit,0) DESC""", tenant_id)
    return {"alerts": [dict(r) for r in rows]}
