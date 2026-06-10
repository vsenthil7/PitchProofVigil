import { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";
import { useAuth } from "../hooks/useAuth";
import { NAV_ITEMS, buildNavSections } from "../lib/nav";

// Platform-health self-check. Pings the live backend probes (liveness,
// readiness, security posture) and verifies client-side invariants (session,
// nav wiring), so an operator can see at a glance that the control room is
// wired to a healthy backend. Mirrors the SpoofVane demo-health pattern.
interface Check {
  label: string;
  state: "ok" | "warn" | "fail" | "pending";
  detail: string;
}

export function HealthPage() {
  const { session } = useAuth();
  const [checks, setChecks] = useState<Check[]>([]);
  const [ranAt, setRanAt] = useState<string>("");

  const run = useCallback(async () => {
    const next: Check[] = [];

    // 1. Liveness
    try {
      const h = await api.health();
      next.push({ label: "API liveness", state: h.status === "ok" ? "ok" : "warn", detail: `/health → ${h.status}` });
    } catch (e) {
      next.push({ label: "API liveness", state: "fail", detail: msg(e) });
    }

    // 2. Readiness
    try {
      const r = await api.ready();
      next.push({ label: "API readiness", state: r.ready ? "ok" : "warn", detail: r.ready ? "dependencies ready" : "not ready" });
    } catch (e) {
      next.push({ label: "API readiness", state: "fail", detail: msg(e) });
    }

    // 3. Encryption posture
    try {
      const s = await api.securityStatus();
      next.push({
        label: "Encryption at rest",
        state: s.encryption_at_rest ? (s.using_ephemeral_dev_key ? "warn" : "ok") : "fail",
        detail: s.using_ephemeral_dev_key
          ? `ephemeral dev key (set ENCRYPTION_KEYS) · ring ${s.key_ring_size}`
          : `key ring ${s.key_ring_size} · rotation ${s.rotation_supported ? "on" : "off"}`,
      });
    } catch (e) {
      next.push({ label: "Encryption at rest", state: "fail", detail: msg(e) });
    }

    // 4. Authenticated session (client invariant)
    next.push({
      label: "Authenticated session",
      state: session ? "ok" : "fail",
      detail: session ? `${session.email} · ${session.role} · ${session.tenantName}` : "no session",
    });

    // 5. Navigation wiring (every nav item resolves to a known group)
    const sections = session ? buildNavSections(session.role) : [];
    const navCount = sections.reduce((n, s) => n + s.items.length, 0);
    next.push({
      label: "Navigation wiring",
      state: navCount > 0 ? "ok" : "fail",
      detail: `${navCount}/${NAV_ITEMS.length} items visible to ${session?.role ?? "—"} across ${sections.length} groups`,
    });

    setChecks(next);
    setRanAt(new Date().toLocaleTimeString());
  }, [session]);

  useEffect(() => {
    run();
    const t = setInterval(run, 5000);
    return () => clearInterval(t);
  }, [run]);

  const passed = checks.filter((c) => c.state === "ok").length;
  const anyFail = checks.some((c) => c.state === "fail");
  const summaryState = checks.length === 0 ? "pending" : anyFail ? "fail" : passed === checks.length ? "ok" : "warn";

  return (
    <section className="panel" data-testid="health-page">
      <div className="panel-head">
        <span className="panel-title">Platform Health</span>
        <button className="btn btn-ghost btn-small" data-testid="health-refresh" onClick={run}>
          Re-run
        </button>
      </div>

      <div className={`health-summary health-${summaryState}`} data-testid="health-summary">
        <span className="health-summary-icon" aria-hidden>
          {summaryState === "ok" ? "✓" : summaryState === "fail" ? "✕" : "…"}
        </span>
        <span>
          {checks.length === 0
            ? "Running checks…"
            : `${passed}/${checks.length} checks healthy${ranAt ? ` · ${ranAt}` : ""}`}
        </span>
      </div>

      <div className="health-list" data-testid="health-checks">
        {checks.map((c) => (
          <div className={`health-row health-${c.state}`} key={c.label} data-testid={`health-${c.state}`}>
            <span className="health-dot" aria-hidden />
            <span className="health-label">{c.label}</span>
            <span className="health-detail">{c.detail}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

function msg(e: unknown): string {
  return e instanceof Error ? e.message : "unreachable";
}
