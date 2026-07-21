import assert from "node:assert/strict";
import test from "node:test";

import {
  deriveFleetNodeTruth,
  fetchRawFleetNodes,
  nodeStatusTone,
  parseFleetNodesResponse,
} from "../components/a2a-node/a2aNodeFleet.ts";
import { classifyNodeReadError } from "../components/a2a-node/a2aNodeReadModel.ts";
import {
  RECEIPT_TIER_ORDER,
  buildReceiptLadder,
  deriveFreshness,
  deriveStreamEmptyState,
  extractReceiptTier,
  mergeActivity,
} from "./a2aNodeModel.ts";

const MODEL_NOW = Date.parse("2026-07-14T18:00:00Z");

function fleetNode(overrides: Record<string, unknown> = {}) {
  return {
    node_id: "agni",
    endpoint: "https://agni.example",
    ssh_alias: "agni",
    status: "online",
    last_heartbeat: "2026-07-14T17:59:30Z",
    capabilities: ["dispatch", "review"],
    metadata: { agent_uid: "agni-runtime" },
    api_key_env: "DHARMA_NODE_KEY_AGNI",
    ...overrides,
  };
}

test("receipt ladder preserves strict evidence order and exact counts", () => {
  const ladder = buildReceiptLadder([
    { body: "contact_evidence_tier: NO_CONTACT" },
    { contact_evidence_tier: "HANDLER_ACKED" },
    { body: "kind: reply_capture\ncontact_evidence_tier: DOMAIN_RECEIPTED" },
    { ack_tier: "PUBLISH_ACCEPTED" },
    { body: "contact_evidence_tier: CORE_FLUSH_ONLY" },
    { body: "contact_evidence_tier: HANDLER_ACKED" },
  ]);

  assert.deepEqual(
    ladder.tiers.map(({ tier }) => tier),
    RECEIPT_TIER_ORDER,
  );
  assert.deepEqual(
    ladder.tiers.map(({ count }) => count),
    [1, 2, 1, 1, 1],
  );
  assert.equal(ladder.unknown.length, 0);
});

test("receipt extraction fails loud for unknown tiers without upgrading status claims", () => {
  assert.throws(
    () =>
      extractReceiptTier({
        body: "contact_evidence_tier: DELIVERED_TO_CONSUMER",
      }),
    /Unknown evidence tier "DELIVERED_TO_CONSUMER"/,
  );

  const ladder = buildReceiptLadder([
    {
      id: "unknown-tier",
      status: "DOMAIN_RECEIPTED",
      body: "contact_evidence_tier: DELIVERED_TO_CONSUMER",
    },
    {
      id: "status-only",
      status: "DOMAIN_RECEIPTED",
      body: "no explicit contact tier",
    },
  ]);

  assert.deepEqual(
    ladder.tiers.map(({ count }) => count),
    [0, 0, 0, 0, 0],
  );
  assert.deepEqual(
    ladder.unknown.map(({ id, rawTier }) => ({ id, rawTier })),
    [
      { id: "unknown-tier", rawTier: "DELIVERED_TO_CONSUMER" },
      { id: "status-only", rawTier: "<missing>" },
    ],
  );
});

