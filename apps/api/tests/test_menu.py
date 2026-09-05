"""The owner's cards as data: every dish costs, every package prices, choices resolve, and a
visitor never sees a cost."""
from __future__ import annotations

from decimal import Decimal as D

import pytest

from app.menu import recipes as R
from app.menu import sri_sai_raja as M
from app.menu.builder import INDICATIVE_GUESTS, Selection, catalog_view, customer_view, price_selection, resolve
from app.pricing.engine import MarginPolicy, parse_tier_adj, parse_volume_ladder
from app.pricing.models import IngredientPrice, MenuItem, RecipeLine
from app.pricing.packages import PackageTemplate, SlotChoice

# The seed's opening wholesale rates, plus the ingredients the real card added.
_BASE = {"chicken": 200, "mutton": 760, "fish": 320, "prawns": 520, "egg": 78, "paneer": 360, "milk": 56, "curd": 70, "ghee": 620, "butter": 480,
         "cream": 220, "rice": 95, "sona_rice": 58, "wheat_flour": 42, "urad_dal": 130, "toor_dal": 150, "oil": 128, "onion": 26, "tomato": 30,
         "potato": 26, "green_chilli": 60, "ginger_garlic": 140, "brinjal": 34, "raw_banana": 40, "mixed_veg": 45, "coconut": 28,
         "coriander_mint": 80, "lemon": 70, "spices": 600, "sugar": 44, "dry_fruits": 900, "bread": 90, "fruits": 80, "tamarind": 160,
         "pasta": 140, "soda_syrups": 120, "tea_coffee": 700, **{k: v[3] for k, v in R.EXTRA_INGREDIENTS.items()}}
PRICES = {k: IngredientPrice(k, k, "kg", D(str(v)), D(str(round(v * 1.28, 2)))) for k, v in _BASE.items()}
POLICY = MarginPolicy(D("38"), D("30"), tier_adj=parse_tier_adj("classic:-3,signature:0,royal:2"), volume_ladder=parse_volume_ladder("75:0,150:-2,300:-5,500:-8"))


def _item(slug: str) -> MenuItem:
    d, r = M.DISH_BY_SLUG[slug], R.RECIPES[slug]
    return MenuItem(slug, d.name, d.category, d.diet, tuple(RecipeLine(k, q) for k, q in r.lines.items()), r.labour, M.OVERHEAD_PCT, r.setup,
                    is_jain_ok=R.jain_ok(r), contains=tuple(R.contains_for(r)), popularity=d.popularity, tags=d.tags)


CATALOG = {d.slug: _item(d.slug) for d in M.DISHES}


def _tpl(p: M.Package) -> PackageTemplate:
    return PackageTemplate(p.key, p.tier, p.diet, tuple(M.default_slugs(p)), occasions=p.occasions, description=p.description, name=p.name,
                           tagline=p.tagline, list_price=p.list_price, includes=p.includes, margin_adj=p.margin_adj, sort_order=p.sort_order,
                           slots=tuple(SlotChoice(s.key, s.label, s.options) for s in p.slots))


TEMPLATES = [_tpl(p) for p in M.PACKAGES]


def test_every_dish_on_the_card_has_a_recipe_in_priced_ingredients():
    for d in M.DISHES:
        assert d.slug in R.RECIPES, d.slug
        for key in R.RECIPES[d.slug].lines:
            assert key in PRICES, f"{d.slug} uses unpriced ingredient {key}"
    assert set(R.RECIPES) == {d.slug for d in M.DISHES}, "a recipe with no dish, or a dish with no recipe"


def test_packages_reference_real_dishes_and_carry_disposables_not_water():
    for p in M.PACKAGES:
        for slug in M.all_slugs(p):
            assert slug in M.DISH_BY_SLUG, (p.key, slug)
        assert "disposables" in p.fixed and "water" not in M.all_slugs(p), p.key
        assert len(set(M.default_slugs(p))) == len(M.default_slugs(p)), f"{p.key} lists a dish twice"
        if p.diet == "veg":
            assert all(M.DISH_BY_SLUG[s].diet == "veg" for s in M.all_slugs(p)), p.key


