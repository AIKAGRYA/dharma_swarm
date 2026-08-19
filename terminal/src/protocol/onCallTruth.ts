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
const RFC3339_TIMESTAMP = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?(Z|[+-]\d{2}:\d{2})$/;
const NANOS_PER_SECOND = 1_000_000_000n;
const MAX_ROUTE_VERIFICATION_TTL_NANOS = 24n * 60n * 60n * NANOS_PER_SECOND;
const AUTHORITATIVE_UNKNOWN_REASONS = new Set([
  "awaiting_authoritative_projection",
  "malformed_evidence_batch",
  "runtime_epoch_mismatch",
]);
const REJECTED_REASONS = new Set([
  "seat_mismatch",
  "lineage_mismatch",
  "provider_completion_failed",
  "synthetic_evidence",
  "requested_identity_missing",
  "served_identity_missing",
  "served_identity_mismatch",
  "timestamp_not_timezone_aware",
  "expiry_not_after_observation",
  "ttl_exceeds_24_hours",
  "evidence_expired",
  "verifier_identity_rejected",
  "verifier_decision_rejected",
  "receipt_reference_missing",
  "receipt_hash_invalid",
  "receipt_duplicated",
  "receipt_replayed",
]);

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

function isLeapYear(year: number): boolean {
  return year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
}

function daysInMonth(year: number, month: number): number {
  if (month === 2) {
    return isLeapYear(year) ? 29 : 28;
  }
  return [4, 6, 9, 11].includes(month) ? 30 : 31;
}

/**
 * Parse only the timestamp grammar emitted by the Python projection codec.
 *
 * The result is used solely to reject an internally contradictory wire value.
 * It is never compared with the terminal clock, so TypeScript cannot refresh,
 * extend, clamp, or otherwise manufacture Python's positive truth.
 */
function rfc3339Nanoseconds(value: unknown): bigint | undefined {
  if (typeof value !== "string") {
    return undefined;
  }
  const match = RFC3339_TIMESTAMP.exec(value);
  if (!match) {
    return undefined;
  }
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const hour = Number(match[4]);
  const minute = Number(match[5]);
  const second = Number(match[6]);
  const fraction = match[7] ?? "";
  const zone = match[8] ?? "";
  if (
    year < 1
    || month < 1
    || month > 12
    || day < 1
    || day > daysInMonth(year, month)
    || hour > 23
    || minute > 59
    || second > 59
  ) {
    return undefined;
  }
  if (zone !== "Z") {
    const offsetHour = Number(zone.slice(1, 3));
    const offsetMinute = Number(zone.slice(4, 6));
    if (offsetHour > 23 || offsetMinute > 59) {
      return undefined;
    }
  }
  const wholeSecond = `${match[1]}-${match[2]}-${match[3]}T${match[4]}:${match[5]}:${match[6]}${zone}`;
  const epochMilliseconds = Date.parse(wholeSecond);
  if (!Number.isFinite(epochMilliseconds)) {
    return undefined;
  }
  const fractionNanoseconds = fraction ? BigInt(fraction.padEnd(9, "0")) : 0n;
  return BigInt(epochMilliseconds) * 1_000_000n + fractionNanoseconds;
}

function servedIdentityIsAdmissible(
  seat: (typeof HELM_SEAT_ORDER)[number],
  evidence: HelmRouteEvidenceIdentity,
): boolean {
  return seat.admissibleServedIdentities.some(([provider, model]) => (
    evidence.served_provider === provider && evidence.served_model === model
  ));
}

function positiveEvidenceIsInternallyConsistent(
  seat: (typeof HELM_SEAT_ORDER)[number],
  evidence: HelmRouteEvidenceIdentity,
  evaluatedAtNanoseconds: bigint,
): boolean {
  const observedAtNanoseconds = rfc3339Nanoseconds(evidence.observed_at);
  const expiresAtNanoseconds = rfc3339Nanoseconds(evidence.expires_at);
  if (
    observedAtNanoseconds === undefined
    || expiresAtNanoseconds === undefined
    || !servedIdentityIsAdmissible(seat, evidence)
    || observedAtNanoseconds > evaluatedAtNanoseconds
    || evaluatedAtNanoseconds >= expiresAtNanoseconds
    || expiresAtNanoseconds <= observedAtNanoseconds
    || expiresAtNanoseconds - observedAtNanoseconds > MAX_ROUTE_VERIFICATION_TTL_NANOS
  ) {
    return false;
  }
  const serializedAge = evidence.age_seconds;
  return serializedAge !== null
    && BigInt(serializedAge) === (evaluatedAtNanoseconds - observedAtNanoseconds) / NANOS_PER_SECOND;
}

