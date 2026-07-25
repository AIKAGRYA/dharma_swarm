import {describe, expect, test} from "bun:test";

import {paneSwitcherWindow} from "../src/components/PaneSwitcher.tsx";
import type {TabSpec} from "../src/types.ts";

function tabs(count: number): TabSpec[] {
  return Array.from({length: count}, (_, index) => ({
    id: `pane-${index}`,
    title: `Pane ${index + 1}`,
    kind: "generic" as const,
    lines: [],
  }));
}

describe("compact pane switcher", () => {
  test("keeps a late selection inside the bounded 80x24 row window", () => {
    const window = paneSwitcherWindow(tabs(15), 13, 10);

    expect(window.start).toBe(5);
    expect(window.tabs).toHaveLength(10);
    expect(window.tabs.some((tab) => tab.id === "pane-13")).toBe(true);
  });

  test("keeps the first page anchored at the beginning", () => {
    const window = paneSwitcherWindow(tabs(15), 2, 10);
    expect(window.start).toBe(0);
    expect(window.tabs[0]?.id).toBe("pane-0");
  });
});
