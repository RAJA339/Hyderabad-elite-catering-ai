# Deployment — from your laptop to a shareable URL

Two services, two free-tier hosts, about twenty minutes. At the end you have a public
address you can send to anyone.

| Piece | Host | Free tier |
|---|---|---|
| PostgreSQL + pgvector | Neon | yes |
| Redis | Upstash | yes |
| API (FastAPI) | Railway | trial credit, then paid |
| Website (Next.js) | Vercel | yes |

Redis is optional. Without it the semantic cache and rate limiting are skipped; everything
else works. Skip step 2 if you would rather keep it simple.

---

## 1. Database (Neon)

1. Create a project at neon.tech. Choose a region near your users (Singapore or Mumbai for India).
2. Copy the connection string. It looks like
   `postgresql://user:pass@ep-xxx.ap-southeast-1.aws.neon.tech/neondb?sslmode=require`.
3. Enable pgvector once, from the Neon SQL editor:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```

## 2. Redis (Upstash), optional

Create a database at upstash.com and copy the `rediss://` URL.

## 3. Fill the database from your laptop

Point your local `.env` at Neon temporarily and run one command:

```bash
cd apps/api
python -m app.cli set-env DATABASE_URL=postgresql://...neon.tech/neondb?sslmode=require
python -m app.cli bootstrap
```

`bootstrap` applies the schema, seeds menus, prices, festivals and rules, computes item
costs, builds the search index, and rotates the admin password. **It prints the new admin
password once — copy it.** The password shipped in this repository stops working, which
matters because anyone can read it here.

Point `DATABASE_URL` back at localhost afterwards if you want to keep developing locally.

## 4. API (Railway)

1. New project, then Deploy from GitHub, and pick this repository.
2. In **Settings → Build**, set these by hand and confirm each one saves — a field left in
   Railway's unsaved state (an × and a ✓ beside it) is not applied, and the build silently
   falls back to Railpack, which cannot work out how to build a monorepo:

   | Setting | Value |
   |---|---|
   | Builder | `Dockerfile` |
   | Dockerfile Path | `apps/api/Dockerfile` |
   | Root Directory | leave empty |

   The root directory must stay at the repository root: the Dockerfile copies `db/`,
   `knowledge/` and `eval/` from there, so `apps/api` as the context cannot build.
   `railway.json` is not read — Railway's Config-as-code is deprecated and services created
   after 2026-08-28 cannot opt in — so the dashboard is the only source of truth.
3. In **Settings → Deploy**, set Healthcheck Path to `/health`, its timeout to `120`, and the
   restart policy to On Failure. Without a healthcheck a broken deploy replaces a working one.
4. Add these variables:

   | Variable | Value |
   |---|---|
   | `DATABASE_URL` | your Neon string |
   | `REDIS_URL` | your Upstash string, or leave unset |
   | `APP_SECRET` | `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
   | `ANTHROPIC_API_KEY` | your key |
   | `ANTHROPIC_WORKSPACE_ID` | only if your key is identity-linked |
   | `APP_ENV` | `prod` |
   | `CORS_ORIGINS` | your Vercel URL **with `https://`**, filled in after step 5 |
   | `PUBLIC_WEB_URL` | the same Vercel URL |
   | `RUN_SCHEDULER` | `1` on exactly one instance, `0` on any others |

5. Deploy, then open `https://<your-api>.up.railway.app/health`. It reports the state that
   decides whether the site works — `db`, `llm_key_present`, and the exact `cors_origins` the
   API is running with. A CORS rejection is invisible in the browser, so this is the only
   place the live value can be read:

   ```json
   {"status":"ok","db":true,"redis":false,
    "cors_origins":["https://your-site.vercel.app"],"llm_key_present":true}
   ```

   `cors_origins` must match the site's address character for character, scheme included.
   `redis:false` is fine — rate limiting and the semantic cache are simply off.

## 5. Website (Vercel)