test("trace and A2A activity merge newest-first and retain malformed timestamps deterministically", () => {
  const traces = [
    {
      id: "trace-new",
      timestamp: "2026-07-14T18:00:00Z",
      agent: "agni",
      action: "heartbeat projected",
      state: "done",
      metadata: {},
    },
    {
      id: "trace-bad",
      timestamp: "not-a-timestamp",
      agent: "unknown",
      action: "unparseable trace",
      state: "unknown",
      metadata: {},
    },
  ];
  const a2aCards = [
    {
      id: "a2a-mid",
      title: "A2A hermes",
      body: "to: hermes\ncontact_evidence_tier: HANDLER_ACKED",
      status: "review",
      created_at: "2026-07-14T17:59:00Z",
      updated_at: "2026-07-14T17:59:00Z",
    },
    {
      id: "a2a-bad",
      title: "Malformed send evidence",
      body: "contact_evidence_tier: PUBLISH_ACCEPTED",
      status: "review",
      created_at: "yesterday-ish",
      updated_at: "also-invalid",
    },
  ];

  const first = mergeActivity(traces, a2aCards, MODEL_NOW);
  const second = mergeActivity(traces, a2aCards, MODEL_NOW);

  assert.deepEqual(
    first.map(({ id }) => id),
    ["trace-new", "a2a-mid", "trace-bad", "a2a-bad"],
  );
  assert.deepEqual(first, second);
  assert.equal(first[0]?.evidenceState, "known");
  assert.equal(first[1]?.evidenceState, "known");
  assert.equal(first[2]?.evidenceState, "unknown");
  assert.equal(first[3]?.evidenceState, "unknown");
  assert.match(first[2]?.detail ?? "", /malformed timestamp/i);
  assert.match(first[3]?.detail ?? "", /malformed timestamp/i);
});

test("strict timestamps require RFC3339 offsets and never promote future evidence", () => {
  assert.deepEqual(deriveFreshness("2026-07-14T17:59:00Z", MODEL_NOW), {
    state: "runtime",
    ageMs: 60_000,
  });
  assert.deepEqual(
    deriveFreshness("2026-07-14T23:29:00+05:30", MODEL_NOW),
    { state: "runtime", ageMs: 60_000 },
  );
  for (const timestamp of [
    "2026-07-14T17:59:00",
    "2026-02-30T17:59:00Z",
    "not-a-time",
    "2026-07-14T18:00:00.001Z",
    "2099-01-01T00:00:00Z",
  ]) {
    assert.deepEqual(deriveFreshness(timestamp, MODEL_NOW), {
      state: "unknown",
      ageMs: null,
    });
  }

  assert.throws(
    () =>
      parseFleetNodesResponse(
        {
          count: 1,
          nodes: [fleetNode({ last_heartbeat: "2026-07-14T17:59:00" })],
        },
        MODEL_NOW,
      ),
    /RFC3339.*timezone/i,
  );
  assert.throws(
    () =>
      parseFleetNodesResponse(
        {
          count: 1,
          nodes: [fleetNode({ last_heartbeat: "2099-01-01T00:00:00Z" })],
        },
        MODEL_NOW,
      ),
    /future/i,
  );

  const futureActivity = mergeActivity(
    [
      {
        id: "future-trace",
        timestamp: "2026-07-14T18:00:00.001Z",
        agent: "agni",
        action: "future claim",
        state: "done",
      },
    ],
    [],
    MODEL_NOW,
  );
  assert.equal(futureActivity[0]?.evidenceState, "unknown");
  assert.match(futureActivity[0]?.detail ?? "", /future timestamp/i);

  const futureReceipt = buildReceiptLadder(
    [
      {
        id: "future-receipt",
        contact_evidence_tier: "DOMAIN_RECEIPTED",
        created_at: "2099-01-01T00:00:00Z",
      },
    ],
    MODEL_NOW,
  );
  assert.deepEqual(
    futureReceipt.tiers.map(({ count }) => count),
    [0, 0, 0, 0, 0],
  );
  assert.match(futureReceipt.unknown[0]?.reason ?? "", /future timestamp/i);
});

