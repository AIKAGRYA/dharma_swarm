// FACE-2 command post laws (design truth DESIGN_FEEDBACK_OPERATOR_20260612 +
// handoff §7): status single-source (F-164), one-row status line (F-110),
// de-bordered chrome (F-165), Hokusai truecolor tokens, no-vermilion-offline.
import {describe, expect, test} from "bun:test";
import React from "react";

import {ShellHeader} from "../src/components/ShellHeader";
import {StatusFooter} from "../src/components/StatusFooter";
import {OperatorSummaryBand} from "../src/components/OperatorSummaryBand";
import {buildOperatorSummaryItems} from "../src/app";
import {initialState} from "../src/state";
import {AGENT_STATES, THEME} from "../src/theme";

function flattenText(node: React.ReactNode): string {
  if (node === null || node === undefined || typeof node === "boolean") {
    return "";
  }
  if (typeof node === "string" || typeof node === "number") {
    return String(node);
  }
  if (Array.isArray(node)) {
    return node.map((child) => flattenText(child)).join("");
  }
  if (React.isValidElement(node)) {
    return flattenText(node.props.children);
  }
  return "";
}

type TextNodeProbe = {text: string; color?: string; bold?: boolean};

function collectTextNodes(node: React.ReactNode, out: TextNodeProbe[] = []): TextNodeProbe[] {
  if (node === null || node === undefined || typeof node === "boolean" || typeof node === "string" || typeof node === "number") {
    return out;
  }
  if (Array.isArray(node)) {
    for (const child of node) {
      collectTextNodes(child, out);
    }
    return out;
  }
  if (React.isValidElement(node)) {
    const props = node.props as {children?: React.ReactNode; color?: string; bold?: boolean};
    const text = flattenText(props.children);
    if (text.trim().length > 0) {
      out.push({text, color: props.color, bold: props.bold});
    }
    collectTextNodes(props.children, out);
  }
  return out;
}

describe("StatusFooter — the ONE status row (F-110/F-164)", () => {
  test("offline renders the ○ gate in persimmon (never vermilion) and suppresses READY", () => {
    const footer = StatusFooter({
      mode: "compose",
      routeLabel: "codex:gpt-5.4",
      bridgeStatus: "offline",
      routeState: "ready",
      strategy: "responsive",
    });
    const text = flattenText(footer);
    expect(text).toContain("compose");
    expect(text).toContain("route codex:gpt-5.4");
    expect(text).toContain("○ offline");
    // A dead bridge cannot certify a ready route (design truth directive #2).
    expect(text).not.toContain("ready");
    const gateNode = collectTextNodes(footer).find((node) => node.text.trim() === "○ offline");
    expect(gateNode?.color).toBe(THEME.persimmon);
    expect(gateNode?.color).not.toBe(THEME.vermilion);
  });

  test("connected renders bridge transport plus the route gate state exactly once", () => {
    const footer = StatusFooter({
      mode: "session list",
      routeLabel: "anthropic:claude",
      bridgeStatus: "connected",
      routeState: "ready",
      strategy: "responsive",
    });
    const text = flattenText(footer);
    expect(text).toContain("● bridge");
    expect(text.split("ready").length - 1).toBe(1);
    expect(text).not.toContain("live");
  });

  test("the model name renders through the parchment identity accent", () => {
    const footer = StatusFooter({
      mode: "compose",
      routeLabel: "codex:gpt-5.4",
      bridgeStatus: "offline",
      routeState: "ready",
    });
    const routeNode = collectTextNodes(footer).find((node) => node.text === "codex:gpt-5.4");
    expect(routeNode?.color).toBe(THEME.parchment);
  });
});

describe("ShellHeader — identity only, zero status tokens (F-164/F-165)", () => {
  test("carries brand + place and never offline/ready/route/model status", () => {
    const header = ShellHeader({activeTitle: "Sessions", activeCount: 15});
    const text = flattenText(header);
    expect(text).toContain("◆ DHARMA");
    expect(text).toContain("COMMAND POST");
    expect(text).toContain("Sessions");
    expect(text).toContain("panes 15");
    expect(text.toLowerCase()).not.toContain("offline");
    expect(text.toLowerCase()).not.toContain("ready");
    expect(text).not.toContain("route ");
  });

  test("compact header drops the suffix but keeps the brand glyph", () => {
    const header = ShellHeader({activeTitle: "Chat", compact: true});
    const text = flattenText(header);
    expect(text).toContain("◆ DHARMA");
    expect(text).not.toContain("COMMAND POST");
  });
});

describe("OperatorSummaryBand — calm density (FACE-2)", () => {
  test("empty values render quiet stone and never bold", () => {
    const band = OperatorSummaryBand({
      items: [
        {label: "loop", value: "unknown", tone: "neutral"},
        {label: "verify", value: "1 failing, 3/4 passing", tone: "critical"},
      ],
    });
    const nodes = collectTextNodes(band);
    const empty = nodes.find((node) => node.text === "unknown");
    expect(empty?.color).toBe(THEME.stone);
    expect(empty?.bold ?? false).toBe(false);
    const critical = nodes.find((node) => node.text === "1 failing, 3/4 passing");
    expect(critical?.color).toBe(THEME.vermilion);
  });
});

describe("status single-source projection (F-164)", () => {
  test("the summary band carries ops data only — bridge/route/strategy live in the status row", () => {
    const labels = buildOperatorSummaryItems(initialState).map((item) => item.label);
    expect(labels).toEqual(["loop", "verify", "runtime", "approvals", "sessions"]);
  });
});

describe("Nihonga Mineral truecolor tokens (operator pick 2026-06-16)", () => {
  test("surfaces and core text land the mineral-pigment spec values", () => {
    expect(THEME.night).toBe("#14110E"); // warm sumi black
    expect(THEME.indigo).toBe("#201913");
    expect(THEME.foam).toBe("#E8DCC0"); // gofun cream
    expect(THEME.wave).toBe("#6FA890"); // rokushō verdigris — chrome accent
    expect(THEME.persimmon).toBe("#E0A24E"); // ōdo ochre
    expect(THEME.vermilion).toBe("#E85A4E"); // shu vermilion
    expect(THEME.ridge).toBe("#9A7C5A"); // kincha ridge
  });

  test("AGENT_STATES pairs every color with a glyph (color never sole signal)", () => {
    for (const state of Object.values(AGENT_STATES)) {
      expect(state.glyph.length).toBeGreaterThan(0);
      expect(state.color.startsWith("#")).toBe(true);
    }
    expect(AGENT_STATES.offline.glyph).toBe("○");
    expect(AGENT_STATES.error.color).toBe(THEME.vermilion);
  });
});
