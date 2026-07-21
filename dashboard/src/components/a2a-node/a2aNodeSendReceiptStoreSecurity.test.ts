import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import {
  chmodSync,
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  symlinkSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawn } from "node:child_process";
import test from "node:test";

type SendInput = { to: string; body: string; packet_id: string };
type Observer = (event: string) => void;
type StoreOptions = {
  observe?: Observer;
  staleAfterMs?: number;
  now?: () => number;
};

interface ReceiptStore {
  requestFingerprint(input: SendInput): string;
  claimPacket(
    receiptDir: string,
    input: SendInput,
    options?: StoreOptions,
  ): Promise<Record<string, unknown>>;
  persistStored(
    receiptDir: string,
    input: SendInput,
    result: Record<string, unknown>,
    ownerToken: string,
    options?: StoreOptions,
  ): Promise<Record<string, unknown>>;
  persistUnknown(
    receiptDir: string,
    input: SendInput,
    error: Record<string, unknown>,
    ownerToken: string,
    options?: StoreOptions,
  ): Promise<Record<string, unknown>>;
  releasePacket(
    receiptDir: string,
    packetId: string,
    ownerToken: string,
    options?: StoreOptions,
  ): Promise<boolean>;
  getPacketStatus(
    receiptDir: string,
    packetId: string,
    options?: StoreOptions,
  ): Promise<Record<string, unknown>>;
}

const STORE_URL = new URL(
  "./a2aNodeSendReceiptStore.mjs",
  import.meta.url,
).href;

async function store(): Promise<ReceiptStore> {
  return (await import("./a2aNodeSendReceiptStore.mjs")) as ReceiptStore;
}

function sandbox(): string {
  return mkdtempSync(join(tmpdir(), "a2a-receipt-security-"));
}

function input(
  packetId: string = randomUUID(),
  body = "hello",
): SendInput {
  return { to: "hermes", body, packet_id: packetId };
}

function result(packetId: string) {
  return {
    ok: true,
    subject: "dharma.a2a.hermes",
    seq: 42,
    from: "operator-node",
    packet_id: packetId,
    evidence_tier: "STORED",
  };
}

function assertOrdered(events: string[], expected: string[]) {
  let position = -1;
  for (const item of expected) {
    position = events.indexOf(item, position + 1);
    assert.notEqual(
      position,
      -1,
      `missing ordered event ${item}; got ${events.join(", ")}`,
    );
  }
}

function child(mode: string, env: Record<string, string>): Promise<unknown> {
  const script = `
    const store = await import(process.env.STORE_URL);
    const input = JSON.parse(process.env.SEND_INPUT);
    const result = JSON.parse(process.env.SEND_RESULT);
    if (process.env.DELAY_MS) {
      await new Promise((resolve) => setTimeout(resolve, Number(process.env.DELAY_MS)));
    }
    let value;
    if (process.env.MODE === "claim") {
      value = await store.claimPacket(process.env.RECEIPT_DIR, input);
    } else if (process.env.MODE === "stored") {
      value = await store.persistStored(
        process.env.RECEIPT_DIR,
        input,
        result,
        process.env.OWNER_TOKEN,
      );
    } else {
      value = await store.persistUnknown(
        process.env.RECEIPT_DIR,
        input,
        { kind: "upstream", status: 502 },
        process.env.OWNER_TOKEN,
      );
    }
    process.stdout.write(JSON.stringify(value ?? null));
  `;
  return new Promise((resolve, reject) => {
    const processHandle = spawn(
      process.execPath,
      ["--input-type=module", "-e", script],
      {
        env: {
          ...process.env,
          STORE_URL,
          MODE: mode,
          SEND_RESULT: "{}",
          ...env,
        },
        stdio: ["ignore", "pipe", "pipe"],
      },
    );
    let stdout = "";
    let stderr = "";
    processHandle.stdout.setEncoding("utf8");
    processHandle.stderr.setEncoding("utf8");
    processHandle.stdout.on("data", (chunk) => {
      stdout += chunk;
    });
    processHandle.stderr.on("data", (chunk) => {
      stderr += chunk;
    });
    processHandle.on("error", reject);
    processHandle.on("close", (code) => {
      if (code !== 0) {
        reject(new Error(`child exited ${code}: ${stderr}`));
        return;
      }
      resolve(JSON.parse(stdout));
    });
  });
}

