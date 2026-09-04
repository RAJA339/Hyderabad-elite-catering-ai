"""Redis helpers: dedup, locks, rate limits, semantic cache storage."""
from __future__ import annotations

import redis.asyncio as redis

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger("cache")

_client: redis.Redis | None = None
_warned = False


def redis_degraded(op: str, e: Exception) -> None:
    """Redis is optional. Losing it must never fail a request: an exception raised here
    escapes past the CORS middleware, so the browser sees a header-less 500 and reports it
    as an unreachable API rather than as a server error."""
    global _warned
    if not _warned:
        _warned = True
        log.warning("redis_unavailable", op=op, error=f"{type(e).__name__}: {e}",
                    message="Continuing without Redis: rate limiting, webhook de-duplication and the semantic cache are off. Set REDIS_URL to enable them.")


def get_redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(get_settings().redis_url, decode_responses=True)
    return _client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


async def seen_once(key: str, ttl_s: int = 86400) -> bool:
    """Returns True the first time a key is seen (SET NX), False on repeats.
    Without Redis every message is treated as new: a rare duplicate reply beats silence."""
    try:
        return bool(await get_redis().set(key, "1", ex=ttl_s, nx=True))
    except Exception as e:  # noqa: BLE001
        redis_degraded("seen_once", e)
        return True


async def rate_limit(key: str, limit: int, window_s: int) -> bool:
    """Allows the request when Redis is unavailable — an unenforced limit beats a dead endpoint."""
    try:
        r = get_redis()
        n = await r.incr(key)
        if n == 1:
            await r.expire(key, window_s)
        return n <= limit
    except Exception as e:  # noqa: BLE001
        redis_degraded("rate_limit", e)
        return True
