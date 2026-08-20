# IMPLEMENTATION_PLAN.md

Execution plan for migrating `mcp-server-market` to MCP **2026-07-28** with centralized observability and a rebuilt Control Room UI.

Status: **awaiting go-ahead to start MCP-001.** No implementation code written yet.

Companion docs: [MIGRATION_PLAN.md](MIGRATION_PLAN.md) (why) · [SPECS.md](SPECS.md) (acceptance criteria) · [CLAUDE.md](CLAUDE.md) (ground truth + SDLC) · [DESIGN.md](DESIGN.md) (UI spec)

---

## 1. Locked decisions

| ID | Decision | Consequence |
| :--- | :--- | :--- |
| **D-1** | agentgateway **retained** | It is the chokepoint that makes cross-host observability possible |
| **D-1a** | Gateway targets `http://127.0.0.1:8000/mcp` over HTTP | `stdio:` target and all `C:\Users\…` paths leave `config.yaml` |
| **D-1b** | Attribution via `_meta` `clientInfo`, **per-route fallback** | Hosts that send nothing usable get a dedicated gateway listener |
| **D-1c** | Audit persisted by **ingesting the gateway's JSON log into SQLite** | The UI owns the schema it queries |
| **D-2** | MCP tools call **repositories directly** | `DataAPIClient` leaves the tool path; golden tests are the safety net |
| **D-3** | **`2026-07-28` only** — no legacy handshake | See §1.1. Spike MCP-701 first |
| **D-4** | AG-UI agent keeps its OpenAI tool loop | Migration is protocol-only |
| **D-5** | Progress reporting **in scope, end to end** | Server → client → AG-UI → UI |
| **Platform** | Windows primary; developed on macOS | Gateway-dependent tests do not run in CI on macOS — see §5.4 |
| **UI** | Next.js rebuilt to the Control Room structure of `index(2).html` | `lib/agui.ts`, `lib/store.ts`, the 7 tool cards are carried over |
| **E2E** | Real LLM proxy available | A small, marked set of e2e tests may drive the real model |

### 1.1 Consequence of D-3 that must be resolved first

Rejecting pre-`2026-07-28` clients is safe for Claude Code and VS Code Copilot, which connect natively. It is **not** obviously safe for Claude Desktop and Antigravity, which connect through `npx mcp-remote`. If that bridge speaks only the legacy handshake, both hosts break outright.

`MCP-701` is a spike scheduled **before** any host config is finalized, with three possible outcomes:

1. `mcp-remote` already speaks `2026-07-28` → nothing to do.
2. The gateway can absorb a legacy client and re-emit modern requests upstream → backend stays `2026-07-28`-only, compatibility lives at the gateway. **Preferred.**
3. Neither → escalate. The one-line fallback is to let SDK v2 serve both revisions, reverting D-3 only for the two bridged hosts.

Do not finalize `EPIC 7` until MCP-701 reports.

---

## 2. SDLC workflow for this build

### 2.1 Branch and PR model

```
main
 └── feat/mcp-2026-07-28          integration branch for the whole migration
      ├── feat/p0-baseline        EPIC 0
      ├── feat/p1-sdk-v2          EPIC 1
      ├── feat/p2-transport       EPIC 2
      ├── feat/p2b-observability  EPIC 3
      ├── feat/p3-conformance     EPIC 4
      ├── feat/p4-resources       EPIC 5
      ├── feat/p5-progress        EPIC 6
      ├── feat/p6-hosts           EPIC 7
      └── feat/p7-control-room    EPIC 8
```

One epic per branch, one ticket per commit. Epic branches merge into `feat/mcp-2026-07-28`; that merges to `main` once EPIC 9 passes.

### 2.2 Per-ticket cycle

```
Read spec (SPECS.md §) → write failing test → implement → self-review (CLAUDE.md §8.3) → commit → CI green
```

A commit that changes behaviour without touching a test is rejected at review.

### 2.3 Commit convention

```
<type>(<scope>): <subject>        # feat, fix, chore, test, docs, refactor
MCP-123
```

Example: `refactor(api_tools): replace exec() with typed tool builder` / body references `MCP-103` and `SPECS TOOL-1.4`.

### 2.4 PR gate — every epic branch

