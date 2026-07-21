import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test, { after } from "node:test";

type RouteHandler = (
  request: Request,
  context: { params: Promise<{ path: string[] }> },
) => Promise<Response>;

const ENV_KEYS = [
  "A2A_NODE_OPERATOR_USER",
  "A2A_NODE_OPERATOR_PASSWORD",
  "A2A_GATEWAY_URL",
  "A2A_GATEWAY_TOKEN",
  "A2A_NODE_SEND_RECEIPT_DIR",
  "NODE_ENV",
] as const;
const RECEIPT_DIR = mkdtempSync(join(tmpdir(), "a2a-send-route-"));

after(() => rmSync(RECEIPT_DIR, { recursive: true, force: true }));

async function postRoute(): Promise<RouteHandler> {
  const loaded = await import(
    "../../app/dashboard/a2a-node/api/[...path]/route.ts"
  );
  return loaded.POST as RouteHandler;
}

function basic(user = "operator", password = "phone-secret"): string {
  return `Basic ${Buffer.from(`${user}:${password}`, "utf8").toString("base64")}`;
}

function context(path: string[] = ["a2a", "send"]) {
  return { params: Promise.resolve({ path }) };
}

function request(
  body: BodyInit,
  {
    authorization = basic(),
    contentType = "application/json",
    suffix = "",
  }: {
    authorization?: string | null;
    contentType?: string | null;
    suffix?: string;
  } = {},
): Request {
  const headers = new Headers();
  if (authorization) headers.set("Authorization", authorization);
  if (contentType) headers.set("Content-Type", contentType);
  return new Request(
    `http://dashboard/dashboard/a2a-node/api/a2a/send${suffix}`,
    { method: "POST", headers, body },
  );
}

function jsonRequest(
  body: unknown,
  options: Parameters<typeof request>[1] = {},
): Request {
  return request(JSON.stringify(body), options);
}

function captureEnv(): Record<string, string | undefined> {
  return Object.fromEntries(
    ENV_KEYS.map((key) => [key, process.env[key]]),
  );
}

function setEnv(
  values: Partial<Record<(typeof ENV_KEYS)[number], string | undefined>>,
): void {
  for (const key of ENV_KEYS) {
    const value = values[key];
    if (value === undefined) delete process.env[key];
    else process.env[key] = value;
  }
}

function productionEnv(
  overrides: Partial<Record<(typeof ENV_KEYS)[number], string | undefined>> = {},
): void {
  setEnv({
    A2A_NODE_OPERATOR_USER: "operator",
    A2A_NODE_OPERATOR_PASSWORD: "phone-secret",
    A2A_GATEWAY_URL: "https://gateway.example",
    A2A_GATEWAY_TOKEN: "gateway-secret",
    A2A_NODE_SEND_RECEIPT_DIR: RECEIPT_DIR,
    NODE_ENV: "production",
    ...overrides,
  });
}

function restoreEnv(snapshot: Record<string, string | undefined>): void {
  for (const key of ENV_KEYS) {
    const value = snapshot[key];
    if (value === undefined) delete process.env[key];
    else process.env[key] = value;
  }
}

test("send authenticates ingress before path, body, or upstream access", async () => {
  const POST = await postRoute();
  const originalFetch = globalThis.fetch;
  const originalEnv = captureEnv();
  let upstreamCalls = 0;
  globalThis.fetch = (async () => {
    upstreamCalls += 1;
    throw new Error("must not be reached");
  }) as typeof fetch;
  productionEnv();

  try {
    const unauthorized = await POST(
      request("{not-json", { authorization: null, contentType: "text/plain" }),
      context(),
    );
    assert.equal(unauthorized.status, 401);
    assert.equal(
      unauthorized.headers.get("WWW-Authenticate"),
      'Basic realm="A2A Operator Node", charset="UTF-8"',
    );

    const wrongPath = await POST(
      jsonRequest({ to: "hermes", body: "hello", packet_id: randomUUID() }),
      context(["agents"]),
    );
    assert.equal(wrongPath.status, 405);

    const traversal = await POST(
      jsonRequest({ to: "hermes", body: "hello", packet_id: randomUUID() }),
      context(["a2a", ".."]),
    );
    assert.ok([400, 404].includes(traversal.status));

    const query = await POST(
      jsonRequest(
        { to: "hermes", body: "hello", packet_id: randomUUID() },
        { suffix: "?debug=1" },
      ),
      context(),
    );
    assert.equal(query.status, 400);
    assert.equal(upstreamCalls, 0);
  } finally {
    globalThis.fetch = originalFetch;
    restoreEnv(originalEnv);
  }
});

