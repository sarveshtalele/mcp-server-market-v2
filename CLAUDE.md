# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Backend (run from `backend/`, venv at `backend/.venv`):
```
.venv/Scripts/python -m pytest tests/                                  # run all tests
.venv/Scripts/python -m pytest tests/test_calculations.py::test_name   # single test
python -m core.seed                 # create tables + seed if empty
python -m core.seed --reset          # drop everything and reseed (deterministic Faker data)
uvicorn data_api.main:app --port 8000       # Data API (FastAPI, REST)
uvicorn agui_agent.main:app --port 8001     # AG-UI agent (web chatbot backend)
python -m mcp_server.server                 # MCP server directly, stdio (only used by agentgateway now)
```
No lint/format tooling is configured for the backend (no ruff/black/mypy config present).

agentgateway (`backend/mcp_server/gateway/`):
```
setup.ps1   # one-time: downloads agentgateway-windows-amd64.exe into bin/ (gitignored, 86MB)
run.ps1     # starts it against config.yaml
```

Frontend (run from `frontend/`):
```
npm run dev       # dev server on :3000
npm run build
npm run lint
```

`run_all.bat` (repo root) starts the whole stack — Data API, agentgateway, AG-UI agent, frontend — each in its own window, in the right order with a readiness poll between steps (not a blind sleep).

## Architecture

Services are independently runnable and wired by plain HTTP, in this order:

```
frontend :3000 --> agui_agent :8001 --> agentgateway :3111 --> mcp_server (stdio subprocess) --> data_api :8000 --> SQLite
```

**Module registry pattern** (`core/registry.py`) is the core extensibility mechanism. A "module" under `backend/modules/` (currently `listings`, `filings`, `analytics`) exposes one `MODULE = ModuleSpec(...)` with an optional FastAPI `router`, an optional `register_tools` hook, and an optional `seed` hook. `discover_modules()` auto-imports every module package; both `data_api/main.py` and `mcp_server/server.py` iterate the discovered specs to mount routers / register MCP tools. Adding a new module directory wires it into both the REST API and the MCP tool surface — no other file needs editing.

Tools get declared in a module's `tools.py` one of two ways: declarative `EndpointTool` records (`core/api_tools.py`) that proxy 1:1 to a Data API endpoint (used by `listings`/`filings`), or hand-written `@mcp.tool()` async functions for compute-only tools with no backing table (`analytics` — ratios, growth, comparisons, sector ranking; these call the Data API themselves via the shared `DataAPIClient`).

**agentgateway is the only thing that spawns the MCP server.** Nothing else launches `python -m mcp_server.server` directly — not Claude Code, Claude Desktop, VS Code Copilot, Antigravity, nor this project's own AG-UI agent. `backend/mcp_client/session.py` (used by both the AG-UI agent and the CLI chatbot) connects via Streamable HTTP to the gateway at `settings.mcp_gateway_url` (default `http://127.0.0.1:3111/mcp`). The gateway's `backend/mcp_server/gateway/config.yaml` is the actual spawn point (`mcp.targets[].stdio`), plus a tool-name allowlist (`policies.mcpAuthorization` — edit this file to add/remove callable tools, not the Python server) and per-call audit logging built in (no custom logging code needed for that).

Two things about the gateway that aren't obvious from its docs, confirmed by testing rather than assumed:
- It's HTTP/SSE-only — it cannot be spawned as a stdio child process the way `python.exe` was. Claude Desktop's and Antigravity's config formats also don't accept a plain `type: http` entry, so those two connect through the `mcp-remote` npm bridge instead (see `claude_desktop_config.example.json` / `integrations/antigravity.mcp.example.json`); Claude Code and VS Code Copilot use `type: http` directly (`.mcp.json`, `.vscode/mcp.json`).
- `mcp_client/session.py`'s `connect()` does a raw TCP probe loop (`_wait_for_port`) before attempting the real MCP handshake, rather than retrying the handshake itself on failure — the Streamable HTTP client's anyio task group doesn't tolerate being retried after a failed connect (its cancel-scope teardown assumes one connect attempt only), so retrying at that layer turns a clean "not up yet" into an uglier crash on cleanup.
- Its own web UI (`http://localhost:15000/ui`) has no log viewer or logs API of any kind (confirmed by probing, not assumed) — `GET http://localhost:8000/gateway-logs` (added to `data_api/main.py`) tails the gateway's audit log + the wrapped Python server's stderr instead. The UI's left-nav **"MCP"** section is also a trap: it's a wizard that creates a brand-new listener/target rather than editing the existing one — our real target was hand-written as config and shows up under Traffic → Listeners instead; clicking through the MCP wizard once already created a stray second target on a dead port that had to be cleaned out of `config.yaml`.

**Logging convention** (`core/logging_config.py`): everything goes to stderr only, never stdout. The MCP server's stdout is the JSON-RPC channel when it's run directly over stdio, so any stray print/log line there corrupts the protocol for whatever's talking to it. This is also why the gateway's own helper scripts (`run.ps1`, `setup.ps1`) must stay plain ASCII — Windows PowerShell 5.1 reads `.ps1` files in the system codepage without a UTF-8 BOM, and a stray non-ASCII character (an em dash, once) can break the parser outright, not just print garbled text.

**Data is synthetic**, generated by `Faker` with a fixed seed (`core/seed.py`, `SEED = 2025`) — not real market data, disclosed as such in the seed files. `shares_outstanding` is seeded from a realistic per-company range (`modules/listings/seed.py`'s `shares_band`), not one flat range applied to every symbol — market cap is price × shares, and a flat range makes cross-company market-cap comparisons meaningless regardless of how realistic the price bands look.

**Frontend chat** (`frontend/components/chat/`) tracks two independent kinds of timing — don't conflate them when extending either: client-measured per-tool-call `ms` (from AG-UI `TOOL_CALL_START`/`RESULT` event timestamps, computed in `AppShell.tsx`), and backend-measured end-to-end response time + LLM token usage (a `CUSTOM` AG-UI event emitted once per run from `agui_agent/agent.py`, surfaced as `Msg.usage`).

The MCP server ships a server-level `instructions` string (`mcp_server/server.py`) telling any connected client to answer only from tool data, not pretrained knowledge, and to say so explicitly rather than guess if a tool call fails. This is advisory only — MCP has no mechanism to enforce it on a client you don't control — the AG-UI agent's own `SYSTEM_PROMPT` (`agui_agent/agent.py`) is the one place this is actually enforced in code.
