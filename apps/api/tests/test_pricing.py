from decimal import Decimal as D

import pytest

from app.pricing.costing import cost_item
from app.pricing.engine import AppliedDiscount, GuestLimitExceeded, MarginPolicy, price_package, price_point, suggest_alternatives
from app.pricing.market import market_snapshot
from app.pricing.packages import apply_diet, build_tiers, modify_items
from tests.fixtures import CATALOG, PRICES, TEMPLATES

POLICY = MarginPolicy(D("40"), D("32"), D("5"), 500)


def test_cost_item_includes_waste_labour_overhead():
    c = cost_item(CATALOG["chicken_biryani"], PRICES, 100)
    # chicken 0.18*1.05*230 = 43.47, rice 0.12*1.05*95=11.97, onion 0.05*1.05*32=1.68, oil 0.02*1.05*130=2.73, spices 0.01*1.05*600=6.3 → 66.15
    assert c.food_cost_per_guest == D("66.15")
    assert c.labour_per_guest == D("12")
    assert c.overhead_per_guest == D("9.38")  # 12% of 78.15
    assert c.total_cost_per_guest == D("87.53")
    assert "chicken" in c.volatile_drivers


def test_price_point_rounds_up_to_5():
    assert price_point(D("101")) == D("105")
    assert price_point(D("105")) == D("105")
    assert price_point(D("489.2")) == D("490")


def test_package_hits_target_margin_and_guest_cap():
    pkg = price_package(tier="classic", items=[CATALOG["paneer_butter_masala"], CATALOG["pulihora"]], prices=PRICES, guest_count=120, diet="veg", policy=POLICY)
    assert pkg.margin_pct >= pkg.target_margin_pct  # rounding up only helps margin; target is the effective one
    assert pkg.margin_ok
    assert pkg.grand_total == pkg.subtotal + pkg.surcharge_total - pkg.discount_total + pkg.tax_total
    with pytest.raises(GuestLimitExceeded):
        price_package(tier="classic", items=[CATALOG["pulihora"]], prices=PRICES, guest_count=501, diet="veg", policy=POLICY)


def test_no_surcharge_below_spike_threshold():
    pkg = price_package(tier="classic", items=[CATALOG["chicken_biryani"]], prices=PRICES, guest_count=100, diet="non_veg", policy=POLICY)
    assert pkg.surcharge_total == 0  # weighted 7-day change is ~9.7%, under the 12% threshold


def test_spike_applies_transparent_capped_surcharge():
    from dataclasses import replace
    spiky = {**PRICES, "chicken": replace(PRICES["chicken"], change_7d_pct=D("28"))}
    pkg = price_package(tier="classic", items=[CATALOG["chicken_biryani"]], prices=spiky, guest_count=100, diet="non_veg", policy=POLICY)
    assert pkg.surcharge_total > 0
    assert any("surcharge" in n for n in pkg.notes)
    line = pkg.lines[0]
    eff = POLICY.effective("classic", 100)
    base = price_point(cost_item(CATALOG["chicken_biryani"], spiky, 100).total_cost_per_guest / (D("1") - eff.target))
    assert line.unit_price - base <= base * D("0.06") + D("0.01")  # capped at 6%


def test_discount_rejected_when_margin_would_breach_floor():
    items = [CATALOG["paneer_butter_masala"], CATALOG["pulihora"]]
    ok = AppliedDiscount("small", "Small", D("500"), "ok")
    huge = AppliedDiscount("huge", "Huge", D("50000"), "too much")
    pkg = price_package(tier="classic", items=items, prices=PRICES, guest_count=100, diet="veg", policy=POLICY, discounts=[huge, ok])
    assert pkg.discount_total == D("500")
    assert any("skipped" in n for n in pkg.notes)
    assert pkg.margin_ok


def test_live_counter_setup_amortised_by_guests():
    small = cost_item(CATALOG["live_dosa"], PRICES, 50)
    big = cost_item(CATALOG["live_dosa"], PRICES, 400)
    assert small.setup_per_guest == D("50.00") and big.setup_per_guest == D("6.25")
    assert small.total_cost_per_guest > big.total_cost_per_guest


def test_jain_transformation_substitutes_or_removes():
    items = [CATALOG["chicken_biryani"], CATALOG["aloo_curry"], CATALOG["pulihora"]]
    out, notes = apply_diet(items, "jain", CATALOG)
    slugs = [i.slug for i in out]
    assert "chicken_biryani" not in slugs and "aloo_curry" not in slugs
    assert "raw_banana_fry" in slugs and "pulihora" in slugs
    assert any("Jain" in n for n in notes)


def test_build_tiers_returns_three_priced_tiers_in_ascending_order():
    pkgs = build_tiers(templates=TEMPLATES, catalog=CATALOG, prices=PRICES, guest_count=150, diet="veg", policy=POLICY)
    assert [p.tier for p in pkgs] == ["classic", "signature", "royal"]
    assert pkgs[0].per_plate < pkgs[1].per_plate < pkgs[2].per_plate
    assert all(p.margin_ok for p in pkgs)


def test_modify_items_remove_by_tag_and_add():
    items = [CATALOG["chicken_biryani"], CATALOG["mutton_biryani"]]
    out, notes = modify_items(items, remove=["mutton"], add=["live_dosa"], catalog=CATALOG)
    assert [i.slug for i in out] == ["chicken_biryani", "live_dosa"]
    assert notes == ["removed mutton", "added Live Dosa Counter"]


