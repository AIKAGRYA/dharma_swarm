export const SADHANA_CONTROL_CSRF = "sadhana-10-20260823";
export const SADHANA_CONTROL_ROUTE = "/dharma-internal/operator-control";
export const OPERATOR_CONTROL_EVIDENCE_SCHEMA =
  "dharma.sadhana.operator_control_evidence.v1";

export type OperatorControlAction = "pause" | "resume" | "emergency_stop";
export type ClaimStage =
  | "none"
  | "authority_applied"
  | "effect_observed"
  | "effect_violated";
export type ControlState = "RUNNING" | "PAUSED" | "STOPPED_TERMINAL";
export type EffectState = "unobserved" | "observed" | "violated";

export interface OperatorControlRequest {
  action: OperatorControlAction;
  request_id: string;
  idempotency_key: string;
  issued_at: string;
  expires_at: string;
  reason: string;
}

export interface RequestAccepted {
  request_id: string;
  idempotency_key: string;
  action: OperatorControlAction;
  source_envelope_sha256: string;
  request_accepted: true;
  applied: false;
  decision_applied: false;
  effect_executed: false;
}

export interface OperatorControlEvidence {
  schema_version: typeof OPERATOR_CONTROL_EVIDENCE_SCHEMA;
  claim_stage: ClaimStage;
  control_state: ControlState;
  campaign_generation: number;
  transition_sequence: number;
  request_id: string;
  idempotency_key: string;
  action: OperatorControlAction | "";
  source_envelope_sha256: string;
  authority_receipt_ref: string;
  authority_receipt_sha256: string;
  authority_applied_at: string | null;
  effect_state: EffectState;
  effect_receipt_ref: string;
  effect_receipt_sha256: string;
  effect_observed_at: string | null;
}

export interface PendingControl {
  accepted: RequestAccepted;
  baseline_campaign_generation: number | null;
  baseline_transition_sequence: number | null;
}

export type ControlProgress =
  | "request_accepted_awaiting_authority"
  | "authority_applied_effect_unobserved"
  | "effect_observed"
  | "effect_violated"
  | "evidence_unknown";

export interface DurableControlSummary {
  valid: boolean;
  controlState: ControlState | "UNKNOWN";
  claimStage: ClaimStage | "unknown";
  generationSequence: string;
  lastAction: OperatorControlAction | "none" | "unknown";
  authorityEvidence: string;
  effectEvidence: string;
}

export class OperatorControlDeliveryUnknown extends Error {
  readonly code = "operator_control_delivery_unknown";

  constructor() {
    super(
      "delivery outcome unknown—reconnect and inspect durable control evidence",
    );
    this.name = "OperatorControlDeliveryUnknown";
  }
}

const ACTIONS = new Set<OperatorControlAction>([
  "pause",
  "resume",
  "emergency_stop",
]);
const CLAIM_STAGES = new Set<ClaimStage>([
  "none",
  "authority_applied",
  "effect_observed",
  "effect_violated",
]);
const CONTROL_STATES = new Set<ControlState>([
  "RUNNING",
  "PAUSED",
  "STOPPED_TERMINAL",
]);
const EFFECT_STATES = new Set<EffectState>([
  "unobserved",
  "observed",
  "violated",
]);
const IDENTIFIER = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/;
const SHA256_REF = /^sha256:[0-9a-f]{64}$/;
const RFC3339_UTC =
  /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?Z$/;
const ACCEPTED_FIELDS = [
  "action",
  "applied",
  "decision_applied",
  "effect_executed",
  "idempotency_key",
  "request_accepted",
  "request_id",
  "source_envelope_sha256",
] as const;
const EVIDENCE_FIELDS = [
  "action",
  "authority_applied_at",
  "authority_receipt_ref",
  "authority_receipt_sha256",
  "campaign_generation",
  "claim_stage",
  "control_state",
  "effect_observed_at",
  "effect_receipt_ref",
  "effect_receipt_sha256",
  "effect_state",
  "idempotency_key",
  "request_id",
  "schema_version",
  "source_envelope_sha256",
  "transition_sequence",
] as const;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function hasExactFields(
  value: Record<string, unknown>,
  expected: readonly string[],
): boolean {
  const actual = Object.keys(value).sort();
  return (
    actual.length === expected.length &&
    actual.every((field, index) => field === [...expected].sort()[index])
  );
}

