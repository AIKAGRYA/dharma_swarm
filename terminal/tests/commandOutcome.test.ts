import {describe, expect, test} from "bun:test";

import {normalizeCommandOutcome} from "../src/commandOutcome";

describe("normalizeCommandOutcome", () => {
  test("only explicit completed plus ok=true permits a completion glyph", () => {
    expect(normalizeCommandOutcome({outcome: "completed", ok: true})).toEqual({
      outcome: "completed",
      phase: "complete",
      terminal: true,
      rendersCompletion: true,
      reason: "explicit_completed",
    });
    expect(normalizeCommandOutcome({outcome: "completed", ok: false}).rendersCompletion).toBe(false);
  });

  test("keeps accepted work running without rendering completion", () => {
    expect(normalizeCommandOutcome({outcome: "accepted", ok: true})).toEqual({
      outcome: "accepted",
      phase: "running",
      terminal: false,
      rendersCompletion: false,
      reason: "explicit_accepted",
    });
  });

  test("projects unsupported and failed outcomes as terminal failures", () => {
    expect(normalizeCommandOutcome({outcome: "unsupported", ok: false})).toMatchObject({
      outcome: "unsupported",
      phase: "failed",
      terminal: true,
      rendersCompletion: false,
    });
    expect(normalizeCommandOutcome({outcome: "failed", ok: false})).toMatchObject({
      outcome: "failed",
      phase: "failed",
      terminal: true,
      rendersCompletion: false,
    });
  });

  test("fails closed for missing, nested, unknown, and contradictory outcomes", () => {
    const cases = [
      {},
      {payload: {outcome: "completed", ok: true}},
      {outcome: "stub", ok: true},
      {outcome: "completed"},
      {outcome: "accepted", ok: false},
      {outcome: "unsupported", ok: true},
      {outcome: "failed", ok: true},
      {outcome: "completed", ok: true, completed: false},
      {outcome: "accepted", ok: true, completed: true},
      {outcome: "completed", ok: true, supported: false},
      {outcome: "failed", ok: false, supported: true},
      {outcome: "completed", ok: true, completed: "true"},
      null,
    ];
    for (const value of cases) {
      const normalized = normalizeCommandOutcome(value);
      expect(normalized.outcome).toBe("failed");
      expect(normalized.phase).toBe("failed");
      expect(normalized.rendersCompletion).toBe(false);
    }
  });
});
