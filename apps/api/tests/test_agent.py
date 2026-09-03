from datetime import date

from app.agent.guardrails import check_reply
from app.agent.qualification import Qualification, extract, next_questions, parse_budget, parse_date, parse_guests

TODAY = date(2026, 9, 3)


def test_extract_qualifies_in_two_messages():
    q = Qualification()
    q = extract("Hi, need catering for gruhapravesam on 14th Oct, around 120 people all veg", q, today=TODAY)
    assert q.fields["event_date"] == "2026-10-14" and q.fields["guest_count"] == 120 and q.fields["diet"] == "veg" and q.fields["occasion"] == "housewarming"
    assert q.missing == ["venue_area", "budget"]
    q = extract("Kompally, maybe 500-600 per plate", q, today=TODAY)
    assert q.is_qualified and q.fields["venue_area"] == "Kompally" and q.fields["budget"] == {"min_per_plate": 500, "max_per_plate": 600}
    assert next_questions(q) == []


def test_guest_cap_sets_over_limit_without_storing_count():
    q = extract("wedding reception for 800 guests", Qualification(), today=TODAY)
    assert q.over_limit and "guest_count" not in q.fields and q.fields["requested_guest_count"] == 800
    q = extract("ok make it 450 guests", q, today=TODAY)
    assert not q.over_limit and q.fields["guest_count"] == 450


def test_parsers():
    assert parse_date("on 5/1", TODAY) == date(2027, 1, 5)
    assert parse_date("in 2 weeks", TODAY) == date(2026, 9, 17)
    assert parse_guests("we are 75 pax") == 75
    assert parse_budget("budget around 700 per head") == (595, 700)


def test_guardrail_strips_ungrounded_amounts_and_competitors():
    tools = [{"name": "price_package", "result": {"packages": [{"per_plate": "489.00", "grand_total": "58680.00"}]}}]
    reply, v = check_reply("Classic is ₹489/plate, total ₹58,680. Unlike Paradise we also throw in ₹999 dessert.", tools, {}, max_guests=500)
    assert "₹489" in reply and "₹58,680" in reply
    assert "₹999" not in reply and "(price on request)" in reply
    assert "Paradise" not in reply
    assert any(x.startswith("ungrounded_amount") for x in v) and any(x.startswith("competitor") for x in v)


def test_guardrail_flags_guest_cap_not_communicated():
    _, v = check_reply("Sure, 800 guests is fine, let's plan!", [], {}, max_guests=500)
    assert "guest_cap_not_communicated" in v