def test_alternatives_are_cheaper_and_not_spiking():
    spiked = cost_item(CATALOG["mutton_biryani"], PRICES, 100)
    alts = suggest_alternatives(spiked, list(CATALOG.values()), PRICES, 100, "non_veg")
    assert all(c.total_cost_per_guest < spiked.total_cost_per_guest for _, c in alts)


def test_market_snapshot_exposes_benchmark_and_drivers():
    pkg = price_package(tier="classic", items=[CATALOG["chicken_biryani"]], prices=PRICES, guest_count=100, diet="non_veg", policy=POLICY)
    snap = market_snapshot(pkg, PRICES)
    assert D(snap["market_benchmark_per_plate"]) > D(snap["our_per_plate"])
    assert snap["ingredients"][0]["key"] == "chicken"


def test_jain_substitution_never_repeats_a_dish():
    # Three non-Jain mains would otherwise all collapse onto the same replacement.
    items = [CATALOG["chicken_biryani"], CATALOG["mutton_biryani"], CATALOG["aloo_curry"], CATALOG["paneer_butter_masala"]]
    out, notes = apply_diet(items, "jain", CATALOG)
    slugs = [i.slug for i in out]
    assert len(slugs) == len(set(slugs)), f"duplicate dish in Jain menu: {slugs}"
    assert all(i.is_jain_ok for i in out)


def test_diet_filter_does_not_duplicate_existing_items():
    items = [CATALOG["pulihora"], CATALOG["pulihora"], CATALOG["gulab_jamun"]]
    out, _ = apply_diet(items, "veg", CATALOG)
    assert [i.slug for i in out] == ["pulihora", "gulab_jamun"]



# ── margin shaping: low headline price, bigger events cheaper per plate, profit intact ──
from app.pricing.engine import MIN_FLOOR_PCT, parse_tier_adj, parse_volume_ladder  # noqa: E402

VEG = [CATALOG["paneer_butter_masala"], CATALOG["pulihora"], CATALOG["gulab_jamun"]]


def test_classic_is_the_cheapest_tier_and_royal_carries_the_margin():
    c = price_package(tier="classic", items=VEG, prices=PRICES, guest_count=120, diet="veg", policy=POLICY)
    s = price_package(tier="signature", items=VEG, prices=PRICES, guest_count=120, diet="veg", policy=POLICY)
    r = price_package(tier="royal", items=VEG, prices=PRICES, guest_count=120, diet="veg", policy=POLICY)
    assert c.per_plate < s.per_plate < r.per_plate
    assert c.target_margin_pct < s.target_margin_pct < r.target_margin_pct
    assert all(p.margin_ok for p in (c, s, r))


def test_bigger_event_costs_less_per_plate_and_makes_more_money():
    small = price_package(tier="signature", items=VEG, prices=PRICES, guest_count=50, diet="veg", policy=POLICY)   # ≤75: no volume band
    mid = price_package(tier="signature", items=VEG, prices=PRICES, guest_count=100, diet="veg", policy=POLICY)   # ≤150: −2
    big = price_package(tier="signature", items=VEG, prices=PRICES, guest_count=400, diet="veg", policy=POLICY)   # >300: −8
    assert big.per_plate < mid.per_plate < small.per_plate
    assert "Volume rate applied for 400 guests" in big.notes and not any("Volume" in n for n in small.notes)
    profit = lambda p: p.subtotal + p.surcharge_total - p.discount_total - p.cost_total  # noqa: E731
    assert profit(big) > profit(small) * 6  # eight times the plates at a lower rate is still far more rupees


def test_floor_follows_target_but_never_drops_below_the_hard_minimum():
    assert POLICY.effective("royal", 50).min_margin_pct == D("32")          # 44% target, tenant floor holds
    assert POLICY.effective("classic", 500).min_margin_pct == MIN_FLOOR_PCT  # 28% target → floor pinned at 24
    assert POLICY.effective("classic", 500).target_margin_pct == D("30")     # a target under 30 is refused
    assert "volume" in POLICY.effective("signature", 300).reason


def test_offers_still_work_on_big_events_because_the_floor_moved():
    # ~6.5% off a 400-plate quote: lands around 29% margin, under the tenant's 32% floor but
    # above the 26% the volume band moved it to. A flat floor would have refused it.
    offer = AppliedDiscount("fest", "Dasara early bird", D("3000"), "festival")
    big = price_package(tier="signature", items=VEG, prices=PRICES, guest_count=400, diet="veg", policy=POLICY, discounts=[offer])
    assert big.discount_total == D("3000") and big.margin_ok and big.margin_pct < D("32")
    greedy = AppliedDiscount("greedy", "Too deep", D("6000"), "festival")
    assert price_package(tier="signature", items=VEG, prices=PRICES, guest_count=400, diet="veg", policy=POLICY, discounts=[greedy]).discount_total == 0


def test_shaping_is_tunable_from_env_strings():
    assert parse_tier_adj("classic:-6, royal:+5")["classic"] == D("-6")
    assert parse_tier_adj("")["signature"] == D("0")
    ladder = parse_volume_ladder("100:0,250:-3,500:-7")
    assert ladder[0] == (100, D("0")) and ladder[-1] == (10_000, D("-7"))
    flat = MarginPolicy(D("40"), D("32"), D("5"), 500, tier_adj={"classic": D("0"), "signature": D("0"), "royal": D("0")}, volume_ladder=((10_000, D("0")),))
    assert flat.effective("classic", 500).target_margin_pct == D("40")
