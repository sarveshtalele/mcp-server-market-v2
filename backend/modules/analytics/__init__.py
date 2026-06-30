"""Analytics module — calculation tools over the listings + filings APIs.

No database table and no router: just MCP tools. Demonstrates a tool-only module.
"""
from __future__ import annotations

from modules.analytics.tools import register_tools
from core.registry import ModuleSpec

MODULE = ModuleSpec(
    name="analytics",
    description="Financial-ratio, growth, comparison and ranking calculations.",
    register_tools=register_tools,
    priority=30,
    tags=["analytics"],
)
