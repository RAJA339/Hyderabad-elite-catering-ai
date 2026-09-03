"""Operational CLI: python -m app.cli <command>
  refresh-costs   recompute menu_item_costs from latest prices
  reindex         run the RAG indexing pipeline
  eval            run the RAG evaluation set
  ingest-csv PATH ingest a supplier/market CSV
  sync-festivals  upsert the static festival calendar
  check-llm       test the API key, workspace and model without starting the server
  doctor          show which .env files exist and what the app actually read from them
  set-env K=V     safely write one setting into the root .env (handles newlines/encoding)
  bootstrap       prepare a new database: schema, seed, costs, index, admin password
  set-password EMAIL [PASSWORD]   set a staff password (generates a strong one if omitted)
  simulate "text" run one agent turn from the CLI (dev)
"""
from __future__ import annotations

import asyncio
import json
import sys

from app.core import db
from app.core.logging import configure_logging
from app.routers.deps import default_tenant

SENSITIVE = ("KEY", "SECRET", "TOKEN", "PASSWORD")


def _mask(key: str, value: str) -> str:
    if not value:
        return "(empty)"
    if any(w in key.upper() for w in SENSITIVE):
        return f"{value[:7]}...{value[-4:]} ({len(value)} chars)" if len(value) > 14 else f"set ({len(value)} chars)"
    return value


def set_env(assignment: str) -> None:
    """Write one KEY=VALUE into the root .env correctly.

    Windows shells make this deceptively hard: Add-Content joins onto the last line when the
    file has no trailing newline, editors append .txt, and encodings vary. Doing it here
    removes all three."""
    from app.core.config import ENV_FILES

    if "=" not in assignment:
        print("Usage: python -m app.cli set-env KEY=VALUE")
        return
    key, value = assignment.split("=", 1)
    key, value = key.strip(), value.strip().strip('"').strip("'")
    target = ENV_FILES[0]

    lines = target.read_text(encoding="utf-8-sig").splitlines() if target.exists() else []
    replaced = False
    for i, line in enumerate(lines):
        if line.lstrip().startswith(f"{key}=") and not line.lstrip().startswith("#"):
            lines[i] = f"{key}={value}"
            replaced = True
            break
    if not replaced:
        lines.append(f"{key}={value}")
    target.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    shown = f"{value[:7]}...{value[-4:]}" if any(w in key.upper() for w in SENSITIVE) and len(value) > 14 else value
    print(f"{'Updated' if replaced else 'Added'} {key}={shown}")
    print(f"in {target}")
    print("\nNext: python -m app.cli check-llm")


def doctor() -> None:
    """Inspect the .env files on disk. Windows editors silently rename '.env' to '.env.txt',
    which looks correct in Explorer and is invisible to the app, so list what is really there."""
    from dotenv import dotenv_values

    from app.core.config import ENV_FILES, get_settings

    print("=" * 68)
    print("ENV FILE DOCTOR")
    print("=" * 68)
    found_any = False
    for target in ENV_FILES:
        folder = target.parent
        print(f"\nFolder: {folder}")
        if not folder.exists():
            print("  ! folder does not exist")
            continue
        candidates = sorted(x for x in folder.iterdir() if x.name.lower().startswith(".env") or x.name.lower() == "env.txt")
        if not candidates:
            print("  (no .env* files here)")
        for c in candidates:
            note = ""
            if c.name == ".env":
                note = "  <-- THIS is the one the app reads"
                found_any = True
            elif c.name.lower() in (".env.txt", "env.txt", ".env.text"):
                note = "  <-- WRONG NAME. Rename it to exactly '.env'"
            elif c.name == ".env.example":
                note = "  (template only, never read)"
            print(f"  {c.name:<22} {c.stat().st_size:>6} bytes{note}")

    if not found_any:
        print("\nNo file named exactly '.env' was found, which is why nothing is read.")
        print("Fix it in PowerShell from the repo root:")
        print("    Rename-Item .env.txt .env")
        print("Or create it directly, which never adds a .txt extension:")
        print("    notepad.exe (New-Item -Path .env -ItemType File -Force).FullName")
        return

    for target in ENV_FILES:
        if not target.exists():
            continue
        print(f"\nParsed from {target}:")
        parsed = dotenv_values(target)
        if not parsed:
            print("  (file is empty or has no KEY=VALUE lines)")
        for k, v in parsed.items():
            flag = ""
            # A shell append onto a file with no trailing newline welds two settings together.
            if v and "=" in v and not v.lstrip().startswith("#"):
                flag = "   <-- two settings on one line; run set-env to repair"
            print(f"  {k:<26} = {_mask(k, v or '')}{flag}")
        raw = target.read_text(encoding="utf-8-sig", errors="replace")
        if raw and not raw.endswith("\n"):
            print("  ! file has no trailing newline: a shell append would join onto the last line")

    st = get_settings()
    print("\nWhat the app actually resolved:")
    print(f"  ANTHROPIC_API_KEY          = {_mask('KEY', st.anthropic_api_key or '')}")
    print(f"  ANTHROPIC_WORKSPACE_ID     = {st.anthropic_workspace_id or 'NOT SET'}")
    print(f"  LLM_PROVIDER / model       = {st.llm_provider} / {st.resolved_llm_model}")
    print("\nNext: python -m app.cli check-llm")