function isIdentifier(value: unknown, allowEmpty = false): value is string {
  return typeof value === "string" && (allowEmpty && value === "" ? true : IDENTIFIER.test(value));
}

function isSha256(value: unknown, allowEmpty = false): value is string {
  return typeof value === "string" && (allowEmpty && value === "" ? true : SHA256_REF.test(value));
}

function isBoundedRef(value: unknown): value is string {
  return (
    typeof value === "string" &&
    value.length <= 512 &&
    value.trim() === value &&
    value.normalize("NFC") === value &&
    !/\p{C}/u.test(value)
  );
}

export function isOperatorControlReason(value: unknown): value is string {
  return (
    typeof value === "string" &&
    value.length > 0 &&
    value.length <= 512 &&
    value.trim() === value &&
    value.normalize("NFC") === value &&
    !/\p{C}/u.test(value)
  );
}

function isTimestamp(value: unknown, allowNull = false): value is string | null {
  if (allowNull && value === null) return true;
  if (typeof value !== "string") return false;
  const match = RFC3339_UTC.exec(value);
  if (!match) return false;
  const [year, month, day, hour, minute, second] = match
    .slice(1, 7)
    .map(Number);
  if (year < 1) return false;
  const millisecond = Number((match[7] ?? "").padEnd(3, "0").slice(0, 3));
  const parsed = new Date(0);
  parsed.setUTCFullYear(year, month - 1, day);
  parsed.setUTCHours(hour, minute, second, millisecond);
  return (
    parsed.getUTCFullYear() === year &&
    parsed.getUTCMonth() === month - 1 &&
    parsed.getUTCDate() === day &&
    parsed.getUTCHours() === hour &&
    parsed.getUTCMinutes() === minute &&
    parsed.getUTCSeconds() === second
  );
}

export function buildOperatorControlRequest(
  action: OperatorControlAction,
  reason: string,
  options: {
    now?: Date;
    requestId?: string;
    idempotencyKey?: string;
  } = {},
): OperatorControlRequest {
  if (!ACTIONS.has(action)) throw new Error("unsupported operator control action");
  if (!isOperatorControlReason(reason)) {
    throw new Error("reason must be 1-512 canonical characters");
  }
  const now = options.now ?? new Date();
  if (!Number.isFinite(now.getTime())) throw new Error("request time is invalid");
  const requestId = options.requestId ?? crypto.randomUUID();
  const idempotencyKey = options.idempotencyKey ?? crypto.randomUUID();
  if (!isIdentifier(requestId) || !isIdentifier(idempotencyKey)) {
    throw new Error("request identifiers are invalid");
  }
  return {
    action,
    request_id: requestId,
    idempotency_key: idempotencyKey,
    issued_at: now.toISOString(),
    expires_at: new Date(now.getTime() + 90_000).toISOString(),
    reason,
  };
}

export function parseRequestAccepted(value: unknown): RequestAccepted | null {
  if (!isRecord(value) || !ACCEPTED_FIELDS.every((field) => field in value)) return null;
  if (
    !ACTIONS.has(value.action as OperatorControlAction) ||
    !isIdentifier(value.request_id) ||
    !isIdentifier(value.idempotency_key) ||
    !isSha256(value.source_envelope_sha256) ||
    value.request_accepted !== true ||
    value.applied !== false ||
    value.decision_applied !== false ||
    value.effect_executed !== false
  ) {
    return null;
  }
  return {
    request_id: value.request_id,
    idempotency_key: value.idempotency_key,
    action: value.action as OperatorControlAction,
    source_envelope_sha256: value.source_envelope_sha256,
    request_accepted: true,
    applied: false,
    decision_applied: false,
    effect_executed: false,
  };
}

