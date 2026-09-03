"""Startup preflight for the LLM: proves the key and model work before any customer does.

A bad key or an unavailable model used to fail deep inside a chat turn, wrapped in an SDK
exception repr that reads like a request for more configuration. This runs once at boot,
asks the Models API for the configured model, and logs a plain verdict with the server's
own message. It never blocks startup: the agent degrades to the scripted flow instead."""
from __future__ import annotations

from dataclasses import dataclass

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger("llm.preflight")


@dataclass
class Preflight:
    ok: bool
    provider: str
    model: str
    detail: str


def _explain(status: int | None, server_message: str) -> str:
    if status == 401:
        return "The API key was rejected. Copy a fresh key from console.anthropic.com/settings/keys into ANTHROPIC_API_KEY."
    if status == 403:
        return "The key is valid but not allowed to use this model. Check the key's workspace and model access in the Console, or set LLM_MODEL to a model your workspace can use."
    if status == 404:
        return "The model id is not available to this account. Set LLM_MODEL to one your account lists, e.g. claude-sonnet-5."
    if status == 429:
        return "Rate limited or out of credit. Add credit at console.anthropic.com/settings/billing."
    return server_message


async def run_llm_preflight() -> Preflight:
    s = get_settings()
    provider, model = s.llm_provider, s.resolved_llm_model
    key = s.anthropic_api_key if provider == "anthropic" else s.openai_api_key
    if not key:
        return Preflight(False, provider, model, "no API key configured; scripted fallback agent is active")
    try:
        if provider == "anthropic":
            import anthropic

            client = anthropic.AsyncAnthropic(api_key=key)
            try:
                m = await client.models.retrieve(model)
                return Preflight(True, provider, model, f"key accepted, model '{m.id}' available")
            except anthropic.APIStatusError as e:
                body = e.body if isinstance(e.body, dict) else {}
                server = (body.get("error") or {}).get("message") if isinstance(body.get("error"), dict) else str(e)
                return Preflight(False, provider, model, f"HTTP {e.status_code} {e.type or ''}: {server}. {_explain(e.status_code, server or '')}")
            except anthropic.APIConnectionError as e:
                return Preflight(False, provider, model, f"could not reach api.anthropic.com: {e}")
        else:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=key)
            m = await client.models.retrieve(model)
            return Preflight(True, provider, model, f"key accepted, model '{m.id}' available")
    except Exception as e:  # noqa: BLE001 - preflight must never crash startup
        return Preflight(False, provider, model, f"{type(e).__name__}: {e}")


async def log_llm_preflight() -> Preflight:
    p = await run_llm_preflight()
    if p.ok:
        log.info("llm_preflight_ok", provider=p.provider, model=p.model, detail=p.detail)
    else:
        log.error("llm_preflight_failed", provider=p.provider, model=p.model, detail=p.detail,
                  consequence="Anvi will use the scripted fallback until this is fixed.")
    return p
