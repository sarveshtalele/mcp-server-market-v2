"""Centralised configuration loaded from environment / .env.

All services import `settings` from here so ports, URLs and the DB path are
defined once. Nothing in this file may contain an absolute or OS-specific
path: the project runs identically on macOS, Linux and Windows.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ root (two levels up from this file: core/config.py -> core -> backend)
BACKEND_ROOT = Path(__file__).resolve().parent.parent

# The MCP protocol revision this server implements. Single source of truth --
# the server, the client and the tests all read it from here.
PROTOCOL_VERSION = "2026-07-28"


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

    # --- Backend service (REST + MCP + AG-UI, one process) ----------------
    host: str = "127.0.0.1"
    port: int = 8000

    # Browser origins allowed to call the backend. Never "*": the MCP endpoint
    # must reject unknown origins (DNS-rebinding protection is mandatory under
    # the 2026-07-28 transport rules).
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:15000",
        "http://127.0.0.1:15000",
    ]

    # --- MCP --------------------------------------------------------------
    # Path the MCP Streamable HTTP endpoint is mounted at.
    mcp_path: str = "/mcp"
    # Freshness hint returned on cacheable results (1 hour).
    mcp_cache_ttl_ms: int = 3_600_000
    # Serve only PROTOCOL_VERSION. The SDK would otherwise also answer the
    # legacy 2025-11-25 initialize handshake. Set false if a bridge such as
    # mcp-remote turns out to require the older revision.
    strict_protocol: bool = True

    # Where MCP clients connect. This is the GATEWAY, not the backend: every
    # consumer goes through agentgateway so that all calls land in one audit
    # log. See CLAUDE.md invariant #7.
    mcp_gateway_url: str = "http://127.0.0.1:3111/mcp"

    # --- Observability ----------------------------------------------------
    # agentgateway's structured access log, tailed by the ingester.
    gateway_log_path: str = "mcp_server/gateway/logs/access.log"
    gateway_stdout_log: str = "mcp_server/gateway/logs/stdout.log"
    gateway_stderr_log: str = "mcp_server/gateway/logs/stderr.log"
    observability_database_url: str = f"sqlite:///{(BACKEND_ROOT / 'observability.db').as_posix()}"
    # Poll interval for the log tailer, seconds.
    ingest_interval_s: float = 1.0
    # Calls from one source separated by more than this are different episodes.
    episode_idle_gap_s: int = 30
    # Retention: keep at most this many rows, and nothing older than this.
    audit_max_rows: int = 50_000
    audit_max_age_days: int = 30
    # Truncation caps so the audit DB never stores whole payloads.
    audit_args_max_chars: int = 500
    audit_meta_max_chars: int = 1_000

    # Let the Control Room edit the gateway's tool allowlist. This is a
    # localhost PoC with no auth, so a browser editing a security policy is a
    # deliberate trade; set false to make the endpoint read-only.
    allow_policy_edit: bool = True

    # --- Client identity --------------------------------------------------
    # How this project's own agent identifies itself on every MCP request.
    client_name: str = "control-room"
    client_version: str = "2.0.0"

    # --- LLM (OpenAI-compatible; e.g. a LiteLLM proxy) --------------------
    llm_api_key: str | None = None
    # Proxy root, e.g. https://litellm-proxy.example.net  (no /v1 suffix).
    llm_base_url: str | None = None
    llm_model: str = "claude-sonnet-4-6"
    max_tokens: int = 4096

    @property
    def openai_base_url(self) -> str | None:
        """OpenAI client base URL (proxy root + /v1)."""
        if not self.llm_base_url:
            return None
        return self.llm_base_url.rstrip("/") + "/v1"

    @property
    def backend_mcp_url(self) -> str:
        """The backend's own MCP endpoint (what the gateway targets)."""
        return f"http://{self.host}:{self.port}{self.mcp_path}"

    def resolve(self, relative: str) -> Path:
        """Resolve a repo-relative setting to an absolute path."""
        return BACKEND_ROOT / relative

    # Currency label for synthetic data.
    currency: str = "USD"

    # Logging verbosity: DEBUG | INFO | WARNING | ERROR.
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()


settings = get_settings()
