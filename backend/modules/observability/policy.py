"""Read and edit the gateway's tool allowlist.

The allowlist is the governance boundary: a tool the gateway does not permit is
refused before it ever reaches the server. It lives in the gateway's own
``config.yaml`` so it stays versioned in git and identical on every machine —
this module edits that file rather than introducing a second source of truth.

Two consequences worth being explicit about:

* **A change needs a gateway restart.** agentgateway reads its config at startup
  only. Every write here reports ``restart_required``.
* **This lets a browser edit a security policy.** For a localhost PoC with no
  auth that is a deliberate trade; set ``ALLOW_POLICY_EDIT=false`` to make the
  endpoint read-only.

The file is edited line-wise rather than through a YAML round-trip: a real YAML
load/dump would reformat and strip every comment in the config, and those
comments are the only explanation of why the gateway is configured as it is.
"""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

# Imported as a module, not `from core.config import settings`: the settings
# singleton can be rebound (the test harness does it when it starts a server on
# a random port), and a security flag must not be decided by a stale binding
# captured at import time.
from core import config

# One allowlist rule, capturing its indentation and the tool name.
_RULE = re.compile(r"^(?P<indent>\s*)-\s*'mcp\.tool\.name\s*==\s*\"(?P<name>[^\"]+)\"'\s*$")
_RULES_KEY = re.compile(r"^(?P<indent>\s*)rules:\s*$")

# Tool names are identifiers; anything else is a malformed request, and letting
# it through would let a caller inject arbitrary YAML into the gateway config.
_VALID_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class PolicyError(RuntimeError):
    """Raised when the allowlist cannot be read or written."""


def config_path() -> Path:
    return config.settings.resolve("mcp_server/gateway/config.yaml")


def read_allowlist() -> list[str]:
    """Tool names the gateway is currently configured to permit."""
    path = config_path()
    if not path.exists():
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise PolicyError(f"cannot read {path}: {exc}") from exc

    names: list[str] = []
    for line in text.splitlines():
        match = _RULE.match(line)
        if match:
            names.append(match.group("name"))
    return names


def write_allowlist(names: list[str], known_tools: list[str]) -> None:
    """Replace the allowlist rules with ``names``.

    ``known_tools`` is the server's actual tool surface; anything outside it is
    rejected rather than written, so the file cannot drift into naming tools
    that do not exist.
    """
    if not config.settings.allow_policy_edit:
        raise PolicyError(
            "policy editing is disabled (ALLOW_POLICY_EDIT=false); edit "
            "backend/mcp_server/gateway/config.yaml directly"
        )

    unique: list[str] = []
    for name in names:
        if not _VALID_NAME.match(name):
            raise PolicyError(f"not a valid tool name: {name!r}")
        if name not in known_tools:
            raise PolicyError(f"unknown tool: {name!r}")
        if name not in unique:
            unique.append(name)

    path = config_path()
    if not path.exists():
        raise PolicyError(f"no gateway config at {path}")
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)

    first, last, indent = _locate_rules(lines)
    if first is None:
        raise PolicyError(
            "no mcpAuthorization rules block found in the gateway config; "
            "edit the file by hand"
        )

    replacement = [f'{indent}- \'mcp.tool.name == "{name}"\'\n' for name in unique]
    if not replacement:
        # An empty list would leave `rules:` dangling, which agentgateway
        # rejects. Deny-all is expressed as a rule that can never match.
        replacement = [f"{indent}- 'false'\n"]

    updated = lines[:first] + replacement + lines[last + 1 :]
    _atomic_write(path, "".join(updated))


def _locate_rules(lines: list[str]) -> tuple[int | None, int, str]:
    """Find the contiguous rule lines; returns (first, last, indent)."""
    first: int | None = None
    last = -1
    indent = "                      "

    for index, line in enumerate(lines):
        match = _RULE.match(line)
        if match:
            if first is None:
                first = index
                indent = match.group("indent")
            last = index
        elif first is not None:
            break

    if first is not None:
        return first, last, indent

    # No rules yet: insert immediately after the `rules:` key, if present.
    for index, line in enumerate(lines):
        key = _RULES_KEY.match(line)
        if key:
            return index + 1, index, key.group("indent") + "  "
    return None, -1, indent


def _atomic_write(path: Path, content: str) -> None:
    """Write via a temp file in the same directory, then replace.

    A half-written gateway config is worse than an unchanged one: the gateway
    would fail to start on its next restart.
    """
    temp_name = ""
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp"
        ) as handle:
            temp_name = handle.name
            handle.write(content)
        os.replace(temp_name, path)
    except OSError as exc:
        if temp_name:
            Path(temp_name).unlink(missing_ok=True)
        raise PolicyError(f"cannot write {path}: {exc}") from exc
