import { useState } from "react";
import { buildNavSections, type Tab } from "../lib/nav";
import { useAuth } from "../hooks/useAuth";

// Grouped, collapsible left navigation. Sections are RBAC-filtered (a viewer
// never sees an admin-only group) and collapse to an icon rail. In-app state
// only — no localStorage.
export function Sidebar({ tab, onSelect }: { tab: Tab; onSelect: (t: Tab) => void }) {
  const { session } = useAuth();
  const [collapsed, setCollapsed] = useState(false);
  if (!session) return null;
  const sections = buildNavSections(session.role);

  return (
    <aside
      className={`sidebar ${collapsed ? "sidebar-collapsed" : ""}`}
      data-testid="sidebar"
      data-collapsed={collapsed ? "true" : "false"}
    >
      <button
        className="sidebar-toggle"
        data-testid="sidebar-toggle"
        aria-label="Toggle navigation"
        onClick={() => setCollapsed((c) => !c)}
      >
        {collapsed ? "»" : "«"}
      </button>

      <nav className="sidebar-nav">
        {sections.map((section) => (
          <div className="nav-group" key={section.group} data-testid={`nav-group-${section.group}`}>
            {!collapsed && (
              <div className="nav-group-label" data-testid={`nav-group-label-${section.group}`}>
                {section.group}
              </div>
            )}
            {collapsed && <div className="nav-group-divider" aria-hidden />}
            {section.items.map((item) => (
              <button
                key={item.id}
                className={`nav-item ${tab === item.id ? "active" : ""}`}
                data-testid={`nav-${item.id}`}
                aria-current={tab === item.id ? "page" : undefined}
                title={collapsed ? item.label : undefined}
                onClick={() => onSelect(item.id)}
              >
                <span className="nav-icon" aria-hidden>{item.icon}</span>
                {!collapsed && <span className="nav-label">{item.label}</span>}
              </button>
            ))}
          </div>
        ))}
      </nav>
    </aside>
  );
}
