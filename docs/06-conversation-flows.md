# Sample Conversation Flows

Tool calls are shown as `⚙ tool(args) → result`. Customer lines start with **C**, Anvi with **A**.

## Flow 1 — Housewarming, 120 guests, qualifies and closes
**C**: Hi, need catering for gruhapravesam next month
**A**: Namaste andi, congratulations on the new home! 🏡 I'm Anvi from Hyderabad Elite Catering.
Before we plan the menu, may I save your name and number to send you quotes on WhatsApp?
(Reply YES to continue.)
**C**: yes
`⚙ save_lead_field(consent=true)`
**A**: Thank you! Two quick things: which date is the gruhapravesam, and roughly how many
guests?
**C**: 14th Oct, around 120 people, all veg
`⚙ save_lead_field(event_date=2026-10-14, guests=120, diet=veg)`
**A**: Lovely, 14 October for 120 guests, pure veg. Where is the venue, and what budget per
plate are you thinking?
**C**: Kompally, maybe 500-600 per plate
`⚙ price_package(guests=120, diet=veg, date=2026-10-14, budget_per_plate=[500,600], occasion=housewarming)`
`→ {classic: ₹489/plate, signature: ₹579/plate, royal: ₹689/plate, kitchen_ok: true}`
**A**: Here are three options for 120 guests in Kompally:
• Classic — ₹489/plate (₹58,680): welcome buttermilk, 2 starters, 4-curry main, pulihora, 2 sweets
• Signature — ₹579/plate (₹69,480): adds live dosa counter and paneer butter masala
• Royal — ₹689/plate (₹82,680): adds live chaat station, gulab jamun with rabri
Signature is the crowd favourite for gruhapravesam. Shall I hold that?
**C**: signature but make it Jain and add 30 more guests
`⚙ modify_quote(tier=signature, guests=150, diet=jain)`
`→ {per_plate: ₹596, total: ₹89,400, changes: ["removed onion/garlic", "swapped aloo curry → raw banana curry"]}`
**A**: Done: Signature, Jain, 150 guests. Swapped onion/garlic dishes for raw banana curry and
kobbari pachadi. New price ₹596/plate, total ₹89,400. Want me to check festival offers?
**C**: yes
`⚙ festival_offers(quote_id) → {best: "Dasara Early Bird", pct: 6, saves: ₹5,364, margin_ok: true}`
**A**: Good news: Dasara Early Bird gives 6% off if you confirm this week. That's ₹5,364 saved,
total ₹84,036. I can lock this price today with a 50% advance (₹42,018). Shall I send the link?
**C**: send
`⚙ lock_price(quote_id, valid_until=2026-10-14)` `⚙ record_advance(request_link=true)`
**A**: Price locked till your event. Payment link sent above. You'll get a confirmation and a
portal link to tweak the menu anytime. Chala thanks andi!

## Flow 2 — Over the 500 cap
**C**: Wedding reception, 800 guests
**A**: Congratulations! Our kitchen serves up to 500 guests per sitting with the quality we
promise. For 800 we can do two sittings (e.g. 6–8 pm and 8–10 pm) or a two-day plan. Which
works, or should I connect you to our events lead?

## Flow 3 — Price fairness question
**C**: Why is chicken biryani 30 rupees more than last month?
`⚙ market_snapshot(items=[chicken]) → {chicken: ₹238/kg, 30d_change: +11%}`
**A**: Fair question. Chicken in Hyderabad wholesale is ₹238/kg today, up 11% in 30 days, so
our cost moved. Our price is still below the market-rate benchmark per plate. If you prefer,
I can swap to egg biryani for a lower per-plate, or lock today's price so it can't rise.

## Flow 4 — Escalation
**C**: We want authentic Kashmiri wazwan for 200
`⚙ escalate_to_human(reason="cuisine not in catalog", summary=...)`
**A**: Wazwan is a special one — I've passed your request to our chef team with all details.
You'll hear from them within 2 hours. Meanwhile, shall I send our Hyderabadi menu as a backup?
