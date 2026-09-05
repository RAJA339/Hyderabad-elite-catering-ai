-- Applied idempotently at startup (app.menu.loader) and by `python -m app.cli apply-menu`.
-- A package is a fixed spread plus "choose one" slots; the card's printed price rides along.
ALTER TABLE package_templates ADD COLUMN IF NOT EXISTS tagline text;
ALTER TABLE package_templates ADD COLUMN IF NOT EXISTS list_price numeric(10,2);
ALTER TABLE package_templates ADD COLUMN IF NOT EXISTS includes text[] NOT NULL DEFAULT '{}';
ALTER TABLE package_templates ADD COLUMN IF NOT EXISTS margin_adj numeric(5,2) NOT NULL DEFAULT 0;
ALTER TABLE package_templates ADD COLUMN IF NOT EXISTS sort_order integer NOT NULL DEFAULT 0;
ALTER TABLE package_template_items ADD COLUMN IF NOT EXISTS slot text;
ALTER TABLE package_template_items ADD COLUMN IF NOT EXISTS is_default boolean NOT NULL DEFAULT true;
ALTER TABLE package_template_items ADD COLUMN IF NOT EXISTS position integer NOT NULL DEFAULT 0;
