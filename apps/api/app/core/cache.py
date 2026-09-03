"""Redis helpers: dedup, locks, rate limits, semantic cache storage."""
from __future__ import annotations

import redis.asyncio as redis

from app.core.config import get_settings

_client: redis.Redis | None = None


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
    """Returns True the first time a key is seen (SET NX), False on repeats."""
    return bool(await get_redis().set(key, "1", ex=ttl_s, nx=True))


async def rate_limit(key: str, limit: int, window_s: int) -> bool:
    r = get_redis()
    n = await r.incr(key)
    if n == 1:
        await r.expire(key, window_s)
    return n <= limit
