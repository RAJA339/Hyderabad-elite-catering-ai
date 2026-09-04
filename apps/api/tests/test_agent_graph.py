"""The sale has a shape: which phase a conversation is in, and what Anvi may do there."""
from __future__ import annotations

from app.agent import graph
from app.agent.outreach import compose_opening
from app.agent.playbook import render
from app.agent.tools import TOOLS
from app.voice.speech import for_speech, say_amount

QUOTED = {"status": "draft", "quote_number": "HEC-1"}
LOCKED = {"status": "locked", "quote_number": "HEC-1"}


def test_phase_follows_the_facts_not_the_chatter():
    # No quote and not qualified: still discovering, whatever they say.
    assert graph.classify(lead={"stage": "qualifying"}, quote=None, text="just book it", qualified=False) is graph.DISCOVER
    # Qualified, nothing priced yet: time to design.
    assert graph.classify(lead={"stage": "qualified"}, quote=None, text="ok", qualified=True) is graph.DESIGN
    # A quote exists and they push on price: negotiate.
    assert graph.classify(lead={"stage": "quoted"}, quote=QUOTED, text="that's too expensive", qualified=True) is graph.NEGOTIATE
    assert graph.classify(lead={"stage": "quoted"}, quote=QUOTED, text="konchem thakkuva cheyandi", qualified=True) is graph.NEGOTIATE
    # A buying signal with a quote on the table: close.
    assert graph.classify(lead={"stage": "quoted"}, quote=QUOTED, text="ok let's do it", qualified=True) is graph.CLOSE
    # Paid: stop selling.
    assert graph.classify(lead={"stage": "advance_paid"}, quote=LOCKED, text="thanks", qualified=True) is graph.WON


def test_a_locked_quote_closes_even_on_a_neutral_message():
    assert graph.classify(lead={"stage": "locked"}, quote=LOCKED, text="hello", qualified=True) is graph.CLOSE


def test_discovery_cannot_reach_the_closing_tools():
    names = {t["name"] for t in graph.tools_for(graph.DISCOVER, TOOLS)}
    assert "save_lead_field" in names
    assert not {"lock_price", "record_advance", "price_package"} & names, "must understand the event before pricing it"


def test_every_phase_offers_only_real_tools():
    real = {t["name"] for t in TOOLS}
    for phase in graph.PHASES.values():
        assert set(phase.tools) <= real, f"{phase.key} names a tool that does not exist"
        assert graph.tools_for(phase, TOOLS), f"{phase.key} would leave the model with no tools"
        assert "escalate_to_human" in phase.tools, f"{phase.key} must always be able to reach a human"


def test_the_motive_rides_along_once_discovery_is_done():
    motive = "first function in the new flat, wife's parents visiting"
    assert motive in graph.directive_for(graph.DESIGN, motive=motive)
    assert motive not in graph.directive_for(graph.DISCOVER, motive=motive), "discovery is where we ask, not recite"


def test_enquiry_form_reads_as_something_a_person_would_say():
    text = compose_opening(name="Priya Reddy", occasion="Housewarming", event_date="2026-10-14",
                           guests=120, diet="veg", message="Kompally, around 600 a plate")
    assert text.startswith("Hi, I'm Priya Reddy.")
    assert "housewarming" in text and "120 guests" in text and "pure veg" in text
    assert "2026-10-14" in text and "Kompally" in text and text.endswith("prices?")


def test_playbook_is_silent_until_there_is_something_to_learn():
    assert render({"window_days": 180, "by_occasion": [], "price_band": [], "winning_items": [], "shape_of_a_win": {}, "objections": []}) == ""


def test_playbook_reports_what_wins_and_marks_internal_numbers():
    out = render({
        "window_days": 180,
        "by_occasion": [{"occasion": "housewarming", "won": 9, "quoted": 20, "won_per_plate": 545, "won_tier": "signature", "won_guests": 130}],
        "price_band": [{"band": "76-150", "won_per_plate": 545, "lost_per_plate": 690, "won": 9, "quoted": 20}],
        "winning_items": [{"name": "Kacchi Dum Biryani", "n": 9}],
        "shape_of_a_win": {"turns_to_win": 7, "turns_when_lost": 3, "wins": 9, "closed": 20},
        "objections": [{"reason": "customer requested human", "n": 4}],
    })
    assert "housewarming: 9/20 booked (45%)" in out and "usually signature" in out
    assert "₹545/plate [internal]" in out
    assert "quotes we lose are priced higher" in out
    assert "Kacchi Dum Biryani" in out
    assert "never say them to a customer" in out


def test_money_is_spoken_the_way_hyderabad_says_it():
    assert say_amount(125000) == "one lakh twenty five thousand rupees"
    assert say_amount(485) == "four hundred eighty five rupees"
    assert say_amount(10_000_000) == "one crore rupees"
    assert say_amount(250) == "two hundred fifty rupees"


def test_a_whatsapp_reply_becomes_something_you_can_hear():
    written = ("Here are three options 🌿\n"
               "• Classic — ₹399/plate (₹47,880 incl. GST)\n"
               "• Signature — ₹560/plate\n"
               "View & tweak live: https://site.app/portal/abc123\n"
               "Shall I check festival offers?")
    said = for_speech(written)
    assert "https://" not in said and "•" not in said and "🌿" not in said
    assert "three hundred ninety nine rupees per plate" in said
    assert said.rstrip().endswith("?"), "the caller needs a question to answer into"
    assert said.count(".") + said.count("?") <= 8
