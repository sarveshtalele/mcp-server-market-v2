"""Analytics module — calculation tools and prompt workflows.

No database table and no router: just MCP tools and prompts. Demonstrates a
capability-only module.
"""

from __future__ import annotations

from core.registry import ModuleSpec
from modules.analytics.prompts import register_prompts
from modules.analytics.tools import register_tools

MODULE = ModuleSpec(
    name="analytics",
    description="Financial-ratio, growth, comparison and ranking calculations.",
    register_tools=register_tools,
    register_prompts=register_prompts,
    priority=30,
    tags=["analytics"],
)
