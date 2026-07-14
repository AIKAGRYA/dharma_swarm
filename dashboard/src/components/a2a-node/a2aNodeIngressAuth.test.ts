import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import test from "node:test";

type IngressDecision =
  | { state: "allow" }
  | { state: "unauthorized" }
  | { state: "misconfigured" };

type IngressAuthSupport = {
  evaluateOperatorIngress: (options: {
    authorization: string | null;
    operatorUser: string | undefined;
    operatorPassword: string | undefined;
    nodeEnv: string | undefined;
  }) => IngressDecision;
};

type RouteHandler = (
  request: Request,
  context: { params: Promise<{ path: string[] }> },
) => Promise<Response>;

const authModuleUrl = new URL("./a2aNodeIngressAuth.mjs", import.meta.url);
const routeModuleUrl = new URL(
  "../../app/dashboard/a2a-node/api/[...path]/route.ts",
  import.meta.url,
);
const AUTH_ENV_KEYS = [
  "A2A_NODE_OPERATOR_USER",
  "A2A_NODE_OPERATOR_PASSWORD",
  "DASHBOARD_API_KEY",
  "DHARMA_API_INTERNAL_URL",
  "NODE_ENV",
] as const;

async function ingressAuth(): Promise<IngressAuthSupport> {
  const loaded = await import("./a2aNodeIngressAuth.mjs").catch(() => null);
  assert.ok(loaded, "operator ingress auth support must exist");
  return loaded as IngressAuthSupport;
}

async function proxyGet(): Promise<RouteHandler> {
  const loaded = await import(
    "../../app/dashboard/a2a-node/api/[...path]/route.ts"
  );
  return loaded.GET as RouteHandler;
}

async function proxyPost(): Promise<RouteHandler> {
  const loaded = await import(
    "../../app/dashboard/a2a-node/api/[...path]/route.ts"
  );
  return loaded.POST as RouteHandler;
}

function basic(user: string, password: string): string {
  return `Basic ${Buffer.from(`${user}:${password}`, "utf8").toString("base64")}`;
}

function routeContext() {
  return { params: Promise.resolve({ path: ["agents"] }) };
}

function captureEnv(): Record<string, string | undefined> {
  return Object.fromEntries(
    AUTH_ENV_KEYS.map((key) => [key, process.env[key]]),
  );
}

function setEnv(
  values: Partial<Record<(typeof AUTH_ENV_KEYS)[number], string | undefined>>,
): void {
  for (const key of AUTH_ENV_KEYS) {
    const value = values[key];
    if (value === undefined) {
      delete process.env[key];
    } else {
      process.env[key] = value;
    }
  }
}

function restoreEnv(snapshot: Record<string, string | undefined>): void {
  for (const key of AUTH_ENV_KEYS) {
    const value = snapshot[key];
    if (value === undefined) {
      delete process.env[key];
    } else {
      process.env[key] = value;
    }
  }
}

test("ingress policy is local-open only when both credentials are absent outside production", async () => {
  const { evaluateOperatorIngress } = await ingressAuth();
  const base = {
    authorization: null,
    operatorUser: undefined,
    operatorPassword: undefined,
  };
  assert.deepEqual(
    evaluateOperatorIngress({ ...base, nodeEnv: "development" }),
    { state: "allow" },
  );
  assert.deepEqual(
    evaluateOperatorIngress({ ...base, nodeEnv: "test" }),
    { state: "allow" },
  );
  assert.deepEqual(
    evaluateOperatorIngress({ ...base, nodeEnv: "production" }),
    { state: "misconfigured" },
  );
  assert.deepEqual(
    evaluateOperatorIngress({
      ...base,
      operatorUser: "operator",
      nodeEnv: "test",
    }),
    { state: "misconfigured" },
  );
});