export function parseOperatorControlEvidence(
  value: unknown,
): OperatorControlEvidence | null {
  if (!isRecord(value) || !hasExactFields(value, EVIDENCE_FIELDS)) return null;
  if (
    value.schema_version !== OPERATOR_CONTROL_EVIDENCE_SCHEMA ||
    !CLAIM_STAGES.has(value.claim_stage as ClaimStage) ||
    !CONTROL_STATES.has(value.control_state as ControlState) ||
    !Number.isSafeInteger(value.campaign_generation) ||
    (value.campaign_generation as number) < 1 ||
    !Number.isSafeInteger(value.transition_sequence) ||
    (value.transition_sequence as number) < 0 ||
    !isIdentifier(value.request_id, true) ||
    !isIdentifier(value.idempotency_key, true) ||
    !(value.action === "" || ACTIONS.has(value.action as OperatorControlAction)) ||
    !isSha256(value.source_envelope_sha256, true) ||
    !isBoundedRef(value.authority_receipt_ref) ||
    !isSha256(value.authority_receipt_sha256, true) ||
    !isTimestamp(value.authority_applied_at, true) ||
    !EFFECT_STATES.has(value.effect_state as EffectState) ||
    !isBoundedRef(value.effect_receipt_ref) ||
    !isSha256(value.effect_receipt_sha256, true) ||
    !isTimestamp(value.effect_observed_at, true)
  ) {
    return null;
  }
  const evidence = value as unknown as OperatorControlEvidence;
  const authorityEmpty =
    evidence.request_id === "" &&
    evidence.idempotency_key === "" &&
    evidence.action === "" &&
    evidence.source_envelope_sha256 === "" &&
    evidence.authority_receipt_ref === "" &&
    evidence.authority_receipt_sha256 === "" &&
    evidence.authority_applied_at === null;
  const authorityComplete =
    evidence.request_id !== "" &&
    evidence.idempotency_key !== "" &&
    evidence.action !== "" &&
    evidence.source_envelope_sha256 !== "" &&
    evidence.authority_receipt_ref !== "" &&
    evidence.authority_receipt_sha256 !== "" &&
    evidence.authority_applied_at !== null;
  if (evidence.claim_stage === "none" ? !authorityEmpty : !authorityComplete) return null;
  const effectClaimed =
    evidence.claim_stage === "effect_observed" ||
    evidence.claim_stage === "effect_violated";
  const effectEmpty =
    evidence.effect_receipt_ref === "" &&
    evidence.effect_receipt_sha256 === "" &&
    evidence.effect_observed_at === null;
  const effectComplete =
    evidence.effect_receipt_ref !== "" &&
    evidence.effect_receipt_sha256 !== "" &&
    evidence.effect_observed_at !== null;
  if (effectClaimed ? !effectComplete : !effectEmpty) return null;
  if (
    (evidence.claim_stage === "none" && evidence.transition_sequence !== 0) ||
    (evidence.claim_stage === "none" && evidence.control_state !== "RUNNING") ||
    (evidence.claim_stage !== "none" && evidence.transition_sequence <= 0) ||
    (evidence.claim_stage === "none" && evidence.effect_state !== "unobserved") ||
    (evidence.claim_stage === "authority_applied" &&
      evidence.effect_state !== "unobserved") ||
    (evidence.claim_stage === "effect_observed" &&
      evidence.effect_state !== "observed") ||
    (evidence.claim_stage === "effect_violated" && evidence.effect_state !== "violated")
  ) {
    return null;
  }
  if (
    evidence.action &&
    ({
      pause: "PAUSED",
      resume: "RUNNING",
      emergency_stop: "STOPPED_TERMINAL",
    } satisfies Record<OperatorControlAction, ControlState>)[evidence.action] !==
      evidence.control_state
  ) {
    return null;
  }
  if (
    effectComplete &&
    evidence.authority_applied_at !== null &&
    evidence.effect_observed_at !== null &&
    Date.parse(evidence.authority_applied_at) > Date.parse(evidence.effect_observed_at)
  ) {
    return null;
  }
  return evidence;
}

