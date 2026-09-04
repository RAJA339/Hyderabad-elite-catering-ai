"""Discount rule engine. Selects the best eligible offer(s) for a quote while never breaching
the margin floor. Pure logic; the repository loads rules from `discount_rules`."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.festivals.calendar import Festival, festivals_around
from app.pricing.costing import q
from app.pricing.engine import AppliedDiscount


@dataclass(frozen=True)
class DiscountRule:
    key: str
    name: str
    kind: str                    # percent | flat | free_item | per_plate_off
    value: Decimal
    explanation_template: str
    festival_key: str | None = None
    booking_window_days_before_festival: int | None = None
    guest_min: int | None = None
    guest_max: int | None = None
    diet: str | None = None
    occasions: tuple[str, ...] = ()
    tiers: tuple[str, ...] = ()
    min_margin_pct: Decimal | None = None
    stackable: bool = False
    priority: int = 100
    free_item_slug: str | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    is_active: bool = True


@dataclass(frozen=True)
class QuoteContext:
    event_date: date
    booking_date: date
    guest_count: int
    diet: str
    tier: str
    occasion: str | None
    subtotal: Decimal          # before discount, after surcharge
    cost_total: Decimal
    per_plate: Decimal
    free_item_cost_per_guest: dict[str, Decimal] | None = None


@dataclass(frozen=True)
class Offer:
    rule: DiscountRule
    amount: Decimal
    margin_after_pct: Decimal
    explanation: str
    festival: Festival | None

    def as_applied(self) -> AppliedDiscount:
        return AppliedDiscount(
            key=self.rule.key, name=self.rule.name, amount=self.amount, explanation=self.explanation,
            stackable=self.rule.stackable, min_margin_pct=self.rule.min_margin_pct,
        )


def _matches(rule: DiscountRule, ctx: QuoteContext, festivals: Sequence[Festival]) -> Festival | None | bool:
    if not rule.is_active:
        return False
    if rule.valid_from and ctx.booking_date < rule.valid_from:
        return False
    if rule.valid_to and ctx.booking_date > rule.valid_to:
        return False
    if rule.guest_min and ctx.guest_count < rule.guest_min:
        return False
    if rule.guest_max and ctx.guest_count > rule.guest_max:
        return False
    if rule.diet and rule.diet != ctx.diet and not (rule.diet == "veg" and ctx.diet == "jain"):
        return False
    if rule.occasions and (ctx.occasion or "") not in rule.occasions:
        return False
    if rule.tiers and ctx.tier not in rule.tiers:
        return False
    fest: Festival | None = None
    if rule.festival_key:
        prefix = rule.festival_key  # allow "diwali" to match "diwali_2026"
        fest = next((f for f in festivals if f.key == prefix or f.key.startswith(prefix + "_")), None)
        if fest is None:
            return False
        if rule.booking_window_days_before_festival is not None:
            days_before = (fest.starts_on - ctx.booking_date).days
            if days_before < rule.booking_window_days_before_festival:
                return False
    return fest if fest else True


def _amount(rule: DiscountRule, ctx: QuoteContext) -> Decimal:
    if rule.kind == "percent":
        return q(ctx.subtotal * rule.value / Decimal("100"))
    if rule.kind == "flat":
        return q(min(rule.value, ctx.subtotal))
    if rule.kind == "per_plate_off":
        return q(rule.value * ctx.guest_count)
    if rule.kind == "free_item":
        per_guest = (ctx.free_item_cost_per_guest or {}).get(rule.free_item_slug or "", Decimal("0"))
        return q(per_guest * ctx.guest_count)  # cost of the free item is the effective discount
    return Decimal("0")


def _explain(rule: DiscountRule, ctx: QuoteContext, fest: Festival | None, amount: Decimal) -> str:
    days = (fest.starts_on - ctx.booking_date).days if fest else 0
    return rule.explanation_template.format(
        festival=fest.name if fest else "", days=max(days, 0), pct=rule.value, amount=amount,
        guests=ctx.guest_count, item=(rule.free_item_slug or "").replace("_", " "),
    )


def best_offers(rules: Sequence[DiscountRule], ctx: QuoteContext, min_margin_pct: Decimal, max_total_discount: Decimal | None = None) -> list[Offer]:
    """Evaluate all rules; return offers sorted by customer value that keep margin ≥ floor.
    The first non-stackable offer is the headline; stackable ones may be layered on top.
    `max_total_discount` is the Kelly-sized cap (pricing/psychology.py): offers that would
    take the total concession past it are skipped, largest-first, so the best offer that
    the lead's odds justify is the one that surfaces."""
    festivals = festivals_around(ctx.event_date) + festivals_around(ctx.booking_date, before_days=45)
    seen: dict[str, Festival] = {f.key: f for f in festivals}
    candidates: list[Offer] = []
    for rule in rules:
        m = _matches(rule, ctx, list(seen.values()))
        if m is False:
            continue
        fest = m if isinstance(m, Festival) else None
        amount = _amount(rule, ctx)
        if amount <= 0:
            continue
        net = ctx.subtotal - amount
        margin = q((net - ctx.cost_total) / net * Decimal("100")) if net > 0 else Decimal("0")
        floor = max(min_margin_pct, rule.min_margin_pct or Decimal("0"))
        if margin < floor:
            continue
        candidates.append(Offer(rule, amount, margin, _explain(rule, ctx, fest, amount), fest))

    candidates.sort(key=lambda o: (-o.amount, o.rule.priority))
    cap = max_total_discount if max_total_discount is not None else Decimal("Infinity")
    headline = next((o for o in candidates if not o.rule.stackable and o.amount <= cap), None)
    result: list[Offer] = [headline] if headline else []
    running = headline.amount if headline else Decimal("0")
    for o in candidates:
        if o.rule.stackable and running + o.amount <= cap:
            net = ctx.subtotal - running - o.amount
            margin = q((net - ctx.cost_total) / net * Decimal("100")) if net > 0 else Decimal("0")
            if margin >= max(min_margin_pct, o.rule.min_margin_pct or Decimal("0")):
                result.append(Offer(o.rule, o.amount, margin, o.explanation, o.festival))
                running += o.amount
    return result
