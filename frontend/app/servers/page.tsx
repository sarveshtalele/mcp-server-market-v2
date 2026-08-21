"use client";

import { useEffect, useState } from "react";
import {
  Capabilities,
  ServersInfo,
  fmtTime,
  getCapabilities,
  getServers,
} from "@/lib/api";
import { ToolPolicy } from "@/components/servers/ToolPolicy";

/** MCP Servers — is the thing up, and who is talking to it. */
export default function ServersPage() {
  const [info, setInfo] = useState<ServersInfo | null>(null);
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    const load = () =>
      Promise.all([getServers(controller.signal), getCapabilities(controller.signal)])
        .then(([servers, caps]) => {
          setInfo(servers);
          setCapabilities(caps);
          setError(null);
        })
        .catch((cause: unknown) => {
          if ((cause as Error).name !== "AbortError") setError((cause as Error).message);
        });
    load();
    const timer = setInterval(load, 10_000);
    return () => {
      controller.abort();
      clearInterval(timer);
    };
  }, []);

  const declared = capabilities?.declared;
  const reachable = capabilities?.reachable;

  return (
    <>
      <header className="top">
        <div>
          <div className="top__title">MCP Servers</div>
          <div className="top__sub">Gateway status, capability surface and callers</div>
        </div>
        <div className="top__meta">
          <span className={`badge ${capabilities?.gateway_connected ? "badge--ok" : "badge--err"}`}>
            {capabilities?.gateway_connected ? "● Gateway reachable" : "● Gateway unreachable"}
          </span>
          <span className="badge">MCP {info?.server.protocol_version ?? "…"}</span>
        </div>
      </header>

      <div className="page">
        {error && (
          <div className="notice">
            <b>Cannot reach the backend.</b> {error}
          </div>
        )}
        {capabilities && !capabilities.gateway_connected && (
          <div className="notice">
            <b>Gateway offline.</b> {capabilities.gateway_error}
          </div>
        )}
        <div className="grid-2">
          <div className="panel">
            <p className="panel__title">SERVER</p>
            <div className="meta-block">
              name&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; = <b>{info?.server.name ?? "—"}</b>
              <br />
              version&nbsp;&nbsp; = <b>{info?.server.version ?? "—"}</b>
              <br />
              protocol&nbsp; = <b>{info?.server.protocol_version ?? "—"}</b>
              <br />
              endpoint&nbsp; = <b>{info?.server.endpoint ?? "—"}</b>
              <br />
              transport = <b>{info?.server.transport ?? "—"}</b>
              <br />
              data&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; = <b>synthetic</b>
            </div>
          </div>

          <div className="panel">
            <p className="panel__title">GATEWAY</p>
            <div className="meta-block">
              url&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; = <b>{info?.gateway.url ?? "—"}</b>
              <br />
              config&nbsp;&nbsp; = <b>{info?.gateway.configured ? "loaded" : "not found"}</b>
              <br />
              allowlist = <b>{info?.gateway.allowlist.length ?? 0} tools</b>
              <br />
              in sync&nbsp; ={" "}
              <b>
                {info?.gateway.allowlist_matches_tools === true
                  ? "yes"
                  : info?.gateway.allowlist_matches_tools === false
                    ? "NO — allowlist differs from tools/list"
                    : "—"}
              </b>
              <br />
              listeners = <b>{info?.live_listeners ?? 0} live UI stream(s)</b>
            </div>
          </div>
        </div>

        <div className="panel">
          <p className="panel__title">CAPABILITY SURFACE</p>
          <div className="metrics">
            <div className="metric">
              <b>{declared?.tools.length ?? 0}</b>
              <span>tools declared</span>
            </div>
            <div className="metric">
              <b>{reachable?.tools.length ?? 0}</b>
              <span>tools via gateway</span>
            </div>
            <div className="metric">
              <b>
                {(declared?.resources.length ?? 0) +
                  (declared?.resource_templates.length ?? 0)}
              </b>
              <span>resources declared</span>
            </div>
            <div className="metric">
              <b>{reachable?.resources.length ?? 0}</b>
              <span>resources via gateway</span>
            </div>
            <div className="metric">
              <b>{declared?.prompts.length ?? 0}</b>
              <span>prompts declared</span>
            </div>
            <div className="metric">
              <b>{reachable?.prompts.length ?? 0}</b>
              <span>prompts via gateway</span>
            </div>
          </div>

          <div style={{ marginTop: "var(--s-lg)" }}>
            <div>
              <p className="panel__title">RESOURCES &amp; PROMPTS</p>
              <div className="chips">
                {(declared?.resources ?? []).concat(declared?.resource_templates ?? []).map(
                  (uri) => (
                    <span key={uri} className="chip chip--resource">
                      <span className="chip__state" />
                      {uri}
                    </span>
                  ),
                )}
                {(declared?.prompts ?? []).map((prompt) => (
                  <span key={prompt} className="chip chip--prompt">
                    {prompt}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="panel">
          <ToolPolicy onSaved={() => setInfo(null)} />
        </div>

        <div className="panel">
          <p className="panel__title">CALLERS SEEN · LAST HOUR</p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Source</th>
                  <th className="mono">clientInfo.name</th>
                  <th className="mono">Version</th>
                  <th className="mono">Calls</th>
                  <th className="mono">Last seen</th>
                </tr>
              </thead>
              <tbody>
                {(info?.callers_seen ?? []).length === 0 && (
                  <tr>
                    <td colSpan={5} className="muted">
                      No callers in the last hour.
                    </td>
                  </tr>
                )}
                {(info?.callers_seen ?? []).map((caller) => (
                  <tr key={`${caller.source}:${caller.caller_name}:${caller.caller_version}`}>
                    <td>
                      <span
                        className={`source-tag ${
                          caller.source === "unknown" ? "source-tag--unknown" : ""
                        }`}
                      >
                        {caller.source}
                      </span>
                    </td>
                    <td className="mono">{caller.caller_name ?? "—"}</td>
                    <td className="mono">{caller.caller_version ?? "—"}</td>
                    <td className="mono">{caller.calls}</td>
                    <td className="mono">{fmtTime(caller.last_seen)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted" style={{ marginTop: "var(--s-sm)" }}>
            Sources come from <span className="mono">io.modelcontextprotocol/clientInfo</span>,
            which travels in <span className="mono">_meta</span> on every request under
            MCP 2026-07-28. A caller that sends nothing usable is recorded as{" "}
            <span className="mono">unknown</span> — never guessed.
          </p>
        </div>
      </div>
    </>
  );
}
