"""Recipe → per-guest cost. Deterministic, Decimal-safe, explains volatility drivers."""
from __future__ import annotations

from collections.abc import Mapping
from decimal import ROUND_HALF_UP, Decimal

from app.pricing.models import IngredientPrice, ItemCost, MenuItem

TWO = Decimal("0.01")


def q(x: Decimal) -> Decimal:
    return x.quantize(TWO, rounding=ROUND_HALF_UP)


def cost_item(item: MenuItem, prices: Mapping[str, IngredientPrice], guest_count: int) -> ItemCost:
    """Food cost + labour + overhead + amortised setup (live counters) per guest."""
    food = Decimal("0")
    retail = Decimal("0")
    retail_known = True
    weighted_change = Decimal("0")
    drivers: list[str] = []
    for line in item.recipe:
        p = prices.get(line.ingredient_key)
        if p is None:
            raise KeyError(f"missing price for ingredient '{line.ingredient_key}' in {item.slug}")
        qty = line.qty_per_guest * (Decimal("1") + line.waste_pct / Decimal("100"))
        line_cost = qty * p.wholesale
        food += line_cost
        if p.retail is None:
            retail_known = False
        else:
            retail += qty * p.retail
        weighted_change += line_cost * p.change_7d_pct
        if p.is_volatile and abs(p.change_7d_pct) >= Decimal("8"):
            drivers.append(p.key)
    labour = item.labour_cost_per_guest
    overhead = (food + labour) * item.overhead_pct / Decimal("100")
    setup = item.fixed_setup_cost / Decimal(max(guest_count, 1)) if item.fixed_setup_cost else Decimal("0")
    total = food + labour + overhead + setup
    change = (weighted_change / food) if food else Decimal("0")
    return ItemCost(
        slug=item.slug,
        name=item.name,
        category_key=item.category_key,
        food_cost_per_guest=q(food),
        labour_per_guest=q(labour),
        overhead_per_guest=q(overhead),
        setup_per_guest=q(setup),
        total_cost_per_guest=q(total),
        market_retail_equiv_per_guest=q(retail + labour + overhead + setup) if retail_known else None,
        cost_change_7d_pct=q(change),
        volatile_drivers=tuple(drivers),
    )
