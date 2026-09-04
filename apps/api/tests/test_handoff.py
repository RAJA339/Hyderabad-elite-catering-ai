"""Escalation must reach the owner's phone with enough to act on, and must never break the
customer's reply when it cannot."""
from __future__ import annotations

import pytest

from app.agent import handoff
from app.core.config import Settings

LEAD = {"id": "11111111-1111-1111-1111-111111111111", "occasion": "wedding", "guest_count": 400, "diet": "non_veg", "event_date": "2026-11-21", "venue_area": "Gachibowli"}
CUSTOMER = {"full_name": "Sameer", "wa_id": "919000011111"}


def test_alert_has_who_what_and_both_ways_to_reach_them():
    text = handoff.build_owner_alert(lead=LEAD, customer=CUSTOMER, reason="customer requested human", summary="Wants to negotiate on 400 pax.",
                                     priority="high", admin_url="https://site.vercel.app/admin/leads/1111")
    assert text.startswith("🔴 Anvi needs you — Sameer")
    assert "wedding · 400 guests · non_veg · 2026-11-21 · Gachibowli" in text
    assert "https://wa.me/919000011111" in text
    assert "https://site.vercel.app/admin/leads/1111" in text


def test_website_chat_customers_have_no_wa_link():
    assert handoff.customer_wa_link("web:2f1c0a9e-1c1e-4b6e-9d1a-000000000000") is None
    assert handoff.customer_wa_link("919000011111") == "https://wa.me/919000011111"
    text = handoff.build_owner_alert(lead=LEAD, customer={"wa_id": "web:abc"}, reason="r", summary="s", priority="normal", admin_url=None)
    assert "wa.me" not in text and "website chat" in text


async def test_notify_skips_cleanly_without_owner_number(monkeypatch):
    monkeypatch.setattr(handoff, "get_settings", lambda: Settings(owner_wa_number=None))
    assert await handoff.notify_owner(lead=LEAD, customer=CUSTOMER, reason="r", summary="s") is False


async def test_notify_sends_to_owner_and_survives_send_failure(monkeypatch):
    monkeypatch.setattr(handoff, "get_settings", lambda: Settings(owner_wa_number="+91 98765 43210", public_web_url="https://site.vercel.app/"))
    sent = {}

    class FakeClient:
        async def send_text(self, to, body, preview_url=True):
            sent["to"], sent["body"] = to, body
            return {"id": "wamid.1"}

    monkeypatch.setattr(handoff, "WhatsAppClient", FakeClient)
    assert await handoff.notify_owner(lead=LEAD, customer=CUSTOMER, reason="r", summary="s", priority="normal") is True
    assert sent["to"] == "919876543210", "spaces and + must be stripped for the Graph API"
    assert "https://site.vercel.app/admin/leads/" in sent["body"]

    class Exploding:
        async def send_text(self, *a, **k):
            raise RuntimeError("Graph API 401")

    monkeypatch.setattr(handoff, "WhatsAppClient", Exploding)
    assert await handoff.notify_owner(lead=LEAD, customer=CUSTOMER, reason="r", summary="s") is False


@pytest.mark.parametrize("raw,expected", [("919876543210", "919876543210"), ("+91 98765-43210", "919876543210")])
def test_owner_number_is_normalised(raw, expected):
    digits = "".join(ch for ch in raw if ch.isdigit())
    assert digits == expected
