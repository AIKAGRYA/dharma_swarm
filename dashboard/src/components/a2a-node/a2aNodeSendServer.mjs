import { TextDecoder } from "node:util";
import { isAbsolute } from "node:path";

export const MAX_OPERATOR_MESSAGE_BYTES = 4 * 1024;
export const MAX_SEND_REQUEST_BYTES = 8 * 1024;
export const MAX_UPSTREAM_RESPONSE_BYTES = 8 * 1024;
const MAX_GATEWAY_TOKEN_BYTES = 4 * 1024;
const SEND_PATH = Object.freeze(["a2a", "send"]);
const JSON_CONTENT_TYPE =
  /^application\/json(?:\s*;\s*charset\s*=\s*utf-8)?$/i;
const SUBJECT_TOKEN = /^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$/;
const UUID =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const UNSAFE_CONTROL = /[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/u;
const VISIBLE_ASCII_TOKEN = /^[\x21-\x7e]+$/;
const utf8Decoder = new TextDecoder("utf-8", { fatal: true });

export class SendRequestError extends Error {
  /**
   * @param {string} message
   * @param {"policy" | "configuration" | "contract" | "projection"} kind
   * @param {number} status
   */
  constructor(message, kind, status) {
    super(message);
    this.name = "SendRequestError";
    this.kind = kind;
    this.status = status;
  }
}

/** @param {unknown} value */
function isRecord(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

/** @param {readonly string[]} path */
function validatePathSegments(path) {
  if (!Array.isArray(path) || path.length === 0) {
    throw new SendRequestError("POST path is not allowlisted", "policy", 405);
  }
  for (const segment of path) {
    if (
      typeof segment !== "string" ||
      segment === "." ||
      segment === ".." ||
      !/^[a-z0-9-]+$/.test(segment)
    ) {
      throw new SendRequestError(
        "Path traversal or malformed path was rejected",
        "policy",
        400,
      );
    }
  }
}

/**
 * @param {readonly string[]} path
 * @param {URLSearchParams} searchParams
 */
export function assertExactSendPath(path, searchParams) {
  validatePathSegments(path);
  if (
    path.length !== SEND_PATH.length ||
    path.some((segment, index) => segment !== SEND_PATH[index])
  ) {
    throw new SendRequestError(
      "Only POST a2a/send is allowed",
      "policy",
      405,
    );
  }
  if (Array.from(searchParams).length !== 0) {
    throw new SendRequestError(
      "Send query parameters are not allowed",
      "policy",
      400,
    );
  }
}

/** @param {unknown} packetId */
export function assertSendPacketId(packetId) {
  if (typeof packetId !== "string" || !UUID.test(packetId)) {
    throw new SendRequestError(
      "packet_id must be a UUID",
      "contract",
      400,
    );
  }
  return packetId;
}

/**
 * @param {string | undefined} configuredUrl
 * @param {string | undefined} configuredToken
 * @param {string | undefined} nodeEnv
 * @param {string | undefined} configuredReceiptDir
 */
export function resolveGatewayConfig(
  configuredUrl,
  configuredToken,
  nodeEnv,
  configuredReceiptDir,
) {
  const rawUrl = configuredUrl?.trim() ?? "";
  const token = configuredToken ?? "";
  const receiptDir = configuredReceiptDir?.trim() ?? "";
  if (!rawUrl || !token || !receiptDir) {
    throw new SendRequestError(
      "Mailbox send configuration is unavailable",
      "configuration",
      503,
    );
  }
  if (
    Buffer.byteLength(token, "utf8") > MAX_GATEWAY_TOKEN_BYTES ||
    !VISIBLE_ASCII_TOKEN.test(token) ||
    !isAbsolute(receiptDir)
  ) {
    throw new SendRequestError(
      "Mailbox send configuration is invalid",
      "configuration",
      503,
    );
  }

  let base;
  try {
    base = new URL(rawUrl);
  } catch {
    throw new SendRequestError(
      "Mailbox send configuration is invalid",
      "configuration",
      503,
    );
  }
  const protocolAllowed =
    base.protocol === "https:" ||
    (nodeEnv !== "production" && base.protocol === "http:");
  if (
    !protocolAllowed ||
    base.username ||
    base.password ||
    base.search ||
    base.hash ||
    (base.pathname !== "/" && base.pathname !== "")
  ) {
    throw new SendRequestError(
      "Mailbox send configuration is invalid",
      "configuration",
      503,
    );
  }
  return {
    target: new URL("/a2a/mailbox/send", base),
    token,
    receiptDir,
  };
}

/** @param {string} token */
function assertGatewayToken(token) {
  if (
    typeof token !== "string" ||
    Buffer.byteLength(token, "utf8") > MAX_GATEWAY_TOKEN_BYTES ||
    !VISIBLE_ASCII_TOKEN.test(token)
  ) {
    throw new SendRequestError(
      "Mailbox send configuration is invalid",
      "configuration",
      503,
    );
  }
}

/**
 * Read a web stream without ever accumulating more than the configured cap.
 *
 * @param {ReadableStream<Uint8Array> | null} stream
 * @param {number} maximumBytes
 * @param {() => SendRequestError} limitError
 * @param {AbortSignal | undefined} signal
 */
async function readBoundedStream(
  stream,
  maximumBytes,
  limitError,
  signal,
) {
  if (!stream) return new Uint8Array();
  const reader = stream.getReader();
  const chunks = [];
  let total = 0;
  const abortError = new Error("Mailbox send deadline exceeded");
  abortError.name = "AbortError";
  let rejectAbort;
  const aborted = new Promise((_resolve, reject) => {
    rejectAbort = reject;
  });
  const handleAbort = () => {
    void reader.cancel().catch(() => undefined);
    rejectAbort(abortError);
  };
  if (signal?.aborted) handleAbort();
  else signal?.addEventListener("abort", handleAbort, { once: true });
  try {
    while (true) {
      const { done, value } = await (signal
        ? Promise.race([reader.read(), aborted])
        : reader.read());
      if (done) break;
      const chunk =
        value instanceof Uint8Array ? value : new Uint8Array(value);
      total += chunk.byteLength;
      if (total > maximumBytes) {
        await reader.cancel().catch(() => undefined);
        throw limitError();
      }
      chunks.push(chunk);
    }
  } finally {
    signal?.removeEventListener("abort", handleAbort);
    try {
      reader.releaseLock();
    } catch {
      // Cancellation can settle the outstanding read after this frame.
    }
  }
  const bytes = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return bytes;
}

/** @param {ReadableStream<Uint8Array> | null} stream */
async function cancelStream(stream) {
  await stream?.cancel().catch(() => undefined);
}

/** @param {Request} request */
export async function readSendRequest(request) {
  const contentType = request.headers.get("Content-Type")?.trim() ?? "";
  if (!JSON_CONTENT_TYPE.test(contentType)) {
    await cancelStream(request.body);
    throw new SendRequestError(
      "Send body must use application/json",
      "contract",
      415,
    );
  }

  const declaredLength = request.headers.get("Content-Length");
  if (declaredLength !== null) {
    if (!/^\d+$/.test(declaredLength)) {
      await cancelStream(request.body);
      throw new SendRequestError(
        "Send content length is invalid",
        "contract",
        400,
      );
    }
    if (Number(declaredLength) > MAX_SEND_REQUEST_BYTES) {
      await cancelStream(request.body);
      throw new SendRequestError(
        "Send body exceeds the request limit",
        "contract",
        413,
      );
    }
  }

  const bytes = await readBoundedStream(
    request.body,
    MAX_SEND_REQUEST_BYTES,
    () =>
      new SendRequestError(
        "Send body exceeds the request limit",
        "contract",
        413,
      ),
  );
  let decoded;
  try {
    decoded = utf8Decoder.decode(bytes);
  } catch {
    throw new SendRequestError(
      "Send body must be valid UTF-8 JSON",
      "contract",
      400,
    );
  }

  let payload;
  try {
    payload = JSON.parse(decoded);
  } catch {
    throw new SendRequestError(
      "Send body must be valid JSON",
      "contract",
      400,
    );
  }
  if (!isRecord(payload)) {
    throw new SendRequestError(
      "Send body must be a JSON object",
      "contract",
      400,
    );
  }
  const keys = Object.keys(payload);
  const expected = new Set(["to", "body", "packet_id"]);
  if (keys.length !== expected.size || keys.some((key) => !expected.has(key))) {
    throw new SendRequestError(
      "Send body fields are invalid",
      "contract",
      400,
    );
  }

  const { to, body, packet_id: packetId } = payload;
  if (typeof to !== "string" || !SUBJECT_TOKEN.test(to)) {
    throw new SendRequestError(
      "Recipient must be an allowlisted subject token",
      "contract",
      400,
    );
  }
  if (
    typeof body !== "string" ||
    body.trim().length === 0 ||
    UNSAFE_CONTROL.test(body)
  ) {
    throw new SendRequestError(
      "Message body must be nonempty text",
      "contract",
      400,
    );
  }
  if (Buffer.byteLength(body, "utf8") > MAX_OPERATOR_MESSAGE_BYTES) {
    throw new SendRequestError(
      "Message body exceeds the byte limit",
      "contract",
      413,
    );
  }
  assertSendPacketId(packetId);
  return { to, body, packet_id: packetId };
}

/** @param {Response} response */
export async function readUpstreamJson(response, signal) {
  const contentType = response.headers.get("Content-Type")?.trim() ?? "";
  if (!contentType.toLowerCase().includes("application/json")) {
    await cancelStream(response.body);
    throw new SendRequestError(
      "Mailbox returned malformed storage evidence",
      "projection",
      502,
    );
  }
  const declaredLength = response.headers.get("Content-Length");
  if (
    declaredLength !== null &&
    (!/^\d+$/.test(declaredLength) ||
      Number(declaredLength) > MAX_UPSTREAM_RESPONSE_BYTES)
  ) {
    await cancelStream(response.body);
    throw new SendRequestError(
      "Mailbox returned oversized storage evidence",
      "projection",
      502,
    );
  }
  const bytes = await readBoundedStream(
    response.body,
    MAX_UPSTREAM_RESPONSE_BYTES,
    () =>
      new SendRequestError(
        "Mailbox returned oversized storage evidence",
        "projection",
        502,
      ),
    signal,
  );
  if (signal?.aborted) {
    const error = new Error("Mailbox send deadline exceeded");
    error.name = "AbortError";
    throw error;
  }
  let decoded;
  try {
    decoded = utf8Decoder.decode(bytes);
    return JSON.parse(decoded);
  } catch {
    throw new SendRequestError(
      "Mailbox returned malformed storage evidence",
      "projection",
      502,
    );
  }
}

/** @param {string} token */
export function gatewayHeaders(token) {
  assertGatewayToken(token);
  return new Headers({
    Accept: "application/json",
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  });
}

/** @param {{to: string, body: string, packet_id: string}} input */
export function gatewayPayload(input) {
  return {
    to: input.to,
    body: {
      kind: "a2a_operator_message.v1",
      packet_id: input.packet_id,
      text: input.body,
    },
  };
}

/**
 * @param {unknown} payload
 * @param {{to: string, packet_id: string}} input
 */
export function projectStoredSend(payload, input) {
  if (
    !isRecord(payload) ||
    payload.ok !== true ||
    payload.subject !== `dharma.a2a.${input.to}` ||
    !Number.isSafeInteger(payload.seq) ||
    payload.seq <= 0 ||
    typeof payload.from !== "string" ||
    !SUBJECT_TOKEN.test(payload.from)
  ) {
    throw new SendRequestError(
      "Mailbox returned malformed storage evidence",
      "projection",
      502,
    );
  }
  return {
    ok: true,
    subject: payload.subject,
    seq: payload.seq,
    from: payload.from,
    packet_id: input.packet_id,
    evidence_tier: "STORED",
  };
}
