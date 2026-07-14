import { inspectRfc3339Timestamp } from "../components/a2a-node/a2aNodeTimestamp.mjs";

export {
  deriveEvidenceComparisonNow,
  deriveFreshness,
  inspectRfc3339Timestamp,
} from "../components/a2a-node/a2aNodeTimestamp.mjs";

export const RECEIPT_TIER_ORDER = [
  "DOMAIN_RECEIPTED",
  "HANDLER_ACKED",
  "CORE_FLUSH_ONLY",
  "PUBLISH_ACCEPTED",
  "NO_CONTACT",
] as const;

export type ReceiptTier = (typeof RECEIPT_TIER_ORDER)[number];
export type RuntimeTruthState = "runtime" | "stale" | "unreachable" | "unknown";

export interface ReceiptTierCount {
  tier: ReceiptTier;
  count: number;
}

export interface ReceiptEvidence {
  id: string;
  key: string;
  state: "known" | "unknown";
  tier: ReceiptTier | null;
  rawTier: string;
  reason: string | null;
}

export interface ReceiptLadder {
  tiers: ReceiptTierCount[];
  unknown: ReceiptEvidence[];
  records: ReceiptEvidence[];
}

export interface Freshness {
  state: RuntimeTruthState;
  ageMs: number | null;
}

export interface StreamEmptyState {
  state:
    | "intentional-empty"
    | "partial"
    | "blocked"
    | "unknown"
    | "unreachable";
  title: string;
  detail: string;
}

export type StreamSourceTruth =
  | "ok"
  | "blocked"
  | "unknown"
  | "unreachable";

export interface ActivityItem {
  id: string;
  key: string;
  source: "trace" | "a2a";
  timestamp: string | null;
  timestampMs: number | null;
  actor: string;
  title: string;
  detail: string;
  status: string;
  evidenceState: "known" | "unknown";
}

interface SortableActivity extends ActivityItem {
  sourceIndex: number;
}