- [ ] All tickets in the epic closed
- [ ] `ruff check .` clean
- [ ] `pytest` green (excluding `@pytest.mark.gateway` / `@pytest.mark.llm` on macOS)
- [ ] Golden tests unchanged, or a deliberate, documented, approved diff
- [ ] Spec sections referenced in the PR body, each with its test name
- [ ] `CLAUDE.md` §7 checkboxes ticked for what actually landed
- [ ] Docs updated in the same PR when architecture, commands, or the tool surface changed
- [ ] Windows verification matrix rows executed for anything gateway-dependent (§6)

### 2.5 Definition of done (per ticket)

1. Named spec criteria pass.
2. Test exists, is named in the ticket, and fails without the change.
3. No new `exec`, no stdout writes, no fabricated UI values.
4. Invariants in `CLAUDE.md` §2 hold — including #7, no consumer bypasses the gateway.
5. Ticket checkbox ticked here and in `CLAUDE.md` §7.

---

## 3. Environment setup (MCP-001 … MCP-004)

### MCP-001 — Python toolchain

Files: `backend/requirements.txt`, new `backend/requirements-dev.txt`, new `backend/pyproject.toml`

- `requirements-dev.txt`: `pytest>=8`, `pytest-asyncio>=0.24`, `pytest-cov`, `ruff`, `respx` or equivalent HTTP stub, `freezegun`
- `pyproject.toml`: `[tool.ruff]` (line length 100, target py310), `[tool.pytest.ini_options]` with `asyncio_mode = "auto"` and custom markers `gateway`, `llm`, `windows`
- Python floor stays 3.10 (SDK v2 requires ≥3.10)

**Test:** `ruff check .` and `pytest --collect-only` both succeed.

### MCP-002 — Frontend toolchain

Files: `frontend/package.json`, `frontend/vitest.config.ts`

- Add `vitest`, `@testing-library/react`, `@testing-library/user-event`, `jsdom`
- Scripts: `test`, `test:watch`, keep `lint`

**Test:** `npm run test` runs zero tests successfully.

### MCP-003 — CI

File: `.github/workflows/ci.yml`

- Matrix `ubuntu-latest` + `windows-latest`, Python 3.11, Node 20
- Steps: install → `ruff check` → `pytest -m "not gateway and not llm"` → `npm ci` → `npm run lint` → `npm run test`
- Gateway and LLM jobs are **manual dispatch only**, not on every push

**Test:** workflow green on a no-op commit.

### MCP-004 — Baseline tag

- Tag current `main` as `pre-2026-migration` before any behavioural change.

---

## 4. Work breakdown

Effort is one developer. Every ticket lists the files it touches, so two people can work different epics without collisions.

### EPIC 0 — Baseline & safety net · `feat/p0-baseline` · 1 day

| Ticket | Work | Files | Test | Spec |
| :--- | :--- | :--- | :--- | :--- |
| **MCP-010** | Seed determinism harness: reset twice, diff row sets | `backend/tests/test_seed.py` | `test_seed_determinism`, `test_seed_constants`, `test_market_cap_identity` | DATA-1 |
| **MCP-011** | Golden fixture generator: 9 tools × 6 symbols (`AAPL`, `JPM`, `BAC`, `WFC`, `MSFT`, `NVDA`) → `tests/golden/*.json`, committed | `backend/tests/conftest.py`, `backend/tests/golden/` | generator is itself a test | TOOL-1.2 |
| **MCP-012** | Characterization tests asserting each tool byte-for-byte against its golden file | `backend/tests/test_golden_tools.py` | `test_golden_tools` | TOOL-1.1/1.2 |
| **MCP-013** | Registry tests incl. a fixture module added at test time | `backend/tests/test_registry.py` | `test_registry`, `test_registry_zero_touch` | REG-1 |
| **MCP-014** | `tools/list` snapshot (names + schemas), committed | `backend/tests/golden/tools_list.json` | `test_tool_schemas` | TOOL-1.3 |

**Exit:** `pytest` green on a clean clone. Golden files committed. **These fixtures are the contract for every later epic.**

### EPIC 1 — SDK v2 upgrade · `feat/p1-sdk-v2` · 3 days

The largest and riskiest epic. Nothing else starts until golden tests pass again at the end of it.

