// Pure-logic check for the RBAC nav model. No test runner is configured in this
// project (e2e is Playwright-only), so this is a standalone Node assertion
// script — run with:  node --experimental-strip-types tests/unit/nav.check.mts
// from the frontend/ directory. It guards the role-gating + grouping invariants.
import assert from "node:assert/strict";
import { buildNavSections, allowedTabs, roleAllows, NAV_ITEMS } from "../../src/lib/nav.ts";

const owner = buildNavSections("owner");
assert.deepEqual(owner.map((s) => s.group), ["Operate", "Analyze", "Govern", "Administer"]);
assert.equal(owner.reduce((n, s) => n + s.items.length, 0), NAV_ITEMS.length);

const viewerTabs = [...allowedTabs("viewer")].sort();
assert.deepEqual(viewerTabs, ["analytics", "audit", "console", "health"]);
assert.ok(!viewerTabs.includes("gate"));
assert.ok(!viewerTabs.includes("policies"));
assert.ok(!viewerTabs.includes("webhooks"));

assert.ok([...allowedTabs("operator")].includes("gate"));
assert.ok(![...allowedTabs("operator")].includes("policies"));
assert.ok([...allowedTabs("admin")].includes("policies"));
assert.ok([...allowedTabs("admin")].includes("webhooks"));

assert.ok(roleAllows("owner", "admin"));
assert.ok(!roleAllows("viewer", "operator"));
assert.ok(buildNavSections("viewer").every((s) => s.items.length > 0));

console.log("nav.check: all assertions pass");
