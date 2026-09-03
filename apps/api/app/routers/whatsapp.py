"""Meta Cloud API webhook: GET verification, POST events. Signature-verified, deduped, async."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request, Response

from app.agent.orchestrator import INTERACTIVE_INTENTS, handle_inbound
from app.core import db
from app.core.cache import seen_once
from app.core.config import get_settings
from app.core.logging import get_logger
from app.routers.deps import default_tenant
from app.whatsapp.client import WhatsAppClient
from app.whatsapp.transcribe import transcribe
from app.whatsapp.webhook import InboundMessage, parse_payload, verify_signature

router = APIRouter(prefix="/webhooks/whatsapp", tags=["whatsapp"])
log = get_logger("whatsapp.webhook")


@router.get("")
async def verify(hub_mode: str = Query(alias="hub.mode"), hub_token: str = Query(alias="hub.verify_token"), hub_challenge: str = Query(alias="hub.challenge")):
    if hub_mode == "subscribe" and hub_token == get_settings().whatsapp_verify_token:
        return Response(content=hub_challenge, media_type="text/plain")
    raise HTTPException(403, "verification failed")


@router.post("")
async def receive(request: Request, background: BackgroundTasks):
    body = await request.body()
    if not verify_signature(get_settings().whatsapp_app_secret, body, request.headers.get("x-hub-signature-256")):
        raise HTTPException(401, "bad signature")
    payload = await request.json()
    messages, statuses = parse_payload(payload)
    for s in statuses:
        await db.execute("UPDATE messages SET status = $2 WHERE external_id = $1", s.message_id, s.status)
        await db.execute("UPDATE notifications SET status = $2::notification_status WHERE external_id = $1 AND $2 IN ('delivered','read','failed')", s.message_id, s.status)
    for m in messages:
        if not await seen_once(f"wa:msg:{m.message_id}"):
            continue
        await db.execute("INSERT INTO webhook_events (provider, external_id, payload) VALUES ('whatsapp', $1, $2) ON CONFLICT DO NOTHING", m.message_id, m.raw)
        background.add_task(process_message, m)
    return {"ok": True}


async def process_message(m: InboundMessage) -> None:
    client = WhatsAppClient()
    tenant_id = await default_tenant()
    text, kind, media = m.text, m.kind, None
    try:
        await client.mark_read(m.message_id)
        if m.kind == "interactive" and m.interactive_id:
            text = INTERACTIVE_INTENTS.get(m.interactive_id, m.text or m.interactive_id)
        elif m.kind == "audio" and m.media_id:
            blob, mime = await client.download_media(m.media_id)
            text = await transcribe(blob, mime)
            media = {"media_id": m.media_id, "mime": mime}
            if not text:
                await client.send_text(m.wa_id, "I couldn't hear that voice note clearly — could you type it for me? 🙏")
                return
        elif m.kind in ("image", "document"):
            media = {"media_id": m.media_id, "mime": m.mime}
            text = m.text or "(customer shared a file)"
        elif m.kind == "location" and m.location:
            text = f"Venue location: {m.location.get('name') or ''} {m.location.get('address') or ''} ({m.location.get('latitude')},{m.location.get('longitude')})"
        elif m.kind == "reaction":
            return
        if not text:
            return
        reply = await handle_inbound(tenant_id=tenant_id, wa_id=m.wa_id, text=text, profile_name=m.profile_name, external_id=m.message_id, kind=kind, media=media)
        if reply.buttons:
            await client.send_buttons(m.wa_id, reply.text, reply.buttons)
        else:
            await client.send_text(m.wa_id, reply.text)
        await db.execute("UPDATE webhook_events SET processed_at = now() WHERE provider='whatsapp' AND external_id=$1", m.message_id)
    except Exception as e:  # noqa: BLE001
        log.error("process_failed", message_id=m.message_id, error=str(e))
        await db.execute("UPDATE webhook_events SET error=$2 WHERE provider='whatsapp' AND external_id=$1", m.message_id, str(e)[:500])
        try:
            await client.send_text(m.wa_id, "One moment andi — a small hiccup on my side. Our team will follow up here shortly.")
        except Exception:  # noqa: BLE001
            pass
