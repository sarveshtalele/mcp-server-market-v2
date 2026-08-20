// Typed access to the backend's REST + observability surface.
//
// The backend is one process: REST, the MCP endpoint, the AG-UI stream and the
// audit query API all live behind the same origin.

export const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";
export const AGENT_URL = `${BACKEND_URL}/agui`;

export interface McpCall {
  id: number;
  ts: string;
  source: string;
  caller_name: string | null;
  caller_version: string | null;
  conversation_id: string | null;
  episode: number;
  method: string;
  resource_type: string | null;
  resource_name: string | null;
  args_preview: string | null;
  status: "ok" | "error";
  error_code: number | null;
  error_message: string | null;
  latency_ms: number;
  protocol_version: string | null;
  trace_id: string | null;
  via: string;
  extra_meta: string | null;
}

export interface CallsPage {
  total: number;
  limit: number;
  offset: number;
  calls: McpCall[];
}

export interface Summary {
  total_calls: number;
  error_count: number;
  error_rate_pct: number;
  by_source: Record<string, number>;
  by_tool: Record<string, number>;
  latency_p50_ms: number;
  latency_p95_ms: number;
  sources_seen: string[];
}

export interface Capabilities {
  declared: {
    server_name: string;
    server_version: string;
    protocol_version: string;
    instructions: string | null;
    tools: string[];
    resources: string[];
    resource_templates: string[];
    prompts: string[];
    cache_ttl_ms: number;
  };
  reachable: {
    protocol_version: string | null;
    tools: string[];
    resources: string[];
    resource_templates: string[];
    prompts: string[];
  } | null;
  gateway_url: string;
  gateway_connected: boolean;
  gateway_error?: string;
}

export interface PolicyTool {
  name: string;
  allowed: boolean;
}

export interface Policy {
  editable: boolean;
  config_path: string;
  tools: PolicyTool[];
  /** Allowlisted names the server no longer exposes. */
  orphaned: string[];
  restart_required?: boolean;
  message?: string;
}

export interface ServersInfo {
  server: {
    name: string;
    version: string;
    protocol_version: string;
    endpoint: string;
    transport: string;
    tools: string[];
  };
  gateway: {
    url: string;
    configured: boolean;
    allowlist: string[];
    allowlist_matches_tools: boolean | null;
    editable: boolean;
  };
  callers_seen: {
    source: string;
    caller_name: string | null;
    caller_version: string | null;
    calls: number;
    last_seen: string;
  }[];
  live_listeners: number;
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${BACKEND_URL}${path}`, { signal });
  if (!response.ok) {
    throw new Error(`${path} responded ${response.status} ${response.statusText}`);
  }
  return (await response.json()) as T;
}

export const getCalls = (query = "", signal?: AbortSignal) =>
  getJson<CallsPage>(`/observability/calls${query ? `?${query}` : ""}`, signal);

export const getSummary = (query = "", signal?: AbortSignal) =>
  getJson<Summary>(`/observability/summary${query ? `?${query}` : ""}`, signal);

export const getServers = (signal?: AbortSignal) =>
  getJson<ServersInfo>("/observability/servers", signal);

export const getCapabilities = (signal?: AbortSignal) =>
  getJson<Capabilities>("/agui/capabilities", signal);

export const getPolicy = (signal?: AbortSignal) =>
  getJson<Policy>("/observability/policy", signal);

/** Replace the gateway allowlist. Takes effect when the gateway restarts. */
export async function savePolicy(allowed: string[]): Promise<Policy> {
  const response = await fetch(`${BACKEND_URL}/observability/policy`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ allowed }),
  });
  const body = await response.json();
  if (!response.ok) {
    throw new Error(body?.detail ?? `${response.status} ${response.statusText}`);
  }
  return body as Policy;
}

/**
 * Subscribe to the live cross-host call feed.
 *
 * Every consumer reaches the server through the gateway, so this stream carries
 * calls made in Claude Desktop and an IDE as well as the ones this browser made.
 */
export function subscribeToCalls(onCall: (call: McpCall) => void): () => void {
  const source = new EventSource(`${BACKEND_URL}/observability/stream`);
  source.onmessage = (event) => {
    try {
      onCall(JSON.parse(event.data) as McpCall);
    } catch {
      /* keep-alive comments and malformed frames are ignored */
    }
  };
  return () => source.close();
}

export const fmtTime = (iso: string): string => {
  const date = new Date(iso.endsWith("Z") ? iso : `${iso}Z`);
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleTimeString();
};

export const fmtMs = (ms: number): string =>
  ms >= 1000 ? `${(ms / 1000).toFixed(2)} s` : `${Math.round(ms)} ms`;
