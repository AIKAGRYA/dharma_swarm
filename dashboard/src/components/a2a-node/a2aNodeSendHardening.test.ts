import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import { mkdtempSync, readdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test, { after } from "node:test";

type RouteHandler = (
  request: Request,
  context: { params: Promise<{ path: string[] }> },
) => Promise<Response>;

const RECEIPT_DIR = mkdtempSync(join(tmpdir(), "a2a-send-hardening-"));
const ENV_KEYS = [
  "A2A_NODE_OPERATOR_USER",
  "A2A_NODE_OPERATOR_PASSWORD",
  "A2A_GATEWAY_URL",
  "A2A_GATEWAY_TOKEN",
  "A2A_NODE_SEND_RECEIPT_DIR",
  "NODE_ENV",
] as const;

after(() => rmSync(RECEIPT_DIR, { recursive: true, force: true }));

async function postRoute(): Promise<RouteHandler> {
  const loaded = await import(
    "../../app/dashboard/a2a-node/api/[...path]/route.ts"
  );
  return loaded.POST as RouteHandler;
}

function basic(): string {
  return `Basic ${Buffer.from("operator:phone-secret").toString("base64")}`;
}

function context() {
  return { params: Promise.resolve({ path: ["a2a", "send"] }) };
}

function captureEnv(): Record<string, string | undefined> {
  return Object.fromEntries(ENV_KEYS.map((key) => [key, process.env[key]]));
}

function configure(
  overrides: Partial<Record<(typeof ENV_KEYS)[number], string | undefined>> = {},
) {
  const values = {
    A2A_NODE_OPERATOR_USER: "operator",
    A2A_NODE_OPERATOR_PASSWORD: "phone-secret",
    A2A_GATEWAY_URL: "https://gateway.example",
    A2A_GATEWAY_TOKEN: "gateway-secret",
    A2A_NODE_SEND_RECEIPT_DIR: RECEIPT_DIR,
    NODE_ENV: "test",
    ...overrides,
  };
  for (const key of ENV_KEYS) {
    const value = values[key];
    if (value === undefined) delete process.env[key];
    else process.env[key] = value;
  }
}

function restoreEnv(snapshot: Record<string, string | undefined>) {
  for (const key of ENV_KEYS) {
    const value = snapshot[key];
    if (value === undefined) delete process.env[key];
    else process.env[key] = value;
  }
}

function sendRequest(
  packetId: string,
  options: { authorization?: string | null; body?: BodyInit } = {},
): Request {
  const headers = new Headers({ "Content-Type": "application/json" });
  const authorization =
    options.authorization === undefined ? basic() : options.authorization;
  if (authorization) headers.set("Authorization", authorization);
  return new Request("http://dashboard/dashboard/a2a-node/api/a2a/send", {
    method: "POST",
    headers,
    body:
      options.body ??
      JSON.stringify({ to: "hermes", body: "hello", packet_id: packetId }),
  });
}

function streamRequest(
  packetId: string,
  body: ReadableStream<Uint8Array>,
): Request {
  return new Request(
    "http://dashboard/dashboard/a2a-node/api/a2a/send",
    {
      method: "POST",
      headers: {
        Authorization: basic(),
        "Content-Type": "application/json",
        "X-Packet-For-Test": packetId,
      },
      body,
      duplex: "half",
    } as RequestInit & { duplex: "half" },
  );
}

function assertUnknown(body: unknown, packetId: string) {
  assert.equal(typeof body, "object");
  const error = (body as { error: Record<string, unknown> }).error;
  assert.equal(error.outcome, "UNKNOWN");
  assert.equal(error.packet_id, packetId);
  assert.notEqual(error.kind, "contract");
  assert.doesNotMatch(JSON.stringify(body), /STORED/);
}

test("POST requires configured valid Basic auth even outside production", async () => {
  const POST = await postRoute();
  const originalFetch = globalThis.fetch;
  const originalEnv = captureEnv();
  let upstreamCalls = 0;
  globalThis.fetch = (async () => {
    upstreamCalls += 1;
    return Response.json({
      ok: true,
      subject: "dharma.a2a.hermes",
      seq: 1,
      from: "operator-node",
    });
  }) as typeof fetch;

  try {
    configure({
      A2A_NODE_OPERATOR_USER: undefined,
      A2A_NODE_OPERATOR_PASSWORD: undefined,
    });
    const missingConfig = await POST(sendRequest(randomUUID()), context());
    assert.equal(missingConfig.status, 503);

    configure();
    const missingHeader = await POST(
      sendRequest(randomUUID(), { authorization: null }),
      context(),
    );
    assert.equal(missingHeader.status, 401);
    assert.equal(upstreamCalls, 0);
  } finally {
    globalThis.fetch = originalFetch;
    restoreEnv(originalEnv);
  }
});

test("gateway token rejects every control character before fetch", async () => {
  const POST = await postRoute();
  const originalFetch = globalThis.fetch;
  const originalEnv = captureEnv();
  let upstreamCalls = 0;
  globalThis.fetch = (async () => {
    upstreamCalls += 1;
    throw new Error("must not fetch");
  }) as typeof fetch;

  try {
    for (const control of ["\t", "\n", "\r", "\u0085"]) {
      configure({ A2A_GATEWAY_TOKEN: `gateway${control}secret` });
      const response = await POST(sendRequest(randomUUID()), context());
      assert.equal(response.status, 503);
      assert.equal((await response.json()).error.kind, "configuration");
    }
    assert.equal(upstreamCalls, 0);
  } finally {
    globalThis.fetch = originalFetch;
    restoreEnv(originalEnv);
  }
});

test("non-visible gateway tokens fail before claim or header creation", async () => {
  const POST = await postRoute();
  const originalFetch = globalThis.fetch;
  const originalEnv = captureEnv();
  let upstreamCalls = 0;
  globalThis.fetch = (async () => {
    upstreamCalls += 1;
    throw new Error("must not fetch");
  }) as typeof fetch;
  const initialEntries = readdirSync(RECEIPT_DIR).sort();

  try {
    for (const token of [
      "gateway secret",
      "gáteway-secret",
      "gateway\u00a0secret",
    ]) {
      configure({ A2A_GATEWAY_TOKEN: token });
      const response = await POST(sendRequest(randomUUID()), context());
      assert.equal(response.status, 503);
      assert.equal((await response.json()).error.kind, "configuration");
    }
    assert.equal(upstreamCalls, 0);
    assert.deepEqual(readdirSync(RECEIPT_DIR).sort(), initialEntries);
  } finally {
    globalThis.fetch = originalFetch;
    restoreEnv(originalEnv);
  }
});

test("redirect, 408, 5xx, network, and nonpositive seq remain UNKNOWN", async () => {
  const POST = await postRoute();
  const originalFetch = globalThis.fetch;
  const originalEnv = captureEnv();
  configure();

  try {
    const cases: Array<() => Promise<Response>> = [
      async () => new Response(null, { status: 302 }),
      async () => new Response("timeout", { status: 408 }),
      async () => new Response("failure", { status: 503 }),
      async () => {
        throw new TypeError("ambiguous network failure");
      },
      async () =>
        Response.json({
          ok: true,
          subject: "dharma.a2a.hermes",
          seq: 0,
          from: "operator-node",
        }),
    ];
    for (const upstream of cases) {
      const packetId = randomUUID();
      globalThis.fetch = upstream as typeof fetch;
      const response = await POST(sendRequest(packetId), context());
      assert.ok([408, 502, 503, 504].includes(response.status));
      assertUnknown(await response.json(), packetId);
    }
  } finally {
    globalThis.fetch = originalFetch;
    restoreEnv(originalEnv);
  }
});

test("request and upstream bodies cancel as soon as they exceed 8KiB", async () => {
  const POST = await postRoute();
  const originalFetch = globalThis.fetch;
  const originalEnv = captureEnv();
  configure();

  const boundedStream = () => {
    let pulls = 0;
    let cancelled = false;
    const body = new ReadableStream<Uint8Array>(
      {
        pull(controller) {
          pulls += 1;
          if (pulls === 1) controller.enqueue(new Uint8Array(8 * 1024));
          else if (pulls === 2) controller.enqueue(new Uint8Array([1]));
          else throw new Error("reader consumed beyond its limit");
        },
        cancel() {
          cancelled = true;
        },
      },
      { highWaterMark: 0 },
    );
    return {
      body,
      pulls: () => pulls,
      cancelled: () => cancelled,
    };
  };

  try {
    let upstreamCalls = 0;
    globalThis.fetch = (async () => {
      upstreamCalls += 1;
      throw new Error("must not fetch");
    }) as typeof fetch;
    const incoming = boundedStream();
    const requestResponse = await POST(
      streamRequest(randomUUID(), incoming.body),
      context(),
    );
    assert.equal(requestResponse.status, 413);
    assert.equal(incoming.pulls(), 2);
    assert.equal(incoming.cancelled(), true);
    assert.equal(upstreamCalls, 0);

    const outgoing = boundedStream();
    globalThis.fetch = (async () =>
      new Response(outgoing.body, {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })) as typeof fetch;
    const packetId = randomUUID();
    const response = await POST(sendRequest(packetId), context());
    assert.equal(response.status, 502);
    assertUnknown(await response.json(), packetId);
    assert.equal(outgoing.pulls(), 2);
    assert.equal(outgoing.cancelled(), true);
  } finally {
    globalThis.fetch = originalFetch;
    restoreEnv(originalEnv);
  }
});
