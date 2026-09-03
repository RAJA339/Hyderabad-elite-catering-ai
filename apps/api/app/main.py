"""HEC-AI API entrypoint."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core import db
from app.core.cache import close_redis
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.routers import admin, auth, chat, festivals, health, leads, payments, portal, pricing, rag, whatsapp

log = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    await db.init_pool()
    if os.getenv("RUN_SCHEDULER", "1") == "1":
        from app.workers import scheduler

        scheduler.start()
    log.info("startup", env=get_settings().app_env, llm=get_settings().resolved_llm_model, embeddings=get_settings().resolved_embedding_model)
    yield
    from app.workers import scheduler

    scheduler.stop()
    await close_redis()
    await db.close_pool()


app = FastAPI(title="HEC-AI — Hyderabad Elite Catering AI", version="0.1.0", lifespan=lifespan,
              description="WhatsApp-first catering sales agent with live Hyderabad pricing, festival intelligence and production RAG.")
app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_origin_list, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

for r in (health, auth, whatsapp, payments, chat, pricing, leads, admin, rag, portal, festivals):
    app.include_router(r.router, prefix="/api" if r is not health else "")
