"""Semantic cache in Redis. A hit requires cosine ≥ threshold, identical filter hash and the
same prices_version (bumped on every ingestion) so stale numbers are never served."""
from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Sequence

from app.core.cache import get_redis
from app.core.config import get_settings


def _cos(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


def filters_hash(filters: dict) -> str:
    return hashlib.sha1(json.dumps(filters, sort_keys=True, default=str).encode()).hexdigest()[:12]


class SemanticCache:
    def __init__(self, tenant_id: str):
        self.key = f"semcache:{tenant_id}"
        self.tenant_id = tenant_id

    async def _version(self) -> str:
        return str(await get_redis().get(f"prices_version:{self.tenant_id}") or "0")

    async def get(self, embedding: Sequence[float], fhash: str) -> dict | None:
        s = get_settings()
        r = get_redis()
        version = await self._version()
        entries = await r.lrange(self.key, 0, 199)
        for raw in entries:
            e = json.loads(raw)
            if e["fhash"] != fhash or e["version"] != version:
                continue
            if _cos(embedding, e["embedding"]) >= s.semantic_cache_threshold:
                return e["payload"]
        return None

    async def put(self, embedding: Sequence[float], fhash: str, payload: dict) -> None:
        s = get_settings()
        r = get_redis()
        entry = json.dumps({"embedding": [round(x, 5) for x in embedding], "fhash": fhash, "version": await self._version(), "payload": payload})
        await r.lpush(self.key, entry)
        await r.ltrim(self.key, 0, 199)
        await r.expire(self.key, s.semantic_cache_ttl_s)
