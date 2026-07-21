import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import {
  existsSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawn } from "node:child_process";
import test from "node:test";

const STORE_URL = new URL(
  "./a2aNodeSendReceiptStore.mjs",
  import.meta.url,
).href;
const RECEIPT_FS_URL = new URL(
  "./a2aNodeSendReceiptFs.mjs",
  import.meta.url,
).href;
const STALE_AFTER_MS = 60_000;

function sandbox(): string {
  return mkdtempSync(join(tmpdir(), "a2a-crash-recovery-"));
}

function input(packetId = randomUUID()) {
  return {
    to: "hermes",
    body: "private crash recovery payload",
    packet_id: packetId,
  };
}

function crashDuringClaim(
  receiptDir: string,
  sendInput: ReturnType<typeof input>,
): Promise<number | null> {
  const script = `
    const store = await import(process.env.STORE_URL);
    await store.claimPacket(
      process.env.RECEIPT_DIR,
      JSON.parse(process.env.SEND_INPUT),
      {
        staleAfterMs: Number(process.env.STALE_AFTER_MS),
        observe(event) {
          if (event === "claim:root-fsync") process.exit(73);
        },
      },
    );
  `;
  return new Promise((resolve, reject) => {
    const child = spawn(
      process.execPath,
      ["--input-type=module", "-e", script],
      {
        env: {
          ...process.env,
          STORE_URL,
          RECEIPT_DIR: receiptDir,
          SEND_INPUT: JSON.stringify(sendInput),
          STALE_AFTER_MS: String(STALE_AFTER_MS),
        },
        stdio: ["ignore", "ignore", "pipe"],
      },
    );
    let stderr = "";
    child.stderr.setEncoding("utf8");
    child.stderr.on("data", (chunk) => {
      stderr += chunk;
    });
    child.on("error", reject);
    child.on("close", (code) => {
      if (code !== 73) {
        reject(new Error(`crash child exited ${code}: ${stderr}`));
        return;
      }
      resolve(code);
    });
  });
}

test("stale threshold configuration is bounded", async () => {
  const store = await import("./a2aNodeSendReceiptStore.mjs");
  assert.equal(typeof store.resolveReceiptStaleAfterMs, "function");
  if (typeof store.resolveReceiptStaleAfterMs !== "function") return;
  assert.equal(store.resolveReceiptStaleAfterMs(undefined), 60_000);
  assert.equal(store.resolveReceiptStaleAfterMs("15000"), 15_000);
  for (const invalid of ["", "14999", "86400001", "1.5", "nope"]) {
    assert.throws(() => store.resolveReceiptStaleAfterMs(invalid));
  }
});

test("fresh PENDING remains pending but stale begin becomes durable UNKNOWN", async () => {
  const receiptDir = sandbox();
  const store = await import("./a2aNodeSendReceiptStore.mjs");
  const sendInput = input();
  const startedAt = Date.parse("2026-07-15T10:00:00.000Z");
  const options = {
    staleAfterMs: STALE_AFTER_MS,
    now: () => startedAt,
  };

  try {
    const owner = await store.claimPacket(receiptDir, sendInput, options);
    assert.equal(owner.state, "owner");
    const fresh = await store.getPacketStatus(
      receiptDir,
      sendInput.packet_id,
      {
        ...options,
        now: () => startedAt + STALE_AFTER_MS - 1,
      },
    );
    assert.equal(fresh.status, "PENDING");

    const recovered = await store.claimPacket(receiptDir, sendInput, {
      ...options,
      now: () => startedAt + STALE_AFTER_MS + 1,
    });
    assert.equal(recovered.state, "unknown");
    const state = JSON.parse(
      readFileSync(
        join(receiptDir, sendInput.packet_id, "state.json"),
        "utf8",
      ),
    );
    assert.equal(state.state, "UNKNOWN");
    assert.equal("owner_token" in state, false);
  } finally {
    rmSync(receiptDir, { recursive: true, force: true });
  }
});

test("simulated crash leaves timestamped owner then restart recovers UNKNOWN", async () => {
  const receiptDir = sandbox();
  const store = await import("./a2aNodeSendReceiptStore.mjs");
  const operation = await import("./a2aNodeSendOperation.mjs");
  const sendInput = input();
  const lockDirectory = join(
    receiptDir,
    `.lock-${sendInput.packet_id}`,
  );
  const ownerPath = join(lockDirectory, "owner.json");

  try {
    await crashDuringClaim(receiptDir, sendInput);
    assert.equal(existsSync(lockDirectory), true);
    assert.equal(existsSync(ownerPath), true);
    if (!existsSync(ownerPath)) return;
    const lockOwner = JSON.parse(readFileSync(ownerPath, "utf8"));
    assert.deepEqual(Object.keys(lockOwner).sort(), [
      "acquired_at",
      "owner_token",
      "packet_id",
      "version",
    ]);
    assert.match(lockOwner.owner_token, /^[0-9a-f-]{36}$/i);
    assert.equal(
      Number.isFinite(Date.parse(lockOwner.acquired_at)),
      true,
    );
    const staleOwner = {
      ...lockOwner,
      acquired_at: new Date(
        Date.now() - STALE_AFTER_MS - 1_000,
      ).toISOString(),
    };
    writeFileSync(ownerPath, JSON.stringify(staleOwner), {
      mode: 0o600,
    });

    const recovered = await store.getPacketStatus(
      receiptDir,
      sendInput.packet_id,
      {
        staleAfterMs: STALE_AFTER_MS,
      },
    );
    assert.equal(recovered.status, "UNKNOWN");
    assert.equal(existsSync(lockDirectory), true);
    assert.equal(
      JSON.parse(
        readFileSync(
          join(receiptDir, sendInput.packet_id, "state.json"),
          "utf8",
        ),
      ).state,
      "PENDING",
    );

    let upstreamCalls = 0;
    const restarted = operation.createSendCoordinator({
      fetcher: (async () => {
        upstreamCalls += 1;
        throw new Error("must never republish recovered packet");
      }) as typeof fetch,
    });
    const replay = await restarted.execute({
      input: sendInput,
      target: new URL("https://gateway.example/a2a/mailbox/send"),
      token: "gateway-secret",
      receiptDir,
      staleAfterMs: STALE_AFTER_MS,
    });
    assert.equal(replay.state, "unknown");
    assert.equal(upstreamCalls, 0);
  } finally {
    rmSync(receiptDir, { recursive: true, force: true });
  }
});

