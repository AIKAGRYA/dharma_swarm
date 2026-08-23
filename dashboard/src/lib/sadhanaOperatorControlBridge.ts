import { constants } from "node:fs";
import { open } from "node:fs/promises";
import { isAbsolute, normalize } from "node:path";

import {
  parseRequestAccepted,
  SADHANA_CONTROL_CSRF,
  type RequestAccepted,
} from "./sadhanaOperatorControl";

export const CONTROL_INTERNAL_URL =
  "http://127.0.0.1:18421/v1/operator-control/requests";
export const CONTROL_BODY_LIMIT = 4096;
export const CONTROL_TIMEOUT_MS = 10_000;

interface BridgeEnvironment {
  SADHANA_CONTROL_INTERNAL_URL?: string;
  SADHANA_CONTROL_BEARER_FILE?: string;
  SADHANA_CONTROL_EXPECTED_ORIGIN?: string;
}

export interface BridgeDependencies {
  environment?: BridgeEnvironment;
  fetchImpl?: typeof fetch;
  readBearer?: (path: string) => Promise<string>;
  signal?: AbortSignal;
}

class BridgeRejected extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
  ) {
    super(code);
  }
}

function jsonResponse(status: number, body: Record<string, unknown>): Response {
  return Response.json(body, {
    status,
    headers: {
      "Cache-Control": "no-store",
      Pragma: "no-cache",
      "Referrer-Policy": "no-referrer",
      "X-Content-Type-Options": "nosniff",
    },
  });
}

function reject(status: number, errorCode: string): Response {
  return jsonResponse(status, {
    status: "request_rejected",
    error_code: errorCode,
  });
}

function oneHeader(headers: Headers, name: string): string | null {
  const value = headers.get(name);
  if (value === null || value.includes(",")) return null;
  return value;
}

function exactHttpsOrigin(value: string | undefined): string {
  if (!value || /[^\x21-\x7e]/.test(value)) {
    throw new BridgeRejected(503, "control_bridge_unavailable");
  }
  try {
    const parsed = new URL(value);
    if (
      parsed.protocol !== "https:" ||
      parsed.origin !== value ||
      parsed.username ||
      parsed.password
    ) {
      throw new Error("invalid origin");
    }
  } catch {
    throw new BridgeRejected(503, "control_bridge_unavailable");
  }
  return value;
}

function exactCredentialPath(value: string | undefined): string {
  if (
    !value ||
    !isAbsolute(value) ||
    value.includes("\0") ||
    value.split(/[\\/]/).includes("..") ||
    normalize(value) !== value
  ) {
    throw new BridgeRejected(503, "control_bridge_unavailable");
  }
  return value;
}

export async function readBearerCredential(path: string): Promise<string> {
  if (!Number.isInteger(constants.O_NOFOLLOW) || constants.O_NOFOLLOW === 0) {
    throw new BridgeRejected(503, "control_bridge_unavailable");
  }
  let handle;
  try {
    handle = await open(
      exactCredentialPath(path),
      constants.O_RDONLY | constants.O_NOFOLLOW,
    );
    const before = await handle.stat({ bigint: true });
    if (
      !before.isFile() ||
      before.nlink !== BigInt(1) ||
      before.size < BigInt(32) ||
      before.size > BigInt(512)
    ) {
      throw new BridgeRejected(503, "control_bridge_unavailable");
    }
    const payload = await handle.readFile();
    const after = await handle.stat({ bigint: true });
    if (
      before.dev !== after.dev ||
      before.ino !== after.ino ||
      before.mode !== after.mode ||
      before.nlink !== after.nlink ||
      before.size !== after.size ||
      before.mtimeNs !== after.mtimeNs ||
      before.ctimeNs !== after.ctimeNs ||
      BigInt(payload.byteLength) !== before.size ||
      [...payload].some((byte) => byte < 0x21 || byte > 0x7e)
    ) {
      throw new BridgeRejected(503, "control_bridge_unavailable");
    }
    return payload.toString("ascii");
  } catch (error) {
    if (error instanceof BridgeRejected) throw error;
    throw new BridgeRejected(503, "control_bridge_unavailable");
  } finally {
    await handle?.close().catch(() => undefined);
  }
}

async function boundedBody(
  body: ReadableStream<Uint8Array> | null,
  maximum: number,
): Promise<Uint8Array> {
  if (!body) throw new BridgeRejected(400, "request_body_empty");
  const reader = body.getReader();
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > maximum) {
        throw new BridgeRejected(413, "request_body_too_large");
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  if (size === 0) throw new BridgeRejected(400, "request_body_empty");
  const joined = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) {
    joined.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return joined;
}

