// Navigation model: the operator workflow split into RBAC-gated, grouped items.
// Pure data + a pure builder so the grouping/role logic is unit-testable
// without React (mirrors the backend's pure-logic discipline).
import type { Role } from "./types";

export type Tab =
  | "console"
  | "gate"
  | "policies"
  | "analytics"
  | "audit"
  | "webhooks"
  | "health";

export type NavGroup = "Operate" | "Analyze" | "Govern" | "Administer";

export interface NavItem {
  id: Tab;
  label: string;
  group: NavGroup;
  minRole: Role;
  icon: string;
}

// Role rank for "meets minimum" checks (mirrors backend RBAC ordering).
export const ROLE_RANK: Record<Role, number> = {
  viewer: 0,
  operator: 1,
  admin: 2,
  owner: 3,
};

export function roleAllows(role: Role, minRole: Role): boolean {
  return ROLE_RANK[role] >= ROLE_RANK[minRole];
}

// The canonical nav. Order within a group is declaration order.
export const NAV_ITEMS: NavItem[] = [
  { id: "console",   label: "Console",        group: "Operate",    minRole: "viewer",   icon: "▸" },
  { id: "gate",      label: "Promotion Gate", group: "Operate",    minRole: "operator", icon: "⊟" },
  { id: "analytics", label: "Analytics",      group: "Analyze",    minRole: "viewer",   icon: "◔" },
  { id: "policies",  label: "Policies",       group: "Govern",     minRole: "admin",    icon: "§" },
  { id: "audit",     label: "Audit",          group: "Govern",     minRole: "viewer",   icon: "⛓" },
  { id: "webhooks",  label: "Webhooks",       group: "Administer", minRole: "admin",    icon: "⇲" },
  { id: "health",    label: "Platform Health",group: "Administer", minRole: "viewer",   icon: "♥" },
];

export const NAV_GROUP_ORDER: NavGroup[] = ["Operate", "Analyze", "Govern", "Administer"];

export interface NavSection {
  group: NavGroup;
  items: NavItem[];
}

/**
 * Build ordered nav sections visible to `role`. Groups with no visible item
 * are dropped (no empty headers). Pure — unit-tested in nav.test.ts.
 */
export function buildNavSections(role: Role): NavSection[] {
  const visible = NAV_ITEMS.filter((i) => roleAllows(role, i.minRole));
  const sections: NavSection[] = [];
  for (const group of NAV_GROUP_ORDER) {
    const items = visible.filter((i) => i.group === group);
    if (items.length > 0) sections.push({ group, items });
  }
  return sections;
}

/** The set of tabs a role may open (used to guard the active tab). */
export function allowedTabs(role: Role): Set<Tab> {
  return new Set(NAV_ITEMS.filter((i) => roleAllows(role, i.minRole)).map((i) => i.id));
}