| Ticket | Work | Files | Test | Spec |
| :--- | :--- | :--- | :--- | :--- |
| **MCP-101** | Dependency bump: `mcp>=2.0,<3`, `pydantic>=2.12`, compatible `pydantic-settings`. SDK v2 pulls `httpx2>=2.5.0` | `backend/requirements.txt` | import smoke test | — |
| **MCP-102** | `FastMCP` → `MCPServer`; keep `INSTRUCTIONS` verbatim | `backend/mcp_server/server.py` | `test_smoke` | MCP-2.5 |
| **MCP-103** | Delete `exec()`. Rebuild `EndpointTool` into a typed builder that constructs real callables with annotations. **See §4.1 for the sync-vs-async note.** | `backend/core/api_tools.py` | `test_no_exec`, `test_tool_schemas`, `test_golden_tools` | TOOL-1.3/1.4 |
| **MCP-104** | `ModuleSpec` type hints: `FastMCP` → `MCPServer` | `backend/core/registry.py` | `test_registry` | REG-1 |
| **MCP-105** | Client rewrite: unified `Client`, no `initialize()`, **`asyncio.Lock` deleted**. Re-verify whether `_wait_for_port` is still needed under v2's connect semantics — **test it, do not assume** | `backend/mcp_client/session.py` | `test_mcp_client`, `test_concurrency` | CLI-1 |
| **MCP-106** | snake_case sweep: `inputSchema`→`input_schema`, `isError`→`is_error`, `nextCursor`→`next_cursor`; `McpError`→`MCPError` | `backend/mcp_client/session.py`, `backend/agui_agent/agent.py` | existing tests | — |
| **MCP-107** | Retire `DataAPIClient` from tool paths (superseded by D-2 in MCP-201); removes the `httpx`/`httpx2` conflict | `backend/mcp_server/api_client.py` | `test_golden_tools` | — |
| **MCP-108** | **Gate:** golden tests byte-identical to EPIC 0 output | — | `test_golden_tools` | TOOL-1.2 |

#### 4.1 Design note — sync tools on worker threads

SDK v2 runs plain `def` handlers on worker threads rather than the event loop. The repositories are synchronous SQLAlchemy. Defining data tools as **sync** functions therefore lets the SDK move blocking DB work off the loop with no manual `to_thread` plumbing. Analytics tools that fan out over several symbols stay async and dispatch concurrently. Decide per tool in MCP-103/MCP-201 and record the reason in the docstring.

### EPIC 2 — Transport & single process · `feat/p2-transport` · 2 days

| Ticket | Work | Files | Test | Spec |
| :--- | :--- | :--- | :--- | :--- |
| **MCP-201** | **D-2:** tools call repositories directly. `ModuleSpec.register_tools` second argument changes from `DataAPIClient` to a session provider — a contract change, so all three modules and the module guide update together | `backend/core/registry.py`, `backend/core/api_tools.py`, `backend/modules/*/tools.py`, `backend/modules/README.md` | `test_golden_tools`, `test_tool_error_paths` | TOOL-1.2/1.5 |
| **MCP-202** | Unified ASGI app: mount MCP at `/mcp`, AG-UI at `/agui`, module routers, health | new `backend/app/main.py` | `test_smoke` | MCP-1.1 |
| **MCP-203** | Security: validate `Origin` on `/mcp`, bind `127.0.0.1`, replace `allow_origins=["*"]` with an explicit list | `backend/app/main.py` | `test_security` | MCP-1.5/1.6 |
| **MCP-204** | Transport hygiene: `405` on GET/DELETE to `/mcp`; ignore `Mcp-Session-Id` and `Last-Event-ID`; `X-Accel-Buffering: no` on SSE | `backend/app/main.py` | `test_protocol_conformance` | MCP-1.2/1.3/1.4/1.7 |
| **MCP-205** | Config cleanup: keep `mcp_gateway_url`, drop dead settings, no absolute paths | `backend/core/config.py` | `test_config` | PLAT-1.3 |
| **MCP-206** | Launcher: `run_all.bat` updated for the new process list (Windows primary) plus a portable `scripts/dev.py` fallback | `run_all.bat`, new `scripts/dev.py` | manual | PLAT-1.1/1.2 |

**Exit:** one backend process serves REST + MCP + AG-UI; conformance basics pass against `/mcp` directly.

