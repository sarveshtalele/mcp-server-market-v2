"""Listings module — company master data (the `companies` table)."""

from __future__ import annotations

# Importing models ensures they register on Base.metadata for create_all().
from core.registry import ModuleSpec
from modules.listings import models  # noqa: F401
from modules.listings.resources import register_resources
from modules.listings.router import router
from modules.listings.seed import seed
from modules.listings.tools import register_tools

MODULE = ModuleSpec(
    name="listings",
    description="Company listings and sectors.",
    router=router,
    register_tools=register_tools,
    register_resources=register_resources,
    seed=seed,
    priority=10,  # seed companies before filings
    tags=["listings"],
)
