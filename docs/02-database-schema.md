# Database Schema

Full DDL: [`db/schema.sql`](../db/schema.sql). Seed: [`db/seed/seed.sql`](../db/seed/seed.sql).
PostgreSQL 16 with `pgvector`, `pgcrypto`, `pg_trgm`, and `citext`.

## Entity map
```
tenants ─┬─ users
         ├─ customers ─┬─ consents (DPDP purposes)
         │             ├─ leads ─┬─ messages (full conversation, tool calls, RAG query ids)
         │             │         ├─ escalations
         │             │         └─ quotes ─┬─ quote_items
         │             │                    ├─ quote_events (every menu change)
         │             │                    ├─ discount_applications
         │             │                    ├─ price_locks (certificate hash)
         │             │                    ├─ payments · invoices
         │             │                    ├─ share_links (tracked)
         │             │                    ├─ event_photos · testimonials
         │             │                    └─ portal_sessions
         │             └─ notifications (outbox, WhatsApp utility templates)
         ├─ ingredients ─ ingredient_prices (time series; view ingredient_current_prices)
         ├─ menu_categories ─ menu_items ─ menu_item_ingredients (recipes) · menu_item_costs (cache)
         ├─ package_templates ─ package_template_items
         ├─ festivals (global or tenant) · discount_rules · upsell_rules · venues
         ├─ whatsapp_templates · webhook_events · audit_log
         └─ RAG: rag_sources ─ rag_documents (parents) ─ rag_chunks (children, vector + tsvector)
                 rag_queries (retrieval log) · rag_eval_cases · rag_eval_runs
```

## Design decisions
- **Recipes drive price.** `menu_item_ingredients.qty_per_guest × ingredient_current_prices`
  gives food cost; `menu_items.labour_cost_per_guest`, `overhead_pct`, `fixed_setup_cost`
  complete it. `menu_item_costs` caches the result after every ingestion.
- **Quotes are immutable versions.** Any change creates a new `version` row plus a
  `quote_events` entry with per-plate before/after, so the portal and WhatsApp
  notifications can show exactly what changed.
- **500-guest cap is enforced in the database** (`CHECK` on `leads.guest_count`,
  `quotes.guest_count`, and `tenants.max_guests`), not only in the agent.
- **Consent is per purpose** and revocable; `customers.deleted_at` supports erasure
  requests while keeping financial records intact.
- **RAG parent/child.** `rag_documents` are parents (rich context), `rag_chunks` are
  children (precise retrieval) with embeddings, generated `tsvector` for BM25-style
  ranking, and denormalised filter columns for fast metadata pre-filtering.
  3072-d embeddings are indexed as `halfvec` (pgvector ≥ 0.7) to fit HNSW limits.
- **Volatile numbers stay relational.** No price is ever embedded; chunks carry item
  slugs which the retrieval pipeline enriches with live SQL.
- **Views:** `ingredient_current_prices` (latest per market) and `kitchen_load`
  (committed guests per date) power the market widget and capacity checks.