### EPIC 3 — Gateway & centralized observability · `feat/p2b-observability` · 3 days

The product-differentiating epic.

| Ticket | Work | Files | Test | Spec |
| :--- | :--- | :--- | :--- | :--- |
| **MCP-301** | Upgrade agentgateway to ≥ 1.4.1; make the download script pick the right binary per OS | `backend/mcp_server/gateway/setup.ps1`, new `scripts/get_gateway.py` | manual (§6) | GOV-2.1 |
| **MCP-302** | **D-1a:** `stdio:` target → HTTP target at `http://127.0.0.1:8000/mcp`; delete absolute paths; keep old block commented one release | `backend/mcp_server/gateway/config.yaml` | `test_gateway_config` | GOV-2.4 |
| **MCP-303** | CORS tighten: drop `"*"`, drop `mcp-session-id` from allow/expose headers | `.../config.yaml` | `test_gateway_config` | GOV-2.5 |
| **MCP-304** | Allowlist re-verified against a 2026-07-28 client; assert config list == `tools/list` | `.../config.yaml` | `test_gateway_config`, `test_gateway` | GOV-3 |
| **MCP-305** | Telemetry config: structured JSON access log (`mcp.method.name`, `mcp.target`, `mcp.resource.type`, `mcp.resource.uri`, `gen_ai.tool.name`), CEL fields for `mcp.tool.name`/`arguments`/`error`, **no `mcp.tool.result`**, **no `mcp.session.id`**; OTLP tracing; `/metrics` | `.../config.yaml` | `test_observability` | OBS-1, OBS-5 |
| **MCP-306** | New `observability` module — honours the registry contract like any domain module: `models.py` (`mcp_calls`), `repository.py`, `router.py`, `__init__.py` with `MODULE` | new `backend/modules/observability/` | `test_registry` | REG-1 |
| **MCP-307** | Log ingester: tail the gateway JSON log, parse, dedupe, insert; runs as a background task in the app lifespan | `backend/modules/observability/ingester.py` | `test_ingester` | OBS-3 |
| **MCP-308** | Attribution: `clientInfo` → `caller.name`/`caller.version` → `source`; route-based fallback; `source=unknown` never guessed | `backend/modules/observability/attribution.py` | `test_observability`, `test_multi_host` | OBS-2 |
| **MCP-309** | Our own client sends explicit `clientInfo` **and** a conversation id via `_meta` `baggage` | `backend/mcp_client/session.py`, `backend/agui_agent/agent.py` | `test_mcp_client` | OBS-2.2, OBS-2a.1 |
| **MCP-310** | Preserve unrecognized `_meta` keys on the audit record, size-capped | `backend/modules/observability/ingester.py` | `test_observability` | OBS-2b |
| **MCP-311** | Episode grouping by `(source, idle gap)`, threshold in config, never called a chat | `backend/modules/observability/repository.py` | `test_observability` | OBS-2c |
| **MCP-312** | Query API: `/observability/calls` (filter caller/tool/status/window, paginated), `/summary`, `/stream` (SSE) | `backend/modules/observability/router.py` | `test_observability_api` | OBS-4 |
| **MCP-313** | Retention cap by row count and age | `backend/modules/observability/repository.py` | `test_ingester` | OBS-3.3 |
| **MCP-314** | Retire `/gateway-logs` HTML page; keep `/gateway-logs/raw` | `backend/data_api/main.py` | `test_observability_api` | OBS-4.4 |

**Exit:** a call from two distinct `clientInfo` identities appears in `/observability/calls` with correct, distinct sources.

### EPIC 4 — Protocol conformance · `feat/p3-conformance` · 2 days

