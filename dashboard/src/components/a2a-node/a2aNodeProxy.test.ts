import assert from "node:assert/strict";
import test from "node:test";

type ProxySupport = {
  resolveProxyTarget: (
    path: readonly string[],
    searchParams: URLSearchParams,
    backendBaseUrl: string,
  ) => URL;
  buildUpstreamHeaders: (apiKey: string | undefined) => Headers;
};

type RouteHandler = (
  request: Request,
  context: { params: Promise<{ path: string[] }> },
) => Promise<Response>;

type NodeReadErrorClassification = {
  kind: string;
  truth: "unknown" | "blocked" | "unreachable";
};

async function requireProxySupport(): Promise<ProxySupport> {
  const loaded = await import("./a2aNodeProxy.mjs").catch(() => null);
  assert.ok(loaded, "a2aNodeProxy support module must exist");
  return loaded as ProxySupport;
}

async function requireProxyRoute(): Promise<{
  GET: RouteHandler;
  POST: RouteHandler;
}> {
  const loaded = await import(
    "../../app/dashboard/a2a-node/api/[...path]/route.ts"
  ).catch(() => null);
  assert.ok(loaded, "operator-node proxy route must exist");
  return loaded as { GET: RouteHandler; POST: RouteHandler };
}

async function requireReadModel() {
  const loaded = await import("./a2aNodeReadModel.ts").catch(() => null);
  assert.ok(loaded, "operator-node read model must exist");
  return loaded as {
    fetchNodeAgents: (options: {
      url: string;
      fetcher: typeof fetch;
    }) => Promise<unknown[]>;
    classifyNodeReadError: (error: unknown) => NodeReadErrorClassification;
  };
}

test("proxy allowlist constructs only exact backend read URLs", async () => {
  const { resolveProxyTarget } = await requireProxySupport();
  const base = "http://127.0.0.1:8420";
  const cases = [
    { path: ["fleet", "nodes"], query: "", expected: "/api/fleet/nodes" },
    { path: ["agents"], query: "", expected: "/api/agents" },
    { path: ["tasks"], query: "", expected: "/api/commands/tasks" },
    {
      path: ["traces"],
      query: "limit=48",
      expected: "/api/commands/traces?limit=48",
    },
    {
      path: ["a2a", "cards"],
      query: "limit=48",
      expected: "/api/control-surface/a2a/cards?limit=48",
    },
  ];

  for (const item of cases) {
    const target = resolveProxyTarget(
      item.path,
      new URLSearchParams(item.query),
      base,
    );
    assert.equal(target.toString(), `${base}${item.expected}`);
  }

  for (const [path, query] of [
    [["unknown"], ""],
    [["..", "agents"], ""],
    [["%2e%2e", "agents"], ""],
    [["agents"], "extra=1"],
    [["traces"], "limit=47"],
    [["traces"], "limit=48&limit=48"],
    [["a2a", "cards"], "target=agni&limit=48"],
  ] as const) {
    assert.throws(
      () =>
        resolveProxyTarget(path, new URLSearchParams(query), base),
      /allowlist|traversal|query/i,
    );
  }
  assert.throws(
    () =>
      resolveProxyTarget(
        ["agents"],
        new URLSearchParams(),
        "ftp://backend.example",
      ),
    /backend base/i,
  );
});

test("upstream auth header is server-configured and optional in dev", async () => {
  const { buildUpstreamHeaders } = await requireProxySupport();
  const secured = buildUpstreamHeaders("  server-secret  ");
  assert.equal(secured.get("Authorization"), "Bearer server-secret");
  assert.equal(secured.get("Accept"), "application/json");

  const development = buildUpstreamHeaders(undefined);
  assert.equal(development.get("Authorization"), null);
  assert.equal(development.get("Accept"), "application/json");
});