function validateRequestHeaders(request: Request, expectedOrigin: string): {
  login: string;
  origin: string;
} {
  const login = oneHeader(request.headers, "Tailscale-User-Login");
  const origin = oneHeader(request.headers, "Origin");
  const csrf = oneHeader(request.headers, "X-Sadhana-CSRF");
  const contentType = oneHeader(request.headers, "Content-Type");
  if (!login) throw new BridgeRejected(403, "tailscale_identity_required");
  if (!/^[A-Za-z0-9][A-Za-z0-9@._+:-]{0,253}$/.test(login)) {
    throw new BridgeRejected(403, "tailscale_identity_invalid");
  }
  if (origin !== expectedOrigin) throw new BridgeRejected(403, "origin_mismatch");
  if (csrf !== SADHANA_CONTROL_CSRF) {
    throw new BridgeRejected(403, "csrf_required");
  }
  if (contentType !== "application/json") {
    throw new BridgeRejected(415, "content_type_required");
  }
  const contentLength = request.headers.get("Content-Length");
  if (
    contentLength !== null &&
    (!/^\d+$/.test(contentLength) || Number(contentLength) > CONTROL_BODY_LIMIT)
  ) {
    throw new BridgeRejected(413, "request_body_too_large");
  }
  return { login, origin };
}

function safeAccepted(accepted: RequestAccepted): Response {
  return jsonResponse(202, { ...accepted });
}

function safeUpstreamRejection(status: number): Response {
  if (status === 409) return reject(409, "idempotency_conflict");
  if (status === 501) {
    return jsonResponse(501, {
      status: "unsupported_action",
      error_code: "proposal_effect_warrant_contract_unavailable",
      request_accepted: false,
      decision_applied: false,
      effect_executed: false,
    });
  }
  return reject(status >= 400 && status <= 599 ? status : 502, "control_upstream_rejected");
}

export async function handleOperatorControlBridge(
  request: Request,
  dependencies: BridgeDependencies = {},
): Promise<Response> {
  if (request.method !== "POST") return reject(405, "method_not_allowed");
  const environment = dependencies.environment ?? process.env;
  try {
    if (environment.SADHANA_CONTROL_INTERNAL_URL !== CONTROL_INTERNAL_URL) {
      throw new BridgeRejected(503, "control_bridge_unavailable");
    }
    const expectedOrigin = exactHttpsOrigin(
      environment.SADHANA_CONTROL_EXPECTED_ORIGIN,
    );
    const bearerPath = exactCredentialPath(
      environment.SADHANA_CONTROL_BEARER_FILE,
    );
    const { login, origin } = validateRequestHeaders(request, expectedOrigin);
    const body = await boundedBody(request.body, CONTROL_BODY_LIMIT);
    const bodyBuffer = body.buffer.slice(
      body.byteOffset,
      body.byteOffset + body.byteLength,
    ) as ArrayBuffer;
    const bearer = await (dependencies.readBearer ?? readBearerCredential)(bearerPath);
    if (!/^[\x21-\x7e]{32,512}$/.test(bearer)) {
      throw new BridgeRejected(503, "control_bridge_unavailable");
    }
    const upstream = await (dependencies.fetchImpl ?? fetch)(CONTROL_INTERNAL_URL, {
      method: "POST",
      cache: "no-store",
      redirect: "error",
      signal: dependencies.signal ?? AbortSignal.timeout(CONTROL_TIMEOUT_MS),
      headers: {
        Authorization: `Bearer ${bearer}`,
        "Content-Type": "application/json",
        Origin: origin,
        "Tailscale-User-Login": login,
        "X-Sadhana-CSRF": SADHANA_CONTROL_CSRF,
      },
      body: bodyBuffer,
    });
    if (upstream.status !== 202) {
      await upstream.body?.cancel().catch(() => undefined);
      return safeUpstreamRejection(upstream.status);
    }
    const raw = await boundedBody(upstream.body, CONTROL_BODY_LIMIT);
    let value: unknown;
    try {
      value = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(raw));
    } catch {
      throw new BridgeRejected(502, "control_upstream_response_invalid");
    }
    const accepted = parseRequestAccepted(value);
    if (!accepted) {
      throw new BridgeRejected(502, "control_upstream_response_invalid");
    }
    return safeAccepted(accepted);
  } catch (error) {
    if (error instanceof BridgeRejected) return reject(error.status, error.code);
    return reject(503, "control_bridge_unavailable");
  }
}
