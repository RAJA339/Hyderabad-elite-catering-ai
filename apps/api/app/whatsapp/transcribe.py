"""Voice notes → text. OpenAI Whisper when a key exists; otherwise returns None so the agent
politely asks for text. Telugu + English + Hindi are handled by Whisper's auto-detect."""
from __future__ import annotations

import io

from app.core.config import get_settings


async def transcribe(audio: bytes, mime: str) -> str | None:
    s = get_settings()
    if not s.openai_api_key:
        return None
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=s.openai_api_key)
    ext = "ogg" if "ogg" in mime else "mp3" if "mpeg" in mime else "m4a"
    f = io.BytesIO(audio)
    f.name = f"note.{ext}"
    r = await client.audio.transcriptions.create(model="whisper-1", file=f, prompt="Hyderabad catering enquiry in Telugu, Hindi or English.")
    return (r.text or "").strip() or None
