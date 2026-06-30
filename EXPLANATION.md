# Project Explanation — Stock Exchange MCP Stack

This document explains the **whole project end to end** and what **every file**
does. Read the [Big picture](#1-big-picture) first, then use the
[file-by-file reference](#4-file-by-file-reference) as a lookup.

---

## 1. Big picture

A proof-of-concept that turns synthetic **stock-exchange** data
into an AI chatbot, with five layers:

1. **Database** — SQLite, accessed through SQLAlchemy ORM.
2. **Data API** — one FastAPI app (port 8000) exposing REST endpoints per domain.
3. **MCP server** — wraps the API endpoints as MCP *tools* (+ calculation tools).
4. **Chatbots** — two MCP *clients*: a terminal CLI and a web app (CopilotKit + AG-UI).
5. **Claude integration** — the same MCP server plugs into Claude Code / Claude Desktop.

The backend is **modular**: each domain (`listings`, `filings`, `analytics`) is a
self-contained plugin auto-discovered by a registry. Adding a domain wires it into
the API, the MCP server, and the seeder with no edits to shared code.

> All financial numbers are **synthetic** (deterministically generated). Ticker
> symbols/sectors are real ticker names for realism only.

---

## 2. Architecture & data flow

```
                        ┌─────────────────────────────┐
                        │  SQLite: stock_market.db       │
                        │  tables: companies, filings  │
                        └───────────────┬──────────────┘
                                        │ SQLAlchemy ORM (repositories)
                        ┌───────────────▼──────────────┐
                        │  Data API — FastAPI :8000     │
                        │  /listings/*   /filings/*     │  one port, path per domain
                        └───────────────┬──────────────┘
                                        │ HTTP (httpx) — one base URL
                        ┌───────────────▼──────────────┐
                        │  MCP server (FastMCP, stdio)  │
                        │  9 tools (fetch + calculate)  │
                        └───────┬───────────────┬───────┘
                       stdio    │               │  stdio
        ┌───────────────────────▼──┐   ┌────────▼─────────────────────────┐
        │ CLI chatbot (MCP client) │   │ AG-UI agent (MCP client) :8001    │
        │ mcp_client/cli_chat.py   │   │ OpenAI-compat LLM + AG-UI stream  │
        └──────────────────────────┘   └────────┬─────────────────────────┘
                                                 │ AG-UI events over HTTP/SSE
                                       ┌─────────▼─────────────────────────┐
                                       │ Next.js + CopilotKit  :3000        │
                                       │ streamed text + generative cards   │
                                       └────────────────────────────────────┘
        Claude Code / Claude Desktop ── settings.json / .mcp.json ─────────► MCP server
```

**A question's journey (web chatbot):**
1. User types in the custom React chat (`components/chat/ChatClaude.tsx`).
2. The browser `fetch`-POSTs a `RunAgentInput` **directly** to the AG-UI agent
   (:8001) and reads the **SSE** response stream (`lib/agui.ts`).
3. The agent (an **MCP client**) asks the LLM (LiteLLM proxy) what to do; the LLM
   picks a **tool** by name.
4. The agent calls that tool on the **MCP server** over stdio.
5. The tool does an HTTP GET to the **Data API** (e.g. `/listings/companies/AAPL`).
6. The API queries **SQLite** via a repository and returns JSON.
7. The agent streams **AG-UI events** back; the chat shows a live **tool-call chip**
   (running → done), renders the result as a **card**, and streams the answer text
   token-by-token.

**Two-level routing (how a tool knows which endpoint):**
- The **LLM** chooses *which tool* (from name + description).
- The **tool** carries *which endpoint path* (declared as an `EndpointTool`, or
  hand-written for calculation tools). One base URL; the FastAPI app routes the
  path to the right module.

---

## 2A. Architecture deep dive

### 2A.1 Component map (who owns what)

```
┌──────────────────────────── FRONTEND (Next.js :3000) ─────────────────────────┐
│  app/page.tsx ── full-screen chat shell (header + chat body)                   │
│      └── components/chat/ChatClaude.tsx   (state machine: messages, streaming)  │
│              ├── lib/agui.ts              (POST + parse SSE event stream)       │
│              ├── components/chat/ToolChip.tsx     (live "using tool" pill)      │
│              ├── components/chat/Markdown.tsx      (streamed-text renderer)     │
│              └── components/chat/toolCards.tsx     (tool name -> card)          │
│                      └── components/cards/*        (CompanyCard, RatioCard, …)  │
│  (legacy, still present: app/api/copilotkit/route.ts + components/GenerativeUI) │
└───────────────────────────────────┬───────────────────────────────────────────┘
                                     │  HTTP POST + SSE (AG-UI events)
┌──────────────────────────── BACKEND (Python) ──────────────────────────────────┐
│  agui_agent/  (FastAPI :8001)                                                    │
│      main.py  ── POST /agui  -> StreamingResponse                                │
│      agent.py ── ExchangeAgent: OpenAI tool-loop  <->  AG-UI events                   │
│                      │ (OpenAI SDK)             │ (MCP stdio via MCPToolClient)  │
│                      ▼                          ▼                                │
│              LiteLLM proxy (LLM)        mcp_server/ (FastMCP, stdio)             │
│                                              server.py ── registers module tools │
│                                              api_client.py ── httpx GET          │
│                                                  │ HTTP                          │
│                                                  ▼                               │
│                                         data_api/ (FastAPI :8000)                │
│                                              main.py ── mounts module routers    │
│                                                  │                               │
│                                   ┌──────────────┴───────────────┐               │
│                                   ▼              ▼               ▼               │
│                          modules/listings  modules/filings  modules/analytics    │
│                          (router+repo+ORM) (router+repo+ORM) (tools only)        │
│                                   └──────────────┬───────────────┘               │
│                                                  ▼                               │
│                                          core/database.py -> SQLite              │
│  core/registry.py ── discovers modules; used by data_api, mcp_server, seed       │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 2A.2 Web-chat request sequence (one user message)

```
Browser            Agent (:8001)        LLM proxy        MCP server        Data API (:8000)   SQLite
  │  POST /agui ------>│                                                                        
  │                    │ RUN_STARTED ──> (SSE back to browser: "Thinking…")                     
  │                    │  chat.completions (stream, tools) ─────>│                              
  │                    │<──────── tool_call: sector_ranking ─────│                              
  │  TOOL_CALL_START ◄─│ (browser shows spinning chip)                                          
  │                    │  call_tool("sector_ranking") ─stdio───────────────>│                  
  │                    │                                          GET /listings/companies?sector=…
  │                    │                                                     │── SELECT ──> │    
  │                    │                                                     │<── rows ─────│    
  │                    │<──────────── JSON result ─────────────────────────│                  
  │  TOOL_CALL_RESULT ◄│ (browser renders SectorRankCard)                                       
  │                    │  chat.completions (with tool result, stream) ─────>│                  
  │  TEXT_MESSAGE_*  ◄─│<──────── streamed answer tokens ────────│ (browser appends live)       
  │  RUN_FINISHED   ◄──│                                                                        
```

### 2A.3 Claude Desktop / Code path (no web app)

```
Claude Desktop ──launches──> python -m mcp_server.server  (stdio child process)
      │  (Claude's own model decides which tool)                  │
      │  call_tool ──────────────────────────────────────────────>│ httpx GET
      │                                                            ▼
      │                                              Data API :8000 ── SQLite
      └── tool JSON shown in Claude's UI
```
The MCP server needs the Data API running; it does **not** use any LLM key
(Claude provides the model). Config lives in `.mcp.json` / `settings.json`.

### 2A.4 Module registry lifecycle

```
import modules.*           core.registry.discover_modules()
   each __init__ defines  ───────────────►  [ModuleSpec(listings,10),
   MODULE = ModuleSpec(...)                   ModuleSpec(filings,20),
                                              ModuleSpec(analytics,30)]  (sorted by priority)
            │                                          │
   ┌────────┼─────────────────────┬───────────────────┴───────────────┐
   ▼        ▼                     ▼                                     ▼
 data_api/main.py        mcp_server/server.py                   core/seed.py
 mount spec.router       spec.register_tools(mcp, api)          spec.seed(db) in order
```
One discovery function, three consumers. Add a module → it shows up in all three.

### 2A.5 Two-level tool routing (which API does a tool hit?)

```
LLM picks TOOL by name/description        TOOL carries its ENDPOINT path
   "compare JPM…"  ─► compare_companies     ─► GET /listings/companies/{s}
                                               ─► GET /filings/{s}/latest
   one base URL (http://127.0.0.1:8000) + path  ─► FastAPI routes path to module
```
Pure-proxy tools are declared (`EndpointTool` → one path). Composite tools
(`analytics`) are hand-written and may call several endpoints + `core/calculations`.

### 2A.6 Generative-UI name matching (how a card appears)

```
MCP tool name  ==  AG-UI TOOL_CALL_RESULT.toolCallName  ==  toolCards switch case
"get_company"          "get_company"                        case "get_company" -> <CompanyCard/>
```
Same string end-to-end. The agent never chooses UI; the frontend has a card
pre-wired to each tool name. Unmatched tools simply show as text (never break).

### 2A.7 Processes, ports & transports

| Process | Port | Transport | Started by |
|---|---|---|---|
| Data API (`data_api.main`) | 8000 | HTTP/REST | `run_data_api.bat` / `run_all.bat` |
| AG-UI agent (`agui_agent.main`) | 8001 | HTTP + SSE (AG-UI) | `run_backend.bat` / `run_all.bat` |
| MCP server (`mcp_server.server`) | — | stdio | spawned by clients / Claude |
| Frontend (Next.js) | 3000 | HTTP | `run_all.bat` / `npm run dev` |
| CLI chatbot | — | stdio (to MCP) | `run_cli_chatbot.bat` |

### 2A.8 Tech stack

| Layer | Tech |
|---|---|
| DB / ORM | SQLite · SQLAlchemy 2.0 (typed) |
| API | FastAPI · Uvicorn · Pydantic v2 |
| MCP | `mcp` (FastMCP server + stdio client) |
| Agent protocol | `ag-ui-protocol` (events + encoder) |
| LLM | OpenAI SDK → LiteLLM proxy (Claude/GPT/Kimi models) |
| Synthetic data | Faker (seeded, deterministic) |
| Frontend | Next.js 14 (App Router) · React 18 · TypeScript |
| Streaming UI | Custom AG-UI SSE client (no chat framework) |

---

## 3. The module (plugin) system

A **module** lives in `backend/modules/<name>/` and declares one
`MODULE = ModuleSpec(...)`. The registry (`core/registry.py`) auto-discovers it
and the three entrypoints iterate that registry:

| Entry point | What it pulls from each module |
|---|---|
| `data_api/main.py` | `spec.router` → mounts REST endpoints |
| `mcp_server/server.py` | `spec.register_tools(mcp, api)` → registers MCP tools |
| `core/seed.py` | `spec.seed(db)` → inserts synthetic rows (in `priority` order) |

A module may be **data-backed** (`listings`, `filings`: own a table + router +
tools + seed) or **tool-only** (`analytics`: just tools over existing APIs).

---

## 4. File-by-file reference

### 4.1 Root

| File | Purpose |
|---|---|
| `README.md` | Setup + run guide, prerequisites, troubleshooting. |
| `EXPLANATION.md` | This document. |
| `.gitignore` | Ignores venv, node_modules, `.next`, `*.db`, `.env`, etc. |
| `.mcp.json` | Claude **Code** project MCP config — registers `stock-exchange`. |
| `claude_desktop_config.example.json` | Sample block to merge into Claude **Desktop** config. |
| `setup.bat` | One-time backend setup: venv (uv or pip) + install + seed. |
| `run_all.bat` | Boots Data API + AG-UI agent + frontend, each in its own window. |
| `run_backend.bat` | Boots the two backend apps only (Data API + AG-UI agent). |
| `run_data_api.bat` | Starts only the Data API (needed before using MCP in Claude). |
| `run_cli_chatbot.bat` | Starts Data API, then the terminal chatbot in the same window. |
| `scripts/setup_backend.ps1` | PowerShell equivalent of `setup.bat`. |
| `scripts/run_data_api.ps1` | PowerShell: start Data API. |
| `scripts/run_agui_agent.ps1` | PowerShell: start AG-UI agent. |
| `scripts/run_all.ps1` | PowerShell: start all services in separate windows. |

### 4.2 Backend — framework (`backend/core/`)

The shared framework. Knows nothing about specific domains.

| File | Purpose |
|---|---|
| `core/__init__.py` | Marks `core` as a package; module docstring. |
| `core/config.py` | `Settings` (pydantic-settings) loaded from env / `backend/.env`: DB URL, ports, `LLM_API_KEY/BASE_URL/MODEL`, `MAX_TOKENS`. Exposes `openai_base_url` (`LLM_BASE_URL` + `/v1`). The `LLM_` prefix avoids colliding with any `ANTHROPIC_*` OS env vars. |
| `core/database.py` | SQLAlchemy `engine`, `SessionLocal`, declarative `Base`, `get_db()` FastAPI dependency, and `init_db()` (discovers modules so their models register, then `create_all`). |
| `core/registry.py` | The plugin core. `ModuleSpec` dataclass (name, router, register_tools, seed, priority) and `discover_modules()` which imports every package under `modules/` and collects its `MODULE`, sorted by priority. |
| `core/api_tools.py` | Declarative **endpoint→tool** binding. `EndpointTool` (name, description, path, path_params, query_params) and `register_endpoint_tools()`, which generates a correctly-typed async MCP tool per endpoint (so a pure data proxy needs no function body). |
| `core/calculations.py` | **Pure** financial math (no DB/network): `financial_ratios`, `revenue_growth`, `compare_companies`, `sector_ranking`. Reused by any module. |
| `core/seed.py` | Registry-driven seeder. Sets a fixed random seed for determinism, then runs each module's `seed(db)` in priority order. `--reset` drops and rebuilds. |

### 4.3 Backend — modules (`backend/modules/`)

| File | Purpose |
|---|---|
| `modules/__init__.py` | Marks the modules namespace. |
| `modules/README.md` | **Contributor guide**: how to add a new module (DB + API + tool) step by step. |

**`modules/listings/` — company master data (table `companies`)**

| File | Purpose |
|---|---|
| `__init__.py` | Imports models (registers the table), then defines `MODULE = ModuleSpec(name="listings", router, register_tools, seed, priority=10)`. |
| `models.py` | ORM `Company` (symbol PK, name, sector, industry, market, price, market_cap, P/E, P/B, dividend yield, …). |
| `schemas.py` | Pydantic `CompanyOut`, `SectorOut` for API responses. |
| `repository.py` | All company DB queries: `list_companies`, `get_company`, `list_sectors`, `count`. |
| `router.py` | FastAPI router at `/listings`: `GET /companies`, `/companies/{symbol}`, `/sectors`. |
| `tools.py` | Declares `ENDPOINTS` (3 `EndpointTool`s) → MCP tools `get_company`, `search_companies`, `list_sectors`. |
| `seed.py` | The `UNIVERSE` of 41 real ticker symbols (with price/margin/yield bands) and `seed(db)` that inserts synthetic company rows. Margin bands are reused by the filings module. |

**`modules/filings/` — financial filings (table `filings`)**

| File | Purpose |
|---|---|
| `__init__.py` | Registers models; `MODULE = ModuleSpec(name="filings", …, priority=20)` (after listings). |
| `models.py` | ORM `Filing` (FK → company, filing_type, fiscal_period, revenue, net_profit, assets, liabilities, equity, OCF, EPS). |
| `schemas.py` | Pydantic `FilingOut`. |
| `repository.py` | `list_filings`, `latest_filing`, `count`. |
| `router.py` | FastAPI router at `/filings`: `GET /{symbol}`, `/{symbol}/latest`. |
| `tools.py` | `ENDPOINTS` → MCP tools `get_filings`, `get_latest_filing`. |
| `seed.py` | Generates 8 quarters (2023Q1–2024Q4) + one FY2024 annual per company, using each company's net-margin band; depends on listings being seeded first. |

**`modules/analytics/` — calculation tools (no table, no router)**

| File | Purpose |
|---|---|
| `__init__.py` | `MODULE = ModuleSpec(name="analytics", register_tools, priority=30)` — tools only. |
| `tools.py` | Hand-written MCP tools that fetch from `/listings` + `/filings` and call `core/calculations.py`: `calc_financial_ratios`, `calc_revenue_growth`, `compare_companies`, `sector_ranking`. The template for "composite" (non-proxy) tools. |

### 4.4 Backend — Data API (`backend/data_api/`)

| File | Purpose |
|---|---|
| `data_api/__init__.py` | Package marker. |
| `data_api/main.py` | Builds the FastAPI app, enables CORS, calls `init_db()` on startup, and **auto-mounts every module's router** from the registry. Adds `/health` (lists modules) and `/`. Run: `uvicorn data_api.main:app --port 8000`. |

### 4.5 Backend — MCP server (`backend/mcp_server/`)

| File | Purpose |
|---|---|
| `mcp_server/__init__.py` | Package marker. |
| `mcp_server/api_client.py` | `DataAPIClient` — a generic async `get(path, params)` over the single Data API base URL, plus `DataAPIError`. Module tools call this; no per-module client code. |
| `mcp_server/server.py` | Creates the `FastMCP("stock-exchange")` instance and a `DataAPIClient`, then **registers every module's tools** from the registry. `mcp.run()` serves over stdio (the form Claude Desktop/Code launch). |

### 4.6 Backend — MCP clients (`backend/mcp_client/`)

| File | Purpose |
|---|---|
| `mcp_client/__init__.py` | Package marker. |
| `mcp_client/session.py` | `MCPToolClient` — spawns the MCP server as a stdio subprocess, lists its tools, adapts them to the OpenAI function-calling schema (`openai_tools()`), and `call_tool()` (reassembles FastMCP's multi-block list results into clean JSON; hardened teardown). Shared by both chatbots. |
| `mcp_client/cli_chat.py` | A terminal chatbot: connects via `MCPToolClient`, runs an OpenAI tool-use loop against the LiteLLM proxy, prints answers. Forces UTF-8 stdout (for the `$` symbol on Windows). |

### 4.7 Backend — AG-UI agent (`backend/agui_agent/`)

The bridge that makes the web chatbot possible.

| File | Purpose |
|---|---|
| `agui_agent/__init__.py` | Package marker. |
| `agui_agent/agent.py` | `ExchangeAgent`: holds the OpenAI client (→ LiteLLM proxy) and an `MCPToolClient`. For each run it streams an OpenAI tool-use loop and emits **AG-UI events** — `RUN_STARTED`, `TEXT_MESSAGE_*` (streamed text), `TOOL_CALL_*` (so the frontend renders cards), `RUN_FINISHED`/`RUN_ERROR`. The proxy's Claude models are reasoning models, so it streams only `delta.content` (not `reasoning_content`). |
| `agui_agent/main.py` | FastAPI app exposing `POST /agui` (consumed by CopilotKit's `HttpAgent`) as an SSE stream, plus `/health`. Connects the MCP client on startup. Run: `uvicorn agui_agent.main:app --port 8001`. |

### 4.8 Backend — config/deps

| File | Purpose |
|---|---|
| `backend/requirements.txt` | Python deps: fastapi, uvicorn, SQLAlchemy, pydantic(-settings), Faker, httpx, mcp, ag-ui-protocol, openai. |
| `backend/.env.example` | Template for `.env`: `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`, `MAX_TOKENS`, Data API + agent ports. |
| `backend/.env` | **Local secrets (gitignored)** — your actual proxy key + base URL. |

### 4.9 Frontend (`frontend/`)

A Next.js (App Router) app. The **active chat is a custom component** that streams
directly from the AG-UI agent (no chat framework). CopilotKit files remain in the
repo as a working alternative but are not used by the current page.

| File | Purpose |
|---|---|
| `package.json` | Scripts + deps (Next 14, React 18, TypeScript; `@copilotkit/*` 1.61 + `@ag-ui/client` 0.0.57 kept for the legacy path). |
| `package-lock.json` | Locked dependency tree. |
| `tsconfig.json` | TypeScript config; `@/*` path alias to the frontend root. |
| `next.config.mjs` | Next.js config (`reactStrictMode`). |
| `next-env.d.ts` | Next-generated TS types (do not edit). |
| `.env.local` / `.env.local.example` | `NEXT_PUBLIC_AGUI_URL` (browser → agent, used by the custom chat) and `AGUI_AGENT_URL` (server-side, legacy CopilotKit route). |
| `.gitignore` | Frontend ignores. |
| `app/layout.tsx` | Root layout; imports global CSS; wraps children in `Providers`. |
| `app/globals.css` | All styling: the **amber-cream glass** theme (SF Pro fonts, frosted surfaces), full-screen app shell, chat (`.cc*`), tool chips, markdown, and generative-UI card styles. |
| `app/page.tsx` | Full-screen chat shell — header + `ChatClaude` (dynamically imported with `ssr: false`). No sidebar. |
| **`lib/agui.ts`** | **AG-UI SSE client**: POSTs a `RunAgentInput` to the agent and yields parsed events (`runAgent` async generator). |
| **`components/chat/ChatClaude.tsx`** | **The active chat.** State machine over the AG-UI stream: appends text deltas live, tracks tool calls, renders chips + cards, input/stop. |
| **`components/chat/ToolChip.tsx`** | Live "using a tool" pill (spinner → ✓), shows the tool name + args. |
| **`components/chat/Markdown.tsx`** | Tiny dependency-free markdown renderer for streamed text (headings, lists, bold, code). |
| **`components/chat/toolCards.tsx`** | Maps a tool name + JSON result → the right card; plus friendly tool labels. |
| `lib/types.ts` | TS types mirroring tool JSON (Company, Filing, Ratios, …) + formatters (`fmtCompactUSD` → `1.74 tn $`, `fmtPct`, `parseResult`). |
| `app/api/copilotkit/route.ts` | *(legacy)* CopilotKit runtime endpoint → AG-UI `HttpAgent`. |
| `components/Providers.tsx` | *(legacy)* `<CopilotKit>` provider. |
| `components/ChatApp.tsx` | *(legacy)* CopilotChat-based chat surface. |
| `components/GenerativeUI.tsx` | *(legacy)* render-only CopilotKit actions per tool name. |

**`frontend/components/cards/` — the generative-UI cards**

| File | Renders for tool | Shows |
|---|---|---|
| `Common.tsx` | (shared) | `Card`, `Stat`, `Badge`, `Skeleton` building blocks. |
| `CompanyCard.tsx` | `get_company` | Company profile: price, market cap, P/E, P/B, yield. |
| `CompanyListCard.tsx` | `search_companies` | Scrollable table of companies. |
| `RatioCard.tsx` | `calc_financial_ratios` | Profitability / leverage / efficiency / valuation. |
| `GrowthCard.tsx` | `calc_revenue_growth` | QoQ / YoY revenue & profit badges. |
| `ComparisonTable.tsx` | `compare_companies` | Side-by-side table + highlights. |
| `SectorRankCard.tsx` | `sector_ranking` | Ranked list by a metric. |
| `TrendChart.tsx` | `get_filings` | Inline SVG revenue bars + net-profit line. |

### 4.10 Editor / tooling

| File | Purpose |
|---|---|
| `.claude/settings.local.json` | Local Claude Code project settings (permissions, etc.). |

---

## 5. How to run (quick)

```powershell
setup.bat            # once: venv + install + seed
# put your proxy key in backend\.env  (LLM_API_KEY / LLM_BASE_URL)
run_all.bat          # Data API :8000 + agent :8001 + web :3000
```
- Web chatbot: http://localhost:3000
- API docs: http://127.0.0.1:8000/docs
- Terminal chatbot: `run_cli_chatbot.bat`
- Claude Desktop/Code: start `run_data_api.bat`, then the `stock-exchange` server
  (already in `.mcp.json` / your `settings.json`).

## 6. How to extend

- **Add a data domain + tool:** create `backend/modules/<name>/` with
  `models.py`, `router.py`, `tools.py` (declare `EndpointTool`s), `seed.py`, and
  a `MODULE` spec. It auto-wires into API + MCP + seeder. See
  [`backend/modules/README.md`](backend/modules/README.md).
- **Add a calculation:** put the math in `core/calculations.py` and call it from a
  hand-written tool (see `modules/analytics/tools.py`).
- **Render a tool as a card:** add a render action in
  `frontend/components/GenerativeUI.tsx` + a component in
  `frontend/components/cards/`.
