"""Optional ingester for agentgateway's structured access log.

The in-process recorder (``recorder.py``) already captures every call that
*reaches* the server. This ingester exists for the one thing it cannot see: a
call the gateway **refused** because the tool was not on the allowlist. Those
never arrive at the backend, and a policy denial is exactly the kind of event an
audit log must not miss.

Field mapping caveat: the gateway's log schema is documented as a set of field
names (``mcp.method.name``, ``mcp.target``, ``mcp.resource.type``,
``mcp.resource.uri``, ``gen_ai.tool.name``), and the parser below accepts those
plus a few obvious aliases. It has been written against the documented names,
not against captured output from a running gateway — confirm it against a real
log before relying on it (see the Windows verification matrix in
IMPLEMENTATION_PLAN.md). Anything it cannot classify is skipped rather than
guessed at.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.config import settings
from core.logging_config import get_logger
from modules.observability.recorder import record

log = get_logger("observability.ingest")

# Candidate field names, most specific first.
_METHOD_KEYS = ("mcp.method.name", "mcp.methodName", "method")
_TOOL_KEYS = ("gen_ai.tool.name", "mcp.tool.name", "resource", "name")
_URI_KEYS = ("mcp.resource.uri", "uri")
_TYPE_KEYS = ("mcp.resource.type", "resource_type")
_ERROR_KEYS = ("mcp.tool.error", "error")
_STATUS_KEYS = ("status", "http.status_code", "response.code")
_LATENCY_KEYS = ("duration_ms", "latency_ms", "duration")
_CLIENT_KEYS = ("mcp.client.name", "client.name", "user_agent")


def _first(record_dict: dict, keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in record_dict and record_dict[key] not in (None, ""):
            return record_dict[key]
    return None


def parse_line(line: str) -> dict | None:
    """Turn one gateway log line into recorder kwargs, or None to skip it."""
    line = line.strip()
    if not line or not line.startswith("{"):
        return None
    try:
        entry = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(entry, dict):
        return None

    method = _first(entry, _METHOD_KEYS)
    if not method:
        return None

    name = _first(entry, _TOOL_KEYS) or _first(entry, _URI_KEYS)
    error = _first(entry, _ERROR_KEYS)
    status_code = _first(entry, _STATUS_KEYS)
    denied = bool(error) or (isinstance(status_code, (int, float)) and int(status_code) >= 400)

    client_name = _first(entry, _CLIENT_KEYS)
    meta: dict[str, Any] = {}
    if client_name:
        meta["io.modelcontextprotocol/clientInfo"] = {"name": str(client_name)}

    params: dict[str, Any] = {"_meta": meta}
    if name:
        params["name"] = name

    latency = _first(entry, _LATENCY_KEYS)
    try:
        latency_ms = float(latency) if latency is not None else 0.0
    except (TypeError, ValueError):
        latency_ms = 0.0

    return {
        "method": str(method),
        "params": params,
        "status": "error" if denied else "ok",
        "error_message": str(error) if error else None,
        "latency_ms": latency_ms,
        "via": "gateway",
        "ts": _timestamp(entry),
    }


def _timestamp(entry: dict) -> datetime | None:
    raw = entry.get("timestamp") or entry.get("time") or entry.get("ts")
    if not isinstance(raw, str):
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(UTC).replace(tzinfo=None)
    return parsed


class GatewayLogIngester:
    """Tails the gateway access log and records what the backend never saw."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or settings.resolve(settings.gateway_log_path)
        self._offset = 0
        self._inode: int | None = None
        self._task: asyncio.Task | None = None

    def poll_once(self) -> int:
        """Read whatever is new. Returns the number of rows recorded."""
        if not self.path.exists():
            return 0
        try:
            stat = self.path.stat()
        except OSError:
            return 0

        # A rotated or truncated file restarts from the beginning; without this
        # check a restart would silently stop ingesting.
        if self._inode is not None and (stat.st_ino != self._inode or stat.st_size < self._offset):
            self._offset = 0
        self._inode = stat.st_ino

        if stat.st_size == self._offset:
            return 0

        written = 0
        try:
            with self.path.open("r", encoding="utf-8", errors="replace") as handle:
                handle.seek(self._offset)
                for line in handle:
                    parsed = parse_line(line)
                    if parsed is None:
                        continue
                    # The backend recorder already logged everything it served.
                    # Only denials add information here.
                    if parsed["status"] != "error":
                        continue
                    try:
                        record(**parsed)
                        written += 1
                    except Exception as exc:  # noqa: BLE001
                        log.warning("ingest failed: %s", exc)
                self._offset = handle.tell()
        except OSError as exc:
            log.warning("cannot read gateway log %s: %s", self.path, exc)
        return written

    async def run(self) -> None:
        """Poll forever. Cancelled on app shutdown."""
        log.info("gateway log ingester watching %s", self.path)
        while True:
            try:
                await asyncio.to_thread(self.poll_once)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - never kill the app
                log.warning("ingester error: %s", exc)
            await asyncio.sleep(settings.ingest_interval_s)

    def start(self) -> asyncio.Task:
        self._task = asyncio.create_task(self.run())
        return self._task

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        finally:
            self._task = None
