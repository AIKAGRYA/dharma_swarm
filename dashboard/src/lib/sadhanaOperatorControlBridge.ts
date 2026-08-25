import { createHash } from "node:crypto";
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
export const ACCOUNT_UI_CONFIRMATION_INTERNAL_URL =
  "http://127.0.0.1:18421/v1/account-ui-confirmations";
export const ACCOUNT_UI_CONFIRMATION_HTTP_BINDING_SHA256 =
  "60996ccfa8de0db715d26ecf062d13604e09ab019c51d9047cb250e39652dad1";
export const ACCOUNT_UI_CONFIRMATION_HTTP_BINDING_CANONICAL =
  "schema=dharma.sadhana.account_ui_confirmation_http_binding.v1;method=POST;" +
  "browser_route=/dharma-internal/account-ui-confirmation;internal_url=" +
  "http://127.0.0.1:18421/v1/account-ui-confirmations;headers=authorization," +
  "content-type,origin,tailscale-user-login,x-sadhana-csrf,x-sadhana-release-sha;" +
  "request_schema=dharma.sadhana.authenticated_account_ui_confirmation_request.v1;" +
  "request_fields=campaign_id,client_request_id,coarse_pointer_reported," +
  "dashboard_rendered_reported,document_width_css_px_reported,expires_at," +
  "explicit_confirmation_gesture_reported,issued_at,schema_version," +
  "touch_capability_reported,trusted_browser_event_reported," +
  "viewport_width_css_px_reported,visual_viewport_width_css_px_reported;" +
  "response_fields=account_authenticated,authority_applied,candidate_recorded," +
  "dispatch_authorized,human_identity_attested,physical_device_attested,replayed," +
  "status;http_202=CandidateRecorded<NoAuthority,NoDispatch>;" +
  "candidate=fixed-path-o_excl;mac=derived-domain-separated-hmac-sha256";
if (
  createHash("sha256")
    .update(ACCOUNT_UI_CONFIRMATION_HTTP_BINDING_CANONICAL, "utf8")
    .digest("hex") !== ACCOUNT_UI_CONFIRMATION_HTTP_BINDING_SHA256
) {
  throw new Error("account UI confirmation HTTP binding digest differs");
}
export const CONTROL_BODY_LIMIT = 4096;
export const CONTROL_TIMEOUT_MS = 10_000;

interface BridgeEnvironment {
  SADHANA_CONTROL_INTERNAL_URL?: string;
  SADHANA_CONTROL_BEARER_FILE?: string;
  SADHANA_CONTROL_EXPECTED_ORIGIN?: string;
  SADHANA_ACCOUNT_UI_CONFIRMATION_INTERNAL_URL?: string;
  SADHANA_RELEASE_SHA?: string;
  SADHANA_ACCOUNT_UI_CONFIRMATION_HTTP_BINDING_SHA256?: string;
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

function exactReleaseSha(value: string | undefined): string {
  if (!value || !/^[0-9a-f]{40}$/.test(value)) {
    throw new BridgeRejected(503, "control_bridge_unavailable");
  }
  return value;
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

export async function handleAccountUiConfirmationBridge(
  request: Request,
  dependencies: BridgeDependencies = {},
): Promise<Response> {
  if (request.method !== "POST") return reject(405, "method_not_allowed");
  const environment = dependencies.environment ?? process.env;
  try {
    if (
      environment.SADHANA_ACCOUNT_UI_CONFIRMATION_INTERNAL_URL !==
        ACCOUNT_UI_CONFIRMATION_INTERNAL_URL ||
      environment.SADHANA_ACCOUNT_UI_CONFIRMATION_HTTP_BINDING_SHA256 !==
        ACCOUNT_UI_CONFIRMATION_HTTP_BINDING_SHA256
    ) {
      throw new BridgeRejected(503, "control_bridge_unavailable");
    }
    const expectedOrigin = exactHttpsOrigin(
      environment.SADHANA_CONTROL_EXPECTED_ORIGIN,
    );
    const releaseSha = exactReleaseSha(environment.SADHANA_RELEASE_SHA);
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
    const upstream = await (dependencies.fetchImpl ?? fetch)(
      ACCOUNT_UI_CONFIRMATION_INTERNAL_URL,
      {
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
          "X-Sadhana-Release-SHA": releaseSha,
        },
        body: bodyBuffer,
      },
    );
    if (upstream.status !== 202) {
      await upstream.body?.cancel().catch(() => undefined);
      return reject(
        upstream.status >= 400 && upstream.status <= 599
          ? upstream.status
          : 502,
        "account_ui_confirmation_upstream_rejected",
      );
    }
    const raw = await boundedBody(upstream.body, CONTROL_BODY_LIMIT);
    let value: unknown;
    try {
      value = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(raw));
    } catch {
      throw new BridgeRejected(502, "account_ui_confirmation_response_invalid");
    }
    if (
      typeof value !== "object" ||
      value === null ||
      Array.isArray(value) ||
      Object.keys(value as Record<string, unknown>).sort().join("|") !==
        [
          "account_authenticated",
          "authority_applied",
          "candidate_recorded",
          "dispatch_authorized",
          "human_identity_attested",
          "physical_device_attested",
          "replayed",
          "status",
        ]
          .sort()
          .join("|") ||
      (value as Record<string, unknown>).status !==
        "account_ui_confirmation_accepted" ||
      typeof (value as Record<string, unknown>).replayed !== "boolean" ||
      (value as Record<string, unknown>).account_authenticated !== true ||
      (value as Record<string, unknown>).candidate_recorded !== true ||
      (value as Record<string, unknown>).authority_applied !== false ||
      (value as Record<string, unknown>).dispatch_authorized !== false ||
      (value as Record<string, unknown>).physical_device_attested !== false ||
      (value as Record<string, unknown>).human_identity_attested !== false
    ) {
      throw new BridgeRejected(502, "account_ui_confirmation_response_invalid");
    }
    return jsonResponse(202, value as Record<string, unknown>);
  } catch (error) {
    if (error instanceof BridgeRejected) return reject(error.status, error.code);
    return reject(503, "control_bridge_unavailable");
  }
}
