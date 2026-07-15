import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

interface StoredResult {
  ok: true;
  subject: string;
  seq: number;
  from: string;
  packet_id: string;
  evidence_tier: "STORED";
}

type Execution =
  | { state: "stored"; result: StoredResult; replayed: boolean }
  | {
      state: "unknown";
      error: {
        kind: string;
        status: number;
        outcome: "UNKNOWN";
        packet_id: string;
      };
    }
  | {
      state: "pending";
      error: {
        kind: string;
        status: number;
        outcome: "PENDING";
        packet_id: string;
      };
    }
  | {
      state: "rejected";
      error: { kind: string; status: number; packet_id?: string };
    };

interface Coordinator {
  execute(options: {
    input: { to: string; body: string; packet_id: string };
    target: URL;
    token: string;
    receiptDir: string;
  }): Promise<Execution>;
}

async function createCoordinator(options: {
  fetcher: typeof fetch;
  timeoutMs?: number;
}): Promise<Coordinator> {
  const loaded = await import("./a2aNodeSendOperation.mjs").catch(() => null);
  assert.ok(loaded, "persistent send coordinator must exist");
  return loaded.createSendCoordinator(options) as Coordinator;
}

function sandbox(): string {
  return mkdtempSync(join(tmpdir(), "a2a-send-idempotency-"));
}

function executionInput(packetId = randomUUID(), body = "hello") {
  return {
    input: { to: "hermes", body, packet_id: packetId },
    target: new URL("https://gateway.example/a2a/mailbox/send"),
    token: "gateway-secret",
  };
}

function storedResponse(seq = 4242): Response {
  return Response.json({
    ok: true,
    subject: "dharma.a2a.hermes",
    seq,
    from: "operator-node",
  });
}

test("simultaneous coordinators atomically claim one packet and call upstream once", async () => {
  const receiptDir = sandbox();
  let upstreamCalls = 0;
  const fetcher = (async () => {
    upstreamCalls += 1;
    await new Promise((resolve) => setTimeout(resolve, 10));
    return storedResponse();
  }) as typeof fetch;
  const first = await createCoordinator({ fetcher });
  const second = await createCoordinator({ fetcher });
  const packet = executionInput();

  try {
    const outcomes = await Promise.all([
      first.execute({ ...packet, receiptDir }),
      second.execute({ ...packet, receiptDir }),
    ]);
    assert.equal(upstreamCalls, 1);
    assert.ok(outcomes.some(({ state }) => state === "stored"));
    assert.ok(
      outcomes.every(
        ({ state }) =>
          state === "stored" ||
          state === "unknown" ||
          state === "pending",
      ),
    );
  } finally {
    rmSync(receiptDir, { recursive: true, force: true });
  }
});

test("completed packet replays the exact receipt across coordinator restart", async () => {
  const receiptDir = sandbox();
  let upstreamCalls = 0;
  const packet = executionInput();
  const first = await createCoordinator({
    fetcher: (async () => {
      upstreamCalls += 1;
      return storedResponse(77);
    }) as typeof fetch,
  });

  try {
    const initial = await first.execute({ ...packet, receiptDir });
    assert.equal(initial.state, "stored");
    if (initial.state !== "stored") return;

    const restarted = await createCoordinator({
      fetcher: (async () => {
        upstreamCalls += 1;
        throw new Error("replay must not call upstream");
      }) as typeof fetch,
    });
    const replay = await restarted.execute({ ...packet, receiptDir });
    assert.equal(replay.state, "stored");
    if (replay.state !== "stored") return;
    assert.deepEqual(replay.result, initial.result);
    assert.equal(replay.replayed, true);
    assert.equal(upstreamCalls, 1);

    const state = JSON.parse(
      readFileSync(
        join(receiptDir, packet.input.packet_id, "state.json"),
        "utf8",
      ),
    );
    assert.equal(state.state, "STORED");
    assert.deepEqual(state.result, initial.result);
    assert.equal(JSON.stringify(state).includes(packet.input.body), false);
    assert.equal(JSON.stringify(state).includes(packet.token), false);
  } finally {
    rmSync(receiptDir, { recursive: true, force: true });
  }
});

