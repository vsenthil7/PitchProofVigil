import { useState } from "react";
import { TopBar } from "./components/TopBar";
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

type Tab = "console" | "gate" | "policies" | "analytics" | "audit" | "webhooks";

const TABS: { id: Tab; label: string }[] = [
  { id: "console", label: "Console" },
  { id: "gate", label: "Promotion Gate" },
  { id: "policies", label: "Policies" },
  { id: "analytics", label: "Analytics" },
  { id: "audit", label: "Audit" },
  { id: "webhooks", label: "Webhooks" },
];

// Tabs split the operator workflow. The right rail (platform health) shows on
// the operational tabs; full-width tabs (policies, analytics, audit, webhooks)
// use the whole canvas.
function Dashboard() {
  const { stats, refresh } = useStats();
  const [tab, setTab] = useState<Tab>("console");

  const fullWidth = tab === "policies" || tab === "analytics" || tab === "audit" || tab === "webhooks";

  return (
    <div className="app">
      <TopBar />

      <div className="tabs" data-testid="tabs">
        {TABS.map((t) => (
          <button
            key={t.id}
            className={`tab ${tab === t.id ? "active" : ""}`}
            data-testid={`tab-${t.id}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {fullWidth ? (
        <>
          {tab === "policies" && <PolicyEditor />}
          {tab === "analytics" && <AnalyticsPage />}
          {tab === "audit" && <AuditView />}
          {tab === "webhooks" && <WebhooksManager />}
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
  );
}

export default function App() {
  const { session } = useAuth();
  return session ? <Dashboard /> : <LoginPage />;
}