function clockSkewEvidenceIsInternallyConsistent(
  seat: (typeof HELM_SEAT_ORDER)[number],
  evidence: HelmRouteEvidenceIdentity,
  evaluatedAtNanoseconds: bigint,
): boolean {
  const observedAtNanoseconds = rfc3339Nanoseconds(evidence.observed_at);
  return Boolean(nonEmptyString(evidence.requested_provider))
    && Boolean(nonEmptyString(evidence.requested_model))
    && servedIdentityIsAdmissible(seat, evidence)
    && observedAtNanoseconds !== undefined
    && observedAtNanoseconds > evaluatedAtNanoseconds
    && evidence.age_seconds === null;
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
  if (age !== null && (!Number.isSafeInteger(age) || Number(age) < 0)) {
    return undefined;
  }
  const strings = EVIDENCE_KEYS.filter((key) => key !== "age_seconds");
  if (strings.some((key) => nullableString(evidence[key]) === undefined)) {
    return undefined;
  }
  for (const timestamp of [evidence.observed_at, evidence.expires_at]) {
    if (timestamp !== null && rfc3339Nanoseconds(timestamp) === undefined) {
      return undefined;
    }
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
  evaluatedAtNanoseconds: bigint,
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
  if (evidence !== null && evidence.runtime_epoch !== runtimeEpoch) {
    return undefined;
  }
  const evidenceSeatMatches = evidence !== null && evidence.seat_id === expectedSeat.seatId;
  const evidenceLineageMatches = evidence !== null && evidence.logical_lineage === expectedSeat.logicalLineage;
  if (verdict === "UNKNOWN" && evidence !== null) {
    return undefined;
  }
  if ((verdict === "REJECTED" || verdict === "CLOCK_SKEW" || verdict === "ON_CALL") && evidence === null) {
    return undefined;
  }
  if (verdict === "REJECTED") {
    if (!REJECTED_REASONS.has(String(verification.reason))) {
      return undefined;
    }
    if (verification.reason === "seat_mismatch" && evidenceSeatMatches) {
      return undefined;
    }
    if (
      verification.reason === "lineage_mismatch"
      && (!evidenceSeatMatches || evidenceLineageMatches)
    ) {
      return undefined;
    }
    if (
      verification.reason !== "seat_mismatch"
      && verification.reason !== "lineage_mismatch"
      && (!evidenceSeatMatches || !evidenceLineageMatches)
    ) {
      return undefined;
    }
  } else if (evidence !== null && (!evidenceSeatMatches || !evidenceLineageMatches)) {
    return undefined;
  }
  if (verdict === "CLOCK_SKEW" && (
    verification.reason !== "timestamp_in_future"
    || evidence === null
    || !clockSkewEvidenceIsInternallyConsistent(expectedSeat, evidence, evaluatedAtNanoseconds)
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
    || !positiveEvidenceIsInternallyConsistent(expectedSeat, evidence, evaluatedAtNanoseconds)
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

function seatReasonsAreConsistent(
  state: HelmAggregateState,
  seats: OrderedHelmRouteVerifications,
): boolean {
  if (state === "UNKNOWN") {
    const reasons = new Set(seats.map((seat) => seat.reason));
    return reasons.size === 1 && AUTHORITATIVE_UNKNOWN_REASONS.has(seats[0].reason);
  }
  return seats.every((seat) => seat.verdict !== "UNKNOWN" || seat.reason === "missing_evidence");
}

function positiveReceiptsAreUnique(seats: OrderedHelmRouteVerifications): boolean {
  const evidenceRows = seats
    .map((seat) => seat.evidence)
    .filter((evidence): evidence is HelmRouteEvidenceIdentity => evidence !== null);
  for (const seat of seats) {
    if (seat.verdict !== "ON_CALL" || seat.evidence === null) {
      continue;
    }
    const matchingReferences = evidenceRows.filter((evidence) => evidence.receipt_ref === seat.evidence?.receipt_ref);
    const matchingHashes = evidenceRows.filter((evidence) => evidence.receipt_sha256 === seat.evidence?.receipt_sha256);
    if (matchingReferences.length !== 1 || matchingHashes.length !== 1) {
      return false;
    }
  }
  return true;
}

export function decodeHelmOnCallProjection(value: unknown): HelmOnCallProjection | undefined {
  const projection = asObject(value);
  if (!projection || !hasExactKeys(projection, PROJECTION_KEYS)) {
    return undefined;
  }
  const state = projection.state;
  const runtimeEpoch = nonEmptyString(projection.runtime_epoch);
  const evaluatedAt = nonEmptyString(projection.evaluated_at);
  const evaluatedAtNanoseconds = rfc3339Nanoseconds(evaluatedAt);
  if (
    projection.schema_version !== HELM_ON_CALL_SCHEMA
    || typeof state !== "string"
    || !AGGREGATE_STATES.has(state as HelmAggregateState)
    || projection.total !== HELM_SEAT_COUNT
    || !Array.isArray(projection.seats)
    || projection.seats.length !== HELM_SEAT_COUNT
    || !runtimeEpoch
    || !evaluatedAt
    || evaluatedAtNanoseconds === undefined
  ) {
    return undefined;
  }
  const seats = projection.seats.map((seat, position) => (
    decodeVerification(seat, position, runtimeEpoch, evaluatedAt, evaluatedAtNanoseconds)
  ));
  const [seat0, seat1, seat2, seat3, seat4, seat5, seat6] = seats;
  if (!seat0 || !seat1 || !seat2 || !seat3 || !seat4 || !seat5 || !seat6) {
    return undefined;
  }
  const orderedSeats: OrderedHelmRouteVerifications = [seat0, seat1, seat2, seat3, seat4, seat5, seat6];
  const count = projection.on_call_count;
  if (
    !aggregateIsConsistent(
      state as HelmAggregateState,
      typeof count === "number" ? count : count === null ? null : Number.NaN,
      orderedSeats,
    )
    || !seatReasonsAreConsistent(state as HelmAggregateState, orderedSeats)
    || !positiveReceiptsAreUnique(orderedSeats)
  ) {
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
    || typeof event.request_id !== "string"
  ) {
    return undefined;
  }
  const projection = decodeHelmOnCallProjection(event.projection);
  if (!projection) {
    return undefined;
  }
  // The bridge emits one unsolicited, empty-id baseline at process start. It
  // may bind the new runtime epoch only while remaining UNKNOWN; positive or
  // degraded truth must always be correlated to a real terminal request.
  if (event.request_id.length === 0) {
    return projection.state === "UNKNOWN" ? projection : undefined;
  }
  return nonEmptyString(event.request_id) ? projection : undefined;
}
