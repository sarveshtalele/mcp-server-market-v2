"""Module registry — the heart of the pluggable architecture.

A "module" is a self-contained domain (e.g. listings, filings, analytics) that a
team member can add without touching shared code. Each module package under
``modules/`` exposes a single ``MODULE = ModuleSpec(...)`` object describing:

  * an optional FastAPI ``router``        -> mounted on the Data API
  * an optional ``register_tools`` hook   -> registers MCP tools
  * an optional ``seed`` hook             -> inserts synthetic rows
  * an optional ``priority``              -> seed/order control (lower first)

The Data API, the MCP server and the seeder all iterate ``discover_modules()``,
so dropping a new package in ``modules/`` is enough to wire it everywhere.

See modules/README.md for the step-by-step "add a module" guide.
"""
from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # avoid hard imports so this stays dependency-light
    from fastapi import APIRouter
    from mcp.server.fastmcp import FastMCP
    from sqlalchemy.orm import Session


@dataclass
class ModuleSpec:
    """Declarative description of a domain module."""

    name: str
    description: str = ""
    router: "APIRouter | None" = None
    register_tools: "Callable[[FastMCP, Any], None] | None" = None
    seed: "Callable[[Session], None] | None" = None
    # Lower runs first (controls router order + seed dependencies).
    priority: int = 100
    tags: list[str] = field(default_factory=list)


def discover_modules() -> list[ModuleSpec]:
    """Import every package under ``modules/`` and collect its ModuleSpec.

    Discovery is automatic: a package is included as soon as it defines a
    top-level ``MODULE`` attribute. Results are sorted by ``priority``.
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
    specs.sort(key=lambda s: s.priority)
    return specs