| Ticket | Work | Test | Spec |
| :--- | :--- | :--- | :--- |
| **MCP-401** | `server/discover` shape: `supportedVersions`, `capabilities`, `serverInfo`, `instructions`, `ttlMs`, `cacheScope` | `test_protocol_conformance` | MCP-2 |
| **MCP-402** | Deterministic `tools/list` ordering across calls and restarts | `test_deterministic_ordering` | MCP-4.2 |
| **MCP-403** | `ttlMs` + `cacheScope` on all five cacheable results; tool list 3 600 000 ms / `public` | `test_cacheable_results` | MCP-4.3/4.4 |
| **MCP-404** | `resultType: "complete"` asserted on every result | `test_protocol_conformance` | MCP-4.1 |
| **MCP-405** | Client sends `MCP-Protocol-Version`, `Mcp-Method`, `Mcp-Name`, correct `Accept` | `test_mcp_client` | CLI-2.1/2.2 |
| **MCP-406** | `Mcp-Name` base64 sentinel encoding for non-ASCII | `test_mcp_client` | CLI-2.3 |
| **MCP-407** | `x-mcp-header` support incl. invalid-annotation rejection with a logged warning | `test_mcp_client` | CLI-2.4/2.5 |
| **MCP-408** | Error handling: `-32020` refresh+retry, `-32022` retry on advertised version, `-32602` resource-not-found, `-32601` unknown method | `test_mcp_client`, `test_protocol_conformance` | MCP-3, CLI-3 |
| **MCP-409** | Broken stream re-issued with a **new** request id | `test_mcp_client` | CLI-3.3 |
| **MCP-410** | `traceparent` propagation end-to-end into the audit row | `test_observability` | OBS-5.3 |
| **MCP-411** | Write the `subscriptions/listen` N/A rationale into SPECS MCP-6 and link it from the code | doc review | MCP-6 |

**D-3 note:** `MCP-5` (backward compatibility) is marked **N/A** by decision. If MCP-701 forces a reversal, MCP-5 comes back with `test_backward_compat`.

### EPIC 5 — Resources & prompts · `feat/p4-resources` · 1.5 days

| Ticket | Work | Files | Test | Spec |
| :--- | :--- | :--- | :--- | :--- |
| **MCP-501** | `ModuleSpec` gains optional `register_resources` / `register_prompts`, mirroring `register_tools` | `backend/core/registry.py`, `backend/modules/README.md` | `test_registry_resources` | REG-2 |
| **MCP-502** | Listings resources: `market://companies`, `market://sectors`, `market://companies/{symbol}` | `backend/modules/listings/resources.py` | `test_resources` | RES-1 |
| **MCP-503** | Filings resources: `market://filings/{symbol}/latest`, `market://filings/{symbol}/{period}` | `backend/modules/filings/resources.py` | `test_resources` | RES-1 |
| **MCP-504** | RFC 6570 strictness: traversal rejection, unknown symbol → `-32602` | — | `test_resources` | RES-1.3/1.4 |
| **MCP-505** | Prompts `analyze-equity`, `compare-stocks` with declared arguments | `backend/modules/analytics/prompts.py` | `test_prompts` | PROMPT-1 |
| **MCP-506** | Resource payload parity with the equivalent tool result | — | `test_resources` | RES-1.2 |

### EPIC 6 — Progress reporting (D-5) · `feat/p5-progress` · 1 day

| Ticket | Work | Files | Test | Spec |
| :--- | :--- | :--- | :--- | :--- |
| **MCP-601** | `compare_companies` emits `notifications/progress` per ticker when a `progressToken` is present | `backend/modules/analytics/tools.py` | `test_progress` | AGENT-2.1 |
| **MCP-602** | Client supplies `progressToken` and surfaces progress callbacks | `backend/mcp_client/session.py` | `test_progress` | AGENT-2.1 |
| **MCP-603** | Agent forwards progress as an AG-UI `CUSTOM` `progress` event | `backend/agui_agent/agent.py` | `test_agui` | AGENT-2.2 |
| **MCP-604** | UI: running tool rows show a determinate fraction | `frontend/…` (EPIC 8 components) | component test | AGENT-2.3 |

### EPIC 7 — Host integrations · `feat/p6-hosts` · 1 day

| Ticket | Work | Files | Test | Spec |
| :--- | :--- | :--- | :--- | :--- |
| **MCP-701** | **SPIKE (run first, see §1.1):** does `mcp-remote` speak `2026-07-28`? Can the gateway absorb a legacy client? Report before any config is finalized | — | written finding | — |
| **MCP-702** | Config audit: every host targets `:3111/mcp`; assert no committed config points at `:8000/mcp` | `.mcp.json`, `.vscode/mcp.json`, `claude_desktop_config.example.json`, `integrations/antigravity.mcp.example.json` | `test_host_configs` | GOV-1.1/1.2 |
| **MCP-703** | Record each host's observed `clientInfo` in `CLAUDE.md` §6.1 — measured, not assumed | `CLAUDE.md` | doc review | OBS-2.6 |
| **MCP-704** | Dedicated gateway route for any host that fails clientInfo attribution | `.../config.yaml` | `test_multi_host` | OBS-2.4 |
| **MCP-705** | Per-host manual matrix: 9 tools listed, one resource read, one prompt run, call visible with correct source | — | §6 matrix | HOST-1 |

