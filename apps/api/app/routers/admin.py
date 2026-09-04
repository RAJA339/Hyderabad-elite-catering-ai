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


@router.get("/analytics", dependencies=[Depends(staff)])
async def analytics(days: int = 30, tenant_id=Depends(tenant_from_principal)):
    """Everything the Insights page draws, for one range, plus the same totals for the
    period before it so every headline carries a delta. One round trip; the page never
    stitches numbers from different windows."""
    days = max(7, min(int(days), 365))
    series = await db.fetch(
        """WITH d AS (SELECT generate_series(current_date - ($2::int - 1), current_date, '1 day')::date AS day)
           SELECT d.day,
                  (SELECT count(*) FROM leads l WHERE l.tenant_id=$1 AND l.created_at::date = d.day) AS leads,
                  (SELECT count(*) FROM leads l WHERE l.tenant_id=$1 AND l.created_at::date = d.day AND l.source='whatsapp') AS wa,
                  (SELECT count(*) FROM leads l WHERE l.tenant_id=$1 AND l.created_at::date = d.day AND l.source<>'whatsapp') AS web,
                  (SELECT count(*) FROM quotes q WHERE q.tenant_id=$1 AND q.created_at::date = d.day) AS quotes,
                  (SELECT coalesce(sum(grand_total),0) FROM quotes q WHERE q.tenant_id=$1 AND q.status IN ('locked','accepted') AND q.created_at::date = d.day) AS booked_value,
                  (SELECT coalesce(sum(amount),0) FROM payments p WHERE p.tenant_id=$1 AND p.status='paid' AND p.paid_at::date = d.day) AS paid_value,
                  (SELECT round(avg(margin_pct),1) FROM quotes q WHERE q.tenant_id=$1 AND q.created_at::date = d.day) AS avg_margin,
                  (SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms) FROM messages m JOIN leads l ON l.id=m.lead_id
                     WHERE l.tenant_id=$1 AND m.role='agent' AND m.latency_ms IS NOT NULL AND m.created_at::date = d.day) AS p50_latency_ms
           FROM d ORDER BY d.day""", tenant_id, days)

    async def totals(offset_days: int) -> dict:
        start, end = f"current_date - {offset_days + days - 1}", f"current_date - {offset_days} + 1"
        row = await db.fetchrow(
            f"""SELECT
                  (SELECT count(*) FROM leads WHERE tenant_id=$1 AND created_at >= {start} AND created_at < {end}) AS leads,
                  (SELECT count(*) FROM quotes WHERE tenant_id=$1 AND created_at >= {start} AND created_at < {end}) AS quotes,
                  (SELECT coalesce(sum(grand_total),0) FROM quotes WHERE tenant_id=$1 AND status IN ('locked','accepted') AND created_at >= {start} AND created_at < {end}) AS booked_value,
                  (SELECT coalesce(sum(amount),0) FROM payments WHERE tenant_id=$1 AND status='paid' AND paid_at >= {start} AND paid_at < {end}) AS paid_value,
                  (SELECT round(avg(margin_pct),1) FROM quotes WHERE tenant_id=$1 AND created_at >= {start} AND created_at < {end}) AS avg_margin,
                  (SELECT round(avg(per_plate),0) FROM quotes WHERE tenant_id=$1 AND created_at >= {start} AND created_at < {end}) AS avg_per_plate,
                  (SELECT count(*) FROM leads WHERE tenant_id=$1 AND stage IN ('advance_paid','confirmed','completed') AND created_at >= {start} AND created_at < {end}) AS paid_leads,
                  (SELECT count(*) FROM escalations WHERE tenant_id=$1 AND created_at >= {start} AND created_at < {end}) AS escalations,
                  (SELECT count(*) FROM leads l JOIN customers c ON c.id=l.customer_id WHERE l.tenant_id=$1 AND c.bookings_count > 1 AND l.created_at >= {start} AND l.created_at < {end}) AS repeat_leads""",
            tenant_id)
        r = dict(row)
        leads = int(r["leads"] or 0)
        return {"leads": leads, "quotes": int(r["quotes"] or 0), "booked_value": float(r["booked_value"] or 0), "paid_value": float(r["paid_value"] or 0),
                "avg_margin": float(r["avg_margin"]) if r["avg_margin"] is not None else None, "avg_per_plate": float(r["avg_per_plate"]) if r["avg_per_plate"] is not None else None,
                "conversion_pct": round(int(r["paid_leads"] or 0) / leads * 100, 1) if leads else None, "escalations": int(r["escalations"] or 0),
                "repeat_pct": round(int(r["repeat_leads"] or 0) / leads * 100, 1) if leads else None}

    funnel = await db.fetchrow(
        """SELECT count(*) AS leads,
                  count(*) FILTER (WHERE stage NOT IN ('new','qualifying','lost')) AS qualified,
                  count(*) FILTER (WHERE stage IN ('quoted','negotiating','locked','advance_paid','confirmed','completed')) AS quoted,
                  count(*) FILTER (WHERE stage IN ('locked','advance_paid','confirmed','completed')) AS locked,
                  count(*) FILTER (WHERE stage IN ('advance_paid','confirmed','completed')) AS paid
           FROM leads WHERE tenant_id=$1 AND created_at > current_date - $2::int""", tenant_id, days)
    tiers = await db.fetch(
        """SELECT coalesce(tier,'signature') AS tier, count(*) AS quotes, count(*) FILTER (WHERE status IN ('locked','accepted')) AS booked,
                  round(avg(per_plate),0) AS avg_per_plate, round(avg(margin_pct),1) AS avg_margin,
                  coalesce(sum(grand_total) FILTER (WHERE status IN ('locked','accepted')),0) AS value
           FROM quotes WHERE tenant_id=$1 AND created_at > current_date - $2::int GROUP BY 1
           ORDER BY array_position(ARRAY['classic','signature','royal'], coalesce(tier,'signature'))""", tenant_id, days)
    occasions = await db.fetch(
        """SELECT coalesce(l.occasion,'') AS occasion, count(*) AS leads,
                  coalesce(sum(q.grand_total),0) AS value
           FROM leads l LEFT JOIN LATERAL (SELECT grand_total FROM quotes WHERE lead_id=l.id AND status IN ('locked','accepted') ORDER BY version DESC LIMIT 1) q ON true
           WHERE l.tenant_id=$1 AND l.created_at > current_date - $2::int GROUP BY 1 ORDER BY leads DESC LIMIT 7""", tenant_id, days)
    bands = await db.fetch(
        """SELECT b.band, count(q.id) AS quotes, round(avg(q.per_plate),0) AS avg_per_plate, round(avg(q.margin_pct),1) AS avg_margin
           FROM (VALUES (1,'≤75',0,75),(2,'76–150',76,150),(3,'151–300',151,300),(4,'301–500',301,500)) AS b(ord,band,lo,hi)
           LEFT JOIN quotes q ON q.tenant_id=$1 AND q.guest_count BETWEEN b.lo AND b.hi AND q.created_at > current_date - $2::int
           GROUP BY b.ord, b.band ORDER BY b.ord""", tenant_id, days)
    hist = await db.fetch(
        """SELECT b.bucket, count(q.id) AS n
           FROM (VALUES (1,'<26%',-1,26),(2,'26–32%',26,32),(3,'32–38%',32,38),(4,'38–44%',38,44),(5,'44%+',44,999)) AS b(ord,bucket,lo,hi)
           LEFT JOIN quotes q ON q.tenant_id=$1 AND q.margin_pct >= b.lo AND q.margin_pct < b.hi AND q.created_at > current_date - $2::int
           GROUP BY b.ord, b.bucket ORDER BY b.ord""", tenant_id, days)
    kitchen = await db.fetch(
        """SELECT d::date AS day, coalesce(k.committed_guests,0) AS committed, coalesce(k.bookings,0) AS bookings, t.daily_guest_capacity AS capacity
           FROM generate_series(current_date, current_date + 59, '1 day') d
           CROSS JOIN tenants t LEFT JOIN kitchen_load k ON k.event_date = d::date AND k.tenant_id = t.id WHERE t.id = $1 ORDER BY d""", tenant_id)
    resp = await db.fetchrow(
        """SELECT count(*) AS replies, percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms) AS p50, percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95,
                  coalesce(sum(tokens_in),0) AS tokens_in, coalesce(sum(tokens_out),0) AS tokens_out
           FROM messages m JOIN leads l ON l.id=m.lead_id WHERE l.tenant_id=$1 AND m.role='agent' AND m.created_at > current_date - $2::int""", tenant_id, days)
    handoffs = await db.fetchval("SELECT count(DISTINCT lead_id) FROM escalations WHERE tenant_id=$1 AND created_at > current_date - $2::int", tenant_id, days)
    movers = await db.fetch(
        """WITH cur AS (SELECT ingredient_id, name, unit, price_per_unit FROM ingredient_current_prices WHERE tenant_id=$1 AND market='wholesale'),
                prev AS (SELECT DISTINCT ON (ingredient_id) ingredient_id, price_per_unit FROM ingredient_prices
                         WHERE tenant_id=$1 AND market='wholesale' AND observed_at <= now() - interval '7 days' ORDER BY ingredient_id, observed_at DESC)
           SELECT cur.name, cur.unit, cur.price_per_unit AS price,
                  coalesce(round((cur.price_per_unit - prev.price_per_unit) / NULLIF(prev.price_per_unit,0) * 100, 1), 0) AS change_7d
           FROM cur LEFT JOIN prev USING (ingredient_id) ORDER BY abs(coalesce((cur.price_per_unit - prev.price_per_unit) / NULLIF(prev.price_per_unit,0),0)) DESC LIMIT 6""", tenant_id)
    closep = await db.fetch(
        """SELECT b.bucket, count(l.id) AS n
           FROM (VALUES (1,'<30%',0,0.3),(2,'30–50%',0.3,0.5),(3,'50–70%',0.5,0.7),(4,'70%+',0.7,1.01)) AS b(ord,bucket,lo,hi)
           LEFT JOIN leads l ON l.tenant_id=$1 AND l.stage NOT IN ('completed','lost','advance_paid','confirmed') AND l.conversion_probability >= b.lo AND l.conversion_probability < b.hi
           GROUP BY b.ord, b.bucket ORDER BY b.ord""", tenant_id)

    f = dict(funnel) if funnel else {}
    cur, prev = await totals(0), await totals(days)
    num = lambda v: float(v) if v is not None else None  # noqa: E731
    return {
        "days": days,
        "series": [{"day": r["day"].isoformat(), "leads": int(r["leads"]), "wa": int(r["wa"]), "web": int(r["web"]), "quotes": int(r["quotes"]),
                    "booked_value": float(r["booked_value"]), "paid_value": float(r["paid_value"]), "avg_margin": num(r["avg_margin"]), "p50_latency_ms": num(r["p50_latency_ms"])} for r in series],
        "totals": cur, "prev_totals": prev,
        "funnel": [{"name": n, "value": int(f.get(k) or 0)} for n, k in (("Leads", "leads"), ("Qualified", "qualified"), ("Quoted", "quoted"), ("Price locked", "locked"), ("Advance paid", "paid"))],
        "tiers": [{"tier": r["tier"], "quotes": int(r["quotes"]), "booked": int(r["booked"]), "avg_per_plate": num(r["avg_per_plate"]), "avg_margin": num(r["avg_margin"]), "value": float(r["value"])} for r in tiers],
        "occasions": [{"occasion": r["occasion"], "leads": int(r["leads"]), "value": float(r["value"])} for r in occasions],
        "guest_bands": [{"band": r["band"], "quotes": int(r["quotes"]), "avg_per_plate": num(r["avg_per_plate"]), "avg_margin": num(r["avg_margin"])} for r in bands],
        "margin_hist": [{"bucket": r["bucket"], "n": int(r["n"])} for r in hist],
        "kitchen": [{"day": r["day"].isoformat(), "committed": int(r["committed"]), "capacity": int(r["capacity"]), "bookings": int(r["bookings"])} for r in kitchen],
        "response": {"p50_ms": num(resp["p50"]) if resp else None, "p95_ms": num(resp["p95"]) if resp else None, "tokens_in": int(resp["tokens_in"]) if resp else 0,
                     "tokens_out": int(resp["tokens_out"]) if resp else 0, "replies": int(resp["replies"]) if resp else 0,
                     "handoff_rate": round(int(handoffs or 0) / cur["leads"] * 100, 1) if cur["leads"] else None},
        "cost_movers": [{"name": r["name"], "unit": r["unit"], "price": float(r["price"]), "change_7d": float(r["change_7d"])} for r in movers],
        "close_probability": [{"bucket": r["bucket"], "n": int(r["n"])} for r in closep],
    }
