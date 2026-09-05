"""The menu the customer can see and change, and the plate that comes out of their choices.

Pure functions over the pricing models. The router loads templates, catalogue and prices; this
module decides what a visitor is shown (never a cost or a margin), turns a selection into the
list of dishes to price, and shapes the priced plate for the page.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.pricing.engine import MarginPolicy, price_package
from app.pricing.models import IngredientPrice, MenuItem, PackagePrice
from app.pricing.packages import PackageTemplate, apply_diet

CATEGORY_ORDER = ("welcome_drinks", "starters", "main_veg", "main_nonveg", "rice_breads", "sides", "live_counters", "desserts", "service")
NEVER_REMOVE = {"disposables"}       # part of every plate
OPTIONAL_ADDONS = ("water",)         # offered, never included by default
INDICATIVE_GUESTS = 100


@dataclass(frozen=True)
class Selection:
    package_key: str
    guest_count: int
    choices: Mapping[str, str]          # slot key → chosen slug
    add: Sequence[str] = ()
    remove: Sequence[str] = ()
    diet: str | None = None             # veg | non_veg | jain; defaults to the package's


def dish_view(m: MenuItem, name_te: str | None = None, description: str | None = None) -> dict:
    return {"slug": m.slug, "name": m.name, "name_te": name_te, "description": description, "category": m.category_key,
            "diet": m.diet, "jain_ok": m.is_jain_ok, "tags": list(m.tags), "popularity": m.popularity}


def resolve(tpl: PackageTemplate, sel: Selection, catalog: Mapping[str, MenuItem]) -> tuple[list[str], list[str]]:
    """Slugs to price for this selection, and plain-language notes on what changed from the card."""
    notes: list[str] = []
    chosen: list[str] = []
    slot_slugs = {o for s in tpl.slots for o in s.options}
    for slug in tpl.item_slugs:
        if slug in slot_slugs:
            continue          # slots are filled below
        chosen.append(slug)
    for s in tpl.slots:
        pick = sel.choices.get(s.key, s.options[0])
        if pick not in s.options:
            pick = s.options[0]
        chosen.append(pick)
        if pick != s.options[0]:
            notes.append(f"{s.label}: {catalog[pick].name if pick in catalog else pick}")
    for slug in sel.remove:
        if slug in chosen and slug not in NEVER_REMOVE:
            chosen.remove(slug)
            notes.append(f"without {catalog[slug].name if slug in catalog else slug}")
    for slug in sel.add:
        if slug in catalog and slug not in chosen:
            chosen.append(slug)
            notes.append(f"plus {catalog[slug].name}")
    return chosen, notes


def price_selection(tpl: PackageTemplate, sel: Selection, catalog: Mapping[str, MenuItem], prices: Mapping[str, IngredientPrice],
                    policy: MarginPolicy) -> tuple[PackagePrice, list[str]]:
    slugs, notes = resolve(tpl, sel, catalog)
    diet = sel.diet or tpl.diet
    items = [catalog[s] for s in slugs if s in catalog]
    items, diet_notes = apply_diet(items, diet, catalog)
    pkg = price_package(tier=tpl.tier, items=items, prices=prices, guest_count=sel.guest_count, diet=diet, policy=policy,
                        package_adj=tpl.margin_adj, package_key=tpl.key)
    pkg.notes = diet_notes + pkg.notes
    return pkg, notes + diet_notes


def customer_view(pkg: PackagePrice, tpl: PackageTemplate, notes: Sequence[str]) -> dict:
    """What a visitor may see: prices, never costs or margins."""
    lines = sorted(pkg.lines, key=lambda ln: (CATEGORY_ORDER.index(ln.category_key) if ln.category_key in CATEGORY_ORDER else 99, ln.name))
    return {
        "package_key": tpl.key, "tier": pkg.tier, "guest_count": pkg.guest_count, "diet": pkg.diet,
        "per_plate": str(pkg.per_plate), "subtotal": str(pkg.subtotal), "discount_total": str(pkg.discount_total),
        "surcharge_total": str(pkg.surcharge_total), "tax_pct": str(pkg.tax_pct), "tax_total": str(pkg.tax_total), "grand_total": str(pkg.grand_total),
        "list_price": str(tpl.list_price) if tpl.list_price is not None else None,
        "items": [{"slug": ln.slug, "name": ln.name, "category": ln.category_key, "unit_price": str(ln.unit_price)} for ln in lines],
        "includes": list(tpl.includes), "changes": list(notes),
        # Market notes only: the engine's own notes can mention margins, which are the owner's.
        "notes": [n for n in pkg.notes if "margin" not in n.lower() and "floor" not in n.lower()],
    }


def catalog_view(templates: Sequence[PackageTemplate], catalog: Mapping[str, MenuItem], prices: Mapping[str, IngredientPrice],
                 policy: MarginPolicy, extra: Mapping[str, dict] | None = None) -> dict:
    """Everything the builder page needs in one call: packages with an indicative per-plate at
    INDICATIVE_GUESTS, their slots, and the dishes that can be added."""
    extra = extra or {}
    packages = []
    for tpl in sorted(templates, key=lambda t: t.sort_order):
        try:
            pkg, _ = price_selection(tpl, Selection(tpl.key, INDICATIVE_GUESTS, {}), catalog, prices, policy)
            from_pp = str(pkg.per_plate)
        except Exception:  # noqa: BLE001 — a template whose dish lacks a price still lists, without a number
            from_pp = None
        slot_slugs = {o for s in tpl.slots for o in s.options}
        packages.append({
            "key": tpl.key, "name": tpl.name, "tagline": tpl.tagline, "description": tpl.description, "tier": tpl.tier, "diet": tpl.diet,
            "list_price": str(tpl.list_price) if tpl.list_price is not None else None, "from_per_plate": from_pp,
            "indicative_guests": INDICATIVE_GUESTS, "occasions": list(tpl.occasions), "includes": list(tpl.includes),
            "fixed": [s for s in tpl.item_slugs if s not in slot_slugs],
            "slots": [{"key": s.key, "label": s.label, "default": s.options[0], "options": list(s.options)} for s in tpl.slots],
            "item_count": len(tpl.item_slugs),
        })
    dishes = [dish_view(m, extra.get(m.slug, {}).get("name_te"), extra.get(m.slug, {}).get("description"))
              for m in sorted(catalog.values(), key=lambda m: (CATEGORY_ORDER.index(m.category_key) if m.category_key in CATEGORY_ORDER else 99, -m.popularity, m.name))]
    return {"packages": packages, "dishes": dishes, "categories": list(CATEGORY_ORDER), "optional_addons": list(OPTIONAL_ADDONS), "never_remove": sorted(NEVER_REMOVE)}
