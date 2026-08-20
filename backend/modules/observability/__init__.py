"""Observability module — the centralized audit log every consumer lands in.

A router-only module: no MCP tools, no synthetic seed data. It follows the same
``ModuleSpec`` contract as every domain module, so it is wired in by dropping the
directory here — the registry contract holds even for infrastructure.
"""

from __future__ import annotations

from core.registry import ModuleSpec
from modules.observability import models  # noqa: F401 (register on ObsBase metadata)
from modules.observability.router import router

MODULE = ModuleSpec(
    name="observability",
    description="Cross-host MCP call audit log and query API.",
    router=router,
    priority=90,  # mounted after the domain modules
    tags=["observability"],
)
