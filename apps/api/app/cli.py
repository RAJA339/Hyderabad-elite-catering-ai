"""Operational CLI: python -m app.cli <command>
  refresh-costs   recompute menu_item_costs from latest prices
  reindex         run the RAG indexing pipeline
  eval            run the RAG evaluation set
  ingest-csv PATH ingest a supplier/market CSV
  sync-festivals  upsert the static festival calendar
  check-llm       test the API key, workspace and model without starting the server
  simulate "text" run one agent turn from the CLI (dev)
"""
from __future__ import annotations

import asyncio
import json
import sys

from app.core import db
from app.core.logging import configure_logging
from app.routers.deps import default_tenant


async def check_llm() -> None:
    """Credentials only: deliberately runs before any database connection so it works
    when Postgres is down, which is often exactly when someone is debugging setup."""
    from app.agent.preflight import run_llm_preflight
    from app.core.config import ENV_FILES, get_settings

    st = get_settings()
    print("env files    :", ", ".join(str(p) for p in ENV_FILES))
    print("provider     :", st.llm_provider)
    print("model        :", st.resolved_llm_model)
    print("api key      :", "set" if (st.anthropic_api_key or st.openai_api_key) else "NOT SET")
    print("workspace id :", st.anthropic_workspace_id or "NOT SET")
    r = await run_llm_preflight()
    print()
    print(("PASS  " if r.ok else "FAIL  ") + r.detail)


async def main(argv: list[str]) -> None:
    configure_logging()
    if argv and argv[0] == "check-llm":
        await check_llm()
        return
    await db.init_pool()
    try:
        tid = await default_tenant()
        cmd = argv[0] if argv else "help"
        if cmd == "refresh-costs":
            from app.pricing.repository import refresh_item_costs
            print(json.dumps({"items": await refresh_item_costs(tid)}))
        elif cmd == "reindex":
            from app.rag.indexing import index_tenant
            print(json.dumps(await index_tenant(tid)))
        elif cmd == "eval":
            from app.rag.evaluate import run_eval
            print(json.dumps(await run_eval(tid), indent=2, default=str))
        elif cmd == "ingest-csv":
            from app.pricing.ingestion import ManualCsvSource, ingest
            print(json.dumps(await ingest(tid, [ManualCsvSource(open(argv[1], encoding="utf-8").read(), "supplier_csv")]), default=str))
        elif cmd == "sync-festivals":
            from app.festivals.repository import sync_calendar
            print(json.dumps({"festivals": await sync_calendar(None)}))
        elif cmd == "simulate":
            from app.agent.orchestrator import handle_inbound
            r = await handle_inbound(tenant_id=tid, wa_id=argv[2] if len(argv) > 2 else "919000000001", text=argv[1], profile_name="CLI Tester")
            print(r.text)
            if r.tool_calls:
                print(json.dumps(r.tool_calls, indent=2, default=str))
        else:
            print(__doc__)
    finally:
        await db.close_pool()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
