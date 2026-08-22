import assert from "node:assert/strict";
import test from "node:test";

import {
  classifyCampaignTaskEvidence,
  parseCampaignEvidence,
  type CampaignEvidenceProjection,
  type CampaignTaskIdentity,
} from "./missionCampaignEvidence.ts";

const missionId = "sadhana-10-20260823";
const taskId = "task-one";
const runId = "owner_run_0123456789abcdef01234567";
const dispatchId = "owner_dispatch_0123456789abcdef01234567";

function task(overrides: Partial<CampaignTaskIdentity> = {}): CampaignTaskIdentity {
  return {
    task_id: taskId,
    mission_id: missionId,
    status: "completed",
    assigned_to: "agent-one",
    metadata: {
      mission_control_owner_execution: {
        schema_version: "dharma.mission_control.owner_execution.v1",
        backend: "orchestrator",
        mission_id: missionId,
        task_id: taskId,
        dispatch_key: "default",
        run_id: runId,
        idempotency_key: dispatchId,
      },
      runtime_run_id: runId,
      run_id: runId,
      idempotency_key: dispatchId,
    },
    ...overrides,
  };
}

function evidence(
  overrides: Partial<CampaignEvidenceProjection> = {},
): CampaignEvidenceProjection {
  return {
    schema_version: "dharma.mission_control.campaign_evidence.v1",
    authority: "TaskBoard+RuntimeStateStore+owner execution projection",
    observed_at: "2026-08-22T22:00:00.000Z",
    owner_executions: [
      {
        ref: {
          backend: "orchestrator",
          mission_id: missionId,
          task_id: taskId,
          dispatch_key: "default",
          run_id: runId,
          claim_id: "claim-one",
          agent_id: "agent-one",
          idempotency_key: dispatchId,
          owner_session_id: "owner-session-one",
        },
        task_status: "completed",
        run_status: "completed",
        claim_status: "completed",
        stale: false,
        receipt_ids: ["receipt-one"],
        terminal: true,
        succeeded: true,
        result: "Useful checked result",
        failure_code: "",
        observed_at: "2026-08-22T21:59:59.000Z",
        proves_executor_liveness: false,
      },
    ],
    candidate_task_ids: [],
    accepted_task_ids: [taskId],
    rejected_task_ids: [],
    conflicting_acceptance_task_ids: [],
    invalid_acceptance_receipts: 0,
    acceptance_state: "accepted",
    proves_executor_liveness: false,
    proves_semantic_acceptance: true,
    ...overrides,
  };
}

test("promotes only an exact succeeded owner execution plus acceptance", () => {
  const result = classifyCampaignTaskEvidence(evidence(), task());
  assert.equal(result.state, "verified_complete");
  assert.equal(result.acceptance, "accepted");
  assert.equal(result.ownerExecution?.ref.run_id, runId);
});

test("keeps a succeeded owner result candidate-only without acceptance", () => {
  const result = classifyCampaignTaskEvidence(
    evidence({
      candidate_task_ids: [taskId],
      accepted_task_ids: [],
      acceptance_state: "candidate_only",
      proves_semantic_acceptance: false,
    }),
    task(),
  );
  assert.equal(result.state, "candidate_unverified");
  assert.equal(result.acceptance, "not_observed");
});

test("owner motion never self-promotes to verified work", () => {
  const moving = evidence({
    owner_executions: [
      {
        ...evidence().owner_executions[0],
        task_status: "in_progress",
        run_status: "running",
        claim_status: "running",
        receipt_ids: [],
        terminal: false,
        succeeded: false,
        result: "",
      },
    ],
    accepted_task_ids: [],
    acceptance_state: "unobserved",
    proves_semantic_acceptance: false,
  });
  const result = classifyCampaignTaskEvidence(
    moving,
    task({ status: "in_progress" }),
  );
  assert.equal(result.state, "active_unverified");
  assert.match(result.detail, /do not prove substantive work/);
});

test("rejection and conflict dominate a succeeded owner result", () => {
  const rejected = classifyCampaignTaskEvidence(
    evidence({
      accepted_task_ids: [],
      rejected_task_ids: [taskId],
      acceptance_state: "rejected",
      proves_semantic_acceptance: false,
    }),
    task(),
  );
  assert.equal(rejected.state, "rejected");

  const conflicting = classifyCampaignTaskEvidence(
    evidence({
      accepted_task_ids: [],
      conflicting_acceptance_task_ids: [taskId],
      acceptance_state: "conflicting",
      proves_semantic_acceptance: false,
    }),
    task(),
  );
  assert.equal(conflicting.state, "conflict");
});

test("fails closed on a mismatched task stamp or malformed verdict lattice", () => {
  const mismatched = task({
    metadata: {
      ...task().metadata,
      runtime_run_id: "owner_run_foreign",
    },
  });
  assert.equal(
    classifyCampaignTaskEvidence(evidence(), mismatched).state,
    "conflict",
  );

  const overlapping = evidence({ rejected_task_ids: [taskId] });
  assert.equal(parseCampaignEvidence(overlapping), null);
  assert.equal(
    classifyCampaignTaskEvidence(overlapping, task()).state,
    "conflict",
  );
});

test("absence remains unknown instead of becoming idle, active, or complete", () => {
  const result = classifyCampaignTaskEvidence(undefined, task());
  assert.equal(result.state, "none");
  assert.equal(result.acceptance, "not_observed");
});
