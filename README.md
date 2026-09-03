# HEC-AI — Hyderabad Elite Catering AI

**A WhatsApp-first conversational sales platform for catering in Hyderabad.**
It qualifies leads, designs and prices complete packages from *today's* Hyderabad ingredient
prices, applies festival discounts only when margin is protected, closes with a price lock and
advance, and runs the customer lifecycle — with an Admin Command Center and a Client Portal.

```
WhatsApp / Web chat ──▶ FastAPI agent (tools + production RAG) ──▶ PostgreSQL + pgvector · Redis
                                                       │
                              Next.js 15 ── /admin (owner)  ·  /portal (client, magic link / OTP)
```

## What's inside
| Path | What it is |
|---|---|
| `docs/01-architecture.md` | Text architecture diagram and key flows |
| `docs/02-database-schema.md` · `db/schema.sql` | Complete schema incl. RAG tables, consent, audit, quotes as versions |
| `docs/03-feature-prioritization.md` | MVP → V1 → Ultra |
| `docs/04-agent-system-prompt.md` | Full system prompt for "Anvi" and how it consumes RAG + tools |
| `docs/05-api.md` · `docs/06-conversation-flows.md` · `docs/07-rag.md` · `docs/08-environment.md` | API, sample conversations, RAG design, env vars |
| `apps/api` | FastAPI: pricing engine, festival rule engine, RAG (index + query), agent orchestrator, WhatsApp gateway, lifecycle workers |
| `apps/web` | Next.js 15 + TypeScript + Tailwind: landing + chat widget, Admin Command Center, Client Portal |
| `db/seed/seed.sql` | Tenant, users, 37 ingredients with 8-day price history, 42 recipes, 6 package templates, 11 discount rules, templates, venues |
| `knowledge/` | Policies, FAQ, venue guide (indexed by the RAG pipeline) |
| `eval/queries.jsonl` | 30 real catering questions for RAGAS-style evaluation |
| `scripts/publish-to-new-repo.sh` | Push this folder to its own GitHub repository with a clean history |

## The moat, in one paragraph
Every menu item is a **recipe** (`menu_item_ingredients`). Hourly ingestion writes Hyderabad
wholesale/retail prices; item cost = Σ(qty × ₹/unit × waste) + labour + overhead + amortised
setup. Package price = cost ÷ (1 − target margin) rounded **up** to a ₹5 price point. Discounts
are evaluated after pricing and **rejected if margin would fall below the floor**. Cost spikes
trigger transparent capped surcharges or high-margin substitutions, and the customer sees
"Today's Hyderabad market price vs our price" on every quote. The LLM never invents a number:
the output guardrail strips any rupee amount that did not come from a tool call.

## Quick start
```bash
cp .env.example .env                      # add ANTHROPIC_API_KEY (or OPENAI_API_KEY), WhatsApp creds
docker compose up -d db redis             # Postgres 16 + pgvector (schema + seed auto-applied), Redis
cd apps/api && pip install -e ".[dev]"    # Python 3.11+ (.env is read from the repo root)
python -m app.cli refresh-costs           # compute item costs from seeded prices
python -m app.cli reindex                 # build the RAG index (uses HashEmbedder if no key — dev only)
uvicorn app.main:app --reload             # http://localhost:8000/docs
cd ../web && npm install && npm run dev   # http://localhost:3000
```
Try the agent without WhatsApp:
```bash
python -m app.cli simulate "Hi, need catering for gruhapravesam on 14th Oct, 120 people all veg in Kompally, budget 500-600 per plate"
```
Admin login: `owner@hec.example` / `Admin@12345` (seeded; change it).

At startup the API tests the key against Anthropic and logs `llm_preflight_ok` or
`llm_preflight_failed` with the server's own message and a one-line fix. Until it passes, Anvi
answers with a scripted fallback rather than the conversational agent. If it reports that
`anthropic-workspace-id is required`, your key is identity-linked: set `ANTHROPIC_WORKSPACE_ID`
to the workspace id from the Claude Console under Settings then Workspaces.

## WhatsApp setup (Cloud API via your BSP)
1. Create a Meta app + WhatsApp product (or use a BSP such as Gupshup/Interakt/Wati that exposes the Cloud API).
2. Set `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_APP_SECRET`, `WHATSAPP_VERIFY_TOKEN`.
3. Point the webhook to `https://<api>/api/webhooks/whatsapp` and subscribe to `messages`.
4. Submit the utility templates listed in `db/seed/seed.sql` (`whatsapp_templates`) for approval.

## Tests
```bash
cd apps/api && pytest -q        # pricing engine, discount engine, chunking/RRF, qualification, guardrails
cd apps/web && npm run typecheck
```

## Deployment
- **Web:** Vercel (`apps/web`, env `NEXT_PUBLIC_API_URL`).
- **API:** Railway / Fly / ECS with `apps/api/Dockerfile`; run one instance with `RUN_SCHEDULER=1`, others `0`.
- **DB:** Neon / Supabase / RDS with `pgvector ≥ 0.7` (halfvec HNSW). **Redis:** Upstash / ElastiCache.

## Compliance
Consent is captured per purpose before any personal data is stored (DPDP), every state change
is written to `audit_log`, and `DELETE /api/leads/customers/{id}` performs erasure while
retaining financial records.

## Publishing as its own repository
```bash
scripts/publish-to-new-repo.sh git@github.com:<you>/hyderabad-elite-catering-ai.git
```
