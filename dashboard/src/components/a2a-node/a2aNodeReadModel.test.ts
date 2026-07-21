import assert from "node:assert/strict";
import test from "node:test";

const NOW = Date.parse("2026-07-14T21:40:00Z");
const OBSERVED_AT = "2026-07-14T21:39:00Z";

const validAgent = {
  id: "agent-1",
  name: "agni",
  display_name: "Agni",
  role: "operator",
  status: "running",
  current_task: null,
  provider: "anthropic",
  model: "claude",
  model_label: "Claude",
};

const validTask = {
  id: "task-1",
  title: "Inspect receipts",
  description: "Read only",
  status: "running",
  priority: "high",
  assigned_to: null,
  updated_at: OBSERVED_AT,
};

const validTrace = {
  id: "trace-1",
  timestamp: OBSERVED_AT,
  agent: "agni",
  action: "inspect",
  state: "completed",
};

const validCard = {
  id: "card-1",
  title: "A2A receipt",
  body: "to: soma\ncontact_evidence_tier: HANDLER_ACKED",
  status: "observed",
  created_at: OBSERVED_AT,
  contact_evidence_tier: "HANDLER_ACKED",
};

type ReadOptions = {
  url: string;
  fetcher: typeof fetch;
  nowMs: number;
};

type ReadModel = {
  fetchNodeAgents: (options: ReadOptions) => Promise<unknown[]>;
  fetchNodeTasks: (options: ReadOptions) => Promise<unknown[]>;
  fetchNodeTraces: (options: ReadOptions) => Promise<unknown[]>;
  fetchNodeCards: (
    options: ReadOptions,
  ) => Promise<{
    card_count: number;
    cards: Record<string, unknown>[];
    partial: {
      state: "partial";
      sourceCount: number;
      title: string;
      detail: string;
    } | null;
  }>;
  classifyNodeReadError: (error: unknown) => {
    kind: string;
    truth: string;
  };
  NodeReadError: new (
    message: string,
    kind: string,
    status?: number,
  ) => Error;
  nodeReadFailureView: (
    error: unknown,
    surface: string,
  ) => {
    truth: string;
    surfaceKind: string;
    title: string;
    detail: string;
  };
};

async function readModel(): Promise<ReadModel> {
  const loaded = await import("./a2aNodeReadModel.ts");
  for (const name of [
    "fetchNodeAgents",
    "fetchNodeTasks",
    "fetchNodeTraces",
    "fetchNodeCards",
    "nodeReadFailureView",
  ]) {
    assert.equal(
      typeof loaded[name as keyof typeof loaded],
      "function",
      `${name} must validate its own item projection`,
    );
  }
  return loaded as unknown as ReadModel;
}

function responseWith(data: unknown): typeof fetch {
  return (async () =>
    Response.json({ status: "ok", data })) as typeof fetch;
}

function options(data: unknown): ReadOptions {
  return {
    url: "/dashboard/a2a-node/api/test",
    fetcher: responseWith(data),
    nowMs: NOW,
  };
}

function cardsPayload(cards: unknown[]) {
  return {
    receipt_root: "/receipts",
    target: null,
    card_count: cards.length,
    cards,
  };
}

function malformed(
  valid: Record<string, unknown>,
  field: string,
  value: unknown,
) {
  return { ...valid, [field]: value };
}

async function rejectsProjection(
  operation: () => Promise<unknown>,
  classify: ReadModel["classifyNodeReadError"],
) {
  await assert.rejects(operation, (error) => {
    assert.deepEqual(classify(error), {
      kind: "projection",
      truth: "unknown",
    });
    return true;
  });
}

test("endpoint readers validate and return safe UI projections", async () => {
  const model = await readModel();
  assert.deepEqual(
    await model.fetchNodeAgents(options([validAgent])),
    [validAgent],
  );
  assert.deepEqual(
    await model.fetchNodeTasks(options([validTask])),
    [validTask],
  );
  assert.deepEqual(
    await model.fetchNodeTraces(options([validTrace])),
    [validTrace],
  );
  const cards = await model.fetchNodeCards(
    options(cardsPayload([validCard])),
  );
  assert.equal(cards.card_count, 1);
  assert.equal(cards.cards[0]?.contact_evidence_tier, "HANDLER_ACKED");
  assert.equal(cards.partial, null);
});

