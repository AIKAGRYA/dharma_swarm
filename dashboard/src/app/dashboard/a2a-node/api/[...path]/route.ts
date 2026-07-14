import {
  buildUpstreamHeaders,
  classifyUpstreamStatus,
  ProxyRequestError,
  resolveProxyTarget,
} from "../../../../../components/a2a-node/a2aNodeProxy.mjs";
import { evaluateOperatorIngress } from "../../../../../components/a2a-node/a2aNodeIngressAuth.mjs";

const DEFAULT_BACKEND_BASE_URL = "http://127.0.0.1:8420";
const BASIC_CHALLENGE =
  'Basic realm="A2A Operator Node", charset="UTF-8"';

interface ProxyRouteContext {
  params: Promise<{ path: string[] }>;
}

function errorResponse(
  kind:
    | "policy"
    | "configuration"
    | "auth"
    | "contract"
    | "throttle"
    | "upstream"
    | "projection",
  message: string,
  status: number,
  additionalHeaders: Record<string, string> = {},
): Response {
  return Response.json(
    { error: { kind, status, message } },
    {
      status,
      headers: {
        "Cache-Control": "no-store",
        ...additionalHeaders,
      },
    },
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function hasApplicationError(value: unknown): boolean {
  if (value === null || value === undefined) return false;
  if (typeof value === "string") return value.trim().length > 0;
  if (Array.isArray(value)) return value.length > 0;
  if (isRecord(value)) return Object.keys(value).length > 0;
  return true;
}

const SAFE_SOURCE_PATTERN = /^[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,79}$/;

function sanitizeSourceErrors(
  value: unknown,
): Array<{ source: string }> | null {
  if (!Array.isArray(value)) {
    return null;
  }
  const sanitized: Array<{ source: string }> = [];
  for (const entry of value) {
    if (
      !isRecord(entry) ||
      typeof entry.source !== "string" ||
      !entry.source.trim() ||
      typeof entry.error !== "string" ||
      !entry.error.trim()
    ) {
      return null;
    }
    const source = entry.source.trim();
    sanitized.push({
      source: SAFE_SOURCE_PATTERN.test(source) ? source : "unknown_source",
    });
  }
  return sanitized;
}

function safeUpstreamMessage(
  kind: ReturnType<typeof classifyUpstreamStatus>,
  status: number,
): string {
  switch (kind) {
    case "auth":
      return "Backend authentication rejected this read";
    case "throttle":
      return "Backend throttled this read";
    case "upstream":
      return "Backend read was unavailable";
    case "contract":
      return status === 404
        ? "Backend read contract was not found"
        : "Backend read contract was rejected";
  }
}

function operatorIngressError(request: Request): Response | null {
  const ingress = evaluateOperatorIngress({
    authorization: request.headers.get("Authorization"),
    operatorUser: process.env.A2A_NODE_OPERATOR_USER,
    operatorPassword: process.env.A2A_NODE_OPERATOR_PASSWORD,
    nodeEnv: process.env.NODE_ENV,
  });
  if (ingress.state === "misconfigured") {
    return errorResponse(
      "configuration",
      "Operator ingress authentication is unavailable",
      503,
    );
  }
  if (ingress.state === "unauthorized") {
    return errorResponse(
      "auth",
      "Operator authentication required",
      401,
      { "WWW-Authenticate": BASIC_CHALLENGE },
    );
  }
  return null;
}

function rejectMethod(request: Request): Response {
  return (
    operatorIngressError(request) ??
    errorResponse("policy", "Only GET is allowed", 405)
  );
}

export async function GET(
  request: Request,
  context: ProxyRouteContext,
): Promise<Response> {
  const ingressError = operatorIngressError(request);
  if (ingressError) {
    return ingressError;
  }

  let target: URL;
  try {
    const { path } = await context.params;
    const baseUrl =
      process.env.DHARMA_API_INTERNAL_URL?.trim() ||
      DEFAULT_BACKEND_BASE_URL;
    target = resolveProxyTarget(
      path,
      new URL(request.url).searchParams,
      baseUrl,
    );
  } catch (error) {
    if (error instanceof ProxyRequestError) {
      return errorResponse(error.kind, error.message, error.status);
    }
    return errorResponse(
      "configuration",
      "Proxy request configuration is invalid",
      500,
    );
  }

  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method: "GET",
      headers: buildUpstreamHeaders(process.env.DASHBOARD_API_KEY),
      cache: "no-store",
      redirect: "manual",
    });
  } catch {
    return errorResponse(
      "upstream",
      "Backend read was unreachable",
      502,
    );
  }

  if (!upstream.ok) {
    const kind = classifyUpstreamStatus(upstream.status);
    return errorResponse(
      kind,
      safeUpstreamMessage(kind, upstream.status),
      upstream.status,
    );
  }
  const contentType = upstream.headers.get("Content-Type") ?? "";
  if (!contentType.toLowerCase().includes("application/json")) {
    return errorResponse(
      "projection",
      "Backend read returned malformed JSON evidence",
      502,
    );
  }

  let payload: unknown;
  try {
    payload = await upstream.json();
  } catch {
    return errorResponse(
      "projection",
      "Backend read returned malformed JSON evidence",
      502,
    );
  }
  if (
    isRecord(payload) &&
    (("status" in payload && payload.status !== "ok") ||
      ("error" in payload && hasApplicationError(payload.error)))
  ) {
    return errorResponse(
      "contract",
      "Backend returned an application error envelope",
      502,
    );
  }
  let safePayload = payload;
  if (isRecord(payload) && "source_errors" in payload) {
    if (!("data" in payload)) {
      return errorResponse(
        "projection",
        "Backend read returned malformed source evidence",
        502,
      );
    }
    const sourceErrors = sanitizeSourceErrors(payload.source_errors);
    if (sourceErrors === null) {
      return errorResponse(
        "projection",
        "Backend read returned malformed source evidence",
        502,
      );
    }
    safePayload = {
      ...(typeof payload.schema_version === "string"
        ? { schema_version: payload.schema_version }
        : {}),
      ...(typeof payload.generated_at === "string"
        ? { generated_at: payload.generated_at }
        : {}),
      source_errors: sourceErrors,
      data: payload.data,
    };
  } else if (isRecord(payload) && "status" in payload) {
    if (!("data" in payload)) {
      return errorResponse(
        "projection",
        "Backend read returned malformed envelope evidence",
        502,
      );
    }
    safePayload = { status: "ok", data: payload.data };
  }
  return Response.json(safePayload, {
    status: 200,
    headers: { "Cache-Control": "no-store" },
  });
}

export const HEAD = rejectMethod;
export const POST = rejectMethod;
export const PUT = rejectMethod;
export const PATCH = rejectMethod;
export const DELETE = rejectMethod;
export const OPTIONS = rejectMethod;
