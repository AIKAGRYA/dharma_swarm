import assert from "node:assert/strict";
import test from "node:test";

import { buildDashboardNavSections, isDashboardPathActive } from "./dashboardNav.ts";
import { CONTROL_PLANE_ROUTE_DECK } from "./controlPlaneSurfaces.ts";

function commandSection() {
  const section = buildDashboardNavSections().find((entry) => entry.label === "COMMAND");
  assert.ok(section, "expected COMMAND section");
  return section;
}

test("COMMAND section has Overview, Control Surface, then the canonical operator deck", () => {
  const items = commandSection().items;

  assert.equal(items[0].label, "Overview");
  assert.equal(items[0].href, "/dashboard");
  assert.equal(items[1].label, "Control Surface");
  assert.equal(items[1].href, "/dashboard/control-surface");
  assert.deepEqual(
    items.slice(2, 2 + CONTROL_PLANE_ROUTE_DECK.length).map((item) => item.label),
    CONTROL_PLANE_ROUTE_DECK.map((route) => route.label),
  );
});

test("COMMAND section stays lean (max 12 items) to prevent nav inflation", () => {
  const items = commandSection().items;
  assert.ok(items.length <= 12, `COMMAND has ${items.length} items, expected <= 12`);
});

test("Semantic Graph lives in DEEP, not COMMAND", () => {
  const sections = buildDashboardNavSections();
  const deep = sections.find((s) => s.label === "DEEP");
  assert.ok(deep, "expected DEEP section");
  const semanticGraph = deep.items.find((item) => item.href === "/dashboard/claude");
  assert.equal(semanticGraph?.label, "Semantic Graph");
  assert.equal(commandSection().items.some((item) => item.label === "Control Plane"), false);
});

test("isDashboardPathActive keeps nested routes attached to their canonical top-level nav item", () => {
  assert.equal(isDashboardPathActive("/dashboard/agents", "/dashboard/agents/agent-7"), true);
  assert.equal(isDashboardPathActive("/dashboard/qwen35", "/dashboard/qwen35/telemetry"), true);
});

test("isDashboardPathActive does not let /dashboard match every nested route", () => {
  assert.equal(isDashboardPathActive("/dashboard", "/dashboard"), true);
  assert.equal(isDashboardPathActive("/dashboard", "/dashboard/command-post"), false);
  assert.equal(isDashboardPathActive("/dashboard/log", "/dashboard/logbook"), false);
});