test("empty stream state only claims both sources answered when both succeeded", () => {
  assert.deepEqual(deriveStreamEmptyState("ok", "ok"), {
    state: "intentional-empty",
    title: "The evidence rail is quiet",
    detail: "Both sources answered without recent trace or A2A records.",
  });
  assert.deepEqual(deriveStreamEmptyState("ok", "blocked"), {
    state: "partial",
    title: "Partial evidence rail",
    detail:
      "Trace activity answered, but A2A receipts are blocked. No activity was returned by the available source.",
  });
  assert.deepEqual(deriveStreamEmptyState("unknown", "ok"), {
    state: "partial",
    title: "Partial evidence rail",
    detail:
      "A2A receipts answered, but trace activity is unknown. No activity was returned by the available source.",
  });
  assert.deepEqual(deriveStreamEmptyState("unreachable", "unreachable"), {
    state: "unreachable",
    title: "Evidence rail unreachable",
    detail:
      "Trace activity is unreachable; A2A receipts are unreachable. No empty-state claim can be made.",
  });
  assert.deepEqual(deriveStreamEmptyState("blocked", "unreachable"), {
    state: "blocked",
    title: "Evidence rail blocked",
    detail:
      "Trace activity is blocked; A2A receipts are unreachable. No empty-state claim can be made.",
  });
});

test("raw fleet response validates its unwrapped shape and maps node status tones", () => {
  const response = parseFleetNodesResponse({
    count: 2,
    nodes: [
      {
        node_id: "agni",
        endpoint: "https://agni.example",
        ssh_alias: "agni",
        status: "online",
        last_heartbeat: "2026-07-14T17:59:30Z",
        capabilities: ["dispatch", "review"],
        metadata: { agent_uid: "agni-runtime" },
        api_key_env: "DHARMA_NODE_KEY_AGNI",
      },
      {
        node_id: "hermes",
        endpoint: "",
        ssh_alias: "",
        status: "degraded",
        last_heartbeat: "",
        capabilities: [],
        metadata: {},
        api_key_env: "DHARMA_NODE_KEY_HERMES",
      },
    ],
  }, MODEL_NOW);

  assert.equal(response.count, 2);
  assert.equal(response.nodes[0]?.metadata.agent_uid, "agni-runtime");
  assert.equal(nodeStatusTone("online"), "runtime");
  assert.equal(nodeStatusTone("degraded"), "stale");
  assert.equal(nodeStatusTone("offline"), "unreachable");
  assert.equal(nodeStatusTone("unknown"), "unknown");
  assert.equal(nodeStatusTone("invented"), "unknown");

  assert.throws(
    () =>
      parseFleetNodesResponse({
        status: "ok",
        data: { count: 0, nodes: [] },
      }),
    /raw fleet response/i,
  );
  assert.throws(
    () => parseFleetNodesResponse({ count: 2, nodes: [] }),
    /count does not match nodes length/i,
  );
});

test("fleet node truth composes registry status with strict heartbeat freshness", () => {
  assert.deepEqual(deriveFleetNodeTruth(fleetNode(), MODEL_NOW), {
    state: "runtime",
    ageMs: 30_000,
  });
  assert.deepEqual(
    deriveFleetNodeTruth(fleetNode({ status: "degraded" }), MODEL_NOW),
    { state: "stale", ageMs: 30_000 },
  );
  assert.deepEqual(
    deriveFleetNodeTruth(fleetNode({ status: "offline" }), MODEL_NOW),
    { state: "unreachable", ageMs: 30_000 },
  );
  assert.deepEqual(
    deriveFleetNodeTruth(
      fleetNode({ last_heartbeat: "2026-07-14T18:00:01Z" }),
      MODEL_NOW,
    ),
    { state: "unknown", ageMs: null },
  );
});

test("production fleet fetch preserves the raw contract and rejects wrapped envelopes", async () => {
  const calls: Array<{ input: RequestInfo | URL; init?: RequestInit }> = [];
  const fetcher = (async (
    input: RequestInfo | URL,
    init?: RequestInit,
  ) => {
    calls.push({ input, init });
    return new Response(
      JSON.stringify({
        status: "ok",
        data: { count: 0, nodes: [] },
        error: "",
        timestamp: "2026-07-14T18:00:00Z",
      }),
      {
        status: 200,
        headers: { "Content-Type": "application/json" },
      },
    );
  }) as typeof fetch;

  let rejection: unknown;
  try {
    await fetchRawFleetNodes({
      fetcher,
      url: "/api/fleet/nodes",
      nowMs: MODEL_NOW,
    });
  } catch (error) {
    rejection = error;
  }

  assert.deepEqual(classifyNodeReadError(rejection), {
    kind: "projection",
    truth: "unknown",
  });
  assert.equal(String(calls[0]?.input), "/api/fleet/nodes");
  assert.equal(calls[0]?.init?.method, "GET");
});

