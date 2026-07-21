import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import {
  chmodSync,
  existsSync,
  mkdirSync,
  mkdtempSync,
  readdirSync,
  rmSync,
  statSync,
  symlinkSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

const ENV_KEYS = [
  "A2A_NODE_OPERATOR_USER",
  "A2A_NODE_OPERATOR_PASSWORD",
  "A2A_GATEWAY_URL",
  "A2A_GATEWAY_TOKEN",
  "A2A_NODE_SEND_RECEIPT_DIR",
  "A2A_NODE_SEND_STALE_AFTER_MS",
  "NODE_ENV",
] as const;

function sandbox(): string {
  return mkdtempSync(join(tmpdir(), "a2a-root-provision-"));
}

function input() {
  return {
    to: "hermes",
    body: "hello",
    packet_id: randomUUID(),
  };
}

function captureEnv(): Record<string, string | undefined> {
  return Object.fromEntries(ENV_KEYS.map((key) => [key, process.env[key]]));
}

function restoreEnv(snapshot: Record<string, string | undefined>) {
  for (const key of ENV_KEYS) {
    const value = snapshot[key];
    if (value === undefined) delete process.env[key];
    else process.env[key] = value;
  }
}

function basic(): string {
  return `Basic ${Buffer.from("operator:phone-secret").toString("base64")}`;
}

test("explicit helper provisions only a validated parent with mode 0700", async () => {
  const parent = sandbox();
  const receiptDir = join(parent, "receipts");
  const store = await import("./a2aNodeSendReceiptStore.mjs");

  try {
    assert.equal(typeof store.provisionReceiptRoot, "function");
    if (typeof store.provisionReceiptRoot !== "function") return;
    await store.provisionReceiptRoot(receiptDir);
    const info = statSync(receiptDir);
    assert.equal(info.isDirectory(), true);
    assert.equal(info.mode & 0o777, 0o700);
    if (typeof process.getuid === "function") {
      assert.equal(info.uid, process.getuid());
    }
  } finally {
    rmSync(parent, { recursive: true, force: true });
  }
});

test("request-time APIs reject a missing root without writing it", async () => {
  const parent = sandbox();
  const receiptDir = join(parent, "missing-receipts");
  const store = await import("./a2aNodeSendReceiptStore.mjs");
  const sendInput = input();

  try {
    await assert.rejects(() => store.claimPacket(receiptDir, sendInput));
    assert.equal(existsSync(receiptDir), false);
    await assert.rejects(() =>
      store.getPacketStatus(receiptDir, sendInput.packet_id),
    );
    assert.equal(existsSync(receiptDir), false);
  } finally {
    rmSync(parent, { recursive: true, force: true });
  }
});

test("symlinked parent is rejected before provisioning or request writes", async () => {
  const parent = sandbox();
  const realParent = join(parent, "real-parent");
  const linkedParent = join(parent, "linked-parent");
  const targetRoot = join(realParent, "receipts");
  const linkedRoot = join(linkedParent, "receipts");
  const store = await import("./a2aNodeSendReceiptStore.mjs");
  mkdirSync(realParent, { mode: 0o700 });
  symlinkSync(realParent, linkedParent, "dir");

  try {
    assert.equal(typeof store.provisionReceiptRoot, "function");
    if (typeof store.provisionReceiptRoot !== "function") return;
    await assert.rejects(() => store.provisionReceiptRoot(linkedRoot));
    assert.equal(existsSync(targetRoot), false);
    await assert.rejects(() => store.claimPacket(linkedRoot, input()));
    assert.equal(existsSync(targetRoot), false);
  } finally {
    rmSync(parent, { recursive: true, force: true });
  }
});

test("group or world-writable ancestors are rejected before mutation", async () => {
  const parent = sandbox();
  const unsafeParent = join(parent, "swappable");
  const existingRoot = join(unsafeParent, "existing-receipts");
  const missingRoot = join(unsafeParent, "missing-receipts");
  const store = await import("./a2aNodeSendReceiptStore.mjs");
  mkdirSync(unsafeParent, { mode: 0o700 });
  mkdirSync(existingRoot, { mode: 0o700 });
  chmodSync(unsafeParent, 0o777);

  try {
    await assert.rejects(() => store.provisionReceiptRoot(missingRoot));
    assert.equal(existsSync(missingRoot), false);
    await assert.rejects(() => store.claimPacket(existingRoot, input()));
    assert.deepEqual(readdirSync(existingRoot), []);

    chmodSync(unsafeParent, 0o1777);
    await assert.rejects(() => store.claimPacket(existingRoot, input()));
    assert.deepEqual(readdirSync(existingRoot), []);
  } finally {
    rmSync(parent, { recursive: true, force: true });
  }
});

test("root-owned sticky temporary ancestry remains explicitly allowed", async () => {
  const receiptDir = join(
    tmpdir(),
    `a2a-root-sticky-${randomUUID()}`,
  );
  const store = await import("./a2aNodeSendReceiptStore.mjs");
  const temporaryInfo = statSync(tmpdir());

  try {
    assert.equal(temporaryInfo.uid, 0);
    assert.notEqual(temporaryInfo.mode & 0o1000, 0);
    await store.provisionReceiptRoot(receiptDir);
    assert.equal(statSync(receiptDir).mode & 0o777, 0o700);
  } finally {
    rmSync(receiptDir, { recursive: true, force: true });
  }
});

test("POST fails closed without provisioning and creates no receipt path", async () => {
  const parent = sandbox();
  const receiptDir = join(parent, "missing-receipts");
  const originalEnv = captureEnv();
  const originalFetch = globalThis.fetch;
  let upstreamCalls = 0;
  globalThis.fetch = (async () => {
    upstreamCalls += 1;
    throw new Error("must not fetch");
  }) as typeof fetch;
  process.env.A2A_NODE_OPERATOR_USER = "operator";
  process.env.A2A_NODE_OPERATOR_PASSWORD = "phone-secret";
  process.env.A2A_GATEWAY_URL = "https://gateway.example";
  process.env.A2A_GATEWAY_TOKEN = "gateway-secret";
  process.env.A2A_NODE_SEND_RECEIPT_DIR = receiptDir;
  process.env.A2A_NODE_SEND_STALE_AFTER_MS = "60000";
  process.env.NODE_ENV = "test";
  const { POST } = await import(
    "../../app/dashboard/a2a-node/api/[...path]/route.ts"
  );
  const packetId = randomUUID();

  try {
    const response = await POST(
      new Request(
        "http://dashboard/dashboard/a2a-node/api/a2a/send",
        {
          method: "POST",
          headers: {
            Authorization: basic(),
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            to: "hermes",
            body: "hello",
            packet_id: packetId,
          }),
        },
      ),
      {
        params: Promise.resolve({ path: ["a2a", "send"] }),
      },
    );
    assert.equal(response.status, 503);
    assert.equal((await response.json()).error.kind, "configuration");
    assert.equal(upstreamCalls, 0);
    assert.equal(existsSync(receiptDir), false);
  } finally {
    globalThis.fetch = originalFetch;
    restoreEnv(originalEnv);
    rmSync(parent, { recursive: true, force: true });
  }
});
