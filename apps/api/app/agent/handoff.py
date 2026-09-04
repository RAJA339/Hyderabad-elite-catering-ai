"""Hand a conversation to the owner.

Anvi runs on the business number through the Cloud API, so that number cannot be opened
in the WhatsApp app on anyone's phone. The owner therefore needs to be TOLD when a customer
asks for a human, on their own personal number, with everything needed to act from the
phone: who, what, the customer's number to call or message, and the admin link to reply
through Anvi's number.
"""
from __future__ import annotations

from app.core.config import get_settings
from app.core.logging import get_logger
from app.whatsapp.client import WhatsAppClient

log = get_logger("handoff")

PRIORITY_MARK = {"high": "🔴", "normal": "🟠", "low": "🟡"}


def customer_wa_link(wa_id: str | None) -> str | None:
    """wa.me link for a real WhatsApp customer; None for website-chat sessions (`web:<uuid>`)."""
    if not wa_id:
        return None
    digits = "".join(ch for ch in wa_id if ch.isdigit())
    if not digits or ":" in wa_id or len(digits) < 8:
        return None
    return f"https://wa.me/{digits}"


def build_owner_alert(*, lead: dict, customer: dict, reason: str, summary: str, priority: str, admin_url: str | None) -> str:
    """The message the owner receives. Short enough to read on a lock screen, complete enough
    to act on without opening the dashboard."""
    name = customer.get("full_name") or "New customer"
    wa_id = customer.get("wa_id") or ""
    link = customer_wa_link(wa_id)
    what = " · ".join(x for x in (
        lead.get("occasion"),
        f"{lead['guest_count']} guests" if lead.get("guest_count") else None,
        lead.get("diet"),
        lead.get("event_date"),
        lead.get("venue_area"),
    ) if x)
    lines = [
        f"{PRIORITY_MARK.get(priority, '🟠')} Anvi needs you — {name}",
        what or "Details not captured yet",
        "",
        f"Why: {reason}",
        f"Summary: {summary.strip()[:400]}",
        "",
    ]
    if link:
        lines.append(f"Message them directly: {link}")
    else:
        lines.append("They are on the website chat, so reply from the admin page.")
    if admin_url:
        lines.append(f"Reply as Anvi's number: {admin_url}")
    return "\n".join(lines)


async def notify_owner(*, lead: dict, customer: dict, reason: str, summary: str, priority: str = "normal") -> bool:
    """Best-effort. Returns True when an alert was sent, False when nothing is configured or
    the send failed — the escalation itself is already recorded either way."""
    s = get_settings()
    owner = "".join(ch for ch in (s.owner_wa_number or "") if ch.isdigit())
    if not owner:
        log.info("owner_alert_skipped", reason="OWNER_WA_NUMBER not set", lead=str(lead.get("id")))
        return False
    admin_url = f"{s.public_web_url.rstrip('/')}/admin/leads/{lead['id']}" if s.public_web_url and lead.get("id") else None
    text = build_owner_alert(lead=lead, customer=customer, reason=reason, summary=summary, priority=priority, admin_url=admin_url)
    try:
        r = await WhatsAppClient().send_text(owner, text, preview_url=False)
        log.info("owner_alerted", lead=str(lead.get("id")), message_id=r.get("id"), dry_run=r.get("dry_run", False))
        return not r.get("dry_run", False)
    except Exception as e:  # noqa: BLE001 — never let the alert failure break the customer's reply
        log.error("owner_alert_failed", lead=str(lead.get("id")), error=str(e))
        return False
