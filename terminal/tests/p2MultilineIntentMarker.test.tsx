import {describe, expect, test} from "bun:test";
import React from "react";

import {Composer} from "../src/components/Composer";

function elementText(node: React.ReactNode): string {
  if (node === null || node === undefined || typeof node === "boolean") return "";
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(elementText).join(" ");
  if (React.isValidElement<{children?: React.ReactNode}>(node)) return elementText(node.props.children);
  return "";
}

function frameFor(prompt: string): string {
  return elementText(Composer({prompt, focused: true, width: 140})).replace(/\s+/g, " ").trim();
}

describe("P2 F3 multiline intent boundary", () => {
  test("a multiline draft visibly says it will go to chat and that UI intents are one-line only", () => {
    const visible = frameFor("open the sessions pane\nthen explain the latest run");

    expect(visible).toMatch(/multi-line\s*→\s*chat/i);
    expect(visible).toMatch(/intents are single-line/i);
  });

  test("an exact one-line UI intent does not wear the backend-chat warning", () => {
    const visible = frameFor("open the sessions pane");

    expect(visible).not.toMatch(/multi-line\s*→\s*chat/i);
    expect(visible).not.toMatch(/intents are single-line/i);
  });
});
