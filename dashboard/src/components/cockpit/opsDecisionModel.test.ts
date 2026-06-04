import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import type { ControlSurfaceRow } from "../../lib/types.ts";
import {
  decisionBucketForRow,
  decisionBuckets,
  proposalPreviewForRow,
} from "./opsDecisionModel.ts";

function row(overrides: Partial<ControlSurfaceRow>): ControlSurfaceRow {
  return {
    id: "live_ops.test",
    kind: "fleet",
    label: "Test surface",
    authority_role: "observed_authority",
    declared_state: "live",
    desired_state: "live",
    observed_state: "healthy",
    coherence_state: "bound",
    priority: "p1",
    owner_module: "scripts/runtime/live_ops_census.py",
    truth_owner: "live_ops_census",
    evidence: [],
    freshness: "2026-06-04T00:00:00+00:00",
    gap_codes: [],
    next_action: "",
    human_decision_required: false,
    source_refs: [],
    raw: {},
    ...overrides,
  };
}

test("decisionBucketForRow classifies operator-facing buckets deterministically", () => {
  assert.equal(decisionBucketForRow(row({ human_decision_required: true })), "needs_john");
  assert.equal(decisionBucketForRow(row({ kind: "pr_queue" })), "pr_queue");
  assert.equal(decisionBucketForRow(row({ gap_codes: ["vps_candidate"] })), "vps_candidates");
  assert.equal(decisionBucketForRow(row({ gap_codes: ["heavy_local_load"] })), "heavy_local_load");
  assert.equal(decisionBucketForRow(row({ observed_state: "blocked" })), "blocked");
  assert.equal(decisionBucketForRow(row({ gap_codes: ["freshness_state:stale"] })), "stale_refresh");
  assert.equal(decisionBucketForRow(row({ gap_codes: ["authority_tier:direct_probe"] })), "live_unauthorized");
});

test("decisionBuckets returns visible counts for the cockpit bucket rail", () => {
  const buckets = decisionBuckets([
    row({ human_decision_required: true }),
    row({ kind: "pr_queue" }),
    row({ gap_codes: ["heavy_local_load"] }),
  ]);

  const byKey = new Map(buckets.map((bucket) => [bucket.key, bucket.count]));
  assert.equal(byKey.get("needs_john"), 1);
  assert.equal(byKey.get("pr_queue"), 1);
  assert.equal(byKey.get("heavy_local_load"), 1);
});

test("proposalPreviewForRow renders packet text without execution authority", () => {
  const preview = proposalPreviewForRow(
    row({
      id: "pr.#446",
      kind: "pr_queue",
      source_refs: [{ kind: "file", path: "scripts/runtime/pr_merge_control.py" }],
      evidence: [{ kind: "file", source: "~/.dharma/pr_review/queue/latest.json" }],
      raw: {
        pr_number: 446,
        queue_status: "GITHUB_GREEN_NEEDS_PACKET",
      },
    }),
  );

  assert.equal(preview?.kind, "pr_packet_proposal");
  assert.equal(preview?.commandText, "make pr-packet PR=446");
  assert.equal(preview?.sourceRefCount, 1);
  assert.equal(preview?.evidenceCount, 1);
  assert.equal(preview?.forbiddenInlineExecution, true);
});

test("proposal cockpit files do not add mutation paths", () => {
  const files = [
    "dashboard/src/components/cockpit/OpsRunbookPanel.tsx",
    "dashboard/src/components/cockpit/SystemTruthMatrix.tsx",
    "dashboard/src/components/cockpit/opsDecisionModel.ts",
  ];
  const forbidden = [
    "fetch(",
    "apiFetch",
    "gh pr merge",
    "gh pr close",
    "pkill",
    "kill ",
    "subprocess",
    "process-control",
  ];

  for (const file of files) {
    const source = readFileSync(file, "utf8");
    for (const token of forbidden) {
      assert.equal(source.includes(token), false, `${file} must not contain ${token}`);
    }
  }
});
