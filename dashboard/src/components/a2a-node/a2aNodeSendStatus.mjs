export const A2A_SEND_SESSION_KEY =
  "a2a-node:unresolved-send:v1";

const STATUS_URL =
  "/dashboard/a2a-node/api/a2a/send/status";
const UUID =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const SUBJECT_TOKEN = /^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$/;

function isRecord(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function exactKeys(value, expected) {
  const keys = Object.keys(value);
  return (
    keys.length === expected.length &&
    keys.every((key) => expected.includes(key))
  );
}

function unresolvedDescriptor(value) {
  if (
    !isRecord(value) ||
    !exactKeys(value, ["packet_id", "target", "status"]) ||
    typeof value.packet_id !== "string" ||
    !UUID.test(value.packet_id) ||
    typeof value.target !== "string" ||
    !SUBJECT_TOKEN.test(value.target) ||
    (value.status !== "PENDING" && value.status !== "UNKNOWN")
  ) {
    return null;
  }
  return {
    packet_id: value.packet_id,
    target: value.target,
    status: value.status,
  };
}

export function parseA2ASendUnresolved(value) {
  if (value === null) return null;
  try {
    return unresolvedDescriptor(JSON.parse(value));
  } catch {
    return null;
  }
}

export function serializeA2ASendUnresolved(value) {
  const safe = unresolvedDescriptor(value);
  if (!safe) throw new Error("Unsafe unresolved send descriptor");
  return JSON.stringify(safe);
}

export class A2AStatusRequestError extends Error {
  constructor(message, kind, status) {
    super(message);
    this.name = "A2AStatusRequestError";
    this.kind = kind;
    this.status = status;
  }
}

function statusKind(status) {
  if (status === 401 || status === 403) return "auth";
  if (status === 429) return "throttle";
  if (status >= 500) return "upstream";
  return "contract";
}

function storedStatus(value, packetId) {
  if (
    !isRecord(value) ||
    !exactKeys(value, ["packet_id", "target", "status", "receipt"]) ||
    value.packet_id !== packetId ||
    typeof value.target !== "string" ||
    !SUBJECT_TOKEN.test(value.target) ||
    value.status !== "STORED" ||
    !isRecord(value.receipt)
  ) {
    return null;
  }
  const receipt = value.receipt;
  if (
    !exactKeys(receipt, [
      "ok",
      "subject",
      "seq",
      "from",
      "packet_id",
      "evidence_tier",
    ]) ||
    receipt.ok !== true ||
    receipt.subject !== `dharma.a2a.${value.target}` ||
    !Number.isSafeInteger(receipt.seq) ||
    receipt.seq <= 0 ||
    typeof receipt.from !== "string" ||
    !SUBJECT_TOKEN.test(receipt.from) ||
    receipt.packet_id !== packetId ||
    receipt.evidence_tier !== "STORED"
  ) {
    return null;
  }
  return {
    packet_id: packetId,
    target: value.target,
    status: "STORED",
    receipt: {
      ok: true,
      subject: receipt.subject,
      seq: receipt.seq,
      from: receipt.from,
      packet_id: packetId,
      evidence_tier: "STORED",
    },
  };
}

export async function requestA2ASendStatus(packetId, options = {}) {
  if (!UUID.test(packetId)) {
    throw new A2AStatusRequestError(
      "Packet status identifier is invalid",
      "contract",
      400,
    );
  }
  const fetcher = options.fetcher ?? globalThis.fetch;
  let response;
  try {
    response = await fetcher(`${STATUS_URL}/${packetId}`, {
      method: "GET",
      headers: { Accept: "application/json" },
      cache: "no-store",
      credentials: "same-origin",
    });
  } catch {
    throw new A2AStatusRequestError(
      "Packet status is unreachable",
      "transport",
      null,
    );
  }
  if (!response.ok) {
    throw new A2AStatusRequestError(
      "Packet status is unavailable",
      statusKind(response.status),
      response.status,
    );
  }
  if (
    !(response.headers.get("Content-Type") ?? "")
      .toLowerCase()
      .includes("application/json")
  ) {
    throw new A2AStatusRequestError(
      "Packet status evidence is malformed",
      "projection",
      502,
    );
  }
  let payload;
  try {
    payload = await response.json();
  } catch {
    throw new A2AStatusRequestError(
      "Packet status evidence is malformed",
      "projection",
      502,
    );
  }
  const unresolved = unresolvedDescriptor(payload);
  if (unresolved && unresolved.packet_id === packetId) return unresolved;
  const stored = storedStatus(payload, packetId);
  if (stored) return stored;
  throw new A2AStatusRequestError(
    "Packet status evidence is malformed",
    "projection",
    502,
  );
}
