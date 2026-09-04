"""UPI collection: the link every app opens, the QR that carries it, and the UTR gate."""
from __future__ import annotations

from decimal import Decimal

from app.agent import handoff
from app.core.config import Settings
from app.payments import upi
from app.routers.public import normalise_phone


def _with(monkeypatch, **kw):
    monkeypatch.setattr(upi, "get_settings", lambda: Settings(**kw))


def test_link_carries_payee_exact_amount_and_quote_reference(monkeypatch):
    _with(monkeypatch, upi_vpa="9705316350@ybl", upi_payee_name="Hyderabad Elite Catering")
    link = upi.upi_link(Decimal("48000"), note="Advance HEC-2026-0042 HEC", ref="HEC-2026-0042")
    assert link.startswith("upi://pay?")
    assert "pa=9705316350%40ybl" in link and "am=48000.00" in link and "cu=INR" in link
    assert "pn=Hyderabad%20Elite%20Catering" in link and "tr=HEC-2026-0042" in link


def test_no_vpa_means_no_link_but_the_number_still_shows(monkeypatch):
    _with(monkeypatch, upi_vpa=None, upi_payee_phone="+91 97053 16350")
    assert upi.upi_link(100, note="x", ref="y") is None
    card = upi.payment_card(amount=100, quote_number="Q", payment_id="p", portal_token="t")
    assert card["link"] is None and card["qr_svg"] is None
    assert card["phone"] == "+91 97053 16350" and card["claim_url"] == "/api/portal/t/upi-claim"


def test_unconfigured_yields_no_card(monkeypatch):
    _with(monkeypatch, upi_vpa=None, upi_payee_phone=None)
    assert upi.payment_card(amount=100, quote_number="Q", payment_id="p", portal_token="t") is None


def test_qr_is_a_scalable_svg_of_the_link(monkeypatch):
    _with(monkeypatch, upi_vpa="9705316350@ybl", upi_payee_phone="919705316350")
    card = upi.payment_card(amount=Decimal("48000.00"), quote_number="HEC-2026-0042", payment_id="p", portal_token=None)
    svg = card["qr_svg"]
    assert svg.startswith("<svg") and 'width="100%"' in svg and 'fill="currentColor"' in svg
    assert card["amount"] == "48000" and card["claim_url"] is None


def test_utr_must_be_twelve_digits():
    assert upi.valid_utr("4255 1234 5678") == "425512345678"
    assert upi.valid_utr("12345") is None
    assert upi.valid_utr("abcdefghijkl") is None


def test_enquiry_phone_normalisation():
    assert normalise_phone("98765 43210") == "919876543210"
    assert normalise_phone("+91 98765-43210") == "919876543210"
    assert normalise_phone("12345") is None


def test_claim_alert_tells_owner_where_to_look():
    subject, text = handoff.build_order_alert(kind="upi_claimed", lead={"occasion": "wedding"}, customer={"full_name": "Sameer", "wa_id": "919000011111"},
                                              quote={"quote_number": "HEC-1"}, extra={"amount": "48000", "utr": "425512345678"}, admin_url="https://x/admin/leads/1")
    assert subject.startswith("🧾 UPI payment claimed — Sameer")
    assert "UTR 425512345678" in text and "PhonePe/GPay" in text and "https://x/admin/leads/1" in text


def test_enquiry_alert_has_phone_and_wa_link():
    subject, text = handoff.build_enquiry_alert(name="Priya", phone="+919876543210", email="p@x.in", lead={"occasion": "housewarming", "guest_count": 120},
                                                message="Kompally, veg", admin_url=None)
    assert subject == "📞 Callback requested — Priya"
    assert "housewarming · 120 guests" in text and "https://wa.me/919876543210" in text and "Note: Kompally, veg" in text
