import {describe, expect, test} from "bun:test";

import {wrapComposerText} from "../src/components/Composer";

describe("expandable composer wrapping", () => {
  test("short text stays one line", () => {
    expect(wrapComposerText("hello there", 40)).toEqual(["hello there"]);
  });

  test("greedy word-wrap at the width budget", () => {
    const lines = wrapComposerText("alpha bravo charlie delta echo", 11);
    expect(lines).toEqual(["alpha bravo", "charlie", "delta echo"]);
    expect(lines.every((line) => line.length <= 11)).toBe(true);
  });

  test("a word longer than the budget is hard-split", () => {
    expect(wrapComposerText("supercalifragilistic", 8)).toEqual(["supercal", "ifragili", "stic"]);
  });

  test("explicit newlines are honored as line breaks", () => {
    expect(wrapComposerText("line one\nline two", 40)).toEqual(["line one", "line two"]);
    expect(wrapComposerText("a\n\nb", 40)).toEqual(["a", "", "b"]);
  });

  test("the last line carries the typing position (no trailing collapse)", () => {
    const lines = wrapComposerText("one two three four five six seven eight nine ten", 9);
    // every visual line fits, and the final word is on the last line where the
    // cursor will render — so the operator always sees what they just typed.
    expect(lines.every((line) => line.length <= 9)).toBe(true);
    expect(lines.at(-1)).toContain("ten");
  });
});
