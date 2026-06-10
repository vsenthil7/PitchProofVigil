import { useAuth } from "../hooks/useAuth";

// Top command bar: product mark, a tenant switcher (owners span multiple
// tenants), the signed-in role badge + email, and logout.
const ROLE_LABEL: Record<string, string> = {
  owner: "Owner",
  admin: "Admin",
  operator: "Operator",
  viewer: "Viewer",
};

export function TopBar() {
  const { session, logout, switchTenant } = useAuth();
  return (
    <header className="topbar">
      <div className="brand">
        <div className="brand-mark" aria-hidden>
          ◎
        </div>
        <div>
          <div className="brand-title">PitchProof Vigil</div>
          <div className="brand-sub">AGENT RELIABILITY CONTROL ROOM · T1 ARIZE</div>
        </div>
      </div>
      {session && (
        <div className="session" data-testid="session-bar">
          <label className="tenant-switch" title="Active tenant scope">
            <span className="tenant-switch-label">TENANT</span>
            <select
              data-testid="tenant-switcher"
              value={session.tenantId}
              disabled={session.tenants.length <= 1}
              onChange={(e) => switchTenant(e.target.value)}
            >
              {session.tenants.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </label>

          <span className={`role-badge role-${session.role}`} data-testid="role-badge">
            {ROLE_LABEL[session.role] ?? session.role}
          </span>

          <span className="session-email" title={session.email}>
            {session.email}
          </span>

          <button className="btn btn-ghost btn-small" data-testid="logout-btn" onClick={logout}>
            Sign out
          </button>
        </div>
      )}
    </header>
  );
}