test("Basic parser rejects malformed base64, UTF-8, and user-colon semantics", async () => {
  const { evaluateOperatorIngress } = await ingressAuth();
  const options = {
    operatorUser: "operator",
    operatorPassword: "pa:ssword",
    nodeEnv: "test",
  };
  assert.deepEqual(
    evaluateOperatorIngress({
      ...options,
      authorization: basic("operator", "pa:ssword"),
    }),
    { state: "allow" },
  );

  const invalidUtf8 = Buffer.from([
    ...Buffer.from("operator:", "utf8"),
    0xc3,
    0x28,
  ]).toString("base64");
  for (const authorization of [
    null,
    "Bearer not-basic",
    "Basic !!!=",
    `Basic ${Buffer.from("operator", "utf8").toString("base64")}`,
    `Basic ${Buffer.from(":pa:ssword", "utf8").toString("base64")}`,
    `Basic ${invalidUtf8}`,
    `Basic ${Buffer.from("operator:pa:ssword\0", "utf8").toString("base64")}`,
    `${basic("operator", "pa:ssword")} trailing`,
  ]) {
    assert.deepEqual(
      evaluateOperatorIngress({ ...options, authorization }),
      { state: "unauthorized" },
    );
  }
  assert.deepEqual(
    evaluateOperatorIngress({
      authorization: basic("operator", "password"),
      operatorUser: "bad:user",
      operatorPassword: "password",
      nodeEnv: "test",
    }),
    { state: "misconfigured" },
  );
});

