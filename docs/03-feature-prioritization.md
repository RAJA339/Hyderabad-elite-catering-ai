# Feature Prioritization — MVP → V1 → Ultra

Guiding rule: ship the moat first (pricing engine + WhatsApp agent), then the surfaces,
then the delighters. Every phase is deployable on its own.

## MVP (weeks 1–4) — "Sell a package on WhatsApp, profitably"
| Area | Scope | Status in repo |
|---|---|---|
| WhatsApp gateway | Cloud API webhook, signature verification, dedup, text + interactive replies | ✅ `apps/api/app/whatsapp` |
| Lead qualification | FSM: date, guests (≤500 hard cap), veg/non-veg, venue, budget, occasion | ✅ `app/agent/qualification.py` |
| Pricing engine | Ingredient prices → recipe cost → item cost → package price with margin guard | ✅ `app/pricing` |
| Package generation | 2–3 tiered packages (Classic / Signature / Royal) with live pricing | ✅ `app/pricing/packages.py` |
| Live modifications | add guests, remove item, make Jain, add live counter | ✅ `modify_quote` tool |
| Festival discounts | Calendar + rule engine, margin-protected, best-offer selection | ✅ `app/festivals` |
| Customer vault + consent | Leads, customers, quotes, messages, consents, audit log | ✅ `db/schema.sql` |
| RAG v1 | Parent/child chunking, pgvector + BM25, RRF, rerank hook, semantic cache | ✅ `app/rag` |
| Admin dashboard | Pipeline, margin health, kitchen calendar | ✅ `apps/web/app/admin` |
| Client portal | Quote view, live market widget, change request, magic link | ✅ `apps/web/app/portal` |
| Seed + docs + eval set | Menu catalog, festival calendar, prices, 30 eval queries | ✅ |

## V1 (weeks 5–10) — "Run the business on it"
- Payments: Razorpay links for advance, webhook → `payments`, auto invoice PDF.
- WhatsApp utility templates end-to-end (price lock, menu change, reminder, thank-you).
- Voice notes: Whisper/Deepgram transcription (Telugu + Hyderabadi English), reply in text.
- Quote PDF + menu image cards via the BSP media API.
- Human hand-off inbox in Admin with full context and takeover/return-to-AI.
- Supplier price alerts with thresholds and inventory hints.
- Analytics: funnels, festival performance, CLV, rebooking rate, exports.
- LangFuse tracing + nightly RAGAS-style eval gating deploys.
- Multi-tenant hardening: per-tenant keys, RBAC roles (owner, manager, kitchen, sales).

## Ultra (weeks 11+) — "Impossible to copy"
- Visual buffet-layout mockups (image generation from the finalized menu).
- Predictive upsell engine trained on `quote_events` + conversions.
- Tracked "share with family/office" links with per-viewer engagement.
- Price-lock certificate (signed PDF with hash) for bookings above ₹2L.
- Venue partnership marketplace with preferred rates.
- Post-event photo collection + AI testimonial drafts (consent-gated).
- Instagram DM channel, multi-language voice replies.
- Qdrant migration path if chunk count > 5M or filter latency > 50 ms p95.