test("ambiguous network outcome persists UNKNOWN and can never duplicate", async () => {
  const receiptDir = sandbox();
  let upstreamCalls = 0;
  const packet = executionInput();
  const first = await createCoordinator({
    fetcher: (async () => {
      upstreamCalls += 1;
      throw new TypeError("connection reset after write");
    }) as typeof fetch,
  });

  try {
    const ambiguous = await first.execute({ ...packet, receiptDir });
    assert.equal(ambiguous.state, "unknown");
    if (ambiguous.state !== "unknown") return;
    assert.equal(ambiguous.error.outcome, "UNKNOWN");
    assert.equal(ambiguous.error.packet_id, packet.input.packet_id);
    const state = JSON.parse(
      readFileSync(
        join(receiptDir, packet.input.packet_id, "state.json"),
        "utf8",
      ),
    );
    assert.equal(state.state, "UNKNOWN");
    assert.equal(JSON.stringify(state).includes(packet.input.body), false);
    assert.equal(JSON.stringify(state).includes(packet.token), false);

    const restarted = await createCoordinator({
      fetcher: (async () => {
        upstreamCalls += 1;
        return storedResponse();
      }) as typeof fetch,
    });
    const replay = await restarted.execute({ ...packet, receiptDir });
    assert.deepEqual(replay, ambiguous);
    assert.equal(upstreamCalls, 1);
  } finally {
    rmSync(receiptDir, { recursive: true, force: true });
  }
});

test("deadline abort persists UNKNOWN without retrying", async () => {
  const receiptDir = sandbox();
  let upstreamCalls = 0;
  const packet = executionInput();
  const coordinator = await createCoordinator({
    timeoutMs: 5,
    fetcher: (async (_input, init) => {
      upstreamCalls += 1;
      return new Promise<Response>((_resolve, reject) => {
        init?.signal?.addEventListener(
          "abort",
          () => reject(new DOMException("deadline", "AbortError")),
          { once: true },
        );
      });
    }) as typeof fetch,
  });

  try {
    const timedOut = await coordinator.execute({ ...packet, receiptDir });
    assert.equal(timedOut.state, "unknown");
    if (timedOut.state !== "unknown") return;
    assert.equal(timedOut.error.status, 504);
    assert.equal(timedOut.error.outcome, "UNKNOWN");

    const replay = await coordinator.execute({ ...packet, receiptDir });
    assert.deepEqual(replay, timedOut);
    assert.equal(upstreamCalls, 1);
  } finally {
    rmSync(receiptDir, { recursive: true, force: true });
  }
});

test("deadline remains active through a stalled 200 response body", async () => {
  const receiptDir = sandbox();
  let cancelled = false;
  let guard: ReturnType<typeof setTimeout> | undefined;
  const packet = executionInput();
  const stalled = new ReadableStream<Uint8Array>({
    start() {
      // Deliberately never enqueue or close.
    },
    cancel() {
      cancelled = true;
    },
  });
  const coordinator = await createCoordinator({
    timeoutMs: 15,
    fetcher: (async () =>
      new Response(stalled, {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })) as typeof fetch,
  });

  try {
    const outcome = await Promise.race([
      coordinator.execute({ ...packet, receiptDir }),
      new Promise<never>((_resolve, reject) => {
        guard = setTimeout(
          () => reject(new Error("response body escaped its deadline")),
          250,
        );
      }),
    ]);
    assert.equal(outcome.state, "unknown");
    if (outcome.state !== "unknown") return;
    assert.equal(outcome.error.status, 504);
    assert.equal(outcome.error.outcome, "UNKNOWN");
    assert.equal(cancelled, true);
  } finally {
    if (guard) clearTimeout(guard);
    rmSync(receiptDir, { recursive: true, force: true });
  }
});

test("same packet ID with different content is rejected without upstream", async () => {
  const receiptDir = sandbox();
  let upstreamCalls = 0;
  const packetId = randomUUID();
  const coordinator = await createCoordinator({
    fetcher: (async () => {
      upstreamCalls += 1;
      return storedResponse();
    }) as typeof fetch,
  });

  try {
    const first = await coordinator.execute({
      ...executionInput(packetId, "first"),
      receiptDir,
    });
    assert.equal(first.state, "stored");
    const conflict = await coordinator.execute({
      ...executionInput(packetId, "different"),
      receiptDir,
    });
    assert.equal(conflict.state, "rejected");
    if (conflict.state !== "rejected") return;
    assert.equal(conflict.error.status, 409);
    assert.equal(upstreamCalls, 1);
  } finally {
    rmSync(receiptDir, { recursive: true, force: true });
  }
});