test("live PENDING owner is immutable to contenders", async () => {
  const receiptDir = sandbox();
  const api = await store();
  const send = input();

  try {
    const owner = await api.claimPacket(receiptDir, send);
    assert.equal(owner.state, "owner");
    assert.match(String(owner.ownerToken), /^[0-9a-f-]{36}$/i);
    const statePath = join(receiptDir, send.packet_id, "state.json");
    const before = readFileSync(statePath, "utf8");

    const contender = await api.claimPacket(receiptDir, send);
    assert.equal(contender.state, "pending");
    assert.equal(readFileSync(statePath, "utf8"), before);
    assert.equal(JSON.parse(before).state, "PENDING");
  } finally {
    rmSync(receiptDir, { recursive: true, force: true });
  }
});

test("owner-token CAS cannot overwrite a terminal STORED receipt", async () => {
  const receiptDir = sandbox();
  const api = await store();
  const send = input();

  try {
    const owner = await api.claimPacket(receiptDir, send);
    const ownerToken = String(owner.ownerToken);
    const stored = await api.persistStored(
      receiptDir,
      send,
      result(send.packet_id),
      ownerToken,
    );
    assert.equal(stored?.state, "stored");

    const stale = await api.persistUnknown(
      receiptDir,
      send,
      { kind: "upstream", status: 504 },
      ownerToken,
    );
    assert.equal(stale?.state, "stored");
    const state = JSON.parse(
      readFileSync(
        join(receiptDir, send.packet_id, "state.json"),
        "utf8",
      ),
    );
    assert.equal(state.state, "STORED");
    assert.deepEqual(state.result, result(send.packet_id));
  } finally {
    rmSync(receiptDir, { recursive: true, force: true });
  }
});

test("separate processes elect one owner and contenders stay PENDING", async () => {
  const receiptDir = sandbox();
  const send = input();
  const childEnv = {
    RECEIPT_DIR: receiptDir,
    SEND_INPUT: JSON.stringify(send),
  };

  try {
    const claims = (await Promise.all(
      Array.from({ length: 6 }, () => child("claim", childEnv)),
    )) as Array<Record<string, unknown>>;
    assert.equal(claims.filter(({ state }) => state === "owner").length, 1);
    assert.equal(claims.filter(({ state }) => state === "pending").length, 5);
    const state = JSON.parse(
      readFileSync(
        join(receiptDir, send.packet_id, "state.json"),
        "utf8",
      ),
    );
    assert.equal(state.state, "PENDING");
  } finally {
    rmSync(receiptDir, { recursive: true, force: true });
  }
});

test("multiprocess stale finalizer cannot replace STORED", async () => {
  const receiptDir = sandbox();
  const api = await store();
  const send = input();

  try {
    const owner = await api.claimPacket(receiptDir, send);
    const ownerToken = String(owner.ownerToken);
    const childEnv = {
      RECEIPT_DIR: receiptDir,
      SEND_INPUT: JSON.stringify(send),
      SEND_RESULT: JSON.stringify(result(send.packet_id)),
      OWNER_TOKEN: ownerToken,
    };
    const [stored, stale] = (await Promise.all([
      child("stored", childEnv),
      child("unknown", { ...childEnv, DELAY_MS: "100" }),
    ])) as Array<Record<string, unknown>>;
    assert.equal(stored?.state, "stored");
    assert.equal(stale?.state, "stored");
    const status = await api.getPacketStatus(receiptDir, send.packet_id);
    assert.equal(status.status, "STORED");
  } finally {
    rmSync(receiptDir, { recursive: true, force: true });
  }
});

