---
version: alpha
name: Enterprise MCP Control Room
description: Enterprise-grade conversational control room for an MCP 2026-07-28 market-intelligence agent, with transparent tool, resource and protocol telemetry.
colors:
  primary: "#0B1220"
  primary-60: "#162238"
  primary-70: "#1D3150"
  secondary: "#5F6B7A"
  tertiary: "#2F6BFF"
  tertiary-hover: "#2457D6"
  neutral: "#F5F7FA"
  surface: "#FFFFFF"
  surface-subtle: "#F8FAFC"
  surface-elevated: "#EEF2F7"
  border: "#D9E0EA"
  text: "#0B1220"
  text-muted: "#667085"
  on-primary: "#FFFFFF"
  on-tertiary: "#FFFFFF"
  success: "#178A5B"
  warning: "#B7791F"
  error: "#D64545"
  info: "#2878C8"
  agent: "#7C3AED"
  tool: "#0E7490"
typography:
  headline-xl:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: 650
    lineHeight: 1.15
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: 650
    lineHeight: 1.2
    letterSpacing: -0.015em
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.55
  body-sm:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: 400
    lineHeight: 1.5
  label-md:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: 0.01em
  mono-md:
    fontFamily: "IBM Plex Mono"
    fontSize: 12px
    fontWeight: 500
    lineHeight: 1.45
rounded:
  none: 0px
  sm: 6px
  md: 10px
  lg: 14px
  full: 9999px
spacing:
  xs: 4px
  sm: 8px
  md: 12px
  lg: 16px
  xl: 24px
  2xl: 32px
  3xl: 48px
components:
  app-shell:
    backgroundColor: "{colors.neutral}"
    textColor: "{colors.text}"
  primary-nav:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    rounded: "{rounded.none}"
    height: 56px
  panel:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.lg}"
    padding: 16px
  button-primary:
    backgroundColor: "{colors.tertiary}"
    textColor: "{colors.on-tertiary}"
    rounded: "{rounded.md}"
    padding: 10px
    height: 40px
  button-primary-hover:
    backgroundColor: "{colors.tertiary-hover}"
  message-assistant:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.lg}"
    padding: 16px
  message-user:
    backgroundColor: "{colors.primary-60}"
    textColor: "{colors.on-primary}"
    rounded: "{rounded.lg}"
    padding: 14px
  tool-chip:
    backgroundColor: "{colors.surface-subtle}"
    textColor: "{colors.tool}"
    rounded: "{rounded.full}"
    padding: 8px
  agent-chip:
    backgroundColor: "#F3E8FF"
    textColor: "{colors.agent}"
    rounded: "{rounded.full}"
    padding: 8px
  resource-chip:
    backgroundColor: "{colors.surface-subtle}"
    textColor: "{colors.info}"
    rounded: "{rounded.full}"
    padding: 8px
  prompt-chip:
    backgroundColor: "{colors.surface-elevated}"
    textColor: "{colors.secondary}"
    rounded: "{rounded.full}"
    padding: 8px
  source-tag:
    backgroundColor: "{colors.surface-elevated}"
    textColor: "{colors.secondary}"
    rounded: "{rounded.sm}"
    padding: 4px
  protocol-badge:
    backgroundColor: "{colors.surface-subtle}"
    textColor: "{colors.text-muted}"
    rounded: "{rounded.sm}"
    padding: 6px
---

## Overview

Enterprise MCP Control Room is a high-trust, operations-oriented chat UI for a **single orchestrating agent** that reasons over an OpenAI-compatible model and executes tools on one MCP server (`stock-exchange`) speaking **MCP 2026-07-28** over Streamable HTTP. The interface should feel like an internal platform console rather than a consumer messenger: calm, precise, information-dense, and auditable.

The primary interaction is conversational. The user should always understand five things without opening developer tools: what the assistant is saying, which MCP tools were invoked and how long each took, which resources or prompts were used as context, how much model context the turn consumed, and which protocol version and endpoint served the request.

**The Control Room is also a fleet view, not just a chat.** Every consumer — Claude Desktop, Claude Code, VS Code Copilot, Antigravity, and this UI's own agent — reaches the server through one gateway. A tool call made inside a Claude Desktop conversation must be visible here, tagged with where it came from. Two scopes therefore coexist and must never be blurred together: **this conversation's** tool calls, and **the fleet's** calls. Conversation scope answers "what did my last question cost"; fleet scope answers "who is using this server right now".

The visual system uses a deep ink navigation shell, white working surfaces, a single electric blue interaction color, and distinct semantic accents for the orchestrator, tools, resources, success, warning, and errors. Telemetry uses monospace type and compact metric cards.

