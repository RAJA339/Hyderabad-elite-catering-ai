"""Embedding providers. The same provider/model is used for indexing and querying, and the
model name is persisted on every chunk so a mismatch is detected at query time."""
from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

import httpx

from app.core.config import get_settings


class Embedder(Protocol):
    model: str
    dim: int

    async def embed(self, texts: Sequence[str], *, input_type: str = "document") -> list[list[float]]: ...


class OpenAIEmbedder:
    def __init__(self, api_key: str, model: str = "text-embedding-3-large"):
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=api_key)
        self.model, self.dim = model, 3072

    async def embed(self, texts: Sequence[str], *, input_type: str = "document") -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), 96):
            batch = list(texts[i : i + 96])
            r = await self._client.embeddings.create(model=self.model, input=batch)
            out.extend([d.embedding for d in r.data])
        return out


class VoyageEmbedder:
    def __init__(self, api_key: str, model: str = "voyage-3-large"):
        self._key, self.model, self.dim = api_key, model, 1024

    async def embed(self, texts: Sequence[str], *, input_type: str = "document") -> list[list[float]]:
        out: list[list[float]] = []
        async with httpx.AsyncClient(timeout=60) as client:
            for i in range(0, len(texts), 64):
                r = await client.post(
                    "https://api.voyageai.com/v1/embeddings",
                    headers={"Authorization": f"Bearer {self._key}"},
                    json={"input": list(texts[i : i + 64]), "model": self.model, "input_type": "query" if input_type == "query" else "document"},
                )
                r.raise_for_status()
                out.extend([d["embedding"] for d in r.json()["data"]])
        return out


class HashEmbedder:
    """Deterministic local fallback for tests / offline dev. NOT for production."""

    def __init__(self, dim: int = 3072):
        self.model, self.dim = "hash-dev", dim

    async def embed(self, texts: Sequence[str], *, input_type: str = "document") -> list[list[float]]:
        import hashlib
        import math

        vecs = []
        for t in texts:
            v = [0.0] * self.dim
            for tok in t.lower().split():
                h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
                v[h % self.dim] += 1.0
            n = math.sqrt(sum(x * x for x in v)) or 1.0
            vecs.append([x / n for x in v])
        return vecs


def get_embedder() -> Embedder:
    s = get_settings()
    if s.embedding_provider == "openai" and s.openai_api_key:
        return OpenAIEmbedder(s.openai_api_key, s.resolved_embedding_model)
    if s.embedding_provider == "voyage" and s.voyage_api_key:
        return VoyageEmbedder(s.voyage_api_key, s.resolved_embedding_model)
    return HashEmbedder(s.embedding_dim)