test("fleet failures preserve auth, transport, and projection truth categories", async () => {
  const unavailable = (async () =>
    Response.json(
      {
        error: {
          kind: "upstream",
          status: 503,
          message: "Backend read was unavailable",
        },
      },
      { status: 503 },
    )) as typeof fetch;

  let transportFailure: unknown;
  try {
    await fetchRawFleetNodes({ fetcher: unavailable, nowMs: MODEL_NOW });
  } catch (error) {
    transportFailure = error;
  }
  assert.deepEqual(classifyNodeReadError(transportFailure), {
    kind: "upstream",
    truth: "unreachable",
  });

  const denied = (async () =>
    Response.json(
      {
        error: {
          kind: "auth",
          status: 401,
          message: "Backend authentication rejected this read",
        },
      },
      { status: 401 },
    )) as typeof fetch;
  let authFailure: unknown;
  try {
    await fetchRawFleetNodes({ fetcher: denied, nowMs: MODEL_NOW });
  } catch (error) {
    authFailure = error;
  }
  assert.deepEqual(classifyNodeReadError(authFailure), {
    kind: "auth",
    truth: "blocked",
  });

  let projectionFailure: unknown;
  try {
    parseFleetNodesResponse({ count: 1, nodes: [] }, MODEL_NOW);
  } catch (error) {
    projectionFailure = error;
  }
  assert.deepEqual(classifyNodeReadError(projectionFailure), {
    kind: "projection",
    truth: "unknown",
  });
});

test("duplicate model identities are rejected or deterministically disambiguated", () => {
  assert.throws(
    () =>
      parseFleetNodesResponse(
        {
          count: 2,
          nodes: [fleetNode(), fleetNode({ endpoint: "https://other.example" })],
        },
        MODEL_NOW,
      ),
    /duplicate node_id "agni"/i,
  );
  assert.throws(
    () =>
      parseFleetNodesResponse(
        {
          count: 1,
          nodes: [
            fleetNode({ capabilities: ["dispatch", " dispatch "] }),
          ],
        },
        MODEL_NOW,
      ),
    /duplicate capability "dispatch"/i,
  );

  const activity = mergeActivity(
    [
      {
        id: "same-activity",
        timestamp: "2026-07-14T17:58:00Z",
        agent: "agni",
        action: "first",
        state: "done",
      },
      {
        id: "same-activity",
        timestamp: "2026-07-14T17:59:00Z",
        agent: "agni",
        action: "second",
        state: "done",
      },
    ],
    [],
    MODEL_NOW,
  );
  assert.equal(new Set(activity.map(({ key }) => key)).size, activity.length);
});

test("freshness derives runtime, stale, unreachable, and unknown without clock dependence", () => {
  const now = Date.parse("2026-07-14T18:00:00Z");

  assert.deepEqual(
    deriveFreshness("2026-07-14T17:55:00Z", now),
    { state: "runtime", ageMs: 300_000 },
  );
  assert.deepEqual(
    deriveFreshness("2026-07-14T17:54:59.999Z", now),
    { state: "stale", ageMs: 300_001 },
  );
  assert.deepEqual(
    deriveFreshness("2026-07-14T17:45:00Z", now),
    { state: "stale", ageMs: 900_000 },
  );
  assert.deepEqual(
    deriveFreshness("2026-07-14T17:44:59.999Z", now),
    { state: "unreachable", ageMs: 900_001 },
  );
  assert.deepEqual(deriveFreshness("not-a-time", now), {
    state: "unknown",
    ageMs: null,
  });
});
