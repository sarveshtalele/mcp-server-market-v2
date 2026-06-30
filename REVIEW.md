# Code Review & Gap Analysis

Manual review of the full project (the repo is not a git repo, so this is a
whole-tree audit rather than a diff review). Findings are grouped by severity,
each with status: **Fixed** in this pass, or **Noted** (acceptable for a PoC,
listed so it's a conscious decision).

## Summary

| # | Area | Severity | Status |
|---|------|----------|--------|
| 1 | Shared MCP stdio session under concurrent requests | High | ✅ Fixed |
| 2 | Markdown renderer ignored tables | Medium | ✅ Fixed |
| 3 | No automated tests | Medium | ✅ Fixed (added) |
| 4 | Dead code / unused deps (CopilotKit path) | Medium | ✅ Fixed (removed) |
| 5 | SQLite foreign keys not enforced | Low | Noted |
| 6 | CORS `allow_origins=["*"]` on both APIs | Low | Noted (local only) |
| 7 | `exec()` in declarative tool builder | Low | Noted (controlled) |
| 8 | Secrets live in `backend/.env` | Info | Noted (gitignored) |
| 9 | Agent error text sent to client verbatim | Low | Noted |
| 10 | Multi-turn tool context not replayed | Low | Noted (by design) |

---

## Fixed

### 1. Shared MCP stdio session under concurrency (High)
`ExchangeAgent` holds one `MCPToolClient` (a single stdio session) reused across all
`/agui` requests. Two simultaneous users could interleave reads/writes on that
duplex pipe and corrupt responses.
**Fix:** added an `asyncio.Lock` in `MCPToolClient.call_tool` so tool
invocations are serialised. Tool calls are short; throughput is fine for a PoC.
*(`backend/mcp_client/session.py`)*

### 2. Markdown renderer ignored tables (Medium, UX)
The custom chat's `Markdown.tsx` handled headings/lists/bold/code but rendered
markdown tables as raw `| … |` lines. The model occasionally emits a table in
prose.
**Fix:** added table parsing (header + separator + body) and themed
`.md-table` styles. *(`frontend/components/chat/Markdown.tsx`, `globals.css`)*

### 3. No automated tests (Medium)
**Fix:** added `backend/tests/test_calculations.py` — 6 unit tests over the pure
functions in `core/calculations.py` (margins, ROE, divide-by-zero safety, QoQ/YoY
growth, ranking order/validation, comparison highlights). `pytest` added to
`requirements.txt`. Run: `python -m pytest tests/`.

### 4. Dead code / unused dependencies (Medium)
The web chat was reimplemented as a custom AG-UI client, leaving the CopilotKit
path unused.
**Fix:** removed `components/{ChatApp,GenerativeUI,Providers}.tsx`,
`app/api/copilotkit/route.ts`, the `@copilotkit/*` + `@ag-ui/client` deps, and the
CopilotKit CSS/imports. Also consolidated five `.bat` files + the `scripts/`
PowerShell folder down to a single `run_all.bat`; setup/run commands now live in
the README. First-load JS dropped ~8 kB and the `/api/copilotkit` route is gone.

---

## Noted (acceptable for a PoC)

### 5. SQLite foreign keys not enforced (Low)
`filings.symbol` is declared `ForeignKey("companies.symbol")` but SQLite does not
enforce FKs unless `PRAGMA foreign_keys=ON` is set per connection. Seeding is
ordered (listings before filings) so data is consistent; enforcement only matters
if external writes arrive. *To harden:* add a `connect` event that runs the pragma.

### 6. CORS `*` on both FastAPI apps (Low)
Fine for `localhost` development. For any real deployment, restrict
`allow_origins` to the known frontend origin.

### 7. `exec()` in the declarative tool builder (Low)
`core/api_tools.py` generates tool functions from `EndpointTool` specs via
`exec` of a module-authored template (no user input reaches it). This is how the
correct FastMCP parameter schema is produced. Controlled and safe, but flagged so
it's a conscious choice; a `makefun`-style library could replace it if preferred.

### 8. Secrets in `backend/.env` (Info)
The real LiteLLM key sits in `backend/.env`, which is gitignored — good. Make sure
it (and your Claude `settings.json`) are never committed. The MCP-in-Claude path
needs no LLM key at all.

### 9. Agent error text sent verbatim (Low)
`RUN_ERROR` forwards `str(exc)` to the browser, which can expose internal detail.
Acceptable locally; sanitise for production.

### 10. Multi-turn tool context not replayed (Low, by design)
Each `/agui` run rebuilds history from the browser's user/assistant **text**;
prior tool results aren't replayed into the LLM context. Follow-ups that need an
earlier tool's raw numbers trigger a fresh tool call instead. This keeps the
protocol simple and the answers grounded.

---

## What's solid
- Clean module/plugin boundary; one registry, three consumers (API, MCP, seed).
- Tools fetch over HTTP (real API boundary), calculations are pure and reused.
- Deterministic synthetic data (seeded Faker/random).
- LLM access is gateway-agnostic (`LLM_*` env, OpenAI-compatible).
- End-to-end verified: API, MCP roundtrip, agent streaming, CORS, SSE framing.
