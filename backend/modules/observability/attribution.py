"""Turn a caller's self-reported identity into a stable source label.

Under MCP 2026-07-28 ``io.modelcontextprotocol/clientInfo`` arrives in ``_meta``
on **every** request. Earlier revisions announced identity once, during the
``initialize`` handshake, and it had to be remembered against a session — which
is why per-call attribution was not possible before this revision.

Two rules, both deliberate:

* Matching is on a configured substring table, not on guesswork.
* Anything unmatched is ``unknown``. An unattributed call must look
  unattributed; a plausible-looking wrong host is worse than an honest gap.
"""

from __future__ import annotations

import json
import os
from typing import Any

SOURCE_UNKNOWN = "unknown"

# Substring -> source label, checked in order against a lowercased client name.
# Populate from *observed* values (see CLAUDE.md §6.1). Everything here is a
# starting guess except "control-room", which we set ourselves and therefore
# know to be exact.
DEFAULT_PATTERNS: tuple[tuple[str, str], ...] = (
    ("control-room", "control-room"),
    ("claude-code", "claude-code"),
    ("claude code", "claude-code"),
    ("claude-desktop", "claude-desktop"),
    ("claude desktop", "claude-desktop"),
    ("claude-ai", "claude-desktop"),
    ("vscode", "vscode-copilot"),
    ("visual studio code", "vscode-copilot"),
    ("copilot", "vscode-copilot"),
    ("antigravity", "antigravity"),
    ("mcp-remote", "mcp-remote-bridge"),
    ("cli-chat", "cli-chat"),
    ("mcp-inspector", "mcp-inspector"),
)


def _patterns() -> tuple[tuple[str, str], ...]:
    """Allow the table to be overridden without a code change.

    ``MCP_SOURCE_PATTERNS`` is a JSON object of ``{"substring": "label"}``.
    """
    raw = os.environ.get("MCP_SOURCE_PATTERNS")
    if not raw:
        return DEFAULT_PATTERNS
    try:
        overrides = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return DEFAULT_PATTERNS
    if not isinstance(overrides, dict):
        return DEFAULT_PATTERNS
    extra = tuple((str(k).lower(), str(v)) for k, v in overrides.items())
    return extra + DEFAULT_PATTERNS


def source_for(client_name: str | None, route_hint: str | None = None) -> str:
    """Resolve a source label from a client name, else a gateway route hint.

    ``route_hint`` is the fallback for hosts whose bridge strips or rewrites
    ``clientInfo``: give that host its own gateway listener and the route
    becomes the identity.
    """
    if client_name:
        lowered = client_name.strip().lower()
        for needle, label in _patterns():
            if needle in lowered:
                return label
    if route_hint:
        hint = route_hint.strip().lower()
        for needle, label in _patterns():
            if needle in hint:
                return label
        if hint:
            return hint
    return SOURCE_UNKNOWN


def client_info_from_meta(meta: Any) -> tuple[str | None, str | None]:
    """Extract (name, version) from a request's ``_meta`` block."""
    if not isinstance(meta, dict):
        return None, None
    info = meta.get("io.modelcontextprotocol/clientInfo")
    if not isinstance(info, dict):
        return None, None
    name = info.get("name")
    version = info.get("version")
    return (str(name) if name else None, str(version) if version else None)


def conversation_from_meta(meta: Any) -> str | None:
    """Pull a conversation id out of ``_meta``, if the client sent one.

    Only clients we control do. The value travels in the W3C ``baggage`` key,
    which the spec reserves for exactly this kind of correlation data. A vendor
    key is also accepted so a host that adds one later is picked up with no
    code change.
    """
    if not isinstance(meta, dict):
        return None
    baggage = meta.get("baggage")
    if isinstance(baggage, str):
        for item in baggage.split(","):
            key, _, value = item.partition("=")
            if key.strip() == "conversationId" and value.strip():
                return value.strip()[:64]
    for key, value in meta.items():
        if key.endswith("/conversationId") and isinstance(value, str) and value:
            return value[:64]
    return None


def trace_id_from_meta(meta: Any) -> str | None:
    """Extract the trace id from a W3C ``traceparent`` in ``_meta``."""
    if not isinstance(meta, dict):
        return None
    traceparent = meta.get("traceparent")
    if not isinstance(traceparent, str):
        return None
    parts = traceparent.split("-")
    # version-traceid-spanid-flags
    if len(parts) >= 3 and len(parts[1]) == 32:
        return parts[1]
    return None


# _meta keys the protocol defines. Anything else is third-party and worth
# preserving verbatim (capped) rather than dropping.
RESERVED_META_KEYS = frozenset(
    {
        "progressToken",
        "io.modelcontextprotocol/protocolVersion",
        "io.modelcontextprotocol/clientInfo",
        "io.modelcontextprotocol/clientCapabilities",
        "io.modelcontextprotocol/logLevel",
        "io.modelcontextprotocol/subscriptionId",
        "traceparent",
        "tracestate",
        "baggage",
    }
)


def extra_meta(meta: Any, limit: int) -> str | None:
    """JSON of any non-reserved ``_meta`` keys, truncated to ``limit`` chars."""
    if not isinstance(meta, dict):
        return None
    extras = {k: v for k, v in meta.items() if k not in RESERVED_META_KEYS}
    if not extras:
        return None
    try:
        blob = json.dumps(extras, separators=(",", ":"), default=str)
    except (TypeError, ValueError):
        return None
    return blob[:limit]