test("stale orphan lock recovers PENDING to readable UNKNOWN", async () => {
  const receiptDir = sandbox();
  const api = await store();
  const send = input();

  try {
    const owner = await api.claimPacket(receiptDir, send);
    assert.equal(owner.state, "owner");
    mkdirSync(join(receiptDir, `.lock-${send.packet_id}`), {
      mode: 0o700,
    });
    const recoveredAt = Date.now() + 60_001;
    const status = await api.getPacketStatus(
      receiptDir,
      send.packet_id,
      { staleAfterMs: 60_000, now: () => recoveredAt },
    );
    assert.equal(status.status, "UNKNOWN");
  } finally {
    rmSync(receiptDir, { recursive: true, force: true });
  }
});

test("store rejects traversal, symlink roots, and unsafe root mode", async () => {
  const parent = sandbox();
  const api = await store();
  const realRoot = join(parent, "real");
  const linkedRoot = join(parent, "linked");
  const unsafeRoot = join(parent, "unsafe");
  const outside = join(parent, "outside");
  mkdirSync(realRoot, { mode: 0o700 });
  symlinkSync(realRoot, linkedRoot, "dir");
  mkdirSync(unsafeRoot, { mode: 0o700 });
  chmodSync(unsafeRoot, 0o755);
  mkdirSync(outside, { mode: 0o700 });
  const sentinel = join(outside, "sentinel");
  writeFileSync(sentinel, "keep", { mode: 0o600 });
  const traversal = input("../outside");

  try {
    assert.throws(() => api.requestFingerprint(traversal));
    await assert.rejects(() => api.claimPacket(linkedRoot, input()));
    await assert.rejects(() => api.claimPacket(unsafeRoot, input()));
    await assert.rejects(() => api.claimPacket(join(parent, "receipts"), traversal));
    await assert.rejects(() =>
      api.persistStored(
        join(parent, "receipts"),
        traversal,
        result(traversal.packet_id),
        randomUUID(),
      ),
    );
    await assert.rejects(() =>
      api.persistUnknown(
        join(parent, "receipts"),
        traversal,
        { kind: "upstream", status: 502 },
        randomUUID(),
      ),
    );
    await assert.rejects(() =>
      api.releasePacket(
        join(parent, "receipts"),
        "../outside",
        randomUUID(),
      ),
    );
    await assert.rejects(() =>
      api.getPacketStatus(join(parent, "receipts"), "../outside"),
    );
    assert.equal(existsSync(sentinel), true);
    assert.equal(readFileSync(sentinel, "utf8"), "keep");
  } finally {
    rmSync(parent, { recursive: true, force: true });
  }
});

test("claim, transition, and removal fsync in durable order", async () => {
  const receiptDir = sandbox();
  const api = await store();
  const send = input();
  const events: string[] = [];
  const observe = (event: string) => events.push(event);

  try {
    const owner = await api.claimPacket(receiptDir, send, { observe });
    assertOrdered(events, [
      "claim:file-fsync",
      "claim:staging-dir-fsync",
      "claim:rename",
      "claim:root-fsync",
    ]);

    events.length = 0;
    await api.persistUnknown(
      receiptDir,
      send,
      { kind: "upstream", status: 502 },
      String(owner.ownerToken),
      { observe },
    );
    assertOrdered(events, [
      "transition:file-fsync",
      "transition:rename",
      "transition:packet-dir-fsync",
      "transition:root-fsync",
    ]);

    const removable = input();
    const removableOwner = await api.claimPacket(receiptDir, removable);
    events.length = 0;
    await api.releasePacket(
      receiptDir,
      removable.packet_id,
      String(removableOwner.ownerToken),
      { observe },
    );
    assertOrdered(events, [
      "removal:state-unlink",
      "removal:packet-dir-fsync",
      "removal:packet-rmdir",
      "removal:root-fsync",
    ]);
  } finally {
    rmSync(receiptDir, { recursive: true, force: true });
  }
});
