"""Unauthenticated marketing surface: the live market ticker shown on the landing page.

Wholesale rates are the public claim the whole product rests on, so they are served without
auth. Costs, margins and prices stay behind the staff endpoints."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from app.agent.handoff import admin_url_for, build_enquiry_alert
from app.agent.outreach import compose_opening, greet_new_enquiry
from app.core import db
from app.core.cache import rate_limit
from app.core.config import get_settings
from app.leads import repository as leads
from app.notify.channels import alert_owner, send_email
from app.routers.deps import default_tenant

router = APIRouter(prefix="/public", tags=["public"])

TICKER_KEYS = ("chicken", "mutton", "paneer", "onion", "tomato", "rice", "oil", "milk", "potato", "fish")


@router.get("/market-ticker")
async def market_ticker(tenant_id=Depends(default_tenant)):
    rows = await db.fetch(
        """WITH cur AS (
             SELECT ingredient_id, key, name, unit, price_per_unit, observed_at
             FROM ingredient_current_prices WHERE tenant_id = $1 AND market = 'wholesale'
           ), prev AS (
             SELECT DISTINCT ON (ingredient_id) ingredient_id, price_per_unit
             FROM ingredient_prices
             WHERE tenant_id = $1 AND market = 'wholesale' AND observed_at <= now() - interval '7 days'
             ORDER BY ingredient_id, observed_at DESC
           )
           SELECT cur.key, cur.name, cur.unit, cur.price_per_unit AS price, cur.observed_at,
                  COALESCE(round((cur.price_per_unit - prev.price_per_unit) / NULLIF(prev.price_per_unit, 0) * 100, 1), 0) AS change_7d
           FROM cur LEFT JOIN prev USING (ingredient_id)
           WHERE cur.key = ANY($2::text[])
           ORDER BY array_position($2::text[], cur.key)""",
        tenant_id, list(TICKER_KEYS),
    )
    return {
        "as_of": rows[0]["observed_at"].isoformat() if rows else None,
        "source": "Bowenpally wholesale",
        "prices": [
            {"key": r["key"], "name": r["name"], "unit": r["unit"], "price": str(r["price"]), "change_7d": float(r["change_7d"])}
            for r in rows
        ],
    }


class EnquiryIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    phone: str = Field(min_length=10, max_length=20)
    email: str | None = None
    occasion: str | None = None
    event_date: str | None = None
    guests: int | None = Field(default=None, ge=1, le=5000)
    diet: str | None = None
    message: str | None = Field(default=None, max_length=1000)


def normalise_phone(raw: str) -> str | None:
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) == 10:
        digits = "91" + digits
    return digits if 11 <= len(digits) <= 15 else None


@router.post("/enquiry")
async def enquiry(body: EnquiryIn, background: BackgroundTasks, tenant_id=Depends(default_tenant)):
    """The "call me" form. Lands in the same customer and lead Anvi uses — keyed on the phone
    number, so a later WhatsApp message is the same person — and alerts the owner at once."""
    phone = normalise_phone(body.phone)
    if not phone:
        raise HTTPException(422, "Please enter a phone number with the country code, e.g. +91 98765 43210.")
    if not await rate_limit(f"rl:enquiry:{phone}", 3, 3600):
        raise HTTPException(429, "We already have your request — the owner will call shortly.")
    s = get_settings()
    customer = await leads.get_or_create_customer(tenant_id, phone, body.name.strip())
    email = (body.email or "").strip().lower() or None
    if email and "@" in email:
        await db.execute("UPDATE customers SET email = $2 WHERE id = $1", customer["id"], email)
    # Sending the form is the consent: the copy beside the button says so.
    await leads.record_consent(tenant_id, customer["id"], "communication", True, {"via": "enquiry_form"})
    await leads.record_consent(tenant_id, customer["id"], "data_storage", True, {"via": "enquiry_form"})
    lead = await leads.get_or_create_open_lead(tenant_id, customer["id"], source="web_chat")
    fields: dict = {}
    if body.occasion:
        fields["occasion"] = body.occasion.strip().lower().replace(" ", "_")
    if body.event_date:
        try:
            fields["event_date"] = date.fromisoformat(body.event_date)
        except ValueError:
            pass
    if body.guests and body.guests <= s.max_guests:
        fields["guest_count"] = body.guests
    if body.diet in ("veg", "non_veg", "mixed", "jain"):
        fields["diet"] = body.diet
    if fields:
        lead = await leads.update_lead_fields(lead["id"], fields)
    note = f"(website enquiry form) {body.message.strip()}" if body.message and body.message.strip() else "(website enquiry form) Requested a callback."
    if body.guests and body.guests > s.max_guests:
        note += f" Requested {body.guests} guests — above our {s.max_guests} limit."
    await leads.create_escalation(tenant_id, lead["id"], "callback requested", note, "normal")
    subject, text = build_enquiry_alert(name=body.name.strip(), phone="+" + phone, email=email, lead=lead, message=body.message, admin_url=admin_url_for(lead))
    await alert_owner(subject, text)
    # Anvi answers now rather than after the callback: the form is handed to the same agent
    # pipeline as a chat message, and her priced reply goes out on whatever channel we have.
    opening = compose_opening(name=body.name, occasion=body.occasion, event_date=body.event_date,
                              guests=body.guests, diet=body.diet, message=body.message)
    background.add_task(greet_new_enquiry, tenant_id=tenant_id, wa_id=phone, name=body.name.strip(), email=email, opening=opening)

    if email:
        await send_email(email, "We have your catering enquiry",
                         f"Namaste {body.name.split()[0]},\n\nThank you — the Hyderabad Elite Catering team has your details and will call you on +{phone} within two hours (9am–9pm IST).\n\n"
                         f"Anvi is putting menu options together for you right now — they will land in your inbox in a minute. "
                         f"You can also talk to her here: {s.public_web_url}/#chat\n\nWarmly,\nAnvi")
    return {"ok": True, "lead_id": str(lead["id"])}


# ── The menu builder ─────────────────────────────────────────────────────────
# The owner's packages, priced live, with every "choose one" line on the card as a real
# choice. A visitor sees prices only; costs and margins never leave the server.

class PriceIn(BaseModel):
    package_key: str = Field(min_length=3, max_length=60)
    guest_count: int = Field(ge=1, le=500)
    choices: dict[str, str] = Field(default_factory=dict)
    add: list[str] = Field(default_factory=list, max_length=20)
    remove: list[str] = Field(default_factory=list, max_length=30)
    diet: str | None = None


async def _menu_context(tenant_id):
    from app.pricing.repository import load_catalog, load_policy, load_prices, load_templates

    return await load_templates(tenant_id), await load_catalog(tenant_id), await load_prices(tenant_id), await load_policy(tenant_id)


@router.get("/menu")
async def menu(tenant_id=Depends(default_tenant)):
    from app.menu.builder import catalog_view

    templates, catalog, prices, policy = await _menu_context(tenant_id)
    rows = await db.fetch("SELECT slug, name_te, description FROM menu_items WHERE tenant_id = $1 AND is_active", tenant_id)
    extra = {r["slug"]: {"name_te": r["name_te"], "description": r["description"]} for r in rows}
    return catalog_view(templates, catalog, prices, policy, extra)


def _selection(body: PriceIn):
    from app.menu.builder import Selection

    diet = body.diet if body.diet in ("veg", "non_veg", "mixed", "jain") else None
    return Selection(body.package_key, body.guest_count, body.choices, body.add, body.remove, diet)


@router.post("/menu/price")
async def menu_price(body: PriceIn, tenant_id=Depends(default_tenant)):
    from app.menu.builder import customer_view, price_selection

    templates, catalog, prices, policy = await _menu_context(tenant_id)
    tpl = next((t for t in templates if t.key == body.package_key), None)
    if not tpl:
        raise HTTPException(404, "That package is not on the menu.")
    pkg, notes = price_selection(tpl, _selection(body), catalog, prices, policy)
    return customer_view(pkg, tpl, notes)


class MenuEnquiryIn(PriceIn):
    name: str = Field(min_length=2, max_length=80)
    phone: str = Field(min_length=10, max_length=20)
    email: str | None = None
    occasion: str | None = None
    event_date: str | None = None


@router.post("/menu/enquire")
async def menu_enquire(body: MenuEnquiryIn, tenant_id=Depends(default_tenant)):
    """The built menu becomes a real quote on the customer's own portal link — the same quote
    Anvi and the owner see — and the owner is alerted at once."""
    from datetime import timedelta

    from app.leads import lifecycle
    from app.leads import quotes as qrepo
    from app.menu.builder import customer_view, price_selection
    from app.pricing.market import market_snapshot

    phone = normalise_phone(body.phone)
    if not phone:
        raise HTTPException(422, "Please enter a phone number with the country code, e.g. +91 98765 43210.")
    if not await rate_limit(f"rl:menu-enquiry:{phone}", 5, 3600):
        raise HTTPException(429, "We have this menu already — the owner will call shortly.")
    templates, catalog, prices, policy = await _menu_context(tenant_id)
    tpl = next((t for t in templates if t.key == body.package_key), None)
    if not tpl:
        raise HTTPException(404, "That package is not on the menu.")
    pkg, notes = price_selection(tpl, _selection(body), catalog, prices, policy)

    s = get_settings()
    customer = await leads.get_or_create_customer(tenant_id, phone, body.name.strip())
    email = (body.email or "").strip().lower() or None
    if email and "@" in email:
        await db.execute("UPDATE customers SET email = $2 WHERE id = $1", customer["id"], email)
    await leads.record_consent(tenant_id, customer["id"], "communication", True, {"via": "menu_builder"})
    await leads.record_consent(tenant_id, customer["id"], "data_storage", True, {"via": "menu_builder"})
    lead = await leads.get_or_create_open_lead(tenant_id, customer["id"], source="web_chat")
    fields: dict = {"guest_count": body.guest_count, "diet": pkg.diet}
    if body.occasion:
        fields["occasion"] = body.occasion.strip().lower().replace(" ", "_")
    ev = None
    if body.event_date:
        try:
            ev = date.fromisoformat(body.event_date)
            fields["event_date"] = ev
        except ValueError:
            pass
    lead = await leads.update_lead_fields(lead["id"], fields)
    ev = ev or date.today() + timedelta(days=21)
    snap = market_snapshot(pkg, prices)
    saved = await qrepo.save_quote(tenant_id, lead["id"], pkg, ev, market_snapshot=snap, actor="customer",
                                   event_payload={"package": tpl.key, "changes": notes, "via": "menu_builder"})
    if lead.get("stage") in ("new", "qualifying", "qualified"):
        await leads.set_stage(tenant_id, lead["id"], "quoted", actor="customer")
    portal_url = f"{s.public_web_url}/portal/{saved['portal_token']}"
    await lifecycle.on_quote_saved(tenant_id, lead, saved, changed=False, change_summary=None, portal_url=portal_url)
    summary = f"{tpl.name} · {body.guest_count} guests · ₹{pkg.per_plate}/plate · total ₹{pkg.grand_total}" + (f" · {'; '.join(notes)}" if notes else "")
    subject, text = build_enquiry_alert(name=body.name.strip(), phone="+" + phone, email=email, lead=lead,
                                        message=f"(built on the website) {summary}", admin_url=admin_url_for(lead))
    await alert_owner(subject, text)
    if email:
        await send_email(email, f"Your menu and price · {saved['quote_number']}",
                         f"Namaste {body.name.split()[0]},\n\nHere is the menu you built, priced on today's market rates:\n{summary}\n\n"
                         f"Your live quote (change it, lock the price, pay the advance): {portal_url}\n\nWarmly,\nAnvi")
    return {"ok": True, "quote_number": saved["quote_number"], "portal_token": saved["portal_token"], "portal_url": portal_url,
            **customer_view(pkg, tpl, notes)}
