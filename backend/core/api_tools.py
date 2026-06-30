"""Declarative API-endpoint -> MCP-tool binding.

Instead of hand-writing a function per tool, a module lists its endpoints as
``EndpointTool`` specs. ``register_endpoint_tools`` turns each spec into an MCP
tool that calls exactly one Data API endpoint. This makes the
"one MCP tool per API endpoint" mapping explicit and removes boilerplate.

Everything still goes through the single Data API base URL (one port); the spec
only carries the **path** (e.g. ``/listings/companies/{symbol}``).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from mcp.server.fastmcp import FastMCP

from mcp_server.api_client import DataAPIClient, DataAPIError


@dataclass
class EndpointTool:
    """Binds one MCP tool name to one Data API endpoint."""

    name: str
    description: str
    path: str  # may contain {placeholders} that match path_params
    path_params: list[str] = field(default_factory=list)  # required, str
    query_params: list[str] = field(default_factory=list)  # optional, str|None


def _build(spec: EndpointTool, api: DataAPIClient):
    """Create a properly-typed async function for FastMCP from a spec.

    We generate real source so FastMCP can infer the parameter schema (it reads
    the function signature). The function calls a single endpoint.
    """
    params = [f"{p}: str" for p in spec.path_params]
    params += [f"{q}: str | None = None" for q in spec.query_params]
    sig = ", ".join(params)

    if spec.query_params:
        qbuild = "{" + ", ".join(f"{q!r}: {q}" for q in spec.query_params) + "}"
    else:
        qbuild = "None"

    src = (
        f"async def {spec.name}({sig}):\n"
        f"    try:\n"
        f"        return await _api.get(f{spec.path!r}, {qbuild})\n"
        f"    except _DataAPIError as e:\n"
        f"        return {{'error': str(e)}}\n"
    )
    ns: dict = {"_api": api, "_DataAPIError": DataAPIError}
    exec(src, ns)  # noqa: S102 - controlled, module-authored template
    fn = ns[spec.name]
    fn.__doc__ = spec.description
    return fn


def register_endpoint_tools(
    mcp: FastMCP, api: DataAPIClient, specs: list[EndpointTool]
) -> None:
    """Register every endpoint spec as an MCP tool."""
    for spec in specs:
        fn = _build(spec, api)
        mcp.tool(name=spec.name, description=spec.description)(fn)
