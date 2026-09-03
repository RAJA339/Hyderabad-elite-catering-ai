"""Package pricing with a hard margin guard.

price_per_guest = cost_per_guest / (1 - target_margin)  → rounded to a premium price point
Discounts are applied *after* pricing and are rejected if margin would fall below the floor.
Cost spikes trigger one of three strategies: substitute, surcharge, or restrict discounts.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

from app.pricing.costing import cost_item, q
from app.pricing.models import Diet, IngredientPrice, ItemCost, MenuItem, PackagePrice, PricedLine, Tier

PRICE_POINT_STEP = Decimal("5")        # per-plate prices end in 0 or 5 → premium feel
SPIKE_THRESHOLD_PCT = Decimal("12")    # 7-day cost rise that counts as a spike
MAX_SURCHARGE_PCT = Decimal("6")       # transparent surcharge cap


@dataclass(frozen=True)
class MarginPolicy:
    target_margin_pct: Decimal = Decimal("40")
    min_margin_pct: Decimal = Decimal("32")
    tax_pct: Decimal = Decimal("5")
    max_guests: int = 500

    @property
    def target(self) -> Decimal:
        return self.target_margin_pct / Decimal("100")

    @property
    def floor(self) -> Decimal:
        return self.min_margin_pct / Decimal("100")


class GuestLimitExceeded(ValueError):
    pass


def price_point(x: Decimal) -> Decimal:
    """Round up to the next multiple of 5 — never round down against margin."""
    return (x / PRICE_POINT_STEP).quantize(Decimal("1"), rounding=ROUND_CEILING) * PRICE_POINT_STEP


def unit_price_for(cost: Decimal, policy: MarginPolicy) -> Decimal:
    return price_point(cost / (Decimal("1") - policy.target))


def _margin(subtotal: Decimal, cost: Decimal) -> Decimal:
    if subtotal <= 0:
        return Decimal("0")
    return q((subtotal - cost) / subtotal * Decimal("100"))


def price_package(
    *,
    tier: Tier,
    items: Sequence[MenuItem],
    prices: Mapping[str, IngredientPrice],
    guest_count: int,
    diet: Diet,
    policy: MarginPolicy,
    discounts: Iterable[AppliedDiscount] = (),
    allow_surcharge: bool = True,
) -> PackagePrice:
    if guest_count <= 0:
        raise ValueError("guest_count must be positive")
    if guest_count > policy.max_guests:
        raise GuestLimitExceeded(f"guest_count {guest_count} exceeds hard limit {policy.max_guests}")

    lines: list[PricedLine] = []
    costs: list[ItemCost] = []
    notes: list[str] = []
    food_total = Decimal("0")
    cost_total = Decimal("0")
    subtotal = Decimal("0")
    surcharge = Decimal("0")

    for item in items:
        c = cost_item(item, prices, guest_count)
        costs.append(c)
        unit_price = unit_price_for(c.total_cost_per_guest, policy)
        line_surcharge = Decimal("0")
        if allow_surcharge and c.cost_change_7d_pct >= SPIKE_THRESHOLD_PCT:
            # Transparent, capped surcharge: pass through at most MAX_SURCHARGE_PCT
            line_surcharge = q(min(c.cost_change_7d_pct, MAX_SURCHARGE_PCT) / Decimal("100") * unit_price)
            notes.append(
                f"{item.name}: market cost up {c.cost_change_7d_pct}% this week "
                f"({', '.join(c.volatile_drivers) or 'ingredients'}); transparent surcharge ₹{line_surcharge}/plate"
            )
        line_total = q((unit_price + line_surcharge) * guest_count)
        lines.append(
            PricedLine(
                slug=item.slug, name=item.name, category_key=item.category_key,
                unit_cost=c.total_cost_per_guest, unit_price=unit_price + line_surcharge, line_total=line_total,
            )
        )
        food_total += c.food_cost_per_guest * guest_count
        cost_total += c.total_cost_per_guest * guest_count
        subtotal += unit_price * guest_count
        surcharge += line_surcharge * guest_count

    subtotal = q(subtotal)
    surcharge = q(surcharge)
    cost_total = q(cost_total)

    # ── Discounts: apply in priority order, reject any that breaches the floor ──
    discount_total = Decimal("0")
    applied: list[dict] = []
    for d in discounts:
        candidate = q(discount_total + d.amount)
        net = subtotal + surcharge - candidate
        m = _margin(net, cost_total)
        floor = max(policy.min_margin_pct, d.min_margin_pct or Decimal("0"))
        if m < floor:
            notes.append(f"Offer '{d.name}' skipped: would drop margin to {m}% (floor {floor}%)")
            continue
        discount_total = candidate
        applied.append({"key": d.key, "name": d.name, "amount": str(d.amount), "margin_after_pct": str(m), "explanation": d.explanation})
        if not d.stackable:
            break

    net = q(subtotal + surcharge - discount_total)
    tax = q(net * policy.tax_pct / Decimal("100"))
    grand = q(net + tax)
    per_plate = (net / guest_count).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    margin = _margin(net, cost_total)

    trace = {
        "policy": {"target_margin_pct": str(policy.target_margin_pct), "min_margin_pct": str(policy.min_margin_pct)},
        "items": [
            {"slug": c.slug, "food": str(c.food_cost_per_guest), "labour": str(c.labour_per_guest),
             "overhead": str(c.overhead_per_guest), "setup": str(c.setup_per_guest), "total_cost": str(c.total_cost_per_guest),
             "change_7d_pct": str(c.cost_change_7d_pct), "drivers": list(c.volatile_drivers)}
            for c in costs
        ],
        "discounts_applied": applied,
    }
    return PackagePrice(
        tier=tier, guest_count=guest_count, diet=diet, lines=lines,
        food_cost_total=q(food_total), cost_total=cost_total, subtotal=subtotal,
        discount_total=discount_total, surcharge_total=surcharge, tax_pct=policy.tax_pct, tax_total=tax,
        grand_total=grand, per_plate=per_plate, margin_pct=margin,
        target_margin_pct=policy.target_margin_pct, min_margin_pct=policy.min_margin_pct,
        notes=notes, trace=trace,
    )


@dataclass(frozen=True)
class AppliedDiscount:
    key: str
    name: str
    amount: Decimal
    explanation: str
    stackable: bool = False
    min_margin_pct: Decimal | None = None


def suggest_alternatives(
    spiked: ItemCost, catalog: Sequence[MenuItem], prices: Mapping[str, IngredientPrice], guest_count: int, diet: Diet
) -> list[tuple[MenuItem, ItemCost]]:
    """High-margin, same-category alternatives when an item's cost spikes."""
    out: list[tuple[MenuItem, ItemCost]] = []
    for m in catalog:
        if m.category_key != spiked.category_key or m.slug == spiked.slug:
            continue
        if diet == "veg" and m.diet != "veg":
            continue
        if diet == "jain" and not m.is_jain_ok:
            continue
        c = cost_item(m, prices, guest_count)
        if c.total_cost_per_guest < spiked.total_cost_per_guest and c.cost_change_7d_pct < SPIKE_THRESHOLD_PCT:
            out.append((m, c))
    out.sort(key=lambda mc: (mc[1].total_cost_per_guest, -mc[0].popularity))
    return out[:3]