**Truthfulness rule.** Every value on screen must trace to a real backend signal. The backend emits per-tool client-measured latency, one per-run usage event (`elapsedMs`, `promptTokens`, `completionTokens`, `totalTokens`, `toolCalls`), the capability set from `server/discover`, and per-call audit rows. It does **not** currently emit cached-token counts, multi-agent orchestration, or a context-window limit. Do not render what the backend does not produce; hide the field instead. Fixture data must be labelled `DEMO`, and the dataset is synthetic (`Faker`, fixed seed) and must be labelled as such wherever figures appear.

## Colors

The palette is deliberately restrained so operational signals are meaningful.

- **Primary (#0B1220):** Deep ink for the global shell and high-emphasis surfaces.
- **Secondary (#5F6B7A):** Slate for metadata, helper copy, timestamps, and inactive controls.
- **Tertiary (#2F6BFF):** Electric blue is the primary interaction color for buttons, selected states, links, and active progress.
- **Neutral (#F5F7FA):** Cool gray page background that separates the app shell from white work surfaces.
- **Agent (#7C3AED):** Violet identifies the orchestrator and its reasoning rounds.
- **Tool (#0E7490):** Deep cyan identifies MCP tool execution.
- **Info (#2878C8):** Blue identifies MCP resources — context read rather than computed.
- **Success (#178A5B):** Reserved for completed operations and healthy service states.
- **Warning (#B7791F):** Reserved for degraded states, stale caches, and protocol fallback.
- **Error (#D64545):** Reserved for failures and blocked actions.

Agents, tools and resources are three different kinds of activity and must never share an accent. Avoid gradients, neon glows, decorative color noise, and color-only status communication. Every status color must be paired with text or an icon.

## Typography

Inter is the default product typeface because it remains highly legible at small sizes and behaves consistently across dense enterprise interfaces. IBM Plex Mono is reserved for technical telemetry: token counts, latency, model IDs, tool names, resource URIs, protocol versions, JSON snippets, trace ids, and error codes.

Headlines are compact and moderately weighted. Body text stays at 13–14px for application density. Labels use 12px semibold text with restrained letter spacing. Do not use more than two visible font families on a screen.

## Layout

Use a fixed desktop shell with three primary regions:

1. **Global navigation rail:** 232px wide. Product identity, conversation list, navigation, environment badge, and account controls.
2. **Conversation workspace:** fluid center column, optimized for 680–820px readable content width. Conversation header, message timeline, generative tool cards, composer, and turn-level status.
3. **Observability rail:** 340–380px wide. Token usage, MCP capability surface, tool execution timeline, cache state, and request metadata.

Use a 12-column mental grid with 8px rhythm. Outer page padding is 24px on desktop and 16px on smaller screens. The app should not use excessive whitespace: the interface is designed for operators who may scan many runtime signals during one task.

Keep the message column centered inside the workspace while telemetry remains docked to the right. On widths below 1100px, collapse the observability rail into a drawer. On widths below 800px, collapse global navigation into a top bar. Both side rails are resizable and their widths persist.

## Elevation & Depth

Depth comes from tonal layers and 1px borders rather than heavy shadows. Panels sit on `surface`, the page sits on `neutral`, and the global shell sits on `primary`.

Default panel border is `1px solid #D9E0EA`. Use a subtle shadow only for floating menus, dialogs, or the composer when it visually separates from the timeline. Never use large blurred shadows around normal cards.

## Shapes

The shape language is structured and moderately soft. Use 6px for compact controls and badges, 10px for buttons and cards, 14px for larger message surfaces, and pill shapes only for tags/chips/status badges.

Do not mix sharp 0px cards with rounded cards in the same component family. Tables, telemetry rows, and timeline items use controlled corner radii; message groups can use 14px.

## Components

### Global shell

Stable across all routes. The left navigation uses the primary ink color and remains visually distinct from the product workspace. The current environment is always visible and should not rely on a small tooltip. Because the dataset is synthetic, the environment badge reads `DEMO · SYNTHETIC DATA` rather than implying production market data.

Routes: **Chat** (conversation workspace), **MCP Servers** (gateway and server health), **Audit Log** (fleet-wide call history). Every entry resolves to a real view — no placeholder links.

### Conversation header

Show the assistant name, the model id, connection state, and a compact action menu. Connection state describes the MCP endpoint, not a gateway: `MCP /mcp · connected`. Add a **protocol badge** in monospace showing the negotiated revision, e.g. `MCP 2026-07-28`. If the client had to fall back to an older revision, the badge takes the warning semantic and reads `MCP 2025-11-25 · fallback`.

The title stays human-readable; technical ids belong in the telemetry rail.

### User message

Right-aligned or clearly distinct from assistant content. Keep the surface visually compact. Do not show internal telemetry inside the user bubble.

### Assistant message

Left-aligned on a white panel. Supports Markdown, code, structured data cards, and inline tool chips. The prose answer must read normally on its own even when telemetry is present; raw tool JSON is rendered separately as generative cards, never pasted into the prose.

### Orchestrator step

There is exactly one agent. Do not draw a multi-agent tree, and do not invent Planner / Research / Synthesis roles — the backend runs a single orchestrator with a bounded tool loop (maximum six rounds).

Represent orchestration as **rounds** of that loop: a collapsible timeline item per round showing round number, status, duration, and how many tools it dispatched. Use the violet agent accent. Recommended labels: `ROUND 1 · PLANNING`, `ROUND 2 · TOOL DISPATCH`, `FINAL · SYNTHESIS`. Never show chain-of-thought — the model's reasoning stream is deliberately not forwarded from the backend.

### MCP tool chip

Show tool name, server (`stock-exchange`), status, duration, and a short argument preview. Use the cyan tool accent. While running, show a small spinner; on completion, a check icon and duration; on failure, the error semantic plus the protocol error code. Tool names appear in monospace, exactly as the server declares them.

### MCP resource chip

New surface. When a turn reads an MCP resource instead of calling a tool, show a chip in the info accent carrying the URI in monospace, e.g. `market://companies/AAPL`. Resource chips must be visually distinct from tool chips: reading context is not the same operation as executing a function, and conflating them destroys the audit story.

If the agent does not read resources in a given deployment, this chip simply never appears. Do not render a placeholder.

### MCP prompt launcher

Server-declared prompts (`analyze-equity`, `compare-stocks`) appear as secondary chips above the composer. Selecting one fills the composer with the prompt's arguments for the user to complete — it does not auto-send. Show the prompt name in monospace and its declared arguments as inline placeholders.

### Token usage meter

The right rail shows input tokens, output tokens, and total tokens from the backend's per-run usage event, in monospace. Include a cached-tokens cell **only when the provider reports one** — omit the cell entirely otherwise rather than showing zero.

The backend reports no configured context limit, so do not render a percentage-of-context bar against an invented ceiling. Show a bar only when a real limit is configured; otherwise show total tokens plus the run's end-to-end time. Label the two timings distinctly: response time is backend-measured, tool durations are client-measured.

### MCP capability surface

New panel in the right rail, populated from `server/discover`. Show the server name and version, and counts for tools, resources and prompts. Each count expands into a list. This replaces guessing at the server's shape by probing three separate list endpoints, and it gives operators one place to confirm what the connected server actually offers.

### Cache state indicator

Cacheable results carry a freshness hint (`ttlMs`) and a scope (`cacheScope`). Show the tool-list cache as a compact monospace line: remaining TTL and scope, e.g. `tools/list · 58m left · public`. When the TTL has expired and a refresh is pending, use the warning semantic. This makes the client's caching behaviour observable instead of magical.

### Tool execution timeline

Sort newest first. Each row includes tool name, argument preview, server, latency, status, and an expand affordance. Rows remain scannable at 13px. Running rows update in place; when progress notifications are available, a running row shows a determinate fraction rather than an indeterminate spinner.

### Request metadata

Monospace block at the foot of the right rail. Show only fields that exist under this protocol revision:

```
gateway    = agentgateway:3111
endpoint   = http://127.0.0.1:8000/mcp
transport  = streamable-http
protocol   = 2026-07-28
policy     = stock-exchange-allowlist
trace_id   = <traceparent>
data       = synthetic
```

The gateway is genuinely in the path and stays on display — it is what makes the audit view possible. There is **no session id** under this revision: sessions were removed from the transport, so such a field would be actively misleading. Correlation is by `trace_id` and caller identity instead.

### Source tag

A compact monospace tag identifying which consumer originated a call: `claude-desktop`, `claude-code`, `vscode-copilot`, `antigravity`, `control-room`. Uses the secondary slate treatment — it is metadata, not status, and must not compete with the tool and resource accents.

When a call cannot be attributed, the tag reads `unknown` in the warning semantic. Never substitute a plausible-looking host: an unattributed call is an observability defect and should look like one.

### Fleet activity panel

Right-rail section, below the conversation's own tool timeline and clearly separated from it by a divider and its own section label. Shows the newest MCP calls across **all** consumers, streaming live.

Each row: source tag · tool name · target server · latency · status. Rows originating from this browser session are marked (a left accent bar in the tertiary color) so the operator can tell their own traffic from everyone else's at a glance. Cap the panel at roughly ten rows with a link into the full Audit Log.

If a tool call appears in the conversation but no matching audit row arrives within the ingestion window, show an inline warning — that means something reached the server without passing the gateway, which is a defect worth surfacing loudly.

### Audit log view

A full route, not a modal. The nav entry must resolve to a real page; a dead link here is worse than no link, because the product's premise is auditability.

Layout: a filter bar (caller, tool, status, time window) over a dense table — timestamp, source tag, conversation, method, tool/resource, argument preview, latency, status, trace id.

**The conversation column is honest about its limits.** MCP defines no conversation identifier in any revision, so only this product's own client can supply one. Rows from `control-room` show a conversation reference that links back to the saved chat; rows from every other source show `n/a`.

Where no real identifier exists, rows may be grouped into **episodes** — runs of calls from one source separated by an idle gap. An episode is a reading aid inferred from timing, and the interface must say so: label it `episode`, show it as a subdued grouping rule rather than a column value, and never use the words chat, thread, conversation, or session for it. A guessed identity that looks authoritative is worse than an empty cell. 13px body, monospace for every technical column, newest first, sortable by latency and timestamp. A row expands in place to reveal full arguments and any error, using the same expandable-inspection pattern as the tool timeline. Never auto-expand raw JSON.

Above the table, a compact summary strip: total calls, calls by source, error rate, p50/p95 latency — the same metric-card treatment used for token usage, so the two read as one system.

### MCP servers view

A full route showing the connected server as an operator would want it: gateway status and version, target endpoint and health, negotiated protocol version, the tool allowlist as it is actually configured, and the callers seen in the last hour with their call counts. This is the page that answers "is the thing up, and who is talking to it".

### Composer

Large text input with attachment/action affordances kept secondary. Send uses the primary blue button. While a run is active, replace send with a stop action. Keyboard-first: Enter sends, Shift+Enter newlines, focus is preserved across runs.

### Empty state

Use operational examples drawn from tools that actually exist: `Show AAPL's company profile`, `Compare JPM, BAC and WFC`, `MSFT financial ratios`, `NVDA revenue trend`, `Top 5 Financials by market cap`. Keep the empty state useful and quiet, not promotional, and state that the data is synthetic.

### Loading and streaming

No full-screen loaders. Stream assistant text into the existing message surface while tool states update beside it. Preserve previous content. Running tool rows update in place. A broken response stream is not resumable under this revision — surface a re-run affordance rather than implying silent recovery.

### Error handling

Errors are localized to the failing operation and preserve useful context. Name the operation, the code, and the elapsed time. Recommended copy:

| Condition | Copy |
| :--- | :--- |
| Tool failure | `Tool failed — compare_companies returned an error after 1.2s` |
| Header mismatch (`-32020`) | `Request rejected — header/body mismatch on tools/call. Refreshing tool definitions.` |
| Unsupported version (`-32022`) | `Protocol mismatch — server supports 2025-11-25. Retrying on a supported revision.` |
| Resource not found (`-32602`) | `Resource not found — market://companies/XYZ` |
| Unknown method (`-32601`) | `Server does not implement prompts/get` |
| Endpoint unreachable | `Can't reach the MCP endpoint at /mcp. Is the backend running on :8000?` |

Offer retry only for idempotent reads. Never replace the conversation with a generic failure state.

## Do's and Don'ts

- Do make runtime behavior legible without exposing raw implementation details by default.
- Do distinguish the orchestrator, tools, and resources through hierarchy and accent, not decoration.
- Do use monospace for telemetry, tool names, resource URIs, protocol versions, and error codes.
- Do keep the right rail persistent on desktop so tool calls stay visible while the user reads the answer.
- Do expose exact token accounting when the backend provides provider usage — and hide the field when it does not.
- Do keep the server name visible for every MCP call.
- Do tag every fleet-scope row with its source, and keep conversation scope and fleet scope visually separate.
- Do label the dataset as synthetic wherever figures appear.
- Do make every nav entry resolve to a real view.
- Don't hide tool calls behind a developer-only mode; operational transparency is this product's value.
- Don't show chain-of-thought or private reasoning. Show execution summaries, tool names, statuses, and observable metadata.
- Don't render agents, session ids, cached-token counts, or context limits that the backend does not actually report.
- Don't merge this conversation's tool calls with other hosts' calls into one undifferentiated list.
- Don't guess a source. `unknown` is an honest answer; a plausible wrong hostname is not.
- Don't use color alone to encode state.
- Don't use giant avatars, oversized chat bubbles, or playful social-chat patterns.
- Don't place raw JSON in the main conversation unless explicitly requested; use generative cards and expandable inspection panels.
