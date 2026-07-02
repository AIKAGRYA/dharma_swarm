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
    ...CONTROL_PLANE_ROUTE_DECK.map((route) => route.label),
    "Conv. Log",
  ];
  const expectedHrefs = [
    "/dashboard",
    "/dashboard/cockpit",
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

test("buildDashboardNavSections exposes Livelihood Loom as an internal command surface", () => {
  const items = commandSection().items;
  const loom = items.find((item) => item.href === "/dashboard/livelihood-loom");

  assert.equal(loom?.label, "Livelihood Loom");
  assert.equal(loom?.icon, "HeartPulse");
  assert.equal(loom?.level, 1);
});

test("isDashboardPathActive keeps nested routes attached to their canonical top-level nav item", () => {
  assert.equal(isDashboardPathActive("/dashboard/agents", "/dashboard/agents/agent-7"), true);
  assert.equal(isDashboardPathActive("/dashboard/qwen35", "/dashboard/qwen35/telemetry"), true);
  assert.equal(
    isDashboardPathActive(
      "/dashboard/livelihood-loom",
      "/dashboard/livelihood-loom/packet/packet_01",
    ),
    true,
  );
});

test("isDashboardPathActive does not let /dashboard match every nested route", () => {
  assert.equal(isDashboardPathActive("/dashboard", "/dashboard"), true);
  assert.equal(isDashboardPathActive("/dashboard", "/dashboard/command-post"), false);
  assert.equal(isDashboardPathActive("/dashboard/log", "/dashboard/logbook"), false);
});