test("credential comparison is timing-safe and never logs secrets", () => {
  assert.equal(existsSync(authModuleUrl), true, "auth support must exist");
  if (!existsSync(authModuleUrl)) return;
  const source = readFileSync(authModuleUrl, "utf8");
  const routeSource = readFileSync(routeModuleUrl, "utf8");
  assert.match(source, /timingSafeEqual/);
  assert.match(source, /createHash/);
  assert.match(source, /const userMatches = constantTimeEqual\(/);
  assert.match(source, /const passwordMatches = constantTimeEqual\(/);
  assert.match(source, /Number\(userMatches\) & Number\(passwordMatches\)/);
  assert.doesNotMatch(source, /operatorUser\s*===|operatorPassword\s*===/);
  assert.doesNotMatch(source + routeSource, /console\.(?:log|warn|error)/);
});

test("missing, wrong, or malformed Basic credentials cannot exercise the backend key", async () => {
  const GET = await proxyGet();
  const originalFetch = globalThis.fetch;
  const originalEnv = captureEnv();
  let upstreamCalls = 0;
  globalThis.fetch = (async () => {
    upstreamCalls += 1;
    return Response.json({ status: "ok", data: [] });
  }) as typeof fetch;
  setEnv({
    A2A_NODE_OPERATOR_USER: "phone-operator",
    A2A_NODE_OPERATOR_PASSWORD: "phone-password",
    DASHBOARD_API_KEY: "backend-server-key",
    NODE_ENV: "test",
  });

  try {
    for (const authorization of [
      undefined,
      basic("phone-operator", "wrong-password"),
      "Basic !!!=",
      `Basic ${Buffer.from("no-colon", "utf8").toString("base64")}`,
    ]) {
      const headers = new Headers();
      if (authorization) headers.set("Authorization", authorization);
      const response = await GET(
        new Request("http://dashboard/dashboard/a2a-node/api/agents", {
          headers,
        }),
        routeContext(),
      );
      assert.equal(response.status, 401);
      assert.equal(
        response.headers.get("WWW-Authenticate"),
        'Basic realm="A2A Operator Node", charset="UTF-8"',
      );
      assert.doesNotMatch(
        JSON.stringify(await response.json()),
        /phone-operator|phone-password|backend-server-key/,
      );
    }
    assert.equal(upstreamCalls, 0);
  } finally {
    globalThis.fetch = originalFetch;
    restoreEnv(originalEnv);
  }
});

test("valid Basic ingress is replaced by the server-side Bearer credential", async () => {
  const GET = await proxyGet();
  const originalFetch = globalThis.fetch;
  const originalEnv = captureEnv();
  const calls: Array<{ input: string; init?: RequestInit }> = [];
  globalThis.fetch = (async (
    input: RequestInfo | URL,
    init?: RequestInit,
  ) => {
    calls.push({ input: String(input), init });
    return Response.json({ status: "ok", data: [] });
  }) as typeof fetch;
  setEnv({
    A2A_NODE_OPERATOR_USER: "phone-operator",
    A2A_NODE_OPERATOR_PASSWORD: "phone-password",
    DASHBOARD_API_KEY: "backend-server-key",
    DHARMA_API_INTERNAL_URL: "http://backend.internal:8420",
    NODE_ENV: "production",
  });
  const inbound = basic("phone-operator", "phone-password");

  try {
    const response = await GET(
      new Request("http://dashboard/dashboard/a2a-node/api/agents", {
        headers: { Authorization: inbound },
      }),
      routeContext(),
    );
    assert.equal(response.status, 200);
    assert.equal(calls.length, 1);
    assert.equal(calls[0]?.input, "http://backend.internal:8420/api/agents");
    const outbound = new Headers(calls[0]?.init?.headers);
    assert.equal(
      outbound.get("Authorization"),
      "Bearer backend-server-key",
    );
    assert.notEqual(outbound.get("Authorization"), inbound);
    assert.doesNotMatch(
      JSON.stringify([...outbound.entries()]),
      /phone-operator|phone-password|Basic/,
    );
  } finally {
    globalThis.fetch = originalFetch;
    restoreEnv(originalEnv);
  }
});

test("non-GET requests pass ingress authentication before method rejection", async () => {
  const POST = await proxyPost();
  const originalFetch = globalThis.fetch;
  const originalEnv = captureEnv();
  let upstreamCalls = 0;
  globalThis.fetch = (async () => {
    upstreamCalls += 1;
    return Response.json({ status: "ok", data: [] });
  }) as typeof fetch;
  setEnv({
    A2A_NODE_OPERATOR_USER: "phone-operator",
    A2A_NODE_OPERATOR_PASSWORD: "phone-password",
    DASHBOARD_API_KEY: "backend-server-key",
    NODE_ENV: "test",
  });

  try {
    const unauthorized = await POST(
      new Request("http://dashboard/dashboard/a2a-node/api/agents", {
        method: "POST",
      }),
      routeContext(),
    );
    assert.equal(unauthorized.status, 401);
    assert.equal(
      unauthorized.headers.get("WWW-Authenticate"),
      'Basic realm="A2A Operator Node", charset="UTF-8"',
    );

    const authenticated = await POST(
      new Request("http://dashboard/dashboard/a2a-node/api/agents", {
        method: "POST",
        headers: {
          Authorization: basic("phone-operator", "phone-password"),
        },
      }),
      routeContext(),
    );
    assert.equal(authenticated.status, 405);
    assert.equal(upstreamCalls, 0);
  } finally {
    globalThis.fetch = originalFetch;
    restoreEnv(originalEnv);
  }
});

test("production missing or incomplete ingress credentials fails closed before fetch", async () => {
  const GET = await proxyGet();
  const originalFetch = globalThis.fetch;
  const originalEnv = captureEnv();
  let upstreamCalls = 0;
  globalThis.fetch = (async () => {
    upstreamCalls += 1;
    return Response.json({ status: "ok", data: [] });
  }) as typeof fetch;

  try {
    for (const credentials of [
      {},
      { A2A_NODE_OPERATOR_USER: "operator-only" },
      { A2A_NODE_OPERATOR_PASSWORD: "password-only" },
    ]) {
      setEnv({
        ...credentials,
        DASHBOARD_API_KEY: "backend-server-key",
        NODE_ENV: "production",
      });
      const response = await GET(
        new Request("http://dashboard/dashboard/a2a-node/api/agents"),
        routeContext(),
      );
      assert.equal(response.status, 503);
      assert.deepEqual(await response.json(), {
        error: {
          kind: "configuration",
          status: 503,
          message: "Operator ingress authentication is unavailable",
        },
      });
    }
    assert.equal(upstreamCalls, 0);
  } finally {
    globalThis.fetch = originalFetch;
    restoreEnv(originalEnv);
  }
});
