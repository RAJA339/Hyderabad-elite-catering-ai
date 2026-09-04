# Environment Variables

Copy `.env.example` to `.env` (API) and `apps/web/.env.local` (web).

## API (`apps/api`)
| Variable | Required | Purpose |
|---|---|---|
| `DATABASE_URL` | yes | `postgresql+asyncpg://user:pass@host:5432/hecai` |
| `REDIS_URL` | yes | `redis://localhost:6379/0` |
| `APP_SECRET` | yes | JWT signing, magic links, OTP HMAC |
| `TENANT_DEFAULT_SLUG` | no | default tenant for single-business deployments (`hec`) |
| `LLM_PROVIDER` | yes | `anthropic` (default) or `openai` |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | one | model access |
| `ANTHROPIC_WORKSPACE_ID` | if identity-linked | Sent as the `anthropic-workspace-id` header. Identity-linked keys return HTTP 400 without it; ordinary keys need nothing. |
| `LLM_MODEL` | no | default `claude-opus-5` (Anthropic) / `gpt-4o` (OpenAI) |
| `LLM_EFFORT` | no | `low`–`max`, default `medium`. Steers thinking depth and spend on current Claude models, which reject `temperature`. |
| `LLM_MAX_TOKENS` | no | default 8000. Thinking is billed against this, so a small cap returns empty replies. |
| `EMBEDDING_PROVIDER` | yes | `openai` (text-embedding-3-large) or `voyage` (voyage-3-large) |
| `VOYAGE_API_KEY` | if voyage | |
| `COHERE_API_KEY` | no | enables Cohere rerank |
| `WHATSAPP_VERIFY_TOKEN` | yes | webhook verification challenge |
| `WHATSAPP_APP_SECRET` | yes | X-Hub-Signature-256 verification |
| `WHATSAPP_ACCESS_TOKEN` | yes | Cloud API bearer token |
| `WHATSAPP_PHONE_NUMBER_ID` | yes | sending number |
| `WHATSAPP_API_VERSION` | no | default `v21.0` |
| `OWNER_WA_NUMBER` | no | owner's personal WhatsApp, digits with country code; receives escalation alerts |
| `TELEGRAM_BOT_TOKEN` | no | from @BotFather; owner alerts on Telegram, no approvals needed |
| `TELEGRAM_CHAT_ID` | no | the owner's chat id with that bot |
| `RESEND_API_KEY` | no | email for customers who gave an address, and the owner's backup |
| `OWNER_EMAIL` | no | owner alerts by email |
| `EMAIL_FROM` | no | sender; Resend's onboarding address works without a domain |
| `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` | V1 | payment links |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` / `LANGFUSE_HOST` | no | tracing |
| `TARGET_MARGIN_PCT` | no | default 40 |
| `MIN_MARGIN_PCT` | no | default 32 |
| `MAX_GUESTS` | no | default 500 (hard cap) |
| `PRICE_INGEST_CRON` | no | default `0 * * * *` |
| `CORS_ORIGINS` | no | comma-separated web origins |

## Web (`apps/web`)
| Variable | Purpose |
|---|---|
| `NEXT_PUBLIC_API_URL` | FastAPI base URL |
| `NEXT_PUBLIC_WA_NUMBER` | display number for "Chat on WhatsApp" |