### EPIC 8 — Control Room UI · `feat/p7-control-room` · 4 days

Next.js is kept; the shell is rebuilt to `index(2).html`'s structure under `DESIGN.md` tokens. `lib/agui.ts`, `lib/store.ts`, `lib/types.ts` and `components/cards/*` are carried over intact.

| Ticket | Work | Files | Test | Spec |
| :--- | :--- | :--- | :--- | :--- |
| **MCP-801** | Design tokens from `DESIGN.md` frontmatter → CSS custom properties; Inter + IBM Plex Mono | `frontend/app/globals.css` | visual review | DESIGN |
| **MCP-802** | Shell: 232px nav rail, workspace, 340–380px observability rail; resizable + persisted; responsive collapse at 1100/800px | `frontend/components/shell/AppShell.tsx` | component test | DESIGN Layout |
| **MCP-803** | Routing: `/` chat, `/audit`, `/servers`; no `href="#"` anywhere | `frontend/app/*/page.tsx` | route test | UI-5.6 |
| **MCP-804** | Chat view rebuilt on the new shell, existing streaming behaviour preserved | `frontend/components/chat/*` | component test | AGENT-1, UI-4 |
| **MCP-805** | Conversation header: model, connection state, **protocol badge**; warning treatment on fallback | `frontend/components/chat/ConversationHeader.tsx` | component test | UI-2.1 |
| **MCP-806** | Token meter: real usage only; **cached cell hidden when unreported**; no invented context ceiling | `frontend/components/rail/TokenUsage.tsx` | component test | UI-1.1/1.2 |
| **MCP-807** | Capability surface from `server/discover`: tool/resource/prompt counts, expandable | `frontend/components/rail/CapabilitySurface.tsx` | component test | UI-2.2 |
| **MCP-808** | Cache-state indicator: `ttlMs` remaining + `cacheScope`, warning when stale | `frontend/components/rail/CacheState.tsx` | component test | UI-2.4 |
| **MCP-809** | Request metadata block: gateway, endpoint, transport, protocol, policy, trace id, `data=synthetic`; **no session id** | `frontend/components/rail/RequestMeta.tsx` | component test | UI-2.3 |
| **MCP-810** | Orchestrator rounds timeline — single agent, no invented Planner/Research/Synthesis | `frontend/components/chat/RoundTimeline.tsx` | component test | UI-1.4 |
| **MCP-811** | Resource + prompt chips; prompt launcher fills the composer without sending | `frontend/components/chat/Chips.tsx` | component test | DESIGN |
| **MCP-812** | **Fleet Activity panel** over `/observability/stream`, source tags, own-traffic accent, separated from conversation scope | `frontend/components/rail/FleetActivity.tsx` | component test | UI-5.1/5.2/5.3 |
| **MCP-813** | **Audit Log route**: filter bar, dense table, expandable rows, summary strip; conversation column with `n/a` and episode grouping labelled as inferred | `frontend/app/audit/page.tsx` | component test | UI-5.4, OBS-2a.4, OBS-2c.3 |
| **MCP-814** | **MCP Servers route**: gateway status, target health, protocol, allowlist, recent callers | `frontend/app/servers/page.tsx` | component test | UI-5.5 |
| **MCP-815** | Error copy mapping for `-32020`, `-32022`, `-32602`, `-32601`, unreachable endpoint; localized to the failing row | `frontend/components/chat/ErrorRow.tsx` | component test | UI-3 |
| **MCP-816** | Missing-audit warning: tool call with no matching audit row inside the ingestion window | `frontend/components/rail/FleetActivity.tsx` | component test | UI-5.8 |
| **MCP-817** | Progress UI (D-5): determinate fraction on running rows | `frontend/components/chat/ToolRow.tsx` | component test | AGENT-2.3 |