1. Import the same repository. Set the root directory to `apps/web`.
2. Add `NEXT_PUBLIC_API_URL` = your Railway URL, and `NEXT_PUBLIC_WA_NUMBER` = your number.
3. Deploy. **Then go back to Railway** and set `CORS_ORIGINS` and `PUBLIC_WEB_URL` to the
   Vercel URL, and redeploy the API. The browser calls the API directly, so it is blocked
   until its origin is allowed. Write the full origin, `https://` and all: matching is exact
   against what the browser sends, and a bare `site.vercel.app` matches nothing.

   Note that Railway's **Redeploy** replays a past deployment's code snapshot. To build a new
   commit, push to the connected branch or use the service's own Deploy button.

Your shareable link is the Vercel URL.

## 6. Before you share it

- [ ] `/health` reports `db: true`
- [ ] The API log shows `llm_preflight_ok` at startup
- [ ] You can log in at `/admin` with the password `bootstrap` printed
- [ ] The old password `Admin@12345` is rejected
- [ ] `APP_SECRET` is not the placeholder
- [ ] The landing page ticker shows prices, which proves the browser reaches the API

## 7. WhatsApp, when you are ready

Local testing needs none of this; the widget on the site is enough. Everything below is
already built — webhook, signature check, media, buttons, hand-off — and waits on four
environment variables and a Meta account.

### Two numbers, not one

A number registered with the Cloud API **cannot be used in the WhatsApp app any more**.
Anvi answers on it through the API, and nobody can open it on a phone. So:

| Number | Who uses it | Where it goes |
|---|---|---|
| **Business number** — a fresh SIM, never used on WhatsApp | Customers message it; Anvi replies | `WHATSAPP_PHONE_NUMBER_ID` on Railway, `NEXT_PUBLIC_WA_NUMBER` on Vercel |
| **Owner's own number** — stays on the WhatsApp app as today | Receives an alert every time Anvi hands off | `OWNER_WA_NUMBER` on Railway |

Do not put the owner's personal number on the API. Registering it would remove it from
their phone.

Until the API is approved, `NEXT_PUBLIC_WA_NUMBER` can be the owner's number: the site's
"Chat on WhatsApp" button then opens a normal chat that the owner answers by hand. Set the
business number there once Anvi is live on it.

### What the owner receives

When a customer asks for a person, or Anvi decides she needs one, the owner gets one
WhatsApp message on their own phone: who, the event, why, a `wa.me` link to message the
customer from their personal number, and a link to the lead in the admin, from which a
reply goes out as the business number. Website-chat customers have no WhatsApp thread, so
they are offered a "continue on WhatsApp" link into the business number instead.

### Not in India? Start here instead

The Cloud API needs a GST document and an Indian SIM to take one OTP. Neither is doable from
abroad, so these two channels carry the business until someone in Hyderabad can do that.
They need no approval from anyone and take about ten minutes.

**Owner alerts on Telegram**

1. In Telegram, message **@BotFather** → `/newbot` → pick a name. Copy the token.
2. Open your new bot and send it any message (this is what lets it message you back).
3. Visit `https://api.telegram.org/bot<TOKEN>/getUpdates` in a browser and copy the number
   under `"chat":{"id":…}`.
