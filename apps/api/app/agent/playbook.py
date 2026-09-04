"""What the business has learned about itself, computed from its own closed deals.

Anvi should not sell the same way in month six as she did in week one. Every quote that was
locked or paid, and every lead marked lost, is evidence: which tier wins a housewarming,
what per-plate the 300-guest weddings actually accept, which dishes show up in the menus
people book. This module turns that history into a short, factual briefing that is injected
into her system prompt.

Two deliberate limits:

- It is derived, never invented. Every line comes from an aggregate over this tenant's own
  quotes; with too little history a section is simply absent rather than guessed at.
- It is internal. The numbers here describe our own book, not a price for any customer, so
  the prompt marks them as guidance for *framing and menu design* only. The hard rule that
  every rupee shown to a customer comes from a tool call is unchanged.

Recomputed on a TTL rather than per message: it moves on the timescale of bookings, and one
aggregate query per conversation would be waste.
"""
from __future__ import annotations

import time
from typing import Any
from uuid import UUID

from app.core import db
from app.core.logging import get_logger

log = get_logger("playbook")

TTL_S = 900
MIN_SAMPLE = 5          # below this a section is not reported at all
_cache: dict[str, tuple[float, dict]] = {}

WON_QUOTE = "q.status IN ('locked','accepted')"
LOST_LEAD = "l.stage = 'lost'"


async def compute(tenant_id: UUID, days: int = 180) -> dict:
    """Aggregate the tenant's recent history into learnable facts."""
    out: dict[str, Any] = {"window_days": days}

    out["by_occasion"] = [dict(r) for r in await db.fetch(
        f"""SELECT coalesce(l.occasion,'other') AS occasion,
                   count(*) FILTER (WHERE {WON_QUOTE}) AS won,
                   count(*) AS quoted,
                   round(percentile_cont(0.5) WITHIN GROUP (ORDER BY q.per_plate) FILTER (WHERE {WON_QUOTE})) AS won_per_plate,
                   mode() WITHIN GROUP (ORDER BY q.tier) FILTER (WHERE {WON_QUOTE}) AS won_tier,
                   round(avg(q.guest_count) FILTER (WHERE {WON_QUOTE})) AS won_guests
            FROM quotes q JOIN leads l ON l.id = q.lead_id
            WHERE q.tenant_id = $1 AND q.created_at > now() - ($2::int || ' days')::interval
            GROUP BY 1 HAVING count(*) >= $3 ORDER BY won DESC NULLS LAST LIMIT 6""",
        tenant_id, days, MIN_SAMPLE)]

    out["price_band"] = [dict(r) for r in await db.fetch(
        f"""SELECT b.band,
                   round(percentile_cont(0.5) WITHIN GROUP (ORDER BY q.per_plate) FILTER (WHERE {WON_QUOTE})) AS won_per_plate,
                   round(percentile_cont(0.5) WITHIN GROUP (ORDER BY q.per_plate) FILTER (WHERE {LOST_LEAD})) AS lost_per_plate,
                   count(*) FILTER (WHERE {WON_QUOTE}) AS won, count(*) AS quoted
            FROM (VALUES (1,'up to 75',0,75),(2,'76-150',76,150),(3,'151-300',151,300),(4,'301-500',301,500)) AS b(ord,band,lo,hi)
            JOIN quotes q ON q.tenant_id = $1 AND q.guest_count BETWEEN b.lo AND b.hi AND q.created_at > now() - ($2::int || ' days')::interval
            JOIN leads l ON l.id = q.lead_id
            GROUP BY b.ord, b.band HAVING count(*) >= $3 ORDER BY b.ord""",
        tenant_id, days, MIN_SAMPLE)]

    out["winning_items"] = [dict(r) for r in await db.fetch(
        f"""SELECT i.name, count(*) AS n
            FROM quote_items i JOIN quotes q ON q.id = i.quote_id
            WHERE q.tenant_id = $1 AND {WON_QUOTE} AND q.created_at > now() - ($2::int || ' days')::interval
            GROUP BY 1 ORDER BY n DESC LIMIT 8""",
        tenant_id, days)]

    # What separates a booking from a lost lead: how fast we replied, how many turns it took.
    out["shape_of_a_win"] = dict(await db.fetchrow(
        f"""SELECT round(avg(t.turns) FILTER (WHERE t.won)) AS turns_to_win,
                   round(avg(t.turns) FILTER (WHERE NOT t.won)) AS turns_when_lost,
                   count(*) FILTER (WHERE t.won) AS wins, count(*) AS closed
            FROM (SELECT l.id, {LOST_LEAD} IS FALSE AND l.stage IN ('advance_paid','confirmed','completed') AS won,
                         (SELECT count(*) FROM messages m WHERE m.lead_id = l.id AND m.role = 'customer') AS turns
                  FROM leads l
                  WHERE l.tenant_id = $1 AND l.created_at > now() - ($2::int || ' days')::interval
                    AND (l.stage = 'lost' OR l.stage IN ('advance_paid','confirmed','completed'))) t""",
        tenant_id, days) or {})

    out["objections"] = [dict(r) for r in await db.fetch(
        """SELECT reason, count(*) AS n FROM escalations
           WHERE tenant_id = $1 AND created_at > now() - ($2::int || ' days')::interval
           GROUP BY 1 ORDER BY n DESC LIMIT 5""",
        tenant_id, days)]
    return out


