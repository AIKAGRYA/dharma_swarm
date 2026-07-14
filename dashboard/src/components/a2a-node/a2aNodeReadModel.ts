import type { AgentOut, TaskOut, TraceOut } from "@/lib/types";
import {
  inspectRfc3339Timestamp,
  normalizePythonDatetime,
} from "./a2aNodeTimestamp.mjs";
import {
  classifyNodeReadError,
  fetchNodeJson,
  NodeReadError,
} from "./a2aNodeTransport.mjs";

export {
  classifyNodeReadError,
  fetchNodeJson,
  NodeReadError,
} from "./a2aNodeTransport.mjs";

export type A2ANodeAgent = Pick<
  AgentOut,
  | "id"
  | "name"
  | "display_name"
  | "role"
  | "status"
  | "current_task"
  | "provider"
  | "model"
  | "model_label"
>;

export type A2ANodeTask = Pick<
  TaskOut,
  | "id"
  | "title"
  | "description"
  | "status"
  | "priority"
  | "assigned_to"
  | "updated_at"
>;

export type A2ANodeTrace = Pick<
  TraceOut,
  "id" | "timestamp" | "agent" | "action" | "state"
>;

export interface A2ANodeCard extends Record<string, unknown> {
  id: string;
  title: string;
  body: string;
  status: string;
  created_at: string;
}

export interface A2ANodeCardsPayload extends Record<string, unknown> {
  card_count: number;
  cards: A2ANodeCard[];
  partial: A2ANodePartialTruth | null;
}

export interface A2ANodePartialTruth {
  state: "partial";
  sourceCount: number;
  title: string;
  detail: string;
}

export type NodeReadErrorKind =
  | "transport"
  | "policy"
  | "configuration"
  | "auth"
  | "contract"
  | "throttle"
  | "upstream"
  | "projection";

