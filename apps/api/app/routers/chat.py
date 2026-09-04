"""Website chat widget endpoint (secondary channel). Same orchestrator, session id as wa_id."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.agent.orchestrator import handle_inbound
from app.core.cache import rate_limit
from app.core.logging import get_logger
from app.routers.deps import default_tenant

router = APIRouter(prefix="/chat", tags=["chat"])
log = get_logger("chat")


class ChatIn(BaseModel):
    session_id: str = Field(min_length=6, max_length=64)
    message: str = Field(min_length=1, max_length=2000)
    name: str | None = None


@router.post("")
async def chat(body: ChatIn, tenant_id=Depends(default_tenant)):
    if not await rate_limit(f"rl:chat:{body.session_id}", 30, 60):
        return {"reply": "You're sending messages very fast — give me a few seconds. 🙂", "buttons": []}
    try:
        r = await handle_inbound(tenant_id=tenant_id, wa_id=f"web:{body.session_id}", text=body.message, profile_name=body.name, channel="web_chat")
    except Exception as e:  # noqa: BLE001 - the widget shows this, so name the real cause
        log.exception("chat_failed", session=body.session_id)
        raise HTTPException(500, f"{type(e).__name__}: {e}") from e
    return {"reply": r.text, "buttons": [{"id": b[0], "title": b[1]} for b in r.buttons], "escalated": r.escalated, "latency_ms": r.latency_ms,
            "attachments": r.attachments}
