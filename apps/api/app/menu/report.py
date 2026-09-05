"""The owner's pricing report: every package costed on today's rates, beside the printed card
and the Justdial band. `python -m app.cli price-report`."""
from __future__ import annotations

from decimal import Decimal as D
from uuid import UUID

from app.menu import sri_sai_raja as M
from app.menu.builder import Selection, price_selection
from app.pricing.repository import load_catalog, load_policy, load_prices, load_templates

GUEST_BANDS = (50, 100, 200, 400)


async def build(tenant_id: UUID) -> str:
    templates, catalog, prices, policy = await load_templates(tenant_id), await load_catalog(tenant_id), await load_prices(tenant_id), await load_policy(tenant_id)
    L = ["# Package pricing report", f"Base margin {policy.target_margin_pct}% (floor {policy.min_margin_pct}%) · tier {dict(policy.tier_adj)} · "
         f"volume {[(u, str(a)) for u, a in policy.volume_ladder]}", "", "| Package | Card | Cost | " + " | ".join(f"{g} guests" for g in GUEST_BANDS) + " | Justdial band |",
         "|---|---:|---:|" + "---:|" * len(GUEST_BANDS) + "---|"]
    for tpl in templates:
        src = M.PACKAGE_BY_KEY.get(tpl.key)
        cells = []
        cost = None
        for g in GUEST_BANDS:
            pkg, _ = price_selection(tpl, Selection(tpl.key, g, {}), catalog, prices, policy)
            cost = cost or (pkg.cost_total / g).quantize(D("0.01"))
            cells.append(f"₹{pkg.per_plate:.0f} ({pkg.margin_pct:.0f}%)")
        band = f"₹{src.market_low:.0f}–{src.market_high:.0f}" if src and src.market_high else "—"
        card = f"₹{tpl.list_price:.0f}" if tpl.list_price is not None else "—"
        L.append(f"| {tpl.name} | {card} | ₹{cost} | " + " | ".join(cells) + f" | {band} |")
    L += ["", "Cost is food + labour + overhead per plate on the latest wholesale observations. Margin in brackets is on that cost.",
          "Card is the printed per-plate; the Justdial band is what listed Hyderabad caterers quote for a comparable spread."]
    return "\n".join(L)
