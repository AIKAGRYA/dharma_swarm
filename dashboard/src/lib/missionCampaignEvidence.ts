const CAMPAIGN_EVIDENCE_SCHEMA =
  "dharma.mission_control.campaign_evidence.v1";
const OWNER_EXECUTION_SCHEMA =
  "dharma.mission_control.owner_execution.v1";

export interface CampaignOwnerExecutionRef {
  backend: string;
  mission_id: string;
  task_id: string;
  dispatch_key: string;
  run_id: string;
  claim_id: string;
  agent_id: string;
  idempotency_key: string;
  owner_session_id: string;
}

export interface CampaignOwnerExecution {
  ref: CampaignOwnerExecutionRef;
  task_status: string;
  run_status: string;
  claim_status: string;
  stale: boolean;
  receipt_ids: string[];
  terminal: boolean;
  succeeded: boolean;
  result: string;
  failure_code: string;
  observed_at: string;
  proves_executor_liveness: false;
}

export interface CampaignEvidenceProjection {
  schema_version: typeof CAMPAIGN_EVIDENCE_SCHEMA;
  authority: string;
  observed_at: string;
  owner_executions: CampaignOwnerExecution[];
  candidate_task_ids: string[];
  accepted_task_ids: string[];
  rejected_task_ids: string[];
  conflicting_acceptance_task_ids: string[];
  invalid_acceptance_receipts: number;
  acceptance_state:
    | "unobserved"
    | "candidate_only"
    | "accepted"
    | "rejected"
    | "conflicting";
  proves_executor_liveness: false;
  proves_semantic_acceptance: boolean;
}

export interface CampaignTaskIdentity {
  task_id: string;
  mission_id: string;
  status: string;
  assigned_to: string;
  metadata: Record<string, unknown>;
}

export type CampaignTaskEvidenceState =
  | "none"
  | "active_unverified"
  | "candidate_unverified"
  | "verified_complete"
  | "rejected"
  | "conflict";

