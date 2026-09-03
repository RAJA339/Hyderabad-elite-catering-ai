# API Reference (FastAPI · `/api`)

Interactive docs: `http://localhost:8000/docs`. Staff endpoints need `Authorization: Bearer <jwt>`
from `POST /api/auth/login`. Roles: owner > manager > sales > kitchen > viewer.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/health` | – | DB + Redis liveness |
| POST | `/api/auth/login` | – | `{email,password,tenant}` → JWT |
| GET | `/api/webhooks/whatsapp` | Meta | Webhook verification challenge |
| POST | `/api/webhooks/whatsapp` | HMAC | Inbound messages/statuses (async processing, deduped) |
| POST | `/api/webhooks/razorpay` | HMAC | `payment_link.paid` → advance paid → lifecycle |
| POST | `/api/chat` | rate-limited | Website widget: `{session_id,message}` → `{reply,buttons}` |
| POST | `/api/pricing/quote` | staff | `{guest_count,diet,occasion,event_date}` → 3 tiers + market snapshot + trace |
| GET | `/api/pricing/market` | staff | Latest wholesale/retail per ingredient |
| GET | `/api/pricing/costs` | staff | Cached per-item cost, suggested price, 7-day change |
| GET | `/api/pricing/alerts` | staff | Ingredients that moved beyond their alert threshold |
| POST | `/api/pricing/ingest` | manager | `{csv}` supplier/market prices → recompute costs |
| GET | `/api/leads?stage=` | staff | Pipeline list with latest quote value |
| GET | `/api/leads/{id}` | staff | Lead + full conversation + quote versions + events |
| POST | `/api/leads/{id}/stage` | staff | Move stage (audit-logged) |
| POST | `/api/leads/{id}/reply` | staff | Human reply on WhatsApp; `return_to_ai` ends hand-off |
| GET | `/api/leads/export/customers.csv` | manager | Customer vault export |
| DELETE | `/api/leads/customers/{id}` | owner | DPDP erasure |
| GET | `/api/admin/overview` | staff | Pipeline, margin health, funnel, CLV, open escalations |
| GET | `/api/admin/kitchen-calendar` | staff | Committed guests per day vs 500 capacity |
| GET | `/api/admin/festival-performance` | staff | Quotes, bookings, revenue, discounts per festival |
| GET | `/api/admin/escalations` | staff | Open hand-offs |
| GET | `/api/admin/rag-health` | staff | Index size, query latency, cache hit rate, last eval |
| POST | `/api/rag/query` | staff | Debug retrieval: plan, hits, context, enrichment |
| POST | `/api/rag/reindex` | manager | Incremental reindex (optionally by source type) |
| POST | `/api/rag/eval` | manager | Run eval set, store `rag_eval_runs` |
| GET | `/api/festivals?near=YYYY-MM-DD` | – | Calendar / festivals around a date |
| GET | `/api/festivals/rules` | staff | Active discount rules |
| GET | `/api/portal/{token}` | magic link | Quote bundle: items, events, payments, lock, chat |
| POST | `/api/portal/{token}/change` | magic link | Natural-language change → agent re-prices |
| POST | `/api/portal/{token}/share` | magic link | Tracked share link + wa.me deep link |
| GET | `/api/portal/shared/{slug}` | – | Read-only shared quote (views counted) |
| POST | `/api/portal/otp/request` · `/verify` | – | WhatsApp OTP login → portal session |

## Agent tools (internal)
`save_lead_field`, `price_package`, `modify_quote`, `festival_offers`, `market_snapshot`,
`lock_price`, `record_advance`, `suggest_upsell`, `escalate_to_human` — see `app/agent/tools.py`.