export interface NodeFetchOptions {
  url: string;
  fetcher?: typeof fetch;
  nowMs?: number;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function unwrapEnvelope(payload: unknown): unknown {
  if (!isRecord(payload) || !("status" in payload) || !("data" in payload)) {
    return payload;
  }
  if (payload.status !== "ok") {
    throw new NodeReadError(
      "Backend returned an application error envelope",
      "contract",
    );
  }
  return payload.data;
}

function projectionError(message: string): never {
  throw new NodeReadError(message, "projection");
}

function projectionArray(payload: unknown, label: string): unknown[] {
  if (!Array.isArray(payload)) {
    projectionError(`${label} response is not an evidence array`);
  }
  return payload;
}

function projectionRecord(
  value: unknown,
  label: string,
  index: number,
): Record<string, unknown> {
  if (!isRecord(value)) {
    projectionError(`${label} item ${index} must be an object`);
  }
  return value;
}

function stringField(
  record: Record<string, unknown>,
  field: string,
  label: string,
  index: number,
  requireValue = false,
): string {
  const value = record[field];
  if (typeof value !== "string" || (requireValue && !value.trim())) {
    projectionError(
      `${label} item ${index} field "${field}" must be ${requireValue ? "a non-empty " : "a "}string`,
    );
  }
  return value;
}

function nullableStringField(
  record: Record<string, unknown>,
  field: string,
  label: string,
  index: number,
): string | null {
  const value = record[field];
  if (value !== null && typeof value !== "string") {
    projectionError(
      `${label} item ${index} field "${field}" must be a string or null`,
    );
  }
  return value;
}

function timestampField(
  record: Record<string, unknown>,
  field: string,
  label: string,
  index: number,
  nowMs: number,
  allowPythonDatetime = false,
): string {
  const value = allowPythonDatetime
    ? normalizePythonDatetime(record[field])
    : record[field];
  const evidence = inspectRfc3339Timestamp(value, nowMs);
  if (!evidence.valid || evidence.raw === null) {
    projectionError(
      `${label} item ${index} field "${field}" ${evidence.detail}`,
    );
  }
  return evidence.raw;
}

function assertUniqueIds(
  records: readonly { id: string }[],
  label: string,
): void {
  const seen = new Set<string>();
  for (const record of records) {
    if (seen.has(record.id)) {
      projectionError(`${label} response contains duplicate id "${record.id}"`);
    }
    seen.add(record.id);
  }
}

function readSourceErrorCount(value: unknown): number {
  if (!Array.isArray(value)) {
    projectionError("A2A card source_errors must be an array");
  }
  for (const [index, item] of value.entries()) {
    const sourceError = projectionRecord(item, "A2A source errors", index);
    stringField(sourceError, "source", "A2A source errors", index, true);
    if (
      "error" in sourceError &&
      (typeof sourceError.error !== "string" || !sourceError.error.trim())
    ) {
      projectionError(
        `A2A source errors item ${index} field "error" must be a non-empty string when present`,
      );
    }
  }
  return value.length;
}

function partialCardTruth(
  sourceCount: number,
  cardCount: number,
): A2ANodePartialTruth {
  return {
    state: "partial",
    sourceCount,
    title: "PARTIAL EVIDENCE · A2A card sources degraded",
    detail: `${sourceCount} ${sourceCount === 1 ? "source" : "sources"} failed; ${cardCount} validated ${cardCount === 1 ? "card" : "cards"} preserved. Backend error details were withheld.`,
  };
}

function parseAgent(value: unknown, index: number): A2ANodeAgent {
  const record = projectionRecord(value, "agents", index);
  return {
    id: stringField(record, "id", "agents", index, true),
    name: stringField(record, "name", "agents", index),
    display_name: stringField(record, "display_name", "agents", index),
    role: stringField(record, "role", "agents", index),
    status: stringField(record, "status", "agents", index, true),
    current_task: nullableStringField(
      record,
      "current_task",
      "agents",
      index,
    ),
    provider: stringField(record, "provider", "agents", index),
    model: stringField(record, "model", "agents", index),
    model_label: stringField(record, "model_label", "agents", index),
  };
}

function parseTask(
  value: unknown,
  index: number,
  nowMs: number,
): A2ANodeTask {
  const record = projectionRecord(value, "tasks", index);
  return {
    id: stringField(record, "id", "tasks", index, true),
    title: stringField(record, "title", "tasks", index, true),
    description: stringField(record, "description", "tasks", index),
    status: stringField(record, "status", "tasks", index, true),
    priority: stringField(record, "priority", "tasks", index),
    assigned_to: nullableStringField(
      record,
      "assigned_to",
      "tasks",
      index,
    ),
    updated_at: timestampField(
      record,
      "updated_at",
      "tasks",
      index,
      nowMs,
      true,
    ),
  };
}

function parseTrace(
  value: unknown,
  index: number,
  nowMs: number,
): A2ANodeTrace {
  const record = projectionRecord(value, "traces", index);
  return {
    id: stringField(record, "id", "traces", index, true),
    timestamp: timestampField(
      record,
      "timestamp",
      "traces",
      index,
      nowMs,
      true,
    ),
    agent: stringField(record, "agent", "traces", index, true),
    action: stringField(record, "action", "traces", index, true),
    state: stringField(record, "state", "traces", index, true),
  };
}

function parseCard(
  value: unknown,
  index: number,
  nowMs: number,
): A2ANodeCard {
  const record = projectionRecord(value, "A2A cards", index);
  return {
    ...record,
    id: stringField(record, "id", "A2A cards", index, true),
    title: stringField(record, "title", "A2A cards", index, true),
    body: stringField(record, "body", "A2A cards", index, true),
    status: stringField(record, "status", "A2A cards", index, true),
    created_at: timestampField(
      record,
      "created_at",
      "A2A cards",
      index,
      nowMs,
    ),
  };
}

export async function fetchNodeAgents(
  options: NodeFetchOptions,
): Promise<A2ANodeAgent[]> {
  const payload = unwrapEnvelope(await fetchNodeJson(options));
  const agents = projectionArray(payload, "agents").map(parseAgent);
  assertUniqueIds(agents, "agents");
  return agents;
}

export async function fetchNodeTasks(
  options: NodeFetchOptions,
): Promise<A2ANodeTask[]> {
  const payload = unwrapEnvelope(await fetchNodeJson(options));
  const nowMs = options.nowMs ?? Date.now();
  const tasks = projectionArray(payload, "tasks").map((value, index) =>
    parseTask(value, index, nowMs),
  );
  assertUniqueIds(tasks, "tasks");
  return tasks;
}

export async function fetchNodeTraces(
  options: NodeFetchOptions,
): Promise<A2ANodeTrace[]> {
  const payload = unwrapEnvelope(await fetchNodeJson(options));
  const nowMs = options.nowMs ?? Date.now();
  const traces = projectionArray(payload, "traces").map((value, index) =>
    parseTrace(value, index, nowMs),
  );
  assertUniqueIds(traces, "traces");
  return traces;
}

export async function fetchNodeCards(
  options: NodeFetchOptions,
): Promise<A2ANodeCardsPayload> {
  const response = await fetchNodeJson(options);
  let sourceErrorCount = 0;
  let payload: unknown;
  if (isRecord(response) && "source_errors" in response) {
    if (!("data" in response)) {
      projectionError("A2A card envelope is missing its data projection");
    }
    sourceErrorCount = readSourceErrorCount(response.source_errors);
    payload = response.data;
  } else {
    payload = unwrapEnvelope(response);
  }
  if (!isRecord(payload) || !Array.isArray(payload.cards)) {
    projectionError(
      "A2A card response is not a valid evidence projection",
    );
  }
  if (
    !Number.isInteger(payload.card_count) ||
    Number(payload.card_count) !== payload.cards.length
  ) {
    projectionError("A2A card response count does not match cards length");
  }
  const nowMs = options.nowMs ?? Date.now();
  const cards = payload.cards.map((value, index) =>
    parseCard(value, index, nowMs),
  );
  if (sourceErrorCount > 0 && cards.length === 0) {
    throw new NodeReadError(
      "A2A card sources returned no usable evidence; backend details were withheld",
      "contract",
    );
  }
  return {
    ...payload,
    card_count: Number(payload.card_count),
    cards,
    partial:
      sourceErrorCount > 0
        ? partialCardTruth(sourceErrorCount, cards.length)
        : null,
  };
}

export function nodeReadFailureView(error: unknown, surface: string): {
  truth: "unknown" | "blocked" | "unreachable";
  surfaceKind: "unknown" | "error";
  title: string;
  detail: string;
} {
  const classification = classifyNodeReadError(error);
  const titles: Record<NodeReadErrorKind, string> = {
    auth: `BLOCKED · ${surface} authentication rejected`,
    throttle: `BLOCKED · ${surface} throttled`,
    contract: `UNKNOWN EVIDENCE · ${surface} contract rejected`,
    projection: `UNKNOWN EVIDENCE · ${surface} projection rejected`,
    policy: `UNKNOWN EVIDENCE · ${surface} proxy policy rejected`,
    configuration: `UNKNOWN EVIDENCE · ${surface} proxy misconfigured`,
    transport: `${surface} unreachable`,
    upstream: `${surface} unreachable`,
  };
  const trustedDetail =
    error instanceof NodeReadError ||
    (error instanceof Error && error.name === "FleetProjectionError")
      ? error.message
      : "The read failed without trusted structured evidence.";
  return {
    truth: classification.truth,
    surfaceKind:
      classification.truth === "unreachable" ? "error" : "unknown",
    title: titles[classification.kind],
    detail: trustedDetail,
  };
}
