"""Admin Command Center analytics."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core import db
from app.routers.deps import staff, tenant_from_principal

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/overview", dependencies=[Depends(staff)])
async def overview(tenant_id=Depends(tenant_from_principal)):
    pipeline = await db.fetch("SELECT stage::text AS stage, count(*) AS n, coalesce(sum(q.grand_total),0) AS value FROM leads l LEFT JOIN LATERAL (SELECT grand_total FROM quotes WHERE lead_id=l.id ORDER BY version DESC LIMIT 1) q ON true WHERE l.tenant_id=$1 GROUP BY stage", tenant_id)
    margin = await db.fetchrow(
        """SELECT round(avg(margin_pct),2) AS avg_margin, round(min(margin_pct),2) AS min_margin, count(*) AS quotes_30d,
                  coalesce(sum(grand_total) FILTER (WHERE status IN ('locked','accepted')),0) AS booked_value_30d
           FROM quotes WHERE tenant_id=$1 AND created_at > now() - interval '30 days'""", tenant_id)
    funnel = await db.fetchrow(
        """SELECT count(*) FILTER (WHERE source='whatsapp') AS wa_leads, count(*) FILTER (WHERE source='web_chat') AS web_leads,
                  count(*) FILTER (WHERE stage IN ('quoted','negotiating','locked','advance_paid','confirmed','completed')) AS quoted,
                  count(*) FILTER (WHERE stage IN ('locked','advance_paid','confirmed','completed')) AS locked,
                  count(*) FILTER (WHERE stage IN ('advance_paid','confirmed','completed')) AS paid
           FROM leads WHERE tenant_id=$1 AND created_at > now() - interval '90 days'""", tenant_id)
    clv = await db.fetchrow("SELECT round(avg(lifetime_value),0) AS avg_clv, round(avg(bookings_count),2) AS avg_bookings, count(*) FILTER (WHERE bookings_count>1) AS repeat_customers, count(*) AS customers FROM customers WHERE tenant_id=$1 AND deleted_at IS NULL", tenant_id)
    escal = await db.fetchval("SELECT count(*) FROM escalations WHERE tenant_id=$1 AND status='open'", tenant_id)
    return {"pipeline": [dict(r) for r in pipeline], "margin": dict(margin) if margin else {}, "funnel": dict(funnel) if funnel else {},
            "clv": dict(clv) if clv else {}, "open_escalations": escal}


@router.get("/kitchen-calendar", dependencies=[Depends(staff)])
async def kitchen_calendar(days: int = 60, tenant_id=Depends(tenant_from_principal)):
    rows = await db.fetch(
        """SELECT d::date AS day, coalesce(k.committed_guests,0) AS committed, coalesce(k.bookings,0) AS bookings, t.daily_guest_capacity AS capacity
           FROM generate_series(current_date, current_date + $2::int, '1 day') d
           CROSS JOIN tenants t LEFT JOIN kitchen_load k ON k.event_date = d::date AND k.tenant_id = t.id WHERE t.id = $1 ORDER BY d""", tenant_id, days)
    return {"days": [dict(r) for r in rows]}


@router.get("/festival-performance", dependencies=[Depends(staff)])
async def festival_performance(tenant_id=Depends(tenant_from_principal)):
    rows = await db.fetch(
        """SELECT f.key, f.name, f.starts_on, f.ends_on, count(q.id) AS quotes, count(q.id) FILTER (WHERE q.status IN ('locked','accepted')) AS booked,
                  coalesce(sum(q.grand_total) FILTER (WHERE q.status IN ('locked','accepted')),0) AS revenue,
                  coalesce(sum(da.amount),0) AS discounts_given, round(avg(q.margin_pct),2) AS avg_margin
           FROM festivals f LEFT JOIN quotes q ON q.tenant_id=$1 AND q.event_date BETWEEN f.starts_on - 3 AND f.ends_on
           LEFT JOIN discount_applications da ON da.quote_id=q.id
           WHERE f.tenant_id IS NULL OR f.tenant_id=$1 GROUP BY f.id ORDER BY f.starts_on""", tenant_id)
    return {"festivals": [dict(r) for r in rows]}


@router.get("/escalations", dependencies=[Depends(staff)])
async def escalations(tenant_id=Depends(tenant_from_principal)):
    rows = await db.fetch("SELECT e.*, c.full_name, c.phone FROM escalations e JOIN leads l ON l.id=e.lead_id JOIN customers c ON c.id=l.customer_id WHERE e.tenant_id=$1 AND e.status<>'resolved' ORDER BY e.created_at DESC", tenant_id)
    return {"escalations": [dict(r) for r in rows]}


@router.get("/rag-health", dependencies=[Depends(staff)])
async def rag_health(tenant_id=Depends(tenant_from_principal)):
    chunks = await db.fetchrow("SELECT count(*) AS chunks, count(DISTINCT source_id) AS sources, max(updated_at) AS last_indexed FROM rag_chunks WHERE tenant_id=$1 AND status='active'", tenant_id)
    q = await db.fetchrow("SELECT count(*) AS queries_7d, round(avg(latency_ms)) AS avg_latency_ms, round(avg(cache_hit::int)*100,1) AS cache_hit_pct FROM rag_queries WHERE tenant_id=$1 AND created_at > now() - interval '7 days'", tenant_id)
    ev = await db.fetchrow("SELECT ran_at, context_precision, context_recall, faithfulness, answer_relevancy FROM rag_eval_runs WHERE tenant_id=$1 ORDER BY ran_at DESC LIMIT 1", tenant_id)
    return {"index": dict(chunks) if chunks else {}, "queries": dict(q) if q else {}, "last_eval": dict(ev) if ev else None}
