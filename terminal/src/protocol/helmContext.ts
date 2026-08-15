import {createHash} from "node:crypto";
import {
  HELM_CONTEXT_PROJECTION_NAMES,
  HELM_CONTEXT_SCHEMA,
  helmProjectionDataIsValid,
  type AuthorityModality,
  type AuthorityStamp,
  type HelmContextEnvelope,
  type HelmContextProjection,
  type HelmContextProjectionName,
  type HelmContextProjections,
  type HelmContextResultEvent,
  type HelmProjectionStatus,
} from "../helmContext/types";
type UnknownObject = {[key: string]: unknown};
const ENVELOPE_KEYS = [
  "schema_version", "generated_at", "expires_at", "runtime_epoch", "synthetic",
  "provider_state_promotion", "projections", "context_digest",
] as const;
const PROJECTION_KEYS = ["region", "status", "authority", "data", "unavailable_reason"] as const;
const AUTHORITY_KEYS = [
  "modality", "owner", "source", "observed_at", "expires_at", "runtime_epoch",
] as const;
const EVENT_KEYS = ["type", "request_id", "envelope"] as const;
const AUTHORITY_MODALITIES = new Set<AuthorityModality>([
  "observed", "configured", "unverified", "stale", "unknown", "held",
]);
const PROJECTION_STATUSES = new Set<HelmProjectionStatus>([
  ...AUTHORITY_MODALITIES,
  "unavailable",
]);
const OWNER_BY_REGION: Record<HelmContextProjectionName, string> = {workspace: "TerminalBridge", bridge_session: "TerminalBridge", ui: "NihongaShell", mission_control: "MissionControl", task_board: "TaskBoard", runtime_state: "RuntimeStateStore", session: "SessionStore", receipts: "RuntimeStateStore", swarm: "SwarmManager", a2a: "A2AContactRegistry", evolution: "EvolutionArchive", actions: "TerminalBridge"};
const SOURCE_BY_REGION: Record<HelmContextProjectionName, string> = {workspace: "TerminalBridge.workspace_inventory", bridge_session: "terminal_bridge.session_runtime", ui: "helm.context.request.ui", mission_control: "MissionControl.get_snapshot", task_board: "TaskBoard.list_tasks", runtime_state: "RuntimeStateStore.read_projection", session: "SessionStore.list_sessions", receipts: "RuntimeStateStore.read_recent_receipts", swarm: "SwarmManager.status", a2a: "A2AContactRegistry.list_all", evolution: "EvolutionArchive.list_entries", actions: "terminal_bridge.action_projection"};
const SHA256_DIGEST = /^sha256:[0-9a-f]{64}$/;
const RFC3339_TIMESTAMP = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?(Z|[+-]\d{2}:\d{2})$/;
const MAX_ENVELOPE_BYTES = 64 * 1024;
const MAX_STRING_CODE_POINTS = 4096;
const MAX_KEY_CODE_POINTS = 128;
const MAX_COLLECTION_ITEMS = 64;
const MAX_JSON_DEPTH = 8;
const MAX_JSON_NODES = 2048;
const MAX_REQUEST_ID_CODE_POINTS = 128;
const MAX_ENVELOPE_TTL_NANOSECONDS = 3_600_000_000_000n, MAX_ROUTE_TTL_NANOSECONDS = 86_400_000_000_000n;
const MIN_RFC3339_NANOSECONDS = -62_135_596_800_000_000_000n;
const MAX_RFC3339_NANOSECONDS = 253_402_300_799_999_999_000n;
const RESERVED_DATA_KEYS = new Set(["authority", "authority_stamp", "authority_modality", "modality", "provider_state_promotion", "state_promotion_allowed", "narration_verified"]);
const SECRET_DATA_KEYS = new Set(["access_key", "access_token", "api_key", "apikey", "authorization", "client_secret", "cookie", "credential", "openai_api_key", "password", "private_key", "provider_raw_metadata", "raw", "raw_metadata", "refresh_token", "response_headers", "secret", "secret_key", "session_cookie", "system_info", "token"]);
const SECRET_KEY_SUFFIXES = ["_access_key", "_api_key", "_cookie", "_credential", "_password", "_private_key", "_secret", "_token"] as const;
const SECRET_VALUE_PREFIXES = ["bearer ", "ghp_", "gho_", "github_pat_", "xai-", "xapp-", "xoxa-", "xoxc-", "xoxe-", "xoxr-", "xoxs-", "xoxb-", "xoxp-"] as const;
const SECRET_VALUE_PATTERN = /(?:\bbearer\s+[a-z0-9._~+/=-]{8,}|\b(?:gh[opusr]_|github_pat_|xox[a-z]-|xapp-)[a-z0-9_-]{8,}|\b(?:sk-or-v1-|xai-)[a-z0-9_-]{8,}|\bsk-(?:(?:proj|ant|live|svcacct)-[a-z0-9_-]{8,}|[a-z0-9]{20,})\b|\bAIza[a-z0-9_-]{8,}|\bAKIA[0-9A-Z]{16}\b|https?:\/\/[^\s/@]*@|-----BEGIN [A-Z ]*PRIVATE KEY-----)/i;
const CONTROL_OR_FORMAT = /[\p{Cc}\p{Cf}]/u;
const SAFE_REQUEST_ID = /^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$/;
function asObject(value: unknown): UnknownObject | undefined {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return undefined;
  const object = value as UnknownObject, prototype = Object.getPrototypeOf(object), descriptors = Object.getOwnPropertyDescriptors(object);
  return (prototype === Object.prototype || prototype === null) && Reflect.ownKeys(object).length === Object.keys(object).length
    && Object.values(descriptors).every((item) => Object.hasOwn(item, "value") && item.enumerable) ? object : undefined;
}
function denseJsonArray(value: unknown): value is unknown[] {
  return Array.isArray(value) && value.length <= MAX_COLLECTION_ITEMS && Object.getPrototypeOf(value) === Array.prototype
    && Reflect.ownKeys(value).length === value.length + 1 && Array.from({length: value.length}, (_, index) => Object.getOwnPropertyDescriptor(value, index)).every((item) => !!item && Object.hasOwn(item, "value") && item.enumerable);
}
function hasExactKeys(value: UnknownObject, expected: readonly string[]): boolean {
  const actual = Object.keys(value);
  return actual.length === expected.length && expected.every((key) => Object.hasOwn(value, key));
}
function deepFreeze<T>(value: T): T {
  if (typeof value === "object" && value !== null && !Object.isFrozen(value)) {
    Object.values(value).forEach((item) => deepFreeze(item));
    Object.freeze(value);
  }
  return value;
}
function codePointLength(value: string): number { return [...value].length; }
function hasOnlySafeUnicodeText(value: string): boolean {
  return !CONTROL_OR_FORMAT.test(value) && [...value].every((character) => {
    const point = character.codePointAt(0)!;
    return point < 0xD800 || point > 0xDFFF;
  });
}
function boundedNonEmptyString(value: unknown, maxLength = MAX_STRING_CODE_POINTS): string | undefined {
  return typeof value === "string"
    && value.length > 0
    && codePointLength(value) <= maxLength
    && hasOnlySafeUnicodeText(value)
    ? value
    : undefined;
}
function isLeapYear(year: number): boolean { return year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0); }
function daysInMonth(year: number, month: number): number {
  if (month === 2) return isLeapYear(year) ? 29 : 28;
  return [4, 6, 9, 11].includes(month) ? 30 : 31;
}
function rfc3339Nanoseconds(value: unknown): bigint | undefined {
  if (typeof value !== "string") return undefined;
  const match = RFC3339_TIMESTAMP.exec(value);
  if (!match) return undefined;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const hour = Number(match[4]);
  const minute = Number(match[5]);
  const second = Number(match[6]);
  const fraction = match[7] ?? "";
  const zone = match[8] ?? "";
  if (year < 1 || month < 1 || month > 12 || day < 1 || day > daysInMonth(year, month)
    || hour > 23 || minute > 59 || second > 59) return undefined;
  if (zone !== "Z") {
    const offsetHour = Number(zone.slice(1, 3));
    const offsetMinute = Number(zone.slice(4, 6));
    if (offsetHour > 23 || offsetMinute > 59) return undefined;
  }
  const wholeSecond = `${match[1]}-${match[2]}-${match[3]}T${match[4]}:${match[5]}:${match[6]}${zone}`;
  const epochMilliseconds = Date.parse(wholeSecond);
  if (!Number.isFinite(epochMilliseconds)) return undefined;
  const fractionNanoseconds = fraction ? BigInt(fraction.padEnd(9, "0")) : 0n;
  const instant = BigInt(epochMilliseconds) * 1_000_000n + fractionNanoseconds;
  return instant < MIN_RFC3339_NANOSECONDS || instant > MAX_RFC3339_NANOSECONDS ? undefined : instant;
}
function serializedSizeWithinLimit(value: unknown): boolean {
  try {
    const serialized = canonicalJson(value);
    return serialized !== undefined && new TextEncoder().encode(serialized).byteLength <= MAX_ENVELOPE_BYTES;
  } catch {
    return false;
  }
}
function stringLooksSecret(value: string): boolean {
  if (value === "[REDACTED]") return false;
  const normalized = value.trim().toLowerCase();
  return SECRET_VALUE_PATTERN.test(value)
    || SECRET_VALUE_PREFIXES.some((prefix) => normalized.startsWith(prefix))
    || (normalized.startsWith("eyj") && normalized.split(".").length === 3);
}
function keyLooksSecret(value: string): boolean {
  const normalized = value.toLowerCase().replaceAll("-", "_");
  return SECRET_DATA_KEYS.has(normalized)
    || SECRET_KEY_SUFFIXES.some((suffix) => normalized.endsWith(suffix))
    || normalized.includes("provider_raw");
}
function boundedJsonValue(value: unknown, depth: number, nodes: {count: number}): boolean {
  nodes.count += 1;
  if (nodes.count > MAX_JSON_NODES || depth > MAX_JSON_DEPTH) {
    return false;
  }
  if (value === null || typeof value === "boolean") {
    return true;
  }
  if (typeof value === "string") {
    return codePointLength(value) <= MAX_STRING_CODE_POINTS
      && hasOnlySafeUnicodeText(value)
      && !stringLooksSecret(value);
  }
  if (typeof value === "number") {
    return Number.isSafeInteger(value);
  }
  if (Array.isArray(value)) {
    return denseJsonArray(value)
      && value.every((item) => boundedJsonValue(item, depth + 1, nodes));
  }
  const object = asObject(value);
  if (!object) {
    return false;
  }
  const keys = Object.keys(object);
  if (keys.length > MAX_COLLECTION_ITEMS) {
    return false;
  }
  return keys.every((key) => (
    key.length > 0
    && codePointLength(key) <= MAX_KEY_CODE_POINTS
    && hasOnlySafeUnicodeText(key)
    && !RESERVED_DATA_KEYS.has(key.toLowerCase().replaceAll("-", "_"))
    && (
      keyLooksSecret(key)
        ? object[key] === "[REDACTED]"
        : boundedJsonValue(object[key], depth + 1, nodes)
    )
  ));
}
function compareUnicodeCodePoints(left: string, right: string): number {
  const leftPoints = [...left].map((character) => character.codePointAt(0)!);
  const rightPoints = [...right].map((character) => character.codePointAt(0)!);
  const sharedLength = Math.min(leftPoints.length, rightPoints.length);
  for (let index = 0; index < sharedLength; index += 1) {
    const difference = leftPoints[index]! - rightPoints[index]!;
    if (difference !== 0) {
      return difference;
    }
  }
  return leftPoints.length - rightPoints.length;
}
/** Match Python's sort_keys=True, separators=(",", ":"), ensure_ascii=False. */
function canonicalJson(value: unknown): string | undefined {
  if (value === null) return "null";
  if (value === true) return "true";
  if (value === false) return "false";
  if (typeof value === "string") {
    return JSON.stringify(value);
  }
  if (typeof value === "number") {
    return Number.isSafeInteger(value) ? String(value) : undefined;
  }
  if (Array.isArray(value)) {
    const items = denseJsonArray(value) ? value.map(canonicalJson) : [];
    return items.length !== value.length || items.some((item) => item === undefined) ? undefined : `[${items.join(",")}]`;
  }
  const object = asObject(value);
  if (!object) {
    return undefined;
  }
  const members: string[] = [];
  for (const key of Object.keys(object).sort(compareUnicodeCodePoints)) {
    const serializedValue = canonicalJson(object[key]);
    if (serializedValue === undefined) {
      return undefined;
    }
    members.push(`${JSON.stringify(key)}:${serializedValue}`);
  }
  return `{${members.join(",")}}`;
}
function digestMatchesEnvelope(envelope: UnknownObject): boolean {
  const unsigned: UnknownObject = {};
  for (const [key, value] of Object.entries(envelope)) {
    if (key !== "context_digest") {
      unsigned[key] = value;
    }
  }
  const canonical = canonicalJson(unsigned);
  if (canonical === undefined) {
    return false;
  }
  const digest = `sha256:${createHash("sha256").update(canonical, "utf8").digest("hex")}`;
  return envelope.context_digest === digest;
}
function decodeAuthority(value: unknown, generatedAtNanoseconds: bigint): AuthorityStamp | undefined {
  const stamp = asObject(value);
  if (!stamp || !hasExactKeys(stamp, AUTHORITY_KEYS)) {
    return undefined;
  }
  const modality = stamp.modality;
  const owner = boundedNonEmptyString(stamp.owner);
  const source = boundedNonEmptyString(stamp.source);
  const runtimeEpoch = boundedNonEmptyString(stamp.runtime_epoch, MAX_KEY_CODE_POINTS);
  const observedAt = boundedNonEmptyString(stamp.observed_at);
  const observedAtNanoseconds = rfc3339Nanoseconds(observedAt);
  const expiresAt = stamp.expires_at;
  const expiresAtNanoseconds = expiresAt === null ? null : rfc3339Nanoseconds(expiresAt);
  if (
    typeof modality !== "string"
    || !AUTHORITY_MODALITIES.has(modality as AuthorityModality)
    || !owner
    || !source
    || stringLooksSecret(owner)
    || stringLooksSecret(source)
    || !runtimeEpoch
    || stringLooksSecret(runtimeEpoch)
    || !observedAt
    || observedAtNanoseconds === undefined
    || observedAtNanoseconds > generatedAtNanoseconds
    || (expiresAt !== null && expiresAtNanoseconds === undefined)
    || (
      expiresAtNanoseconds !== null
      && expiresAtNanoseconds !== undefined
      && expiresAtNanoseconds <= observedAtNanoseconds
    )
    || (expiresAtNanoseconds !== null && expiresAtNanoseconds !== undefined
      && expiresAtNanoseconds - observedAtNanoseconds > MAX_ENVELOPE_TTL_NANOSECONDS)
  ) {
    return undefined;
  }
  return {
    modality: modality as AuthorityModality,
    owner,
    source,
    observed_at: observedAt,
    expires_at: expiresAt as string | null,
    runtime_epoch: runtimeEpoch,
  };
}
function freshnessIsConsistent(status: HelmProjectionStatus, authority: AuthorityStamp, generatedAtNanoseconds: bigint, envelopeRuntimeEpoch: string): boolean {
  const expiresAtNanoseconds = rfc3339Nanoseconds(authority.expires_at);
  if (status === "unavailable") {
    return authority.modality === "unknown" && authority.expires_at === null
      && authority.runtime_epoch === envelopeRuntimeEpoch;
  }
  if (status !== authority.modality) {
    return false;
  }
  if (
    ["observed", "configured", "held"].includes(status)
    && authority.runtime_epoch !== envelopeRuntimeEpoch
  ) {
    return false;
  }
  if (status === "stale") {
    return expiresAtNanoseconds !== undefined && expiresAtNanoseconds <= generatedAtNanoseconds;
  }
  return expiresAtNanoseconds === undefined || generatedAtNanoseconds < expiresAtNanoseconds;
}
const ROUTE_IDENTITY_FIELDS = ["served_provider_id", "served_model_id", "served_identity_observed_at", "route_evidence_expires_at", "route_receipt_ref", "route_receipt_sha256", "route_verifier_id", "route_verifier_version", "route_evidence_synthetic"] as const;
const OBSERVATION_COLLECTIONS: Partial<Record<HelmContextProjectionName, readonly [string, string]>> = {
  task_board: ["tasks", "updated_at"], runtime_state: ["sessions", "updated_at"], session: ["sessions", "updated_at"], receipts: ["receipts", "created_at"], swarm: ["agents", "last_heartbeat"], evolution: ["entries", "timestamp"],
};
function nonemptyString(value: unknown): value is string { return typeof value === "string" && value.length > 0; }
function collectionRows(data: UnknownObject, key: string): UnknownObject[] {
  const items = asObject(data[key])?.items;
  return Array.isArray(items) ? items.map(asObject).filter((item): item is UnknownObject => !!item) : [];
}
function bridgeRouteIsConsistent(data: UnknownObject, generated: bigint): boolean {
  const evaluator = data.served_identity_source === "provider_response_via_route_evaluator";
  const identifiers = ["active_session_id", "requested_provider_id", "requested_model_id", "served_provider_id", "served_model_id", "route_receipt_ref", "route_verifier_id", "route_verifier_version", "route_seat_id"];
  if (identifiers.some((key) => data[key] !== null && !nonemptyString(data[key])) || !nonemptyString(data.route_verdict_reason)
    || (data.requested_provider_id === null) !== (data.requested_model_id === null)
    || (data.active_phase !== null && !nonemptyString(data.active_session_id))
    || (!evaluator && (ROUTE_IDENTITY_FIELDS.some((key) => data[key] !== null)
      || (data.route_seat_id === null) !== (data.route_verification_evaluated_at === null)))) return false;
  const observed = rfc3339Nanoseconds(data.served_identity_observed_at);
  const expiry = rfc3339Nanoseconds(data.route_evidence_expires_at);
  const evaluated = rfc3339Nanoseconds(data.route_verification_evaluated_at);
  if (evaluator && (!nonemptyString(data.served_provider_id) || !nonemptyString(data.served_model_id)
    || observed === undefined || !["fresh", "expired"].includes(data.route_evidence_freshness as string))) return false;
  const onCall = data.route_verdict === "ON_CALL";
  if (onCall !== data.route_exact_model_proven) return false;
  const complete = evaluator && observed !== undefined && expiry !== undefined && evaluated !== undefined
    && ["route_receipt_ref", "route_verifier_id", "route_verifier_version", "route_seat_id"].every((key) => nonemptyString(data[key]))
    && typeof data.route_evidence_synthetic === "boolean"
    && typeof data.route_receipt_sha256 === "string" && /^[0-9a-f]{64}$/.test(data.route_receipt_sha256);
  if (data.route_evidence_freshness === "fresh" && (!complete || expiry! <= generated)) return false;
  if (data.route_evidence_freshness === "expired" && (!complete || expiry! > generated)) return false;
  if (onCall && (data.route_evidence_freshness !== "fresh" || data.route_evidence_synthetic !== false
    || data.route_verdict_reason !== "verified")) return false;
  return !(observed !== undefined && expiry !== undefined && (observed >= expiry || expiry - observed > MAX_ROUTE_TTL_NANOSECONDS))
    && !(observed !== undefined && evaluated !== undefined && observed > evaluated);
}
function actionSemanticsAreConsistent(data: UnknownObject): boolean {
  return collectionRows(data, "actions").every((item) => {
    const effects = item.effects as unknown[];
    const cancel = nonemptyString(item.cancel_action_id);
    return nonemptyString(item.action_id) && nonemptyString(item.label) && nonemptyString(item.owner)
      && effects.length > 0 && effects.every((effect) => typeof effect === "string" && effect.length > 0)
      && (item.risk === "safe_read" || item.requires_approval === true)
      && (item.cancel_action_id === null || cancel) && item.reversible === cancel;
  });
}
function projectionSemanticsAreConsistent(region: HelmContextProjectionName, data: UnknownObject, authority: AuthorityStamp, generated: bigint): boolean {
  const observations: unknown[] = region === "bridge_session"
    ? [data.served_identity_observed_at, data.route_verification_evaluated_at]
    : region === "mission_control" ? [asObject(data.mission)?.updated_at] : [];
  const spec = OBSERVATION_COLLECTIONS[region];
  if (spec) observations.push(...collectionRows(data, spec[0]).map((item) => item[spec[1]]));
  const authorityObserved = rfc3339Nanoseconds(authority.observed_at)!;
  const chronology = observations.every((value) => {
    const instant = value === null || value === undefined ? undefined : rfc3339Nanoseconds(value);
    return value === null || value === undefined || (instant !== undefined && instant <= authorityObserved && instant <= generated);
  });
  return chronology
    && (region !== "bridge_session" || bridgeRouteIsConsistent(data, generated))
    && (region !== "actions" || actionSemanticsAreConsistent(data));
}
function decodeProjection(value: unknown, expectedRegion: HelmContextProjectionName, runtimeEpoch: string, generatedAtNanoseconds: bigint, dataNodes: {count: number}, synthetic: boolean): HelmContextProjection | undefined {
  const projection = asObject(value);
  if (!projection || !hasExactKeys(projection, PROJECTION_KEYS)) {
    return undefined;
  }
  const status = projection.status;
  const authority = decodeAuthority(projection.authority, generatedAtNanoseconds);
  const data = asObject(projection.data);
  const reason = projection.unavailable_reason;
  const canonicalAuthority = authority && authority.owner === OWNER_BY_REGION[expectedRegion]
    && authority.source === `${SOURCE_BY_REGION[expectedRegion]}${status === "unavailable" ? ":not_observed" : ""}`;
  const authorityAllowed = synthetic && status !== "unavailable" ? authority?.owner === "SyntheticHelmContextFixture" && authority.source === `synthetic.${expectedRegion}` : canonicalAuthority || (!synthetic && status !== "unavailable" && expectedRegion === "swarm" && authority?.owner === "AgentPool" && authority.source === "AgentPool.list_agents");
  if (
    projection.region !== expectedRegion
    || typeof status !== "string"
    || !PROJECTION_STATUSES.has(status as HelmProjectionStatus)
    || !authority
    || !authorityAllowed
    || !data
    || !boundedJsonValue(data, 0, dataNodes)
    || (status !== "unavailable" && !helmProjectionDataIsValid(
      expectedRegion, data, (item) => rfc3339Nanoseconds(item) !== undefined,
    ))
    || (status !== "unavailable" && !projectionSemanticsAreConsistent(
      expectedRegion, data, authority, generatedAtNanoseconds,
    ))
    || !freshnessIsConsistent(
      status as HelmProjectionStatus,
      authority,
      generatedAtNanoseconds,
      runtimeEpoch,
    )
  ) {
    return undefined;
  }
  if (status === "unavailable") {
    if (!boundedNonEmptyString(reason) || stringLooksSecret(reason as string) || Object.keys(data).length !== 0) {
      return undefined;
    }
  } else if (reason !== null) {
    return undefined;
  }
  return {
    region: expectedRegion,
    status: status as HelmProjectionStatus,
    authority,
    data: JSON.parse(canonicalJson(data)!) as UnknownObject,
    unavailable_reason: reason as string | null,
  } as HelmContextProjection;
}
export function decodeHelmContextEnvelope(value: unknown): HelmContextEnvelope | undefined {
  const envelope = asObject(value);
  if (!envelope || !hasExactKeys(envelope, ENVELOPE_KEYS) || !serializedSizeWithinLimit(envelope)) {
    return undefined;
  }
  const generatedAt = boundedNonEmptyString(envelope.generated_at);
  const expiresAt = boundedNonEmptyString(envelope.expires_at);
  const runtimeEpoch = boundedNonEmptyString(envelope.runtime_epoch, MAX_KEY_CODE_POINTS);
  const generatedAtNanoseconds = rfc3339Nanoseconds(generatedAt);
  const expiresAtNanoseconds = rfc3339Nanoseconds(expiresAt);
  const projectionsObject = asObject(envelope.projections);
  if (
    envelope.schema_version !== HELM_CONTEXT_SCHEMA
    || !generatedAt
    || !expiresAt
    || !runtimeEpoch
    || stringLooksSecret(runtimeEpoch)
    || generatedAtNanoseconds === undefined
    || expiresAtNanoseconds === undefined
    || generatedAtNanoseconds >= expiresAtNanoseconds
    || expiresAtNanoseconds - generatedAtNanoseconds > MAX_ENVELOPE_TTL_NANOSECONDS
    || typeof envelope.synthetic !== "boolean"
    || envelope.provider_state_promotion !== false
    || typeof envelope.context_digest !== "string"
    || !SHA256_DIGEST.test(envelope.context_digest)
    || !digestMatchesEnvelope(envelope)
    || !projectionsObject
    || !hasExactKeys(projectionsObject, HELM_CONTEXT_PROJECTION_NAMES)
  ) {
    return undefined;
  }
  const dataNodes = {count: 0};
  const decoded = HELM_CONTEXT_PROJECTION_NAMES.map((region) => (
    decodeProjection(projectionsObject[region], region, runtimeEpoch, generatedAtNanoseconds, dataNodes, envelope.synthetic as boolean)
  ));
  if (decoded.some((projection) => projection === undefined || projection.authority.expires_at !== null
    && rfc3339Nanoseconds(projection.authority.expires_at)! > expiresAtNanoseconds)) {
    return undefined;
  }
  const projections = Object.fromEntries(
    HELM_CONTEXT_PROJECTION_NAMES.map((region, index) => [region, decoded[index]]),
  ) as HelmContextProjections;
  return deepFreeze({
    schema_version: HELM_CONTEXT_SCHEMA,
    generated_at: generatedAt,
    expires_at: expiresAt,
    runtime_epoch: runtimeEpoch,
    synthetic: envelope.synthetic,
    provider_state_promotion: false,
    projections,
    context_digest: envelope.context_digest,
  });
}
export function helmContextEnvelopeIsUsableAt(
  envelope: HelmContextEnvelope, now: Date = new Date(),
): boolean {
  const instant = Number.isFinite(now.getTime()) ? BigInt(now.getTime()) * 1_000_000n : undefined;
  const generated = rfc3339Nanoseconds(envelope.generated_at);
  const expires = rfc3339Nanoseconds(envelope.expires_at);
  const bridge = envelope.projections.bridge_session;
  const evidenceExpiry = bridge.status !== "unavailable"
    ? rfc3339Nanoseconds(bridge.data.route_evidence_expires_at) : undefined;
  const routeUsable = bridge.status === "unavailable" || bridge.data.route_evidence_freshness !== "fresh"
    || (instant !== undefined && evidenceExpiry !== undefined && instant < evidenceExpiry);
  const projectionsUsable = instant !== undefined && Object.values(envelope.projections).every((item) =>
    item.status === "stale" || item.status === "unavailable" || item.authority.expires_at === null
    || (rfc3339Nanoseconds(item.authority.expires_at) ?? instant) > instant);
  return instant !== undefined && generated !== undefined && expires !== undefined
    && generated <= instant && instant < expires && routeUsable && projectionsUsable;
}
export function helmContextEnvelopeFromEvent(value: unknown): HelmContextResultEvent | undefined {
  const event = asObject(value);
  if (!event || !hasExactKeys(event, EVENT_KEYS) || event.type !== "helm.context.result") {
    return undefined;
  }
  const requestId = boundedNonEmptyString(event.request_id, MAX_REQUEST_ID_CODE_POINTS);
  const envelope = decodeHelmContextEnvelope(event.envelope);
  if (
    !requestId
    || !SAFE_REQUEST_ID.test(requestId)
    || stringLooksSecret(requestId)
    || !envelope
  ) {
    return undefined;
  }
  return deepFreeze({type: "helm.context.result", request_id: requestId, envelope});
}
