"""'Today's Hyderabad Market Price vs Our Price' transparency snapshot."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal

from app.pricing.costing import q
from app.pricing.models import IngredientPrice, PackagePrice


def market_snapshot(pkg: PackagePrice, prices: Mapping[str, IngredientPrice], highlight_keys: Sequence[str] = ()) -> dict:
    """Compare our per-plate to a retail-cost benchmark and expose key ingredient prices."""
    keys = list(highlight_keys) or _top_drivers(pkg, prices)
    ingredients = []
    for k in keys:
        p = prices.get(k)
        if not p:
            continue
        ingredients.append({
            "key": p.key, "name": p.name, "unit": p.unit,
            "wholesale": str(p.wholesale), "retail": str(p.retail) if p.retail is not None else None,
            "change_7d_pct": str(p.change_7d_pct), "volatile": p.is_volatile,
        })
    cost_pp = q(pkg.cost_total / pkg.guest_count)
    # Benchmark: what a typical Hyderabad caterer charges ≈ retail-cost × 1.9 (industry rule of thumb)
    benchmark_pp = q(cost_pp * Decimal("1.9"))
    return {
        "as_of": None,  # filled by repository with observed_at
        "our_per_plate": str(pkg.per_plate),
        "our_cost_per_plate": str(cost_pp),
        "market_benchmark_per_plate": str(benchmark_pp),
        "you_save_vs_benchmark": str(q(max(benchmark_pp - pkg.per_plate, Decimal("0")))),
        "ingredients": ingredients,
        "surcharge_total": str(pkg.surcharge_total),
        "notes": [n for n in pkg.notes if "surcharge" in n or "market" in n],
    }


def _top_drivers(pkg: PackagePrice, prices: Mapping[str, IngredientPrice]) -> list[str]:
    drivers = []
    for it in pkg.trace.get("items", []):
        drivers.extend(it.get("drivers", []))
    common = ["chicken", "mutton", "paneer", "onion", "tomato", "rice", "oil"]
    ordered = list(dict.fromkeys(drivers + common))
    return [k for k in ordered if k in prices][:6]
