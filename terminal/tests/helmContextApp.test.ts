import {createHash} from "node:crypto";
import {readFileSync} from "node:fs";
import {describe, expect, test} from "bun:test";

import {createBridgeEventHandler} from "../src/app";
import type {DharmaBridge} from "../src/bridge";
import {HELM_CONTEXT_PROJECTION_NAMES, type HelmContextEnvelope} from "../src/helmContext/types";
import {
  helmContextActionsForBridgeEvent,
  helmContextProjectionLines,
  helmContextRequestPayload,
} from "../src/helmContext/appProjection";
import {decodeHelmContextEnvelope} from "../src/protocol/helmContext";
import {initialState, reduceApp} from "../src/state";
import {requestAuthoritativeResync} from "../src/surfaceAuthority";
import type {AppAction, AppState} from "../src/types";

type MutableJson = null | boolean | number | string | MutableJson[] | {[key: string]: MutableJson};
type MutableEnvelope = {
  schema_version: string;
  generated_at: string;
  expires_at: string;
  runtime_epoch: string;
  synthetic: boolean;
  provider_state_promotion: boolean;
  projections: Record<string, {
    region: string;
    status: string;
    authority: {
      modality: string;
      owner: string;
      source: string;
      observed_at: string;
      expires_at: string | null;
      runtime_epoch: string;
    };
    data: Record<string, MutableJson>;
    unavailable_reason: string | null;
  }>;
  context_digest: string;
};

type SentRequest = {id: string; type: string; payload: Record<string, unknown>};

function compareUnicodeCodePoints(left: string, right: string): number {
  const leftPoints = [...left].map((character) => character.codePointAt(0)!);
  const rightPoints = [...right].map((character) => character.codePointAt(0)!);
  for (let index = 0; index < Math.min(leftPoints.length, rightPoints.length); index += 1) {
    const difference = leftPoints[index]! - rightPoints[index]!;
    if (difference !== 0) return difference;
  }
  return leftPoints.length - rightPoints.length;
}