4. Railway → Variables: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`. Redeploy.

From then on the owner's phone gets a message for every hand-off, locked price, advance
requested and advance paid — each with the customer's details and the admin link.

**Customers by email**

1. resend.com → API key. The `onboarding@resend.dev` sender works immediately with no
   domain; add your own domain later for deliverability.
2. Railway → Variables: `RESEND_API_KEY`, and `OWNER_EMAIL` if you also want alerts by mail.

Anvi asks for an email when it is useful and stores it; quotes, price-lock confirmations
and payment reminders then go by email to customers who are not on WhatsApp — which, until
the API is approved, is all of them. The website chat and the portal link remain the live
channel for the conversation itself.

**Check it worked:** `/health` now lists `owner_channels`. Then type "I want to talk to a
person" into the site chat — the owner's Telegram should buzz within a second.

### How Anvi learns

Two mechanisms, both grounded in this kitchen's own data rather than in a model's opinion.

**The sale has phases** (`app/agent/graph.py`). Every turn is classified — discover, design,
negotiate, close, won — from the lead's stage and whether a quote exists, and the phase
decides which tools are even on the belt. Anvi cannot lock a price before she has understood
the event, and cannot keep interrogating someone who is ready to pay. Discovery is where she
asks *why* the event matters, not just the logistics; that motive is stored on the lead and
shapes every menu she proposes afterwards.

**The playbook** (`app/agent/playbook.py`). A nightly job aggregates the last six months of
closed deals into a short briefing that goes into her prompt: which tier books a
housewarming, the median per-plate that was accepted versus lost in each guest band, the
dishes that appear in menus people actually book, how many messages a booking usually takes.
With fewer than five quotes in a category, that category is simply absent — it never guesses.
The figures are marked internal: they steer which menu she leads with and how she frames it,
and the hard rule that every rupee shown to a customer comes from a tool call is unchanged.

### How the price is set (and what to tune)

Three layers, all in `apps/api/app/pricing/`:

1. **Cost → margin → price** (`engine.py`). Every dish is a recipe costed on this morning's
   wholesale rates plus labour and overhead. The tenant's target margin is shaped per
   quote: Classic a few points under target, Royal a few over; and it steps down with guest
   count, so big events are cheaper per plate and still bring in more rupees. The floor
   follows the target but never drops below 24%. Tune with `MARGIN_TIER_ADJ` and
   `MARGIN_VOLUME_LADDER` against real competitor quotes.
2. **Positioning** (`psychology.py`). The headline per-plate lands on a price point —
   Classic ends in 9, the others in 0 — by upward rounding only. The customer's segment
   (value / mid / premium, from budget or occasion) picks the working tier and the order
   Anvi presents them in: mid-market buyers see Royal first so Signature lands as the
   sensible middle.
3. **Kelly-sized offers** (`psychology.py`, applied in `festivals/rules.py`). A discount is
   a bet on the booking closing. Half-Kelly of the margin headroom, using the lead's
   estimated close probability, caps the total concession — strong leads on fat margins get
   real festival offers, weak leads and thin margins get the market comparison instead.
   The estimate is stored on the lead and shown in the admin pipeline.

### Anvi on the phone

The call handling is built; it needs a telephony account and a number. Twilio works from
anywhere and is the fastest to test; Exotel and Plivo are the Indian equivalents and speak
the same webhook shape.

1. twilio.com → buy a number (an Indian number needs KYC; a US number works for testing and
   can receive international calls).
2. Railway → Variables: `VOICE_ENABLED=1`. Optionally `VOICE_LANGUAGE` (default `en-IN`) and
   `VOICE_TTS_VOICE` (default `Polly.Aditi`, an Indian-English voice).
3. Twilio → your number → **Voice → A call comes in** → Webhook, POST, to
   `https://<your-api>.up.railway.app/api/voice/incoming`. Set the status callback to
   `/api/voice/status`.
4. Call the number. Anvi greets, listens, and answers with the same brain that answers
   WhatsApp — the same tools, the same prices, the same guardrails.

What happens on a call: the carrier transcribes each thing the caller says and posts it to
`/api/voice/turn`; the orchestrator runs one normal turn; the reply is rewritten for the ear
(`app/voice/speech.py`) — rupees spoken in lakhs, links and emoji removed, trimmed to a few
sentences ending in a question — and returned as TwiML. A caller is keyed on their phone
number, so their call and their WhatsApp thread are the same lead.

Cost is per minute and set by the provider. Two honest limits: recognition of heavy
code-mixing (Telugu inside English) is the provider's, not ours, and this is turn-based
rather than full-duplex, so a caller cannot interrupt mid-sentence. Both are fixable later
with a streaming voice model; neither blocks taking real calls today.

### Getting paid by UPI, with no gateway

Razorpay needs KYC and days of onboarding. UPI needs a phone number that already has
PhonePe or Google Pay on it.

