"""Channels that work from anywhere, today.

WhatsApp Cloud API needs a Meta-verified business, a GST document and an Indian SIM to take
an OTP — days of work that cannot be done from abroad. These two need none of that:

- Telegram: a bot token from @BotFather and the owner's chat id. Free, instant, reliable.
  This is the owner's alert channel until (and alongside) WhatsApp.
- Email via Resend: an API key and a sender. Carries quotes and confirmations to customers
  who gave an email, and doubles as the owner's backup.

Every send is best-effort and returns True/False; callers never fail because a channel did.
"""
from __future__ import annotations

import html

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger("notify")


def owner_channels() -> list[str]:
    """Which owner-alert channels are configured. Surfaced on /health so it can be checked
    from a browser, the same way cors_origins is."""
    s = get_settings()
    out = []
    if s.owner_wa_number and s.whatsapp_access_token and s.whatsapp_phone_number_id:
        out.append("whatsapp")
    if s.telegram_bot_token and s.telegram_chat_id:
        out.append("telegram")
    if s.resend_api_key and s.owner_email:
        out.append("email")
    return out


async def send_telegram(text: str, *, chat_id: str | None = None) -> bool:
    s = get_settings()
    chat = chat_id or s.telegram_chat_id
    if not (s.telegram_bot_token and chat):
        return False
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(f"https://api.telegram.org/bot{s.telegram_bot_token}/sendMessage",
                                  json={"chat_id": chat, "text": text, "disable_web_page_preview": True})
            if r.status_code >= 400:
                log.error("telegram_send_failed", status=r.status_code, body=r.text[:300])
                return False
        return True
    except Exception as e:  # noqa: BLE001
        log.error("telegram_send_failed", error=str(e))
        return False


async def send_email(to: str, subject: str, text: str) -> bool:
    """Plain text wrapped in the lightest possible HTML so links are clickable everywhere."""
    s = get_settings()
    if not (s.resend_api_key and to):
        return False
    body = "<br>".join(html.escape(line) for line in text.splitlines())
    body = _linkify(body)
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post("https://api.resend.com/emails",
                                  headers={"Authorization": f"Bearer {s.resend_api_key}"},
                                  json={"from": s.email_from, "to": [to], "subject": subject, "text": text,
                                        "html": f'<div style="font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;color:#141312">{body}</div>'})
            if r.status_code >= 400:
                log.error("email_send_failed", status=r.status_code, body=r.text[:300], to=to)
                return False
        return True
    except Exception as e:  # noqa: BLE001
        log.error("email_send_failed", error=str(e), to=to)
        return False


def _linkify(escaped: str) -> str:
    out = []
    for token in escaped.split(" "):
        if token.startswith(("https://", "http://")):
            out.append(f'<a href="{token}">{token}</a>')
        else:
            out.append(token)
    return " ".join(out)


async def alert_owner(subject: str, text: str) -> list[str]:
    """Fan out one alert to every configured owner channel. Returns the channels that
    accepted it, so callers and logs can see whether anyone was actually told."""
    s = get_settings()
    delivered: list[str] = []
    if s.owner_wa_number:
        from app.whatsapp.client import WhatsAppClient  # local import: keeps this module free of the WA dependency at import time

        try:
            r = await WhatsAppClient().send_text("".join(ch for ch in s.owner_wa_number if ch.isdigit()), text, preview_url=False)
            if not r.get("dry_run"):
                delivered.append("whatsapp")
        except Exception as e:  # noqa: BLE001
            log.error("owner_whatsapp_failed", error=str(e))
    if await send_telegram(text):
        delivered.append("telegram")
    if s.owner_email and await send_email(s.owner_email, subject, text):
        delivered.append("email")
    if not delivered:
        log.warning("owner_alert_undelivered", subject=subject,
                    message="No owner channel is configured or reachable. Set TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID (works from anywhere), OWNER_EMAIL + RESEND_API_KEY, or OWNER_WA_NUMBER with the Cloud API.")
    else:
        log.info("owner_alerted", subject=subject, channels=delivered)
    return delivered
