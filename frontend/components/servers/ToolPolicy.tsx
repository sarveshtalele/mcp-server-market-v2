"use client";

import { useEffect, useState } from "react";
import { Policy, getPolicy, savePolicy } from "@/lib/api";

/**
 * The gateway's tool allowlist, editable.
 *
 * This is the governance boundary: a tool that is not permitted here is refused
 * at the gateway before it ever reaches the server. Two things the UI has to be
 * honest about, because getting either wrong would mislead an operator about
 * what is actually enforced:
 *
 *  - Saving writes the gateway's config file but does **not** take effect until
 *    the gateway restarts, since it reads its config only at startup.
 *  - Unsaved toggles are pending state, not policy. They are marked as such.
 */
export function ToolPolicy({ onSaved }: { onSaved?: () => void }) {
  const [policy, setPolicy] = useState<Policy | null>(null);
  const [draft, setDraft] = useState<Record<string, boolean>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [needsRestart, setNeedsRestart] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    getPolicy(controller.signal)
      .then((loaded) => {
        setPolicy(loaded);
        setDraft(Object.fromEntries(loaded.tools.map((t) => [t.name, t.allowed])));
      })
      .catch((cause: unknown) => {
        if ((cause as Error).name !== "AbortError") setError((cause as Error).message);
      });
    return () => controller.abort();
  }, []);

  if (error && !policy) {
    return (
      <div className="notice">
        <b>Cannot load the allowlist.</b> {error}
      </div>
    );
  }
  if (!policy) return <div className="muted">Loading allowlist…</div>;

  const dirty = policy.tools.some((tool) => draft[tool.name] !== tool.allowed);
  const allowedCount = Object.values(draft).filter(Boolean).length;

  async function save() {
    setSaving(true);
    setError(null);
    try {
      const allowed = Object.entries(draft)
        .filter(([, on]) => on)
        .map(([name]) => name);
      const updated = await savePolicy(allowed);
      setPolicy(updated);
      setDraft(Object.fromEntries(updated.tools.map((t) => [t.name, t.allowed])));
      setNeedsRestart(true);
      onSaved?.();
    } catch (cause: unknown) {
      setError((cause as Error).message);
    } finally {
      setSaving(false);
    }
  }

  function reset() {
    setDraft(Object.fromEntries(policy!.tools.map((t) => [t.name, t.allowed])));
    setError(null);
  }

  return (
    <>
      <div className="policy__head">
        <div>
          <p className="panel__title" style={{ margin: 0 }}>
            TOOL ACCESS · GATEWAY ALLOWLIST
          </p>
          <span className="muted">
            {allowedCount} of {policy.tools.length} tools permitted · enforced at the
            gateway, before the server is reached
          </span>
        </div>
        {policy.editable && (
          <div className="policy__actions">
            {dirty && (
              <button className="btn btn--secondary" onClick={reset} disabled={saving}>
                Reset
              </button>
            )}
            <button className="btn" onClick={save} disabled={!dirty || saving}>
              {saving ? "Saving…" : dirty ? "Save changes" : "Saved"}
            </button>
          </div>
        )}
      </div>

      {!policy.editable && (
        <div className="notice">
          <b>Read-only.</b> Editing is disabled (<span className="mono">ALLOW_POLICY_EDIT=false</span>).
          Change the allowlist in <span className="mono">{policy.config_path}</span>.
        </div>
      )}

      {error && (
        <div className="notice notice--error">
          <b>Save failed.</b> {error}
        </div>
      )}

      {needsRestart && !dirty && (
        <div className="notice">
          <b>Saved — restart the gateway to apply.</b> agentgateway reads its config
          only at startup, so the calls it permits have not changed yet. Run{" "}
          <span className="mono">python3 scripts/dev.py gateway</span>.
        </div>
      )}

      {dirty && (
        <div className="notice">
          <b>Unsaved changes.</b> These toggles are not policy until you save — and
          not enforced until the gateway restarts.
        </div>
      )}

      {policy.orphaned.length > 0 && (
        <div className="notice">
          <b>Allowlisted but not exposed:</b>{" "}
          <span className="mono">{policy.orphaned.join(", ")}</span>. Harmless, but it
          means the config names tools this server no longer has.
        </div>
      )}

      <div className="policy__grid">
        {policy.tools.map((tool) => {
          const on = draft[tool.name];
          const changed = on !== tool.allowed;
          return (
            <label
              key={tool.name}
              className={`policy__row ${on ? "policy__row--on" : "policy__row--off"} ${
                changed ? "policy__row--changed" : ""
              }`}
              title={
                policy.editable
                  ? on
                    ? "Permitted — click to block"
                    : "Blocked at the gateway — click to permit"
                  : "Read-only"
              }
            >
              <input
                type="checkbox"
                checked={on}
                disabled={!policy.editable || saving}
                onChange={(event) =>
                  setDraft({ ...draft, [tool.name]: event.target.checked })
                }
              />
              <span className="policy__name mono">{tool.name}</span>
              <span className="policy__state">
                {on ? "permitted" : "blocked"}
                {changed ? " *" : ""}
              </span>
            </label>
          );
        })}
      </div>
    </>
  );
}