1. In PhonePe, open your profile and copy the **UPI ID** (looks like `9705316350@ybl`). In
   Google Pay it is under your name on the profile screen (`…@okaxis`, `…@oksbi`).
2. Railway → Variables: `UPI_VPA=<that id>`, `UPI_PAYEE_PHONE=919705316350`,
   `UPI_PAYEE_NAME=Hyderabad Elite Catering`. Redeploy.

From then on, when Anvi locks a price and the customer asks to pay, a card appears under her
message with the exact advance: one tap opens any UPI app with the amount filled in; on a
laptop the QR does the same from the phone camera. The customer types the 12-digit UTR their
app shows, the owner is alerted on every configured channel, and confirms with one tap on
the lead page in the admin — which marks the quote accepted and moves the lead to
"advance paid", exactly as a gateway webhook would.

The money goes straight to the owner's account. There is no fee and nothing to reconcile.

### Getting the Cloud API (India)

Allow three to ten working days, most of it waiting on Meta.

1. **Meta Business Portfolio** at business.facebook.com, then **Settings → Security Centre →
   Start verification**. You need a document that names the business: GST certificate,
   Udyam (MSME) registration, Shop & Establishment licence, or Certificate of Incorporation.
   Verification takes two to four days; nothing else can go live before it.
2. **developers.facebook.com → Create app → Business**. Add the **WhatsApp** product. This
   creates the WhatsApp Business Account (WABA) and a test number. Ignore the test number.
3. **WhatsApp → API Setup → Add phone number.** Enter the business SIM, take the SMS code,
   set a six-digit two-step PIN and keep it. Note the **Phone number ID** shown beside it.
   Set the display name here; it is reviewed within a day once the business is verified.
4. **A permanent token.** The token on the API Setup page expires in 24 hours. Go to
   **Business settings → Users → System users → Add**, role Admin, then **Generate token**
   with `whatsapp_business_messaging` and `whatsapp_business_management`. That token does
   not expire.
5. **App secret.** App → **Settings → Basic → App secret → Show**.
6. **Railway → Variables**:

   ```
   WHATSAPP_ACCESS_TOKEN=<system user token>
   WHATSAPP_PHONE_NUMBER_ID=<from step 3>
   WHATSAPP_APP_SECRET=<from step 5>
   WHATSAPP_VERIFY_TOKEN=<any long random string you choose>
   OWNER_WA_NUMBER=91XXXXXXXXXX
   ```

   Redeploy, and wait for `/health` to come back.
7. **Webhook.** App → WhatsApp → **Configuration → Callback URL**:
   `https://<your-api>.up.railway.app/api/webhooks/whatsapp`, verify token as in step 6,
   **Verify and save**. Then under **Webhook fields**, subscribe to **messages**.
8. **Templates.** Anything sent to a customer more than 24 hours after their last message
   must be an approved template. Submit the utility templates listed in
   `db/seed/seed.sql` under WhatsApp Manager → Message templates; approval takes a day.
9. **Test.** WhatsApp the business number from any phone. Anvi replies. Type "I want to talk
   to a person" — the owner's phone buzzes.
10. **Vercel**: set `NEXT_PUBLIC_WA_NUMBER` to the business number and redeploy.

Meta pricing is per message, with the first 1,000 service conversations a month free;
marketing templates are the expensive category. A qualification-to-quote conversation is a
service conversation.

## Keeping prices fresh

The scheduler recomputes costs hourly on whichever instance has `RUN_SCHEDULER=1`. To load
real market rates, either set `PRICE_SOURCE_URL` to a JSON feed you are licensed to use, or
upload a CSV from the admin Pricing page. Without a source it keeps recosting from the last
known prices, so quotes stay consistent but stop tracking the market.

## Costs

Neon, Upstash and Vercel have usable free tiers. Railway charges after trial credit,
typically a few dollars a month at this size. The Anthropic API is pay-as-you-go; a
qualification-to-quote conversation is a fraction of a rupee at current rates.
