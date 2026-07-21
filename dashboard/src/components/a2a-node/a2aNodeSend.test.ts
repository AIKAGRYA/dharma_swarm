import assert from "node:assert/strict";
import test from "node:test";

const PACKET_ID = "018f1f2e-7b4c-7abc-8def-0123456789ab";

type SendSupport = {
  A2ASendError: new (
    message: string,
    kind: string,
    status?: number | null,
  ) => Error & {
    kind: string;
    status: number | null;
    outcome: "PENDING" | "UNKNOWN" | "REJECTED";
    packet_id: string | null;
  };
  sendA2AMessage: (
    input: { to: string; body: string; packet_id: string },
    options?: { fetcher?: typeof fetch },
  ) => Promise<{
    ok: true;
    subject: string;
    seq: number;
    from: string;
    packet_id: string;
    evidence_tier: "STORED";
  }>;
  sendA2AMessageAttempt: (
    input: { to: string; body: string },
    options?: {
      fetcher?: typeof fetch;
      randomUUID?: () => string;
      packetId?: string;
    },
  ) => Promise<{
    ok: true;
    subject: string;
    seq: number;
    from: string;
    packet_id: string;
    evidence_tier: "STORED";
  }>;
  sendFailureView: (error: unknown) => {
    kind: string;
    title: string;
    detail: string;
    outcome: "PENDING" | "UNKNOWN" | "REJECTED";
    packetId: string | null;
  };
  sendOutcomeText: (result: { seq: number; evidence_tier: "STORED" }) => string;
  A2A_SEND_SESSION_KEY: string;
  parseA2ASendUnresolved: (value: string | null) => {
    packet_id: string;
    target: string;
    status: "PENDING" | "UNKNOWN";
  } | null;
  serializeA2ASendUnresolved: (value: {
    packet_id: string;
    target: string;
    status: "PENDING" | "UNKNOWN";
  }) => string;
  checkA2ASendStatus: (
    packetId: string,
    options?: { fetcher?: typeof fetch },
  ) => Promise<
    | {
        packet_id: string;
        target: string;
        status: "PENDING" | "UNKNOWN";
      }
    | {
        packet_id: string;
        target: string;
        status: "STORED";
        receipt: {
          ok: true;
          subject: string;
          seq: number;
          from: string;
          packet_id: string;
          evidence_tier: "STORED";
        };
      }
  >;
};

async function sendSupport(): Promise<SendSupport> {
  const loaded = await import("./a2aNodeSend.ts").catch(() => null);
  assert.ok(loaded, "A2A send model must exist");
  return loaded as SendSupport;
}

function storedResponse(packetId = PACKET_ID): Response {
  return Response.json({
    ok: true,
    subject: "dharma.a2a.hermes",
    seq: 4242,
    from: "operator-node",
    packet_id: packetId,
    evidence_tier: "STORED",
  });
}

test("one send attempt generates one UUID and performs one exact POST", async () => {
  const { sendA2AMessageAttempt } = await sendSupport();
  let uuidCalls = 0;
  const calls: Array<{ input: string; init?: RequestInit }> = [];
  const fetcher = (async (
    input: RequestInfo | URL,
    init?: RequestInit,
  ) => {
    calls.push({ input: String(input), init });
    return storedResponse();
  }) as typeof fetch;

  const result = await sendA2AMessageAttempt(
    { to: "hermes", body: "hello" },
    {
      fetcher,
      randomUUID: () => {
        uuidCalls += 1;
        return PACKET_ID;
      },
    },
  );

  assert.equal(uuidCalls, 1);
  assert.equal(calls.length, 1);
  assert.equal(calls[0]?.input, "/dashboard/a2a-node/api/a2a/send");
  assert.equal(calls[0]?.init?.method, "POST");
  assert.equal(calls[0]?.init?.cache, "no-store");
  const headers = new Headers(calls[0]?.init?.headers);
  assert.equal(headers.get("Content-Type"), "application/json");
  assert.equal(headers.get("Authorization"), null);
  assert.deepEqual(JSON.parse(String(calls[0]?.init?.body)), {
    to: "hermes",
    body: "hello",
    packet_id: PACKET_ID,
  });
  assert.equal(result.packet_id, PACKET_ID);
  assert.equal(result.evidence_tier, "STORED");
});

test("send never retries a rejected attempt", async () => {
  const { A2ASendError, sendA2AMessageAttempt } = await sendSupport();
  let fetchCalls = 0;
  let uuidCalls = 0;
  const fetcher = (async () => {
    fetchCalls += 1;
    return Response.json(
      {
        error: {
          kind: "upstream",
          status: 503,
          message: "PRIVATE gateway-secret diagnostic",
        },
      },
      { status: 503 },
    );
  }) as typeof fetch;

  await assert.rejects(
    () =>
      sendA2AMessageAttempt(
        { to: "hermes", body: "hello" },
        {
          fetcher,
          randomUUID: () => {
            uuidCalls += 1;
            return PACKET_ID;
          },
        },
      ),
    (error) => {
      assert.ok(error instanceof A2ASendError);
      assert.equal(error.kind, "upstream");
      assert.equal(error.status, 503);
      assert.doesNotMatch(error.message, /PRIVATE|gateway-secret/);
      return true;
    },
  );
  assert.equal(uuidCalls, 1);
  assert.equal(fetchCalls, 1);
});

