import assert from "node:assert/strict";
import test from "node:test";

import {
  buildReceiptLadder,
  deriveEvidenceComparisonNow,
  deriveFreshness,
  mergeActivity,
} from "../../lib/a2aNodeModel.ts";

const MODEL_NOW = Date.parse("2026-07-14T18:00:00Z");

test("query updates advance comparison now for evidence arriving between ticks", () => {
  const lastClockTick = MODEL_NOW;
  const evidenceTimestamp = "2026-07-14T18:00:10Z";
  const queryDataUpdatedAt = MODEL_NOW + 11_000;
  assert.deepEqual(deriveFreshness(evidenceTimestamp, lastClockTick), {
    state: "unknown",
    ageMs: null,
  });

  const comparisonNow = deriveEvidenceComparisonNow(lastClockTick, [
    0,
    queryDataUpdatedAt,
    MODEL_NOW + 5_000,
  ]);
  assert.equal(comparisonNow, queryDataUpdatedAt);
  assert.deepEqual(deriveFreshness(evidenceTimestamp, comparisonNow), {
    state: "runtime",
    ageMs: 1_000,
  });
});

test("every duplicate receipt is unknown across conflicting-tier permutations", () => {
  const strongDuplicate = {
    id: "same-receipt",
    title: "Strong duplicate",
    body: "to: agni\ncontact_evidence_tier: DOMAIN_RECEIPTED",
    status: "review",
    created_at: "2026-07-14T17:58:00Z",
  };
  const weakDuplicate = {
    id: "same-receipt",
    title: "Weak duplicate",
    body: "to: agni\ncontact_evidence_tier: NO_CONTACT",
    status: "review",
    created_at: "2026-07-14T17:59:00Z",
  };
  const unique = {
    id: "unique-receipt",
    title: "Unique receipt",
    body: "to: hermes\ncontact_evidence_tier: HANDLER_ACKED",
    status: "review",
    created_at: "2026-07-14T17:57:00Z",
  };
  const permutations = [
    [strongDuplicate, weakDuplicate, unique],
    [weakDuplicate, unique, strongDuplicate],
    [unique, strongDuplicate, weakDuplicate],
  ];

  for (const records of permutations) {
    const ladder = buildReceiptLadder(records, MODEL_NOW);
    assert.deepEqual(
      ladder.tiers.map(({ count }) => count),
      [0, 1, 0, 0, 0],
    );
    const duplicateEvidence = ladder.records.filter(
      ({ id }) => id === "same-receipt",
    );
    assert.equal(duplicateEvidence.length, 2);
    assert.ok(
      duplicateEvidence.every(
        ({ state, tier, reason }) =>
          state === "unknown" &&
          tier === null &&
          /duplicate receipt id/i.test(reason ?? ""),
      ),
    );

    const duplicateActivity = mergeActivity([], records, MODEL_NOW).filter(
      ({ id }) => id === "same-receipt",
    );
    assert.equal(duplicateActivity.length, 2);
    assert.ok(
      duplicateActivity.every(
        ({ evidenceState, detail }) =>
          evidenceState === "unknown" &&
          /duplicate receipt id/i.test(detail),
      ),
    );
  }
});
