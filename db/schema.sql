-- HEC-AI — PostgreSQL 16 schema (pgvector required)
-- Apply: psql "$DATABASE_URL" -f db/schema.sql
-- Conventions: uuid PKs, tenant_id on every business table, timestamptz, soft status columns.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "citext";

-- ─────────────────────────────────────────────────────────────────────────────
-- Tenancy, auth, audit
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE tenants (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug          text UNIQUE NOT NULL,
  name          text NOT NULL,
  city          text NOT NULL DEFAULT 'Hyderabad',
  currency      text NOT NULL DEFAULT 'INR',
  target_margin_pct numeric(5,2) NOT NULL DEFAULT 40.00,
  min_margin_pct    numeric(5,2) NOT NULL DEFAULT 32.00,
  max_guests    integer NOT NULL DEFAULT 500 CHECK (max_guests <= 500),
  daily_guest_capacity integer NOT NULL DEFAULT 500,
  settings      jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TYPE user_role AS ENUM ('owner','manager','sales','kitchen','viewer');

CREATE TABLE users (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  email         citext,
  phone         text,
  full_name     text NOT NULL,
  role          user_role NOT NULL DEFAULT 'sales',
  password_hash text,
  is_active     boolean NOT NULL DEFAULT true,
  last_login_at timestamptz,
  created_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, email)
);

