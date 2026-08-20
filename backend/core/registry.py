"""Module registry — the heart of the pluggable architecture.

A "module" is a self-contained domain (e.g. listings, filings, analytics) that a
team member can add without touching shared code. Each module package under
``modules/`` exposes a single ``MODULE = ModuleSpec(...)`` object describing:

  * an optional FastAPI ``router``           -> mounted on the REST API
  * an optional ``register_tools`` hook      -> registers MCP tools
  * an optional ``register_resources`` hook  -> registers MCP resources
  * an optional ``register_prompts`` hook    -> registers MCP prompts
  * an optional ``seed`` hook                -> inserts synthetic rows
  * an optional ``priority``                 -> seed/order control (lower first)

The app, the MCP server and the seeder all iterate ``discover_modules()``,
so dropping a new package in ``modules/`` is enough to wire it everywhere.

See modules/README.md for the step-by-step "add a module" guide.
"""

from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # avoid hard imports so this stays dependency-light
    from fastapi import APIRouter
    from mcp.server import MCPServer
    from sqlalchemy.orm import Session

# Every MCP registration hook has the same shape: it receives the server and
# attaches things to it. Tools no longer receive an HTTP client -- they reach
# data through ``core.data``, in-process (decision D-2).
RegisterHook = Callable[["MCPServer"], None]


@dataclass
class ModuleSpec:
    """Declarative description of a domain module."""

    name: str
    description: str = ""
    router: APIRouter | None = None
    register_tools: RegisterHook | None = None
    register_resources: RegisterHook | None = None
    register_prompts: RegisterHook | None = None
    seed: Callable[[Session], None] | None = None
    # Lower runs first (controls router order + seed dependencies).
    priority: int = 100
    tags: list[str] = field(default_factory=list)


def discover_modules() -> list[ModuleSpec]:
    """Import every package under ``modules/`` and collect its ModuleSpec.

    Discovery is automatic: a package is included as soon as it defines a
    top-level ``MODULE`` attribute. Results are sorted by ``priority``, then by
    name so the ordering is fully deterministic even when priorities collide --
    ``tools/list`` ordering depends on it (SPECS MCP-4.2).
    """
    import modules  # local import to avoid cycles at startup

    specs: list[ModuleSpec] = []
    for info in pkgutil.iter_modules(modules.__path__):
        if not info.ispkg:
            continue
        pkg = importlib.import_module(f"modules.{info.name}")
        spec = getattr(pkg, "MODULE", None)
        if isinstance(spec, ModuleSpec):
            specs.append(spec)
    specs.sort(key=lambda s: (s.priority, s.name))
    return specs


def register_all(mcp: MCPServer) -> dict[str, int]:
    """Run every module's MCP registration hooks against ``mcp``.

    Returns a count per capability so the caller can log what was wired.
    """
    counts = {"tools": 0, "resources": 0, "prompts": 0}
    for spec in discover_modules():
        if spec.register_tools is not None:
            spec.register_tools(mcp)
            counts["tools"] += 1
        if spec.register_resources is not None:
            spec.register_resources(mcp)
            counts["resources"] += 1
        if spec.register_prompts is not None:
            spec.register_prompts(mcp)
            counts["prompts"] += 1
    return counts