test("production send fails closed when ingress or gateway config is missing", async () => {
  const POST = await postRoute();
  const originalFetch = globalThis.fetch;
  const originalEnv = captureEnv();
  let upstreamCalls = 0;
  globalThis.fetch = (async () => {
    upstreamCalls += 1;
    throw new Error("must not be reached");
  }) as typeof fetch;
  const payload = { to: "hermes", body: "hello", packet_id: randomUUID() };

  try {
    productionEnv({
      A2A_NODE_OPERATOR_USER: undefined,
      A2A_NODE_OPERATOR_PASSWORD: undefined,
    });
    const noIngress = await POST(jsonRequest(payload), context());
    assert.equal(noIngress.status, 503);

    for (const missing of [
      "A2A_GATEWAY_URL",
      "A2A_GATEWAY_TOKEN",
      "A2A_NODE_SEND_RECEIPT_DIR",
    ] as const) {
      productionEnv({ [missing]: undefined });
      const response = await POST(jsonRequest(payload), context());
      assert.equal(response.status, 503);
      assert.equal((await response.json()).error.kind, "configuration");
    }
    assert.equal(upstreamCalls, 0);
  } finally {
    globalThis.fetch = originalFetch;
    restoreEnv(originalEnv);
  }
});

test("send enforces an exact JSON boundary and byte limits", async () => {
  const POST = await postRoute();
  const originalFetch = globalThis.fetch;
  const originalEnv = captureEnv();
  let upstreamCalls = 0;
  globalThis.fetch = (async () => {
    upstreamCalls += 1;
    throw new Error("must not be reached");
  }) as typeof fetch;
  productionEnv();
  const id = randomUUID();

  const cases: Array<{ candidate: Request; status: number }> = [
    { candidate: request("{}", { contentType: "text/plain" }), status: 415 },
    { candidate: request("{"), status: 400 },
    { candidate: jsonRequest([]), status: 400 },
    {
      candidate: jsonRequest({
        to: "hermes",
        body: "hello",
        packet_id: id,
        from: "spoofed",
      }),
      status: 400,
    },
    {
      candidate: jsonRequest({ to: "../hermes", body: "hello", packet_id: id }),
      status: 400,
    },
    {
      candidate: jsonRequest({ to: "hermes.agent", body: "hello", packet_id: id }),
      status: 400,
    },
    {
      candidate: jsonRequest({ to: "hermes", body: " \n ", packet_id: id }),
      status: 400,
    },
    {
      candidate: jsonRequest({ to: "hermes", body: { text: "hello" }, packet_id: id }),
      status: 400,
    },
    {
      candidate: jsonRequest({ to: "hermes", body: "hello", packet_id: "not-a-uuid" }),
      status: 400,
    },
    {
      candidate: jsonRequest({
        to: "hermes",
        body: "é".repeat(4_097),
        packet_id: id,
      }),
      status: 413,
    },
    {
      candidate: request("x".repeat(20_000)),
      status: 413,
    },
  ];

  try {
    for (const { candidate, status } of cases) {
      const response = await POST(candidate, context());
      assert.equal(response.status, status);
      const serialized = JSON.stringify(await response.json());
      assert.doesNotMatch(serialized, /gateway-secret|phone-secret/);
    }
    assert.equal(upstreamCalls, 0);
  } finally {
    globalThis.fetch = originalFetch;
    restoreEnv(originalEnv);
  }
});