export interface CampaignTaskEvidenceVerdict {
  state: CampaignTaskEvidenceState;
  acceptance: "accepted" | "rejected" | "not_observed";
  label: string;
  detail: string;
  ownerExecution: CampaignOwnerExecution | null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isIdentifier(value: unknown): value is string {
  return (
    typeof value === "string" &&
    value.length > 0 &&
    value.length <= 500 &&
    value.trim() === value &&
    !/\s/.test(value)
  );
}

function canonicalIds(value: unknown): value is string[] {
  if (!Array.isArray(value) || !value.every(isIdentifier)) return false;
  return (
    new Set(value).size === value.length &&
    value.every((item, index) => index === 0 || value[index - 1] < item)
  );
}

function uniqueIds(value: unknown): value is string[] {
  return (
    Array.isArray(value) &&
    value.every(isIdentifier) &&
    new Set(value).size === value.length
  );
}

function parseOwnerExecution(value: unknown): CampaignOwnerExecution | null {
  if (!isRecord(value) || !isRecord(value.ref)) return null;
  const ref = value.ref;
  if (
    ref.backend !== "orchestrator" ||
    ![
      "mission_id",
      "task_id",
      "dispatch_key",
      "run_id",
      "claim_id",
      "agent_id",
      "idempotency_key",
      "owner_session_id",
    ].every((field) => isIdentifier(ref[field])) ||
    !["task_status", "run_status", "claim_status", "result", "failure_code"].every(
      (field) => typeof value[field] === "string",
    ) ||
    typeof value.stale !== "boolean" ||
    typeof value.terminal !== "boolean" ||
    typeof value.succeeded !== "boolean" ||
    value.proves_executor_liveness !== false ||
    !uniqueIds(value.receipt_ids) ||
    typeof value.observed_at !== "string" ||
    !Number.isFinite(Date.parse(value.observed_at))
  ) {
    return null;
  }
  return value as unknown as CampaignOwnerExecution;
}

function expectedAcceptanceState(
  evidence: Pick<
    CampaignEvidenceProjection,
    | "candidate_task_ids"
    | "accepted_task_ids"
    | "rejected_task_ids"
    | "conflicting_acceptance_task_ids"
  >,
): CampaignEvidenceProjection["acceptance_state"] {
  if (evidence.conflicting_acceptance_task_ids.length > 0) return "conflicting";
  if (evidence.accepted_task_ids.length > 0) return "accepted";
  if (evidence.rejected_task_ids.length > 0) return "rejected";
  if (evidence.candidate_task_ids.length > 0) return "candidate_only";
  return "unobserved";
}

/**
 * Validate the browser-facing evidence shape again before it can promote a
 * presentation claim. The API is authoritative; this guard prevents a future
 * loose caller or malformed fixture from turning arbitrary JSON into truth.
 */
export function parseCampaignEvidence(
  value: unknown,
): CampaignEvidenceProjection | null {
  if (
    !isRecord(value) ||
    value.schema_version !== CAMPAIGN_EVIDENCE_SCHEMA ||
    typeof value.authority !== "string" ||
    typeof value.observed_at !== "string" ||
    !Number.isFinite(Date.parse(value.observed_at)) ||
    !Array.isArray(value.owner_executions) ||
    !canonicalIds(value.candidate_task_ids) ||
    !canonicalIds(value.accepted_task_ids) ||
    !canonicalIds(value.rejected_task_ids) ||
    !canonicalIds(value.conflicting_acceptance_task_ids) ||
    typeof value.invalid_acceptance_receipts !== "number" ||
    !Number.isInteger(value.invalid_acceptance_receipts) ||
    value.invalid_acceptance_receipts < 0 ||
    value.proves_executor_liveness !== false ||
    typeof value.proves_semantic_acceptance !== "boolean"
  ) {
    return null;
  }
  const owners = value.owner_executions.map(parseOwnerExecution);
  if (owners.some((owner) => owner === null)) return null;
  const typedOwners = owners as CampaignOwnerExecution[];
  const ownerTaskIds = typedOwners.map((owner) => owner.ref.task_id);
  const ownerRunIds = typedOwners.map((owner) => owner.ref.run_id);
  if (
    new Set(ownerTaskIds).size !== ownerTaskIds.length ||
    new Set(ownerRunIds).size !== ownerRunIds.length
  ) {
    return null;
  }
  const verdictSets = [
    value.candidate_task_ids,
    value.accepted_task_ids,
    value.rejected_task_ids,
    value.conflicting_acceptance_task_ids,
  ] as string[][];
  const verdictIds = verdictSets.flat();
  if (
    new Set(verdictIds).size !== verdictIds.length ||
    !verdictIds.every((taskId) => ownerTaskIds.includes(taskId))
  ) {
    return null;
  }
  const evidence = {
    ...value,
    owner_executions: typedOwners,
  } as unknown as CampaignEvidenceProjection;
  if (
    evidence.acceptance_state !== expectedAcceptanceState(evidence) ||
    evidence.proves_semantic_acceptance !==
      (evidence.accepted_task_ids.length > 0)
  ) {
    return null;
  }
  return evidence;
}

function exactOwnerForTask(
  evidence: CampaignEvidenceProjection,
  task: CampaignTaskIdentity,
): CampaignOwnerExecution | null {
  const matching = evidence.owner_executions.filter(
    (owner) =>
      owner.ref.mission_id === task.mission_id &&
      owner.ref.task_id === task.task_id,
  );
  if (matching.length !== 1) return null;
  const owner = matching[0];
  const stamp = task.metadata.mission_control_owner_execution;
  if (
    !isRecord(stamp) ||
    stamp.schema_version !== OWNER_EXECUTION_SCHEMA ||
    stamp.backend !== "orchestrator" ||
    stamp.mission_id !== task.mission_id ||
    stamp.task_id !== task.task_id ||
    stamp.dispatch_key !== owner.ref.dispatch_key ||
    stamp.run_id !== owner.ref.run_id ||
    stamp.idempotency_key !== owner.ref.idempotency_key ||
    task.assigned_to !== owner.ref.agent_id ||
    owner.task_status !== task.status ||
    (task.metadata.runtime_run_id !== undefined &&
      task.metadata.runtime_run_id !== owner.ref.run_id) ||
    (task.metadata.run_id !== undefined &&
      task.metadata.run_id !== owner.ref.run_id) ||
    (task.metadata.idempotency_key !== undefined &&
      task.metadata.idempotency_key !== owner.ref.idempotency_key)
  ) {
    return null;
  }
  return owner;
}

function verdict(
  state: CampaignTaskEvidenceState,
  acceptance: CampaignTaskEvidenceVerdict["acceptance"],
  label: string,
  detail: string,
  ownerExecution: CampaignOwnerExecution | null,
): CampaignTaskEvidenceVerdict {
  return { state, acceptance, label, detail, ownerExecution };
}

/**
 * Typed promotion rule:
 * CandidateResult(exact succeeded owner run) + IndependentAcceptance(task id)
 * -> VerifiedComplete. No connectivity or owner self-observation can inhabit
 * the VerifiedComplete state.
 */
export function classifyCampaignTaskEvidence(
  rawEvidence: unknown,
  task: CampaignTaskIdentity,
): CampaignTaskEvidenceVerdict {
  if (rawEvidence === undefined || rawEvidence === null) {
    return verdict("none", "not_observed", "Not observed", "No campaign evidence was projected.", null);
  }
  const evidence = parseCampaignEvidence(rawEvidence);
  if (!evidence) {
    return verdict(
      "conflict",
      "not_observed",
      "Evidence conflict",
      "Campaign evidence has an invalid or internally conflicting shape; no claim is promoted.",
      null,
    );
  }
  const owner = exactOwnerForTask(evidence, task);
  const hasOwnerRow = evidence.owner_executions.some(
    (candidate) => candidate.ref.task_id === task.task_id,
  );
  const isCandidate = evidence.candidate_task_ids.includes(task.task_id);
  const isAccepted = evidence.accepted_task_ids.includes(task.task_id);
  const isRejected = evidence.rejected_task_ids.includes(task.task_id);
  const isConflicting =
    evidence.conflicting_acceptance_task_ids.includes(task.task_id);

  if (isConflicting) {
    return verdict(
      "conflict",
      "not_observed",
      "Acceptance conflict",
      "Independent acceptance evidence conflicts; positive claims are suppressed.",
      owner,
    );
  }
  if (isRejected) {
    return verdict(
      "rejected",
      "rejected",
      "Rejected",
      "The independent acceptance verdict rejected this terminal result.",
      owner,
    );
  }
  if (hasOwnerRow && !owner) {
    return verdict(
      "conflict",
      "not_observed",
      "Owner conflict",
      "The owner observation does not match the task's canonical owner stamp.",
      null,
    );
  }
  const succeededTerminal = Boolean(
    owner?.terminal &&
      owner.succeeded &&
      owner.run_status === "completed" &&
      owner.task_status === "completed" &&
      task.status === "completed",
  );
  if (isAccepted) {
    if (!owner || !succeededTerminal || !evidence.proves_semantic_acceptance) {
      return verdict(
        "conflict",
        "not_observed",
        "Promotion conflict",
        "Acceptance lacks an exact succeeded owner execution; no completion claim is promoted.",
        owner,
      );
    }
    return verdict(
      "verified_complete",
      "accepted",
      "Verified complete",
      "Exact succeeded owner execution and independent semantic acceptance are coherent.",
      owner,
    );
  }
  if (isCandidate || succeededTerminal) {
    return verdict(
      "candidate_unverified",
      "not_observed",
      "Candidate · unverified",
      "A terminal owner result exists, but independent acceptance was not observed.",
      owner,
    );
  }
  if (owner && !owner.terminal) {
    return verdict(
      "active_unverified",
      "not_observed",
      "Owner observed · unverified",
      "The owner run is observed, but owner state and connectivity do not prove substantive work.",
      owner,
    );
  }
  return verdict("none", "not_observed", "Not observed", "No exact owner evidence exists for this task.", owner);
}
