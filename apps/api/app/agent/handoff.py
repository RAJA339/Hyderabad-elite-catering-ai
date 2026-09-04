"""Everything the owner needs to hear about, phrased for a phone lock screen.

Anvi runs on the business number through the Cloud API, so that number cannot be opened in
the WhatsApp app. The owner therefore has to be TOLD — on Telegram, on their own WhatsApp,
by email, whichever is configured (see app.notify.channels) — when something needs a person
or changes an order: a hand-off, a locked price, an advance requested, an advance paid.
"""
from __future__ import annotations

from app.core.config import get_settings
from app.notify.channels import alert_owner

PRIORITY_MARK = {"high": "🔴", "normal": "🟠", "low": "🟡"}


def customer_wa_link(wa_id: str | None) -> str | None:
    """wa.me link for a real WhatsApp customer; None for website-chat sessions (`web:<uuid>`)."""
    if not wa_id:
        return None
    digits = "".join(ch for ch in wa_id if ch.isdigit())
    if not digits or ":" in wa_id or len(digits) < 8:
        return None
    return f"https://wa.me/{digits}"


def _who(customer: dict) -> str:
    return customer.get("full_name") or "New customer"


def _what(lead: dict) -> str:
    return " · ".join(str(x) for x in (
        lead.get("occasion"),
        f"{lead['guest_count']} guests" if lead.get("guest_count") else None,
        lead.get("diet"),
        lead.get("event_date"),
        lead.get("venue_area"),
    ) if x) or "Details not captured yet"


def _reach(customer: dict, admin_url: str | None) -> list[str]:
    lines = []
    link = customer_wa_link(customer.get("wa_id"))
    if link:
        lines.append(f"Message them directly: {link}")
    elif customer.get("email"):
        lines.append(f"Email: {customer['email']}")
    else:
        lines.append("They are on the website chat, so reply from the admin page.")
    if admin_url:
        lines.append(f"Open in admin: {admin_url}")
    return lines


def admin_url_for(lead: dict) -> str | None:
    s = get_settings()
    return f"{s.public_web_url.rstrip('/')}/admin/leads/{lead['id']}" if s.public_web_url and lead.get("id") else None


def build_owner_alert(*, lead: dict, customer: dict, reason: str, summary: str, priority: str, admin_url: str | None) -> str:
    """The hand-off message. Short enough to read on a lock screen, complete enough to act
    on without opening the dashboard."""
    return "\n".join([
        f"{PRIORITY_MARK.get(priority, '🟠')} Anvi needs you — {_who(customer)}",
        _what(lead),
        "",
        f"Why: {reason}",
        f"Summary: {summary.strip()[:400]}",
        "",
        *_reach(customer, admin_url),
    ])


def build_order_alert(*, kind: str, lead: dict, customer: dict, quote: dict, extra: dict, admin_url: str | None) -> tuple[str, str]:
    """(subject, text) for an order event. `kind` is one of price_locked, advance_requested,
    advance_paid."""
    q = quote.get("quote_number", "")
    head = {
        "price_locked": f"🔒 Price locked — {_who(customer)}",
        "advance_requested": f"💳 Advance link sent — {_who(customer)}",
        "advance_paid": f"✅ Advance PAID — {_who(customer)}",
    }.get(kind, f"Order update — {_who(customer)}")
    detail = {
        "price_locked": f"{q}: ₹{extra.get('per_plate')}/plate, total ₹{extra.get('total')}, locked till {extra.get('valid_until')}.",
        "advance_requested": f"{q}: ₹{extra.get('amount')} requested. Reminders go out at 24h and 72h.",
        "advance_paid": f"{q}: ₹{extra.get('amount')} received. The booking is confirmed — put it on the kitchen calendar.",
    }.get(kind, q)
    text = "\n".join([head, _what(lead), "", detail, "", *_reach(customer, admin_url)])
    return head, text


async def notify_owner(*, lead: dict, customer: dict, reason: str, summary: str, priority: str = "normal") -> bool:
    """Hand-off alert. Best-effort: True when at least one channel delivered it."""
    text = build_owner_alert(lead=lead, customer=customer, reason=reason, summary=summary, priority=priority, admin_url=admin_url_for(lead))
    return bool(await alert_owner(text.splitlines()[0], text))


async def notify_owner_order(kind: str, *, lead: dict, customer: dict, quote: dict, **extra) -> bool:
    subject, text = build_order_alert(kind=kind, lead=lead, customer=customer, quote=quote, extra=extra, admin_url=admin_url_for(lead))
    return bool(await alert_owner(subject, text))