export function evidenceFromSnapshot(snapshot: unknown): OperatorControlEvidence | null {
  if (!isRecord(snapshot)) return null;
  return parseOperatorControlEvidence(snapshot.operator_control_evidence);
}

function shortRef(value: string): string {
  return value.length > 30 ? `${value.slice(0, 14)}…${value.slice(-10)}` : value;
}

export function describeDurableControlEvidence(
  evidence: OperatorControlEvidence | null,
): DurableControlSummary {
  if (!evidence) {
    return {
      valid: false,
      controlState: "UNKNOWN",
      claimStage: "unknown",
      generationSequence: "unknown",
      lastAction: "unknown",
      authorityEvidence: "Not available",
      effectEvidence: "Not available",
    };
  }
  const authorityEvidence =
    evidence.authority_applied_at === null
      ? "No authority transition projected"
      : `${evidence.authority_applied_at} · ${shortRef(evidence.authority_receipt_ref)}`;
  const effectEvidence =
    evidence.effect_observed_at === null
      ? "Not independently observed"
      : `${evidence.effect_observed_at} · ${shortRef(evidence.effect_receipt_ref)}`;
  return {
    valid: true,
    controlState: evidence.control_state,
    claimStage: evidence.claim_stage,
    generationSequence: `${evidence.campaign_generation}/${evidence.transition_sequence}`,
    lastAction: evidence.action || "none",
    authorityEvidence,
    effectEvidence,
  };
}

export function classifyControlProgress(
  pending: PendingControl,
  evidence: OperatorControlEvidence | null,
): ControlProgress {
  if (!evidence) return "request_accepted_awaiting_authority";
  const accepted = pending.accepted;
  if (
    evidence.request_id !== accepted.request_id ||
    evidence.idempotency_key !== accepted.idempotency_key ||
    evidence.action !== accepted.action ||
    evidence.source_envelope_sha256 !== accepted.source_envelope_sha256
  ) {
    return "request_accepted_awaiting_authority";
  }
  if (
    pending.baseline_campaign_generation !== null &&
    evidence.campaign_generation !== pending.baseline_campaign_generation
  ) {
    return "evidence_unknown";
  }
  if (
    pending.baseline_transition_sequence !== null &&
    evidence.transition_sequence <= pending.baseline_transition_sequence
  ) {
    return "evidence_unknown";
  }
  if (evidence.claim_stage === "effect_observed") return "effect_observed";
  if (evidence.claim_stage === "effect_violated") return "effect_violated";
  if (evidence.claim_stage === "authority_applied") {
    return "authority_applied_effect_unobserved";
  }
  return "evidence_unknown";
}

export async function submitOperatorControl(
  request: OperatorControlRequest,
  fetchImpl: typeof fetch = fetch,
): Promise<RequestAccepted> {
  let response: Response;
  try {
    response = await fetchImpl(SADHANA_CONTROL_ROUTE, {
      method: "POST",
      cache: "no-store",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-Sadhana-CSRF": SADHANA_CONTROL_CSRF,
      },
      body: JSON.stringify(request),
    });
  } catch {
    if (request.action === "emergency_stop") {
      throw new OperatorControlDeliveryUnknown();
    }
    throw new Error("operator_control_transport_failed");
  }
  const value: unknown = await response.json().catch(() => null);
  if (response.status !== 202) {
    throw new Error(
      isRecord(value) && typeof value.error_code === "string"
        ? value.error_code
        : "operator_control_rejected",
    );
  }
  const accepted = parseRequestAccepted(value);
  if (!accepted) {
    if (request.action === "emergency_stop") {
      throw new OperatorControlDeliveryUnknown();
    }
    throw new Error("operator_control_response_invalid");
  }
  if (
    accepted.request_id !== request.request_id ||
    accepted.idempotency_key !== request.idempotency_key ||
    accepted.action !== request.action
  ) {
    if (request.action === "emergency_stop") {
      throw new OperatorControlDeliveryUnknown();
    }
    throw new Error("operator_control_response_mismatch");
  }
  return accepted;
}
