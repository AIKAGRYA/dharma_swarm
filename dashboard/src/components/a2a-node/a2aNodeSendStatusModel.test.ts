import assert from "node:assert/strict";
import test from "node:test";

const PACKET_ID = "018f1f2e-7b4c-7abc-8def-0123456789ab";

async function model() {
  return import("./a2aNodeSend.ts");
}

test("packet status uses authenticated same-origin GET and validates STORED evidence", async () => {
  const { A2ASendError, checkA2ASendStatus } = await model();
  const calls: Array<{ input: string; init?: RequestInit }> = [];
  const responses = [
    Response.json({
      packet_id: PACKET_ID,
      target: "hermes",
      status: "PENDING",
    }),
    Response.json({
      packet_id: PACKET_ID,
      target: "hermes",
      status: "UNKNOWN",
    }),
    Response.json({
      packet_id: PACKET_ID,
      target: "hermes",
      status: "STORED",
      receipt: {
        ok: true,
        subject: "dharma.a2a.hermes",
        seq: 17,
        from: "operator-node",
        packet_id: PACKET_ID,
        evidence_tier: "STORED",
      },
    }),
  ];
  const fetcher = (async (
    request: RequestInfo | URL,
    init?: RequestInit,
  ) => {
    calls.push({ input: String(request), init });
    const response = responses.shift();
    assert.ok(response);
    return response;
  }) as typeof fetch;

  assert.equal(
    (await checkA2ASendStatus(PACKET_ID, { fetcher })).status,
    "PENDING",
  );
  assert.equal(
    (await checkA2ASendStatus(PACKET_ID, { fetcher })).status,
    "UNKNOWN",
  );
  const stored = await checkA2ASendStatus(PACKET_ID, { fetcher });
  assert.equal(stored.status, "STORED");
  if (stored.status === "STORED") assert.equal(stored.receipt.seq, 17);
  assert.equal(calls.length, 3);
  for (const call of calls) {
    assert.equal(
      call.input,
      `/dashboard/a2a-node/api/a2a/send/status/${PACKET_ID}`,
    );
    assert.equal(call.init?.method, "GET");
    assert.equal(call.init?.credentials, "same-origin");
    assert.equal(call.init?.body, undefined);
    assert.equal(new Headers(call.init?.headers).get("Authorization"), null);
  }

  await assert.rejects(
    () =>
      checkA2ASendStatus(PACKET_ID, {
        fetcher: (async () =>
          Response.json({
            packet_id: PACKET_ID,
            target: "hermes",
            status: "STORED",
            receipt: {
              ok: true,
              subject: "dharma.a2a.hermes",
              seq: 0,
              from: "operator-node",
              packet_id: PACKET_ID,
              evidence_tier: "STORED",
            },
          })) as typeof fetch,
      }),
    (error) => {
      assert.ok(error instanceof A2ASendError);
      assert.equal(error.kind, "projection");
      return true;
    },
  );
});

test("session descriptor persists only safe unresolved identity", async () => {
  const {
    A2A_SEND_SESSION_KEY,
    parseA2ASendUnresolved,
    serializeA2ASendUnresolved,
  } = await model();
  const descriptor = {
    packet_id: PACKET_ID,
    target: "hermes",
    status: "UNKNOWN" as const,
  };
  const serialized = serializeA2ASendUnresolved(descriptor);

  assert.match(A2A_SEND_SESSION_KEY, /unresolved/i);
  assert.deepEqual(JSON.parse(serialized), descriptor);
  assert.deepEqual(parseA2ASendUnresolved(serialized), descriptor);
  assert.doesNotMatch(serialized, /body|message|token|secret/i);
  for (const unsafe of [
    null,
    "{}",
    JSON.stringify({ ...descriptor, body: "private" }),
    JSON.stringify({ ...descriptor, packet_id: "../escape" }),
    JSON.stringify({ ...descriptor, target: "../hermes" }),
    JSON.stringify({ ...descriptor, status: "STORED" }),
  ]) {
    assert.equal(parseA2ASendUnresolved(unsafe), null);
  }
});

test("PENDING send response retains the packet without republishing", async () => {
  const { A2ASendError, sendA2AMessage } = await model();
  await assert.rejects(
    () =>
      sendA2AMessage(
        { to: "hermes", body: "hello", packet_id: PACKET_ID },
        {
          fetcher: (async () =>
            Response.json(
              {
                error: {
                  kind: "upstream",
                  status: 409,
                  message: "Mailbox send is still pending",
                  outcome: "PENDING",
                  packet_id: PACKET_ID,
                },
              },
              { status: 409 },
            )) as typeof fetch,
        },
      ),
    (error) => {
      assert.ok(error instanceof A2ASendError);
      assert.equal(error.outcome, "PENDING");
      assert.equal(error.packet_id, PACKET_ID);
      return true;
    },
  );
});
