import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { useAuth } from "../hooks/useAuth";
import type { TenantSummary } from "../lib/types";

// Owner-only organization lifecycle. Lists every tenant the platform owner can
// see and lets them disable (suspend) or enable an org. A disabled org retains
// all data but blocks new logins and tenant-switches into it. You cannot
// disable the org you are currently signed into (guarded server-side too).
export function OrganizationsPage() {
  const { session } = useAuth();
  const [orgs, setOrgs] = useState<TenantSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = () => {
    api
      .listTenants()
      .then(setOrgs)
      .catch((e) => setError(e instanceof Error ? e.message : "failed to load"));
  };

  useEffect(() => {
    load();
  }, []);

  const toggle = async (org: TenantSummary) => {
    setError(null);
    setBusyId(org.id);
    try {
      await api.setTenantActive(org.id, !org.is_active);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "update failed");
    } finally {
      setBusyId(null);
    }
  };

  const activeCount = orgs.filter((o) => o.is_active).length;

  return (
    <section className="panel" data-testid="organizations-page">
      <div className="panel-head">
        <span className="panel-title">Organizations</span>
        <span className="panel-sub" data-testid="org-count">
          {activeCount}/{orgs.length} active
        </span>
      </div>

      <p className="hint" data-testid="org-hint">
        Disable an organization to suspend all access (logins and tenant
        switches are blocked) without deleting any data. Re-enable to restore
        it. You cannot disable the organization you are signed into.
      </p>

      {error && (
        <div className="auth-error" data-testid="org-error">
          {error}
        </div>
      )}

      {orgs.length === 0 ? (
        <div className="empty" data-testid="orgs-empty">
          no organizations visible
        </div>
      ) : (
        <div data-testid="org-list">
          {orgs.map((org) => {
            const isCurrent = org.id === session?.tenantId;
            return (
              <div className="webhook-row" key={org.id} data-testid="org-row">
                <span className="webhook-event">{org.name}</span>
                <span className="webhook-url">{org.slug}</span>
                <span
                  className={`role-badge ${org.is_active ? "role-operator" : "role-viewer"}`}
                  data-testid={`org-status-${org.id}`}
                >
                  {org.is_active ? "active" : "disabled"}
                </span>
                {isCurrent ? (
                  <span className="hint" data-testid={`org-current-${org.id}`}>
                    current session
                  </span>
                ) : (
                  <button
                    className={`btn btn-small ${org.is_active ? "btn-ghost" : "btn-primary"}`}
                    data-testid={`org-toggle-${org.id}`}
                    disabled={busyId === org.id}
                    onClick={() => toggle(org)}
                  >
                    {org.is_active ? "Disable" : "Enable"}
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
