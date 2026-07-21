import {
  deriveFreshness,
  inspectRfc3339Timestamp,
} from "./a2aNodeTimestamp.mjs";
import { fetchNodeJson } from "./a2aNodeTransport.mjs";

export type FleetRuntimeTruthState =
  | "runtime"
  | "stale"
  | "unreachable"
  | "unknown";

export interface FleetNode {
  node_id: string;
  endpoint: string;
  ssh_alias: string;
  status: string;
  last_heartbeat: string;
  capabilities: string[];
  metadata: Record<string, unknown>;
  api_key_env: string;
}

export interface FleetNodesResponse {
  count: number;
  nodes: FleetNode[];
}

export interface RawFleetFetchOptions {
  fetcher?: typeof fetch;
  url?: string;
  nowMs?: number;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export class FleetProjectionError extends Error {
  constructor(message: string, cause?: unknown) {
    super(message, cause === undefined ? undefined : { cause });
    this.name = "FleetProjectionError";
  }
}

function projectionError(message: string): FleetProjectionError {
  return new FleetProjectionError(message);
}

function requireString(
  record: Record<string, unknown>,
  key: string,
  index: number,
): string {
  if (typeof record[key] !== "string") {
    throw projectionError(
      `fleet node ${index} field "${key}" must be a string`,
    );
  }
  return record[key] as string;
}

function parseFleetNode(
  value: unknown,
  index: number,
  nowMs: number,
): FleetNode {
  if (!isRecord(value)) {
    throw projectionError(`fleet node ${index} must be an object`);
  }

  const nodeId = requireString(value, "node_id", index).trim();
  if (!nodeId) {
    throw projectionError(
      `fleet node ${index} field "node_id" cannot be empty`,
    );
  }
  if (
    !Array.isArray(value.capabilities) ||
    value.capabilities.some((capability) => typeof capability !== "string")
  ) {
    throw projectionError(
      `fleet node ${index} field "capabilities" must be a string array`,
    );
  }
  const capabilities = value.capabilities.map((capability) => capability.trim());
  if (capabilities.some((capability) => !capability)) {
    throw projectionError(
      `fleet node ${index} capabilities cannot contain empty names`,
    );
  }
  const seenCapabilities = new Set<string>();
  for (const capability of capabilities) {
    if (seenCapabilities.has(capability)) {
      throw projectionError(
        `fleet node ${index} has duplicate capability "${capability}"`,
      );
    }
    seenCapabilities.add(capability);
  }
  if (!isRecord(value.metadata)) {
    throw projectionError(
      `fleet node ${index} field "metadata" must be an object`,
    );
  }

  const lastHeartbeat = requireString(value, "last_heartbeat", index).trim();
  if (lastHeartbeat) {
    const timestamp = inspectRfc3339Timestamp(lastHeartbeat, nowMs);
    if (!timestamp.valid) {
      throw projectionError(
        `fleet node ${index} field "last_heartbeat" ${timestamp.detail}`,
      );
    }
  }

  return {
    node_id: nodeId,
    endpoint: requireString(value, "endpoint", index),
    ssh_alias: requireString(value, "ssh_alias", index),
    status: requireString(value, "status", index),
    last_heartbeat: lastHeartbeat,
    capabilities,
    metadata: { ...value.metadata },
    api_key_env: requireString(value, "api_key_env", index),
  };
}

export function parseFleetNodesResponse(
  payload: unknown,
  nowMs = Date.now(),
): FleetNodesResponse {
  if (isRecord(payload) && "status" in payload && "data" in payload) {
    throw projectionError(
      "Expected raw fleet response {count,nodes}; received an ApiResponse wrapper",
    );
  }
  if (!isRecord(payload)) {
    throw projectionError("Raw fleet response must be an object");
  }
  if (!Number.isInteger(payload.count) || Number(payload.count) < 0) {
    throw projectionError(
      "Raw fleet response count must be a non-negative integer",
    );
  }
  if (!Array.isArray(payload.nodes)) {
    throw projectionError("Raw fleet response nodes must be an array");
  }

  const nodes = payload.nodes.map((node, index) =>
    parseFleetNode(node, index, nowMs),
  );
  const count = Number(payload.count);
  if (count !== nodes.length) {
    throw projectionError(
      "Raw fleet response count does not match nodes length",
    );
  }

  const seenNodeIds = new Set<string>();
  for (const node of nodes) {
    if (seenNodeIds.has(node.node_id)) {
      throw projectionError(`Duplicate node_id "${node.node_id}"`);
    }
    seenNodeIds.add(node.node_id);
  }
  return { count, nodes };
}

export function nodeStatusTone(status: string): FleetRuntimeTruthState {
  switch (status.trim().toLowerCase()) {
    case "online":
      return "runtime";
    case "degraded":
      return "stale";
    case "offline":
      return "unreachable";
    default:
      return "unknown";
  }
}

export function deriveFleetNodeTruth(
  node: Pick<FleetNode, "status" | "last_heartbeat">,
  nowMs = Date.now(),
): ReturnType<typeof deriveFreshness> {
  const status = nodeStatusTone(node.status);
  const freshness = deriveFreshness(node.last_heartbeat, nowMs);
  if (status === "unreachable" || freshness.state === "unreachable") {
    return { state: "unreachable", ageMs: freshness.ageMs };
  }
  if (status === "stale" || freshness.state === "stale") {
    return { state: "stale", ageMs: freshness.ageMs };
  }
  if (status === "runtime" && freshness.state === "runtime") {
    return { state: "runtime", ageMs: freshness.ageMs };
  }
  return { state: "unknown", ageMs: freshness.ageMs };
}

export async function fetchRawFleetNodes(
  options: RawFleetFetchOptions = {},
): Promise<FleetNodesResponse> {
  const url = options.url ?? "/api/fleet/nodes";
  const payload = await fetchNodeJson({
    url,
    fetcher: options.fetcher,
  });
  return parseFleetNodesResponse(payload, options.nowMs ?? Date.now());
}