# The seed ships a known bcrypt hash so local dev has a login. It is public in the repo,
# so it must never survive into a deployment.
DEV_PASSWORD_HASH = "$2b$12$3F2FQmQ1r3xk1rY8VZk1JeMCTQSPCx1Yp8gYLtMGhuNwzM2p0OY8m"


async def set_password(email: str, password: str | None = None) -> None:
    import secrets

    from app.core.security import hash_password

    if not email:
        print("Usage: python -m app.cli set-password EMAIL [PASSWORD]")
        return
    generated = password is None
    password = password or secrets.token_urlsafe(15)
    row = await db.fetchrow("UPDATE users SET password_hash = $2 WHERE email = $1 RETURNING full_name, role::text AS role",
                            email, hash_password(password))
    if not row:
        print(f"No user with email {email}. Seeded accounts: owner@hec.example, sales@hec.example")
        return
    print(f"Password updated for {email} ({row['role']}).")
    if generated:
        print(f"\n    {password}\n")
        print("Copy it now - it is not stored anywhere in readable form.")


async def bootstrap() -> None:
    """Prepare a brand-new database: schema, seed, costs, search index.

    docker compose applies schema.sql and seed.sql automatically on first start, but a hosted
    Postgres has neither, so deployment needs this."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    async with db.pool().acquire() as conn:
        exists = await conn.fetchval("SELECT to_regclass('public.tenants') IS NOT NULL")
        if not exists:
            print("Applying schema...")
            await conn.execute((root / "db" / "schema.sql").read_text(encoding="utf-8"))
        else:
            print("Schema already present, skipping.")
        seeded = await conn.fetchval("SELECT count(*) FROM tenants")
        if not seeded:
            print("Seeding menus, prices, festivals and rules...")
            await conn.execute((root / "db" / "seed" / "seed.sql").read_text(encoding="utf-8"))
        else:
            print("Tenant already seeded, skipping.")

    from app.pricing.repository import refresh_item_costs
    from app.rag.indexing import index_tenant
    from app.routers.deps import default_tenant

    tid = await default_tenant()
    print(f"Item costs computed: {await refresh_item_costs(tid)}")
    print(f"Search index: {(await index_tenant(tid))['chunks_embedded']} chunks embedded")

    still_default = await db.fetchval("SELECT count(*) FROM users WHERE password_hash = $1", DEV_PASSWORD_HASH)
    if still_default:
        print("\nThe seeded admin password is published in this repository. Rotating it now.")
        await set_password("owner@hec.example")
        await db.execute("UPDATE users SET password_hash = NULL WHERE password_hash = $1", DEV_PASSWORD_HASH)
        print("Other seeded logins disabled. Use set-password to enable one.")
    print("\nReady.")


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
    if argv and argv[0] == "set-env":
        set_env(argv[1] if len(argv) > 1 else "")
        return
    if argv and argv[0] == "doctor":
        doctor()
        return
    if argv and argv[0] == "check-llm":
        await check_llm()
        return
    await db.init_pool()
    try:
        cmd = argv[0] if argv else "help"
        # bootstrap runs against an empty database, so the tenant lookup cannot come first.
        if cmd == "bootstrap":
            await bootstrap()
            return
        if cmd == "set-password":
            await set_password(argv[1] if len(argv) > 1 else "", argv[2] if len(argv) > 2 else None)
            return
        if cmd == "help":
            print(__doc__)
            return

        tid = await default_tenant()
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
