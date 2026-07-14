/** @typedef {"transport" | "policy" | "configuration" | "auth" | "contract" | "throttle" | "upstream" | "projection"} NodeReadErrorKind */

export class NodeReadError extends Error {
  /**
   * @param {string} message
   * @param {NodeReadErrorKind} kind
   * @param {number | null} [status]
   */
  constructor(message, kind, status = null) {
    super(message);
    this.name = "NodeReadError";
    this.kind = kind;
    this.status = status;
  }
}

/** @param {unknown} value */
function isRecord(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

/** @param {unknown} value */
function hasApplicationError(value) {
  if (value === null || value === undefined) return false;
  if (typeof value === "string") return value.trim().length > 0;
  if (Array.isArray(value)) return value.length > 0;
  if (isRecord(value)) return Object.keys(value).length > 0;
  return true;
}

/**
 * @param {number} status
 * @returns {NodeReadErrorKind}
 */
function statusErrorKind(status) {
  if (status === 401 || status === 403) return "auth";
  if (status === 429) return "throttle";
  if (status >= 500) return "upstream";
  return "contract";
}

/**
 * @param {unknown} value
 * @param {number} status
 * @returns {NodeReadErrorKind}
 */
function routeErrorKind(value, status) {
  if (
    value === "policy" ||
    value === "configuration" ||
    value === "auth" ||
    value === "contract" ||
    value === "throttle" ||
    value === "projection" ||
    value === "upstream"
  ) {
    return value;
  }
  return statusErrorKind(status);
}

/**
 * @param {NodeReadErrorKind} kind
 * @param {number} status
 */
function safeErrorMessage(kind, status) {
  switch (kind) {
    case "auth":
      return `Backend authentication blocked this read (${status})`;
    case "throttle":
      return `Backend throttled this read (${status})`;
    case "contract":
      return `Backend contract rejected this read (${status})`;
    case "projection":
      return "Backend returned malformed projection evidence";
    case "policy":
      return `Operator proxy policy rejected this read (${status})`;
    case "configuration":
      return "Operator proxy configuration blocked this read";
    case "transport":
    case "upstream":
      return `Backend read was unreachable (${status})`;
  }
}

/** @param {Response} response */
async function readRouteError(response) {
  let payload;
  try {
    payload = await response.json();
  } catch {
    const kind = statusErrorKind(response.status);
    return new NodeReadError(
      safeErrorMessage(kind, response.status),
      kind,
      response.status,
    );
  }
  const detail = isRecord(payload) && isRecord(payload.error)
    ? payload.error
    : null;
  const kind = routeErrorKind(detail?.kind, response.status);
  return new NodeReadError(
    safeErrorMessage(kind, response.status),
    kind,
    response.status,
  );
}

/**
 * @param {{url: string, fetcher?: typeof fetch}} options
 * @returns {Promise<unknown>}
 */
export async function fetchNodeJson(options) {
  const fetcher = options.fetcher ?? globalThis.fetch;
  let response;
  try {
    response = await fetcher(options.url, {
      method: "GET",
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
  } catch {
    throw new NodeReadError(
      "Operator proxy could not be reached",
      "transport",
    );
  }
  if (!response.ok) {
    throw await readRouteError(response);
  }
  let payload;
  try {
    payload = await response.json();
  } catch {
    throw new NodeReadError(
      "Operator proxy returned malformed JSON evidence",
      "projection",
      response.status,
    );
  }
  if (
    isRecord(payload) &&
    (("status" in payload && payload.status !== "ok") ||
      ("error" in payload && hasApplicationError(payload.error)))
  ) {
    throw new NodeReadError(
      "Backend returned an application error envelope",
      "contract",
      response.status,
    );
  }
  return payload;
}

/**
 * @param {unknown} error
 * @returns {{kind: NodeReadErrorKind, truth: "unknown" | "blocked" | "unreachable"}}
 */
export function classifyNodeReadError(error) {
  if (!(error instanceof NodeReadError)) {
    return { kind: "projection", truth: "unknown" };
  }
  return {
    kind: error.kind,
    truth:
      error.kind === "transport" || error.kind === "upstream"
        ? "unreachable"
        : error.kind === "auth" || error.kind === "throttle"
          ? "blocked"
          : "unknown",
  };
}
