"""Operational CLI: python -m app.cli <command>
  refresh-costs   recompute menu_item_costs from latest prices
  reindex         run the RAG indexing pipeline
  eval            run the RAG evaluation set
  ingest-csv PATH ingest a supplier/market CSV
  sync-festivals  upsert the static festival calendar
  simulate "text" run one agent turn from the CLI (dev)
"""
from __future__ import annotations

import asyncio
import json
import sys

from app.core import db
from app.core.logging import configure_logging
from app.routers.deps import default_tenant


async def main(argv: list[str]) -> None:
    configure_logging()
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
