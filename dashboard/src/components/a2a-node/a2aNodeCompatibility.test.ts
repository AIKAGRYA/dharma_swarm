import assert from "node:assert/strict";
import test from "node:test";

type RouteHandler = (
  request: Request,
  context: { params: Promise<{ path: string[] }> },
) => Promise<Response>;

async function proxyGet(): Promise<RouteHandler> {
  const loaded = await import(
    "../../app/dashboard/a2a-node/api/[...path]/route.ts"
  );
  return loaded.GET as RouteHandler;
}

function routeContext(path: string[]) {
  return { params: Promise.resolve({ path }) };
}

test("proxy rejects HTTP 200 application failures without leaking payload details", async () => {
  const GET = await proxyGet();
  const originalFetch = globalThis.fetch;
  const cases = [
    {
      status: "ok",
      data: [],
      error: "PRIVATE database URL and credential",
    },
    {
      status: "failed",
      data: { private: "PRIVATE internal state" },
      error: "",
    },
    {
      status: "degraded",
      data: [],
    },
  ];

  try {
    for (const payload of cases) {
      globalThis.fetch = (async () =>
        Response.json(payload)) as typeof fetch;
      const response = await GET(
        new Request("http://dashboard/dashboard/a2a-node/api/agents"),
        routeContext(["agents"]),
      );
      assert.equal(response.status, 502);
      assert.deepEqual(await response.json(), {
        error: {
          kind: "contract",
          status: 502,
          message: "Backend returned an application error envelope",
        },
      });
    }
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("proxy strips A2A source error details while preserving partial card data", async () => {
  const GET = await proxyGet();
  const originalFetch = globalThis.fetch;
  const card = {
    id: "card-1",
    title: "A2A receipt",
    body: "to: soma\ncontact_evidence_tier: HANDLER_ACKED",
    status: "observed",
    created_at: "2026-07-14T21:39:00Z",
  };

  try {
    globalThis.fetch = (async () =>
      Response.json({
        schema_version: "0.2.0",
        request_id: "request-1",
        generated_at: "2026-07-14T21:39:00Z",
        source_errors: [
          {
            source: "a2a_send_cards",
            error: "PRIVATE /home/operator path and broker credential",
          },
        ],
        data: {
          receipt_root: "/receipts",
          target: null,
          card_count: 1,
          cards: [card],
        },
      })) as typeof fetch;
    const response = await GET(
      new Request(
        "http://dashboard/dashboard/a2a-node/api/a2a/cards?limit=48",
      ),
      routeContext(["a2a", "cards"]),
    );
    assert.equal(response.status, 200);
    const payload = await response.json();
    assert.deepEqual(payload.source_errors, [
      { source: "a2a_send_cards" },
    ]);
    assert.deepEqual(payload.data.cards, [card]);
    assert.doesNotMatch(
      JSON.stringify(payload),
      /PRIVATE|\/home\/operator|broker credential/,
    );
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("proxy rejects malformed source error projections without reflecting them", async () => {
  const GET = await proxyGet();
  const originalFetch = globalThis.fetch;
  try {
    globalThis.fetch = (async () =>
      Response.json({
        schema_version: "0.2.0",
        source_errors: "PRIVATE malformed source error",
        data: { card_count: 0, cards: [] },
      })) as typeof fetch;
    const response = await GET(
      new Request(
        "http://dashboard/dashboard/a2a-node/api/a2a/cards?limit=48",
      ),
      routeContext(["a2a", "cards"]),
    );
    assert.equal(response.status, 502);
    const payload = await response.json();
    assert.equal(payload.error.kind, "projection");
    assert.doesNotMatch(JSON.stringify(payload), /PRIVATE/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
