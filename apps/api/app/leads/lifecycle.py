"""Lifecycle automation via WhatsApp utility templates.

Templates (approved at Meta under these names; see db/seed for params):
  price_lock_confirmation · menu_change_update · festival_offer_alert · payment_reminder
  post_event_thankyou · reengagement_festival · quote_ready
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from app.core import db
from app.core.logging import get_logger
from app.festivals.calendar import FESTIVALS

log = get_logger("lifecycle")


async def enqueue(tenant_id: UUID, customer_id: UUID, template_key: str, params: dict, *, lead_id: UUID | None = None, when: datetime | None = None) -> UUID:
    return await db.fetchval(
        """INSERT INTO notifications (tenant_id, customer_id, lead_id, template_key, params, scheduled_for)
           VALUES ($1,$2,$3,$4,$5,$6) RETURNING id""",
        tenant_id, customer_id, lead_id, template_key, params, when or datetime.now(UTC),
    )


async def on_quote_saved(tenant_id: UUID, lead: dict, quote: dict, *, changed: bool, change_summary: str | None, portal_url: str) -> None:
    key = "menu_change_update" if changed else "quote_ready"
    params = {"quote_number": quote["quote_number"], "per_plate": str(quote["per_plate"]), "total": str(quote["grand_total"]),
              "portal_url": portal_url, "change_summary": change_summary or ""}
    await enqueue(tenant_id, lead["customer_id"], key, params, lead_id=lead["id"])


async def on_price_locked(tenant_id: UUID, lead: dict, quote: dict, lock: dict, portal_url: str) -> None:
    await enqueue(tenant_id, lead["customer_id"], "price_lock_confirmation",
                  {"quote_number": quote["quote_number"], "per_plate": str(lock["locked_per_plate"]), "valid_until": lock["valid_until"].date().isoformat(),
                   "certificate": lock["certificate_hash"][:12].upper(), "portal_url": portal_url}, lead_id=lead["id"])


async def on_advance_requested(tenant_id: UUID, lead: dict, quote: dict, payment: dict) -> None:
    now = datetime.now(UTC)
    for offset_h in (24, 72):
        await enqueue(tenant_id, lead["customer_id"], "payment_reminder",
                      {"quote_number": quote["quote_number"], "amount": str(payment["amount"]), "link": payment.get("payment_link") or ""},
                      lead_id=lead["id"], when=now + timedelta(hours=offset_h))


async def on_event_completed(tenant_id: UUID, lead: dict, quote: dict) -> None:
    ev = quote["event_date"]
    when = datetime.combine(ev + timedelta(days=1), datetime.min.time(), tzinfo=UTC).replace(hour=5)  # 10:30 IST
    upcoming = [f for f in FESTIVALS if f.starts_on > ev][:1]
    await enqueue(tenant_id, lead["customer_id"], "post_event_thankyou",
                  {"occasion": lead.get("occasion") or "event", "review_url": "", "next_offer": f"{upcoming[0].name} early-bird" if upcoming else ""},
                  lead_id=lead["id"], when=when)


async def schedule_festival_reengagement(tenant_id: UUID, days_before: int = 21) -> int:
    """Nightly: for each festival starting in `days_before` days, ping past clients with consent."""
    target = date.today() + timedelta(days=days_before)
    fests = [f for f in FESTIVALS if f.starts_on == target]
    if not fests:
        return 0
    rows = await db.fetch(
        """SELECT c.id FROM customers c JOIN consents k ON k.customer_id = c.id AND k.purpose = 'marketing' AND k.granted AND k.revoked_at IS NULL
           WHERE c.tenant_id = $1 AND c.bookings_count > 0 AND c.deleted_at IS NULL""", tenant_id)
    n = 0
    for f in fests:
        for r in rows:
            already = await db.fetchval("SELECT 1 FROM notifications WHERE customer_id = $1 AND template_key = 'reengagement_festival' AND params->>'festival' = $2", r["id"], f.key)
            if already:
                continue
            await enqueue(tenant_id, r["id"], "reengagement_festival", {"festival": f.key, "festival_name": f.name, "date": f.starts_on.isoformat()})
            n += 1
    return n


async def dispatch_due(limit: int = 100) -> int:
    """Send queued notifications whose time has come. Consent is re-checked at send time."""
    from app.whatsapp.client import WhatsAppClient

    rows = await db.fetch(
        """SELECT n.*, c.wa_id, c.deleted_at,
                  (SELECT granted FROM consents WHERE customer_id = n.customer_id AND purpose = 'communication' AND revoked_at IS NULL) AS consent
           FROM notifications n JOIN customers c ON c.id = n.customer_id
           WHERE n.status = 'queued' AND n.scheduled_for <= now() ORDER BY n.scheduled_for LIMIT $1""", limit)
    client = WhatsAppClient()
    sent = 0
    for r in rows:
        if r["deleted_at"] or not r["consent"]:
            await db.execute("UPDATE notifications SET status='skipped', error='no consent' WHERE id=$1", r["id"])
            continue
        tpl = await db.fetchrow("SELECT meta_name, language, params_schema FROM whatsapp_templates WHERE tenant_id=$1 AND key=$2", r["tenant_id"], r["template_key"])
        try:
            if tpl:
                ordered = [str(r["params"].get(p, "")) for p in tpl["params_schema"]]
                res = await client.send_template(r["wa_id"], tpl["meta_name"], tpl["language"], ordered)
            else:  # fall back to plain text inside a 24h window (dev)
                res = await client.send_text(r["wa_id"], _render_plain(r["template_key"], r["params"]))
            await db.execute("UPDATE notifications SET status='sent', sent_at=now(), external_id=$2 WHERE id=$1", r["id"], (res or {}).get("id"))
            sent += 1
        except Exception as e:  # noqa: BLE001
            await db.execute("UPDATE notifications SET status='failed', error=$2 WHERE id=$1", r["id"], str(e)[:500])
    return sent


def _render_plain(key: str, p: dict) -> str:
    return {
        "quote_ready": f"Your quote {p.get('quote_number')} is ready: ₹{p.get('per_plate')}/plate, total ₹{p.get('total')}. View & edit: {p.get('portal_url')}",
        "menu_change_update": f"Menu updated on {p.get('quote_number')}: {p.get('change_summary')}. New price ₹{p.get('per_plate')}/plate (₹{p.get('total')}). {p.get('portal_url')}",
        "price_lock_confirmation": f"Price locked: ₹{p.get('per_plate')}/plate on {p.get('quote_number')} till {p.get('valid_until')}. Certificate {p.get('certificate')}. {p.get('portal_url')}",
        "payment_reminder": f"Gentle reminder: advance ₹{p.get('amount')} for {p.get('quote_number')} is pending. Pay here: {p.get('link')}",
        "post_event_thankyou": f"Thank you for choosing Hyderabad Elite Catering for your {p.get('occasion')}! We'd love a quick review. Next time: {p.get('next_offer')}.",
        "reengagement_festival": f"{p.get('festival_name')} is on {p.get('date')} — as a past client you get first access to our festival menus. Reply to plan.",
        "festival_offer_alert": f"New offer for your quote {p.get('quote_number')}: {p.get('offer')}. Valid till {p.get('valid_until')}.",
    }.get(key, str(p))
