"""Central settings. Every secret comes from the environment; nothing is hard-coded."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env from the package, not the shell's working directory: the API is normally
# started from apps/api (or, once pip-installed, from anywhere), while .env sits at the
# repository root. Later files win, so apps/api/.env can override the shared root file.
_API_DIR = Path(__file__).resolve().parents[2]
_REPO_ROOT = _API_DIR.parents[1]
ENV_FILES = (_REPO_ROOT / ".env", _API_DIR / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILES, env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def _normalise_workspace_id(self):
        """`wrkspc_wrkspc_01ABC` happens when the prefix is typed and then a full id is
        pasted after it. It is never a real id, so repair it instead of failing at request
        time with an opaque 400."""
        wid = (self.anthropic_workspace_id or "").strip()
        while wid.startswith("wrkspc_wrkspc_"):
            wid = wid[len("wrkspc_") :]
        self.anthropic_workspace_id = wid or None
        return self

    @model_validator(mode="before")
    @classmethod
    def _drop_leftover_comments(cls, data):
        """`KEY=            # note` parses as the literal comment, not as empty. A stray
        model name or API key like that fails far from its cause, so treat it as unset."""
        if not isinstance(data, dict):
            return data
        return {k: (None if isinstance(v, str) and v.lstrip().startswith("#") else v) for k, v in data.items()}

    app_env: Literal["dev", "staging", "prod"] = "dev"
    app_secret: str = Field(default="change-me-in-prod", min_length=8)
    database_url: str = "postgresql://hecai:hecai@localhost:5432/hecai"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: str = "http://localhost:3000"
    tenant_default_slug: str = "hec"
    public_web_url: str = "http://localhost:3000"

    # LLM
    llm_provider: Literal["anthropic", "openai"] = "anthropic"
    llm_model: str | None = None
    anthropic_api_key: str | None = None
    # Identity-linked keys must name the workspace each request acts in. The SDK only
    # resolves this for its credential-file/federation chain, which a plain api_key skips,
    # so it is sent as an explicit anthropic-workspace-id header.
    anthropic_workspace_id: str | None = None
    openai_api_key: str | None = None
    llm_max_tokens: int = 8000        # thinking is billed against this; a low cap returns empty replies
    llm_effort: Literal["low", "medium", "high", "xhigh", "max"] = "medium"
    llm_temperature: float = 0.3      # OpenAI only; current Claude models reject sampling params

    # Embeddings / rerank
    embedding_provider: Literal["openai", "voyage"] = "openai"
    embedding_model: str | None = None
    voyage_api_key: str | None = None
    cohere_api_key: str | None = None
    rerank_model: str = "rerank-v3.5"

    # WhatsApp Cloud API
    whatsapp_verify_token: str = "verify-me"
    whatsapp_app_secret: str | None = None
    whatsapp_access_token: str | None = None
    whatsapp_phone_number_id: str | None = None
    whatsapp_api_version: str = "v21.0"
    # The owner's personal WhatsApp (digits with country code, e.g. 91XXXXXXXXXX). Anvi's
    # business number cannot be opened in the WhatsApp app, so escalations are pushed here.
    owner_wa_number: str | None = None

    # Channels that need no telecom approval and work from any country.
    telegram_bot_token: str | None = None   # from @BotFather
    telegram_chat_id: str | None = None     # the owner's chat id with that bot
    resend_api_key: str | None = None
    email_from: str = "Anvi at Hyderabad Elite Catering <onboarding@resend.dev>"
    owner_email: str | None = None

    # UPI collection. The VPA behind the owner's PhonePe/GPay number (see the app's profile
    # screen) makes the pay link and QR; the number alone is shown for people who type it.
    upi_vpa: str | None = None
    upi_payee_name: str = "Hyderabad Elite Catering"
    upi_payee_phone: str | None = None

    # Voice. Off until a telephony provider (Twilio, Exotel, Plivo) points its webhook here.
    voice_enabled: bool = False
    voice_language: str = "en-IN"
    voice_tts_voice: str = "Polly.Aditi"   # Indian-English neural voice on Twilio

    # Payments
    razorpay_key_id: str | None = None
    razorpay_key_secret: str | None = None

    # Observability
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "https://cloud.langfuse.com"

    # Business rules
    target_margin_pct: float = 38.0
    min_margin_pct: float = 30.0
    max_guests: int = 500
    gst_pct: float = 5.0
    advance_pct: float = 50.0  # half up front is the norm in Indian catering; the balance on the day
    # Margin shaping (see pricing/engine.py). Points added to the tenant target, per tier and
    # per guest-count band; tune against real competitor quotes without touching code.
    margin_tier_adj: str = "classic:-3,signature:0,royal:2"
    # Which menu the database follows at startup: "sri_sai_raja" (the owner's cards) or "" to leave the catalogue alone.
    menu_source: str = "sri_sai_raja"
    margin_volume_ladder: str = "75:0,150:-2,300:-5,500:-8"
    price_ingest_cron: str = "0 * * * *"
    semantic_cache_ttl_s: int = 6 * 3600
    semantic_cache_threshold: float = 0.96

    @property
    def resolved_llm_model(self) -> str:
        if self.llm_model:
            return self.llm_model
        return "claude-opus-5" if self.llm_provider == "anthropic" else "gpt-4o"

    @property
    def resolved_embedding_model(self) -> str:
        if self.embedding_model:
            return self.embedding_model
        return "text-embedding-3-large" if self.embedding_provider == "openai" else "voyage-3-large"

    @property
    def embedding_dim(self) -> int:
        return 3072 if self.embedding_provider == "openai" else 1024

    @property
    def cors_origin_list(self) -> list[str]:
        # CORS matching is exact and the browser sends a bare scheme://host, so anything the
        # value picks up on its way through a dashboard makes it silently never match:
        # surrounding quotes from a copy-paste, stray whitespace, a trailing slash.
        out = []
        for raw in self.cors_origins.split(","):
            o = raw.strip().strip("\"'").strip().rstrip("/")
            if not o:
                continue
            # A bare "site.vercel.app" reads as correct on a dashboard but matches nothing:
            # the browser sends a full scheme://host. Assume https, except for local dev.
            if "://" not in o:
                o = ("http://" if o.split(":")[0] in {"localhost", "127.0.0.1"} else "https://") + o
            out.append(o)
        return out


@lru_cache
def get_settings() -> Settings:
    return Settings()
