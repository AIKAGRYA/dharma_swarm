const PROXY_ENDPOINTS = Object.freeze({
  "fleet/nodes": {
    upstreamPath: "/api/fleet/nodes",
    query: null,
  },
  agents: {
    upstreamPath: "/api/agents",
    query: null,
  },
  tasks: {
    upstreamPath: "/api/commands/tasks",
    query: null,
  },
  traces: {
    upstreamPath: "/api/commands/traces",
    query: Object.freeze({ limit: "48" }),
  },
  "a2a/cards": {
    upstreamPath: "/api/control-surface/a2a/cards",
    query: Object.freeze({ limit: "48" }),
  },
});

export class ProxyRequestError extends Error {
  /**
   * @param {string} message
   * @param {"policy" | "configuration"} kind
   * @param {number} status
   */
  constructor(message, kind, status) {
    super(message);
    this.name = "ProxyRequestError";
    this.kind = kind;
    this.status = status;
  }
}

/**
 * @param {readonly string[]} path
 * @returns {string}
 */
function allowlistedPath(path) {
  if (!Array.isArray(path) || path.length === 0) {
    throw new ProxyRequestError(
      "Proxy path is not allowlisted",
      "policy",
      404,
    );
  }
  for (const segment of path) {
    if (
      typeof segment !== "string" ||
      segment === "." ||
      segment === ".." ||
      !/^[a-z0-9-]+$/.test(segment)
    ) {
      throw new ProxyRequestError(
        "Path traversal or malformed path was rejected",
        "policy",
        400,
      );
    }
  }
  return path.join("/");
}

/**
 * @param {URLSearchParams} actual
 * @param {Readonly<Record<string, string>> | null} expected
 */
function assertExactQuery(actual, expected) {
  const entries = Array.from(actual.entries());
  const expectedEntries = expected ? Object.entries(expected) : [];
  if (
    entries.length !== expectedEntries.length ||
    expectedEntries.some(
      ([key, value]) =>
        entries.filter(
          ([candidateKey, candidateValue]) =>
            candidateKey === key && candidateValue === value,
        ).length !== 1,
    )
  ) {
    throw new ProxyRequestError(
      "Proxy query is not allowlisted",
      "policy",
      400,
    );
  }
}

/**
 * @param {string} value
 * @returns {URL}
 */
function parseBackendBase(value) {
  let base;
  try {
    base = new URL(value);
  } catch {
    throw new ProxyRequestError(
      "Backend base URL is invalid",
      "configuration",
      500,
    );
  }
  if (
    !["http:", "https:"].includes(base.protocol) ||
    base.username ||
    base.password ||
    base.search ||
    base.hash ||
    (base.pathname !== "/" && base.pathname !== "")
  ) {
    throw new ProxyRequestError(
      "Backend base URL must be an HTTP(S) origin",
      "configuration",
      500,
    );
  }
  return base;
}

/**
 * Resolve one exact browser route to one exact backend read route.
 *
 * @param {readonly string[]} path
 * @param {URLSearchParams} searchParams
 * @param {string} backendBaseUrl
 * @returns {URL}
 */
export function resolveProxyTarget(path, searchParams, backendBaseUrl) {
  const key = allowlistedPath(path);
  const endpoint = PROXY_ENDPOINTS[key];
  if (!endpoint) {
    throw new ProxyRequestError(
      "Proxy path is not allowlisted",
      "policy",
      404,
    );
  }
  assertExactQuery(searchParams, endpoint.query);

  const target = new URL(endpoint.upstreamPath, parseBackendBase(backendBaseUrl));
  for (const [name, value] of Object.entries(endpoint.query ?? {})) {
    target.searchParams.set(name, value);
  }
  return target;
}

/**
 * @param {string | undefined} apiKey
 * @returns {Headers}
 */
export function buildUpstreamHeaders(apiKey) {
  const headers = new Headers({ Accept: "application/json" });
  const key = apiKey?.trim();
  if (key) {
    headers.set("Authorization", `Bearer ${key}`);
  }
  return headers;
}

/**
 * @param {number} status
 * @returns {"auth" | "contract" | "throttle" | "upstream"}
 */
export function classifyUpstreamStatus(status) {
  if (status === 401 || status === 403) {
    return "auth";
  }
  if (status === 429) {
    return "throttle";
  }
  if (status >= 500 && status <= 599) {
    return "upstream";
  }
  return "contract";
}
