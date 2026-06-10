import { useAuth } from "../hooks/useAuth";

// Top command bar: product mark, the signed-in tenant/email, and logout.
export function TopBar() {
  const { session, logout } = useAuth();
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
          <span title={session.tenantId}>
            {session.email} · tenant {session.tenantId.slice(0, 8)}…
          </span>
          <button className="btn btn-ghost btn-small" data-testid="logout-btn" onClick={logout}>
            Sign out
          </button>
        </div>
      )}
    </header>
  );
}
