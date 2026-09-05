# The menu: Sri Sai Raja Caterers' cards, priced live

The owner's printed menu ("Amma chethi vanta", Sri Sai Raja Caterers) is data in this repo:
`apps/api/app/menu/sri_sai_raja.py` holds the 50 dishes and the 9 per-plate cards;
`apps/api/app/menu/recipes.py` holds what one catering plate of each dish takes, in the
ingredient keys the market feed prices. The database follows that file: on every API boot
`app.menu.loader.ensure()` applies it when `MENU_VERSION` is newer than what the tenant
records, and `python -m app.cli apply-menu` forces it. Nothing about the menu is edited in
the database by hand.

## The cards, as transcribed

| Card | Tier | Printed | Fixed items | Choose-one lines |
|---|---|---:|---|---|
| Classic Veg | classic | ₹185 | veg biryani, white rice, pulihora, sambar, pappu, papad, curd, raita | curry (gutti vankaya / alu masala), fry (dondakaya / bendakaya), chutney (gongura / vankaya-dosakaya), sweet (purnalu / double ka meetha / gulab jamun), snack (mirchi bajji / vada / masala vada) |
| Comfort Veg | classic | ₹205 | Classic + paneer butter masala, dondakaya fry, both chutneys, puri, vanilla ice cream | — |
| Signature Veg | signature | ₹235 | biryani, rice, pulihora, sambar, pappu, paneer, vankaya-dosakaya chutney, papad, curd, raita, meetha paan, ice cream | curry (chole / alu tomato), fry (alu 65 / cauliflower 65 / dondakaya), sweet (purnalu / bobbatlu / double ka meetha), snack (mirchi bajji / masala vada), bread (puri / chapati) |
| Festive Veg | signature | ₹265 | rice, pulihora, sambar, pappu, paneer, alu tomato, dondakaya fry, both chutneys, papad, karapodi, curd, raita, puri, paan, ice cream | rice (veg biryani / bagara rice), sweet (purnalu / bobbatlu / gulab jamun / rava kesari), snack |
| Grand Veg | royal | ₹305 | 22 items incl. paneer, chole, two fries, two chutneys, purnalu, chakkara pongali, butterscotch ice cream, majjiga charu, fruit salad, karapodi & ghee, puri, phulka | — |
| Chicken Dum | classic | ₹315 | chicken dum biryani, mutton curry, chicken fry, white rice, sambar, rasam, gutti vankaya, curd, raita, salad, ice cream | sweet (gulab jamun / double ka meetha), snack |
| Mutton Dum | signature | ₹315 | mutton dum biryani, chicken curry, chicken fry, … | sweet, snack |
| Chicken Dum · Coastal | signature | ₹365 | Chicken Dum + fish fry | prawns (curry / fry), sweet, snack |
| Mutton Dum · Coastal | royal | ₹365 | Mutton Dum + fish fry | prawns (curry / fry), sweet, snack |

Disposable plates, glasses and spoons, tissues and dustbin covers are inside every plate
(`disposables`, cannot be removed). Packaged water is **not** in any card: it is an optional
add-on (`water`), priced per plate, that the builder and Anvi offer.

## What a plate costs, and what to charge

Costing is the same as for everything else: recipe × today's wholesale rate, plus per-dish
labour, plus 18% overhead (transport, gas, vessels, cooks) — see `OVERHEAD_PCT`. On the seed's
opening rates the cards work out like this at 100 guests:

