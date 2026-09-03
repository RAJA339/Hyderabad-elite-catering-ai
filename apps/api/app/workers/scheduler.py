"""APScheduler jobs: hourly price ingestion, notification dispatch, nightly reindex + eval,
festival re-engagement, post-event follow-ups. Locks in Redis prevent double runs."""
from __future__ import annotations

import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.cache import get_redis
from app.core.config import get_settings
from app.core.logging import get_logger
from app.leads import lifecycle
from app.pricing.ingestion import HttpJsonSource, ManualCsvSource, ingest
from app.pricing.repository import refresh_item_costs
from app.rag.evaluate import run_eval
from app.rag.indexing import index_tenant
from app.routers.deps import default_tenant

log = get_logger("workers")
scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")


async def _locked(name: str, ttl: int = 3300) -> bool:
    try:
        return bool(await get_redis().set(f"job:{name}", "1", ex=ttl, nx=True))
    except Exception:  # noqa: BLE001
        return True


async def job_ingest_prices():
    if not await _locked("ingest"):
        return
    tid = await default_tenant()
    sources = []
    url = os.getenv("PRICE_SOURCE_URL")
    if url:
        sources.append(HttpJsonSource(url, os.getenv("PRICE_SOURCE_LABEL", "market_feed"), {"Authorization": os.getenv("PRICE_SOURCE_AUTH", "")}))
    csv_path = os.getenv("PRICE_SOURCE_CSV")
    if csv_path and os.path.exists(csv_path):
        sources.append(ManualCsvSource(open(csv_path, encoding="utf-8").read(), "supplier_csv"))
    if sources:
        await ingest(tid, sources)
    else:
        await refresh_item_costs(tid)
        log.info("ingest_skipped_no_sources")


async def job_dispatch_notifications():
    if not await _locked("dispatch", ttl=50):
        return
    n = await lifecycle.dispatch_due()
    if n:
        log.info("notifications_sent", n=n)


async def job_nightly():
    if not await _locked("nightly", ttl=20000):
        return
    tid = await default_tenant()
    await index_tenant(tid)
    await lifecycle.schedule_festival_reengagement(tid)
    try:
        summary = await run_eval(tid, generate=bool(get_settings().anthropic_api_key or get_settings().openai_api_key))
        if not summary.get("gate_passed", True):
            log.error("rag_eval_gate_failed", **summary)
    except Exception as e:  # noqa: BLE001
        log.error("rag_eval_failed", error=str(e))


def start():
    s = get_settings()
    scheduler.add_job(job_ingest_prices, CronTrigger.from_crontab(s.price_ingest_cron), id="ingest", replace_existing=True)
    scheduler.add_job(job_dispatch_notifications, "interval", minutes=1, id="dispatch", replace_existing=True)
    scheduler.add_job(job_nightly, CronTrigger(hour=2, minute=30), id="nightly", replace_existing=True)
    scheduler.start()
    log.info("scheduler_started")


def stop():
    if scheduler.running:
        scheduler.shutdown(wait=False)
