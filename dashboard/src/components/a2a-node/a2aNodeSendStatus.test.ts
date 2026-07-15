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

const RECEIPT_DIR = mkdtempSync(join(tmpdir(), "a2a-send-status-"));
const ENV_KEYS = [
  "A2A_NODE_OPERATOR_USER",
  "A2A_NODE_OPERATOR_PASSWORD",
  "A2A_GATEWAY_URL",
  "A2A_GATEWAY_TOKEN",
  "A2A_NODE_SEND_RECEIPT_DIR",
  "NODE_ENV",
] as const;

after(() => rmSync(RECEIPT_DIR, { recursive: true, force: true }));

function basic(): string {
  return `Basic ${Buffer.from("operator:phone-secret").toString("base64")}`;
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

function statusRequest(packetId: string, authorization: string | null = basic()) {
  const headers = new Headers();
  if (authorization) headers.set("Authorization", authorization);
  return new Request(
    `http://dashboard/dashboard/a2a-node/api/a2a/send/status/${packetId}`,
    { headers },
  );
}

function statusContext(packetId: string) {
  return {
    params: Promise.resolve({
      path: ["a2a", "send", "status", packetId],
    }),
  };
}

async function routes(): Promise<{ GET: RouteHandler }> {
  const loaded = await import(
    "../../app/dashboard/a2a-node/api/[...path]/route.ts"
  );
  return { GET: loaded.GET as RouteHandler };
}

test("packet status requires configured Basic auth in every environment", async () => {
  const { GET } = await routes();
  const originalEnv = captureEnv();
  const packetId = randomUUID();

  try {
    configure();
    const unauthorized = await GET(
      statusRequest(packetId, null),
      statusContext(packetId),
    );
    assert.equal(unauthorized.status, 401);

    configure({
      A2A_NODE_OPERATOR_USER: undefined,
      A2A_NODE_OPERATOR_PASSWORD: undefined,
    });
    const unconfigured = await GET(
      statusRequest(packetId),
      statusContext(packetId),
    );
    assert.equal(unconfigured.status, 503);
  } finally {
    restoreEnv(originalEnv);
  }
});

test("status projects only safe PENDING, UNKNOWN, and STORED descriptors", async () => {
  const { GET } = await routes();
  const originalEnv = captureEnv();
  const originalFetch = globalThis.fetch;
  let upstreamCalls = 0;
  globalThis.fetch = (async () => {
    upstreamCalls += 1;
    throw new Error("status must not call upstream");
  }) as typeof fetch;
  configure({
    A2A_GATEWAY_URL: undefined,
    A2A_GATEWAY_TOKEN: undefined,
  });
  const store = await import("./a2aNodeSendReceiptStore.mjs");

  try {
    const pendingInput = {
      to: "hermes",
      body: "pending private body",
      packet_id: randomUUID(),
    };
    const pendingOwner = await store.claimPacket(RECEIPT_DIR, pendingInput);
    assert.equal(pendingOwner.state, "owner");
    const pending = await GET(
      statusRequest(pendingInput.packet_id),
      statusContext(pendingInput.packet_id),
    );
    assert.equal(pending.status, 200);
    const pendingBody = await pending.json();
    assert.deepEqual(pendingBody, {
      packet_id: pendingInput.packet_id,
      target: "hermes",
      status: "PENDING",
    });

    const unknownInput = {
      to: "codex",
      body: "unknown private body",
      packet_id: randomUUID(),
    };
    const unknownOwner = await store.claimPacket(RECEIPT_DIR, unknownInput);
    assert.equal(unknownOwner.state, "owner");
    if (unknownOwner.state !== "owner") return;
    await store.persistUnknown(
      RECEIPT_DIR,
      unknownInput,
      { kind: "upstream", status: 504, secret: "gateway-secret" },
      unknownOwner.ownerToken,
    );
    const unknown = await GET(
      statusRequest(unknownInput.packet_id),
      statusContext(unknownInput.packet_id),
    );
    const unknownBody = await unknown.json();
    assert.deepEqual(unknownBody, {
      packet_id: unknownInput.packet_id,
      target: "codex",
      status: "UNKNOWN",
    });

    const storedInput = {
      to: "agni",
      body: "stored private body",
      packet_id: randomUUID(),
    };
    const storedOwner = await store.claimPacket(RECEIPT_DIR, storedInput);
    assert.equal(storedOwner.state, "owner");
    if (storedOwner.state !== "owner") return;
    const receipt = {
      ok: true,
      subject: "dharma.a2a.agni",
      seq: 9,
      from: "operator-node",
      packet_id: storedInput.packet_id,
      evidence_tier: "STORED",
    };
    await store.persistStored(
      RECEIPT_DIR,
      storedInput,
      receipt,
      storedOwner.ownerToken,
    );
    const stored = await GET(
      statusRequest(storedInput.packet_id),
      statusContext(storedInput.packet_id),
    );
    const storedBody = await stored.json();
    assert.deepEqual(storedBody, {
      packet_id: storedInput.packet_id,
      target: "agni",
      status: "STORED",
      receipt,
    });

    for (const responseBody of [
      pendingBody,
      unknownBody,
      storedBody,
    ]) {
      assert.doesNotMatch(
        JSON.stringify(responseBody),
        /private body|gateway-secret|owner_token|ownerToken/,
      );
    }
    assert.equal(upstreamCalls, 0);
  } finally {
    globalThis.fetch = originalFetch;
    restoreEnv(originalEnv);
  }
});

test("status rejects invalid identifiers and reports missing packets safely", async () => {
  const { GET } = await routes();
  const originalEnv = captureEnv();
  configure();

  try {
    const invalid = await GET(
      statusRequest(".."),
      statusContext(".."),
    );
    assert.equal(invalid.status, 400);

    const packetId = randomUUID();
    const missing = await GET(
      statusRequest(packetId),
      statusContext(packetId),
    );
    assert.equal(missing.status, 404);
    assert.deepEqual(await missing.json(), {
      error: {
        kind: "contract",
        status: 404,
        message: "Send packet status was not found",
      },
    });
  } finally {
    restoreEnv(originalEnv);
  }
});