CREATE TABLE audit_log (
  id            bigserial PRIMARY KEY,
  tenant_id     uuid NOT NULL,
  actor_type    text NOT NULL,            -- user | agent | system | customer
  actor_id      text,
  action        text NOT NULL,            -- quote.item_added, lead.stage_changed, ...
  entity_type   text NOT NULL,
  entity_id     text NOT NULL,
  before        jsonb,
  after         jsonb,
  ip            inet,
  created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX audit_log_entity_idx ON audit_log (tenant_id, entity_type, entity_id, created_at DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- Customers, consent (DPDP), leads, conversations
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE customers (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  wa_id         text NOT NULL,            -- WhatsApp id (E.164 without +)
  phone         text NOT NULL,
  full_name     text,
  email         citext,
  address       text,
  area          text,                     -- Kompally, Gachibowli, ...
  language_pref text NOT NULL DEFAULT 'en-IN',
  tags          text[] NOT NULL DEFAULT '{}',
  lifetime_value numeric(12,2) NOT NULL DEFAULT 0,
  bookings_count integer NOT NULL DEFAULT 0,
  first_seen_at timestamptz NOT NULL DEFAULT now(),
  last_seen_at  timestamptz NOT NULL DEFAULT now(),
  deleted_at    timestamptz,              -- DPDP erasure marker
  UNIQUE (tenant_id, wa_id)
);

CREATE TYPE consent_purpose AS ENUM ('communication','data_storage','marketing','testimonial','photo_use');

CREATE TABLE consents (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL,
  customer_id   uuid NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
  purpose       consent_purpose NOT NULL,
  granted       boolean NOT NULL,
  channel       text NOT NULL DEFAULT 'whatsapp',
  evidence      jsonb NOT NULL DEFAULT '{}'::jsonb,   -- message id, text, timestamp
  granted_at    timestamptz NOT NULL DEFAULT now(),
  revoked_at    timestamptz,
  UNIQUE (customer_id, purpose)
);

CREATE TYPE lead_stage AS ENUM ('new','qualifying','qualified','quoted','negotiating','locked','advance_paid','confirmed','completed','lost');
CREATE TYPE lead_source AS ENUM ('whatsapp','web_chat','instagram','referral','share_link','manual');
CREATE TYPE diet_pref AS ENUM ('veg','non_veg','mixed','jain');

CREATE TABLE leads (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  customer_id   uuid NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
  source        lead_source NOT NULL DEFAULT 'whatsapp',
  stage         lead_stage NOT NULL DEFAULT 'new',
  occasion      text,
  event_date    date,
  event_time    text,
  guest_count   integer CHECK (guest_count IS NULL OR (guest_count > 0 AND guest_count <= 500)),
  diet          diet_pref,
  venue_name    text,
  venue_area    text,
  venue_address text,
  budget_min_per_plate numeric(10,2),
  budget_max_per_plate numeric(10,2),
  qualification jsonb NOT NULL DEFAULT '{}'::jsonb,  -- FSM state: collected fields, missing, turns
  conversion_probability numeric(4,3),
  assigned_user_id uuid REFERENCES users(id),
  handoff_active boolean NOT NULL DEFAULT false,
  lost_reason   text,
  referrer_share_link_id uuid,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX leads_pipeline_idx ON leads (tenant_id, stage, event_date);
CREATE INDEX leads_customer_idx ON leads (customer_id);

CREATE TYPE message_role AS ENUM ('customer','agent','human','system');
CREATE TYPE message_kind AS ENUM ('text','interactive','image','document','audio','template','location','reaction');

CREATE TABLE messages (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL,
  lead_id       uuid NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
  role          message_role NOT NULL,
  kind          message_kind NOT NULL DEFAULT 'text',
  channel       text NOT NULL DEFAULT 'whatsapp',
  external_id   text,                     -- wamid
  content       text,
  transcript    text,                     -- for audio
  media         jsonb,                    -- {url, mime, sha256}
  tool_calls    jsonb,                    -- agent turns: [{name,args,result}]
  rag_query_id  uuid,
  tokens_in     integer,
  tokens_out    integer,
  latency_ms    integer,
  status        text NOT NULL DEFAULT 'sent',  -- sent|delivered|read|failed
  created_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, external_id)
);
CREATE INDEX messages_lead_idx ON messages (lead_id, created_at);

CREATE TABLE escalations (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL,
  lead_id       uuid NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
  reason        text NOT NULL,
  summary       text NOT NULL,
  priority      text NOT NULL DEFAULT 'normal',
  status        text NOT NULL DEFAULT 'open',   -- open|claimed|resolved
  claimed_by    uuid REFERENCES users(id),
  resolved_at   timestamptz,
  created_at    timestamptz NOT NULL DEFAULT now()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- Catalog: ingredients, prices, menu items (recipes), packages
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE ingredients (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  key           text NOT NULL,            -- onion, chicken, paneer
  name          text NOT NULL,
  unit          text NOT NULL,            -- kg | l | pc | dozen
  category      text NOT NULL,            -- vegetable|meat|dairy|grain|oil|spice|other
  is_volatile   boolean NOT NULL DEFAULT false,
  alert_threshold_pct numeric(5,2) NOT NULL DEFAULT 15.00,
  UNIQUE (tenant_id, key)
);

CREATE TABLE ingredient_prices (
  id            bigserial PRIMARY KEY,
  tenant_id     uuid NOT NULL,
  ingredient_id uuid NOT NULL REFERENCES ingredients(id) ON DELETE CASCADE,
  source        text NOT NULL,            -- bowenpally_wholesale | rythu_bazar | supplier:xyz | manual
  market        text NOT NULL DEFAULT 'wholesale',  -- wholesale | retail
  price_per_unit numeric(10,2) NOT NULL,
  observed_at   timestamptz NOT NULL DEFAULT now(),
  raw           jsonb
);
CREATE INDEX ingredient_prices_latest_idx ON ingredient_prices (ingredient_id, market, observed_at DESC);

-- Fast "current price" view: latest wholesale + retail per ingredient
CREATE VIEW ingredient_current_prices AS
SELECT DISTINCT ON (ip.ingredient_id, ip.market)
  ip.tenant_id, ip.ingredient_id, i.key, i.name, i.unit, ip.market,
  ip.price_per_unit, ip.observed_at, ip.source
FROM ingredient_prices ip JOIN ingredients i ON i.id = ip.ingredient_id
ORDER BY ip.ingredient_id, ip.market, ip.observed_at DESC;

CREATE TABLE menu_categories (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  key           text NOT NULL,            -- welcome_drinks|starters|main_veg|main_nonveg|rice_breads|live_counters|desserts
  name          text NOT NULL,
  sort_order    integer NOT NULL DEFAULT 0,
  UNIQUE (tenant_id, key)
);

CREATE TABLE menu_items (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  category_id   uuid NOT NULL REFERENCES menu_categories(id),
  slug          text NOT NULL,
  name          text NOT NULL,
  name_te       text,                     -- Telugu display name
  description   text,
  diet          diet_pref NOT NULL,
  is_jain_ok    boolean NOT NULL DEFAULT false,
  is_live_counter boolean NOT NULL DEFAULT false,
  contains      text[] NOT NULL DEFAULT '{}',   -- onion, garlic, egg, nuts, dairy
  labour_cost_per_guest numeric(10,2) NOT NULL DEFAULT 0,
  overhead_pct  numeric(5,2) NOT NULL DEFAULT 12.00,
  fixed_setup_cost numeric(10,2) NOT NULL DEFAULT 0,   -- live counters
  min_guests    integer NOT NULL DEFAULT 1,
  popularity    integer NOT NULL DEFAULT 0,
  tags          text[] NOT NULL DEFAULT '{}',
  is_active     boolean NOT NULL DEFAULT true,
  image_url     text,
  updated_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, slug)
);

CREATE TABLE menu_item_ingredients (
  menu_item_id  uuid NOT NULL REFERENCES menu_items(id) ON DELETE CASCADE,
  ingredient_id uuid NOT NULL REFERENCES ingredients(id),
  qty_per_guest numeric(10,4) NOT NULL,   -- in ingredient.unit
  waste_pct     numeric(5,2) NOT NULL DEFAULT 5.00,
  PRIMARY KEY (menu_item_id, ingredient_id)
);

CREATE TABLE package_templates (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  key           text NOT NULL,            -- classic_veg, signature_mixed, royal_nonveg
  tier          text NOT NULL,            -- classic|signature|royal
  name          text NOT NULL,
  diet          diet_pref NOT NULL,
  occasions     text[] NOT NULL DEFAULT '{}',
  guest_min     integer NOT NULL DEFAULT 25,
  guest_max     integer NOT NULL DEFAULT 500,
  description   text,
  is_active     boolean NOT NULL DEFAULT true,
  UNIQUE (tenant_id, key)
);

CREATE TABLE package_template_items (
  package_template_id uuid NOT NULL REFERENCES package_templates(id) ON DELETE CASCADE,
  menu_item_id  uuid NOT NULL REFERENCES menu_items(id),
  is_optional   boolean NOT NULL DEFAULT false,
  PRIMARY KEY (package_template_id, menu_item_id)
);

-- Cached computed cost per menu item (refreshed after each price ingestion)
CREATE TABLE menu_item_costs (
  menu_item_id  uuid PRIMARY KEY REFERENCES menu_items(id) ON DELETE CASCADE,
  tenant_id     uuid NOT NULL,
  food_cost_per_guest numeric(10,2) NOT NULL,
  total_cost_per_guest numeric(10,2) NOT NULL,
  suggested_price_per_guest numeric(10,2) NOT NULL,
  market_retail_equiv_per_guest numeric(10,2),
  cost_change_7d_pct numeric(6,2),
  computed_at   timestamptz NOT NULL DEFAULT now()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- Quotes, items, events, locks, payments
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TYPE quote_status AS ENUM ('draft','sent','modified','locked','accepted','expired','cancelled');

CREATE TABLE quotes (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  lead_id       uuid NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
  quote_number  text NOT NULL,
  version       integer NOT NULL DEFAULT 1,
  tier          text,
  package_template_id uuid REFERENCES package_templates(id),
  guest_count   integer NOT NULL CHECK (guest_count > 0 AND guest_count <= 500),
  diet          diet_pref NOT NULL,
  event_date    date NOT NULL,
  status        quote_status NOT NULL DEFAULT 'draft',
  food_cost_total numeric(12,2) NOT NULL,
  cost_total    numeric(12,2) NOT NULL,
  subtotal      numeric(12,2) NOT NULL,   -- before discounts
  discount_total numeric(12,2) NOT NULL DEFAULT 0,
  surcharge_total numeric(12,2) NOT NULL DEFAULT 0,
  tax_pct       numeric(5,2) NOT NULL DEFAULT 5.00,   -- GST on catering
  tax_total     numeric(12,2) NOT NULL,
  grand_total   numeric(12,2) NOT NULL,
  per_plate     numeric(10,2) NOT NULL,
  margin_pct    numeric(5,2) NOT NULL,
  market_snapshot jsonb,                  -- "today's Hyderabad market" comparison shown to client
  pricing_trace jsonb,                    -- full breakdown for audit
  portal_token  text,          -- shared by every version of a quote so the client's link never changes
  valid_until   timestamptz,
  created_by    text NOT NULL DEFAULT 'agent',
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, quote_number, version)
);
CREATE INDEX quotes_lead_idx ON quotes (lead_id, version DESC);
CREATE INDEX quotes_event_date_idx ON quotes (tenant_id, event_date) WHERE status IN ('locked','accepted');
CREATE INDEX quotes_portal_token_idx ON quotes (portal_token);

CREATE TABLE quote_items (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  quote_id      uuid NOT NULL REFERENCES quotes(id) ON DELETE CASCADE,
  menu_item_id  uuid NOT NULL REFERENCES menu_items(id),
  category_key  text NOT NULL,
  name          text NOT NULL,
  qty_guests    integer NOT NULL,
  unit_cost     numeric(10,2) NOT NULL,   -- cost per guest at quote time
  unit_price    numeric(10,2) NOT NULL,   -- price per guest at quote time
  line_total    numeric(12,2) NOT NULL,
  is_substitution boolean NOT NULL DEFAULT false,
  notes         text
);

CREATE TYPE quote_event_type AS ENUM ('created','item_added','item_removed','item_substituted','guests_changed','diet_changed','discount_applied','discount_removed','surcharge_applied','locked','sent','accepted','expired','change_requested');

CREATE TABLE quote_events (
  id            bigserial PRIMARY KEY,
  tenant_id     uuid NOT NULL,
  quote_id      uuid NOT NULL REFERENCES quotes(id) ON DELETE CASCADE,
  type          quote_event_type NOT NULL,
  actor_type    text NOT NULL,            -- agent|customer|human|system
  payload       jsonb NOT NULL DEFAULT '{}'::jsonb,
  per_plate_before numeric(10,2),
  per_plate_after  numeric(10,2),
  created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX quote_events_quote_idx ON quote_events (quote_id, created_at);

CREATE TABLE price_locks (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL,
  quote_id      uuid NOT NULL REFERENCES quotes(id) ON DELETE CASCADE,
  locked_per_plate numeric(10,2) NOT NULL,
  locked_total  numeric(12,2) NOT NULL,
  valid_until   timestamptz NOT NULL,
  certificate_hash text,                  -- sha256 for "Price Locked" certificate
  certificate_url text,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TYPE payment_status AS ENUM ('pending','paid','failed','refunded');

CREATE TABLE payments (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL,
  quote_id      uuid NOT NULL REFERENCES quotes(id),
  kind          text NOT NULL,            -- advance|balance|refund
  amount        numeric(12,2) NOT NULL,
  provider      text NOT NULL DEFAULT 'razorpay',
  provider_ref  text,
  payment_link  text,
  status        payment_status NOT NULL DEFAULT 'pending',
  paid_at       timestamptz,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE invoices (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL,
  quote_id      uuid NOT NULL REFERENCES quotes(id),
  invoice_number text NOT NULL,
  pdf_url       text,
  amount        numeric(12,2) NOT NULL,
  issued_at     timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, invoice_number)
);

-- ─────────────────────────────────────────────────────────────────────────────
-- Festivals & discount intelligence
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE festivals (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid REFERENCES tenants(id) ON DELETE CASCADE,   -- NULL = global calendar
  key           text NOT NULL,            -- ganesh_chaturthi_2026
  name          text NOT NULL,
  region        text NOT NULL DEFAULT 'Hyderabad',
  starts_on     date NOT NULL,
  ends_on       date NOT NULL,
  demand_multiplier numeric(4,2) NOT NULL DEFAULT 1.00,  -- >1 = peak
  tags          text[] NOT NULL DEFAULT '{}',   -- veg_heavy, sweets, wedding_season
  UNIQUE NULLS NOT DISTINCT (tenant_id, key)
);
CREATE INDEX festivals_window_idx ON festivals (starts_on, ends_on);

CREATE TYPE discount_kind AS ENUM ('percent','flat','free_item','per_plate_off');

CREATE TABLE discount_rules (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  key           text NOT NULL,
  name          text NOT NULL,
  kind          discount_kind NOT NULL,
  value         numeric(10,2) NOT NULL,   -- percent or ₹ or per-plate ₹
  free_item_slug text,
  festival_key  text,                     -- links to festivals.key (optional)
  booking_window_days_before_festival integer,  -- early-bird: book ≥ N days before
  guest_min     integer,
  guest_max     integer,
  diet          diet_pref,
  occasions     text[],
  tiers         text[],
  min_margin_pct numeric(5,2),            -- override tenant min margin (never below)
  stackable     boolean NOT NULL DEFAULT false,
  priority      integer NOT NULL DEFAULT 100,
  explanation_template text NOT NULL,     -- "Book {days} days before {festival} and save {pct}%"
  valid_from    date,
  valid_to      date,
  is_active     boolean NOT NULL DEFAULT true,
  UNIQUE (tenant_id, key)
);

CREATE TABLE discount_applications (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL,
  quote_id      uuid NOT NULL REFERENCES quotes(id) ON DELETE CASCADE,
  discount_rule_id uuid NOT NULL REFERENCES discount_rules(id),
  amount        numeric(12,2) NOT NULL,
  margin_after_pct numeric(5,2) NOT NULL,
  explanation   text NOT NULL,
  applied_at    timestamptz NOT NULL DEFAULT now()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- Notifications, WhatsApp, webhooks
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE whatsapp_templates (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL,
  key           text NOT NULL,            -- price_lock_confirmation
  meta_name     text NOT NULL,            -- approved template name at Meta
  language      text NOT NULL DEFAULT 'en',
  category      text NOT NULL DEFAULT 'UTILITY',
  params_schema jsonb NOT NULL DEFAULT '[]'::jsonb,
  UNIQUE (tenant_id, key)
);

CREATE TYPE notification_status AS ENUM ('queued','sent','delivered','read','failed','skipped');

CREATE TABLE notifications (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL,
  customer_id   uuid NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
  lead_id       uuid REFERENCES leads(id) ON DELETE SET NULL,
  template_key  text NOT NULL,
  channel       text NOT NULL DEFAULT 'whatsapp',
  params        jsonb NOT NULL DEFAULT '{}'::jsonb,
  scheduled_for timestamptz NOT NULL DEFAULT now(),
  status        notification_status NOT NULL DEFAULT 'queued',
  external_id   text,
  error         text,
  sent_at       timestamptz,
  created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX notifications_due_idx ON notifications (status, scheduled_for) WHERE status = 'queued';

CREATE TABLE webhook_events (
  id            bigserial PRIMARY KEY,
  provider      text NOT NULL,            -- whatsapp|razorpay
  external_id   text NOT NULL,
  payload       jsonb NOT NULL,
  processed_at  timestamptz,
  error         text,
  received_at   timestamptz NOT NULL DEFAULT now(),
  UNIQUE (provider, external_id)
);

-- ─────────────────────────────────────────────────────────────────────────────
-- Portal, sharing, OTP, venues, upsell, testimonials
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE portal_sessions (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL,
  customer_id   uuid NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
  quote_id      uuid REFERENCES quotes(id) ON DELETE CASCADE,
  token_hash    text NOT NULL UNIQUE,     -- magic link / OTP-issued session
  method        text NOT NULL,            -- magic_link|wa_otp
  expires_at    timestamptz NOT NULL,
  last_used_at  timestamptz,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE otp_codes (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL,
  wa_id         text NOT NULL,
  code_hash     text NOT NULL,
  attempts      integer NOT NULL DEFAULT 0,
  expires_at    timestamptz NOT NULL,
  consumed_at   timestamptz
);

CREATE TABLE share_links (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL,
  quote_id      uuid NOT NULL REFERENCES quotes(id) ON DELETE CASCADE,
  slug          text NOT NULL UNIQUE,
  created_by_customer_id uuid REFERENCES customers(id),
  views         integer NOT NULL DEFAULT 0,
  unique_viewers integer NOT NULL DEFAULT 0,
  last_viewed_at timestamptz,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE venues (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL,
  name          text NOT NULL,
  area          text NOT NULL,
  capacity      integer NOT NULL,
  preferred_rate numeric(12,2),
  contact       jsonb,
  tags          text[] NOT NULL DEFAULT '{}',
  is_partner    boolean NOT NULL DEFAULT true
);

CREATE TABLE upsell_rules (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL,
  guest_min     integer,
  guest_max     integer,
  occasion      text,
  diet          diet_pref,
  suggest_item_slug text NOT NULL,
  attach_rate   numeric(4,3) NOT NULL,    -- learned: share of similar bookings that added it
  message       text NOT NULL,
  is_active     boolean NOT NULL DEFAULT true
);

CREATE TABLE event_photos (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL,
  quote_id      uuid NOT NULL REFERENCES quotes(id) ON DELETE CASCADE,
  url           text NOT NULL,
  uploaded_by   text NOT NULL,
  consent_id    uuid REFERENCES consents(id),
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE testimonials (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL,
  quote_id      uuid NOT NULL REFERENCES quotes(id) ON DELETE CASCADE,
  customer_id   uuid NOT NULL REFERENCES customers(id),
  rating        integer CHECK (rating BETWEEN 1 AND 5),
  raw_feedback  text,
  generated_text text,
  approved      boolean NOT NULL DEFAULT false,
  consent_id    uuid REFERENCES consents(id),
  created_at    timestamptz NOT NULL DEFAULT now()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- RAG knowledge layer
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TYPE rag_source_type AS ENUM ('menu_catalog','package_template','policy','faq','festival_rules','discount_rules','historical_quote','venue_guide');

CREATE TABLE rag_sources (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  source_type   rag_source_type NOT NULL,
  source_ref    text NOT NULL,            -- file path, table row id, or URL
  title         text NOT NULL,
  content_hash  text NOT NULL,
  status        text NOT NULL DEFAULT 'active',   -- active|stale|deleted
  last_indexed_at timestamptz,
  UNIQUE (tenant_id, source_type, source_ref)
);

CREATE TABLE rag_documents (            -- parent chunks
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL,
  source_id     uuid NOT NULL REFERENCES rag_sources(id) ON DELETE CASCADE,
  breadcrumb    text NOT NULL,            -- "Menu > Starters > Non-Veg"
  content       text NOT NULL,
  token_count   integer NOT NULL,
  metadata      jsonb NOT NULL DEFAULT '{}'::jsonb,
  ordinal       integer NOT NULL,
  content_hash  text NOT NULL
);
CREATE INDEX rag_documents_source_idx ON rag_documents (source_id, ordinal);

CREATE TABLE rag_chunks (               -- child chunks
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL,
  document_id   uuid NOT NULL REFERENCES rag_documents(id) ON DELETE CASCADE,
  source_id     uuid NOT NULL REFERENCES rag_sources(id) ON DELETE CASCADE,
  ordinal       integer NOT NULL,
  content       text NOT NULL,            -- header + metadata line + body
  token_count   integer NOT NULL,
  content_hash  text NOT NULL,
  embedding     vector(3072),             -- text-embedding-3-large; voyage-3-large uses 1024 → see note
  embedding_model text NOT NULL,
  content_tsv   tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
  -- denormalised filters (also present in metadata JSONB)
  category      text,
  subcategory   text,
  diet          text,                     -- veg|non_veg|mixed|jain|any
  guest_min     integer,
  guest_max     integer,
  season_tags   text[] NOT NULL DEFAULT '{}',
  festival_keys text[] NOT NULL DEFAULT '{}',
  price_band    text,                     -- budget|mid|premium|any
  source_type   rag_source_type NOT NULL,
  status        text NOT NULL DEFAULT 'active',
  valid_from    timestamptz,
  valid_to      timestamptz,
  metadata      jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (document_id, ordinal)
);
-- pgvector HNSW supports at most 2000 dims for `vector`, so a 3072-d column is indexed
-- through a halfvec expression. halfvec needs pgvector >= 0.7, so the index is created only
-- when the type exists; without it retrieval still works, just as a sequential scan.
DO $$
BEGIN
  IF to_regtype('halfvec') IS NOT NULL THEN
    EXECUTE 'CREATE INDEX rag_chunks_embedding_hnsw ON rag_chunks '
            'USING hnsw ((embedding::halfvec(3072)) halfvec_cosine_ops) WITH (m = 16, ef_construction = 128)';
  ELSE
    RAISE NOTICE 'pgvector lacks halfvec (needs >= 0.7); skipping the HNSW index on rag_chunks.';
  END IF;
END $$;
CREATE INDEX rag_chunks_tsv_idx ON rag_chunks USING gin (content_tsv);
CREATE INDEX rag_chunks_filter_idx ON rag_chunks (tenant_id, status, source_type, diet, guest_min, guest_max);
CREATE INDEX rag_chunks_metadata_idx ON rag_chunks USING gin (metadata jsonb_path_ops);

CREATE TABLE rag_queries (              -- retrieval log for observability + eval
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL,
  lead_id       uuid,
  raw_query     text NOT NULL,
  rewritten_query text,
  intent        text,
  filters       jsonb NOT NULL DEFAULT '{}'::jsonb,
  dense_ids     uuid[] NOT NULL DEFAULT '{}',
  bm25_ids      uuid[] NOT NULL DEFAULT '{}',
  fused_ids     uuid[] NOT NULL DEFAULT '{}',
  reranked_ids  uuid[] NOT NULL DEFAULT '{}',
  cache_hit     boolean NOT NULL DEFAULT false,
  latency_ms    integer,
  trace_id      text,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE rag_eval_cases (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL,
  question      text NOT NULL,
  expected_source_refs text[] NOT NULL DEFAULT '{}',
  reference_answer text,
  filters       jsonb NOT NULL DEFAULT '{}'::jsonb,
  tags          text[] NOT NULL DEFAULT '{}'
);

CREATE TABLE rag_eval_runs (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL,
  ran_at        timestamptz NOT NULL DEFAULT now(),
  embedding_model text NOT NULL,
  llm_model     text NOT NULL,
  cases         integer NOT NULL,
  context_precision numeric(5,4),
  context_recall    numeric(5,4),
  faithfulness      numeric(5,4),
  answer_relevancy  numeric(5,4),
  details       jsonb NOT NULL DEFAULT '{}'::jsonb
);

-- ─────────────────────────────────────────────────────────────────────────────
-- Helpers
-- ─────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION touch_updated_at() RETURNS trigger AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END; $$ LANGUAGE plpgsql;

CREATE TRIGGER leads_touch BEFORE UPDATE ON leads FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER quotes_touch BEFORE UPDATE ON quotes FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER rag_chunks_touch BEFORE UPDATE ON rag_chunks FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- Kitchen load per date (guests already committed)
CREATE VIEW kitchen_load AS
SELECT tenant_id, event_date, SUM(guest_count) AS committed_guests, COUNT(*) AS bookings
FROM quotes WHERE status IN ('locked','accepted')
GROUP BY tenant_id, event_date;
