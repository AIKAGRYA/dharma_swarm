import {
  HELM_ON_CALL_SCHEMA,
  HELM_ROUTE_VERIFICATION_SCHEMA,
  HELM_SEAT_COUNT,
  HELM_SEAT_ORDER,
  type HelmAggregateState,
  type HelmOnCallProjection,
  type HelmRouteEvidenceIdentity,
  type HelmRouteVerdict,
  type HelmRouteVerification,
  type OrderedHelmRouteVerifications,
} from "../onCallTruth";

type UnknownObject = {[key: string]: unknown};

const PROJECTION_KEYS = [
  "schema_version",
  "state",
  "on_call_count",
  "total",
  "seats",
  "evaluated_at",
  "runtime_epoch",
] as const;

const VERIFICATION_KEYS = [
  "schema_version",
  "seat_id",
  "display_label",
  "logical_lineage",
  "verdict",
  "reason",
  "evaluated_at",
  "runtime_epoch",
  "evidence",
] as const;

const EVIDENCE_KEYS = [
  "seat_id",
  "logical_lineage",
  "requested_provider",
  "requested_model",
  "served_provider",
  "served_model",
  "observed_at",
  "expires_at",
  "age_seconds",
  "verifier_id",
  "verifier_version",
  "receipt_ref",
  "receipt_sha256",
  "runtime_epoch",
] as const;

const EVENT_KEYS = ["type", "request_id", "projection"] as const;
const ROUTE_VERDICTS = new Set<HelmRouteVerdict>(["ON_CALL", "UNKNOWN", "REJECTED", "CLOCK_SKEW"]);
const AGGREGATE_STATES = new Set<HelmAggregateState>(["ON_CALL", "LIVE_DEGRADED", "CLOCK_SKEW", "UNKNOWN"]);
const SHA256_HEX = /^[0-9a-f]{64}$/;

function asObject(value: unknown): UnknownObject | undefined {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? value as UnknownObject
    : undefined;
}

function hasExactKeys(value: UnknownObject, expected: readonly string[]): boolean {
  const actual = Object.keys(value);
  return actual.length === expected.length && expected.every((key) => Object.hasOwn(value, key));
}

function nonEmptyString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim().length > 0 ? value : undefined;
}

function nullableString(value: unknown): string | null | undefined {
  return value === null ? null : typeof value === "string" ? value : undefined;
}

function decodeEvidence(value: unknown): HelmRouteEvidenceIdentity | null | undefined {
  if (value === null) {
    return null;
  }
  const evidence = asObject(value);
  if (!evidence || !hasExactKeys(evidence, EVIDENCE_KEYS)) {
    return undefined;
  }
  const age = evidence.age_seconds;
  if (age !== null && (!Number.isInteger(age) || Number(age) < 0)) {
    return undefined;
  }
  const strings = EVIDENCE_KEYS.filter((key) => key !== "age_seconds");
  if (strings.some((key) => nullableString(evidence[key]) === undefined)) {
    return undefined;
  }
  return {
    seat_id: nullableString(evidence.seat_id)!,
    logical_lineage: nullableString(evidence.logical_lineage)!,
    requested_provider: nullableString(evidence.requested_provider)!,
    requested_model: nullableString(evidence.requested_model)!,
    served_provider: nullableString(evidence.served_provider)!,
    served_model: nullableString(evidence.served_model)!,
    observed_at: nullableString(evidence.observed_at)!,
    expires_at: nullableString(evidence.expires_at)!,
    age_seconds: age === null ? null : Number(age),
    verifier_id: nullableString(evidence.verifier_id)!,
    verifier_version: nullableString(evidence.verifier_version)!,
    receipt_ref: nullableString(evidence.receipt_ref)!,
    receipt_sha256: nullableString(evidence.receipt_sha256)!,
    runtime_epoch: nullableString(evidence.runtime_epoch)!,
  };
}