const RECEIPT_TIERS = new Set<string>(RECEIPT_TIER_ORDER);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function stringValue(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function bodyField(body: unknown, key: string): string {
  if (typeof body !== "string") {
    return "";
  }
  const prefix = `${key}:`;
  const line = body
    .split(/\r?\n/)
    .find((candidate) => candidate.trimStart().startsWith(prefix));
  return line ? line.trimStart().slice(prefix.length).trim() : "";
}

export function readEvidenceField(record: unknown, key: string): string {
  if (!isRecord(record)) {
    return "";
  }
  return stringValue(record[key]) || bodyField(record.body, key);
}

function rawReceiptTier(record: unknown): string {
  if (!isRecord(record)) {
    return "<missing>";
  }
  return (
    stringValue(record.contact_evidence_tier) ||
    bodyField(record.body, "contact_evidence_tier") ||
    stringValue(record.ack_tier) ||
    "<missing>"
  );
}

export class UnknownEvidenceTierError extends Error {
  readonly rawTier: string;

  constructor(rawTier: string) {
    super(`Unknown evidence tier "${rawTier}"`);
    this.name = "UnknownEvidenceTierError";
    this.rawTier = rawTier;
  }
}

export function extractReceiptTier(record: unknown): ReceiptTier {
  const rawTier = rawReceiptTier(record);
  const canonical = rawTier.toUpperCase();
  if (!RECEIPT_TIERS.has(canonical)) {
    throw new UnknownEvidenceTierError(rawTier);
  }
  return canonical as ReceiptTier;
}

function recordId(record: unknown, index: number): string {
  if (isRecord(record)) {
    const id = stringValue(record.id) || stringValue(record.receipt_id);
    if (id) {
      return id;
    }
  }
  return `receipt-unknown-${index + 1}`;
}

export function readReceiptEvidence(
  record: unknown,
  index = 0,
  nowMs = Date.now(),
): ReceiptEvidence {
  const id = recordId(record, index);
  const key = `receipt:${id}:${index}`;
  const createdAt = readEvidenceField(record, "created_at");
  if (createdAt) {
    const timestamp = inspectRfc3339Timestamp(createdAt, nowMs);
    if (!timestamp.valid) {
      return {
        id,
        key,
        state: "unknown",
        tier: null,
        rawTier: rawReceiptTier(record),
        reason: `Unknown receipt evidence — ${timestamp.detail}`,
      };
    }
  }

  try {
    const tier = extractReceiptTier(record);
    return {
      id,
      key,
      state: "known",
      tier,
      rawTier: tier,
      reason: null,
    };
  } catch (error) {
    const rawTier =
      error instanceof UnknownEvidenceTierError
        ? error.rawTier
        : rawReceiptTier(record);
    return {
      id,
      key,
      state: "unknown",
      tier: null,
      rawTier,
      reason: `Unknown evidence tier "${rawTier}"`,
    };
  }
}

function groupReceiptEvidence(
  records: readonly unknown[],
  nowMs: number,
): ReceiptEvidence[] {
  const evidenceRecords = records.map((record, index) =>
    readReceiptEvidence(record, index, nowMs),
  );
  const idCounts = new Map<string, number>();
  for (const evidence of evidenceRecords) {
    idCounts.set(evidence.id, (idCounts.get(evidence.id) ?? 0) + 1);
  }
  return evidenceRecords.map((evidence) =>
    (idCounts.get(evidence.id) ?? 0) > 1
      ? {
          ...evidence,
          state: "unknown",
          tier: null,
          reason: `Duplicate receipt id "${evidence.id}"`,
        }
      : evidence,
  );
}

export function buildReceiptLadder(
  records: readonly unknown[],
  nowMs = Date.now(),
): ReceiptLadder {
  const counts = new Map<ReceiptTier, number>(
    RECEIPT_TIER_ORDER.map((tier) => [tier, 0]),
  );
  const unknown: ReceiptEvidence[] = [];
  const evidenceRecords = groupReceiptEvidence(records, nowMs);
  for (const evidence of evidenceRecords) {
    if (evidence.state === "unknown" || evidence.tier === null) {
      unknown.push(evidence);
      continue;
    }
    counts.set(evidence.tier, (counts.get(evidence.tier) ?? 0) + 1);
  }

  return {
    tiers: RECEIPT_TIER_ORDER.map((tier) => ({
      tier,
      count: counts.get(tier) ?? 0,
    })),
    unknown,
    records: evidenceRecords,
  };
}

export function deriveStreamEmptyState(
  traceState: StreamSourceTruth,
  a2aState: StreamSourceTruth,
): StreamEmptyState {
  if (traceState === "ok" && a2aState === "ok") {
    return {
      state: "intentional-empty",
      title: "The evidence rail is quiet",
      detail: "Both sources answered without recent trace or A2A records.",
    };
  }
  if (traceState === "ok") {
    return {
      state: "partial",
      title: "Partial evidence rail",
      detail: `Trace activity answered, but A2A receipts are ${a2aState}. No activity was returned by the available source.`,
    };
  }
  if (a2aState === "ok") {
    return {
      state: "partial",
      title: "Partial evidence rail",
      detail: `A2A receipts answered, but trace activity is ${traceState}. No activity was returned by the available source.`,
    };
  }
  const state =
    traceState === "unreachable" && a2aState === "unreachable"
      ? "unreachable"
      : traceState === "blocked" || a2aState === "blocked"
        ? "blocked"
        : "unknown";
  return {
    state,
    title:
      state === "unreachable"
        ? "Evidence rail unreachable"
        : state === "blocked"
          ? "Evidence rail blocked"
          : "Evidence rail truth unknown",
    detail: `Trace activity is ${traceState}; A2A receipts are ${a2aState}. No empty-state claim can be made.`,
  };
}

export function formatEvidenceAge(ageMs: number | null): string {
  if (ageMs === null) {
    return "time unknown";
  }
  if (ageMs < 60_000) {
    return `${Math.floor(ageMs / 1_000)}s ago`;
  }
  if (ageMs < 3_600_000) {
    return `${Math.floor(ageMs / 60_000)}m ago`;
  }
  if (ageMs < 86_400_000) {
    return `${Math.floor(ageMs / 3_600_000)}h ago`;
  }
  return `${Math.floor(ageMs / 86_400_000)}d ago`;
}

function parsedTimestamp(
  value: unknown,
  nowMs: number,
): {
  raw: string | null;
  time: number | null;
  issue: string | null;
} {
  const timestamp = inspectRfc3339Timestamp(value, nowMs);
  return {
    raw: timestamp.raw,
    time: timestamp.valid ? timestamp.timestampMs : null,
    issue: timestamp.issue,
  };
}

function unknownTimestampDetail(
  kind: string,
  timestamp: ReturnType<typeof parsedTimestamp>,
): string {
  const problem =
    timestamp.issue === "future" ? "future timestamp" : "malformed timestamp";
  return `Unknown ${kind} evidence — ${problem}: ${timestamp.raw ?? "<missing>"}`;
}

function traceActivity(
  record: unknown,
  index: number,
  nowMs: number,
): SortableActivity {
  const value = isRecord(record) ? record : {};
  const id = stringValue(value.id) || `trace-unknown-${index + 1}`;
  const agent = stringValue(value.agent);
  const action = stringValue(value.action);
  const state = stringValue(value.state);
  const timestamp = parsedTimestamp(value.timestamp, nowMs);
  const known = Boolean(
    isRecord(record) &&
      stringValue(value.id) &&
      agent &&
      action &&
      state &&
      timestamp.time !== null,
  );

  return {
    id,
    key: `activity:trace:${id}:${index}`,
    source: "trace",
    timestamp: timestamp.raw,
    timestampMs: timestamp.time,
    actor: agent || "unknown agent",
    title: action || "Unknown trace evidence",
    detail: known
      ? `${agent} · ${state}`
      : timestamp.time === null
        ? unknownTimestampDetail("trace", timestamp)
        : "Unknown trace evidence — required fields are malformed",
    status: state || "unknown",
    evidenceState: known ? "known" : "unknown",
    sourceIndex: index,
  };
}

function a2aActivity(
  record: unknown,
  index: number,
  nowMs: number,
  evidence: ReceiptEvidence,
): SortableActivity {
  const value = isRecord(record) ? record : {};
  const id = stringValue(value.id) || `a2a-unknown-${index + 1}`;
  const title = stringValue(value.title);
  const body = typeof value.body === "string" ? value.body : "";
  const status = stringValue(value.status);
  const target =
    bodyField(body, "to") ||
    bodyField(body, "agent_uid") ||
    bodyField(body, "target_uid") ||
    "unknown peer";
  const timestamp = parsedTimestamp(value.created_at, nowMs);
  const known = Boolean(
    isRecord(record) &&
      stringValue(value.id) &&
      title &&
      body &&
      status &&
      timestamp.time !== null &&
      evidence.state === "known",
  );

  let detail = `${evidence.rawTier} · ${status || "unknown status"}`;
  if (timestamp.time === null) {
    detail = unknownTimestampDetail("A2A", timestamp);
  } else if (!known) {
    detail =
      evidence.reason ??
      "Unknown A2A evidence — required fields are malformed";
  }

  return {
    id,
    key: `activity:a2a:${id}:${index}`,
    source: "a2a",
    timestamp: timestamp.raw,
    timestampMs: timestamp.time,
    actor: target,
    title: title || "Unknown A2A evidence",
    detail,
    status: status || "unknown",
    evidenceState: known ? "known" : "unknown",
    sourceIndex: index,
  };
}

export function mergeActivity(
  traces: readonly unknown[],
  a2aCards: readonly unknown[],
  nowMs = Date.now(),
): ActivityItem[] {
  const sourceRank = { trace: 0, a2a: 1 } as const;
  const a2aEvidence = groupReceiptEvidence(a2aCards, nowMs);
  const merged = [
    ...traces.map((record, index) => traceActivity(record, index, nowMs)),
    ...a2aCards.map((record, index) =>
      a2aActivity(
        record,
        index,
        nowMs,
        a2aEvidence[index] ?? readReceiptEvidence(record, index, nowMs),
      ),
    ),
  ];

  merged.sort((left, right) => {
    if (left.timestampMs !== null && right.timestampMs !== null) {
      const timeDifference = right.timestampMs - left.timestampMs;
      if (timeDifference !== 0) {
        return timeDifference;
      }
    } else if (left.timestampMs !== null) {
      return -1;
    } else if (right.timestampMs !== null) {
      return 1;
    }

    const sourceDifference =
      sourceRank[left.source] - sourceRank[right.source];
    return sourceDifference || left.sourceIndex - right.sourceIndex;
  });

  return merged.map(({ sourceIndex, ...activity }) => {
    void sourceIndex;
    return activity;
  });
}
