from datetime import date
from decimal import Decimal as D

from app.festivals.calendar import demand_multiplier_for, festivals_around
from app.festivals.rules import DiscountRule, QuoteContext, best_offers

RULES = [
    DiscountRule("diwali_early", "Diwali Early Bird", "percent", D("8"), "Book {days} days before {festival} and save {pct}%", festival_key="diwali", booking_window_days_before_festival=14, priority=10),
    DiscountRule("volume_300", "Volume 300+", "per_plate_off", D("15"), "₹15 off per plate for {guests} guests", guest_min=300, stackable=True, priority=50),
    DiscountRule("veg_dasara", "Dasara Veg Special", "percent", D("5"), "{pct}% off veg menus for {festival}", festival_key="dasara", diet="veg", priority=20),
    DiscountRule("crazy", "Crazy Deal", "percent", D("40"), "nope", priority=1),
]


def ctx(**kw):
    base = dict(event_date=date(2026, 11, 7), booking_date=date(2026, 10, 1), guest_count=200, diet="non_veg", tier="signature", occasion="corporate",
                subtotal=D("120000"), cost_total=D("70000"), per_plate=D("600"))
    base.update(kw)
    return QuoteContext(**base)


def test_calendar_windows():
    around = festivals_around(date(2026, 11, 7))
    assert any(f.key == "diwali_2026" for f in around)
    assert demand_multiplier_for(date(2026, 11, 7)) >= 1.4
    assert demand_multiplier_for(date(2026, 7, 1)) == 1.0


def test_best_offer_respects_margin_floor_and_picks_largest():
    offers = best_offers(RULES, ctx(), D("32"))
    keys = [o.rule.key for o in offers]
    assert "crazy" not in keys                # 40% would breach floor
    assert keys[0] == "diwali_early"          # headline = largest safe non-stackable
    assert offers[0].amount == D("9600")
    assert "14 days" not in offers[0].explanation and "Diwali" in offers[0].explanation


def test_stackable_volume_offer_layers_when_safe():
    offers = best_offers(RULES, ctx(guest_count=320, subtotal=D("190000"), cost_total=D("110000")), D("32"))
    keys = [o.rule.key for o in offers]
    assert "volume_300" in keys and keys[0] == "diwali_early"
    assert all(o.margin_after_pct >= D("32") for o in offers)


def test_early_bird_window_enforced():
    late = ctx(booking_date=date(2026, 11, 1))  # 5 days before Diwali
    assert all(o.rule.key != "diwali_early" for o in best_offers(RULES, late, D("32")))


def test_diet_and_festival_matching():
    veg = ctx(event_date=date(2026, 10, 15), booking_date=date(2026, 9, 20), diet="jain")
    keys = [o.rule.key for o in best_offers(RULES, veg, D("32"))]
    assert "veg_dasara" in keys  # jain counts as veg
