"""Listings module — company master data (the `companies` table)."""
from __future__ import annotations

# Importing models ensures they register on Base.metadata for create_all().
from modules.listings import models  # noqa: F401
from modules.listings.router import router
from modules.listings.seed import seed
from modules.listings.tools import register_tools
from core.registry import ModuleSpec

MODULE = ModuleSpec(
    name="listings",
    description="SET/mai company listings and sectors.",
    router=router,
    register_tools=register_tools,
    seed=seed,
    priority=10,  # seed companies before filings
    tags=["listings"],
)
