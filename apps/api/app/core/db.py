"""asyncpg pool wrapper. All SQL lives next to the module that owns it; this only manages
connections, transactions and JSON/UUID codecs."""
from __future__ import annotations

import json
import re
import socket
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import asyncpg

from app.core.config import get_settings  # noqa: F401  (re-exported for tests to clear the cache)

_pool: asyncpg.Pool | None = None


async def _init_conn(conn: asyncpg.Connection) -> None:
    await conn.set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")
    await conn.set_type_codec("json", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")


class DatabaseUnreachable(RuntimeError):
    """Raised with the host and a likely cause instead of a driver traceback."""


def _host_of(dsn: str) -> str:
    m = re.search(r"@([^/?]+)", dsn)
    return m.group(1) if m else "(unknown host)"


async def init_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        dsn = get_settings().database_url.replace("postgresql+asyncpg://", "postgresql://")
        host = _host_of(dsn)
        try:
            _pool = await asyncpg.create_pool(dsn, min_size=2, max_size=20, init=_init_conn)
        except socket.gaierror as e:
            raise DatabaseUnreachable(
                f"Cannot resolve the database host '{host}'.\n"
                "DATABASE_URL points at a name that does not exist. Check it with:\n"
                "    python -m app.cli doctor\n"
                "A placeholder from the docs copied verbatim is the usual cause."
            ) from e
        except (ConnectionRefusedError, OSError) as e:
            local = host.split(":")[0] in ("localhost", "127.0.0.1", "::1")
            if local and get_settings().app_env != "dev":
                raise DatabaseUnreachable(
                    f"DATABASE_URL is not set, so it defaulted to '{host}' - and nothing is listening there.\n"
                    "On Railway, Render or Fly, add DATABASE_URL to the service's variables and redeploy.\n"
                    "It is the same connection string you used for `python -m app.cli bootstrap`."
                ) from e
            raise DatabaseUnreachable(
                f"Cannot reach the database at '{host}': {e}.\n"
                "If it is local, start it with: docker compose up -d db redis"
            ) from e
        except asyncpg.InvalidPasswordError as e:
            raise DatabaseUnreachable(f"The database at '{host}' rejected the username or password in DATABASE_URL.") from e
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB pool not initialised; call init_pool() on startup")
    return _pool


@asynccontextmanager
async def transaction() -> AsyncIterator[asyncpg.Connection]:
    async with pool().acquire() as conn:
        async with conn.transaction():
            yield conn


async def fetch(sql: str, *args: Any) -> list[asyncpg.Record]:
    async with pool().acquire() as conn:
        return await conn.fetch(sql, *args)


async def fetchrow(sql: str, *args: Any) -> asyncpg.Record | None:
    async with pool().acquire() as conn:
        return await conn.fetchrow(sql, *args)


async def fetchval(sql: str, *args: Any) -> Any:
    async with pool().acquire() as conn:
        return await conn.fetchval(sql, *args)


async def execute(sql: str, *args: Any) -> str:
    async with pool().acquire() as conn:
        return await conn.execute(sql, *args)
