"""Reranking: Cohere Rerank when available → local cross-encoder → RRF order."""
from __future__ import annotations

from collections.abc import Sequence

from app.core.config import get_settings
from app.rag.store import Hit


async def rerank(query: str, hits: Sequence[Hit], top_n: int = 6) -> list[Hit]:
    s = get_settings()
    if not hits:
        return []
    if s.cohere_api_key:
        try:
            import cohere  # type: ignore

            client = cohere.AsyncClientV2(api_key=s.cohere_api_key)
            r = await client.rerank(model=s.rerank_model, query=query, documents=[h.content for h in hits], top_n=top_n)
            out = []
            for res in r.results:
                h = hits[res.index]
                h.score = float(res.relevance_score)
                out.append(h)
            return out
        except Exception:  # noqa: BLE001 — fall through to local reranker
            pass
    try:
        from sentence_transformers import CrossEncoder  # type: ignore

        model = _local_model(CrossEncoder)
        scores = model.predict([(query, h.content) for h in hits])
        ranked = sorted(zip(hits, scores, strict=False), key=lambda hs: -float(hs[1]))
        out = []
        for h, sc in ranked[:top_n]:
            h.score = float(sc)
            out.append(h)
        return out
    except Exception:  # noqa: BLE001
        return list(hits)[:top_n]


_LOCAL = None


def _local_model(CrossEncoder):
    global _LOCAL
    if _LOCAL is None:
        _LOCAL = CrossEncoder("BAAI/bge-reranker-base", max_length=512)
    return _LOCAL
