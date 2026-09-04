"""Package pricing with a hard margin guard.

price_per_guest = cost_per_guest / (1 - target_margin)  → rounded to a premium price point
Discounts are applied *after* pricing and are rejected if margin would fall below the floor.
Cost spikes trigger one of three strategies: substitute, surcharge, or restrict discounts.

The margin is not one number. The Indian catering market is won on the headline per-plate
price of the entry package and on the per-plate rate for big events, and it is kept
profitable on the middle and top tiers and on the absolute rupees a large booking brings.
So the tenant's target margin is adjusted per quote, in two independent steps:

  tier    — Classic is priced a few points under target (the price people compare us on),
            Signature at target (where most bookings land), Royal a few points over.
  volume  — the target steps down as guest count rises. Fixed costs are already spread
            thinner, and 400 plates at 32% is far more profit than 100 plates at 40%.

The floor moves with the target so festival offers still work on big events, but never
drops below MIN_FLOOR_PCT: we are never the cheapest at a loss.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

from app.pricing.costing import cost_item, q
from app.pricing.models import Diet, IngredientPrice, ItemCost, MenuItem, PackagePrice, PricedLine, Tier
from app.pricing.psychology import charm_per_plate

PRICE_POINT_STEP = Decimal("5")        # per-plate prices end in 0 or 5 → premium feel
SPIKE_THRESHOLD_PCT = Decimal("12")    # 7-day cost rise that counts as a spike
MAX_SURCHARGE_PCT = Decimal("6")       # transparent surcharge cap


# Points added to the tenant's target margin per tier, and per guest-count band (upper
# bound inclusive). Both are overridable from MARGIN_TIER_ADJ / MARGIN_VOLUME_LADDER so the
# owner can tune them against real competitor quotes without a deploy of code.
DEFAULT_TIER_ADJ: Mapping[str, Decimal] = {"classic": Decimal("-4"), "signature": Decimal("0"), "royal": Decimal("4")}
DEFAULT_VOLUME_LADDER: tuple[tuple[int, Decimal], ...] = ((75, Decimal("0")), (150, Decimal("-2")), (300, Decimal("-5")), (10_000, Decimal("-8")))
MIN_FLOOR_PCT = Decimal("24")          # no quote, offer or volume band ever goes below this
FLOOR_GAP_PCT = Decimal("6")           # the floor sits this far under the effective target


def parse_tier_adj(spec: str) -> dict[str, Decimal]:
    """'classic:-4,signature:0,royal:4' → {...}. Blank or malformed falls back to defaults."""
    out: dict[str, Decimal] = {}
    for part in (spec or "").split(","):
        if ":" in part:
            k, v = part.split(":", 1)
            try:
                out[k.strip().lower()] = Decimal(v.strip())
            except Exception:  # noqa: BLE001
                continue
    return out or dict(DEFAULT_TIER_ADJ)


def parse_volume_ladder(spec: str) -> tuple[tuple[int, Decimal], ...]:
    """'75:0,150:-2,300:-5,500:-8' → ((75,0),(150,-2),...). Bands are 'up to N guests'. The
    last band is extended to cover any count, so the top adjustment also applies above it."""
    bands: list[tuple[int, Decimal]] = []
    for part in (spec or "").split(","):
        if ":" in part:
            k, v = part.split(":", 1)
            try:
                bands.append((int(k.strip()), Decimal(v.strip())))
            except Exception:  # noqa: BLE001
                continue
    if not bands:
        return DEFAULT_VOLUME_LADDER
    bands.sort()
    upto, adj = bands[-1]
    return tuple(bands[:-1]) + ((10_000, adj),)


@dataclass(frozen=True)
class MarginPolicy:
    target_margin_pct: Decimal = Decimal("40")
    min_margin_pct: Decimal = Decimal("32")
    tax_pct: Decimal = Decimal("5")
    max_guests: int = 500
    tier_adj: Mapping[str, Decimal] = field(default_factory=lambda: dict(DEFAULT_TIER_ADJ))
    volume_ladder: tuple[tuple[int, Decimal], ...] = DEFAULT_VOLUME_LADDER
    reason: str = ""  # how an effective policy was derived; empty on the tenant's base policy

    @property
    def target(self) -> Decimal:
        return self.target_margin_pct / Decimal("100")

    @property
    def floor(self) -> Decimal:
        return self.min_margin_pct / Decimal("100")

    def effective(self, tier: str, guest_count: int) -> MarginPolicy:
        """The policy this particular quote is priced on."""
        t_adj = Decimal(self.tier_adj.get(tier, Decimal("0")))
        v_adj = Decimal("0")
        band = None
        for upto, adj in self.volume_ladder:
            if guest_count <= upto:
                v_adj, band = Decimal(adj), upto
                break
        target = self.target_margin_pct + t_adj + v_adj
        target = max(target, MIN_FLOOR_PCT + FLOOR_GAP_PCT)  # a target under 30 is not a pricing strategy
        floor = max(MIN_FLOOR_PCT, min(self.min_margin_pct, target - FLOOR_GAP_PCT))
        why = [f"base {self.target_margin_pct}%"]
        if t_adj:
            why.append(f"{tier} {t_adj:+}")
        if v_adj:
            why.append(f"volume ≤{band} guests {v_adj:+}")
        return replace(self, target_margin_pct=target, min_margin_pct=floor, reason=" · ".join(why) + f" → {target}% (floor {floor}%)")


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
    base_target = policy.target_margin_pct
    policy = policy.effective(tier, guest_count)

    lines: list[PricedLine] = []
    costs: list[ItemCost] = []
    notes: list[str] = []
    if policy.target_margin_pct < base_target + Decimal(policy.tier_adj.get(tier, 0)):
        notes.append(f"Volume rate applied for {guest_count} guests")
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

    # ── Positioning: the headline per-plate lands on the tier's price point. Upward only. ──
    raw_pp = (subtotal + surcharge) / guest_count
    charm_pp = charm_per_plate(raw_pp, tier)
    positioning_pp = max(Decimal("0"), charm_pp - raw_pp).quantize(Decimal("0.01"))
    subtotal = q(subtotal + positioning_pp * guest_count)

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
        "policy": {"target_margin_pct": str(policy.target_margin_pct), "min_margin_pct": str(policy.min_margin_pct), "base_target_pct": str(base_target), "derived": policy.reason},
        "positioning": {"raw_per_plate": str(raw_pp.quantize(Decimal("0.01"))), "price_point_per_plate": str(charm_pp), "uplift_per_plate": str(positioning_pp)},
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
        notes=notes, trace=trace, positioning_per_plate=positioning_pp,
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
