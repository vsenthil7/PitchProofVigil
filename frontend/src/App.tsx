import { useState } from "react";
import { TopBar } from "./components/TopBar";
import { Console } from "./components/Console";
import { GatePanel } from "./components/GatePanel";
import { StatsPanel } from "./components/StatsPanel";
import { useAuth } from "./hooks/useAuth";
import { useStats } from "./hooks/useStats";
import { LoginPage } from "./pages/LoginPage";
import { PolicyEditor } from "./pages/PolicyEditor";

type Tab = "console" | "gate" | "policies";

// Authenticated control room. Tabs split the operator workflow: live console,
// promotion gate, and the policy editor. The right rail always shows platform
// health. Unauthenticated users see the login/register screen.
function Dashboard() {
  const { stats, refresh } = useStats();
  const [tab, setTab] = useState<Tab>("console");

  return (
    <div className="app">
      <TopBar />

      <div className="tabs" data-testid="tabs">
        <button
          className={`tab ${tab === "console" ? "active" : ""}`}
          data-testid="tab-console"
          onClick={() => setTab("console")}
        >
          Console
        </button>
        <button
          className={`tab ${tab === "gate" ? "active" : ""}`}
          data-testid="tab-gate"
          onClick={() => setTab("gate")}
        >
          Promotion Gate
        </button>
        <button
          className={`tab ${tab === "policies" ? "active" : ""}`}
          data-testid="tab-policies"
          onClick={() => setTab("policies")}
        >
          Policies
        </button>
      </div>

      {tab === "policies" ? (
        <PolicyEditor />
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