test("task and trace readers normalize exact timezone-bearing Python datetime strings", async () => {
  const model = await readModel();
  const [task] = await model.fetchNodeTasks(
    options([
      {
        ...validTask,
        updated_at: "2026-07-14 21:39:00+00:00",
      },
    ]),
  );
  const [trace] = await model.fetchNodeTraces(
    options([
      {
        ...validTrace,
        timestamp: "2026-07-14 17:39:00.123456-04:00",
      },
    ]),
  );

  assert.equal(
    (task as Record<string, unknown>).updated_at,
    "2026-07-14T21:39:00+00:00",
  );
  assert.equal(
    (trace as Record<string, unknown>).timestamp,
    "2026-07-14T17:39:00.123456-04:00",
  );
});

test("Python datetime compatibility remains timezone-bound, standard, and non-future", async () => {
  const model = await readModel();
  for (const timestamp of [
    "2026-07-14 21:39:00",
    "2026-07-14 21:39:00.123+00:00",
    "2026/07/14 21:39:00+00:00",
    "2026-07-14 21:39:00Z",
    "2026-07-14 21:41:00+00:00",
  ]) {
    await rejectsProjection(
      () =>
        model.fetchNodeTasks(
          options([{ ...validTask, updated_at: timestamp }]),
        ),
      model.classifyNodeReadError,
    );
    await rejectsProjection(
      () =>
        model.fetchNodeTraces(
          options([{ ...validTrace, timestamp }]),
        ),
      model.classifyNodeReadError,
    );
  }

  await rejectsProjection(
    () =>
      model.fetchNodeCards(
        options(
          cardsPayload([
            {
              ...validCard,
              created_at: "2026-07-14 21:39:00+00:00",
            },
          ]),
        ),
      ),
    model.classifyNodeReadError,
  );
});

test("HTTP 200 application error envelopes become sanitized contract failures", async () => {
  const model = await readModel();
  for (const payload of [
    {
      status: "ok",
      data: [],
      error: "PRIVATE database path and credentials",
    },
    { status: "failed", data: [], error: "" },
    { status: "degraded", data: [] },
  ]) {
    await assert.rejects(
      () =>
        model.fetchNodeAgents({
          url: "/dashboard/a2a-node/api/agents",
          fetcher: (async () => Response.json(payload)) as typeof fetch,
          nowMs: NOW,
        }),
      (error) => {
        assert.deepEqual(model.classifyNodeReadError(error), {
          kind: "contract",
          truth: "unknown",
        });
        assert.doesNotMatch(
          error instanceof Error ? error.message : String(error),
          /PRIVATE|database|credentials/,
        );
        return true;
      },
    );
  }
});

test("A2A source errors preserve useful cards as explicit sanitized partial truth", async () => {
  const model = await readModel();
  const payload = {
    schema_version: "0.2.0",
    request_id: "request-private",
    generated_at: OBSERVED_AT,
    source_errors: [
      {
        source: "a2a_send_cards",
        error: "PRIVATE /home/operator receipt path",
      },
    ],
    data: cardsPayload([validCard]),
  };
  const result = await model.fetchNodeCards({
    url: "/dashboard/a2a-node/api/a2a/cards?limit=48",
    fetcher: (async () => Response.json(payload)) as typeof fetch,
    nowMs: NOW,
  });

  assert.equal(result.cards.length, 1);
  assert.deepEqual(result.partial, {
    state: "partial",
    sourceCount: 1,
    title: "PARTIAL EVIDENCE · A2A card sources degraded",
    detail:
      "1 source failed; 1 validated card preserved. Backend error details were withheld.",
  });
  assert.doesNotMatch(JSON.stringify(result), /PRIVATE|\/home\/operator/);
});

test("A2A source errors without useful cards fail typed and sanitized", async () => {
  const model = await readModel();
  const payload = {
    schema_version: "0.2.0",
    request_id: "request-private",
    generated_at: OBSERVED_AT,
    source_errors: [
      {
        source: "a2a_send_cards",
        error: "PRIVATE broker credentials",
      },
    ],
    data: cardsPayload([]),
  };

  await assert.rejects(
    () =>
      model.fetchNodeCards({
        url: "/dashboard/a2a-node/api/a2a/cards?limit=48",
        fetcher: (async () => Response.json(payload)) as typeof fetch,
        nowMs: NOW,
      }),
    (error) => {
      assert.deepEqual(model.classifyNodeReadError(error), {
        kind: "contract",
        truth: "unknown",
      });
      assert.doesNotMatch(
        error instanceof Error ? error.message : String(error),
        /PRIVATE|broker|credentials/,
      );
      return true;
    },
  );
});

