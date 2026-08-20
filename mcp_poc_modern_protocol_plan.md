> **Superseded.** This was the original modernization proposal. Its review, corrections and the plan that was actually executed live in [MIGRATION_PLAN.md](MIGRATION_PLAN.md) and [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

# Lean PoC Modernization Plan: Native Modern MCP Implementation

## 1. Executive Summary & PoC Objectives

This document outlines a lightweight, focused modernization plan designed specifically for the **`mcp-server-market` Proof of Concept (PoC)**. 

Rather than introducing heavy enterprise infrastructure (distributed Kubernetes clusters, PostgreSQL, OAuth 2.0 identity providers, or Redis clusters), this plan refactors the existing PoC to be **100% native to the latest Model Context Protocol (MCP 2026-07-28) standard**.

### 1.1 Core PoC Modernization Goals
- **Eliminate External Binary Wrappers**: Remove `agentgateway.exe` and the Node `mcp-remote` bridge; mount the FastMCP server directly inside FastAPI using native **Stateless Streamable HTTP**.
- **Adopt 2026-07-28 Stateless Protocol**: Transition from legacy handshake connections (`initialize`/`initialized`) to lightweight discovery (`server/discover`) and per-request `_meta` capability negotiation.
- **Unlock Multi-Session Concurrency**: Remove the global standard I/O synchronization lock (`asyncio.Lock`), enabling responsive concurrent web chat sessions locally.
- **Expand Beyond Pure Tools**: Introduce read-only **MCP Resources** (`market://`), dynamic **Resource Templates**, and domain **MCP Prompts**.
- **Modernize Developer Experience**: Replace runtime dynamic string evaluation (`exec`) with typed Pydantic models and deterministic tool ordering.

---

## 2. Lean PoC Target Architecture

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                LEAN MODERN POC ARCHITECTURE MAP                                  │
├──────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                  │
│   [ External AI Hosts / IDEs ]                           [ Next.js Generative Web UI (:3000) ]   │
│   (Claude Desktop, Antigravity, Claude Code)             (App Router + Generative Tool Cards)    │
│               │                                                              │                   │
│               │ (Native Streamable HTTP / stdio)                             │ (AG-UI SSE Stream)│
│               ▼                                                              ▼                   │
│  ┌────────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │                    UNIFIED BACKEND SERVICE (FastAPI / ASGI :8000)                          │  │
│  │                                                                                            │  │
│  │   ┌─────────────────────────────┐                  ┌──────────────────────────────────┐    │  │
│  │   │  Native FastMCP Engine      │                  │  AG-UI Agent Service             │    │  │
│  │   │  (2026-07-28 Stateless)     │                  │  • OpenAI SDK Tool Loop          │    │  │
│  │   │  • server/discover RPC      │                  │  • Lock-Free MCPToolClient       │    │  │
│  │   │  • Deterministic tools/list │                  │  • Real-Time Token / Timing Telemetry││  │
│  │   │  • CacheableResult (ttlMs)  │                  └────────────────┬─────────────────┘    │  │
│  │   │  • market:// Resources      │                                   │                      │  │
│  │   │  • Prompt Workflows         │                                   │                      │  │
│  │   │  • Progress & MRTR          │                                   │                      │  │
│  │   └──────────────┬──────────────┘                                   │                      │  │
│  │                  │                                                  │                      │  │
│  │                  ▼                                                  ▼                      │  │
│  │   ┌───────────────────────────────────────────────────────────────────────────────────┐    │  │
│  │   │                             Data API REST Endpoints                               │    │  │
│  │   │               • /listings/*                • /filings/*                           │    │  │
│  │   └─────────────────────────────────────────┬─────────────────────────────────────────┘    │  │
│  │                                             │                                              │  │
│  │                                             ▼                                              │  │
│  │   ┌───────────────────────────────────────────────────────────────────────────────────┐    │  │
│  │   │                           Pure Mathematical Core                                  │    │  │
│  │   │                     (financial_ratios, compare_companies)                         │    │  │
│  │   └─────────────────────────────────────────┬─────────────────────────────────────────┘    │  │
│  │                                             │                                              │  │
│  │                                             ▼                                              │  │
│  │   ┌───────────────────────────────────────────────────────────────────────────────────┐    │  │
│  │   │                           SQLite Database (stock_market.db)                       │    │  │
│  │   │                     (Deterministic Faker Seeding: SEED = 2025)                    │    │  │
│  │   └───────────────────────────────────────────────────────────────────────────────────┘    │  │
│  └────────────────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Key MCP 2026-07-28 Modernization Enhancements for the PoC

### 3.1 Transport: Native Stateless Streamable HTTP
- **Current Approach**: Python MCP server runs as a hidden subprocess inside `agentgateway.exe`, requiring `npx mcp-remote` bridges for Claude Desktop and Antigravity.
- **PoC Target**: Mount FastMCP directly on the FastAPI application using native **Streamable HTTP**. External hosts and the local AG-UI agent connect directly via HTTP endpoints without external binary dependencies.

### 3.2 Concurrency: Lock-Free Client Execution
- **Current Approach**: `MCPToolClient` wraps all tool execution in a global `asyncio.Lock()`, serializing every incoming user message.
- **PoC Target**: Eliminate the global lock. Under the 2026-07-28 stateless standard, requests carry independent `_meta` blocks and execute concurrently without cross-session interference.

### 3.3 Data Layer: Native MCP Resources (`market://`)
- **Current Approach**: Static data (company details, quarterly balance sheets) requires the LLM to invoke tool functions (`get_company`, `get_filings`).
- **PoC Target**: Expose financial data as direct **MCP Resources**:
  - `market://companies/{symbol}` -> Direct company profile and listing metadata.
  - `market://filings/{symbol}/latest` -> Direct quarterly balance sheet, income statement, and cash flow.
- **PoC Benefit**: AI hosts can attach financial documents directly to prompts, saving ~40% in token consumption and skipping function-calling roundtrips.

### 3.4 Reusable Workflows: Domain MCP Prompts
- **Current Approach**: Prompt instructions are hardcoded in the frontend or backend agent system strings.
- **PoC Target**: Expose structured **MCP Prompts**:
  - `prompts/analyze-equity` -> Automated financial health check (resource inspection + ratio calculations).
  - `prompts/compare-stocks` -> Side-by-side valuation and margin benchmarking.
- **PoC Benefit**: Claude Desktop, Antigravity IDE, and web chats can discover and trigger identical structured financial memos with 1 click.

### 3.5 Type Safety: Declarative Pydantic Models
- **Current Approach**: `EndpointTool` uses runtime string evaluation (`exec()`) to generate function signatures dynamically.
- **PoC Target**: Replace string evaluation with declarative Pydantic parameter schemas conforming to JSON Schema 2020-12.

### 3.6 Cache Optimization & Determinism
- **Current Approach**: Tool list order is non-deterministic and uncached.
- **PoC Target**: Enforce deterministic sorting in `tools/list` and supply `CacheableResult` with `ttlMs` (1 hour) for tool definitions, maximizing LLM prompt-cache hits and reducing startup latency.

---

## 4. PoC File-by-File Upgrade Matrix

| File Path | Current PoC Role | Target 2026-07-28 PoC Implementation | Rationale & Benefit |
| :--- | :--- | :--- | :--- |
| **`backend/mcp_server/server.py`** | FastMCP stdio server registering tools from modules. | Expose native Streamable HTTP, declare full capabilities, add Resources (`market://`) and Prompts. | Enables multi-transport access without external gateway binaries; adds direct context attachment. |
| **`backend/core/api_tools.py`** | Dynamic tool generation using runtime string `exec()`. | Build dynamic tools using typed Pydantic models without `exec()`. | Eliminates dynamic code evaluation; provides static type safety and schema validation. |
| **`backend/mcp_client/session.py`** | Streamable HTTP client with `initialize()` and `asyncio.Lock`. | Remove `initialize()` and `asyncio.Lock`; use stateless `server/discover` and per-request `_meta`. | Complies with 2026-07-28 stateless transport; unlocks parallel multi-session concurrency. |
| **`backend/modules/listings/tools.py`** | 3 endpoint tools for company listings and sector search. | Keep analytical tools + expose `market://companies/{symbol}` as an MCP Resource. | Allows direct document reading into LLM context without burning tool-calling steps. |
| **`backend/modules/filings/tools.py`** | 2 endpoint tools for filing history and latest filing. | Keep analytical tools + expose `market://filings/{symbol}/{period}` as an MCP Resource. | Direct attachment of raw balance sheets and income statements into IDE prompts. |
| **`backend/modules/analytics/tools.py`** | 4 pure calculation tools (ratios, growth, compare, rank). | Add progress reporting (`_meta.progressToken`) and deterministic schemas. | Granular progress feedback during multi-ticker comparisons. |
| **`backend/core/config.py`** | Central configuration with hardcoded gateway URL. | Clean relative configuration; eliminate gateway binary paths. | Complete cross-platform compatibility across macOS, Linux, and Windows. |
| **`integrations/`** | Configs using `npx mcp-remote` bridges to agentgateway. | Native HTTP configurations (`type: http`) pointing directly to FastAPI MCP endpoint. | Eliminates Node/npx dependencies for Claude Desktop, Antigravity, and Claude Code. |

---

## 5. Lightweight PoC Phased Execution Plan

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    LEAN POC EXECUTION TIMELINE                                   │
├───────────────────────┬──────────────────────────────────────────┬───────────────────────────────┤
│ Step & Focus          │ Action Items                             │ Expected Output               │
├───────────────────────┼──────────────────────────────────────────┼───────────────────────────────┤
│ **Step 1: Transport &**│ • Pin/bump MCP SDK in requirements.txt   │ • MCP mounted on FastAPI :8000│
│ **Decoupling**        │ • Mount FastMCP on FastAPI /mcp endpoint │ • agentgateway binary removed │
│ *(Days 1 – 2)*        │ • Remove agentgateway setup & run scripts│ • Streamable HTTP enabled     │
├───────────────────────┼──────────────────────────────────────────┼───────────────────────────────┤
│ **Step 2: Concurrency**│ • Remove `asyncio.Lock` in session.py    │ • Lock-free async client      │
│ **& Discovery**       │ • Replace `initialize()` with `discover` │ • 2026-07-28 stateless headers│
│ *(Days 3 – 4)*        │ • Add version-negotiation safeguards     │ • High concurrent throughput  │
├───────────────────────┼──────────────────────────────────────────┼───────────────────────────────┤
│ **Step 3: Resources &**│ • Add `market://` URI Resource endpoints │ • Direct context attachment   │
│ **Prompts**           │ • Define Prompt templates (equity-memo)  │ • 1-click workflows in IDEs   │
│ *(Days 5 – 6)*        │ • Refactor `core/api_tools.py` (no exec) │ • Typed Pydantic validation   │
├───────────────────────┼──────────────────────────────────────────┼───────────────────────────────┤
│ **Step 4: End-to-End**│ • Verify Claude Desktop / Antigravity    │ • Unified 2-process launcher  │
│ **Verification**      │ • Test AG-UI streaming & generative cards│ • Instant cross-platform run  │
│ *(Days 7 – 8)*        │ • Verify deterministic tool ordering     │ • Full test suite pass        │
└───────────────────────┴──────────────────────────────────────────┴───────────────────────────────┘
```

---

## 6. Simplified Developer Execution Workflow

With this modernized PoC architecture, running the entire stack is reduced from 4 complex processes down to **2 simple commands**:

1. **Backend (Data API + Native MCP Server + AG-UI Agent)**:
   - Single Uvicorn process serving REST endpoints, MCP Streamable HTTP (`/mcp`), and AG-UI event streaming (`/agui`) on Port 8000.
2. **Frontend (Next.js Web UI)**:
   - Single Next.js dev server on Port 3000 rendering streaming text, live tool status chips, and generative cards.

---

## 7. Verification & Governance Confirmation

- **Strictly Code-Free Document**: Contains zero code snippets or executable scripts, adhering to pure architectural and strategic specification guidelines.
- **GitHub Safety Maintained**: Zero code pushed or modified on remote GitHub repositories.
- **Full Standard Compliance**: Fully aligned with the latest **Model Context Protocol (2026-07-28)** specification.
