"""Vector store abstraction. PgVectorStore is the default; QdrantStore is the upgrade path."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.core import db


@dataclass
class Hit:
    chunk_id: UUID
    document_id: UUID
    source_id: UUID
    content: str
    breadcrumb: str
    metadata: dict
    score: float
    source_type: str
    parent_content: str | None = None


@dataclass(frozen=True)
class Filters:
    tenant_id: UUID
    diet: str | None = None
    guest_count: int | None = None
    source_types: tuple[str, ...] = ()
    festival_keys: tuple[str, ...] = ()
    price_band: str | None = None

    def sql(self, start_idx: int) -> tuple[str, list]:
        """Build WHERE fragments starting at $start_idx."""
        clauses = ["c.tenant_id = $1", "c.status = 'active'", "(c.valid_to IS NULL OR c.valid_to > now())"]
        args: list = []
        i = start_idx
        if self.diet:
            clauses.append(f"(c.diet IS NULL OR c.diet = 'any' OR c.diet = ${i} OR (${i} = 'jain' AND c.diet = 'veg') OR (${i} = 'mixed'))")
            args.append(self.diet)
            i += 1
        if self.guest_count:
            clauses.append(f"(c.guest_min IS NULL OR c.guest_min <= ${i}) AND (c.guest_max IS NULL OR c.guest_max >= ${i})")
            args.append(self.guest_count)
            i += 1
        if self.source_types:
            clauses.append(f"c.source_type = ANY(${i}::rag_source_type[])")
            args.append(list(self.source_types))
            i += 1
        if self.festival_keys:
            clauses.append(f"(cardinality(c.festival_keys) = 0 OR c.festival_keys && ${i}::text[])")
            args.append(list(self.festival_keys))
            i += 1
        if self.price_band:
            clauses.append(f"(c.price_band IS NULL OR c.price_band = 'any' OR c.price_band = ${i})")
            args.append(self.price_band)
            i += 1
        return " AND ".join(clauses), args


class VectorStore(Protocol):
    async def dense_search(self, embedding: Sequence[float], filters: Filters, k: int) -> list[Hit]: ...
    async def lexical_search(self, query: str, filters: Filters, k: int) -> list[Hit]: ...
    async def expand_parents(self, hits: list[Hit]) -> list[Hit]: ...


def _vec(e: Sequence[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in e) + "]"


class PgVectorStore:
    SELECT = """
      SELECT c.id AS chunk_id, c.document_id, c.source_id, c.content, d.breadcrumb, c.metadata, c.source_type::text AS source_type
    """

    async def dense_search(self, embedding: Sequence[float], filters: Filters, k: int) -> list[Hit]:
        where, args = filters.sql(3)
        dim = len(embedding)
        rows = await db.fetch(
            f"""{self.SELECT}, 1 - (c.embedding::halfvec({dim}) <=> $2::halfvec({dim})) AS score
                FROM rag_chunks c JOIN rag_documents d ON d.id = c.document_id
                WHERE {where} AND c.embedding IS NOT NULL
                ORDER BY c.embedding::halfvec({dim}) <=> $2::halfvec({dim}) LIMIT {int(k)}""",
            filters.tenant_id, _vec(embedding), *args,
        )
        return [self._hit(r) for r in rows]

    async def lexical_search(self, query: str, filters: Filters, k: int) -> list[Hit]:
        where, args = filters.sql(3)
        rows = await db.fetch(
            f"""{self.SELECT}, ts_rank_cd(c.content_tsv, websearch_to_tsquery('english', $2)) AS score
                FROM rag_chunks c JOIN rag_documents d ON d.id = c.document_id
                WHERE {where} AND c.content_tsv @@ websearch_to_tsquery('english', $2)
                ORDER BY score DESC LIMIT {int(k)}""",
            filters.tenant_id, query, *args,
        )
        return [self._hit(r) for r in rows]

    async def expand_parents(self, hits: list[Hit]) -> list[Hit]:
        ids = list({h.document_id for h in hits})
        if not ids:
            return hits
        rows = await db.fetch("SELECT id, content FROM rag_documents WHERE id = ANY($1::uuid[])", ids)
        parents = {r["id"]: r["content"] for r in rows}
        for h in hits:
            h.parent_content = parents.get(h.document_id)
        return hits

    @staticmethod
    def _hit(r) -> Hit:
        return Hit(
            chunk_id=r["chunk_id"], document_id=r["document_id"], source_id=r["source_id"], content=r["content"],
            breadcrumb=r["breadcrumb"], metadata=r["metadata"] or {}, score=float(r["score"] or 0), source_type=r["source_type"],
        )


class QdrantStore:  # pragma: no cover — upgrade path
    """Drop-in replacement when scale/filtering outgrows pgvector. Requires `qdrant-client`."""

    def __init__(self, url: str, collection: str = "hecai_chunks"):
        from qdrant_client import AsyncQdrantClient  # type: ignore

        self.client = AsyncQdrantClient(url=url)
        self.collection = collection

    async def dense_search(self, embedding, filters, k):
        raise NotImplementedError("Implement payload filters mirroring Filters.sql()")

    async def lexical_search(self, query, filters, k):
        raise NotImplementedError("Use Qdrant sparse vectors (BM25/SPLADE) here")

    async def expand_parents(self, hits):
        return hits