test("stale lock never admits a concurrent replacement owner", async () => {
  const receiptDir = sandbox();
  const store = await import("./a2aNodeSendReceiptStore.mjs");
  const sendInput = input();
  const startedAt = Date.parse("2026-07-15T10:00:00.000Z");
  const lockDirectory = join(
    receiptDir,
    `.lock-${sendInput.packet_id}`,
  );
  const ownerPath = join(lockDirectory, "owner.json");
  const script = `
    const fs = await import(process.env.RECEIPT_FS_URL);
    await fs.withPacketLock(
      process.env.RECEIPT_DIR,
      process.env.PACKET_ID,
      {
        staleAfterMs: Number(process.env.STALE_AFTER_MS),
        now: () => Number(process.env.STARTED_AT),
      },
      async () => {
        process.stdout.write("READY\\n");
        await new Promise(() => {
          process.stdin.once("data", () => process.exit(0));
        });
      },
    );
  `;
  const holder = spawn(
    process.execPath,
    ["--input-type=module", "-e", script],
    {
      env: {
        ...process.env,
        RECEIPT_FS_URL,
        RECEIPT_DIR: receiptDir,
        PACKET_ID: sendInput.packet_id,
        STALE_AFTER_MS: String(STALE_AFTER_MS),
        STARTED_AT: String(startedAt),
      },
      stdio: ["pipe", "pipe", "pipe"],
    },
  );

  try {
    await new Promise<void>((resolve, reject) => {
      let output = "";
      holder.stdout.setEncoding("utf8");
      holder.stdout.on("data", (chunk) => {
        output += chunk;
        if (output.includes("READY\n")) resolve();
      });
      holder.once("error", reject);
      holder.once("close", (code) => {
        if (!output.includes("READY\n")) {
          reject(new Error(`lock holder exited before ready: ${code}`));
        }
      });
    });
    const originalOwner = readFileSync(ownerPath, "utf8");
    const events: string[] = [];
    const result = await store.claimPacket(receiptDir, sendInput, {
      staleAfterMs: STALE_AFTER_MS,
      now: () => startedAt + STALE_AFTER_MS + 1,
      observe: (event: string) => events.push(event),
    });

    assert.equal(holder.exitCode, null);
    assert.equal(result.state, "unknown");
    assert.equal(existsSync(lockDirectory), true);
    assert.equal(readFileSync(ownerPath, "utf8"), originalOwner);
    assert.equal(
      events.includes("lock:root-fsync"),
      false,
      "contender must never acquire a replacement lock",
    );
    assert.equal(
      existsSync(join(receiptDir, sendInput.packet_id)),
      false,
    );
  } finally {
    holder.stdin.write("crash\n");
    await new Promise<void>((resolve) => {
      if (holder.exitCode !== null) resolve();
      else holder.once("close", () => resolve());
    });
    rmSync(receiptDir, { recursive: true, force: true });
  }
});

test("high-iteration release/acquire races stay ordinary contention", async () => {
  const receiptDir = sandbox();
  const receiptFs = await import("./a2aNodeSendReceiptFs.mjs");
  const packetId = randomUUID();
  const workers = 8;
  const iterations = 50;
  let activeOwners = 0;
  let completed = 0;

  try {
    await Promise.all(
      Array.from({ length: workers }, async () => {
        for (let index = 0; index < iterations; index += 1) {
          await receiptFs.withPacketLock(
            receiptDir,
            packetId,
            { staleAfterMs: STALE_AFTER_MS },
            async () => {
              activeOwners += 1;
              try {
                assert.equal(
                  activeOwners,
                  1,
                  "lock generations must never overlap",
                );
                await new Promise<void>((resolve) => {
                  setImmediate(resolve);
                });
                completed += 1;
              } finally {
                activeOwners -= 1;
              }
            },
          );
        }
      }),
    );
    assert.equal(completed, workers * iterations);
    assert.equal(activeOwners, 0);
  } finally {
    rmSync(receiptDir, { recursive: true, force: true });
  }
});