function canonicalJson(value: MutableJson): string {
  if (value === null || typeof value === "boolean" || typeof value === "number" || typeof value === "string") {
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  return `{${Object.keys(value).sort(compareUnicodeCodePoints).map((key) => (
    `${JSON.stringify(key)}:${canonicalJson(value[key]!)}`
  )).join(",")}}`;
}

function signEnvelope(envelope: MutableEnvelope): MutableEnvelope {
  const unsigned = Object.fromEntries(
    Object.entries(envelope).filter(([key]) => key !== "context_digest"),
  ) as MutableJson;
  envelope.context_digest = `sha256:${createHash("sha256").update(canonicalJson(unsigned), "utf8").digest("hex")}`;
  return envelope;
}

function fixtureEnvelope(
  generatedAt: Date,
  expiresAt: Date,
  unavailableRegion?: string,
): MutableEnvelope {
  const envelope = JSON.parse(readFileSync(new URL(
    "../../tests/fixtures/terminal_bridge/helm_context_v1.json",
    import.meta.url,
  ), "utf8")) as MutableEnvelope;
  envelope.generated_at = generatedAt.toISOString();
  envelope.expires_at = expiresAt.toISOString();
  for (const projection of Object.values(envelope.projections)) {
    projection.authority.observed_at = generatedAt.toISOString();
    projection.authority.expires_at = expiresAt.toISOString();
  }
  if (unavailableRegion) {
    const projection = envelope.projections[unavailableRegion]!;
    projection.status = "unavailable";
    projection.authority.modality = "unknown";
    projection.authority.owner = unavailableRegion === "mission_control" ? "MissionControl" : projection.authority.owner;
    projection.authority.source = unavailableRegion === "mission_control"
      ? "MissionControl.get_snapshot:not_observed"
      : `${projection.authority.source}:not_observed`;
    projection.authority.expires_at = null;
    projection.data = {};
    projection.unavailable_reason = `${unavailableRegion}_owner_not_injected`;
  }
  return signEnvelope(envelope);
}

function freshFixture(now: Date, unavailableRegion?: string): MutableEnvelope {
  return fixtureEnvelope(
    new Date(now.getTime() - 1_000),
    new Date(now.getTime() + 5 * 60_000),
    unavailableRegion,
  );
}

function applyActions(state: AppState, actions: AppAction[]): AppState {
  return actions.reduce(reduceApp, state);
}

function bridgeHarness(): {
  state: () => AppState;
  sent: SentRequest[];
  handler: (event: Record<string, unknown>) => void;
} {
  let state = structuredClone(initialState);
  const sent: SentRequest[] = [];
  const bridge = {
    send(type: string, payload: Record<string, unknown> = {}) {
      const id = `request-${sent.length + 1}`;
      sent.push({id, type, payload});
      return id;
    },
    sendBackground(type: string, payload: Record<string, unknown> = {}) {
      const id = `request-${sent.length + 1}`;
      sent.push({id, type, payload});
      return id;
    },
  } as unknown as DharmaBridge;
  const handler = createBridgeEventHandler({
    dispatch(action) { state = reduceApp(state, action); },
    getState: () => state,
    bridge,
    pendingBootstraps: {current: {}},
  });
  return {state: () => state, sent, handler};
}

function connect(harness: ReturnType<typeof bridgeHarness>): SentRequest {
  harness.handler({
    type: "handshake.result",
    default_provider: "codex",
    default_model: "gpt-5.6-sol",
    providers: [],
  });
  const contextRequest = harness.sent.find((request) => request.type === "helm.context.request");
  expect(contextRequest).toBeDefined();
  return contextRequest!;
}

describe("HELM owner context app boundary", () => {
  test("initial authoritative sync requests the exact current HELM coordinates and records correlation", () => {
    const harness = bridgeHarness();
    const request = connect(harness);

    expect(request.payload).toEqual({
      ui: {
        face: "zen",
        place: "conversation",
        facet: "chat",
        overlay: "none",
        keyboard_focus: "composer",
        available_navigation: ["home", "conversation", "activity", "evidence", "system"],
      },
    });
    expect(harness.state().helmContext).toEqual({pendingRequestId: request.id});
  });

  test("every authoritative resync includes one correlated helm.context request", () => {
    const state: AppState = {
      ...structuredClone(initialState),
      uiMode: {
        ...initialState.uiMode,
        activeTabId: "repo",
        focusedPaneId: "repo",
        keyboardFocus: "navigation",
        layoutMode: "scroll",
      },
    };
    const sent: SentRequest[] = [];
    const bridge = {
      sendBackground(type: string, payload: Record<string, unknown> = {}) {
        const id = `resync-${sent.length + 1}`;
        sent.push({id, type, payload});
        return id;
      },
      send(type: string, payload: Record<string, unknown> = {}) {
        const id = `resync-${sent.length + 1}`;
        sent.push({id, type, payload});
        return id;
      },
    } as unknown as DharmaBridge;
    const payload = helmContextRequestPayload(state);

    requestAuthoritativeResync(bridge, "codex", "gpt-5.6-sol", "responsive", payload);

    expect(sent.filter((request) => request.type === "helm.context.request")).toEqual([{
      id: expect.any(String),
      type: "helm.context.request",
      payload: {
        ui: {
          face: "scroll",
          place: "evidence",
          facet: "repo",
          overlay: "none",
          keyboard_focus: "navigation",
          available_navigation: ["home", "conversation", "activity", "evidence", "system"],
        },
      },
    }]);
  });

  test("only an exact correlated, structurally valid, currently usable result enters app state", () => {
    const now = new Date();
    const harness = bridgeHarness();
    const request = connect(harness);
    const envelope = freshFixture(now);

    harness.handler({type: "helm.context.result", request_id: request.id, envelope});

    expect(harness.state().helmContext.pendingRequestId).toBeUndefined();
    expect(harness.state().helmContext.envelope?.context_digest).toBe(envelope.context_digest);
    expect(harness.state().helmContext.envelope?.projections).toHaveProperty("actions");
  });

  test("mismatched correlation is a no-op and cannot promote an otherwise valid envelope", () => {
    const now = new Date();
    const pending = {pendingRequestId: "context-expected"};
    const actions = helmContextActionsForBridgeEvent(
      {type: "helm.context.result", request_id: "context-attacker", envelope: freshFixture(now)},
      pending,
      now,
    );

    expect(actions).toEqual([]);
    expect(applyActions({...structuredClone(initialState), helmContext: pending}, actions).helmContext).toEqual(pending);
  });

  test.each([
    ["malformed", (now: Date) => {
      const envelope = freshFixture(now);
      envelope.projections.workspace.data.branch = "tampered-after-signing";
      return envelope;
    }],
    ["expired", (now: Date) => fixtureEnvelope(
      new Date(now.getTime() - 10 * 60_000),
      new Date(now.getTime() - 5 * 60_000),
    )],
    ["future", (now: Date) => fixtureEnvelope(
      new Date(now.getTime() + 5 * 60_000),
      new Date(now.getTime() + 10 * 60_000),
    )],
  ])("a correlated %s envelope revokes pending/current owner truth", (_name, build) => {
    const now = new Date();
    const current = decodeHelmContextEnvelope(freshFixture(now)) as HelmContextEnvelope;
    const helmContext = {pendingRequestId: "context-1", envelope: current};
    const actions = helmContextActionsForBridgeEvent(
      {type: "helm.context.result", request_id: "context-1", envelope: build(now)},
      helmContext,
      now,
    );
    const next = applyActions({...structuredClone(initialState), helmContext}, actions);

    expect(actions).toEqual([{type: "helm.context.reset"}]);
    expect(next.helmContext).toEqual({});
  });

  test("bridge disconnect revokes a previously current owner envelope", () => {
    const now = new Date();
    const harness = bridgeHarness();
    const request = connect(harness);
    harness.handler({type: "helm.context.result", request_id: request.id, envelope: freshFixture(now)});
    expect(harness.state().helmContext.envelope).toBeDefined();

    harness.handler({type: "bridge.error", code: "bridge_send_failed", message: "transport gone"});

    expect(harness.state().helmContext).toEqual({});
  });

  test("a later unrelated bridge.error neither wipes owner truth nor clears the pending anchor", () => {
    const now = new Date();
    const current = decodeHelmContextEnvelope(freshFixture(now)) as HelmContextEnvelope;
    const helmContext = {pendingRequestId: "7", envelope: current};

    const errorActions = helmContextActionsForBridgeEvent(
      {type: "bridge.error", request_id: "8", code: "chat_refused", message: "turn refused"},
      helmContext,
      now,
    );
    expect(errorActions).toEqual([]);

    const resultActions = helmContextActionsForBridgeEvent(
      {type: "helm.context.result", request_id: "7", envelope: freshFixture(now)},
      helmContext,
      now,
    );
    expect(resultActions.map((action) => action.type)).toEqual(["helm.context.set"]);
  });

  test("renders exactly twelve owner-stamped lines, including typed unavailable", () => {
    const now = new Date();
    const decoded = decodeHelmContextEnvelope(freshFixture(now, "mission_control"));
    expect(decoded).toBeDefined();
    const lines = helmContextProjectionLines({envelope: decoded}, now);

    expect(lines).toHaveLength(12);
    expect(lines).toEqual(HELM_CONTEXT_PROJECTION_NAMES.map((region) => {
      const projection = decoded!.projections[region];
      return `${region} · status=${projection.status} · owner=${projection.authority.owner} · source=${projection.authority.source} · observed=${projection.authority.observed_at} · expires=${projection.authority.expires_at ?? "none"} · reason=${projection.unavailable_reason ?? "none"}`;
    }));
    expect(lines.find((line) => line.startsWith("mission_control ·"))).toContain(
      "status=unavailable · owner=MissionControl · source=MissionControl.get_snapshot:not_observed",
    );
  });

  test("legacy six-surface booleans cannot synthesize or upgrade owner envelopes", () => {
    let state = structuredClone(initialState);
    for (const surface of ["repo", "control", "sessions", "approvals", "models", "agents"] as const) {
      state = reduceApp(state, {type: "surface.truth.mark", surface});
    }
    expect(Object.values(state.authoritativeSurfaces).every(Boolean)).toBe(true);
    expect(state.helmContext.envelope).toBeUndefined();

    const lines = helmContextProjectionLines(state.helmContext, new Date());
    expect(lines).toHaveLength(12);
    for (const [index, region] of HELM_CONTEXT_PROJECTION_NAMES.entries()) {
      expect(lines[index]).toContain(`${region} · status=unavailable`);
      expect(lines[index]).toContain("reason=owner_projection_not_observed");
      expect(lines[index]).not.toContain("status=observed");
    }
  });
});

describe("HELM owner context slow-result correlation", () => {
  test("a fan-out slower than the resync interval still lands instead of being orphaned by the next tick", () => {
    const now = new Date();
    let state: AppState = structuredClone(initialState);
    state = applyActions(state, [{type: "helm.context.requested", requestId: "7"}]);
    state = applyActions(state, [{type: "helm.context.requested", requestId: "12"}]);
    expect(state.helmContext.pendingRequestId).toBe("7");

    const stale = helmContextActionsForBridgeEvent(
      {type: "helm.context.result", request_id: "3", envelope: freshFixture(now)},
      state.helmContext,
      now,
    );
    expect(stale).toEqual([]);

    const lateFirstReply = helmContextActionsForBridgeEvent(
      {type: "helm.context.result", request_id: "7", envelope: freshFixture(now)},
      state.helmContext,
      now,
    );
    expect(lateFirstReply.map((action) => action.type)).toEqual(["helm.context.set"]);

    const laterTickReply = helmContextActionsForBridgeEvent(
      {type: "helm.context.result", request_id: "12", envelope: freshFixture(now)},
      state.helmContext,
      now,
    );
    expect(laterTickReply.map((action) => action.type)).toEqual(["helm.context.set"]);

    state = applyActions(state, laterTickReply);
    expect(state.helmContext.pendingRequestId).toBeUndefined();
    expect(state.helmContext.envelope).toBeDefined();
    state = applyActions(state, [{type: "helm.context.requested", requestId: "20"}]);
    expect(state.helmContext.pendingRequestId).toBe("20");
  });

  test("non-numeric correlation ids still require an exact match", () => {
    const now = new Date();
    const actions = helmContextActionsForBridgeEvent(
      {type: "helm.context.result", request_id: "context-later", envelope: freshFixture(now)},
      {pendingRequestId: "context-expected"},
      now,
    );
    expect(actions).toEqual([]);
  });
});
