"""Builds Classic / Signature / Royal packages from templates + dietary transformation
(e.g. Jain substitutions, remove mutton) and applies live pricing."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.pricing.engine import AppliedDiscount, MarginPolicy, price_package
from app.pricing.models import Diet, IngredientPrice, MenuItem, PackagePrice, Tier

JAIN_FORBIDDEN = {"onion", "garlic", "potato", "carrot", "beetroot", "radish", "ginger", "mushroom", "egg", "meat"}


@dataclass(frozen=True)
class PackageTemplate:
    key: str
    tier: Tier
    diet: Diet
    item_slugs: tuple[str, ...]
    guest_min: int = 25
    guest_max: int = 500
    occasions: tuple[str, ...] = ()
    description: str = ""


def apply_diet(items: Sequence[MenuItem], diet: Diet, catalog: Mapping[str, MenuItem]) -> tuple[list[MenuItem], list[str]]:
    """Filter/substitute items for the requested diet. Returns (items, change_notes)."""
    notes: list[str] = []
    out: list[MenuItem] = []
    for it in items:
        if diet == "veg" and it.diet == "non_veg":
            notes.append(f"removed {it.name} (non-veg)")
            continue
        if diet == "jain":
            if it.diet == "non_veg" or (set(it.contains) & JAIN_FORBIDDEN) or not it.is_jain_ok:
                sub = _jain_substitute(it, catalog)
                if sub:
                    notes.append(f"swapped {it.name} → {sub.name} (Jain)")
                    out.append(sub)
                else:
                    notes.append(f"removed {it.name} (not Jain-compatible)")
                continue
        out.append(it)
    return out, notes


def _jain_substitute(item: MenuItem, catalog: Mapping[str, MenuItem]) -> MenuItem | None:
    candidates = [
        m for m in catalog.values()
        if m.category_key == item.category_key and m.is_jain_ok and m.diet == "veg" and m.slug != item.slug
    ]
    candidates.sort(key=lambda m: -m.popularity)
    return candidates[0] if candidates else None


def build_tiers(
    *,
    templates: Sequence[PackageTemplate],
    catalog: Mapping[str, MenuItem],
    prices: Mapping[str, IngredientPrice],
    guest_count: int,
    diet: Diet,
    policy: MarginPolicy,
    occasion: str | None = None,
    discounts: Sequence[AppliedDiscount] = (),
) -> list[PackagePrice]:
    """Return one priced package per tier (classic, signature, royal) best matching diet/occasion."""
    base_diet: Diet = "veg" if diet in ("veg", "jain") else diet
    out: list[PackagePrice] = []
    for tier in ("classic", "signature", "royal"):
        tpl = _pick_template(templates, tier, base_diet, guest_count, occasion)
        if not tpl:
            continue
        items = [catalog[s] for s in tpl.item_slugs if s in catalog]
        items, notes = apply_diet(items, diet, catalog)
        pkg = price_package(tier=tier, items=items, prices=prices, guest_count=guest_count, diet=diet, policy=policy, discounts=discounts)
        pkg.notes = notes + pkg.notes
        pkg.trace["template"] = tpl.key
        out.append(pkg)
    return out


def _pick_template(templates: Sequence[PackageTemplate], tier: str, diet: Diet, guests: int, occasion: str | None) -> PackageTemplate | None:
    scored: list[tuple[int, PackageTemplate]] = []
    for t in templates:
        if t.tier != tier or not (t.guest_min <= guests <= t.guest_max):
            continue
        score = 0
        if t.diet == diet:
            score += 10
        elif diet == "mixed" and t.diet == "non_veg":
            score += 6
        elif t.diet == "mixed":
            score += 4
        if occasion and occasion in t.occasions:
            score += 5
        scored.append((score, t))
    scored.sort(key=lambda s: -s[0])
    return scored[0][1] if scored else None


def modify_items(
    items: Sequence[MenuItem], *, add: Sequence[str] = (), remove: Sequence[str] = (), catalog: Mapping[str, MenuItem]
) -> tuple[list[MenuItem], list[str]]:
    notes: list[str] = []
    out = [i for i in items]
    for slug in remove:
        before = len(out)
        out = [i for i in out if i.slug != slug and slug not in i.tags]
        if len(out) < before:
            notes.append(f"removed {slug}")
    for slug in add:
        if slug in catalog and all(i.slug != slug for i in out):
            out.append(catalog[slug])
            notes.append(f"added {catalog[slug].name}")
    return out, notes


def rounded_display(pkg: PackagePrice) -> dict:
    return {
        "tier": pkg.tier,
        "guest_count": pkg.guest_count,
        "diet": pkg.diet,
        "per_plate": str(pkg.per_plate),
        "subtotal": str(pkg.subtotal),
        "discount_total": str(pkg.discount_total),
        "surcharge_total": str(pkg.surcharge_total),
        "tax_total": str(pkg.tax_total),
        "grand_total": str(pkg.grand_total),
        "margin_pct": str(pkg.margin_pct),
        "margin_ok": pkg.margin_ok,
        "items": [{"slug": ln.slug, "name": ln.name, "category": ln.category_key, "unit_price": str(ln.unit_price)} for ln in pkg.lines],
        "notes": pkg.notes,
    }