test("send exposes safe typed failures for route categories", async () => {
  const { A2ASendError, sendA2AMessage } = await sendSupport();
  const cases = [
    { status: 401, kind: "auth" },
    { status: 403, kind: "auth" },
    { status: 429, kind: "throttle" },
    { status: 503, kind: "upstream" },
  ] as const;

  for (const item of cases) {
    const fetcher = (async () =>
      Response.json(
        {
          error: {
            kind: item.kind,
            status: item.status,
            message: "PRIVATE gateway-secret diagnostic",
          },
        },
        { status: item.status },
      )) as typeof fetch;
    await assert.rejects(
      () =>
        sendA2AMessage(
          { to: "hermes", body: "hello", packet_id: PACKET_ID },
          { fetcher },
        ),
      (error) => {
        assert.ok(error instanceof A2ASendError);
        assert.equal(error.kind, item.kind);
        assert.equal(error.status, item.status);
        assert.doesNotMatch(error.message, /PRIVATE|gateway-secret/);
        return true;
      },
    );
  }
});

test("unknown outcome retains and exposes one packet ID across manual checks", async () => {
  const {
    A2ASendError,
    sendA2AMessageAttempt,
    sendFailureView,
  } = await sendSupport();
  let fetchCalls = 0;
  let uuidCalls = 0;
  const fetcher = (async () => {
    fetchCalls += 1;
    return Response.json(
      {
        error: {
          kind: "upstream",
          status: 502,
          message: "Mailbox send outcome is unknown",
          outcome: "UNKNOWN",
          packet_id: PACKET_ID,
        },
      },
      { status: 502 },
    );
  }) as typeof fetch;
  const randomUUID = () => {
    uuidCalls += 1;
    return PACKET_ID;
  };

  let firstError:
    | (Error & {
        outcome: "PENDING" | "UNKNOWN" | "REJECTED";
        packet_id: string | null;
      })
    | null = null;
  try {
    await sendA2AMessageAttempt(
      { to: "hermes", body: "hello" },
      { fetcher, randomUUID },
    );
  } catch (error) {
    assert.ok(error instanceof A2ASendError);
    firstError = error;
  }
  assert.ok(firstError);
  assert.equal(firstError.outcome, "UNKNOWN");
  assert.equal(firstError.packet_id, PACKET_ID);
  const view = sendFailureView(firstError);
  assert.equal(view.outcome, "UNKNOWN");
  assert.equal(view.packetId, PACKET_ID);

  await assert.rejects(() =>
    sendA2AMessageAttempt(
      { to: "hermes", body: "hello" },
      { fetcher, randomUUID, packetId: firstError?.packet_id ?? undefined },
    ),
  );
  assert.equal(uuidCalls, 1);
  assert.equal(fetchCalls, 2);
});

test("browser transport, redirect, and 408 failures remain unknown for the packet", async () => {
  const { A2ASendError, sendA2AMessage } = await sendSupport();
  const fetchers = [
    (async () => {
      throw new TypeError("network ambiguous");
    }) as typeof fetch,
    (async () => new Response(null, { status: 302 })) as typeof fetch,
    (async () => new Response("timeout", { status: 408 })) as typeof fetch,
  ];

  for (const fetcher of fetchers) {
    await assert.rejects(
      () =>
        sendA2AMessage(
          { to: "hermes", body: "hello", packet_id: PACKET_ID },
          { fetcher },
        ),
      (error) => {
        assert.ok(error instanceof A2ASendError);
        assert.equal(error.outcome, "UNKNOWN");
        assert.equal(error.packet_id, PACKET_ID);
        return true;
      },
    );
  }
});

test("send rejects malformed success evidence instead of upgrading it", async () => {
  const { A2ASendError, sendA2AMessage } = await sendSupport();
  const malformed = [
    Response.json({
      ok: true,
      subject: "dharma.a2a.hermes",
      seq: 1,
      from: "operator-node",
      packet_id: PACKET_ID,
      evidence_tier: "DELIVERED",
    }),
    Response.json({
      ok: true,
      subject: "dharma.a2a.hermes",
      seq: 0,
      from: "operator-node",
      packet_id: PACKET_ID,
      evidence_tier: "STORED",
    }),
    Response.json({
      ok: true,
      subject: "dharma.a2a.hermes",
      seq: -1,
      from: "operator-node",
      packet_id: PACKET_ID,
      evidence_tier: "STORED",
    }),
    Response.json({
      ok: true,
      subject: "dharma.a2a.hermes",
      seq: "1",
      from: "operator-node",
      packet_id: PACKET_ID,
      evidence_tier: "STORED",
    }),
    new Response("not-json", {
      status: 200,
      headers: { "Content-Type": "text/plain" },
    }),
  ];

  for (const response of malformed) {
    await assert.rejects(
      () =>
        sendA2AMessage(
          { to: "hermes", body: "hello", packet_id: PACKET_ID },
          { fetcher: (async () => response) as typeof fetch },
        ),
      (error) => {
        assert.ok(error instanceof A2ASendError);
        assert.equal(error.kind, "projection");
        return true;
      },
    );
  }
});

test("send presentation says STORED with sequence and never implies delivery", async () => {
  const { sendFailureView, sendOutcomeText } = await sendSupport();
  const success = sendOutcomeText({ evidence_tier: "STORED", seq: 4242 });
  assert.equal(success, "STORED · seq 4242");
  assert.doesNotMatch(success, /delivered|processed|effect/i);

  const failure = sendFailureView(
    Object.assign(new Error("PRIVATE gateway-secret"), {
      name: "A2ASendError",
      kind: "throttle",
      status: 429,
      outcome: "REJECTED",
      packet_id: null,
    }),
  );
  assert.equal(failure.kind, "throttle");
  assert.match(failure.title, /throttled/i);
  assert.doesNotMatch(JSON.stringify(failure), /PRIVATE|gateway-secret/);
});
