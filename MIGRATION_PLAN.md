# Migration Plan — `mcp-server-market` → MCP 2026-07-28

Status: **Delivered.** Kept as the record of why the architecture looks like this, which
alternatives were rejected, and what was measured rather than assumed. For the current state see
[CLAUDE.md](CLAUDE.md); for how it was executed see [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).
Author pass: plan drafted → reviewed against the actual repo → gaps listed → final plan below.

---

## 0. What this document is

Three parts:

1. **Part A — Verdict on `mcp_poc_modern_protocol_plan.md`**: what it got right, what is wrong, what it missed.
2. **Part B — Ground truth of the current repo** (what actually exists, from source).
3. **Part C — The final migration plan**: phases, task checklist, test plan, risks, rollback.

Companion docs: [CLAUDE.md](CLAUDE.md) (ground truth + SDLC rules), [SPECS.md](SPECS.md) (feature specs + acceptance criteria), [DESIGN.md](DESIGN.md) (UI spec).

---

# Part A — Review of the existing plan

## A.1 Verified against the live spec

Every claim below was checked against `modelcontextprotocol.io` on 2026-08-20, not from memory.

| Claim in plan | Verdict | Evidence |
| :--- | :--- | :--- |
| `2026-07-28` is the current protocol revision | **Correct** | Versioning page: "The **current** protocol version is 2026-07-28" |
| `initialize` / `notifications/initialized` handshake removed; protocol is stateless | **Correct** | Changelog major change #2 (SEP-2575) |
| `server/discover` exists and servers MUST implement it | **Correct** | Changelog #3; `server/discover` page |
| Per-request `_meta` carries version + client capabilities | **Correct** | `io.modelcontextprotocol/protocolVersion`, `/clientCapabilities`, `/clientInfo` |
| `CacheableResult` with `ttlMs` | **Correct but incomplete** | Minor change #5 — `cacheScope` is also **required**, and it applies to `tools/list`, `prompts/list`, `resources/list`, `resources/read`, `resources/templates/list` — not just tool definitions |
| Deterministic `tools/list` ordering | **Correct** | Minor change #3 (SHOULD, for client-side + prompt caching) |
| Native Streamable HTTP mount | **Correct** | Streamable HTTP is the transport for this revision |
| Drop `agentgateway.exe` | **REJECTED** | It is the only chokepoint that sees all five consumers, and 1.4.1 already supports 2026-07-28. See §A.4.1 and §A.6 |
| Progress via `_meta.progressToken` | **Correct** | `notifications/progress` still flows on the originating request's response stream |
| MRTR mentioned in the architecture box | **Correct** | Changelog #7 — `InputRequiredResult` / `resultType: "input_required"` |
| Replace `exec()` with typed Pydantic | **Correct, but not a protocol matter** | Good hygiene; JSON Schema 2020-12 keywords were loosened (minor #10) |
| Resources + Resource Templates + Prompts | **Correct, but not new** | These have existed since 2024-11-05. Framing them as "2026-07-28 modernization" is wrong; they are simply features this PoC never used |

**Bottom line: the plan's spine is accurate.** The protocol version is real, statelessness is real, `server/discover` is real, `ttlMs` is real. This is not a hallucinated spec.

## A.2 Errors

**A.2.1 — Wrong cause attributed to the `asyncio.Lock`.**
Plan says the lock exists because of "global standard I/O synchronization" and that statelessness removes the need for it. Both halves are off:

- The client (`backend/mcp_client/session.py:341`) already talks **Streamable HTTP to the gateway**, not stdio. The docstring says "the stdio session is shared" — that comment is stale in the current repo.
- The lock exists because one long-lived `ClientSession` object is shared across concurrent web requests. Statelessness at the *protocol* layer does not by itself make a shared v1 `ClientSession` re-entrant.

The **action** (remove the lock) is right. The **reason** must be: under 2026-07-28 each call is an independent HTTP POST with no session, so the client can issue calls concurrently — and SDK v2's `Client` is built for that.

**A.2.2 — The "~40% token saving from Resources" figure is invented.**
There is no such number in the spec and no measurement in this repo. Worse, it does not apply to this PoC's own UI at all:

- MCP Resources are consumed by **hosts** (Claude Desktop, Claude Code, IDEs) that let a user attach context.
- This repo's web chat runs an **OpenAI function-calling loop** (`backend/agui_agent/agent.py`). That loop has no concept of MCP resources. Adding `market://` resources changes nothing for the Next.js UI unless the agent is explicitly coded to fetch and inline them.

Keep Resources in scope — they are genuinely useful for the Claude Desktop / IDE story — but state the benefit honestly and drop the number.

**A.2.3 — "Bump the MCP SDK" understates the work by an order of magnitude.**
`mcp` on PyPI is now **2.0.0** (verified). `pip install mcp` installs 2.x. v2 is a rewrite, and it breaks this repo in at least six places:

| v1 (in repo today) | v2 |
| :--- | :--- |
| `from mcp.server.fastmcp import FastMCP` | `from mcp.server import MCPServer` |
| `from mcp.client.streamable_http import streamablehttp_client` | removed spelling; use the unified `Client` |
| `ClientSession(...).initialize()` | `async with Client(target) as client` (auto-negotiates) |
| `tool.inputSchema` | `tool.input_schema` (all attrs snake_case; wire stays camelCase) |
| `result.isError` | `result.is_error` |
| `McpError` | `MCPError` |
| depends on `httpx` | depends on **`httpx2>=2.5.0`** |
| `pydantic>=2.7` OK | requires **`pydantic>=2.12.0`** |

`backend/mcp_client/session.py`, `backend/mcp_server/server.py`, `backend/core/api_tools.py` and `backend/requirements.txt` all break on upgrade. The plan's "Pin/bump MCP SDK in requirements.txt" is one line for what is the single largest work item.

**A.2.4 — Statelessness is not what unlocks concurrency here; the SDK rewrite is.**
Even on 2025-11-25 you could have run concurrent calls with a per-request client. The genuine win is that with no session there is nothing to serialize and nothing to pin to a worker.

## A.3 Gaps — spec changes the plan never mentions

Each of these is a real requirement or removal in 2026-07-28 that this migration will hit.

1. **`resultType` is required on every result** (`"complete"` or `"input_required"`). Clients must treat a missing field from older servers as `"complete"`.
2. **`subscriptions/listen` replaces the HTTP GET stream and `resources/subscribe` / `resources/unsubscribe`.** Clients opt in to `toolsListChanged` / `promptsListChanged` / `resourcesListChanged` / `resourceSubscriptions`.
3. **`Mcp-Session-Id` header is gone.** So is the GET endpoint (respond `405`), and so is `Last-Event-ID` resumability — a broken stream loses the in-flight request and the client must re-issue with a **new request id**.
4. **New required HTTP headers on every POST**: `MCP-Protocol-Version`, `Mcp-Method`, and `Mcp-Name` (for `tools/call`, `resources/read`, `prompts/get`). Header values must match the body or the server returns `400` + `-32020 HeaderMismatch`.
5. **`x-mcp-header`** — servers may mirror tool params into `Mcp-Param-{Name}` headers; **clients MUST support it**, including the `=?base64?…?=` sentinel encoding.
6. **`ping` and `logging/setLevel` removed.** Log level is now per-request via `_meta['io.modelcontextprotocol/logLevel']`, and servers **MUST NOT** emit `notifications/message` for requests that omit it.
7. **Roots, Sampling and Logging are Deprecated** (SEP-2577). Do not build on them.
8. **Error-code changes**: resource-not-found `-32002` → `-32602`; `HeaderMismatch` `-32020`; `MissingRequiredClientCapability` `-32021`; `UnsupportedProtocolVersion` `-32022`.
9. **Tasks moved out of core** into the `io.modelcontextprotocol/tasks` extension (`tasks/get` polling, `tasks/update`; `tasks/list` removed).
10. **`cacheScope`** (`"public"` | `"private"`) is required alongside `ttlMs`.
11. **`extensions` field** added to `ClientCapabilities` / `ServerCapabilities`.
12. **OpenTelemetry `_meta` conventions** (`traceparent`, `tracestate`, `baggage`) — directly relevant, since the UI's whole value proposition is runtime telemetry.
13. **Security requirements the plan omits entirely**: servers **MUST** validate the `Origin` header (DNS-rebinding defence) and **SHOULD** bind to `127.0.0.1` locally. Today both FastAPI apps run `CORSMiddleware(allow_origins=["*"])` — mounting the MCP endpoint into that app as-is would be a regression, not a modernization.

## A.4 Gaps — repo realities the plan ignores

**A.4.1 — The plan's "eliminate agentgateway" goal is rejected. The gateway is a product requirement, not incidental infrastructure.**

agentgateway is the **single chokepoint every MCP consumer passes through** — Claude Desktop, Claude Code, VS Code Copilot, Antigravity, and this repo's own web agent all reach the server through `:3111`. That is precisely what makes centralized observability possible: a tool call made inside a Claude Desktop chat lands in the same log as one made from the web UI. Remove the gateway and each host talks to `/mcp` directly, observability fragments into five blind spots, and the `policy=stock-exchange-allowlist` line the UI displays becomes a lie.

The gateway is also **not a migration blocker**, which was the main technical worry:

- **agentgateway 1.4** was released **2026-07-27**, one day before the spec revision, with 2026-07-28 support as a headline theme; **1.4.1** followed two days later with further compatibility fixes.
- The spec's new required `Mcp-Method` / `Mcp-Name` headers exist specifically so gateways can route and inspect MCP traffic **without parsing the JSON body** — the revision makes gateways cheaper, not obsolete.
- Its multiplex example covers a mix of legacy and new-era MCP servers, so it can front both revisions during the transition.

**D-1 is therefore resolved: keep the gateway, upgrade it, and build the centralized observability the product has always implied but never delivered.** See §A.6 for what actually exists today and Phase 2B for the work.

**A.4.2 — "Native `type: http` for all hosts" is unverified for two of the five consumers.**
The repo's own notes record that Claude Desktop and Antigravity config formats did *not* accept a plain `type: http` entry, which is why `mcp-remote` is there. Claude Code (`.mcp.json`) and VS Code Copilot (`.vscode/mcp.json`) already use `type: http`. Treat "npx dependency eliminated" as a per-host verification task, not a given.

**A.4.3 — Mounting MCP into the Data API process makes the MCP server call itself over loopback HTTP.**
Today `mcp_server/api_client.py` reaches the Data API at `http://127.0.0.1:8000`. If MCP is mounted on that same app, every tool call becomes an HTTP round-trip from a process to itself. Not a deadlock (both async), but pointless latency. **Decision required** (see D-2).

**A.4.4 — The repo is Windows-only today.** `run_all.bat`, `setup.ps1`, `run.ps1`, and `.venv/Scripts/python` in CLAUDE.md. The plan claims cross-platform as an outcome but lists no task for it.

**A.4.5 — Test coverage is one file.** `backend/tests/test_calculations.py` covers pure math only. There is not a single test for the MCP server, the client, the registry, or the Data API. A protocol migration with no protocol tests is not verifiable.

**A.4.6 — No CI, no lint, no formatter.** Confirmed: "No lint/format tooling is configured for the backend."

**A.4.7 — Progress reporting has nowhere to go.** The plan adds `progressToken` to analytics tools, but AG-UI emits `TOOL_CALL_START/ARGS/END/RESULT` only. There is no progress event, and `ActivityPanel.tsx` has no progress UI. Backend progress with no frontend path is invisible work.

## A.5 So what do you actually get?

Honest accounting, since the plan oversells.

**Real wins**

- **Three processes instead of four**, and the Python MCP server stops being a hidden stdio child of the gateway. Backend (FastAPI, one uvicorn) + gateway + frontend. The gateway stays on purpose (§A.4.1); what goes away is the `python -m mcp_server.server` subprocess with hardcoded Windows paths baked into `config.yaml`.
- **Cross-platform.** Nothing left is Windows-specific: `setup.ps1` downloads the `windows-amd64` gateway binary today, but agentgateway ships Linux and macOS builds, and `run_all.bat` / `*.ps1` get replaced by a portable launcher.
- **Centralized observability becomes real** rather than implied — see §A.6. This is arguably the biggest product win in the whole migration, and the original plan would have destroyed it.
- **Real concurrency.** Removing the shared-session lock genuinely fixes serialized web chat — this is the one change your users would feel.
- **`ttlMs` + `cacheScope` + deterministic ordering** cut `tools/list` chatter and improve LLM prompt-cache hit rates across turns.
- **Prompts + Resources** give Claude Desktop / Claude Code one-click workflows this PoC cannot offer today.
- **Stateless** means no session affinity — the thing you would need before this could ever run on more than one worker.
- **Future-proofing.** v1 SDKs get critical patches only; v2 is where the ecosystem is going.

**Not wins (do not put these on a slide)**

- No improvement in answer quality, data accuracy, or model behaviour.
- No token savings in *your own* web UI from Resources unless you code the agent to read them.
- Statelessness buys nothing operationally at PoC scale beyond the concurrency fix.
- Progress reporting is invisible until the AG-UI/UI path is built.

## A.6 Centralized observability — does the project have it today?

**Requirement:** every MCP call, from any consumer, visible in one place in the Control Room UI, showing *where it came from*.

**Verdict: partially. The collection point exists; the attribution and the UI do not.**

| Capability | Today | Evidence |
| :--- | :--- | :--- |
| Single chokepoint all 5 consumers pass through | ✅ | All host configs point at `127.0.0.1:3111`; `mcp_gateway_url` defaults there too |
| Per-call audit line | ✅ | agentgateway writes one line per MCP call to stdout |
| Tool-name allowlist enforced centrally | ✅ | `policies.mcpAuthorization`, 9 rules in `config.yaml` |
| A way to read the log without a terminal | ⚠️ partial | `/gateway-logs` in `data_api/main.py` — a raw `<pre>` tail of `stdout.log` + `stderr.log`, auto-refreshing every 2s |
| **Caller attribution — which host made the call** | ❌ **missing** | Nothing in the config or the log distinguishes Claude Desktop from Antigravity from the web UI. All five arrive as anonymous HTTP POSTs on one route |
| **Observability inside the Control Room UI** | ❌ **missing** | `ActivityPanel.tsx` shows only tool calls from *the current browser conversation*. Calls from Claude Desktop are invisible to it. The nav's `MCP Servers` / `Audit Log` / `Runs` entries in `index(2).html` are dead `href="#"` links |
| Persistence across gateway restarts | ❌ **missing** | `database:` key is commented out in `config.yaml` — "not supported by this build". Log dies with the process |
| Structured (parseable) logs | ❌ **missing** | Plain text tail. Nothing can filter, sort, or aggregate it |
| Metrics / traces | ❌ **missing** | Not configured, though agentgateway supports both |
| Search / filter / correlation | ❌ **missing** | No query surface at all |

**What the 2026-07-28 revision changes here — mostly in your favour:**

1. **`Mcp-Method` and `Mcp-Name` are now required HTTP headers.** The gateway can log and route on method and tool name without parsing the body. Cheaper, and it works even for streamed responses.
2. **`io.modelcontextprotocol/clientInfo` now travels in `_meta` on *every request*.** Previously client identity was announced once, at `initialize`, and had to be remembered against a session. Now every single call self-identifies. **This is the mechanism that gives you "which host called this" per call** — it did not exist per-call before.
3. **But `mcp.session.id` — an agentgateway default log field — becomes meaningless.** Sessions were removed from the transport. Any correlation logic built on session id must move to `clientInfo` + `traceparent`.

**What agentgateway gives you once configured** (currently: none of it is turned on):

- Metric `mcp_requests_total` labelled `server`, `method`, `resource`, `resource_type`
- Structured log fields `mcp.method.name`, `mcp.target`, `mcp.resource.type`, `mcp.resource.uri`, `gen_ai.tool.name`
- CEL-accessible fields `mcp.tool.name`, `mcp.tool.target`, `mcp.tool.arguments`, `mcp.tool.result`, `mcp.tool.error` — so arguments, results and errors can be logged selectively
- OTLP tracing (`tracing.otlpEndpoint`, `randomSampling`) and a Prometheus `/metrics` endpoint
- MCP Auth: authenticate callers and scope which tools each identity may invoke

**Gap to close:** turn all of that on, attach a per-host identity, persist it, and surface it in the UI. That is Phase 2B.

---

# Part B — Ground truth of the current repo

Read from source at `github.com/sarveshtalele/mcp-server-market`, not assumed.

## B.1 Runtime topology (today)

```
frontend :3000  →  agui_agent :8001  →  agentgateway :3111  →  mcp_server (stdio child)  →  data_api :8000  →  SQLite
```

Four processes plus a Node bridge for two of the five MCP hosts.

## B.2 What exists

| Area | Files | Notes |
| :--- | :--- | :--- |
| MCP server | `backend/mcp_server/server.py` | `FastMCP("stock-exchange", instructions=…)`, stdio only, tools registered from module hooks |
| Tool generation | `backend/core/api_tools.py` | `EndpointTool` dataclass → source string → **`exec()`** → `mcp.tool()` |
| Module registry | `backend/core/registry.py` | `ModuleSpec(router, register_tools, seed, priority)`; `discover_modules()` auto-imports `modules/*` |
| Modules | `listings`, `filings`, `analytics` | 3 + 2 endpoint tools, 4 hand-written analytics tools |
| MCP client | `backend/mcp_client/session.py` | `streamablehttp_client` + `ClientSession.initialize()` + **`asyncio.Lock`**, TCP pre-probe |
| Agent | `backend/agui_agent/agent.py` | Single `ExchangeAgent`, OpenAI-compatible LLM, `MAX_TOOL_ROUNDS = 6`, emits AG-UI events + one `CUSTOM` usage event |
| Data API | `backend/data_api/main.py` | Auto-mounts module routers, `/health`, `/gateway-logs` |
| Frontend | `frontend/` | Next.js App Router, `AppShell` / `ChatView` / `ActivityPanel`, 7 generative tool cards, localStorage conversations |
| Tests | `backend/tests/test_calculations.py` | Pure-math only |

## B.3 The 9 tools

`get_company`, `search_companies`, `list_sectors` (listings) · `get_filings`, `get_latest_filing` (filings) · `calc_financial_ratios`, `calc_revenue_growth`, `compare_companies`, `sector_ranking` (analytics).

## B.4 Facts that constrain the migration

- Data is **synthetic** — `Faker`, `SEED = 2025`, deterministic. Migration must not change a single seeded value.
- Everything logs to **stderr only**; stdout is the stdio JSON-RPC channel.
- The frontend tracks **two independent timings**: client-measured per-tool `ms`, and backend-measured `elapsedMs` + token usage via the `CUSTOM` event. Do not conflate them.
- The server ships an `instructions` string that is advisory; real enforcement is `SYSTEM_PROMPT` in the agent.
- There is **no multi-agent orchestration**. `DESIGN.md` and `index(2).html` both depict Planner / Research / Synthesis agents that do not exist. This is fixed in the updated `DESIGN.md`.

---

# Part C — Final migration plan

## C.0 Decisions needed before Phase 1

| # | Decision | Options | Recommendation |
| :--- | :--- | :--- | :--- |
| **D-1** | Keep agentgateway? | — | **RESOLVED: keep it.** It is the only chokepoint that sees calls from all five consumers, and 1.4.1 already speaks 2026-07-28. See §A.4.1. |
| **D-1a** | How the gateway reaches the MCP server | (a) keep spawning `python -m mcp_server.server` as a stdio child, (b) point the gateway at the backend's `/mcp` Streamable HTTP endpoint | **(b)** — deletes the hardcoded `C:\Users\…` paths from `config.yaml`, makes the gateway config portable, and lets the backend restart without restarting the gateway |
| **D-1b** | How each host is identified in the log | (a) `io.modelcontextprotocol/clientInfo` from `_meta` (now on every request), (b) one gateway listener/route per consumer, (c) MCP Auth token per host | **(a) + (b)** — `clientInfo` is free and automatic; a per-consumer route is the fallback for hosts that send a generic or absent `clientInfo`. Add (c) only if the demo needs to show authorization, not just attribution |
| **D-1c** | Audit persistence | (a) retry the gateway's `database:` key on 1.4.1, (b) ingest the gateway's structured JSON log into the backend's SQLite | **(b)** — the log file is the gateway's contract; parsing it is version-proof, and it puts the data where the UI can query it. Try (a) first; it is one line if it now validates |
| **D-2** | How the MCP server reaches data once co-hosted | (a) keep loopback HTTP, (b) call the repository layer directly, (c) MCP in its own process on :8002 | **(b)** — drops a pointless hop; repositories are already separated. Data API stays for REST consumers and `/docs`. |
| **D-3** | Legacy protocol support window | (a) 2026-07-28 only, (b) serve both revisions | **(b)** — SDK v2 does this with zero config; costs nothing, keeps older hosts working. |
| **D-4** | Keep the OpenAI function-calling loop or move to a native MCP agent | (a) keep, (b) rewrite | **(a)** — out of scope. Migration is protocol-only. |
| **D-5** | Scope of progress reporting | (a) skip, (b) backend + AG-UI + UI end-to-end | **(b)** if `compare_companies` over many tickers is the demo; otherwise **(a)**. |

## C.1 Target topology

```
  Claude Desktop   Claude Code   VS Code Copilot   Antigravity      Next.js UI :3000
        │               │              │                │                  │
        │               │              │                │                  │ AG-UI SSE
        │               │              │                │          ┌───────▼────────┐
        │               │              │                │          │ AG-UI agent    │
        │               │              │                │          │ (in backend)   │
        └───────────────┴──────┬───────┴────────────────┘          └───────┬────────┘
                               │  Streamable HTTP, MCP 2026-07-28          │
                    ┌──────────▼──────────────────────────────────────────▼──────┐
                    │  agentgateway :3111   ← THE single chokepoint              │
                    │    • tool allowlist (mcpAuthorization)                     │
                    │    • per-call audit: method, tool, args, result, latency   │
                    │    • caller attribution via _meta clientInfo (D-1b)        │
                    │    • OTLP traces + Prometheus /metrics                     │
                    └──────────┬────────────────────────────────────────────────┘
                               │  Streamable HTTP (D-1a — no more stdio child)
┌──────────────────────────────▼─────────────────────────────────────────────────┐
│  FastAPI / uvicorn :8000                                                       │
│    /mcp            MCP 2026-07-28 · server/discover · tools · resources · prompts
│    /agui           AG-UI agent (lock-free MCP client → back out through :3111)  │
│    /listings /filings   REST                                                   │
│    /observability  gateway log ingester + query API for the UI                 │
└──────────────────────────────┬─────────────────────────────────────────────────┘
                               │ direct repository calls (D-2)
┌──────────────────────────────▼─────────────────────────────────────────────────┐
│  SQLite  stock_market.db (Faker, SEED = 2025)  +  observability.db (audit)      │
└────────────────────────────────────────────────────────────────────────────────┘
```

Three commands: the gateway, `uvicorn app.main:app --port 8000`, and `npm run dev`.

**Note the loop:** the web agent deliberately goes *out* to `:3111` and back rather than calling `/mcp` in-process. That extra hop is the price of having the web UI's own tool calls appear in the same audit log as every other host — which is the whole point. Do not "optimize" it away.

## C.2 Phases

### Phase 0 — Baseline & safety net *(before touching any protocol code)*

- [ ] Freeze a golden snapshot: `tools/list` output, and the JSON result of all 9 tools for a fixed symbol set (`AAPL`, `JPM`, `BAC`, `WFC`, `MSFT`, `NVDA`).
- [ ] Add characterization tests asserting the snapshot byte-for-byte — this is the migration's regression net.
- [ ] Add `pytest-asyncio`, `ruff`, and a GitHub Actions workflow (lint + test).
- [ ] Verify seeded data is unchanged after a `--reset` (deterministic Faker).
- [ ] Tag the current state `pre-2026-migration`.

**Exit:** `pytest` green on a clean clone; snapshot committed.

### Phase 1 — SDK v2 upgrade *(the real work; A.2.3)*

- [ ] `requirements.txt`: `mcp>=2.0,<3`, `pydantic>=2.12`, `pydantic-settings` bumped to a 2.12-compatible release, resolve `httpx` vs `httpx2` (SDK pulls `httpx2>=2.5.0`).
- [ ] `mcp_server/server.py`: `FastMCP` → `MCPServer`, keep `instructions`.
- [ ] `core/api_tools.py`: delete `exec()`; build tools from typed callables / Pydantic models.
- [ ] `core/registry.py`: update the `FastMCP` type hint in `ModuleSpec`.
- [ ] `mcp_client/session.py`: `streamablehttp_client` + `ClientSession` + `initialize()` → unified `Client`; **delete `asyncio.Lock`**; delete `_wait_for_port` if `Client` handles connect failure cleanly (verify, do not assume).
- [ ] Rename every camelCase SDK attribute: `inputSchema` → `input_schema`, `isError` → `is_error`, `nextCursor` → `next_cursor`.
- [ ] `McpError` → `MCPError`.
- [ ] Migrate `mcp_server/api_client.py` off `httpx` if `httpx2` coexistence proves messy.

**Exit:** all 9 tools return byte-identical results to the Phase 0 snapshot, via the gateway, unchanged topology.

### Phase 2 — Transport & decoupling

- [ ] Mount the MCP ASGI app on FastAPI at `/mcp` (`streamable_http_app(mcp)` — verify the exact export against the installed 2.0.0).
- [ ] Merge Data API + MCP + AG-UI into one uvicorn app (single `app/main.py`).
- [ ] Implement **D-2**: tools call repositories directly; keep REST routers for external consumers.
- [ ] **Security (A.3.13)**: validate `Origin` on `/mcp`, bind `127.0.0.1`, replace `allow_origins=["*"]` with an explicit origin list.
- [ ] Return `405` on GET/DELETE to `/mcp`; ignore any `Mcp-Session-Id` and `Last-Event-ID`.
- [ ] Keep `backend/mcp_server/gateway/` — **do not delete it** (§A.4.1). Keep `settings.mcp_gateway_url`; the agent still routes through `:3111`.
- [ ] Replace `run_all.bat` / `*.ps1` with a cross-platform launcher that starts gateway + backend + frontend in order — **A.4.4**.
- [ ] `setup.ps1` → a portable download script that picks the right agentgateway binary for the host OS.

**Exit:** one backend process behind the gateway; `curl` a `tools/call` at `:3111/mcp` with correct headers and get a result served by `:8000/mcp`.

### Phase 2B — Gateway upgrade & centralized observability *(new; §A.6)*

This phase delivers the requirement the product has always displayed but never had: **every MCP call, from every host, in one UI, with its source.**

**Gateway**
- [ ] Upgrade to agentgateway **≥ 1.4.1** (1.4 shipped 2026-07-27 with 2026-07-28 support; 1.4.1 added compatibility fixes).
- [ ] Implement **D-1a**: replace the `stdio:` target with an HTTP target pointing at `http://127.0.0.1:8000/mcp`. Delete the hardcoded `C:\Users\SarveshTalele\…` `cmd` / `PYTHONPATH` from `config.yaml`.
- [ ] Verify the allowlist still enforces all 9 tool rules against a 2026-07-28 client.
- [ ] Confirm the gateway forwards `Mcp-Method` / `Mcp-Name` and the `_meta` block untouched.
- [ ] Tighten `policies.cors`: drop `"*"`, drop `mcp-session-id` from `allowHeaders` / `exposeHeaders` (no sessions in this revision).

**Telemetry**
- [ ] Enable structured JSON access logging with fields: `mcp.method.name`, `mcp.target`, `mcp.resource.type`, `mcp.resource.uri`, `gen_ai.tool.name`.
- [ ] Add CEL log fields for `mcp.tool.name`, `mcp.tool.target`, `mcp.tool.arguments`, `mcp.tool.error` — truncate arguments; **do not log `mcp.tool.result` wholesale** (it carries the full payload).
- [ ] Drop `mcp.session.id` from the log schema — meaningless under this revision (§A.6).
- [ ] Enable OTLP tracing (`randomSampling: true` locally) and expose Prometheus `/metrics`.
- [ ] Propagate `traceparent` from `_meta` so a UI row links to a trace.

**Caller attribution — D-1b**
- [ ] Log `io.modelcontextprotocol/clientInfo` (name + version) as `caller.name` / `caller.version` on every call.
- [ ] Record the empirical `clientInfo` each host actually sends — Claude Desktop, Claude Code, VS Code Copilot, Antigravity, and our own agent. **Measure it; do not assume.**
- [ ] Set an explicit, distinctive `clientInfo` on our own agent's client so the web UI is unambiguous.
- [ ] For any host sending a generic or empty `clientInfo`, give it a dedicated gateway route/listener and derive the source from the route.
- [ ] Fall back to a `source=unknown` label rather than guessing — an unattributed call must look unattributed.
- [ ] **Conversation attribution (partial by design):** MCP defines no conversation id in any revision, so external hosts cannot supply one. Inject our own web agent's conversation id into `_meta` via OpenTelemetry `baggage`, log it as `conversation_id`, and render it as `n/a` for every other source.
- [ ] Preserve unrecognized `_meta` keys on the audit record, so a host that later starts sending its own conversation identifier is captured without a code change.
- [ ] Group unattributed calls into **episodes** by `(source, idle gap)` — a reading aid, labelled `episode`, never `chat`. Threshold is configuration.
- [ ] **Do not** downgrade the protocol to recover `Mcp-Session-Id`: it identifies a connection, not a conversation, and the trade costs per-call `clientInfo` attribution. See SPECS OBS-2a.

**Persistence & query API — D-1c**
- [ ] Try the gateway's `database:` key on 1.4.1; if it still fails validation, ingest instead.
- [ ] Backend ingester tails the gateway's JSON log into `observability.db` (`mcp_calls` table: ts, caller, method, tool, args_preview, status, latency_ms, error_code, trace_id).
- [ ] `GET /observability/calls` — paginated, filterable by caller / tool / status / time window.
- [ ] `GET /observability/summary` — counts by caller, by tool, error rate, p50/p95 latency.
- [ ] `GET /observability/stream` — SSE of new calls so the UI updates live.
- [ ] Retire `/gateway-logs` once the structured view is at parity; keep `/gateway-logs/raw` as the escape hatch.
- [ ] Retention policy: cap rows / age so the PoC DB does not grow unbounded.

**Exit:** run a tool from Claude Desktop, one from Antigravity, and one from the web chat; all three appear in `GET /observability/calls`, each tagged with its correct source.

### Phase 3 — Protocol conformance

- [ ] Verify `server/discover` answers with `supportedVersions`, `capabilities`, `_meta.io.modelcontextprotocol/serverInfo`, `instructions`, `ttlMs`, `cacheScope` (SDK should supply this — assert it, do not trust it).
- [ ] Deterministic `tools/list` ordering — sort by name, assert in a test.
- [ ] `ttlMs` (1 h) + `cacheScope` on `tools/list`, `prompts/list`, `resources/list`, `resources/read`, `resources/templates/list` — **A.1 / A.3.10**.
- [ ] Assert `resultType: "complete"` on results — **A.3.1**.
- [ ] Client: send `MCP-Protocol-Version`, `Mcp-Method`, `Mcp-Name` on every POST; handle `-32020` — **A.3.4**.
- [ ] Client: handle `-32022 UnsupportedProtocolVersion` by retrying with an advertised version — **A.3.8**.
- [ ] Client: support `x-mcp-header` incl. base64 sentinel (MUST, even if no tool uses it) — **A.3.5**.
- [ ] Handle resource-not-found as `-32602`, not `-32002` — **A.3.8**.
- [ ] Remove any `ping` / `logging/setLevel` usage; adopt per-request `_meta` log level — **A.3.6**.
- [ ] Do not add Roots / Sampling / Logging — **A.3.7**.
- [ ] Decide on `subscriptions/listen`: not needed for a static tool surface. **Document the decision**, do not silently skip it — **A.3.2**.
- [ ] Add `traceparent` propagation into `_meta` and surface the trace id in the UI's request-metadata panel — **A.3.12**.

**Exit:** a conformance test file passes; every checkbox above has an assertion or a written "N/A because…".

### Phase 4 — Resources & Prompts

- [ ] Resource templates: `market://companies/{symbol}`, `market://filings/{symbol}/{period}`, `market://filings/{symbol}/latest`.
- [ ] Static resources: `market://sectors`, `market://companies`.
- [ ] Prompts: `analyze-equity` (symbol → profile + latest filing + ratios memo), `compare-stocks` (symbols → side-by-side valuation memo).
- [ ] RFC 6570 template compliance is strict in SDK v2 — test path-traversal rejection.
- [ ] **Honest scoping**: these serve Claude Desktop / Claude Code. If they must show up in the web UI too, add a task to make the agent read resources — otherwise the UI is unaffected (**A.2.2**).

**Exit:** `resources/templates/list` and `prompts/list` return the declared set; a Claude Desktop session can attach `market://companies/AAPL` and run `analyze-equity`.

### Phase 5 — Host integrations

Every host keeps pointing at the **gateway** (`http://127.0.0.1:3111/mcp`), never directly at `:8000/mcp` — otherwise that host disappears from the audit log.

- [ ] `.mcp.json` (Claude Code) — already `type: http` at `:3111/mcp`; verify against 1.4.1.
- [ ] `.vscode/mcp.json` — same.
- [ ] **Verify** whether Claude Desktop now accepts native HTTP; keep `mcp-remote` only if it does not — **A.4.2**.
- [ ] Same verification for Antigravity (`integrations/antigravity.mcp.example.json`).
- [ ] Record each host's observed `clientInfo` string in `CLAUDE.md` (feeds D-1b).
- [ ] Add a guard: if any host is found configured straight to `:8000/mcp`, treat it as a defect — its calls are invisible. (This has already happened once: `claude_desktop_config.json` silently reverted to a direct stdio entry and routed around the gateway entirely.)

**Exit:** each of the 5 host configs points at the gateway, and each one's calls are attributable in the observability API.

### Phase 6 — UI alignment

- [ ] Implement the updated `DESIGN.md`: protocol badge, capability surface, cache/TTL indicator, resource + prompt chips, corrected single-orchestrator run timeline, trace id.
- [ ] **Fleet Activity panel** in the right rail: live feed of MCP calls from *all* hosts, each row tagged with its source, clearly separated from "this conversation's" tool calls.
- [ ] **Audit Log route** — make the dead `Audit Log` nav link real: full-page table over `/observability/calls` with filters (caller, tool, status, time), expandable argument/error inspection, and a caller breakdown.
- [ ] **MCP Servers route** — make that dead link real too: gateway status, target health, allowlist contents, protocol version, connected callers seen in the last hour.
- [ ] Remove every `Mcp-Session-Id` reference from the UI; **keep** the gateway in request metadata — it is in the path.
- [ ] Token meter: hide the "cached" cell when the provider does not report it — the backend currently supplies only prompt/completion/total (**DESIGN.md fix**).
- [ ] **D-5**: if progress is in scope, add an AG-UI progress event + a progress bar on running tool rows.
- [ ] Map protocol errors to specific UI copy: `-32020`, `-32022`, `-32602`.

**Exit:** the UI shows nothing that does not exist in the backend, and every backend signal has a home in the UI.

## C.3 Test plan

| Layer | What | Where |
| :--- | :--- | :--- |
| Unit | `core/calculations.py` — unchanged | `tests/test_calculations.py` (exists) |
| Golden | 9 tools × 6 symbols, byte-identical pre/post | `tests/test_golden_tools.py` (Phase 0) |
| Registry | `discover_modules()` finds 3 modules, priority order | `tests/test_registry.py` |
| Conformance | `server/discover` shape, deterministic ordering, `ttlMs` + `cacheScope`, `resultType`, `405` on GET, `Origin` rejection, header mismatch → `-32020` | `tests/test_protocol_conformance.py` |
| Client | header construction, `x-mcp-header` encoding, `-32022` retry, no lock | `tests/test_mcp_client.py` |
| Resources | template resolution, path-traversal rejection, not-found → `-32602` | `tests/test_resources.py` |
| Prompts | `prompts/list`, `prompts/get` renders arguments | `tests/test_prompts.py` |
| Concurrency | 10 parallel `tools/call` complete without serialization (assert wall-clock < sum of individual) | `tests/test_concurrency.py` |
| Gateway routing | allowlist blocks an unlisted tool; `Mcp-Method` / `Mcp-Name` / `_meta` survive the hop intact | `tests/test_gateway.py` |
| Observability | every call produces exactly one audit row; `caller` is correct for a known `clientInfo`; unknown → `source=unknown`; args truncated; results not logged | `tests/test_observability.py` |
| Observability API | `/observability/calls` filters by caller / tool / status; `/summary` counts match the rows; `/stream` emits on new calls | `tests/test_observability_api.py` |
| Ingester | restarting the gateway does not lose previously ingested rows; duplicate lines are not double-ingested | `tests/test_ingester.py` |
| E2E smoke | boot app, `server/discover`, call one tool per module, read one resource | `tests/test_smoke.py` |
| E2E multi-host | drive a call from two distinct `clientInfo` identities; both appear with correct sources | `tests/test_multi_host.py` |

Definition of done for the migration: **every box in C.2 ticked, every row in C.3 green, and `DESIGN.md` claims all backed by real backend signals.**

## C.4 Risks

| Risk | Impact | Mitigation |
| :--- | :--- | :--- |
| SDK v2 API differs from the migration guide in specifics | Phase 1 stalls | Read the installed package's own docs/source first; the guide is a summary |
| `httpx` / `httpx2` coexistence conflicts | Import-time breakage | Migrate `api_client.py` to `httpx2`; or moot under D-2 (direct repository calls) |
| `pydantic-settings` incompatible with `pydantic>=2.12` | Config layer breaks | Pin a compatible pair in Phase 1; `core/config.py` is the only consumer |
| Claude Desktop / Antigravity still need `mcp-remote` | "No npx" goal unmet | Accept and document; not a blocker |
| `mcp-remote` rewrites or drops `_meta.clientInfo`, so bridged hosts arrive unattributed | Two of five hosts show `source=unknown` | Fall back to D-1b option (b): a dedicated gateway route per bridged host. Verify early — this is the single biggest risk to the observability goal |
| agentgateway 1.4.x behaves differently from the 1.x build currently pinned | Config no longer validates | Upgrade in its own commit, before Phase 2's target change; re-test the allowlist first |
| Gateway still rejects the `database:` key | No persistence | D-1c option (b) — the log ingester, which is the recommended path anyway |
| Logging `mcp.tool.result` leaks whole payloads into the audit DB | DB bloat, noisy UI | Log a truncated preview only; full results stay in the conversation |
| A host gets reconfigured to hit `:8000/mcp` directly | Silent observability hole | Phase 5 guard + a UI warning when a tool call has no matching audit row |
| Golden output drifts because tool return shapes change | Silent data regression | Phase 0 snapshot is the gate |
| Scope creep into agent redesign | Timeline blows out | D-4 says no |

## C.5 Rollback

Every phase is a separate commit on a `feat/mcp-2026-07-28` branch. `pre-2026-migration` tag is the escape hatch. Phases 0–1 are reversible with `git revert`. Do not merge Phase 2 until Phase 1's golden tests are green. See also C.7.

## C.6 Sequencing note

The original plan's 8-day / 4-step schedule underestimates Phase 1. Realistic split, assuming one developer:

| Phase | Effort |
| :--- | :--- |
| 0 — baseline | 0.5 day |
| 1 — SDK v2 | 2–3 days |
| 2 — transport & decoupling | 1.5 days |
| 2B — gateway upgrade & centralized observability | 2–3 days |
| 3 — conformance | 1.5 days |
| 4 — resources & prompts | 1 day |
| 5 — host integrations | 0.5 day |
| 6 — UI alignment (incl. Audit Log + MCP Servers routes) | 2.5 days |

~12–14 days, versus the original plan's 8 — and that 8 assumed a one-line SDK bump and deleted the observability layer rather than building it.

## C.7 Rollback note for Phase 2B

Phase 2 no longer contains a point of no return, because the gateway is not deleted. The new irreversible step is the `config.yaml` target switch (stdio child → HTTP). Keep the old stdio target commented in the file for one release so a revert is a two-line edit.
