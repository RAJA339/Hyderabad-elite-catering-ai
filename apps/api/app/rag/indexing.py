"""Offline / scheduled indexing pipeline with incremental updates.

Sources → markdown renderings → parent/child chunks → embeddings → rag_documents / rag_chunks.
Unchanged chunk hashes are skipped; removed chunks are deleted; the source's content_hash and
last_indexed_at are updated. Volatile numbers are deliberately NOT rendered into text.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from app.core import db
from app.core.logging import get_logger
from app.rag.chunking import ChildChunk, ParentChunk, chunk_document
from app.rag.embeddings import get_embedder
from app.rag.store import _vec

log = get_logger("rag.indexing")
KNOWLEDGE_DIR = Path(__file__).resolve().parents[3] / "knowledge"


@dataclass
class SourceDoc:
    source_type: str
    source_ref: str
    title: str
    text: str
    metadata: dict


# ── Renderers: DB rows → markdown with slugs in text and metadata for filtering ───────────
async def render_menu_catalog(tenant_id: UUID) -> list[SourceDoc]:
    cats = await db.fetch("SELECT id, key, name FROM menu_categories WHERE tenant_id = $1 ORDER BY sort_order", tenant_id)
    docs: list[SourceDoc] = []
    for c in cats:
        items = await db.fetch(
            """SELECT slug, name, name_te, description, diet::text AS diet, is_jain_ok, is_live_counter, contains, min_guests, tags, popularity
               FROM menu_items WHERE tenant_id = $1 AND category_id = $2 AND is_active ORDER BY popularity DESC""",
            tenant_id, c["id"],
        )
        if not items:
            continue
        lines = [f"# Menu > {c['name']}", ""]
        for diet_label, diet_key in (("Veg", "veg"), ("Non-Veg", "non_veg")):
            group = [i for i in items if i["diet"] == diet_key]
            if not group:
                continue
            lines.append(f"## {diet_label}")
            for i in group:
                flags = []
                if i["is_jain_ok"]:
                    flags.append("Jain-friendly")
                if i["is_live_counter"]:
                    flags.append("live counter")
                if i["contains"]:
                    flags.append("contains " + ", ".join(i["contains"]))
                te = f" ({i['name_te']})" if i["name_te"] else ""
                lines.append(f"- **{i['name']}**{te} (slug: {i['slug']}) — {i['description'] or ''} "
                             f"{'[' + '; '.join(flags) + ']' if flags else ''} Min guests: {i['min_guests']}. Tags: {', '.join(i['tags'] or [])}.")
            lines.append("")
        docs.append(SourceDoc("menu_catalog", f"menu_category:{c['key']}", f"Menu · {c['name']}", "\n".join(lines),
                              {"category": c["key"], "diet": "any", "item_slugs": [i["slug"] for i in items], "price_band": "any"}))
    return docs


async def render_package_templates(tenant_id: UUID) -> list[SourceDoc]:
    rows = await db.fetch(
        """SELECT pt.key, pt.tier, pt.name, pt.diet::text AS diet, pt.occasions, pt.guest_min, pt.guest_max, pt.description,
                  array_agg(mi.name || ' (slug: ' || mi.slug || ')' ORDER BY c.sort_order, mi.name) AS items,
                  array_agg(DISTINCT c.name) AS categories, array_agg(mi.slug) AS slugs
           FROM package_templates pt
           JOIN package_template_items pti ON pti.package_template_id = pt.id
           JOIN menu_items mi ON mi.id = pti.menu_item_id JOIN menu_categories c ON c.id = mi.category_id
           WHERE pt.tenant_id = $1 AND pt.is_active GROUP BY pt.id""",
        tenant_id,
    )
    docs = []
    for r in rows:
        text = (f"# Package > {r['name']} ({r['tier'].title()})\n\n{r['description'] or ''}\n\n"
                f"Diet: {r['diet']}. Suitable for {r['guest_min']}–{r['guest_max']} guests. "
                f"Occasions: {', '.join(r['occasions'] or ['any'])}.\n\n## Includes\n" + "\n".join(f"- {i}" for i in r["items"]))
        band = {"classic": "budget", "signature": "mid", "royal": "premium"}[r["tier"]]
        docs.append(SourceDoc("package_template", f"package:{r['key']}", r["name"], text,
                              {"category": "package", "subcategory": r["tier"], "diet": r["diet"], "guest_min": r["guest_min"],
                               "guest_max": r["guest_max"], "price_band": band, "item_slugs": list(r["slugs"])}))
    return docs


async def render_festival_rules(tenant_id: UUID) -> list[SourceDoc]:
    fests = await db.fetch("SELECT key, name, starts_on, ends_on, tags, demand_multiplier FROM festivals WHERE tenant_id IS NULL OR tenant_id = $1 ORDER BY starts_on", tenant_id)
    rules = await db.fetch("SELECT * FROM discount_rules WHERE tenant_id = $1 AND is_active ORDER BY priority", tenant_id)
    ftext = ["# Festival Calendar (Hyderabad)", ""]
    for f in fests:
        ftext.append(f"- **{f['name']}** (key: {f['key']}): {f['starts_on']} to {f['ends_on']}. Tags: {', '.join(f['tags'] or [])}. "
                     f"Demand: {'peak' if float(f['demand_multiplier']) >= 1.3 else 'high' if float(f['demand_multiplier']) > 1.1 else 'normal'}.")
    rtext = ["# Discount Rules", "", "All offers are applied automatically only when the minimum profit margin is preserved.", ""]
    for r in rules:
        cond = []
        if r["festival_key"]:
            cond.append(f"festival {r['festival_key']}")
        if r["booking_window_days_before_festival"]:
            cond.append(f"book at least {r['booking_window_days_before_festival']} days before")
        if r["guest_min"]:
            cond.append(f"minimum {r['guest_min']} guests")
        if r["diet"]:
            cond.append(f"{r['diet']} menus")
        rtext.append(f"## {r['name']} (rule: {r['key']})\n{r['kind']} {r['value']}{'%' if r['kind']=='percent' else ''}. "
                     f"Conditions: {'; '.join(cond) or 'none'}. Stackable: {'yes' if r['stackable'] else 'no'}. "
                     f"Explanation: {r['explanation_template']}\n")
    return [
        SourceDoc("festival_rules", "festivals:calendar", "Festival Calendar", "\n".join(ftext),
                  {"category": "festival", "festival_keys": [f["key"] for f in fests], "diet": "any"}),
        SourceDoc("discount_rules", "discounts:rules", "Discount Rules", "\n".join(rtext),
                  {"category": "discount", "festival_keys": [r["festival_key"] for r in rules if r["festival_key"]], "diet": "any"}),
    ]


async def render_historical_quotes(tenant_id: UUID, limit: int = 200) -> list[SourceDoc]:
    rows = await db.fetch(
        """SELECT q.id, q.tier, q.guest_count, q.diet::text AS diet, q.event_date, l.occasion, l.venue_area,
                  array_agg(qi.name || ' (slug: ' || mi.slug || ')') AS items, array_agg(mi.slug) AS slugs
           FROM quotes q JOIN leads l ON l.id = q.lead_id
           JOIN quote_items qi ON qi.quote_id = q.id JOIN menu_items mi ON mi.id = qi.menu_item_id
           WHERE q.tenant_id = $1 AND q.status = 'accepted' GROUP BY q.id, l.occasion, l.venue_area
           ORDER BY q.created_at DESC LIMIT $2""",
        tenant_id, limit,
    )
    docs = []
    for r in rows:
        text = (f"# Winning combination > {r['occasion'] or 'event'} for {r['guest_count']} guests ({r['diet']})\n\n"
                f"Booked {r['tier']} tier in {r['venue_area'] or 'Hyderabad'}, event month {r['event_date'].strftime('%B')}.\n\n"
                "## Menu\n" + "\n".join(f"- {i}" for i in r["items"]))
        docs.append(SourceDoc("historical_quote", f"quote:{r['id']}", f"Past booking {r['occasion']}", text,
                              {"category": "historical", "diet": r["diet"], "guest_min": max(int(r["guest_count"] * 0.6), 10),
                               "guest_max": min(int(r["guest_count"] * 1.5), 500), "item_slugs": list(r["slugs"]),
                               "season_tags": [r["event_date"].strftime("%B").lower()]}))
    return docs


def render_knowledge_files() -> list[SourceDoc]:
    docs = []
    if not KNOWLEDGE_DIR.exists():
        return docs
    for p in sorted(KNOWLEDGE_DIR.glob("*.md")):
        st = "faq" if "faq" in p.name else "venue_guide" if "venue" in p.name else "policy"
        docs.append(SourceDoc(st, f"file:{p.name}", p.stem.replace("-", " ").title(), p.read_text(encoding="utf-8"),
                              {"category": st, "diet": "any", "price_band": "any"}))
    return docs


# ── Indexer ──────────────────────────────────────────────────────────────────────────────
async def index_tenant(tenant_id: UUID, *, source_types: set[str] | None = None) -> dict:
    embedder = get_embedder()
    docs: list[SourceDoc] = []
    docs += await render_menu_catalog(tenant_id)
    docs += await render_package_templates(tenant_id)
    docs += await render_festival_rules(tenant_id)
    docs += await render_historical_quotes(tenant_id)
    docs += render_knowledge_files()
    if source_types:
        docs = [d for d in docs if d.source_type in source_types]

    stats = {"sources": 0, "chunks_embedded": 0, "chunks_skipped": 0, "chunks_deleted": 0}
    seen_refs: set[tuple[str, str]] = set()
    for doc in docs:
        seen_refs.add((doc.source_type, doc.source_ref))
        chash = hashlib.sha256(doc.text.encode()).hexdigest()
        async with db.transaction() as conn:
            src = await conn.fetchrow(
                """INSERT INTO rag_sources (tenant_id, source_type, source_ref, title, content_hash, status)
                   VALUES ($1,$2::rag_source_type,$3,$4,$5,'active')
                   ON CONFLICT (tenant_id, source_type, source_ref) DO UPDATE SET title=EXCLUDED.title, status='active'
                   RETURNING id, content_hash, last_indexed_at""",
                tenant_id, doc.source_type, doc.source_ref, doc.title, chash,
            )
            if src["content_hash"] == chash and src["last_indexed_at"] is not None:
                stats["chunks_skipped"] += await conn.fetchval("SELECT count(*) FROM rag_chunks WHERE source_id = $1", src["id"])
                continue
            parents, children = chunk_document(doc.text, doc.title, {**doc.metadata, "source_type": doc.source_type})
            await _write_chunks(conn, tenant_id, src["id"], doc, parents, children, embedder, stats)
            await conn.execute("UPDATE rag_sources SET content_hash=$2, last_indexed_at=now() WHERE id=$1", src["id"], chash)
        stats["sources"] += 1

    # Retire sources that no longer exist in the renderers (e.g. deleted menu category)
    if not source_types:
        rows = await db.fetch("SELECT id, source_type::text AS st, source_ref FROM rag_sources WHERE tenant_id = $1 AND status='active'", tenant_id)
        for r in rows:
            if (r["st"], r["source_ref"]) not in seen_refs:
                await db.execute("UPDATE rag_sources SET status='deleted' WHERE id=$1", r["id"])
                await db.execute("UPDATE rag_chunks SET status='deleted' WHERE source_id=$1", r["id"])
    log.info("index_done", **stats)
    return stats


async def _write_chunks(conn, tenant_id, source_id, doc: SourceDoc, parents: list[ParentChunk], children: list[ChildChunk], embedder, stats):
    existing = {r["content_hash"]: r["id"] for r in await conn.fetch("SELECT id, content_hash FROM rag_chunks WHERE source_id = $1", source_id)}
    await conn.execute("DELETE FROM rag_documents WHERE source_id = $1", source_id)  # cascades chunks
    stats["chunks_deleted"] += len(existing)
    parent_ids: dict[int, UUID] = {}
    for p in parents:
        pid = await conn.fetchval(
            "INSERT INTO rag_documents (tenant_id, source_id, breadcrumb, content, token_count, metadata, ordinal, content_hash) VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING id",
            tenant_id, source_id, p.breadcrumb, p.content, p.token_count, p.metadata, p.ordinal, p.content_hash,
        )
        parent_ids[p.ordinal] = pid
    texts = [c.content for c in children]
    vectors = await embedder.embed(texts) if texts else []
    for c, v in zip(children, vectors, strict=False):
        m = c.metadata
        guest_min, guest_max = m.get("guest_min"), m.get("guest_max")
        await conn.execute(
            """INSERT INTO rag_chunks (tenant_id, document_id, source_id, ordinal, content, token_count, content_hash, embedding, embedding_model,
                 category, subcategory, diet, guest_min, guest_max, season_tags, festival_keys, price_band, source_type, metadata)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8::vector,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18::rag_source_type,$19)""",
            tenant_id, parent_ids[c.parent_ordinal], source_id, c.ordinal, c.content, c.token_count, c.content_hash, _vec(v), embedder.model,
            m.get("category"), m.get("subcategory"), m.get("diet", "any"), guest_min, guest_max,
            list(m.get("season_tags", [])), [k for k in m.get("festival_keys", []) if k], m.get("price_band", "any"), doc.source_type, m,
        )
        stats["chunks_embedded"] += 1