### EPIC 9 — Release · 0.5 day

| Ticket | Work |
| :--- | :--- |
| **MCP-901** | `README.md` + `EXPLANATION.md` rewritten for the new topology and commands |
| **MCP-902** | `CLAUDE.md` §7 fully ticked; §6.1 caller table filled from measurements |
| **MCP-903** | Full Windows verification matrix executed and recorded (§6) |
| **MCP-904** | `REVIEW.md` updated; `mcp_poc_modern_protocol_plan.md` marked superseded by `MIGRATION_PLAN.md` |
| **MCP-905** | Merge to `main`, tag `v2026-07-28` |

---

## 5. Test strategy

### 5.1 Layers

| Layer | Tool | Runs where |
| :--- | :--- | :--- |
| Unit (calculations, attribution, episode grouping) | pytest | everywhere |
| Golden / characterization | pytest + committed fixtures | everywhere |
| Protocol conformance | pytest driving the ASGI app in-process | everywhere |
| Client behaviour (headers, errors, retries) | pytest + HTTP stubs | everywhere |
| Observability (ingest, attribution, API) | pytest + fixture log lines | everywhere |
| Gateway integration | pytest, `@pytest.mark.gateway` | **Windows only** |
| LLM end-to-end | pytest, `@pytest.mark.llm`, real proxy | on demand |
| Frontend components | vitest + Testing Library | everywhere |
| Host integration | manual matrix | **Windows only** |

### 5.2 Marker policy

```
pytest -m "not gateway and not llm"     # default, CI on both OSes
pytest -m gateway                        # Windows, gateway running
pytest -m llm                            # on demand, real proxy, costs tokens
```

`@pytest.mark.gateway` tests **skip loudly** — a skip message naming the missing prerequisite, never a silent pass.

### 5.3 Fixtures

- `golden/` — tool outputs and `tools_list.json`, committed, regenerated only by a deliberate, reviewed commit
- `gateway_logs/` — captured real gateway JSON lines per host, so attribution is tested against reality rather than invented shapes. **Populated by MCP-703; until then, attribution tests are provisional.**
- In-memory SQLite per test for `observability.db`
- Deterministic clock via `freezegun` for TTL and episode-threshold tests

### 5.4 The macOS limitation, stated plainly

The gateway is not exercised on this machine. Everything that depends on it — attribution from real host traffic, allowlist enforcement, telemetry field names, the `mcp-remote` question — is verified by the Windows matrix in §6, not by CI. Automated tests reach `/mcp` directly, which is a test harness, not a consumer configuration; invariant #7 still applies to every real host.

Anything I have not executed will be reported as **unverified**, never as passing.

### 5.5 Coverage targets

| Area | Target |
| :--- | :--- |
| `core/calculations.py` | 95% |
| `core/api_tools.py`, `core/registry.py` | 90% |
| `mcp_client/session.py` | 85% |
| `modules/observability/` | 85% |
| Everything else | 70% floor |

Coverage is a smoke alarm, not a goal. A ticket with 100% coverage and no acceptance-criteria assertion is not done.

---

## 6. Windows verification matrix

Executed by you on the Windows machine; results recorded in the EPIC 9 PR.

| # | Check | Pass condition |
| :-- | :--- | :--- |
| W-1 | Gateway starts on ≥ 1.4.1 with the new `config.yaml` | No validation errors |
| W-2 | `server/discover` through `:3111` | Returns `supportedVersions` incl. `2026-07-28` |
| W-3 | All 9 tools callable through the gateway | Results match golden fixtures |
| W-4 | Unlisted tool name | Refused at the gateway, never reaches the server |
| W-5 | Claude Code | Lists 9 tools, reads a resource, runs a prompt |
| W-6 | VS Code Copilot | Same |
| W-7 | Claude Desktop | Same, or MCP-701 outcome documented |
| W-8 | Antigravity | Same, or MCP-701 outcome documented |
| W-9 | Attribution | Each host appears with a distinct, correct source |
| W-10 | Web UI attribution | Rows tagged `control-room` and linked to the right conversation |
| W-11 | Persistence | Restart gateway and backend; earlier rows still present, none duplicated |
| W-12 | Metrics | `/metrics` exposes `mcp_requests_total` with expected labels |
| W-13 | Tracing | A `tools/call` produces a span; trace id matches the audit row |
| W-14 | Bypass detection | Point one host at `:8000/mcp`; UI raises the missing-audit warning |
| W-15 | Progress | `compare_companies` over 5 tickers shows a determinate progress fraction |