test("browser read failures distinguish upstream from invalid projection", async () => {
  const { fetchNodeAgents, classifyNodeReadError } = await requireReadModel();
  const upstreamFetch = (async () =>
    Response.json(
      {
        error: {
          kind: "upstream",
          message: "Backend read was unreachable",
        },
      },
      { status: 502 },
    )) as typeof fetch;
  await assert.rejects(
    () =>
      fetchNodeAgents({
        url: "/dashboard/a2a-node/api/agents",
        fetcher: upstreamFetch,
      }),
    (error) => {
      assert.deepEqual(classifyNodeReadError(error), {
        kind: "upstream",
        truth: "unreachable",
      });
      return true;
    },
  );

  const malformedFetch = (async () =>
    Response.json({ status: "ok", data: { agents: [] } })) as typeof fetch;
  await assert.rejects(
    () =>
      fetchNodeAgents({
        url: "/dashboard/a2a-node/api/agents",
        fetcher: malformedFetch,
      }),
    (error) => {
      assert.deepEqual(classifyNodeReadError(error), {
        kind: "projection",
        truth: "unknown",
      });
      return true;
    },
  );
});

test("browser status categories map only connectivity and 5xx to unreachable", async () => {
  const { fetchNodeAgents, classifyNodeReadError } = await requireReadModel();
  const cases = [
    { status: 401, kind: "auth", truth: "blocked" },
    { status: 403, kind: "auth", truth: "blocked" },
    { status: 404, kind: "contract", truth: "unknown" },
    { status: 429, kind: "throttle", truth: "blocked" },
    { status: 503, kind: "upstream", truth: "unreachable" },
  ] as const;

  for (const item of cases) {
    const fetcher = (async () =>
      Response.json(
        {
          error: {
            kind: item.kind,
            status: item.status,
            message: "PRIVATE BACKEND BODY MUST NOT SURVIVE",
          },
        },
        { status: item.status },
      )) as typeof fetch;
    await assert.rejects(
      () =>
        fetchNodeAgents({
          url: "/dashboard/a2a-node/api/agents",
          fetcher,
        }),
      (error) => {
        assert.deepEqual(classifyNodeReadError(error), {
          kind: item.kind,
          truth: item.truth,
        });
        assert.equal(
          (error as { status?: number }).status,
          item.status,
        );
        assert.doesNotMatch(
          error instanceof Error ? error.message : String(error),
          /PRIVATE BACKEND BODY/,
        );
        return true;
      },
    );
  }
});

