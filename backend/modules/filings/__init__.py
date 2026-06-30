"""Filings module — periodic financial filings (the `filings` table)."""
from __future__ import annotations

from modules.filings import models  # noqa: F401 (register on Base.metadata)
from modules.filings.router import router
from modules.filings.seed import seed
from modules.filings.tools import register_tools
from core.registry import ModuleSpec

MODULE = ModuleSpec(
    name="filings",
    description="Quarterly and annual financial filings.",
    router=router,
    register_tools=register_tools,
    seed=seed,
    priority=20,  # after listings
    tags=["filings"],
)
