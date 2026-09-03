"""Real-time retrieval pipeline:
rewrite → metadata pre-filter → hybrid (dense + BM25) → RRF → rerank → parent expansion →
live enrichment → context assembly. Semantic cache short-circuits repeats."""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from datetime import date
from uuid import UUID

from app.core import db
from app.rag.cache import SemanticCache, filters_hash
from app.rag.embeddings import get_embedder
from app.rag.enrichment import enrich
from app.rag.fusion import rrf
from app.rag.observability import span
from app.rag.query_rewriter import QueryPlan, plan_query
from app.rag.rerank import rerank
from app.rag.store import Filters, Hit, PgVectorStore, VectorStore

DENSE_K, LEXICAL_K, FINAL_K, PARENT_EXPAND = 40, 40, 6, 3


@dataclass
class RetrievalResult:
    plan: QueryPlan
    hits: list[Hit]
    context_blocks: list[str]
    enrichment: dict
    cache_hit: bool = False
    latency_ms: int = 0
    query_id: UUID | None = None
    debug: dict = field(default_factory=dict)


def assemble_context(hits: list[Hit]) -> list[str]:
    blocks = []
    for i, h in enumerate(hits, start=1):
        body = h.parent_content if (h.parent_content and i <= PARENT_EXPAND) else h.content
        header = f"[K{i}] source={h.source_type} · {h.breadcrumb} · id={str(h.chunk_id)[:8]}"
        blocks.append(f"{header}\n{body}")
    return blocks


async def retrieve(
    *, tenant_id: UUID, query: str, lead_id: UUID | None = None, event_date: date | None = None,
    diet: str | None = None, guest_count: int | None = None, store: VectorStore | None = None, use_llm_rewrite: bool = True,
) -> RetrievalResult:
    t0 = time.perf_counter()
    store = store or PgVectorStore()
    plan = await plan_query(query, use_llm=use_llm_rewrite)
    plan.diet = diet or plan.diet
    plan.guest_count = guest_count or plan.guest_count
    if not plan.needs_retrieval:
        return RetrievalResult(plan=plan, hits=[], context_blocks=[], enrichment={}, latency_ms=int((time.perf_counter() - t0) * 1000))

    filters = Filters(
        tenant_id=tenant_id, diet=plan.diet, guest_count=plan.guest_count,
        source_types=tuple(plan.source_types), festival_keys=tuple(plan.festival_keys), price_band=plan.price_band,
    )
    fhash = filters_hash({**asdict(filters), "tenant_id": str(tenant_id)})
    embedder = get_embedder()
    with span("rag.retrieve", intent=plan.intent, tenant=str(tenant_id)):
        qvec = (await embedder.embed([plan.rewritten], input_type="query"))[0]
        cache = SemanticCache(str(tenant_id))
        cached = None
        try:
            cached = await cache.get(qvec, fhash)
        except Exception:  # noqa: BLE001 — Redis optional in dev
            pass
        if cached:
            hits = [Hit(**{**h, "chunk_id": UUID(h["chunk_id"]), "document_id": UUID(h["document_id"]), "source_id": UUID(h["source_id"])}) for h in cached["hits"]]
            return RetrievalResult(plan=plan, hits=hits, context_blocks=cached["context_blocks"], enrichment=cached["enrichment"],
                                   cache_hit=True, latency_ms=int((time.perf_counter() - t0) * 1000))

        dense = await store.dense_search(qvec, filters, DENSE_K)
        lexical = await store.lexical_search(plan.rewritten, filters, LEXICAL_K)
        fused = [h for h, _ in rrf([dense, lexical], key=lambda h: h.chunk_id)]
        reranked = await rerank(plan.rewritten, fused[: DENSE_K], top_n=FINAL_K)
        reranked = await store.expand_parents(reranked)
        enrichment = await enrich(tenant_id, reranked, event_date) if plan.needs_live_prices or plan.intent in ("menu", "festival") else {}
        blocks = assemble_context(reranked)
        latency = int((time.perf_counter() - t0) * 1000)

        query_id = None
        try:
            query_id = await db.fetchval(
                """INSERT INTO rag_queries (tenant_id, lead_id, raw_query, rewritten_query, intent, filters, dense_ids, bm25_ids, fused_ids, reranked_ids, cache_hit, latency_ms)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,false,$11) RETURNING id""",
                tenant_id, lead_id, query, plan.rewritten, plan.intent,
                {"diet": plan.diet, "guest_count": plan.guest_count, "festival_keys": plan.festival_keys, "price_band": plan.price_band, "source_types": plan.source_types},
                [h.chunk_id for h in dense], [h.chunk_id for h in lexical], [h.chunk_id for h in fused[:DENSE_K]], [h.chunk_id for h in reranked], latency,
            )
        except Exception:  # noqa: BLE001
            pass
        try:
            await cache.put(qvec, fhash, {
                "hits": [{**asdict(h), "chunk_id": str(h.chunk_id), "document_id": str(h.document_id), "source_id": str(h.source_id)} for h in reranked],
                "context_blocks": blocks, "enrichment": enrichment,
            })
        except Exception:  # noqa: BLE001
            pass
        return RetrievalResult(plan=plan, hits=reranked, context_blocks=blocks, enrichment=enrichment, latency_ms=latency, query_id=query_id,
                               debug={"dense": len(dense), "lexical": len(lexical), "fused": len(fused)})