test("GET route injects auth, preserves raw JSON, and rejects policy violations", async () => {
  const { GET, POST } = await requireProxyRoute();
  const originalFetch = globalThis.fetch;
  const originalBase = process.env.DHARMA_API_INTERNAL_URL;
  const originalKey = process.env.DASHBOARD_API_KEY;
  const calls: Array<{ url: string; init?: RequestInit }> = [];
  globalThis.fetch = (async (
    input: RequestInfo | URL,
    init?: RequestInit,
  ) => {
    calls.push({ url: String(input), init });
    return new Response(
      JSON.stringify({
        status: "ok",
        data: [{ id: "agni" }],
        error: "",
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    );
  }) as typeof fetch;
  process.env.DHARMA_API_INTERNAL_URL = "http://backend.internal:9000";
  process.env.DASHBOARD_API_KEY = "server-secret";

  try {
    const response = await GET(
      new Request("http://dashboard/dashboard/a2a-node/api/agents"),
      { params: Promise.resolve({ path: ["agents"] }) },
    );
    assert.equal(response.status, 200);
    assert.deepEqual(await response.json(), {
      status: "ok",
      data: [{ id: "agni" }],
    });
    assert.equal(calls[0]?.url, "http://backend.internal:9000/api/agents");
    const headers = new Headers(calls[0]?.init?.headers);
    assert.equal(headers.get("Authorization"), "Bearer server-secret");
    assert.equal(calls[0]?.init?.method, "GET");

    delete process.env.DASHBOARD_API_KEY;
    const development = await GET(
      new Request("http://dashboard/dashboard/a2a-node/api/agents"),
      { params: Promise.resolve({ path: ["agents"] }) },
    );
    assert.equal(development.status, 200);
    assert.equal(
      new Headers(calls[1]?.init?.headers).get("Authorization"),
      null,
    );

    const unknown = await GET(
      new Request("http://dashboard/dashboard/a2a-node/api/admin"),
      { params: Promise.resolve({ path: ["admin"] }) },
    );
    assert.equal(unknown.status, 404);
    assert.equal(calls.length, 2);

    const method = await POST(
      new Request("http://dashboard/dashboard/a2a-node/api/agents", {
        method: "POST",
      }),
      { params: Promise.resolve({ path: ["agents"] }) },
    );
    assert.equal(method.status, 405);
    assert.equal(calls.length, 2);
  } finally {
    globalThis.fetch = originalFetch;
    if (originalBase === undefined) {
      delete process.env.DHARMA_API_INTERNAL_URL;
    } else {
      process.env.DHARMA_API_INTERNAL_URL = originalBase;
    }
    if (originalKey === undefined) {
      delete process.env.DASHBOARD_API_KEY;
    } else {
      process.env.DASHBOARD_API_KEY = originalKey;
    }
  }
});

test("route preserves safe upstream status categories without body leakage", async () => {
  const { GET } = await requireProxyRoute();
  const originalFetch = globalThis.fetch;
  const originalBase = process.env.DHARMA_API_INTERNAL_URL;
  const originalKey = process.env.DASHBOARD_API_KEY;
  delete process.env.DHARMA_API_INTERNAL_URL;
  delete process.env.DASHBOARD_API_KEY;

  try {
    const cases = [
      { status: 401, kind: "auth" },
      { status: 403, kind: "auth" },
      { status: 404, kind: "contract" },
      { status: 429, kind: "throttle" },
      { status: 503, kind: "upstream" },
    ] as const;
    for (const item of cases) {
      globalThis.fetch = (async () =>
        new Response("PRIVATE BACKEND ERROR BODY", {
          status: item.status,
          headers: { "Content-Type": "text/plain" },
        })) as typeof fetch;
      const response = await GET(
        new Request("http://dashboard/dashboard/a2a-node/api/agents"),
        { params: Promise.resolve({ path: ["agents"] }) },
      );
      assert.equal(response.status, item.status);
      const body = await response.json();
      assert.equal(body.error.kind, item.kind);
      assert.equal(body.error.status, item.status);
      assert.doesNotMatch(JSON.stringify(body), /PRIVATE BACKEND ERROR BODY/);
    }

    globalThis.fetch = (async () => {
      throw new Error("PRIVATE NETWORK FAILURE");
    }) as typeof fetch;
    const network = await GET(
      new Request("http://dashboard/dashboard/a2a-node/api/agents"),
      { params: Promise.resolve({ path: ["agents"] }) },
    );
    assert.equal(network.status, 502);
    assert.deepEqual(await network.json(), {
      error: {
        kind: "upstream",
        status: 502,
        message: "Backend read was unreachable",
      },
    });
  } finally {
    globalThis.fetch = originalFetch;
    if (originalBase === undefined) {
      delete process.env.DHARMA_API_INTERNAL_URL;
    } else {
      process.env.DHARMA_API_INTERNAL_URL = originalBase;
    }
    if (originalKey === undefined) {
      delete process.env.DASHBOARD_API_KEY;
    } else {
      process.env.DASHBOARD_API_KEY = originalKey;
    }
  }
});

test("route classifies malformed upstream bodies as safe projection errors", async () => {
  const { GET } = await requireProxyRoute();
  const originalFetch = globalThis.fetch;
  const bodies = [
    { contentType: "text/plain", body: "PRIVATE NON-JSON BODY" },
    { contentType: "application/json", body: "{PRIVATE MALFORMED JSON" },
  ];

  try {
    for (const item of bodies) {
      globalThis.fetch = (async () =>
        new Response(item.body, {
          status: 200,
          headers: { "Content-Type": item.contentType },
        })) as typeof fetch;
      const response = await GET(
        new Request("http://dashboard/dashboard/a2a-node/api/agents"),
        { params: Promise.resolve({ path: ["agents"] }) },
      );
      assert.equal(response.status, 502);
      assert.deepEqual(await response.json(), {
        error: {
          kind: "projection",
          status: 502,
          message: "Backend read returned malformed JSON evidence",
        },
      });
    }

    globalThis.fetch = (async () =>
      Response.json({
        status: "error",
        error: "PRIVATE ERROR ENVELOPE BODY",
      })) as typeof fetch;
    const errorEnvelope = await GET(
      new Request("http://dashboard/dashboard/a2a-node/api/agents"),
      { params: Promise.resolve({ path: ["agents"] }) },
    );
    assert.equal(errorEnvelope.status, 502);
    assert.deepEqual(await errorEnvelope.json(), {
      error: {
        kind: "contract",
        status: 502,
        message: "Backend returned an application error envelope",
      },
    });
  } finally {
    globalThis.fetch = originalFetch;
  }
});
