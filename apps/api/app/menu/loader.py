"""Puts the owner's menu into the database, and keeps it there.

Runs at startup (see main.lifespan) and from `python -m app.cli apply-menu`. Idempotent: dishes
upsert on slug, recipes are rewritten, templates upsert on key, and everything the demo
catalogue had that the real card does not is switched off rather than deleted, so old quotes
still resolve. A version number on the tenant records what was applied; a newer MENU_VERSION
re-applies, an equal one is a no-op.
"""
from __future__ import annotations

from decimal import Decimal as D
from pathlib import Path
from uuid import UUID

from app.core import db
from app.core.logging import get_logger
from app.menu import recipes as R
from app.menu import sri_sai_raja as M

log = get_logger("menu.loader")

CATEGORIES = (("welcome_drinks", "Welcome Drinks", 1), ("starters", "Starters", 2), ("main_veg", "Curries & Mains · Veg", 3),
              ("main_nonveg", "Mains · Non-Veg", 4), ("rice_breads", "Rice & Breads", 5), ("sides", "Chutneys & Sides", 6),
              ("live_counters", "Live Counters", 7), ("desserts", "Sweets & Desserts", 8), ("service", "Service", 9))

# Attach-rate rules aimed at dishes the owner actually cooks (the demo rules pointed at live counters).
UPSELLS = (
    (None, None, None, "veg", "paneer_butter_masala", 0.55, "Most veg functions add paneer butter masala — it is the dish guests ask for by name."),
    (80, None, None, None, "vanilla_ice_cream", 0.48, "Functions over 80 guests usually close with ice cream; kids remember it."),
    (None, None, "wedding", None, "meetha_paan", 0.52, "Weddings in Hyderabad end with meetha paan — almost every family adds it."),
    (None, None, None, "non_veg", "fish_fry", 0.41, "Non-veg tables with a fish fry get the best feedback for variety."),
    (100, None, None, "veg", "gulab_jamun", 0.44, "A second sweet is the most common addition on 100+ guest veg menus."),
    (None, None, "corporate", None, "fruit_salad", 0.38, "Corporate lunches usually add fruit salad as the light finish."),
    (150, None, None, None, "water", 0.66, "Most 150+ guest events add sealed water bottles — one per guest, billed per plate."),
)


async def current_version(tenant_id: UUID) -> int:
    v = await db.fetchval("SELECT (settings->>'menu_version')::int FROM tenants WHERE id = $1", tenant_id)
    return int(v or 0)


async def ensure(tenant_id: UUID) -> dict | None:
    """Apply the menu if the tenant is behind MENU_VERSION. Returns the apply summary, or None."""
    if await current_version(tenant_id) >= M.MENU_VERSION:
        return None
    return await apply(tenant_id)


