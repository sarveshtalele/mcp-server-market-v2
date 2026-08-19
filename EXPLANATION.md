# Project Explanation — Stock Exchange MCP Stack

Explains the **whole project end to end** and what **every file** does. Read the
[Big picture](#1-big-picture) first, then use the
[file-by-file reference](#4-file-by-file-reference) as a lookup. For the *why/how*
of the gateway specifically, see the "agentgateway" section of the top-level
[`README.md`](README.md); this document focuses on the code.

---

## 1. Big picture

A proof-of-concept that turns synthetic **stock-exchange** data into an AI
chatbot, with six layers:

1. **Database** — SQLite, via SQLAlchemy ORM.
2. **Data API** — one FastAPI app (`:8000`) exposing REST endpoints per domain.
3. **MCP server** — wraps the API endpoints as MCP *tools* (+ calculation tools).
4. **agentgateway** (`:3111`) — a governance/audit proxy that is the **only**
   thing that spawns the MCP server. Every consumer talks to it, not to the
   Python server directly.
5. **Chatbots** — two MCP *clients* (a terminal CLI and a web app), both reaching
   the MCP server *through the gateway*.
6. **AI hosts** — Claude Code, Claude Desktop, VS Code Copilot, Antigravity — also
   through the gateway.

The backend is **modular**: each domain (`listings`, `filings`, `analytics`) is a
self-contained plugin auto-discovered by a registry, wiring itself into the API,
the MCP tool surface, and the seeder with no edits to shared code.

> All financial numbers are **synthetic** (deterministic Faker, `SEED = 2025`).
> Real ticker/sector names are used for flavour only — not market data.

---

## 2. Architecture & data flow

```
                    ┌─────────────────────────────┐
                    │  SQLite: stock_market.db     │
                    │  tables: companies, filings  │
                    └───────────────┬──────────────┘
                                    │ SQLAlchemy ORM (repositories)
                    ┌───────────────▼──────────────┐
                    │  Data API — FastAPI :8000     │  /listings/*  /filings/*
                    │  (+ /gateway-logs viewer)     │
                    └───────────────▲──────────────┘
                                    │ HTTP (httpx) — one base URL
                    ┌───────────────┴──────────────┐
                    │  MCP server (FastMCP, stdio)  │  9 tools (fetch + calc)
                    │  spawned ONLY by the gateway  │
                    └───────────────▲──────────────┘
                             stdio  │  (gateway spawns it as its own child)
                    ┌───────────────┴──────────────┐
                    │  agentgateway :3111           │  tool allowlist + audit log
                    │  config: mcp_server/gateway/  │
                    └──────┬──────────────────┬─────┘
              http (direct)│                  │ stdio via mcp-remote (npx) bridge
       ┌──────────────────▼─────────┐  ┌──────▼───────────────────┐
       │ Claude Code · VS Code       │  │ Claude Desktop ·          │
       │ Copilot · AG-UI agent :8001 │  │ Antigravity               │
       │ · CLI chatbot               │  │ (config can't use http)   │
       └──────────────┬──────────────┘  └───────────────────────────┘
                      │ AG-UI over HTTP/SSE (browser fetch — AG-UI agent only)
             ┌────────▼──────────────────────┐
             │ Next.js custom chat  :3000     │  streamed text + tool chips/cards
             │ + response time / token usage  │
             └────────────────────────────────┘
```

**A question's journey (web chatbot):**
1. User types in the custom React chat (`components/chat/AppShell.tsx` +
   `ChatView.tsx`).
2. The browser `fetch`-POSTs a `RunAgentInput` **directly** to the AG-UI agent
   (`:8001`) and reads the **SSE** response stream (`lib/agui.ts`).
3. The agent (`agui_agent/agent.py`, an **MCP client** via `mcp_client/session.py`)
   asks the LLM (LiteLLM proxy) what to do; the LLM picks a **tool** by name.
4. The agent calls that tool over **Streamable HTTP to agentgateway** (`:3111`).
5. The gateway checks the tool against its allowlist, logs the call, and forwards
   it to the MCP server it spawned as a stdio child.
6. The tool does an HTTP GET to the **Data API** (e.g. `/listings/companies/AAPL`);
   the API queries **SQLite** and returns JSON back up the chain.
7. The agent streams **AG-UI events** back; the chat shows a live **tool-call chip**
   (running → done, with ms), renders the result as a **card**, streams the answer
   text token-by-token, and at the end emits a **`usage`** CUSTOM event
   (response time + token counts) shown under the reply and in the activity panel.

**Two-level routing (how a tool knows which endpoint):**
- The **LLM** chooses *which tool* (from name + description).
- The **tool** carries *which endpoint path* (a declarative `EndpointTool`, or a
  hand-written analytics tool). One Data API base URL; FastAPI routes the path to
  the right module.

---

## 2A. Architecture deep dive

### 2A.1 Component map (who owns what)

```
┌──────────────────────────── FRONTEND (Next.js :3000) ─────────────────────────┐
│  app/page.tsx ── loads AppShell (ssr:false)                                    │
│    components/chat/AppShell.tsx  (owns state: convos, streaming, usage)         │
│      ├── lib/agui.ts        (POST + parse AG-UI SSE event stream)               │
│      ├── lib/store.ts       (saved conversations in localStorage)              │
│      ├── lib/agents.ts      (predefined agent presets)                          │
│      ├── chat/ChatSidebar.tsx  (New chat + saved chats + Agents)               │
│      ├── chat/ChatView.tsx     (transcript + composer + per-reply usage)       │
│      ├── chat/ActivityPanel.tsx(tool calls + ms + latest run's time/tokens)    │
│      ├── chat/ToolChip.tsx     (live "using tool" pill + ms)                   │
│      ├── chat/Markdown.tsx     (streamed-text renderer, incl. tables)          │
│      └── chat/toolCards.tsx    (tool name -> card + friendly labels)           │
│              └── components/cards/*  (CompanyCard, RatioCard, TrendChart, …)    │
└───────────────────────────────────┬───────────────────────────────────────────┘
                                     │  HTTP POST + SSE (AG-UI events)
┌──────────────────────────── BACKEND (Python) ──────────────────────────────────┐
│  agui_agent/  (FastAPI :8001)                                                    │
│    main.py  ── POST /agui -> StreamingResponse                                   │
│    agent.py ── ExchangeAgent: OpenAI tool-loop <-> AG-UI events + usage          │
│                 │ (OpenAI SDK)              │ (mcp_client.session, HTTP to gateway)│
│                 ▼                           ▼                                     │
│         LiteLLM proxy (LLM)        agentgateway :3111                            │
│                                       mcp_server/gateway/config.yaml             │
│                                       (allowlist + audit log; spawns ↓ stdio)    │
│                                    mcp_server/server.py  (FastMCP, module tools) │
│                                       api_client.py ── httpx GET                 │
│                                          │ HTTP                                  │
│                                          ▼                                       │
│                                 data_api/ (FastAPI :8000) ── mounts module routers│
│                          ┌───────────────┼───────────────┐                       │
│                          ▼               ▼               ▼                       │
│                 modules/listings  modules/filings  modules/analytics             │
│                 (router+repo+ORM) (router+repo+ORM) (tools only)                 │
│                          └───────────────┼───────────────┘                       │
│                                          ▼                                       │
│                                  core/database.py -> SQLite                       │
│  core/registry.py ── discovers modules; used by data_api, mcp_server, seed       │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 2A.2 Web-chat request sequence (one user message)

```
Browser        Agent :8001      gateway :3111    MCP server     Data API :8000  SQLite
  │ POST /agui ──►│                                                                
  │               │ RUN_STARTED ──► (SSE: "Thinking…")                              
  │               │ chat.completions(stream, tools) ──► LLM                         
  │               │ ◄── tool_call: sector_ranking                                   
  │ TOOL_CALL_START◄ (chip spins)                                                   
  │               │ call_tool ──http──►│ allowlist+log ─stdio─►│                     
  │               │                    │                        GET /listings/... │  
  │               │                    │                        │── SELECT ──►│    │
  │               │ ◄──────────────────┴── JSON result ────────┘             │    │
  │ TOOL_CALL_RESULT◄ (renders SectorRankCard, records ms)                          
  │               │ chat.completions(with result, stream) ──► LLM                   
  │ TEXT_MESSAGE_*◄─── streamed answer tokens                                       
  │ CUSTOM "usage"◄─── {elapsedMs, prompt/completion/total tokens, toolCalls}       
  │ RUN_FINISHED  ◄───                                                              
```

### 2A.3 AI-host path (Claude Code / Desktop / Copilot / Antigravity)

```
Claude Code / VS Code Copilot ──http──►  agentgateway :3111 ──stdio(spawns)──► mcp_server
Claude Desktop / Antigravity  ──stdio(mcp-remote npx bridge)──►  agentgateway :3111 ──►  same
```
Hosts use `type: http` where their config allows it (Claude Code `.mcp.json`,
VS Code `.vscode/mcp.json`); Claude Desktop and Antigravity configs don't accept a
plain remote http entry, so they use the `mcp-remote` npm bridge to reach the same
gateway. Hosts need **no LLM key** — the host provides the model. The Data API and
the gateway must be running.

### 2A.4 Module registry lifecycle

```
import modules.*           core.registry.discover_modules()
   each __init__ defines  ───────────────►  [ModuleSpec(listings,10),
   MODULE = ModuleSpec(...)                   ModuleSpec(filings,20),
                                              ModuleSpec(analytics,30)]  (by priority)
            │                                          │
   ┌────────┼──────────────────────┬──────────────────┴──────────────┐
   ▼        ▼                      ▼                                   ▼
 data_api/main.py        mcp_server/server.py                  core/seed.py
 mount spec.router       spec.register_tools(mcp, api)         spec.seed(db) in order
```
One discovery function, three consumers. Add a module → it shows up in all three.
(A new **tool** must also be added to the gateway allowlist in
`mcp_server/gateway/config.yaml` before any consumer can call it.)

### 2A.5 Two-level tool routing

```
LLM picks TOOL by name/description        TOOL carries its ENDPOINT path
   "compare JPM…"  ─► compare_companies     ─► GET /listings/companies/{s}
                                             ─► GET /filings/{s}/latest
   one base URL (http://127.0.0.1:8000) + path  ─► FastAPI routes to the module
```
Pure-proxy tools are declared (`EndpointTool` → one path, body generated by
`core/api_tools.py`). Composite tools (`analytics`) are hand-written and may call
several endpoints + `core/calculations`.

### 2A.6 Generative-UI name matching (how a card appears)

```
MCP tool name  ==  AG-UI TOOL_CALL_RESULT.toolCallName  ==  toolCards switch case
"get_company"          "get_company"                       case "get_company" -> <CompanyCard/>
```
Same string end-to-end. The agent never chooses UI; the frontend has a card
pre-wired to each tool name. Unmatched tools show as text (never break).

### 2A.7 Processes, ports & transports

| Process | Port | Transport | Started by |
|---|---|---|---|
| Data API (`data_api.main`) | 8000 | HTTP/REST | `run_all.bat` (or `uvicorn`) |
| agentgateway | 3111 | HTTP (MCP) in front; stdio to its child | `run_all.bat` / `gateway/run.ps1` |
| MCP server (`mcp_server.server`) | — | stdio | **spawned by the gateway only** |
| AG-UI agent (`agui_agent.main`) | 8001 | HTTP + SSE (AG-UI) | `run_all.bat` (or `uvicorn`) |
| Frontend (Next.js) | 3000 | HTTP | `run_all.bat` / `npm run dev` |
| CLI chatbot | — | HTTP to gateway | `python -m mcp_client.cli_chat` |
| agentgateway UI (optional) | 15000 | HTTP | the gateway process itself |

### 2A.8 Tech stack

| Layer | Tech |
|---|---|
| DB / ORM | SQLite · SQLAlchemy 2.0 (typed) |
| API | FastAPI · Uvicorn · Pydantic v2 |
| MCP | `mcp` (FastMCP server + Streamable HTTP client) |
| Governance | agentgateway (Rust; allowlist + audit log) |
| Agent protocol | `ag-ui-protocol` (events + encoder) |
| LLM | OpenAI SDK → LiteLLM proxy (Claude/GPT/Kimi models) |
| Synthetic data | Faker (seeded, deterministic) |
| Frontend | Next.js 14 (App Router) · React 18 · TypeScript |
| Streaming UI | Custom AG-UI SSE client (no chat framework) |

---

## 3. The module (plugin) system

A **module** lives in `backend/modules/<name>/` and declares one
`MODULE = ModuleSpec(...)`. The registry (`core/registry.py`) auto-discovers it and
three entrypoints iterate that registry:

| Entry point | What it pulls from each module |
|---|---|
| `data_api/main.py` | `spec.router` → mounts REST endpoints |
| `mcp_server/server.py` | `spec.register_tools(mcp, api)` → registers MCP tools |
| `core/seed.py` | `spec.seed(db)` → inserts synthetic rows (in `priority` order) |

A module may be **data-backed** (`listings`, `filings`: table + router + tools +
seed) or **tool-only** (`analytics`: tools over existing APIs). Full guide:
[`backend/modules/README.md`](backend/modules/README.md) — note it includes the
required **gateway-allowlist** step for any new tool.

---

## 4. File-by-file reference

### 4.1 Root

| File | Purpose |
|---|---|
| `README.md` | Setup/run guide, host-config JSON, the full agentgateway rationale, troubleshooting. |
| `EXPLANATION.md` | This document. |
| `REVIEW.md` | Code review & gap analysis. |
| `CLAUDE.md` | Guidance for Claude Code sessions working in this repo (commands + architecture notes). |
| `.gitignore` | Ignores venv, node_modules, `.next`, `*.db`, `.env`, the gateway `bin/`, `*.mp4`, etc. |
| `.mcp.json` | Claude **Code** MCP config — `type: http` → `http://127.0.0.1:3111/mcp` (gateway). |
| `.vscode/mcp.json` | VS Code **Copilot** MCP config — `servers` + `type: http` → gateway. |
| `claude_desktop_config.example.json` | Claude **Desktop** config — `npx mcp-remote` bridge → gateway. |
| `integrations/antigravity.mcp.example.json` | **Antigravity** config — `npx mcp-remote` bridge → gateway. |
| `run_all.bat` | Boots the whole stack in four windows: Data API → agentgateway (waits until ready) → AG-UI agent → frontend. |
| `architecture.png` | The architecture image shown in the README. |

### 4.2 Backend — framework (`backend/core/`)

The shared framework. Knows nothing about specific domains.

| File | Purpose |
|---|---|
| `core/config.py` | `Settings` (pydantic-settings) from env / `backend/.env`: `database_url`, Data API host/port + `data_api_base_url`, AG-UI host/port, `LLM_API_KEY/BASE_URL/MODEL`, `max_tokens`, `currency`, `log_level`, and **`mcp_gateway_url`** (default `http://127.0.0.1:3111/mcp`). Exposes `openai_base_url` (`LLM_BASE_URL` + `/v1`). `LLM_` prefix avoids clashing with `ANTHROPIC_*` OS vars. |
| `core/database.py` | SQLAlchemy `engine`, `SessionLocal`, declarative `Base`, `get_db()` dependency, `init_db()` (discovers modules so models register, then `create_all`). |
| `core/registry.py` | Plugin core. `ModuleSpec` dataclass (name, router, register_tools, seed, priority, tags) and `discover_modules()` — imports every package under `modules/`, collects its `MODULE`, sorts by priority. |
| `core/api_tools.py` | Declarative **endpoint→tool** binding. `EndpointTool` + `register_endpoint_tools()` generate a correctly-typed async MCP tool per endpoint (pure data proxy needs no body). |
| `core/calculations.py` | **Pure** financial math (no DB/network): `financial_ratios`, `revenue_growth`, `compare_companies`, `sector_ranking`. |
| `core/seed.py` | Registry-driven seeder. Fixed random/Faker seed (`SEED = 2025`) for determinism; runs each module's `seed(db)` in priority order. `--reset` drops + rebuilds. |
| `core/logging_config.py` | `setup_logging()` / `get_logger()`. **All logs go to stderr only** (stdout is the MCP stdio JSON-RPC channel). Level from `LOG_LEVEL`. |

### 4.3 Backend — modules (`backend/modules/`)

| File | Purpose |
|---|---|
| `modules/__init__.py` | Marks the modules namespace. |
| `modules/README.md` | **Contributor guide**: add a module (DB + API + tool + seed + gateway allowlist). |

**`modules/listings/` — company master data (table `companies`)**

| File | Purpose |
|---|---|
| `__init__.py` | Imports models, defines `MODULE = ModuleSpec(name="listings", router, register_tools, seed, priority=10)`. |
| `models.py` | ORM `Company` (symbol PK, name, sector, industry, market NYSE/NASDAQ, price, market_cap, P/E, P/B, dividend yield, …). |
| `schemas.py` | Pydantic `CompanyOut`, `SectorOut`. |
| `repository.py` | Company queries: `list_companies`, `get_company`, `list_sectors`, `count`. |
| `router.py` | `/listings`: `GET /companies`, `/companies/{symbol}`, `/sectors`. |
| `tools.py` | `ENDPOINTS` (3 `EndpointTool`s) → tools `get_company`, `search_companies`, `list_sectors`. |
| `seed.py` | `UNIVERSE` of 41 real US tickers with per-company bands, incl. a **`shares_band`** sized per company (so market cap = price × shares ranks realistically — a flat share range would break cross-company rankings). |

**`modules/filings/` — financial filings (table `filings`)**

| File | Purpose |
|---|---|
| `__init__.py` | `MODULE = ModuleSpec(name="filings", …, priority=20)` (after listings). |
| `models.py` | ORM `Filing` (FK → company, filing_type, fiscal_period, revenue, net_profit, assets, liabilities, equity, OCF, EPS). |
| `schemas.py` | Pydantic `FilingOut`. |
| `repository.py` | `list_filings`, `latest_filing`, `count`. |
| `router.py` | `/filings`: `GET /{symbol}`, `/{symbol}/latest`. |
| `tools.py` | `ENDPOINTS` → tools `get_filings`, `get_latest_filing`. |
| `seed.py` | 8 quarters (2023Q1–2024Q4) + one FY2024 annual per company, using each company's net-margin band; depends on listings seeded first. |

**`modules/analytics/` — calculation tools (no table, no router)**

| File | Purpose |
|---|---|
| `__init__.py` | `MODULE = ModuleSpec(name="analytics", register_tools, priority=30)` — tools only. |
| `tools.py` | Hand-written MCP tools that fetch from `/listings` + `/filings` and call `core/calculations.py`: `calc_financial_ratios`, `calc_revenue_growth`, `compare_companies`, `sector_ranking`. Template for "composite" (non-proxy) tools. |

### 4.4 Backend — Data API (`backend/data_api/`)

| File | Purpose |
|---|---|
| `data_api/__init__.py` | Package marker. |
| `data_api/main.py` | FastAPI app: CORS, `init_db()` on startup, a **request-logging middleware** (path/status/latency), and **auto-mounts every module's router**. Adds `/health` (lists modules), `/`, and the **agentgateway log viewer**: `/gateway-logs` (auto-refreshing HTML) + `/gateway-logs/raw` (tails the gateway's `stdout.log`/`stderr.log`, since the gateway has no log UI of its own). Run: `uvicorn data_api.main:app --port 8000`. |

### 4.5 Backend — MCP server + gateway (`backend/mcp_server/`)

| File | Purpose |
|---|---|
| `mcp_server/__init__.py` | Package marker. |
| `mcp_server/api_client.py` | `DataAPIClient` — generic async `get(path, params)` over the Data API base URL, plus `DataAPIError`. Module tools use this; no per-module client code. |
| `mcp_server/server.py` | Builds `FastMCP("stock-exchange", instructions=INSTRUCTIONS)` (a server-level `instructions` string telling clients to answer only from tool data), registers every module's tools, and `mcp.run()` over **stdio** — but is now launched **only by agentgateway**, not by hosts/clients directly. |
| `mcp_server/gateway/config.yaml` | agentgateway config: `binds[].listeners[].routes[].backends[].mcp.targets[].stdio` is the actual spawn point for `python -m mcp_server.server` (with `DATA_API_BASE_URL` + `PYTHONPATH`); `policies.mcpAuthorization` is the CEL **tool-name allowlist** (9 rules today); `policies.cors` (browser callers only). |
| `mcp_server/gateway/setup.ps1` | One-time: downloads `agentgateway-windows-amd64.exe` into `bin/` (~86 MB, gitignored). |
| `mcp_server/gateway/run.ps1` | Runs the gateway against `config.yaml` (`agentgateway.exe -f config.yaml`). Kept plain ASCII (PowerShell 5.1 parses `.ps1` in the system codepage). |
| `mcp_server/gateway/bin/agentgateway.exe` | The gateway binary (gitignored — created by `setup.ps1`). |
| `mcp_server/gateway/stdout.log` / `stderr.log` | Where the gateway's audit log / the wrapped Python server's stderr land (tailed by `/gateway-logs`). |

### 4.6 Backend — MCP clients (`backend/mcp_client/`)

| File | Purpose |
|---|---|
| `mcp_client/__init__.py` | Package marker. |
| `mcp_client/session.py` | `MCPToolClient` — connects to the MCP server **through agentgateway over Streamable HTTP** (`settings.mcp_gateway_url`), *not* by spawning the Python process. `connect()` first runs `_wait_for_port` (a raw TCP probe loop) because the Streamable HTTP client can't be safely retried after a failed connect. Adapts tools to OpenAI function schema (`openai_tools()`); `call_tool()` reassembles FastMCP's multi-block list results into clean JSON; a lock serialises the shared session. Used by both chatbots. |
| `mcp_client/cli_chat.py` | Terminal chatbot: same `MCPToolClient` (via the gateway), runs an OpenAI tool-use loop against the LiteLLM proxy, prints answers. Forces UTF-8 stdout for `$`/non-ASCII on Windows. |

### 4.7 Backend — AG-UI agent (`backend/agui_agent/`)

The bridge that makes the web chatbot possible.

| File | Purpose |
|---|---|
| `agui_agent/__init__.py` | Package marker. |
| `agui_agent/agent.py` | `ExchangeAgent`: OpenAI client (→ LiteLLM proxy) + an `MCPToolClient` (→ gateway). Streams an OpenAI tool-use loop and emits **AG-UI events** — `RUN_STARTED`, `TEXT_MESSAGE_*`, `TOOL_CALL_*`, a **`usage` CUSTOM event** (elapsed ms + prompt/completion/total tokens + tool-call count), `RUN_FINISHED`/`RUN_ERROR`. Streams only `delta.content` (not the model's `reasoning_content`). Logs per-turn and per-run timing + token usage. Its `SYSTEM_PROMPT` is where "answer only from tool data" is actually enforced in code. |
| `agui_agent/main.py` | FastAPI app: `POST /agui` (SSE stream consumed by the browser) + `/health`. Connects the `MCPToolClient` on startup. Run: `uvicorn agui_agent.main:app --port 8001`. |

### 4.8 Backend — config/deps

| File | Purpose |
|---|---|
| `backend/requirements.txt` | Python deps: fastapi, uvicorn, SQLAlchemy, pydantic(-settings), Faker, httpx, mcp, ag-ui-protocol, openai, pytest. |
| `backend/.env.example` | Template: `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`, `MAX_TOKENS`, `DATA_API_BASE_URL`, ports, `LOG_LEVEL`. |
| `backend/.env` | **Local secrets (gitignored)** — actual proxy key + base URL. |
| `backend/tests/test_calculations.py` | Pytest over the pure functions in `core/calculations.py`. |

### 4.9 Frontend (`frontend/`)

A Next.js (App Router) app. The chat is a **custom 3-panel component** that streams
directly from the AG-UI agent — no chat framework/CopilotKit.

| File | Purpose |
|---|---|
| `package.json` / `package-lock.json` | Next 14 · React 18 · TypeScript (+ `@opentelemetry/api`, a Next peer dep). No CopilotKit. |
| `tsconfig.json` | `@/*` path alias to the frontend root. |
| `next.config.mjs` | Next config (`reactStrictMode`). |
| `.env.local` / `.env.local.example` | `NEXT_PUBLIC_AGUI_URL` — browser → AG-UI agent (`http://127.0.0.1:8001/agui`). |
| `app/layout.tsx` | Root layout; imports global CSS. |
| `app/globals.css` | The **amber-cream glass** theme (SF Pro, frosted surfaces), the 3-panel `.shell` grid, rails, chat (`.cc*`), tool chips, activity panel, markdown/table, and generative-card styles. |
| `app/page.tsx` | Full-screen shell that dynamically imports `AppShell` with `ssr:false`. |
| `lib/agui.ts` | **AG-UI SSE client**: POSTs a `RunAgentInput` and yields parsed events (`runAgent` async generator). |
| `lib/store.ts` | `useConversations` — saved chats in `localStorage` (lazy init, debounced writes, `setMessagesOf(id, …)`). Defines `Msg` (with `usage`) and `MsgUsage`. |
| `lib/agents.ts` | `AGENTS` presets (Valuation Analyst, Growth Scout, Sector Screener, Peer Comparator) + `agentPrompt()`. |
| `lib/types.ts` | TS types mirroring tool JSON + formatters (`fmtCompactUSD` → `$1.74 tn`, `fmtPct`, `parseResult`). |
| `components/chat/AppShell.tsx` | **Owns all state**: conversation store (left), streaming engine (centre), tool-activity (right). Runs one AG-UI stream per message, measures each tool's ms client-side, records the `usage` CUSTOM event onto the message. |
| `components/chat/ChatSidebar.tsx` | Left rail — New chat, saved conversation list, one-click Agents. |
| `components/chat/ChatView.tsx` | Centre — transcript (chips + cards + streamed markdown), the composer (auto-growing textarea), and each finished reply's response time + token usage. |
| `components/chat/ActivityPanel.tsx` | Right rail — every tool call with args/status/ms + totals, and the latest run's time/tokens. |
| `components/chat/ToolChip.tsx` | The live "using a tool" pill (spinner → ✓) with args + ms. |
| `components/chat/Markdown.tsx` | Dependency-free markdown renderer (headings, lists, bold, code, tables). |
| `components/chat/toolCards.tsx` | `renderToolCard(name, result)` maps a tool → a card; `TOOL_LABEL` gives friendly chip labels. |

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
| `.claude/settings.local.json` | Local Claude Code project settings (permissions). |
| `.claude/launch.json` | Preview-server launch config for the frontend. |

---

## 5. How to run (quick)

```powershell
# one-time
cd backend & uv venv .venv & uv pip install -r requirements.txt
copy .env.example .env          # add LLM_API_KEY / LLM_BASE_URL / LLM_MODEL
python -m core.seed --reset
backend\mcp_server\gateway\setup.ps1   # downloads the gateway binary (~86MB)
cd frontend & copy .env.local.example .env.local & npm install

# run everything (Data API :8000 + agentgateway :3111 + agent :8001 + web :3000)
run_all.bat
```
- Web chatbot: http://localhost:3000
- API docs: http://127.0.0.1:8000/docs
- Gateway logs: http://localhost:8000/gateway-logs
- Terminal chatbot: `python -m mcp_client.cli_chat`
- AI hosts: see README §3 (all point at `http://127.0.0.1:3111/mcp`).

## 6. How to extend

- **Add a data domain + tool:** create `backend/modules/<name>/` with
  `models.py`, `router.py`, `tools.py` (declare `EndpointTool`s), `seed.py`, and a
  `MODULE` spec — then **add the tool name to the gateway allowlist**
  (`mcp_server/gateway/config.yaml`). See
  [`backend/modules/README.md`](backend/modules/README.md).
- **Add a calculation:** put the math in `core/calculations.py`, call it from a
  hand-written tool (see `modules/analytics/tools.py`).
- **Render a tool as a card:** add a case to `renderToolCard` in
  `frontend/components/chat/toolCards.tsx` + a component in
  `frontend/components/cards/`.
