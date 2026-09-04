"""How the price is *positioned*, and how much of it we are willing to give away.

Three ideas from how Hyderabad buys catering, each small and testable:

1. Segments. A customer arrives as value, mid or premium — from their stated budget when
   there is one, from the occasion and size when there is not. The segment decides which
   tier is the working quote ("most chosen"), and in what order the three are presented:
   value buyers see the entry price first; mid buyers see Royal first so Signature lands as
   the sensible middle (the Goldilocks effect); premium buyers see Royal as the default.

2. Price points. The headline per-plate is what gets compared in a WhatsApp group.
   Classic ends in 9 (₹399 is a different number from ₹400 in this market), Signature and
   Royal end in 0. Rounding is upward only, so it can never cost margin.

3. Kelly-sized concessions. A discount is a bet: we give up margin now for a higher chance
   the booking closes. The Kelly criterion sizes a bet by the edge and the odds —
   f* = p − (1 − p) / b — where p is the estimated close probability and b the profit per
   rupee of cost at list price. We use half-Kelly (the conservative convention) of the
   margin headroom above the floor as the most this quote may concede. Strong leads on fat
   margins get real offers; weak leads and thin margins get little or none, which is what
   "constant profit" means in practice.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal
from typing import Literal

from app.pricing.costing import q

Segment = Literal["value", "mid", "premium"]

PREMIUM_OCCASIONS = {"wedding", "reception", "engagement", "sangeet", "haldi", "mehendi"}
KELLY_FRACTION = Decimal("0.5")   # half-Kelly: the standard hedge against an over-confident p
P_MIN, P_MAX = Decimal("0.05"), Decimal("0.95")


def segment_for(*, budget_max_per_plate: Decimal | None, guest_count: int, occasion: str | None,
                tier_per_plate: dict[str, Decimal] | None = None) -> Segment:
    """Budget beats everything; without one, the occasion and size say who is asking."""
    if budget_max_per_plate and tier_per_plate:
        classic = tier_per_plate.get("classic")
        royal = tier_per_plate.get("royal")
        if classic and budget_max_per_plate < classic * Decimal("1.05"):
            return "value"
        if royal and budget_max_per_plate >= royal * Decimal("0.9"):
            return "premium"
        return "mid"
    if (occasion or "").lower() in PREMIUM_OCCASIONS and guest_count <= 300:
        return "premium"
    if guest_count > 300:
        return "value"       # volume buyers compare per-plate hardest
    return "mid"


def default_tier_for(segment: Segment) -> str:
    return {"value": "classic", "mid": "signature", "premium": "royal"}[segment]


def presentation_order(segment: Segment) -> list[str]:
    """The order Anvi should present the tiers in. Anchoring high makes the middle feel
    like the wise choice; leading with the entry price keeps a value buyer in the chat."""
    return {"value": ["classic", "signature", "royal"], "mid": ["royal", "signature", "classic"], "premium": ["royal", "signature", "classic"]}[segment]


def charm_per_plate(x: Decimal, tier: str) -> Decimal:
    """Upward-only rounding to the tier's price point. Classic → …9, others → …0."""
    if tier == "classic":
        up = ((x + Decimal("1")) / Decimal("10")).quantize(Decimal("1"), rounding=ROUND_CEILING) * Decimal("10")
        return up - Decimal("1")
    return (x / Decimal("10")).quantize(Decimal("1"), rounding=ROUND_CEILING) * Decimal("10")


@dataclass(frozen=True)
class CloseSignals:
    fields_known: int            # of occasion, event_date, guest_count, diet, venue_area
    budget_max_per_plate: Decimal | None
    quote_per_plate: Decimal | None
    days_to_event: int | None
    customer_messages: int
    repeat_customer: bool = False


def estimate_close_probability(s: CloseSignals) -> Decimal:
    """A calibrated-looking heuristic, not a model: it exists so that Kelly has a p, and it
    is stored on the lead so the dashboard and the owner see the same number. Replace with
    a fitted model once there are a few hundred closed leads."""
    p = Decimal("0.30")
    p += Decimal("0.05") * min(s.fields_known, 5)
    if s.budget_max_per_plate and s.quote_per_plate:
        if s.quote_per_plate <= s.budget_max_per_plate:
            p += Decimal("0.15")
        elif s.quote_per_plate > s.budget_max_per_plate * Decimal("1.15"):
            p -= Decimal("0.15")
    if s.days_to_event is not None:
        if s.days_to_event <= 7:
            p += Decimal("0.15")
        elif s.days_to_event <= 21:
            p += Decimal("0.10")
    if s.customer_messages >= 12:
        p += Decimal("0.10")
    elif s.customer_messages >= 6:
        p += Decimal("0.05")
    if s.repeat_customer:
        p += Decimal("0.10")
    return min(P_MAX, max(P_MIN, p)).quantize(Decimal("0.001"))


def kelly_fraction(p: Decimal, b: Decimal) -> Decimal:
    """f* = p − (1 − p) / b, clamped to [0, 1]. b is net odds: profit per rupee staked."""
    if b <= 0:
        return Decimal("0")
    f = p - (Decimal("1") - p) / b
    return min(Decimal("1"), max(Decimal("0"), f))


def kelly_discount_cap(*, p: Decimal, subtotal: Decimal, cost_total: Decimal, floor_margin_pct: Decimal,
                       fraction: Decimal = KELLY_FRACTION) -> Decimal:
    """The most this quote may concede, in rupees.

    headroom = subtotal − cost / (1 − floor): every rupee of discount that still keeps the
    margin at or above the floor. Kelly then says what share of that headroom the odds
    justify staking on this particular lead."""
    if subtotal <= 0 or cost_total <= 0:
        return Decimal("0")
    floor = floor_margin_pct / Decimal("100")
    net_min = cost_total / (Decimal("1") - floor)
    headroom = max(Decimal("0"), subtotal - net_min)
    b = (subtotal - cost_total) / cost_total
    return q(headroom * kelly_fraction(p, b) * fraction)
