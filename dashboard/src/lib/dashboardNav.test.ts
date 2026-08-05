import assert from "node:assert/strict";
import test from "node:test";

import { buildDashboardNavSections, isDashboardPathActive } from "./dashboardNav.ts";
import { CONTROL_PLANE_ROUTE_DECK } from "./controlPlaneSurfaces.ts";

function commandSection() {
  const section = buildDashboardNavSections().find((entry) => entry.label === "COMMAND");
  assert.ok(section, "expected COMMAND section");
  return section;
}

test("buildDashboardNavSections keeps the canonical operator deck contiguous near the top of COMMAND", () => {
  const items = commandSection().items;
  const expectedLabels = [
    "Overview",
    "Cockpit",
    "Control Surface",
    ...CONTROL_PLANE_ROUTE_DECK.map((route) => route.label),
    "Conv. Log",
  ];
  const expectedHrefs = [
    "/dashboard",
    "/dashboard/cockpit",
    "/dashboard/control-surface",
    ...CONTROL_PLANE_ROUTE_DECK.map((route) => route.href),
  ];

  assert.deepEqual(
    items.slice(0, expectedLabels.length).map((item) => item.label),
    expectedLabels,
  );
  assert.deepEqual(
    items.slice(0, expectedHrefs.length).map((item) => item.href),
    expectedHrefs,
  );
});

test("buildDashboardNavSections avoids advertising /dashboard/claude as a second control plane", () => {
  const items = commandSection().items;
  const semanticGraph = items.find((item) => item.href === "/dashboard/claude");

  assert.equal(semanticGraph?.label, "Semantic Graph");
  assert.equal(items.some((item) => item.label === "Control Plane"), false);
});

test("buildDashboardNavSections exposes the organism beside the ecosystem map", () => {
  const items = commandSection().items;
  const ecosystemIndex = items.findIndex((item) => item.href === "/dashboard/ecosystem");
  const organismIndex = items.findIndex((item) => item.href === "/dashboard/organism");

  assert.ok(ecosystemIndex >= 0, "expected Ecosystem Map in COMMAND");
  assert.equal(organismIndex, ecosystemIndex + 1);
  assert.equal(items[organismIndex]?.label, "Organism");
  assert.equal(items[organismIndex]?.icon, "Orbit");
});

test("isDashboardPathActive keeps nested routes attached to their canonical top-level nav item", () => {
  assert.equal(isDashboardPathActive("/dashboard/agents", "/dashboard/agents/agent-7"), true);
  assert.equal(isDashboardPathActive("/dashboard/qwen35", "/dashboard/qwen35/telemetry"), true);
  assert.equal(
    isDashboardPathActive("/dashboard/organism", "/dashboard/organism/world-radar"),
    true,
  );
});

test("isDashboardPathActive does not let /dashboard match every nested route", () => {
  assert.equal(isDashboardPathActive("/dashboard", "/dashboard"), true);
  assert.equal(isDashboardPathActive("/dashboard", "/dashboard/command-post"), false);
  assert.equal(isDashboardPathActive("/dashboard/log", "/dashboard/logbook"), false);
});
