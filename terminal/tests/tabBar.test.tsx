import {describe, expect, test} from "bun:test";
import React from "react";

import {TabBar} from "../src/components/TabBar";
import {OperatorSummaryBand} from "../src/components/OperatorSummaryBand";
import type {TabSpec} from "../src/types";

function collectProps(node: React.ReactNode, out: Array<Record<string, unknown>>): Array<Record<string, unknown>> {
  if (node === null || node === undefined || typeof node === "boolean") {
    return out;
  }
  if (Array.isArray(node)) {
    node.forEach((child) => collectProps(child, out));
    return out;
  }
  if (React.isValidElement(node)) {
    out.push(node.props as Record<string, unknown>);
    collectProps((node.props as {children?: React.ReactNode}).children, out);
  }
  return out;
}

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
    return flattenText((node.props as {children?: React.ReactNode}).children);
  }
  return "";
}

function tabSpec(id: string, title: string): TabSpec {
  return {id, title, kind: "transcript", lines: []} as unknown as TabSpec;
}

const FIFTEEN_TABS: TabSpec[] = [
  tabSpec("chat", "Chat"),
  tabSpec("mission", "Mission"),
  tabSpec("repo", "Repo"),
  tabSpec("commands", "Commands"),
  tabSpec("models", "Models"),
  tabSpec("ontology", "Ontology"),
  tabSpec("runtime", "Runtime"),
  tabSpec("sessions", "Sessions"),
  tabSpec("approvals", "Approvals"),
  tabSpec("control", "Control"),
  tabSpec("agents", "Agents"),
  tabSpec("evolution", "Evolution"),
  tabSpec("thinking", "Thinking"),
  tabSpec("tools", "Tools"),
  tabSpec("timeline", "Timeline"),
];

describe("TabBar (F-021 one-line law)", () => {
  test("wide mode renders a borderless single-row window of at most 6 tabs with overflow markers", () => {
    const bar = TabBar({tabs: FIFTEEN_TABS, activeTabId: "chat", compact: false});
    const props = collectProps(bar, []);
    expect(props.some((p) => "borderStyle" in p && p.borderStyle !== undefined)).toBe(false);
    expect(props.some((p) => p.flexWrap === "wrap")).toBe(false);
    const text = flattenText(bar);
    expect(text).toContain("[Chat]");
    expect(text).toContain("▸");
    const shownTitles = FIFTEEN_TABS.filter((tab) => text.includes(tab.title)).length;
    expect(shownTitles).toBeLessThanOrEqual(6);
  });

  test("wide mode keeps full titles; compact mode truncates titles past 8 chars", () => {
    const wide = flattenText(TabBar({tabs: FIFTEEN_TABS, activeTabId: "approvals", compact: false}));
    expect(wide).toContain("[Approvals]");
    const compact = flattenText(TabBar({tabs: FIFTEEN_TABS, activeTabId: "approvals", compact: true}));
    expect(compact).toContain("[Approva…]");
    expect(compact).not.toContain("Approvals");
  });

  test("windows around the active tab with left and right overflow markers", () => {
    const bar = TabBar({tabs: FIFTEEN_TABS, activeTabId: "agents", compact: false});
    const text = flattenText(bar);
    expect(text).toContain("◂");
    expect(text).toContain("▸");
    expect(text).toContain("[Agents]");
  });
});

describe("OperatorSummaryBand compact strip (F-021)", () => {
  test("compact band is a borderless single strip, not a bordered box", () => {
    const band = OperatorSummaryBand({
      compact: true,
      items: [
        {label: "loop", value: "unknown", tone: "neutral"},
        {label: "verify", value: "unknown", tone: "neutral"},
        {label: "runtime", value: "idle", tone: "neutral"},
        {label: "approvals", value: "clear", tone: "live"},
      ],
    });
    const props = collectProps(band, []);
    expect(props.some((p) => "borderStyle" in p && p.borderStyle !== undefined)).toBe(false);
    const text = flattenText(band);
    expect(text).toContain("loop");
    expect(text).toContain("approvals");
  });
});
