"""Webhook verification + normalisation of Cloud API payloads into InboundMessage objects."""
from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass, field

from app.core.config import get_settings


@dataclass
class InboundMessage:
    wa_id: str
    message_id: str
    kind: str                     # text | interactive | audio | image | document | location | reaction | unsupported
    text: str | None = None
    interactive_id: str | None = None
    media_id: str | None = None
    mime: str | None = None
    profile_name: str | None = None
    location: dict | None = None
    timestamp: str | None = None
    raw: dict = field(default_factory=dict)


@dataclass
class StatusUpdate:
    message_id: str
    status: str                   # sent | delivered | read | failed
    recipient: str


def verify_signature(app_secret: str | None, body: bytes, header: str | None) -> bool:
    if not app_secret:
        return get_settings().app_env == "dev"
    if not header or not header.startswith("sha256="):
        return False
    digest = hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, header.split("=", 1)[1])


def parse_payload(payload: dict) -> tuple[list[InboundMessage], list[StatusUpdate]]:
    messages: list[InboundMessage] = []
    statuses: list[StatusUpdate] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            names = {c.get("wa_id"): c.get("profile", {}).get("name") for c in value.get("contacts", [])}
            for m in value.get("messages", []):
                kind = m.get("type", "unsupported")
                im = InboundMessage(wa_id=m["from"], message_id=m["id"], kind=kind, profile_name=names.get(m["from"]), timestamp=m.get("timestamp"), raw=m)
                if kind == "text":
                    im.text = m["text"]["body"]
                elif kind == "interactive":
                    inter = m["interactive"]
                    reply = inter.get("button_reply") or inter.get("list_reply") or {}
                    im.interactive_id, im.text = reply.get("id"), reply.get("title")
                elif kind == "button":
                    im.kind, im.text, im.interactive_id = "interactive", m["button"].get("text"), m["button"].get("payload")
                elif kind in ("audio", "image", "document", "video"):
                    media = m[kind]
                    im.media_id, im.mime, im.text = media.get("id"), media.get("mime_type"), media.get("caption")
                elif kind == "location":
                    im.location = m["location"]
                    im.text = m["location"].get("address") or m["location"].get("name")
                elif kind == "reaction":
                    im.text = m["reaction"].get("emoji")
                messages.append(im)
            for s in value.get("statuses", []):
                statuses.append(StatusUpdate(s["id"], s["status"], s.get("recipient_id", "")))
    return messages, statuses