---

## 7. Sequencing

```
MCP-001..004  setup
      │
EPIC 0  baseline ──────────────────────────┐
      │                                    │ golden fixtures gate everything
EPIC 1  SDK v2 ────────────────────────────┤
      │                                    │
EPIC 2  transport ─────────────────────────┤
      │                                    │
      ├── EPIC 3  observability ───────────┤   (needs EPIC 2's /mcp)
      ├── EPIC 4  conformance ─────────────┤   (parallel with EPIC 3)
      │                                    │
EPIC 5  resources & prompts ───────────────┤
      │                                    │
EPIC 6  progress ──────────────────────────┤
      │                                    │
MCP-701 spike ──► EPIC 7  hosts ───────────┤
      │                                    │
EPIC 8  Control Room UI ───────────────────┘   (MCP-801..811 can start after EPIC 2;
      │                                         812..817 need EPIC 3 and 6)
EPIC 9  release
```

**Critical path:** EPIC 0 → 1 → 2 → 3 → 8. EPIC 4 runs alongside 3. MCP-701 runs early and independently — it is cheap and it can invalidate D-3.

| Epic | Effort |
| :--- | :--- |
| Setup (MCP-001..004) | 0.5 day |
| 0 — baseline | 1 day |
| 1 — SDK v2 | 3 days |
| 2 — transport | 2 days |
| 3 — observability | 3 days |
| 4 — conformance | 2 days |
| 5 — resources & prompts | 1.5 days |
| 6 — progress | 1 day |
| 7 — hosts | 1 day |
| 8 — Control Room UI | 4 days |
| 9 — release | 0.5 day |
| **Total** | **~19.5 days** |

EPIC 4 overlapping EPIC 3 recovers ~2 days for one developer working sequentially elsewhere.

---

## 8. Risk register

| # | Risk | Trigger | Mitigation |
| :-- | :--- | :--- | :--- |
| R-1 | `mcp-remote` cannot speak `2026-07-28`; D-3 locks out two hosts | MCP-701 | Gateway-side compatibility; failing that, revert D-3 for bridged hosts only |
| R-2 | SDK v2 API differs from the migration guide | EPIC 1 | Read the installed package's own source first; the guide is a summary |
| R-3 | `pydantic-settings` incompatible with `pydantic>=2.12` | MCP-101 | Pin a compatible pair; `core/config.py` is the only consumer |
| R-4 | D-2 changes tool output shape | MCP-201 | Golden tests are the gate; MCP-108 blocks progress until they match |
| R-5 | Gateway log field names differ from documentation | MCP-305/307 | Capture real log lines into `gateway_logs/` fixtures before writing the parser |
| R-6 | Attribution untestable on macOS | EPIC 3 | Fixture-driven tests now, W-9 confirms on Windows |
| R-7 | UI rebuild regresses working chat behaviour | EPIC 8 | Carry `lib/` and `components/cards/` over unchanged; component tests before restyling |
| R-8 | Ingestion lag makes fleet rows feel stale | MCP-307 | 2s target asserted in `test_ingester`; SSE push, not polling |
| R-9 | Audit DB grows unbounded | MCP-313 | Retention cap by count and age |
| R-10 | Scope creep into agent redesign | any | D-4 says no; AGENT-3 stays out of this build |

---

## 9. Rollback

- Every epic is its own branch and merges as one unit; `git revert` of a merge commit undoes an epic cleanly.
- `pre-2026-migration` tag is the floor.
- The only irreversible step is MCP-302, the gateway target switch. The old `stdio:` block stays commented in `config.yaml` for one release, making a revert a two-line edit.
- Golden fixtures are the objective test for "did we change behaviour" at any point.

---

## 10. Open items

None blocking. Two to confirm as the work reaches them:

1. **MCP-701 outcome** determines whether D-3 survives contact with the bridged hosts.
2. **Episode idle-gap threshold** (MCP-311) needs a real number. Proposal: 30 seconds, configurable, tuned once real multi-host traffic exists in the log.