test("send replaces Basic auth, embeds packet identity, and returns STORED only", async () => {
  const POST = await postRoute();
  const originalFetch = globalThis.fetch;
  const originalEnv = captureEnv();
  const calls: Array<{ input: string; init?: RequestInit }> = [];
  globalThis.fetch = (async (
    input: RequestInfo | URL,
    init?: RequestInit,
  ) => {
    calls.push({ input: String(input), init });
    return Response.json({
      ok: true,
      subject: "dharma.a2a.hermes",
      seq: 4242,
      from: "operator-node",
      private_debug: "gateway-secret",
    });
  }) as typeof fetch;
  productionEnv({ A2A_GATEWAY_URL: "https://gateway.example/" });
  const packetId = randomUUID();

  try {
    const response = await POST(
      jsonRequest({ to: "hermes", body: "Hello from the operator.", packet_id: packetId }),
      context(),
    );
    assert.equal(response.status, 200);
    assert.deepEqual(await response.json(), {
      ok: true,
      subject: "dharma.a2a.hermes",
      seq: 4242,
      from: "operator-node",
      packet_id: packetId,
      evidence_tier: "STORED",
    });
    assert.equal(calls.length, 1);
    assert.equal(calls[0]?.input, "https://gateway.example/a2a/mailbox/send");
    assert.equal(calls[0]?.init?.method, "POST");
    assert.equal(calls[0]?.init?.redirect, "manual");
    const headers = new Headers(calls[0]?.init?.headers);
    assert.equal(headers.get("Authorization"), "Bearer gateway-secret");
    assert.equal(headers.get("Content-Type"), "application/json");
    assert.doesNotMatch(
      JSON.stringify([...headers.entries()]),
      /Basic|phone-secret|operator:/,
    );
    assert.deepEqual(JSON.parse(String(calls[0]?.init?.body)), {
      to: "hermes",
      body: {
        kind: "a2a_operator_message.v1",
        packet_id: packetId,
        text: "Hello from the operator.",
      },
    });
  } finally {
    globalThis.fetch = originalFetch;
    restoreEnv(originalEnv);
  }
});

test("send fails closed if a success-shaped upstream payload reflects the token", async () => {
  const POST = await postRoute();
  const originalFetch = globalThis.fetch;
  const originalEnv = captureEnv();
  productionEnv();
  globalThis.fetch = (async () =>
    Response.json({
      ok: true,
      subject: "dharma.a2a.hermes",
      seq: 4242,
      from: "gateway-secret",
    })) as typeof fetch;

  try {
    const response = await POST(
      jsonRequest({
        to: "hermes",
        body: "hello",
        packet_id: randomUUID(),
      }),
      context(),
    );
    assert.equal(response.status, 502);
    const body = await response.json();
    assert.equal(body.error.kind, "projection");
    assert.doesNotMatch(JSON.stringify(body), /gateway-secret/);
  } finally {
    globalThis.fetch = originalFetch;
    restoreEnv(originalEnv);
  }
});

test("send preserves upstream error categories without secret leakage", async () => {
  const POST = await postRoute();
  const originalFetch = globalThis.fetch;
  const originalEnv = captureEnv();
  productionEnv();

  try {
    const cases = [
      { status: 401, kind: "auth" },
      { status: 403, kind: "auth" },
      { status: 429, kind: "throttle" },
      { status: 500, kind: "upstream" },
      { status: 503, kind: "upstream" },
    ] as const;
    for (const item of cases) {
      globalThis.fetch = (async () =>
        new Response(`gateway-secret PRIVATE ${item.status}`, {
          status: item.status,
          headers: { "Content-Type": "text/plain" },
        })) as typeof fetch;
      const response = await POST(
        jsonRequest({
          to: "hermes",
          body: "hello",
          packet_id: randomUUID(),
        }),
        context(),
      );
      assert.equal(response.status, item.status);
      const body = await response.json();
      assert.equal(body.error.kind, item.kind);
      assert.equal(body.error.status, item.status);
      assert.doesNotMatch(JSON.stringify(body), /gateway-secret|PRIVATE/);
    }

    globalThis.fetch = (async () => {
      throw new Error("gateway-secret PRIVATE network detail");
    }) as typeof fetch;
    const network = await POST(
      jsonRequest({
        to: "hermes",
        body: "hello",
        packet_id: randomUUID(),
      }),
      context(),
    );
    assert.equal(network.status, 502);
    assert.equal((await network.json()).error.kind, "upstream");
  } finally {
    globalThis.fetch = originalFetch;
    restoreEnv(originalEnv);
  }
});
