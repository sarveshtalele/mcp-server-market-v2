"""Declarative data-tool binding.

A module lists its data tools as ``DataTool`` specs -- a name, a description and
a plain typed function from ``core.data``. ``register_data_tools`` wraps each one
with uniform error handling and registers it on the MCP server.

Two properties matter here:

* **No dynamic code.** The previous implementation generated Python source and
  ran it through ``exec()`` so the schema could be inferred from a synthesised
  signature. The functions are now real, typed and importable; the SDK derives
  the JSON Schema from their annotations. ``tests/test_no_exec.py`` enforces it.
* **Sync on purpose.** These functions do blocking SQLAlchemy work. Declared as
  plain ``def``, the SDK runs them on a worker thread, keeping the event loop
  free. Async tools (see ``modules/analytics``) are for concurrent fan-out.
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from core.errors import DataError

if TYPE_CHECKING:
    from mcp.server import MCPServer


@dataclass(frozen=True)
class DataTool:
    """Binds one MCP tool name to one typed data function."""

    name: str
    description: str
    fn: Callable[..., Any]


def with_data_errors(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Turn a ``DataError`` into a normal ``{"error": ...}`` tool result.

    A missing ticker is an ordinary answer ("no such company"), not a protocol
    failure, so it must not surface as a JSON-RPC error.
    """

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except DataError as exc:
            return {"error": str(exc)}

    return wrapper


def register_data_tools(mcp: MCPServer, specs: list[DataTool]) -> None:
    """Register every spec as an MCP tool, in the order given."""
    for spec in specs:
        handler = with_data_errors(spec.fn)
        handler.__name__ = spec.name
        handler.__doc__ = spec.description
        mcp.tool(name=spec.name, description=spec.description)(handler)
