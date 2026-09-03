from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends

from app.core import db
from app.festivals.calendar import FESTIVALS, festivals_around
from app.routers.deps import staff, tenant_from_principal

router = APIRouter(prefix="/festivals", tags=["festivals"])


@router.get("")
async def calendar(near: date | None = None):
    fs = festivals_around(near) if near else FESTIVALS
    return {"festivals": [f.__dict__ for f in fs]}


@router.get("/rules", dependencies=[Depends(staff)])
async def rules(tenant_id=Depends(tenant_from_principal)):
    rows = await db.fetch("SELECT key, name, kind::text AS kind, value, festival_key, booking_window_days_before_festival, guest_min, guest_max, diet::text AS diet, stackable, priority, explanation_template, is_active FROM discount_rules WHERE tenant_id=$1 ORDER BY priority", tenant_id)
    return {"rules": [dict(r) for r in rows]}
