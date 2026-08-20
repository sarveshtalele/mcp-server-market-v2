# Adding a module

A **module** is a self-contained domain under `backend/modules/`. Dropping a package here wires it
into REST, MCP and the seeder with **no other file edited**. `tests/test_registry.py` enforces that
by creating a module at test time and asserting it appears — if you ever have to touch a shared file
to add one, that is a bug in `core/registry.py`, not in your module.

## The contract

Your package exports exactly one `MODULE`:

```python
from core.registry import ModuleSpec

MODULE = ModuleSpec(
    name="widgets",
    description="What this domain is.",
    router=router,                        # optional: FastAPI APIRouter
    register_tools=register_tools,        # optional: (MCPServer) -> None
    register_resources=register_resources, # optional: (MCPServer) -> None
    register_prompts=register_prompts,     # optional: (MCPServer) -> None
    seed=seed,                            # optional: (Session) -> None
    priority=40,                          # lower runs first
)
```

Every field except `name` is optional. `analytics` has no table and no router; `observability` has
only a router. `priority` controls seed order (listings before filings) and, together with the
module name, the order tools appear in `tools/list` — which must stay deterministic so clients can
cache it.

## The five-minute path

1. `mkdir backend/modules/widgets`
2. `models.py` (SQLAlchemy, inherit `core.database.Base`), `schemas.py` (Pydantic),
   `repository.py` (all queries), `router.py` (FastAPI), `seed.py`, `tools.py`
3. `__init__.py` importing `models` (so tables register) and exporting `MODULE`
4. `python scripts/dev.py seed`
5. Add a test asserting the tool's shape

## Declaring tools

**Data proxy** — a typed function over `core.data`, plus a `DataTool` row:

```python
from core.api_tools import DataTool, register_data_tools

def get_widget(widget_id: str) -> dict:
    """Get one widget by id."""
    return data.get_widget(widget_id)

TOOLS = [DataTool(name="get_widget", description="Get one widget by id.", fn=get_widget)]

def register_tools(mcp):
    register_data_tools(mcp, TOOLS)
```

`register_data_tools` wraps each function so a `DataError` comes back as `{"error": ...}` — a missing
record is an ordinary answer, not a protocol failure.

**Computation** — a plain `@mcp.tool()` function, with the maths as a pure function in
`core/calculations.py` so it can be unit-tested without a database.

## Things that will bite you

- **Sync vs async.** A plain `def` tool runs on a worker thread, so blocking SQLAlchemy never
  occupies the event loop. Make it `async` only when it must await something (progress reporting,
  concurrent fan-out).
- **Return annotations are enforced.** The SDK derives an output schema from them and validates
  against it. A tool that can return `{"error": ...}` must be annotated `list[dict] | dict`, not
  `list[dict]`, or the error path fails schema validation.
- **No `exec`, no stdout.** Both are asserted by tests.
- **Allowlist the tool.** A new tool is not callable through the gateway until it is added to
  `backend/mcp_server/gateway/config.yaml`. The MCP Servers page flags the mismatch.
- **Give it a card.** Add a `TOOL_LABEL` entry and, if it should render richly, a case in
  `frontend/components/chat/toolCards.tsx`.