def test_nine_cards_priced_near_the_printed_price_at_a_hundred_guests():
    """The engine's number sits within a few percent of the card, so the site never quotes a
    figure the owner would not recognise. Non-veg cards are deliberately lifted (docs/10-menu.md)."""
    for tpl in TEMPLATES:
        pkg, _ = price_selection(tpl, Selection(tpl.key, 100, {}), CATALOG, PRICES, POLICY)
        drift = (pkg.per_plate - tpl.list_price) / tpl.list_price * 100
        lo, hi = (D("-6"), D("6")) if tpl.diet == "veg" else (D("-2"), D("20"))
        assert lo <= drift <= hi, (tpl.key, pkg.per_plate, tpl.list_price)
        assert pkg.margin_ok and pkg.margin_pct >= D("30")


def test_classic_veg_is_the_lead_price_and_falls_with_volume():
    tpl = TEMPLATES[0]
    small, _ = price_selection(tpl, Selection(tpl.key, 100, {}), CATALOG, PRICES, POLICY)
    big, _ = price_selection(tpl, Selection(tpl.key, 400, {}), CATALOG, PRICES, POLICY)
    assert small.per_plate % 10 == 9                       # classic tier price point (…9)
    assert small.per_plate < tpl.list_price               # a little under the card, on purpose
    assert big.per_plate < small.per_plate                # volume rate
    assert big.margin_ok


def test_choices_swap_a_slot_and_the_default_plate_is_the_card_as_printed():
    tpl = TEMPLATES[0]
    slugs, notes = resolve(tpl, Selection(tpl.key, 100, {}), CATALOG)
    assert slugs == list(tpl.item_slugs) and notes == []
    slugs, notes = resolve(tpl, Selection(tpl.key, 100, {"sweet": "gulab_jamun", "snack": "nonsense"}), CATALOG)
    assert "gulab_jamun" in slugs and "purnalu" not in slugs and "mirchi_bajji" in slugs
    assert notes == ["Sweet: Gulab Jamun"]


def test_adding_water_costs_more_and_disposables_cannot_be_removed():
    tpl = TEMPLATES[2]
    base, _ = price_selection(tpl, Selection(tpl.key, 100, {}), CATALOG, PRICES, POLICY)
    plus, notes = price_selection(tpl, Selection(tpl.key, 100, {}, add=["water"], remove=["disposables"]), CATALOG, PRICES, POLICY)
    assert plus.per_plate > base.per_plate
    assert any(ln.slug == "water" for ln in plus.lines) and any(ln.slug == "disposables" for ln in plus.lines)
    assert notes == ["plus Packaged drinking water"]


def test_customer_view_shows_prices_never_costs():
    tpl = TEMPLATES[5]
    pkg, notes = price_selection(tpl, Selection(tpl.key, 120, {"sweet": "double_ka_meetha"}), CATALOG, PRICES, POLICY)
    view = customer_view(pkg, tpl, notes)
    flat = str(view).lower()
    for word in ("cost", "margin", "floor", "food_cost"):
        assert word not in flat, word
    assert view["per_plate"] == str(pkg.per_plate) and view["includes"] == list(M.INCLUDES)
    assert [i["category"] for i in view["items"]] == sorted([i["category"] for i in view["items"]], key=lambda c: ["welcome_drinks", "starters", "main_veg", "main_nonveg", "rice_breads", "sides", "live_counters", "desserts", "service"].index(c))


def test_catalog_view_lists_packages_in_order_with_indicative_prices_and_slots():
    view = catalog_view(TEMPLATES, CATALOG, PRICES, POLICY)
    assert [p["key"] for p in view["packages"]] == [p.key for p in M.PACKAGES]
    first = view["packages"][0]
    assert first["indicative_guests"] == INDICATIVE_GUESTS and D(first["from_per_plate"]) < D(first["list_price"])
    assert first["slots"][0]["default"] == first["slots"][0]["options"][0]
    assert "water" in view["optional_addons"] and "disposables" in view["never_remove"]
    assert {d["slug"] for d in view["dishes"]} == set(CATALOG)


def test_jain_switch_replaces_onion_dishes_with_jain_ones():
    tpl = TEMPLATES[0]
    pkg, notes = price_selection(tpl, Selection(tpl.key, 100, {}, diet="jain"), CATALOG, PRICES, POLICY)
    names = {ln.slug for ln in pkg.lines}
    assert "raita" not in names and "gutti_vankaya" not in names
    assert any("Jain" in n for n in notes)


@pytest.mark.parametrize("slug", ["white_rice", "pulihora", "purnalu", "mirchi_bajji", "vada"])
def test_jain_friendly_dishes_are_marked(slug):
    assert R.jain_ok(R.RECIPES[slug]), slug