async def apply(tenant_id: UUID, *, reindex: bool = True) -> dict:
    root = Path(__file__).resolve().parents[4]
    migration = (root / "db" / "migrations" / "001_real_menu.sql").read_text(encoding="utf-8")
    n_items = n_lines = n_pkgs = 0
    async with db.transaction() as conn:
        await conn.execute(migration)
        for key, name, order in CATEGORIES:
            await conn.execute("INSERT INTO menu_categories (tenant_id, key, name, sort_order) VALUES ($1,$2,$3,$4) "
                               "ON CONFLICT (tenant_id, key) DO UPDATE SET name = EXCLUDED.name, sort_order = EXCLUDED.sort_order", tenant_id, key, name, order)
        cats = {r["key"]: r["id"] for r in await conn.fetch("SELECT key, id FROM menu_categories WHERE tenant_id = $1", tenant_id)}

        # Ingredients the demo never priced: create with an opening wholesale + retail observation.
        for key, (name, unit, cat, opening, volatile) in R.EXTRA_INGREDIENTS.items():
            ing_id = await conn.fetchval(
                "INSERT INTO ingredients (tenant_id, key, name, unit, category, is_volatile, alert_threshold_pct) VALUES ($1,$2,$3,$4,$5,$6,15) "
                "ON CONFLICT (tenant_id, key) DO UPDATE SET name = EXCLUDED.name RETURNING id", tenant_id, key, name, unit, cat, volatile)
            has_price = await conn.fetchval("SELECT 1 FROM ingredient_prices WHERE ingredient_id = $1 LIMIT 1", ing_id)
            if not has_price:
                await conn.execute("INSERT INTO ingredient_prices (tenant_id, ingredient_id, source, market, price_per_unit, observed_at) VALUES "
                                   "($1,$2,'opening_estimate','wholesale',$3,now()), ($1,$2,'opening_estimate','retail',$4,now())",
                                   tenant_id, ing_id, D(str(opening)), D(str(round(opening * 1.25, 2))))
        ings = {r["key"]: r["id"] for r in await conn.fetch("SELECT key, id FROM ingredients WHERE tenant_id = $1", tenant_id)}

        real = {d.slug for d in M.DISHES}
        await conn.execute("UPDATE menu_items SET is_active = false, updated_at = now() WHERE tenant_id = $1 AND slug <> ALL($2::text[]) AND is_active",
                           tenant_id, list(real))
        for d in M.DISHES:
            r = R.RECIPES[d.slug]
            item_id = await conn.fetchval(
                """INSERT INTO menu_items (tenant_id, category_id, slug, name, name_te, description, diet, is_jain_ok, is_live_counter, contains,
                                           labour_cost_per_guest, overhead_pct, fixed_setup_cost, tags, popularity, min_guests, is_active)
                   VALUES ($1,$2,$3,$4,$5,$6,$7::diet_pref,$8,false,$9,$10,$11,$12,$13,$14,1,true)
                   ON CONFLICT (tenant_id, slug) DO UPDATE SET category_id = EXCLUDED.category_id, name = EXCLUDED.name, name_te = EXCLUDED.name_te,
                     description = EXCLUDED.description, diet = EXCLUDED.diet, is_jain_ok = EXCLUDED.is_jain_ok, is_live_counter = false,
                     contains = EXCLUDED.contains, labour_cost_per_guest = EXCLUDED.labour_cost_per_guest, overhead_pct = EXCLUDED.overhead_pct,
                     fixed_setup_cost = EXCLUDED.fixed_setup_cost, tags = EXCLUDED.tags, popularity = EXCLUDED.popularity, is_active = true, updated_at = now()
                   RETURNING id""",
                tenant_id, cats[d.category], d.slug, d.name, d.name_te or None, d.description, d.diet, R.jain_ok(r), R.contains_for(r),
                r.labour, M.OVERHEAD_PCT, r.setup, list(d.tags), d.popularity)
            await conn.execute("DELETE FROM menu_item_ingredients WHERE menu_item_id = $1", item_id)
            for key, qty in r.lines.items():
                await conn.execute("INSERT INTO menu_item_ingredients (menu_item_id, ingredient_id, qty_per_guest, waste_pct) VALUES ($1,$2,$3,5)", item_id, ings[key], qty)
                n_lines += 1
            n_items += 1
        items = {r["slug"]: r["id"] for r in await conn.fetch("SELECT slug, id FROM menu_items WHERE tenant_id = $1", tenant_id)}

        keys = [p.key for p in M.PACKAGES]
        await conn.execute("UPDATE package_templates SET is_active = false WHERE tenant_id = $1 AND key <> ALL($2::text[])", tenant_id, keys)
        for p in M.PACKAGES:
            pt_id = await conn.fetchval(
                """INSERT INTO package_templates (tenant_id, key, tier, name, diet, occasions, guest_min, guest_max, description, is_active,
                                                  tagline, list_price, includes, margin_adj, sort_order)
                   VALUES ($1,$2,$3,$4,$5::diet_pref,$6,25,500,$7,true,$8,$9,$10,$11,$12)
                   ON CONFLICT (tenant_id, key) DO UPDATE SET tier = EXCLUDED.tier, name = EXCLUDED.name, diet = EXCLUDED.diet, occasions = EXCLUDED.occasions,
                     description = EXCLUDED.description, is_active = true, tagline = EXCLUDED.tagline, list_price = EXCLUDED.list_price,
                     includes = EXCLUDED.includes, margin_adj = EXCLUDED.margin_adj, sort_order = EXCLUDED.sort_order
                   RETURNING id""",
                tenant_id, p.key, p.tier, p.name, p.diet, list(p.occasions), p.description, p.tagline, p.list_price, list(p.includes), p.margin_adj, p.sort_order)
            await conn.execute("DELETE FROM package_template_items WHERE package_template_id = $1", pt_id)
            pos = 0
            for slug in p.fixed:
                await conn.execute("INSERT INTO package_template_items (package_template_id, menu_item_id, slot, is_default, position) VALUES ($1,$2,NULL,true,$3)", pt_id, items[slug], pos)
                pos += 1
            for slot in p.slots:
                for i, slug in enumerate(slot.options):
                    await conn.execute("INSERT INTO package_template_items (package_template_id, menu_item_id, slot, is_default, position) VALUES ($1,$2,$3,$4,$5)",
                                       pt_id, items[slug], slot.key, i == 0, pos)
                    pos += 1
            n_pkgs += 1

        # Rules that pointed at demo dishes now point at the owner's.
        await conn.execute("UPDATE discount_rules SET free_item_slug = 'meetha_paan' WHERE tenant_id = $1 AND free_item_slug IS NOT NULL AND free_item_slug <> ALL($2::text[])", tenant_id, list(real))
        await conn.execute("DELETE FROM upsell_rules WHERE tenant_id = $1", tenant_id)
        for gmin, gmax, occ, diet, slug, rate, msg in UPSELLS:
            await conn.execute("INSERT INTO upsell_rules (tenant_id, guest_min, guest_max, occasion, diet, suggest_item_slug, attach_rate, message) VALUES ($1,$2,$3,$4,$5::diet_pref,$6,$7,$8)",
                               tenant_id, gmin, gmax, occ, diet, slug, rate, msg)
        # The margin policy the cards were calibrated on (docs/10-menu.md).
        await conn.execute("UPDATE tenants SET target_margin_pct = 38, min_margin_pct = 30, settings = settings || $2::jsonb WHERE id = $1",
                           tenant_id, {"menu_version": M.MENU_VERSION, "menu_source": "sri_sai_raja"})

    from app.pricing.repository import refresh_item_costs

    costed = await refresh_item_costs(tenant_id)
    summary = {"items": n_items, "recipe_lines": n_lines, "packages": n_pkgs, "costed": costed, "version": M.MENU_VERSION}
    if reindex:
        try:
            from app.rag.indexing import index_tenant

            summary["indexed"] = (await index_tenant(tenant_id, source_types={"menu_catalog", "package_template"}))["chunks_embedded"]
        except Exception as e:  # noqa: BLE001 — search is a convenience; the menu must load even when embeddings are down
            log.warning("menu_reindex_failed", error=str(e))
    try:
        from app.agent import playbook

        playbook.invalidate()
    except Exception:  # noqa: BLE001
        pass
    log.info("menu_applied", **summary)
    return summary
