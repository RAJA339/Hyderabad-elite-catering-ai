# HEC-AI — System Architecture

Hyderabad Elite Catering AI is a WhatsApp-first conversational sales platform. Every
number the customer sees comes from a live pricing engine; every explanation the
agent gives is grounded in a production RAG layer. The two are deliberately kept
apart: **knowledge lives in vectors, numbers live in Postgres.**

```
                                   ┌────────────────────────────────────────────────────┐
                                   │                 CHANNELS                            │
                                   │  WhatsApp Cloud API (BSP)   Web Chat   Instagram DM │
                                   └───────────────┬─────────────────┬───────────────────┘
                                                   │ webhooks         │ REST / SSE
                                                   ▼                  ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│                               FastAPI  —  apps/api  (Python 3.11)                            │
│                                                                                              │
│  ┌──────────────┐   ┌────────────────────┐   ┌───────────────────┐   ┌─────────────────────┐ │
│  │ WhatsApp     │──▶│  Conversation      │──▶│  Agent            │──▶│  Tool Belt          │ │
│  │ Gateway      │   │  Orchestrator      │   │  (LLM + system    │   │  price_package      │ │
│  │ verify, dedup│   │  session, consent, │   │   prompt, tool    │   │  modify_quote       │ │
│  │ media, voice │   │  qualification FSM │   │   loop, guardrails│   │  festival_offers    │ │
│  └──────────────┘   └────────────────────┘   └─────────┬─────────┘   │  market_snapshot    │ │
│                                                        │             │  lock_price/advance │ │
│                                                        ▼             │  escalate_to_human  │ │
│                                     ┌────────────────────────────┐   └──────────┬──────────┘ │
│                                     │  RAG Query Pipeline        │              │            │
│                                     │  rewrite → filter → hybrid │              ▼            │
│                                     │  (pgvector + BM25) → RRF   │   ┌─────────────────────┐ │
│                                     │  → rerank → live enrich    │   │  Pricing Engine     │ │
│                                     │  → semantic cache (Redis)  │   │  ingredient costs   │ │
│                                     └─────────────┬──────────────┘   │  recipe → item cost │ │
│                                                   │                  │  margin guard       │ │
│  ┌────────────────────┐   ┌───────────────────┐   │                  │  market comparison  │ │
│  │ Festival & Discount│   │ Lifecycle Engine  │   │                  └──────────┬──────────┘ │
│  │ Rule Engine        │   │ templates, timers │   │                             │            │
│  │ margin-protected   │   │ re-engagement     │   │                             │            │
│  └────────────────────┘   └───────────────────┘   │                             │            │
│                                                   ▼                             ▼            │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────┐│
│  │  Workers (APScheduler): price ingestion (hourly) · reindex (incremental) · notifications ││
│  │  · post-event follow-ups · festival pre-campaigns · RAG eval nightly                     ││
│  └──────────────────────────────────────────────────────────────────────────────────────────┘│
└──────────────────────────┬─────────────────────────────┬─────────────────────────────────────┘
                           │                             │
                           ▼                             ▼
        ┌──────────────────────────────┐    ┌──────────────────────────────┐
        │  PostgreSQL 16 + pgvector    │    │  Redis 7                     │
        │  relational: leads, quotes,  │    │  semantic cache · rate limit │
        │  prices, festivals, consent  │    │  webhook dedup · job locks   │
        │  vector: rag_chunks (HNSW)   │    └──────────────────────────────┘
        │  fulltext: tsvector (BM25)   │
        └──────────────────────────────┘
                           ▲
                           │ REST / JSON (tenant-scoped JWT, RBAC)
                           │
┌──────────────────────────┴───────────────────────────────────────────────────────────────────┐
│                     Next.js 15  —  apps/web  (TypeScript · Tailwind · shadcn-style UI)       │
│                                                                                              │
│   /admin   Command Center: pipeline, margin health, festival analytics, kitchen calendar,    │
│            supplier alerts, CLV, funnels, customer vault + export                            │
│   /portal  Client Portal (magic link / WhatsApp OTP): live menu builder, live prices,        │
│            market transparency widget, change requests, invoice, chat history, share link    │
│   /        Landing + embedded chat widget                                                    │
└──────────────────────────────────────────────────────────────────────────────────────────────┘

Observability: LangFuse traces on every agent turn + RAG query · structured JSON logs ·
audit_log table for every state mutation · RAGAS-style nightly eval on eval/queries.jsonl.
```

## Key flows

### Inbound WhatsApp message
1. Meta webhook → signature verified (X-Hub-Signature-256) → message id deduped in Redis.
2. Consent gate: first contact triggers a DPDP consent message; state stored in `consents`.
3. Conversation Orchestrator loads the lead + quote state and the qualification FSM
   (date → guests ≤ 500 → veg/non-veg → venue → budget → occasion).
4. Agent turn: RAG retrieval runs *only* for knowledge questions (menu, policy, FAQ).
   Pricing always goes through the `price_package` tool; the LLM never invents a number.
5. Tool results + retrieved chunks are assembled into a grounded context; the reply is
   generated, guard-railed (500-guest cap, margin floor) and sent back via the BSP.
6. Every turn is stored in `messages`; every menu change in `quote_events`.

### Price recalculation
Hourly ingestion writes `ingredient_prices`. Menu items are recipes (`menu_item_ingredients`)
so item cost = Σ(qty_per_guest × ₹/unit) + labour/overhead loading. Package price = cost /
(1 − target margin), rounded to premium price points. If margin after every discount would
drop below `min_margin_pct`, the discount engine rejects it and explains the alternative.

### RAG indexing (offline)
Menu catalog, package templates, policies, FAQs, festival rules, and winning past quotes
→ structure-aware parent/child chunking → embeddings (`text-embedding-3-large` or
`voyage-3-large`) → `rag_documents` / `rag_chunks` with metadata + `tsvector`.
Incremental: content hash per chunk; only changed chunks are re-embedded.

### RAG query (online)
rewrite (intent + filters) → metadata pre-filter → dense top-40 + BM25 top-40 → RRF →
cross-encoder rerank → top 6 → live enrichment (SQL prices, margin rules) → grounded answer.
Semantic cache in Redis short-circuits repeated questions (cosine ≥ 0.96).

## Deployment
- `apps/web` → Vercel. `apps/api` → Railway / Fly / AWS ECS (Dockerfile provided).
- Postgres (Neon / Supabase / RDS with pgvector). Redis (Upstash / ElastiCache).
- Secrets via environment only (see `docs/08-environment.md`).
