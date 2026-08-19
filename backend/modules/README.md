# Adding a module

The backend is **pluggable**. A *module* is a self-contained domain that a team
member owns. Drop a package under `backend/modules/<name>/`, define one
`MODULE = ModuleSpec(...)`, and it is auto-wired into:

- the **Data API** (its router is mounted),
- the **MCP server** (its tools are registered),
- the **seeder** (its `seed` hook runs).

No edits to shared files. Discovery is automatic (`core/registry.py`).

## Anatomy of a module

```
modules/<name>/
├── __init__.py      # defines MODULE = ModuleSpec(...)   <-- the only required file
├── models.py        # SQLAlchemy ORM models (if you own a table)
├── schemas.py       # Pydantic response models
├── repository.py    # DB queries (no HTTP, no business logic leakage)
├── router.py        # FastAPI APIRouter  -> your REST API
├── tools.py         # register_tools(mcp, api) -> your MCP tools
└── seed.py          # seed(db) -> synthetic rows
```

A module can be **data-backed** (own a table + router, e.g. `listings`,
`filings`) or **tool-only** (no table, just tools over existing APIs, e.g.
`analytics`). Use only the pieces you need.

## ModuleSpec

```python
from core.registry import ModuleSpec

MODULE = ModuleSpec(
    name="dividends",
    description="Dividend history per company.",
    router=router,                  # optional: FastAPI APIRouter
    register_tools=register_tools,  # optional: (mcp, api) -> None
    seed=seed,                      # optional: (db) -> None
    priority=40,                    # lower runs first (seed ordering / mounting)
    tags=["dividends"],
)
```

## Step-by-step: add a `dividends` module

### 1. Connect your database (ORM model)
```python
# modules/dividends/models.py
from sqlalchemy import Date, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from core.database import Base

class Dividend(Base):
    __tablename__ = "dividends"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(ForeignKey("companies.symbol"), index=True)
    pay_date: Mapped["date"] = mapped_column(Date)
    amount_per_share: Mapped[float] = mapped_column(Float)
```
> Your table lives in the same SQLite DB. To connect an **external** database
> instead, give your repository its own engine/session — the rest is unchanged.

### 2. Expose it as an API (router)
```python
# modules/dividends/router.py
from fastapi import APIRouter, Depends
from core.database import get_db
router = APIRouter(prefix="/dividends", tags=["dividends"])

@router.get("/{symbol}")
def get_dividends(symbol: str, db=Depends(get_db)):
    ...  # query via your repository, return schema
```

### 3. Add a tool — bind it to your API endpoint (declarative)
Each MCP tool maps 1:1 to one Data API endpoint. Just list the binding; the
function body is generated for you (one tool per endpoint):
```python
# modules/dividends/tools.py
from core.api_tools import EndpointTool, register_endpoint_tools
from mcp_server.api_client import DataAPIClient
from mcp.server.fastmcp import FastMCP

ENDPOINTS = [
    EndpointTool(
        name="get_dividends",
        description="Dividend history for a company.",
        path="/dividends/{symbol}",     # {symbol} fills from path_params
        path_params=["symbol"],
        query_params=["year"],          # optional query args (str|None)
    ),
]

def register_tools(mcp: FastMCP, api: DataAPIClient) -> None:
    register_endpoint_tools(mcp, api, ENDPOINTS)
```
> Need a tool that composes several endpoints or does maths (not a pure proxy)?
> Write it by hand instead — see `modules/analytics/tools.py`, which fetches from
> `/listings` + `/filings` and calls `core/calculations.py`.

### 4. Register it
```python
# modules/dividends/__init__.py
from modules.dividends import models            # noqa: F401 (register table)
from modules.dividends.router import router
from modules.dividends.tools import register_tools
from core.registry import ModuleSpec

MODULE = ModuleSpec(
    name="dividends", description="Dividend history.",
    router=router, register_tools=register_tools, priority=40,
)
```

### 5. Allow the new tool through agentgateway (required)
Every consumer reaches the MCP server **through agentgateway**, which enforces a
tool-name allowlist. A tool that isn't on the list is hidden from `tools/list`
and rejected on call — so a brand-new tool won't be callable until you add it.
Add one rule per tool name in `backend/mcp_server/gateway/config.yaml` under
`policies.mcpAuthorization.rules`:
```yaml
policies:
  mcpAuthorization:
    rules:
      - 'mcp.tool.name == "get_company"'
      # ... existing rules ...
      - 'mcp.tool.name == "get_dividends"'   # <-- your new tool
```
Restart the gateway (`backend/mcp_server/gateway/run.ps1`) to pick it up.

### 6. (optional) seed + run
```bash
python -m core.seed --reset      # picks up your seed() automatically
uvicorn data_api.main:app --port 8000
# then start agentgateway (backend/mcp_server/gateway/run.ps1) — clients reach the
# MCP server through it, not by spawning the Python server directly.
```
Your endpoint is live at `/dividends/...`, and your tool appears in the MCP
server (and therefore in every consumer through the gateway) once whitelisted.

## Rendering a tool as a card (frontend, optional)
Map the tool name to a card in `frontend/components/chat/toolCards.tsx`
(`renderToolCard` switch) and add a component under `frontend/components/cards/`.
See the existing `get_company` / `compare_companies` cases as templates. Friendly
tool labels for the chips/activity panel live in the same file (`TOOL_LABEL`).

## Rules of thumb
- Tools fetch via the **HTTP API**, never the DB directly (keeps the boundary real).
- Pure math goes in `core/calculations.py` so every module can reuse it.
- Pick a unique `priority` if your `seed` depends on another module's data
  (e.g. filings = 20 because it needs listings = 10).
