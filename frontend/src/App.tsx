import { useState } from "react";
import { TopBar } from "./components/TopBar";
import { Console } from "./components/Console";
import { GatePanel } from "./components/GatePanel";
import { Metrics } from "./components/Metrics";
import { LiveFeed } from "./components/LiveFeed";
import { useHealth } from "./hooks/useHealth";
import { useLiveFeed } from "./hooks/useLiveFeed";

// Root layout for the control room. Left column = operator actions (console +
// gate); right column = situational awareness (metrics + live feed). A shared
// refresh counter re-pulls health/drift after any action that adds traces.
export default function App() {
  const { health, refresh } = useHealth();
  const { events, connected } = useLiveFeed();
  const [refreshKey, setRefreshKey] = useState(0);

  const bump = () => {
    setRefreshKey((k) => k + 1);
    refresh();
  };

  return (
    <div className="app">
      <TopBar health={health} />
      <div className="grid">
        <div>
          <Console onTraceAdded={bump} />
          <div className="section-gap">
            <GatePanel onGateRun={bump} />
          </div>
        </div>
        <div>
          <Metrics health={health} refreshKey={refreshKey} />
          <LiveFeed events={events} connected={connected} />
        </div>
      </div>
    </div>
  );
}
