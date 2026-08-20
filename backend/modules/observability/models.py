"""ORM model for one recorded MCP call."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from modules.observability.store import ObsBase


class McpCall(ObsBase):
    """One MCP request, as observed at the server.

    Every consumer — Claude Desktop, Claude Code, VS Code Copilot, Antigravity
    and this project's own web agent — reaches the server through the gateway,
    so one row is written here per call regardless of who made it. That is what
    makes a single cross-host activity view possible.
    """

    __tablename__ = "mcp_calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)

    # --- who ---------------------------------------------------------------
    # Normalised label: claude-desktop | claude-code | vscode-copilot |
    # antigravity | control-room | unknown
    source: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    caller_name: Mapped[str | None] = mapped_column(String(120))
    caller_version: Mapped[str | None] = mapped_column(String(48))
    # Only this project's own client can supply one: MCP defines no conversation
    # identifier, so external hosts leave this null. Never inferred.
    conversation_id: Mapped[str | None] = mapped_column(String(64), index=True)
    # Inferred grouping of calls from one source separated by an idle gap.
    # A reading aid, not an identity — never presented as a conversation.
    episode: Mapped[int] = mapped_column(Integer, nullable=False, default=1, index=True)

    # --- what --------------------------------------------------------------
    method: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    resource_type: Mapped[str | None] = mapped_column(String(24))  # tool|resource|prompt
    resource_name: Mapped[str | None] = mapped_column(String(200), index=True)
    args_preview: Mapped[str | None] = mapped_column(Text)

    # --- how it went -------------------------------------------------------
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)  # ok|error
    error_code: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # --- correlation -------------------------------------------------------
    protocol_version: Mapped[str | None] = mapped_column(String(24))
    trace_id: Mapped[str | None] = mapped_column(String(64), index=True)
    # Where the record was observed: "backend" (our own recorder) or "gateway"
    # (ingested from agentgateway's access log).
    via: Mapped[str] = mapped_column(String(16), nullable=False, default="backend")
    # Unrecognised _meta keys, preserved so a host that later starts sending a
    # conversation identifier is captured without a code change.
    extra_meta: Mapped[str | None] = mapped_column(Text)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "ts": self.ts.isoformat(timespec="milliseconds") + "Z",
            "source": self.source,
            "caller_name": self.caller_name,
            "caller_version": self.caller_version,
            "conversation_id": self.conversation_id,
            "episode": self.episode,
            "method": self.method,
            "resource_type": self.resource_type,
            "resource_name": self.resource_name,
            "args_preview": self.args_preview,
            "status": self.status,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "latency_ms": round(self.latency_ms, 1),
            "protocol_version": self.protocol_version,
            "trace_id": self.trace_id,
            "via": self.via,
            "extra_meta": self.extra_meta,
        }
