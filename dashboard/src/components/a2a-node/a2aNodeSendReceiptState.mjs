import {
  isRecord,
  receiptNow,
  receiptTimestamp,
  resolveReceiptStaleAfterMs,
} from "./a2aNodeSendReceiptFs.mjs";

const SUBJECT_TOKEN = /^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$/;
const SAFE_KIND = new Set(["transport", "upstream", "projection"]);

export function storedResult(value, packetId, to) {
  if (
    !isRecord(value) ||
    Object.keys(value).length !== 6 ||
    value.ok !== true ||
    value.subject !== `dharma.a2a.${to}` ||
    !Number.isSafeInteger(value.seq) ||
    value.seq <= 0 ||
    typeof value.from !== "string" ||
    !SUBJECT_TOKEN.test(value.from) ||
    value.packet_id !== packetId ||
    value.evidence_tier !== "STORED"
  ) {
    return null;
  }
  return {
    ok: true,
    subject: value.subject,
    seq: value.seq,
    from: value.from,
    packet_id: value.packet_id,
    evidence_tier: "STORED",
  };
}

export function unknownError(value, packetId) {
  const error = isRecord(value) ? value : {};
  return {
    kind: SAFE_KIND.has(error.kind) ? error.kind : "upstream",
    status:
      Number.isInteger(error.status) &&
      error.status >= 400 &&
      error.status <= 599
        ? error.status
        : 502,
    message: "Mailbox send outcome is unknown",
    outcome: "UNKNOWN",
    packet_id: packetId,
  };
}

export function publicStatus(state, packetId) {
  const target =
    isRecord(state) &&
    typeof state.to === "string" &&
    SUBJECT_TOKEN.test(state.to)
      ? state.to
      : "unknown";
  if (isRecord(state) && state.state === "STORED") {
    const receipt = storedResult(state.result, packetId, target);
    if (receipt) {
      return {
        state: "stored",
        status: "STORED",
        packet_id: packetId,
        target,
        receipt,
      };
    }
  }
  if (isRecord(state) && state.state === "PENDING") {
    return {
      state: "pending",
      status: "PENDING",
      packet_id: packetId,
      target,
    };
  }
  return {
    state: "unknown",
    status: "UNKNOWN",
    packet_id: packetId,
    target,
    error: unknownError(
      isRecord(state) ? state.error : null,
      packetId,
    ),
  };
}

export function pendingIsStale(state, options) {
  if (!isRecord(state) || state.state !== "PENDING") return false;
  const timestamp = Date.parse(
    typeof state.updated_at === "string"
      ? state.updated_at
      : String(state.created_at),
  );
  return (
    !Number.isFinite(timestamp) ||
    receiptNow(options) - timestamp >=
      resolveReceiptStaleAfterMs(options?.staleAfterMs)
  );
}

export function recoveredUnknownState(
  current,
  packetId,
  options,
) {
  const error = unknownError(
    { kind: "upstream", status: 504 },
    packetId,
  );
  return {
    version: 1,
    packet_id: packetId,
    request_hash:
      isRecord(current) && typeof current.request_hash === "string"
        ? current.request_hash
        : null,
    to:
      isRecord(current) &&
      typeof current.to === "string" &&
      SUBJECT_TOKEN.test(current.to)
        ? current.to
        : "unknown",
    state: "UNKNOWN",
    created_at:
      isRecord(current) && typeof current.created_at === "string"
        ? current.created_at
        : receiptTimestamp(options),
    updated_at: receiptTimestamp(options),
    error,
  };
}

export function initialUnknown(
  packetId,
  to,
  requestHash,
  options,
) {
  const now = receiptTimestamp(options);
  return {
    version: 1,
    packet_id: packetId,
    request_hash: requestHash,
    to,
    state: "UNKNOWN",
    created_at: now,
    updated_at: now,
    error: unknownError(
      { kind: "upstream", status: 504 },
      packetId,
    ),
  };
}
