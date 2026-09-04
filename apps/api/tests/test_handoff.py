"""The owner must hear about hand-offs and order events on whatever channel is configured,
and never be the reason a customer's reply fails."""
from __future__ import annotations

from app.agent import handoff
from app.core.config import Settings
from app.notify import channels

LEAD = {"id": "11111111-1111-1111-1111-111111111111", "occasion": "wedding", "guest_count": 400, "diet": "non_veg", "event_date": "2026-11-21", "venue_area": "Gachibowli"}
CUSTOMER = {"full_name": "Sameer", "wa_id": "919000011111"}
QUOTE = {"quote_number": "HEC-2026-0042"}


def test_handoff_alert_has_who_what_and_both_ways_to_reach_them():
    text = handoff.build_owner_alert(lead=LEAD, customer=CUSTOMER, reason="customer requested human", summary="Wants to negotiate on 400 pax.",
                                     priority="high", admin_url="https://site.vercel.app/admin/leads/1111")
    assert text.startswith("🔴 Anvi needs you — Sameer")
    assert "wedding · 400 guests · non_veg · 2026-11-21 · Gachibowli" in text
    assert "https://wa.me/919000011111" in text
    assert "https://site.vercel.app/admin/leads/1111" in text


def test_website_chat_customers_get_email_or_admin_instead_of_wa_link():
    assert handoff.customer_wa_link("web:2f1c0a9e-1c1e-4b6e-9d1a-000000000000") is None
    assert handoff.customer_wa_link("919000011111") == "https://wa.me/919000011111"
    text = handoff.build_owner_alert(lead=LEAD, customer={"wa_id": "web:abc", "email": "s@x.in"}, reason="r", summary="s", priority="normal", admin_url=None)
    assert "wa.me" not in text and "Email: s@x.in" in text
    text = handoff.build_owner_alert(lead=LEAD, customer={"wa_id": "web:abc"}, reason="r", summary="s", priority="normal", admin_url=None)
    assert "website chat" in text


def test_order_alerts_name_the_event_and_the_money():
    subject, text = handoff.build_order_alert(kind="advance_paid", lead=LEAD, customer=CUSTOMER, quote=QUOTE, extra={"amount": "48000"}, admin_url=None)
    assert subject.startswith("✅ Advance PAID — Sameer")
    assert "HEC-2026-0042: ₹48000 received" in text and "kitchen calendar" in text
    subject, text = handoff.build_order_alert(kind="price_locked", lead=LEAD, customer=CUSTOMER, quote=QUOTE,
                                              extra={"per_plate": "485", "total": "194000", "valid_until": "2026-11-21"}, admin_url=None)
    assert "🔒" in subject and "₹485/plate" in text and "locked till 2026-11-21" in text


async def test_fanout_reports_every_channel_that_delivered(monkeypatch):
    monkeypatch.setattr(channels, "get_settings", lambda: Settings(telegram_bot_token="t", telegram_chat_id="1", resend_api_key="k", owner_email="o@x.in", owner_wa_number=None))
    calls = []

    async def fake_tg(text, *, chat_id=None):
        calls.append(("telegram", text))
        return True

    async def fake_mail(to, subject, text):
        calls.append(("email", to))
        return True

    monkeypatch.setattr(channels, "send_telegram", fake_tg)
    monkeypatch.setattr(channels, "send_email", fake_mail)
    assert await channels.alert_owner("subj", "body") == ["telegram", "email"]
    assert ("email", "o@x.in") in calls


async def test_fanout_with_nothing_configured_is_a_warning_not_an_error(monkeypatch):
    monkeypatch.setattr(channels, "get_settings", lambda: Settings(owner_wa_number=None, telegram_bot_token=None, resend_api_key=None))
    assert await channels.alert_owner("subj", "body") == []


async def test_fanout_survives_a_channel_that_explodes(monkeypatch):
    monkeypatch.setattr(channels, "get_settings", lambda: Settings(owner_wa_number="+91 98765 43210", telegram_bot_token="t", telegram_chat_id="1"))

    class Exploding:
        async def send_text(self, *a, **k):
            raise RuntimeError("Graph API 401")

    import app.whatsapp.client as wa
    monkeypatch.setattr(wa, "WhatsAppClient", Exploding)

    async def fake_tg(text, *, chat_id=None):
        return True

    monkeypatch.setattr(channels, "send_telegram", fake_tg)
    assert await channels.alert_owner("subj", "body") == ["telegram"]


def test_owner_channels_reflects_configuration():
    s = Settings(telegram_bot_token="t", telegram_chat_id="1")
    assert "telegram" in _channels_for(s) and "whatsapp" not in _channels_for(s)
    s = Settings(owner_wa_number="91", whatsapp_access_token="a", whatsapp_phone_number_id="p", resend_api_key="k", owner_email="o@x.in")
    assert _channels_for(s) == ["whatsapp", "email"]


def _channels_for(s: Settings) -> list[str]:
    import app.notify.channels as c
    orig = c.get_settings
    c.get_settings = lambda: s
    try:
        return c.owner_channels()
    finally:
        c.get_settings = orig


def test_email_bodies_get_clickable_links():
    body = channels._linkify("Pay here: https://pay.example/x and reply")
    assert '<a href="https://pay.example/x">' in body
