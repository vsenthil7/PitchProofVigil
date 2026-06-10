import { useEffect, useState } from "react";
import { TopBar } from "./components/TopBar";
import { Sidebar } from "./components/Sidebar";
import { Console } from "./components/Console";
import { GatePanel } from "./components/GatePanel";
import { StatsPanel } from "./components/StatsPanel";
import { useAuth } from "./hooks/useAuth";
import { useStats } from "./hooks/useStats";
import { LoginPage } from "./pages/LoginPage";
import { PolicyEditor } from "./pages/PolicyEditor";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { AuditView } from "./pages/AuditView";
import { WebhooksManager } from "./pages/WebhooksManager";
import { HealthPage } from "./pages/HealthPage";
import { allowedTabs, type Tab } from "./lib/nav";

// The shell: grouped collapsible sidebar + top bar + the active surface. The
// right rail (platform stats) shows only on the operational tabs; the rest use
// the full canvas.
function Dashboard() {
  const { session } = useAuth();
  const { stats, refresh } = useStats();
  const [tab, setTab] = useState<Tab>("console");

  // RBAC guard: if the session's role can't open the current tab (e.g. after a
  // tenant switch lands a viewer on an admin tab), fall back to Console.
  const allowed = allowedTabs(session!.role);
  useEffect(() => {
    if (!allowed.has(tab)) setTab("console");
  }, [allowed, tab]);

  const fullWidth =
    tab === "policies" || tab === "analytics" || tab === "audit" ||
    tab === "webhooks" || tab === "health";

  return (
    <div className="app">
      <TopBar />
      <div className="shell">
        <Sidebar tab={tab} onSelect={setTab} />
        <div className="surface" data-testid="surface">
          {fullWidth ? (
            <>
              {tab === "policies" && <PolicyEditor />}
              {tab === "analytics" && <AnalyticsPage />}
              {tab === "audit" && <AuditView />}
              {tab === "webhooks" && <WebhooksManager />}
              {tab === "health" && <HealthPage />}
            </>
          ) : (
            <div className="grid">
              <div>
                {tab === "console" && <Console onTraceAdded={refresh} />}
                {tab === "gate" && <GatePanel onGateRun={refresh} />}
              </div>
              <div>
                <StatsPanel stats={stats} />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const { session } = useAuth();
  return session ? <Dashboard /> : <LoginPage />;
}
