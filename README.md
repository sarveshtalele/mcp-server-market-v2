# Stock Exchange — MCP + AG-UI PoC

End-to-end proof of concept: synthetic **stock-exchange** market data, served by a
FastAPI **Data API**, exposed to LLMs through an **MCP server**, and consumed by
two chatbots — a terminal client and a streaming **AG-UI** web app (custom
Claude-style UI with live tool-call chips, generative cards, and per-response
timing/token-usage). The same MCP server also plugs into **Claude Code**,
**Claude Desktop**, **VS Code Copilot**, and **Antigravity** — every consumer,
including the two chatbots, connects through **[agentgateway](https://github.com/agentgateway/agentgateway)**,
which enforces a tool-name allowlist and keeps one shared audit log of every
call, instead of each consumer talking to the MCP server directly.

> ⚠️ All financial figures are **synthetic** (deterministically generated). Ticker
> symbols and sectors are real ticker names for realism only — this is not market data.

![Architecture](architecture.png)

---

## Architecture

```
                       ┌────────────────────────────────┐
                       │  SQLite (stock_market.db)       │
                       │  companies · filings (ORM)      │
                       └────────────────┬─────────────────┘
                                        │ SQLAlchemy
                       ┌────────────────▼─────────────────┐
                       │  Data API — FastAPI :8000         │
                       │  /listings  ·  /filings           │
                       └────────────────▲─────────────────┘
                                        │ HTTP (httpx)
                       ┌────────────────┴─────────────────┐
                       │  MCP Server (FastMCP, stdio)      │
                       │  fetch tools + calc tools         │
                       └────────────────▲─────────────────┘
                                 stdio  │  (spawned ONLY by the gateway below —
                                        │   nothing else launches this process)
                       ┌────────────────┴─────────────────┐
                       │  agentgateway :3111                │
                       │  tool-name allowlist + audit log   │
                       │  (config: mcp_server/gateway/*.yaml)│
                       └──────────────┬──────┬─────────────┘
                        http (direct) │      │ stdio (mcp-remote npx bridge)
              ┌────────────────────────▼┐  ┌──▼──────────────────────┐
              │ Claude Code · VS Code    │  │ Claude Desktop ·         │
              │ Copilot · AG-UI agent    │  │ Antigravity              │
              │ (:8001) · CLI chatbot    │  │ (config can't use http)  │
              └────────────┬─────────────┘  └──────────────────────────┘
                           │ AG-UI over HTTP/SSE (browser fetch — AG-UI agent only)
                ┌──────────▼──────────────────────┐
                │ Next.js custom chat   :3000       │
                │ streamed text + tool chips/cards   │
                │ + response time / token usage      │
                └─────────────────────────────────┘
```

**Key design choices**

- The MCP server reaches data **only over the HTTP API** — the API boundary is real.
- All maths lives in `core/calculations.py` (pure functions), reused everywhere.
- **agentgateway is the only thing that spawns the MCP server.** Every consumer
  — Claude Code, Claude Desktop, VS Code Copilot, Antigravity, this project's own
  AG-UI agent, and the terminal chatbot (`mcp_client.cli_chat`, same
  `MCPToolClient` class as the AG-UI agent) — reaches it through the gateway
  instead of launching `python -m mcp_server.server` themselves. One shared
  tool-name allowlist and audit log instead of a separate, ungoverned entry point
  per consumer. See "agentgateway" below for the why/how in full.
- The AG-UI agent *is* an MCP client (`backend/mcp_client/session.py`, connects to
  the gateway over Streamable HTTP), wrapped as an AG-UI event stream. The browser
  consumes that stream directly and renders streaming text **and** tool calls as
  live chips + cards (no chat framework — see `frontend/lib/agui.ts`).

---

## Repository layout

```
MCP-SERVER/
├── backend/
│   ├── core/            config · database · registry · calculations · seed (framework)
│   ├── modules/         PLUGGABLE DOMAINS — each is self-contained
│   │   ├── README.md        how to add a module
│   │   ├── listings/        companies table + /listings + 3 tools + seed
│   │   ├── filings/         filings table + /filings + 2 tools + seed
│   │   └── analytics/       tool-only: 4 calculation tools (no table)
│   ├── data_api/        FastAPI app — auto-mounts every module router; also serves /gateway-logs
│   ├── mcp_server/      FastMCP server — auto-registers every module's tools
│   │   └── gateway/         agentgateway config.yaml + setup.ps1/run.ps1 (governance + audit log)
│   ├── mcp_client/      reusable MCP session (connects via the gateway) + terminal chatbot
│   ├── agui_agent/      AG-UI streaming agent (FastAPI :8001)
│   ├── requirements.txt
│   └── .env.example
│   └── tests/           pytest for the pure calculations
├── frontend/            Next.js custom AG-UI chat (streaming + generative cards)
├── run_all.bat          one launcher: Data API + agentgateway + AG-UI agent + frontend
├── .mcp.json            Claude Code MCP config (→ agentgateway)
├── .vscode/mcp.json     VS Code Copilot MCP config (→ agentgateway)
├── claude_desktop_config.example.json    Claude Desktop config (→ agentgateway, via mcp-remote)
├── integrations/antigravity.mcp.example.json    Antigravity config (→ agentgateway, via mcp-remote)
├── CLAUDE.md            guidance for Claude Code sessions working in this repo
├── EXPLANATION.md       full per-file walkthrough + architecture deep dive
└── REVIEW.md            code review & gap analysis
```

### Modular architecture (add features without touching shared code)

A **module** under `backend/modules/<name>/` declares one `MODULE = ModuleSpec(...)`
and is auto-discovered (`core/registry.py`). It can contribute any of:
a **database table** (ORM), a **REST router**, **MCP tools**, and a **seed** hook.
The Data API, the MCP server and the seeder all iterate the registry — so a new
teammate drops a package in `modules/` and it appears everywhere, no edits to
`data_api`, `mcp_server`, or `core`. Full guide: [`backend/modules/README.md`](backend/modules/README.md).

---

## Prerequisites

- Python 3.11+ (tested on 3.14)
- Node.js 18+ (for the web frontend only)
- An **OpenAI-compatible LLM gateway** — `LLM_API_KEY` + `LLM_BASE_URL` (e.g. a
  LiteLLM proxy). Needed for the two chatbots only; the Data API and the
  MCP-in-Claude integration need **no** LLM key.

> The chatbots speak the **OpenAI Chat Completions** API to `LLM_BASE_URL/v1`.
> Env vars use an `LLM_` prefix on purpose, to avoid colliding with any
> `ANTHROPIC_*` variables already set in your OS environment.

---

## Forked or just cloned? Read this first

These are **gitignored** (not in the repo) — you generate them locally:

| Missing after clone | Create it with |
|---|---|
| `backend/.venv` | `uv venv .venv` (step 1) |
| `frontend/node_modules` | `npm install` (step 1) |
| `backend/stock_market.db` | `python -m core.seed --reset` (step 1) |
| `backend/.env` | `copy .env.example .env` + add your keys |
| `frontend/.env.local` | `copy .env.local.example .env.local` |
| `backend/mcp_server/gateway/bin/agentgateway.exe` | `backend\mcp_server\gateway\setup.ps1` |

**Two things you MUST change for your machine:**

1. **LLM gateway** in `backend/.env` (web chat + CLI need it; the Data API and
   MCP-in-Claude do **not**):
   ```
   LLM_API_KEY=...            # your key
   LLM_BASE_URL=https://...   # your OpenAI-compatible proxy (e.g. LiteLLM)
   LLM_MODEL=...              # a model your proxy serves (GET /v1/models to list)
   ```
2. **Absolute paths**: `.mcp.json`, `claude_desktop_config.example.json`, and the
   other host configs point at `http://127.0.0.1:3111` (agentgateway) — no
   per-machine path to edit there anymore. The one place a path still matters is
   `backend/mcp_server/gateway/config.yaml`'s `cmd`/`env` — point those at
   **your** clone's `…\backend\.venv\Scripts\python.exe` if you didn't clone to
   the same path as the original author's machine.

Then follow the steps below.

---

## 1. One-time setup

**Backend** (from repo root) — uses `uv` (or swap for `python -m venv` + `pip`):

```powershell
cd backend
uv venv .venv
uv pip install -r requirements.txt
copy .env.example .env          # then edit: LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
python -m core.seed --reset     # build + seed SQLite
cd ..
```

**agentgateway** (one-time — downloads the ~86MB binary, gitignored, not committed):

```powershell
backend\mcp_server\gateway\setup.ps1
```

**Frontend** (one-time):

```powershell
cd frontend
copy .env.local.example .env.local
npm install
cd ..
```

## 2. Run the whole project

```powershell
run_all.bat
```
Opens four windows — **Data API :8000**, **agentgateway :3111** (waits for it to
be ready before continuing), **AG-UI agent :8001**, **frontend :3000** — then
browse to **http://localhost:3000**. Ask *"Compare JPM, BAC and WFC"* and watch
the tool chips spin, cards drop in, and the answer stream.

### Run pieces manually (equivalent commands)

```powershell
# Backend — Data API (Swagger at http://127.0.0.1:8000/docs)
cd backend; .venv\Scripts\python.exe -m uvicorn data_api.main:app --port 8000

# agentgateway (must be running before the two below - they connect to it)
backend\mcp_server\gateway\run.ps1

# Backend — AG-UI agent (needs LLM_API_KEY + LLM_BASE_URL in backend\.env)
cd backend; .venv\Scripts\python.exe -m uvicorn agui_agent.main:app --port 8001

# Frontend
cd frontend; npm run dev          # -> http://localhost:3000

# Terminal chatbot (alternative to the web UI; connects through agentgateway,
# same as everything else - does NOT spawn the MCP server itself)
cd backend; .venv\Scripts\python.exe -m mcp_client.cli_chat

# Tests
cd backend; .venv\Scripts\python.exe -m pytest tests/
```

---

## 3. Add the MCP server to your AI host (copy-paste)

One MCP server, four hosts. **None need an LLM key** — the host supplies the model.
Every host connects through **agentgateway** (governance allowlist + audit log
in front of the MCP server — see "agentgateway" below), not by spawning the
Python server directly.

> **Before you start (all hosts):** run, in order:
> 1. **Data API** on :8000 (`run_all.bat`, or `uvicorn data_api.main:app --port 8000`)
> 2. **agentgateway** on :3111 — one-time: `backend/mcp_server/gateway/setup.ps1`
>    (downloads the binary), then `backend/mcp_server/gateway/run.ps1` (or just
>    use `run_all.bat`, which starts both automatically)

### 🟣 Claude Code
Put this in **`.mcp.json`** at the repo root (already committed), then run
`claude` from the repo folder and approve `stock-exchange`.

```json
{
  "mcpServers": {
    "stock-exchange": {
      "type": "http",
      "url": "http://127.0.0.1:3111/mcp"
    }
  }
}
```

### 🟠 Claude Desktop
Merge into **`%APPDATA%\Claude\claude_desktop_config.json`** (Windows) or
**`~/Library/Application Support/Claude/claude_desktop_config.json`** (macOS), then
**fully quit and relaunch Claude Desktop** (a window close is not enough — it
only reloads this file on a full restart). Desktop's config file doesn't support
a plain remote `"type": "http"` entry, so this uses the
[`mcp-remote`](https://www.npmjs.com/package/mcp-remote) bridge (needs Node/npx
on PATH) to speak stdio to Desktop while proxying to the gateway over HTTP:

```json
{
  "mcpServers": {
    "stock-exchange": {
      "command": "npx",
      "args": ["mcp-remote", "http://127.0.0.1:3111/mcp"]
    }
  }
}
```

### 🔵 GitHub Copilot Chat (VS Code)
Put this in **`.vscode/mcp.json`** (already committed). Open the repo in VS Code →
**Copilot Chat → Agent** mode → click the tools icon → enable `stock-exchange`.
Note the key is `servers` (not `mcpServers`).

```json
{
  "servers": {
    "stock-exchange": {
      "type": "http",
      "url": "http://127.0.0.1:3111/mcp"
    }
  }
}
```

### 🟢 Antigravity
Open **Settings → MCP → Add server** (or edit Antigravity's `mcp_config.json`) and
paste this, then reload the MCP servers. Native remote/http MCP support isn't
confirmed for Antigravity, so this uses the same `mcp-remote` bridge as Desktop:

```json
{
  "mcpServers": {
    "stock-exchange": {
      "command": "npx",
      "args": ["mcp-remote", "http://127.0.0.1:3111/mcp"]
    }
  }
}
```

### After it's connected
Ask the host: *"Use stock-exchange: compare JPM, BAC and WFC by ROE"*. Nine tools
are available: `get_company`, `search_companies`, `list_sectors`, `get_filings`,
`get_latest_filing`, `calc_financial_ratios`, `calc_revenue_growth`,
`compare_companies`, `sector_ranking`.

| Host | File / location | Connects via | Notes |
|---|---|---|---|
| Claude Code | `.mcp.json` (repo root) | `type: http` → gateway | run `claude` in the repo |
| Claude Desktop | `%APPDATA%\Claude\claude_desktop_config.json` | `mcp-remote` bridge → gateway | full restart, not just window close |
| Copilot (VS Code) | `.vscode/mcp.json` | `type: http` → gateway | Agent mode |
| Antigravity | Settings → MCP / `mcp_config.json` | `mcp-remote` bridge → gateway | reload servers |

Ready-to-edit copies also live in the repo: [`.mcp.json`](.mcp.json),
[`.vscode/mcp.json`](.vscode/mcp.json),
[`claude_desktop_config.example.json`](claude_desktop_config.example.json),
[`integrations/antigravity.mcp.example.json`](integrations/antigravity.mcp.example.json).

---

## agentgateway (governance + audit logging)

**Why we added this**: before agentgateway, each of the five consumers (Claude
Code, Claude Desktop, VS Code Copilot, Antigravity, and this project's own web
chatbot) spawned `python -m mcp_server.server` directly and independently —
no shared way to see who called which tool, and no way to block a tool without
editing the Python server itself. Adding a proxy in front of the server, instead
of building this into the server, means one place to govern/audit *every*
consumer instead of duplicating that logic five times.

**How it works, in short**: [agentgateway](https://github.com/agentgateway/agentgateway)
(Rust, Apache-2.0, Linux Foundation) sits in front of `python -m
mcp_server.server` for **every** consumer — all four hosts above, and this
project's own web chatbot (`backend/agui_agent`, via
`backend/mcp_client/session.py`). It's the one place that now spawns the
Python server; nothing else does. Every consumer talks to the gateway over
HTTP; the gateway spawns the real Python server itself as its own stdio child
(config in `backend/mcp_server/gateway/config.yaml`), checks each tool call
against an allowlist, and logs it — all before the call ever reaches the
Python server.

```
Claude Code/Copilot  --http-->  agentgateway :3111  --stdio(spawns)-->  python -m mcp_server.server
Claude Desktop/Antigravity --stdio(mcp-remote bridge)-->  agentgateway :3111  --stdio(spawns)-->  same
Our web chatbot (agui_agent) --http-->  agentgateway :3111  --stdio(spawns)-->  same
```

**Setup** (one-time): `backend/mcp_server/gateway/setup.ps1` downloads
`agentgateway-windows-amd64.exe` into `backend/mcp_server/gateway/bin/` (86MB,
gitignored — not committed). **Run**: `backend/mcp_server/gateway/run.ps1`, or
just use `run_all.bat`, which starts it automatically alongside the Data API
and AG-UI agent.

**Config**: `backend/mcp_server/gateway/config.yaml` — the `mcp.targets[].stdio`
block wraps the same `python -m mcp_server.server` command/env every host used
to spawn directly; `policies.mcpAuthorization` is a CEL-based allowlist of tool
names (currently all 9, mirroring what's exposed today — tighten it by removing
rules for tools you want to block). This is **tool-name-level** governance only
— it can't filter by argument content (e.g. "only for Financials sector"); that
would need a separate check inside the tool functions themselves.

**Audit log**: every call appears in the gateway's own stdout (or wherever you
redirect it) as a structured line, no extra logging code needed:
```
... mcp.method.name=tools/call mcp.target=stock-exchange gen_ai.tool.name=get_company mcp.session.id=... duration=299ms
```
A denied tool (removed from the allowlist) disappears from `tools/list` and any
direct call to it gets a JSON-RPC error (`Unknown tool: <name>`) instead of
reaching the Python server.

**Browsing it**: agentgateway ships a UI at `http://localhost:15000/ui` for
inspecting/editing config (Listeners/Routes/Backends, with a live YAML preview)
and an "MCP Playground" for making test tool calls in-browser. Two things to
know going in:
- Its left-nav **"MCP"** section is a wizard that creates a *brand new*
  listener/target when you click through it — it's not "manage the existing
  server." Our `stock-exchange` target was hand-written directly as config, so
  it shows up under **Traffic → Listeners**, not under "MCP". Don't use the MCP
  wizard to "edit" it — that creates a second, unrelated target instead.
- **It has no log viewer** (confirmed — no such page, no API for it either).
  For that, use **`http://localhost:8000/gateway-logs`** instead (added to this
  project's Data API) — an auto-refreshing page tailing the gateway's audit log
  and the wrapped Python server's stderr, so you don't need a terminal window
  open to debug a tool call.

**Note on Claude Desktop/Antigravity**: their config files don't accept a plain
`"type": "http"` server entry, so those two go through the `mcp-remote` npm
bridge instead (a tiny stdio-to-HTTP relay) — verified separately that its own
logs go to stderr only, so it never corrupts the stdio JSON-RPC channel those
two hosts expect.

**CORS**: `policies.cors` in `config.yaml` only matters for *browser*-based
callers — the gateway's own Playground UI (`localhost:15000`) and this
project's own `/gateway-logs` page. Native clients (the Python `mcp` library,
Node's `mcp-remote`) never send CORS preflight requests at all, so this
setting has no effect on whether Claude Code/Desktop/Copilot/Antigravity can
connect — it's purely for testing/browsing from a web page.

**No cross-restart audit history**: this build of agentgateway has no
`database`/persistent-storage option — confirmed by testing, not assumed
(setting one in `config.yaml` fails config validation). The audit log
(`stdout.log` / `/gateway-logs`) only covers the *current* gateway process;
restarting it starts the trail over. If you need history that survives a
restart, redirect/append `stdout.log` externally rather than relying on the
gateway to do it.

**Gotcha we hit for real**: if a host that was working suddenly stops showing
up in the audit log, don't assume the gateway broke — check that host's own
config first. `claude_desktop_config.json` in particular can get reset back to
a direct `command: python.exe` stdio entry (e.g. if Desktop's own connector
UI touches it), silently routing that host straight to the Python server again
with zero governance/logging — same symptoms as a real bug (tools still work,
just invisible to the gateway) but the fix is re-adding the `mcp-remote` entry
above, not touching the gateway at all.

---

## Web UI features

The chatbot at `http://localhost:3000` is a custom 3-panel app:

- **Left rail** — **New chat** + saved conversations (persisted in `localStorage`,
  Claude-style) and one-click **Agents** (Valuation Analyst, Growth Scout, Sector
  Screener, Peer Comparator) that pre-fill a focused prompt.
- **Centre** — streaming answer with live **tool-call chips** and generative cards;
  each finished reply shows **end-to-end response time and token usage**
  (prompt/completion/total), backend-measured.
- **Right rail** — **Tool activity**: every tool call with its arguments, status
  and **execution time (ms)**, plus totals; the latest response's time/tokens
  are shown above it.

## Logging & debugging

All backend processes log to stderr via `core/logging_config.py`. Set the level in
`backend/.env`:
```
LOG_LEVEL=DEBUG      # DEBUG | INFO | WARNING | ERROR
```
`INFO` logs each API request (path, status, latency) and each tool call with its
duration; `DEBUG` adds tool arguments and MCP wire detail.

The AG-UI agent (`backend/agui_agent/agent.py`) additionally logs, per chat run:
- the incoming prompt (truncated to 300 chars)
- each LLM turn: latency, finish reason, response length/preview, tool-call count
- the full run: total response time and full assistant response length/preview

Example (`LOG_LEVEL=INFO`):
```
10:42:16 INFO [agent] run abc123 prompt: 'Compare JPM, BAC and WFC'
10:42:17 INFO [agent] llm turn -> 812.3 ms, finish=tool_calls, 0 char(s), 3 tool_call(s): ''
10:42:17 INFO [agent] tool compare_companies({...}) -> 1204 chars in 45.2 ms
10:42:19 INFO [agent] llm turn -> 1530.1 ms, finish=stop, 412 char(s), 0 tool_call(s): 'JPM leads...'
10:42:19 INFO [agent] run abc123 finished in 2390.6 ms - response 412 chars: 'JPM leads...'
```

---

## MCP tools

| Tool | Type | Description |
|------|------|-------------|
| `get_company` | fetch | Listing details for one ticker |
| `search_companies` | fetch | Filter by sector / board (NYSE|NASDAQ)|(NYSE|NASDAQ) |
| `list_sectors` | fetch | Sectors with company counts |
| `get_filings` | fetch | Filing history (Quarterly\|Annual) — renders as a revenue/profit **trend chart** |
| `get_latest_filing` | fetch | Most recent filing |
| `calc_financial_ratios` | calc | Margin, ROE, ROA, D/E, turnover, valuation |
| `calc_revenue_growth` | calc | QoQ / YoY revenue & profit growth |
| `compare_companies` | calc | Side-by-side valuation + highlights |
| `sector_ranking` | calc | Rank a sector by a chosen metric |

---

## Data model

**companies**: `symbol` (PK), name, sector, industry, market, listing_date,
par_value, shares_outstanding, last_price, market_cap, pe_ratio, pb_ratio,
dividend_yield, is_active.

**filings**: `filing_id` (PK), `symbol` (FK), filing_type, fiscal_period,
filing_date, revenue, net_profit, total_assets, total_liabilities, total_equity,
operating_cash_flow, eps. *(8 quarters 2023Q1–2024Q4 + an FY2024 annual per company.)*

---

## Troubleshooting

- **Agent won't start** — `LLM_API_KEY` / `LLM_BASE_URL` missing in `backend\.env`.
- **401 from the LLM** — wrong key, or `LLM_BASE_URL` overridden by an OS env var.
- **Empty replies** — `MAX_TOKENS` too low for a reasoning model; raise it (≥2048).
- **Tool results say "Not found" / connection refused** — the Data API (8000) isn't running.
- **Web chat / any MCP client can't reach tools, or AG-UI agent fails to start with
  a connection error** — agentgateway (3111) isn't running, or isn't up *yet*.
  `mcp_client/session.py` retries for ~30s before giving up, so a slow gateway
  start is usually fine on its own; check
  `backend\mcp_server\gateway\stdout.log` (or `http://localhost:8000/gateway-logs`
  once the Data API is up) for what it's actually doing.
- **`agentgateway.exe not found`** — run `backend\mcp_server\gateway\setup.ps1` once
  (downloads the binary; it's gitignored, not committed).
- **Reseed** — `python -m core.seed --reset`.
- **Run tests** — `python -m pytest tests/` (from `backend/`).
- **A host (Claude Desktop especially) stops showing up in the gateway's audit
  log** — don't assume the gateway broke; check that host's own MCP config
  first. `claude_desktop_config.json` in particular can silently revert to a
  direct `command: python.exe` stdio entry (bypassing the gateway entirely,
  tools still work but invisible to the audit log) — re-add the `mcp-remote`
  bridge entry from `claude_desktop_config.example.json` and fully **quit**
  from the tray (not just close the window) before retrying.
- **`mcp-remote` fails for Claude Desktop/Antigravity** — needs Node/`npx` on
  PATH; also needs agentgateway already running at the URL in its config.
- **Claude Code/Copilot show no tools** — same root cause as above one level up:
  confirm agentgateway is running on :3111 before the host tries to connect.
