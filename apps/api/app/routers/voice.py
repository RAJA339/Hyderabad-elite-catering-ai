"""Anvi answers the phone.

Twilio (and Exotel/Plivo, which speak the same shape) POST a form to a webhook on every turn
of a call: first when it connects, then again with the caller's speech transcribed. Each time
we hand the transcript to the same orchestrator that serves WhatsApp — same tools, same
pricing, same guardrails — and return TwiML telling the carrier what to say and to listen
again. The caller is identified by their phone number, so a call and a WhatsApp thread from
the same person are one lead.

Set VOICE_ENABLED=1 and point the provider's "A call comes in" webhook at
POST /api/voice/incoming. Everything else is already here.
"""
from __future__ import annotations

from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response

from app.agent.orchestrator import handle_inbound
from app.core.config import get_settings
from app.core.logging import get_logger
from app.routers.deps import default_tenant
from app.voice.speech import for_speech

router = APIRouter(prefix="/voice", tags=["voice"])
log = get_logger("voice")

GREETING = ("Namaste! You've reached Hyderabad Elite Catering. I'm Anvi. "
            "Tell me the occasion, the date and roughly how many guests, and I'll price a full menu for you.")
TROUBLE = "Sorry, I didn't catch that. Could you tell me the occasion and how many guests?"


def _twiml(say: str, *, gather: bool = True, hangup: bool = False) -> Response:
    s = get_settings()
    spoken = escape(say)
    voice = f'<Say voice="{s.voice_tts_voice}" language="{s.voice_language}">{spoken}</Say>'
    if hangup:
        xml = f"<Response>{voice}<Hangup/></Response>"
    elif gather:
        # speechTimeout=auto ends the turn when the caller stops talking, rather than on a fixed clock.
        xml = (f'<Response><Gather input="speech" action="/api/voice/turn" method="POST" '
               f'language="{s.voice_language}" speechTimeout="auto" actionOnEmptyResult="true">{voice}</Gather></Response>')
    else:
        xml = f"<Response>{voice}</Response>"
    return Response(content=f'<?xml version="1.0" encoding="UTF-8"?>{xml}', media_type="application/xml")


def _guard() -> None:
    if not get_settings().voice_enabled:
        raise HTTPException(404, "voice is not enabled; set VOICE_ENABLED=1 and configure a telephony provider")


@router.post("/incoming")
async def incoming(request: Request, From: str = Form(default="")) -> Response:
    """The call has connected. Greet, then listen."""
    _guard()
    log.info("call_started", caller=From[-4:] if From else "unknown")
    return _twiml(GREETING)


@router.post("/turn")
async def turn(request: Request, From: str = Form(default=""), SpeechResult: str = Form(default=""),
               tenant_id=Depends(default_tenant)) -> Response:
    """The caller said something. Answer it with the same brain that answers WhatsApp."""
    _guard()
    said = (SpeechResult or "").strip()
    if not said:
        return _twiml(TROUBLE)

    wa_id = "".join(ch for ch in From if ch.isdigit()) or "voice:unknown"
    try:
        reply = await handle_inbound(tenant_id=tenant_id, wa_id=wa_id, text=said, channel="voice", kind="text")
    except Exception as e:  # noqa: BLE001 — a caller must never hear a stack trace
        log.error("voice_turn_failed", error=f"{type(e).__name__}: {e}")
        return _twiml("Sorry, something went wrong on my side. Our team will call you right back.", hangup=True)

    spoken = for_speech(reply.text)
    log.info("call_turn", caller=wa_id[-4:], heard=said[:80], said=spoken[:80], escalated=reply.escalated)
    if reply.escalated:
        return _twiml(spoken + " I'm connecting you to our events lead now.", hangup=True)
    return _twiml(spoken)


@router.post("/status")
async def status(CallStatus: str = Form(default=""), From: str = Form(default="")) -> dict:
    """Call ended. Logged so the admin can see call volume alongside chat."""
    log.info("call_status", status=CallStatus, caller=From[-4:] if From else "unknown")
    return {"ok": True}
