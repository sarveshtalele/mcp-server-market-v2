"""Centralised configuration loaded from environment / .env.

All services import `settings` from here so ports, URLs and the DB path are
defined once.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ root (two levels up from this file: core/config.py -> core -> backend)
BACKEND_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Process-wide settings.

    Values can be overridden via environment variables or a `.env` file placed
    in the `backend/` directory.
    """

    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Database ---------------------------------------------------------
    database_url: str = f"sqlite:///{(BACKEND_ROOT / 'stock_market.db').as_posix()}"

    # --- Data API ---------------------------------------------------------
    data_api_host: str = "127.0.0.1"
    data_api_port: int = 8000
    # Base URL the MCP server / agent use to reach the Data API over HTTP.
    data_api_base_url: str = "http://127.0.0.1:8000"

    # --- AG-UI agent ------------------------------------------------------
    agui_host: str = "127.0.0.1"
    agui_port: int = 8001

    # --- LLM (OpenAI-compatible; e.g. a LiteLLM proxy) --------------------
    # A dedicated LLM_ prefix avoids colliding with any ANTHROPIC_* variables
    # already set in the user's OS environment (which would override .env).
    llm_api_key: str | None = None
    # Proxy root, e.g. https://litellm-proxy.example.net  (no /v1 suffix).
    llm_base_url: str | None = None
    # Model id as configured on the proxy. The proxy's Claude models are
    # reasoning models, so keep max_tokens generous.
    llm_model: str = "claude-sonnet-4-6"
    max_tokens: int = 4096

    @property
    def openai_base_url(self) -> str | None:
        """OpenAI client base URL (proxy root + /v1)."""
        if not self.llm_base_url:
            return None
        return self.llm_base_url.rstrip("/") + "/v1"

    # Currency label for synthetic data.
    currency: str = "USD"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()


settings = get_settings()
