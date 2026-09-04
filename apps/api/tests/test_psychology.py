"""Positioning and Kelly-sized concessions."""
from __future__ import annotations

from decimal import Decimal as D

from app.festivals.rules import best_offers
from app.pricing import psychology as ps
from app.pricing.engine import MarginPolicy, price_package
from tests.fixtures import CATALOG, PRICES
from tests.test_festivals import RULES, ctx

POLICY = MarginPolicy(D("40"), D("32"), D("5"), 500)
VEG = [CATALOG["paneer_butter_masala"], CATALOG["pulihora"], CATALOG["gulab_jamun"]]


def test_price_points_are_upward_only_and_tier_shaped():
    assert ps.charm_per_plate(D("400.00"), "classic") == D("409")   # never 399: that would cost margin
    assert ps.charm_per_plate(D("395.20"), "classic") == D("399")
    assert ps.charm_per_plate(D("552.10"), "signature") == D("560")
    assert ps.charm_per_plate(D("890"), "royal") == D("890")
    for tier in ("classic", "signature", "royal"):
        pkg = price_package(tier=tier, items=VEG, prices=PRICES, guest_count=120, diet="veg", policy=POLICY)
        assert pkg.positioning_per_plate >= 0 and pkg.margin_ok
        assert pkg.trace["positioning"]["price_point_per_plate"].endswith("9" if tier == "classic" else "0")


def test_segment_from_budget_beats_occasion():
    tiers = {"classic": D("399"), "signature": D("560"), "royal": D("890")}
    assert ps.segment_for(budget_max_per_plate=D("380"), guest_count=120, occasion="wedding", tier_per_plate=tiers) == "value"
    assert ps.segment_for(budget_max_per_plate=D("850"), guest_count=120, occasion="corporate", tier_per_plate=tiers) == "premium"
    assert ps.segment_for(budget_max_per_plate=D("600"), guest_count=120, occasion="wedding", tier_per_plate=tiers) == "mid"
    assert ps.segment_for(budget_max_per_plate=None, guest_count=120, occasion="wedding") == "premium"
    assert ps.segment_for(budget_max_per_plate=None, guest_count=450, occasion="wedding") == "value"
    assert ps.default_tier_for("mid") == "signature" and ps.presentation_order("mid")[0] == "royal"
    assert ps.presentation_order("value")[0] == "classic"


def test_close_probability_moves_with_signal_and_stays_bounded():
    cold = ps.CloseSignals(fields_known=1, budget_max_per_plate=None, quote_per_plate=None, days_to_event=None, customer_messages=1)
    hot = ps.CloseSignals(fields_known=5, budget_max_per_plate=D("600"), quote_per_plate=D("560"), days_to_event=5, customer_messages=14, repeat_customer=True)
    over = ps.CloseSignals(fields_known=5, budget_max_per_plate=D("400"), quote_per_plate=D("560"), days_to_event=90, customer_messages=2)
    assert ps.estimate_close_probability(cold) == D("0.350")
    assert ps.estimate_close_probability(hot) == D("0.950")
    assert ps.estimate_close_probability(over) < ps.estimate_close_probability(hot)
    assert D("0.05") <= ps.estimate_close_probability(over) <= D("0.95")


def test_kelly_gives_more_to_strong_leads_on_fat_margins_and_nothing_to_weak_ones():
    # subtotal 120000, cost 70000 → b = 0.714 profit per rupee; floor 32% → net_min 102941, headroom 17059
    strong = ps.kelly_discount_cap(p=D("0.8"), subtotal=D("120000"), cost_total=D("70000"), floor_margin_pct=D("32"))
    weak = ps.kelly_discount_cap(p=D("0.4"), subtotal=D("120000"), cost_total=D("70000"), floor_margin_pct=D("32"))
    assert strong > weak
    assert weak == 0                              # p=0.4 at these odds: f* = 0.4 − 0.6/0.714 < 0 → no bet
    assert strong < D("17059") / 2 + 1            # never more than half the headroom
    thin = ps.kelly_discount_cap(p=D("0.9"), subtotal=D("100000"), cost_total=D("70000"), floor_margin_pct=D("32"))
    assert thin < strong                          # same lead, thinner margin, smaller bet
    assert ps.kelly_fraction(D("0.6"), D("0")) == 0


def test_offer_engine_respects_the_kelly_cap():
    uncapped = best_offers(RULES, ctx(guest_count=320, subtotal=D("190000"), cost_total=D("110000")), D("32"))
    assert sum(o.amount for o in uncapped) > D("6000")
    capped = best_offers(RULES, ctx(guest_count=320, subtotal=D("190000"), cost_total=D("110000")), D("32"), max_total_discount=D("6000"))
    assert capped and sum(o.amount for o in capped) <= D("6000")
    assert best_offers(RULES, ctx(), D("32"), max_total_discount=D("0")) == []