def render(p: dict) -> str:
    """The briefing, as it appears in the prompt. Empty when there is nothing learned yet."""
    lines: list[str] = []

    occ = [o for o in p.get("by_occasion", []) if o.get("won")]
    if occ:
        lines.append("What books, by occasion (our own closed deals):")
        for o in occ:
            rate = round(int(o["won"]) / max(int(o["quoted"]), 1) * 100)
            bits = [f"{str(o['occasion']).replace('_', ' ')}: {o['won']}/{o['quoted']} booked ({rate}%)"]
            if o.get("won_tier"):
                bits.append(f"usually {o['won_tier']}")
            if o.get("won_guests"):
                bits.append(f"~{int(o['won_guests'])} guests")
            if o.get("won_per_plate"):
                bits.append(f"median accepted ₹{int(o['won_per_plate'])}/plate [internal]")
            lines.append("- " + ", ".join(bits))

    bands = [b for b in p.get("price_band", []) if b.get("won_per_plate") and b.get("lost_per_plate")]
    if bands:
        lines.append("Where price starts costing us the booking [internal]:")
        for b in bands:
            won, lost = int(b["won_per_plate"]), int(b["lost_per_plate"])
            verdict = "quotes we lose are priced higher" if lost > won else "price is not what loses these"
            lines.append(f"- {b['band']} guests: accepted ₹{won}, lost ₹{lost} — {verdict}")

    items = p.get("winning_items", [])
    if items:
        lines.append("Dishes that appear most in menus people actually book: "
                     + ", ".join(f"{i['name']}" for i in items[:8]) + ".")

    s = p.get("shape_of_a_win") or {}
    if s.get("turns_to_win") and s.get("wins"):
        lines.append(f"Bookings typically close in about {int(s['turns_to_win'])} customer messages "
                     f"(lost leads averaged {int(s['turns_when_lost'] or 0)}). Get to a priced menu early.")

    obj = p.get("objections", [])
    if obj:
        lines.append("Most common reasons a person was needed: " + ", ".join(f"{o['reason']} ({o['n']})" for o in obj) + ".")

    if not lines:
        return ""
    return ("## What we have learned from our own bookings\n"
            "Derived from this kitchen's closed deals in the last "
            f"{p.get('window_days', 180)} days. Use it to choose which menu and tier to lead with, and how to frame\n"
            "the conversation. Figures marked [internal] describe our own book — never say them to a customer,\n"
            "and never treat them as a price: every rupee you quote still comes from a tool call.\n"
            + "\n".join(lines))


async def briefing(tenant_id: UUID) -> str:
    """Cached render(). Safe: any failure returns an empty briefing rather than breaking a reply."""
    key = str(tenant_id)
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < TTL_S:
        return render(hit[1])
    try:
        p = await compute(tenant_id)
    except Exception as e:  # noqa: BLE001 — the agent must answer even if the aggregate fails
        log.warning("playbook_unavailable", error=f"{type(e).__name__}: {e}")
        return ""
    _cache[key] = (time.monotonic(), p)
    return render(p)


def invalidate(tenant_id: UUID | None = None) -> None:
    _cache.pop(str(tenant_id), None) if tenant_id else _cache.clear()
