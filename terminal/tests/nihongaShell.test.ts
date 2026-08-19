import {describe, expect, test} from "bun:test";

import {causalEventRowBudget, visibleCausalEvents} from "../src/nihonga/CausalFlowPlane";
import {routeStateForBridge} from "../src/nihonga/NihongaChrome";
import {projectWholeOrganism} from "../src/nihonga/organismView";
import {contextControlForLayout, placeForPane, planeForPane, usesNihongaShell, viewportProfile, workspaceLabel} from "../src/nihonga/shellModel";
import {unknownOnCallTruthState} from "../src/onCallTruth";
import {defaultRoutePolicy} from "../src/routePolicy";

describe("Nihonga Helm responsive profile", () => {
  test("selects the locked profiles at exact breakpoints", () => {
    expect(viewportProfile(43, 40)).toBe("resize-safe");
    expect(viewportProfile(100, 17)).toBe("resize-safe");
    expect(viewportProfile(44, 18)).toBe("survival");
    expect(viewportProfile(79, 24)).toBe("survival");
    expect(viewportProfile(80, 24)).toBe("compact");
    expect(viewportProfile(100, 28)).toBe("standard");
    expect(viewportProfile(119, 30)).toBe("standard");
    expect(viewportProfile(120, 29)).toBe("standard");
    expect(viewportProfile(120, 30)).toBe("panorama");
    expect(viewportProfile(220, 50)).toBe("panorama");
  });

  test("maps legacy facets into five places without making overlays into places", () => {
    expect(placeForPane("chat")).toBe("conversation");
    expect(placeForPane("agents")).toBe("activity");
    expect(placeForPane("repo")).toBe("evidence");
    expect(placeForPane("models")).toBe("system");
    expect(placeForPane("mission")).toBe("home");
    expect(planeForPane("timeline")).toBe("ecosystem");
    expect(planeForPane("approvals")).toBe("ecosystem");
    expect(planeForPane("ontology")).toBe("ecosystem");
  });

  test("keeps zen and scroll facets in Nihonga while isolating legacy deck focus", () => {
    expect(usesNihongaShell("zen")).toBe(true);
    expect(usesNihongaShell("scroll")).toBe(true);
    expect(usesNihongaShell("cockpit")).toBe(true);
    expect(usesNihongaShell("deck-focus:repo")).toBe(false);
    expect(contextControlForLayout("zen")).toBe("navigator");
    expect(contextControlForLayout("deck-focus:repo")).toBe("legacy-sidebar");
  });

  test("uses a bounded workspace label rather than a full path", () => {
    expect(workspaceLabel("/Users/dhyana/dharma_swarm")).toBe("dharma_swarm");
    expect(workspaceLabel("/Users/dhyana/dharma_swarm/terminal")).toBe("dharma_swarm");
    expect(workspaceLabel("/Users/dhyana/wt_helm_t02_20260819/terminal")).toBe("dharma_swarm");
    expect(workspaceLabel("/Users/dhyana/ds_helm_preview_20260819/terminal")).toBe("dharma_swarm");
    expect(workspaceLabel("C:\\work\\dharma_swarm")).toBe("dharma_swarm");
  });
});

test("causal row budgeting keeps the newest complete events visible", () => {
  const events = Array.from({length: 15}, (_, index) => ({
    id: `event-${index}`,
    sourceEventType: "fixture",
    kind: "status" as const,
    phase: "running" as const,
    title: `event ${index}`,
    summary: `summary ${index}`,
  }));

  expect(causalEventRowBudget(30)).toBe(13);
  const visible = visibleCausalEvents(events, 5);
  expect(visible.map((event) => event.id)).toEqual(["event-13", "event-14"]);
  expect(visible.at(-1)?.id).toBe("event-14");
});

test("whole-organism view does not promote configuration into liveness", () => {
  const regions = projectWholeOrganism({
    bridgeStatus: "connected",
    activeTurn: {phase: "idle"},
    routePolicy: {
      ...defaultRoutePolicy(),
      routeState: "unverified",
      selectable: true,
      provider: "codex_text",
      model: "gpt-5.6-sol",
    },
    onCallTruth: unknownOnCallTruthState(),
    authority: {
      repo: true,
      control: false,
      sessions: true,
      approvals: true,
      models: true,
      agents: true,
    },
  });

  expect(regions.find((region) => region.id === "intelligence")?.observation).toBe("unverified");
  expect(regions.find((region) => region.id === "intelligence")?.detail).toContain("bench ?/7");
  expect(regions.find((region) => region.id === "outward")?.observation).toBe("configured");
  expect(regions.find((region) => region.id === "outward")?.detail).toContain("contact unproved");
  expect(regions.find((region) => region.id === "delivery")?.observation).toBe("observed");
  expect(regions.find((region) => region.id === "core")?.observation).toBe("unknown");
});

test("a disconnected ready route becomes stale rather than observed", () => {
  const policy = {...defaultRoutePolicy(), routeState: "ready" as const, selectable: true};
  const regions = projectWholeOrganism({
    bridgeStatus: "offline",
    activeTurn: {phase: "idle"},
    routePolicy: policy,
    onCallTruth: unknownOnCallTruthState(),
    authority: {repo: false, control: false, sessions: false, approvals: false, models: false, agents: false},
  });

  expect(regions.find((region) => region.id === "intelligence")?.observation).toBe("stale");
  expect(routeStateForBridge("offline", "ready")).toBe("stale");
  expect(routeStateForBridge("connected", "ready")).toBe("ready");
});