| Card | Printed | Cost/plate | Margin at printed | Engine | Justdial band* |
|---|---:|---:|---:|---:|---|
| Classic Veg | ₹185 | ₹103 | 44% | **₹179** | ₹250–300 |
| Comfort Veg | ₹205 | ₹121 | 41% | **₹199** | ₹250–320 |
| Signature Veg | ₹235 | ₹147 | 37% | **₹230** | ₹280–350 |
| Festive Veg | ₹265 | ₹155 | 42% | **₹270** | ₹300–400 |
| Grand Veg | ₹305 | ₹179 | 41% | **₹310** | ₹350–450 |
| Chicken Dum | ₹315 | ₹213 | 32% | **₹319** | ₹350–450 |
| Mutton Dum | ₹315 | ₹230 | 27% | **₹350** | ₹400–550 |
| Chicken Dum · Coastal | ₹365 | ₹282 | 23% | **₹410** | ₹450–600 |
| Mutton Dum · Coastal | ₹365 | ₹299 | 18% | **₹430** | ₹500–700 |

\* What listed Hyderabad caterers quote for a comparable spread on Justdial's category
pages (veg buffets from ~₹250, chicken-biryani non-veg from ~₹350, mutton and seafood
menus ₹400+). Stored per card as `market_low` / `market_high`.

The read:

- **Veg is already the cheapest listed price in the city and still carries 37–44%.** The
  engine holds it there and takes the entry card a little lower (₹179, a classic-tier price
  point ending in 9) because that is the number people compare on. Bigger events go lower
  still through the volume ladder (₹169 at 300+).
- **Non-veg is priced on last year's mutton.** At ₹760/kg wholesale the two mutton cards
  earn 18–27%, under the 30% floor the tenant runs on, and every mutton spike comes out of
  the owner's pocket. The engine lifts them to ₹350 / ₹410 / ₹430 — still under the Justdial
  band for the same spread — and Chicken Dum stays where it is. When mutton falls, so do
  they, automatically.
- Live numbers on the site will differ from this table by a few rupees: they are computed
  on that morning's observations, and the seed carries a chicken and onion spike.

## Calibration

The tenant policy the cards are priced on: base 38%, floor 30%, tier shaping
`classic:-3,signature:0,royal:2`, volume ladder `75:0,150:-2,300:-5,500:-8`
(`MARGIN_TIER_ADJ`, `MARGIN_VOLUME_LADDER`). Each card then adds its own points
(`margin_adj` on the template, from `MARGIN_ADJ` in the menu module) so the engine lands on
the recommended number at 100 guests: +9 Classic, +6 Comfort, 0 Signature, +5 Festive,
+3 Grand, 0 Chicken Dum, −2 Mutton Dum, −7 / −8 Coastal. A quote remembers the card it
started from (`pricing_trace.policy.package`), so a later change on the portal or in chat
re-prices with the same shaping.

One engine change came with the cards: a line's price is no longer rounded up to the next
₹5. A twenty-item thali rounded per line was ₹30–40 dearer than its margin needed; the plate
is rounded once, to the tier's price point, in `price_package`.

To re-run the numbers on the live database: `python -m app.cli price-report`.

## Changing the menu

1. Edit `sri_sai_raja.py` (a dish, a card, a slot, a printed price) and, for a new dish, add
   its recipe to `recipes.py` — every ingredient key must exist or be listed in
   `EXTRA_INGREDIENTS`, which the loader creates with an opening rate.
2. Bump `MENU_VERSION`.
3. Run the tests (`tests/test_menu.py` checks every card prices within a few percent of its
   printed number) and deploy. The API applies the new version on boot and re-indexes the
   search corpus; `apply-menu` does the same by hand.

Set `MENU_SOURCE=` (empty) to stop the API touching the catalogue at startup.

## Where the cards show up

- `/menu` — the builder: nine cards, the choose-one lines as chips, add anything from the
  kitchen, live per-plate and total, and "Get this quote on my phone", which creates a real
  quote on the customer's portal link and alerts the owner (`POST /api/public/menu/enquire`).
- The landing page lists the cards with live prices and links into the builder.
- Anvi's `price_package` tool returns each card's `choose_one` lines; the system prompt tells
  her to offer them as free swaps and never to invent a live counter.
- The RAG corpus renders each card with its fixed items, its choices, what is included, and
  that water is an add-on.