test("agent validator rejects every render-dereferenced malformed field", async () => {
  const model = await readModel();
  const adversarialFields: Array<[string, unknown]> = [
    ["id", null],
    ["name", null],
    ["display_name", []],
    ["role", {}],
    ["status", 7],
    ["current_task", {}],
    ["provider", null],
    ["model", 42],
    ["model_label", []],
  ];
  for (const [field, value] of adversarialFields) {
    await rejectsProjection(
      () =>
        model.fetchNodeAgents(
          options([malformed(validAgent, field, value)]),
        ),
      model.classifyNodeReadError,
    );
  }
});

test("task validator rejects dangerous fields and invalid update time", async () => {
  const model = await readModel();
  const adversarialFields: Array<[string, unknown]> = [
    ["id", null],
    ["title", []],
    ["description", null],
    ["status", 1],
    ["priority", {}],
    ["assigned_to", []],
    ["updated_at", "2026-07-14T21:39:00"],
  ];
  for (const [field, value] of adversarialFields) {
    await rejectsProjection(
      () =>
        model.fetchNodeTasks(
          options([malformed(validTask, field, value)]),
        ),
      model.classifyNodeReadError,
    );
  }
});

test("trace validator rejects malformed activity before model rendering", async () => {
  const model = await readModel();
  const adversarialFields: Array<[string, unknown]> = [
    ["id", null],
    ["timestamp", "2026-07-14T21:39:00"],
    ["agent", {}],
    ["action", null],
    ["state", []],
  ];
  for (const [field, value] of adversarialFields) {
    await rejectsProjection(
      () =>
        model.fetchNodeTraces(
          options([malformed(validTrace, field, value)]),
        ),
      model.classifyNodeReadError,
    );
  }
});

test("A2A validator rejects malformed cards but preserves evidence fields", async () => {
  const model = await readModel();
  const adversarialFields: Array<[string, unknown]> = [
    ["id", null],
    ["title", []],
    ["body", {}],
    ["status", 0],
    ["created_at", "2026-07-14T21:39:00"],
  ];
  for (const [field, value] of adversarialFields) {
    await rejectsProjection(
      () =>
        model.fetchNodeCards(
          options(
            cardsPayload([malformed(validCard, field, value)]),
          ),
        ),
      model.classifyNodeReadError,
    );
  }
});

test("identity validators reject ambiguous duplicate agent, task, and trace IDs", async () => {
  const model = await readModel();
  for (const operation of [
    () => model.fetchNodeAgents(options([validAgent, validAgent])),
    () => model.fetchNodeTasks(options([validTask, validTask])),
    () => model.fetchNodeTraces(options([validTrace, validTrace])),
  ]) {
    await rejectsProjection(operation, model.classifyNodeReadError);
  }
});

test("panel failure view names blocked, unknown, and unreachable truth", async () => {
  const model = await readModel();
  const cases = [
    {
      kind: "auth",
      truth: "blocked",
      surfaceKind: "unknown",
      title: "BLOCKED · Agent registry authentication rejected",
    },
    {
      kind: "throttle",
      truth: "blocked",
      surfaceKind: "unknown",
      title: "BLOCKED · Agent registry throttled",
    },
    {
      kind: "contract",
      truth: "unknown",
      surfaceKind: "unknown",
      title: "UNKNOWN EVIDENCE · Agent registry contract rejected",
    },
    {
      kind: "projection",
      truth: "unknown",
      surfaceKind: "unknown",
      title: "UNKNOWN EVIDENCE · Agent registry projection rejected",
    },
    {
      kind: "upstream",
      truth: "unreachable",
      surfaceKind: "error",
      title: "Agent registry unreachable",
    },
  ] as const;

  for (const item of cases) {
    const view = model.nodeReadFailureView(
      new model.NodeReadError("safe detail", item.kind, 502),
      "Agent registry",
    );
    assert.deepEqual(
      {
        truth: view.truth,
        surfaceKind: view.surfaceKind,
        title: view.title,
      },
      {
        truth: item.truth,
        surfaceKind: item.surfaceKind,
        title: item.title,
      },
    );
    assert.equal(view.detail, "safe detail");
  }
});
