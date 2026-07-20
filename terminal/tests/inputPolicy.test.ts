import {describe, expect, test} from "bun:test";

import {isPlainReturn, normalizeComposerInput} from "../src/inputPolicy";

describe("normalizeComposerInput", () => {
  test("normalizes multiline CRLF paste without losing surrounding text", () => {
    expect(normalizeComposerInput("alpha\r\nbeta\rgamma")).toBe("alpha\nbeta\ngamma");
  });

  test("strips bracketed-paste wrappers and forbidden controls character by character", () => {
    expect(normalizeComposerInput("\u001b[200~safe\ttext\u0000\nnext\u001b[201~")).toBe("safetext\nnext");
  });

  test("preserves unicode and a Ctrl-J newline fallback", () => {
    expect(normalizeComposerInput("日本語\nhelm")).toBe("日本語\nhelm");
  });
});

describe("isPlainReturn", () => {
  test("distinguishes submit from multiline chunks", () => {
    expect(isPlainReturn("\r", true)).toBe(true);
    expect(isPlainReturn("", true)).toBe(true);
    expect(isPlainReturn("alpha\r\nbeta", true)).toBe(false);
    expect(isPlainReturn("\n", false)).toBe(false);
  });
});
