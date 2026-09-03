"""Central settings. Every secret comes from the environment; nothing is hard-coded."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

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

    # Payments
    razorpay_key_id: str | None = None
    razorpay_key_secret: str | None = None

    # Observability
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "https://cloud.langfuse.com"

    # Business rules
    target_margin_pct: float = 40.0
    min_margin_pct: float = 32.0
    max_guests: int = 500
    gst_pct: float = 5.0
    advance_pct: float = 30.0
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
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
