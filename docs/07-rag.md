# Production RAG Layer

Two strictly separated pipelines. Code: `apps/api/app/rag/`.

## Indexing (offline / scheduled) — `indexing.py`
| Step | Implementation |
|---|---|
| Sources | `rag_sources` rows: menu catalog (from `menu_items`), package templates, policies (`docs/knowledge/*.md`), FAQs, festival rules (rendered from `festivals` + `discount_rules`), historical winning quotes (`quotes` with status `confirmed`) |
| Chunking | `chunking.py` — structure-aware split on `#`/`##` headings and menu categories → parent chunks (≤ 1,800 tokens) → child chunks (300–600 tokens, 15% overlap). Every child is prefixed with its breadcrumb header (`Menu > Starters > Non-Veg`) and a metadata line. |
| Embeddings | `embeddings.py` — `text-embedding-3-large` (3072-d, default) or `voyage-3-large`. Same provider for index and query, enforced by `EMBEDDING_MODEL` stored on each chunk. |
| Store | `rag_chunks` (pgvector, HNSW cosine) + `content_tsv` (`tsvector`, `english` config) for BM25-style ranking with `ts_rank_cd`. |
| Incremental | `content_hash` per chunk; unchanged hashes are skipped; deleted sources cascade. |
| Metadata | category, subcategory, diet (veg/non-veg/jain/mixed), guest_min/guest_max, season tags, festival keys, price_band, status, source_type, valid_from/valid_to, updated_at |

Volatile numbers (prices, live costs, kitchen load) are **never** embedded. Chunks reference
item ids; the query pipeline enriches with live SQL.

## Query (real-time) — `retrieval.py`
1. **Rewrite** — `query_rewriter.py`: extracts intent (`menu`, `policy`, `pricing`, `festival`,
   `faq`, `smalltalk`) and filters (guest count, diet, festival, budget band) with a fast LLM
   call, falling back to regex heuristics if the LLM is unavailable.
2. **Pre-filter** — SQL `WHERE` on metadata JSONB (`diet`, `guest range`, `status='active'`,
   `valid_to IS NULL OR valid_to > now()`).
3. **Hybrid retrieval** — dense top-40 (`<=>` cosine) ∪ BM25 top-40 (`ts_rank_cd`).
4. **RRF** — `score = Σ 1/(k + rank)` with k = 60.
5. **Rerank** — Cohere `rerank-v3.5` when `COHERE_API_KEY` is set, else a local cross-encoder
   (`BAAI/bge-reranker-base` via sentence-transformers) else RRF order. Keep top 6.
6. **Parent expansion** — replace child text with parent text for the top 3 to give the model
   richer context while keeping precise retrieval.
7. **Live enrichment** — `enrichment.py` pulls current per-plate costs for referenced items,
   margin targets and active festival windows.
8. **Assembly** — `[K1]…[Kn]` blocks with metadata header for grounded generation.

## Semantic cache — `cache.py`
Redis stores `(query_embedding, filters_hash) → answer/context` for 6 hours; a hit requires
cosine ≥ 0.96 **and** identical filter hash **and** no price change since caching
(`prices_version` key is bumped by the ingestion job).

## Observability
`observability.py` wraps every retrieval and generation in a LangFuse trace when
`LANGFUSE_PUBLIC_KEY` is set; otherwise it logs structured spans to stdout.

## Evaluation — `eval/`
`eval/queries.jsonl` holds 30 real catering questions with expected sources and reference
answers. `apps/api/app/rag/evaluate.py` computes context precision / recall, faithfulness and
answer relevancy (RAGAS-style, LLM-judged when a key is present, lexical otherwise) and
writes `rag_eval_runs`. The nightly worker fails loudly if faithfulness drops below 0.85.

## Upgrade path
The vector store is behind `VectorStore` protocol (`store.py`). `PgVectorStore` is the
default; `QdrantStore` is a drop-in when payload filtering or scale demands it.
