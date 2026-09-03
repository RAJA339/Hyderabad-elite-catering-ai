"""WhatsApp Business Cloud API client (Meta Graph). Works with any BSP that exposes the
Cloud API surface. Every send is logged; failures raise so callers can retry/queue."""
from __future__ import annotations

from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger("whatsapp")


class WhatsAppClient:
    def __init__(self):
        s = get_settings()
        self.base = f"https://graph.facebook.com/{s.whatsapp_api_version}/{s.whatsapp_phone_number_id}"
        self.token = s.whatsapp_access_token
        self.enabled = bool(s.whatsapp_access_token and s.whatsapp_phone_number_id)

    async def _post(self, path: str, payload: dict) -> dict:
        if not self.enabled:
            log.info("whatsapp_disabled_dry_run", payload=payload)
            return {"id": None, "dry_run": True}
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(f"{self.base}/{path}", headers={"Authorization": f"Bearer {self.token}"}, json=payload)
            if r.status_code >= 400:
                log.error("whatsapp_send_failed", status=r.status_code, body=r.text[:500])
                r.raise_for_status()
            data = r.json()
            return {"id": (data.get("messages") or [{}])[0].get("id"), "raw": data}

    async def send_text(self, to: str, body: str, preview_url: bool = True) -> dict:
        return await self._post("messages", {"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": body[:4096], "preview_url": preview_url}})

    async def send_buttons(self, to: str, body: str, buttons: list[tuple[str, str]], header: str | None = None) -> dict:
        payload: dict[str, Any] = {
            "messaging_product": "whatsapp", "to": to, "type": "interactive",
            "interactive": {"type": "button", "body": {"text": body[:1024]},
                            "action": {"buttons": [{"type": "reply", "reply": {"id": bid, "title": title[:20]}} for bid, title in buttons[:3]]}},
        }
        if header:
            payload["interactive"]["header"] = {"type": "text", "text": header[:60]}
        return await self._post("messages", payload)

    async def send_list(self, to: str, body: str, button: str, rows: list[tuple[str, str, str]], section_title: str = "Options") -> dict:
        return await self._post("messages", {
            "messaging_product": "whatsapp", "to": to, "type": "interactive",
            "interactive": {"type": "list", "body": {"text": body[:1024]},
                            "action": {"button": button[:20], "sections": [{"title": section_title[:24],
                                       "rows": [{"id": rid, "title": t[:24], "description": d[:72]} for rid, t, d in rows[:10]]}]}},
        })

    async def send_template(self, to: str, name: str, language: str, body_params: list[str]) -> dict:
        return await self._post("messages", {
            "messaging_product": "whatsapp", "to": to, "type": "template",
            "template": {"name": name, "language": {"code": language},
                         "components": [{"type": "body", "parameters": [{"type": "text", "text": p} for p in body_params]}] if body_params else []},
        })

    async def send_document(self, to: str, link: str, filename: str, caption: str | None = None) -> dict:
        return await self._post("messages", {"messaging_product": "whatsapp", "to": to, "type": "document",
                                             "document": {"link": link, "filename": filename, "caption": caption or ""}})

    async def send_image(self, to: str, link: str, caption: str | None = None) -> dict:
        return await self._post("messages", {"messaging_product": "whatsapp", "to": to, "type": "image", "image": {"link": link, "caption": caption or ""}})

    async def mark_read(self, message_id: str) -> None:
        if self.enabled:
            await self._post("messages", {"messaging_product": "whatsapp", "status": "read", "message_id": message_id})

    async def download_media(self, media_id: str) -> tuple[bytes, str]:
        async with httpx.AsyncClient(timeout=60) as client:
            meta = await client.get(f"https://graph.facebook.com/{get_settings().whatsapp_api_version}/{media_id}", headers={"Authorization": f"Bearer {self.token}"})
            meta.raise_for_status()
            url, mime = meta.json()["url"], meta.json().get("mime_type", "application/octet-stream")
            blob = await client.get(url, headers={"Authorization": f"Bearer {self.token}"})
            blob.raise_for_status()
            return blob.content, mime