function decodeVerification(
  value: unknown,
  position: number,
  runtimeEpoch: string,
  evaluatedAt: string,
): HelmRouteVerification | undefined {
  const verification = asObject(value);
  const expectedSeat = HELM_SEAT_ORDER[position];
  if (!verification || !expectedSeat || !hasExactKeys(verification, VERIFICATION_KEYS)) {
    return undefined;
  }
  const verdict = verification.verdict;
  const evidence = decodeEvidence(verification.evidence);
  if (
    verification.schema_version !== HELM_ROUTE_VERIFICATION_SCHEMA
    || verification.seat_id !== expectedSeat.seatId
    || verification.display_label !== expectedSeat.displayLabel
    || verification.logical_lineage !== expectedSeat.logicalLineage
    || typeof verdict !== "string"
    || !ROUTE_VERDICTS.has(verdict as HelmRouteVerdict)
    || !nonEmptyString(verification.reason)
    || verification.evaluated_at !== evaluatedAt
    || verification.runtime_epoch !== runtimeEpoch
    || evidence === undefined
  ) {
    return undefined;
  }
  if (evidence !== null && (
    evidence.seat_id !== expectedSeat.seatId
    || evidence.logical_lineage !== expectedSeat.logicalLineage
    || evidence.runtime_epoch !== runtimeEpoch
  )) {
    return undefined;
  }
  if (verdict === "ON_CALL" && (
    verification.reason !== "verified"
    || evidence === null
    || !nonEmptyString(evidence.requested_provider)
    || !nonEmptyString(evidence.requested_model)
    || !nonEmptyString(evidence.served_provider)
    || !nonEmptyString(evidence.served_model)
    || !nonEmptyString(evidence.observed_at)
    || !nonEmptyString(evidence.expires_at)
    || evidence.age_seconds === null
    || evidence.verifier_id !== "dharma.route_verifier"
    || evidence.verifier_version !== "1.0.0"
    || !nonEmptyString(evidence.receipt_ref)
    || typeof evidence.receipt_sha256 !== "string"
    || !SHA256_HEX.test(evidence.receipt_sha256)
  )) {
    return undefined;
  }
  return {
    schema_version: HELM_ROUTE_VERIFICATION_SCHEMA,
    seat_id: expectedSeat.seatId,
    display_label: expectedSeat.displayLabel,
    logical_lineage: expectedSeat.logicalLineage,
    verdict: verdict as HelmRouteVerdict,
    reason: verification.reason as string,
    evaluated_at: verification.evaluated_at as string,
    runtime_epoch: runtimeEpoch,
    evidence,
  };
}

function aggregateIsConsistent(
  state: HelmAggregateState,
  count: number | null,
  seats: OrderedHelmRouteVerifications,
): boolean {
  const serializedOnCallCount = seats.filter((seat) => seat.verdict === "ON_CALL").length;
  const hasClockSkew = seats.some((seat) => seat.verdict === "CLOCK_SKEW");
  if (state === "UNKNOWN") {
    return count === null && seats.every((seat) => seat.verdict === "UNKNOWN");
  }
  if (!Number.isInteger(count) || count === null || count < 0 || count > HELM_SEAT_COUNT) {
    return false;
  }
  if (count !== serializedOnCallCount) {
    return false;
  }
  if (state === "ON_CALL") {
    return count === HELM_SEAT_COUNT && !hasClockSkew;
  }
  if (state === "CLOCK_SKEW") {
    return count < HELM_SEAT_COUNT && hasClockSkew;
  }
  return count < HELM_SEAT_COUNT && !hasClockSkew;
}

export function decodeHelmOnCallProjection(value: unknown): HelmOnCallProjection | undefined {
  const projection = asObject(value);
  if (!projection || !hasExactKeys(projection, PROJECTION_KEYS)) {
    return undefined;
  }
  const state = projection.state;
  const runtimeEpoch = nonEmptyString(projection.runtime_epoch);
  const evaluatedAt = nonEmptyString(projection.evaluated_at);
  if (
    projection.schema_version !== HELM_ON_CALL_SCHEMA
    || typeof state !== "string"
    || !AGGREGATE_STATES.has(state as HelmAggregateState)
    || projection.total !== HELM_SEAT_COUNT
    || !Array.isArray(projection.seats)
    || projection.seats.length !== HELM_SEAT_COUNT
    || !runtimeEpoch
    || !evaluatedAt
  ) {
    return undefined;
  }
  const seats = projection.seats.map((seat, position) => (
    decodeVerification(seat, position, runtimeEpoch, evaluatedAt)
  ));
  const [seat0, seat1, seat2, seat3, seat4, seat5, seat6] = seats;
  if (!seat0 || !seat1 || !seat2 || !seat3 || !seat4 || !seat5 || !seat6) {
    return undefined;
  }
  const orderedSeats: OrderedHelmRouteVerifications = [seat0, seat1, seat2, seat3, seat4, seat5, seat6];
  const count = projection.on_call_count;
  if (!aggregateIsConsistent(state as HelmAggregateState, typeof count === "number" ? count : count === null ? null : Number.NaN, orderedSeats)) {
    return undefined;
  }
  return {
    schema_version: HELM_ON_CALL_SCHEMA,
    state: state as HelmAggregateState,
    on_call_count: count as number | null,
    total: HELM_SEAT_COUNT,
    seats: orderedSeats,
    evaluated_at: evaluatedAt,
    runtime_epoch: runtimeEpoch,
  };
}

export function helmOnCallProjectionFromEvent(value: unknown): HelmOnCallProjection | undefined {
  const event = asObject(value);
  if (
    !event
    || !hasExactKeys(event, EVENT_KEYS)
    || event.type !== "helm.on_call_projection"
    || !nonEmptyString(event.request_id)
  ) {
    return undefined;
  }
  return decodeHelmOnCallProjection(event.projection);
}
