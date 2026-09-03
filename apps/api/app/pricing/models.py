"""Pure dataclasses for the pricing engine. No I/O here — everything is unit-testable."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

Diet = Literal["veg", "non_veg", "mixed", "jain"]
Tier = Literal["classic", "signature", "royal"]


@dataclass(frozen=True)
class IngredientPrice:
    key: str
    name: str
    unit: str
    wholesale: Decimal            # ₹ per unit, latest wholesale observation
    retail: Decimal | None = None  # ₹ per unit, latest retail observation
    change_7d_pct: Decimal = Decimal("0")
    is_volatile: bool = False


@dataclass(frozen=True)
class RecipeLine:
    ingredient_key: str
    qty_per_guest: Decimal
    waste_pct: Decimal = Decimal("5")


@dataclass(frozen=True)
class MenuItem:
    slug: str
    name: str
    category_key: str
    diet: Diet
    recipe: tuple[RecipeLine, ...]
    labour_cost_per_guest: Decimal = Decimal("0")
    overhead_pct: Decimal = Decimal("12")
    fixed_setup_cost: Decimal = Decimal("0")
    is_live_counter: bool = False
    is_jain_ok: bool = False
    contains: tuple[str, ...] = ()
    popularity: int = 0
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class ItemCost:
    slug: str
    name: str
    category_key: str
    food_cost_per_guest: Decimal
    labour_per_guest: Decimal
    overhead_per_guest: Decimal
    setup_per_guest: Decimal
    total_cost_per_guest: Decimal
    market_retail_equiv_per_guest: Decimal | None
    cost_change_7d_pct: Decimal
    volatile_drivers: tuple[str, ...]


@dataclass
class PricedLine:
    slug: str
    name: str
    category_key: str
    unit_cost: Decimal
    unit_price: Decimal
    line_total: Decimal
    is_substitution: bool = False
    note: str | None = None


@dataclass
class PackagePrice:
    tier: Tier
    guest_count: int
    diet: Diet
    lines: list[PricedLine]
    food_cost_total: Decimal
    cost_total: Decimal
    subtotal: Decimal
    discount_total: Decimal
    surcharge_total: Decimal
    tax_pct: Decimal
    tax_total: Decimal
    grand_total: Decimal
    per_plate: Decimal
    margin_pct: Decimal
    target_margin_pct: Decimal
    min_margin_pct: Decimal
    notes: list[str] = field(default_factory=list)
    market_snapshot: dict | None = None
    trace: dict = field(default_factory=dict)

    @property
    def margin_ok(self) -> bool:
        return self.margin_pct >= self.min_margin_pct
