"""HEC-AI API entrypoint."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core import db
from app.core.cache import close_redis
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.routers import admin, auth, chat, festivals, health, leads, payments, portal, pricing, public, rag, voice, whatsapp

log = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    await db.init_pool()
    if os.getenv("RUN_SCHEDULER", "1") == "1":
        from app.workers import scheduler

        scheduler.start()
    st = get_settings()
    if st.menu_source == "sri_sai_raja":
        # The owner's card is data in the repo; the database follows it on every boot.
        try:
            from app.menu import loader
            from app.routers.deps import default_tenant

            applied = await loader.ensure(await default_tenant())
            if applied:
                log.info("menu_applied_on_startup", **applied)
        except Exception as e:  # noqa: BLE001 — never keep the API down over the menu
            log.error("menu_apply_failed", error=str(e))
    has_key = bool(st.anthropic_api_key or st.openai_api_key)
    log.info("startup", env=st.app_env, llm=st.resolved_llm_model, llm_key_present=has_key,
             workspace_id=st.anthropic_workspace_id or "(not set)",
             cors_origins=st.cors_origin_list,
             effort=st.llm_effort, embeddings=st.resolved_embedding_model)
    if st.app_env != "dev" and any("localhost" in o for o in st.cors_origin_list):
        log.warning("cors_still_localhost", origins=st.cors_origin_list,
                    message="Browsers on the deployed site will be blocked. Set CORS_ORIGINS to the site's exact address, e.g. https://your-app.vercel.app, with no trailing slash.")
    if not has_key:
        from app.core.config import ENV_FILES

        log.warning("no_llm_key", message="Running the scripted fallback agent. Set ANTHROPIC_API_KEY (or OPENAI_API_KEY) in one of these files.",
                    env_files=[str(p) for p in ENV_FILES])
    else:
        from app.agent.preflight import log_llm_preflight

        await log_llm_preflight()
    yield
    from app.workers import scheduler

    scheduler.stop()
    await close_redis()
    await db.close_pool()


app = FastAPI(title="HEC-AI — Hyderabad Elite Catering AI", version="0.1.0", lifespan=lifespan,
              description="WhatsApp-first catering sales agent with live Hyderabad pricing, festival intelligence and production RAG.")
async def _catch_unhandled(request: Request, call_next):
    """Turn any unhandled exception into a normal JSON 500.

    Starlette's own error handler sits OUTSIDE the CORS middleware, so an exception that
    reaches it produces a response with no CORS headers — which a browser cannot read, and
    reports as an unreachable API rather than as the server error it is.
    """
    try:
        return await call_next(request)
    except Exception as e:  # noqa: BLE001 — the client gets the type and message, the log gets the trace
        log.exception("unhandled_error", path=request.url.path, method=request.method)
        return JSONResponse({"detail": f"{type(e).__name__}: {e}"}, status_code=500)


# Registered before CORS so that CORS ends up the outer of the two and still stamps its
# headers onto the 500 above; the middleware added last is the outermost.
app.add_middleware(BaseHTTPMiddleware, dispatch=_catch_unhandled)
app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_origin_list, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

for r in (health, auth, whatsapp, payments, chat, pricing, leads, admin, rag, portal, festivals, public, voice):
    app.include_router(r.router, prefix="/api" if r is not health else "")
