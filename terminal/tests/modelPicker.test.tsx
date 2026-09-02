import {describe, expect, test} from "bun:test";
import React from "react";

import {ModelPicker} from "../src/components/ModelPicker";
import type {RouteTarget} from "../src/types";

function flattenElementText(node: React.ReactNode): string[] {
  if (node === null || node === undefined || typeof node === "boolean") return [];
  if (typeof node === "string" || typeof node === "number") return [String(node)];
  if (Array.isArray(node)) return node.flatMap(flattenElementText);
  return React.isValidElement(node) ? flattenElementText(node.props.children) : [];
}

describe("ModelPicker /models table", () => {
  test("shows every lane with separate usable-now and identity-verified truth plus one-key shortcuts", () => {
    const choices = [
      {
        alias: "live-unverified",
        label: "Live but unverified",
        provider: "kimi_code",
        model: "k3",
        routeId: "kimi_code:k3",
        routeState: "unverified",
        selectable: true,
        usableNow: true,
        identityVerified: false,
      },
      {
        alias: "dead-verified",
        label: "Verified identity, dead lane",
        provider: "claude",
        model: "claude-opus-4.8",
        routeId: "claude:claude-opus-4.8",
        routeState: "unavailable",
        selectable: false,
        usableNow: false,
        identityVerified: true,
      },
    ] satisfies Array<RouteTarget & {usableNow: boolean; identityVerified: boolean}>;

    const text = flattenElementText(ModelPicker({choices, selectedIndex: 0})).join(" ").toLowerCase();

    expect(text).toContain("lane");
    expect(text).toContain("usable now");
    expect(text).toContain("identity verified");
    expect(text).toContain("live-unverified");
    expect(text).toContain("dead-verified");
    expect(text).toMatch(/1\D+live-unverified/);
    expect(text).toMatch(/2\D+dead-verified/);
  });
});
