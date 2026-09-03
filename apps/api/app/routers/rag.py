from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.rag.evaluate import run_eval
from app.rag.indexing import index_tenant
from app.rag.retrieval import retrieve
from app.routers.deps import manager, staff, tenant_from_principal

router = APIRouter(prefix="/rag", tags=["rag"])


class QueryIn(BaseModel):
    query: str
    diet: str | None = None
    guest_count: int | None = None


@router.post("/query", dependencies=[Depends(staff)])
async def query(body: QueryIn, tenant_id=Depends(tenant_from_principal)):
    r = await retrieve(tenant_id=tenant_id, query=body.query, diet=body.diet, guest_count=body.guest_count)
    return {"plan": r.plan.__dict__, "cache_hit": r.cache_hit, "latency_ms": r.latency_ms, "context": r.context_blocks, "enrichment": r.enrichment,
            "hits": [{"id": str(h.chunk_id), "score": h.score, "breadcrumb": h.breadcrumb, "source_type": h.source_type} for h in r.hits]}


@router.post("/reindex", dependencies=[Depends(manager)])
async def reindex(source_types: list[str] | None = None, tenant_id=Depends(tenant_from_principal)):
    return await index_tenant(tenant_id, source_types=set(source_types) if source_types else None)


@router.post("/eval", dependencies=[Depends(manager)])
async def evaluate(generate: bool = True, tenant_id=Depends(tenant_from_principal)):
    return await run_eval(tenant_id, generate=generate)
