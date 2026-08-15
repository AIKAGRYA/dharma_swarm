import {createHash} from "node:crypto";
import {readFileSync} from "node:fs";
import {describe, expect, test} from "bun:test";
import {HELM_CONTEXT_PROJECTION_NAMES} from "../src/helmContext/types";
import {
  decodeHelmContextEnvelope,
  helmContextEnvelopeIsUsableAt,
  helmContextEnvelopeFromEvent,
} from "../src/protocol/helmContext";
type MutableJsonValue = string | number | boolean | null | MutableJsonValue[] | MutableObject;
type MutableObject = {[key: string]: MutableJsonValue};
type MutableAuthority = MutableObject & {
  modality: string;
  owner: string;
  source: string;
  observed_at: string;
  expires_at: string | null;
  runtime_epoch: string;
};
type MutableProjection = MutableObject & {
  region: string;
  status: string;
  authority: MutableAuthority;
  data: MutableObject;
  unavailable_reason: string | null;
};
type MutableEnvelope = MutableObject & {
  schema_version: string;
  generated_at: string;
  expires_at: string;
  runtime_epoch: string;
  synthetic: boolean;
  provider_state_promotion: boolean;
  projections: Record<string, MutableProjection>;
  context_digest: string;
};
function compareUnicodeCodePoints(left: string, right: string): number {
  const leftPoints = [...left].map((character) => character.codePointAt(0)!);
  const rightPoints = [...right].map((character) => character.codePointAt(0)!);
  const sharedLength = Math.min(leftPoints.length, rightPoints.length);
  for (let index = 0; index < sharedLength; index += 1) {
    const difference = leftPoints[index]! - rightPoints[index]!;
    if (difference !== 0) {
      return difference;
    }
  }
  return leftPoints.length - rightPoints.length;
}
function canonicalJson(value: unknown): string {
  if (value === null || typeof value === "boolean" || typeof value === "number" || typeof value === "string") {
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) {
    return `[${value.map(canonicalJson).join(",")}]`;
  }
  const object = value as MutableObject;
  return `{${Object.keys(object).sort(compareUnicodeCodePoints).map((key) => (
    `${JSON.stringify(key)}:${canonicalJson(object[key])}`
  )).join(",")}}`;
}
function signEnvelope(envelope: MutableEnvelope): MutableEnvelope {
  const unsigned = Object.fromEntries(
    Object.entries(envelope).filter(([key]) => key !== "context_digest"),
  );
  envelope.context_digest = `sha256:${createHash("sha256").update(canonicalJson(unsigned), "utf8").digest("hex")}`;
  return envelope;
}
function authority(
  modality: "observed" | "configured" | "unverified" | "stale" | "unknown" | "held",
  overrides: Partial<MutableAuthority> = {},
): MutableAuthority {
  return {
    modality,
    owner: "FixtureOwner",
    source: "fixture.owner.read_projection",
    observed_at: "2026-08-15T09:59:00Z",
    expires_at: modality === "unknown" ? null : "2026-08-15T10:04:00Z",
    runtime_epoch: "terminal-bridge:epoch-a",
    ...overrides,
  };
}
function projection(
  region: string,
  status: string = "observed",
  data: MutableObject = defaultRegionData(region),
): MutableProjection {
  const modality = status === "unavailable" ? "unknown" : status;
  const ownerStamp = status === "unavailable"
    ? {owner: "MissionControl", source: "MissionControl.get_snapshot:not_observed"}
    : {owner: "SyntheticHelmContextFixture", source: `synthetic.${region}`};
  return {
    region,
    status,
    authority: authority(modality as Parameters<typeof authority>[0], ownerStamp),
    data: status === "unavailable" ? {} : data,
    unavailable_reason: status === "unavailable" ? `${region}_owner_not_injected` : null,
  };
}
function collection(items: MutableJsonValue[] = []): MutableObject {
  return {items, total: items.length, truncated: false};
}

function canonicalNavigation(): MutableObject {
  const keys = ["id", "label", "key", "command", "target_kind", "target_id", "resulting_place", "available"];
  const rows: MutableJsonValue[][] = [
    ["home", "Home (Control facet)", null, "open control", "facet", "control", "home", true], ["conversation", "Conversation", "Esc then Ctrl+G", "open chat", "facet", "chat", "conversation", true],
    ["activity", "Activity (Agents facet)", "Esc then Ctrl+A", "open agents", "facet", "agents", "activity", true], ["evidence", "Evidence (Repository facet)", "Esc then Ctrl+R", "open repo", "facet", "repo", "evidence", true],
    ["system", "System (Commands facet)", "Esc then Ctrl+M", "open commands", "facet", "commands", "system", true], ["face_toggle", "Quiet Field / Full Helm", "F2", "/cockpit", "face", null, null, true],
    ["pane_switcher", "Pane switcher", "Esc then Ctrl+K", null, "overlay", "paneSwitcher", null, true], ["model_picker", "Model picker", "Esc then Ctrl+P", "/model", "overlay", "modelPicker", null, true],
    ["receipts", "Receipts", null, null, "projection", "receipts", "evidence", false], ["inspector", "Inspector", null, null, "feature", "inspector", null, false],
  ];
  return collection(rows.map((row) => Object.fromEntries(keys.map((key, index) => [key, row[index]!])) as MutableObject));
}

function defaultRegionData(region: string): MutableObject {
  const data: Record<string, MutableObject> = {
    workspace: {
      workspace_path: "/srv/dharma_swarm", workspace: "dharma_swarm",
      repository: "dharma_swarm", repository_identity: "AIKAGRYA/dharma_swarm",
      remote: "github.com/AIKAGRYA/dharma_swarm", branch: "agent/fixture", head: "abc123",
      upstream: "origin/agent/fixture", ahead: 1, behind: 0, staged: 0, unstaged: 1,
      untracked: 0,
    },
    bridge_session: {
      bridge_status: "connected", active_session_id: "session-1", active_phase: "streaming",
      requested_provider_id: "codex_text", requested_model_id: "gpt-5.6-sol",
      served_provider_id: null, served_model_id: null, served_identity_source: "unavailable",
      served_identity_observed_at: null, route_evidence_expires_at: null,
      route_evidence_freshness: "unavailable", route_receipt_ref: null,
      route_receipt_sha256: null, route_verifier_id: null, route_verifier_version: null,
      route_evidence_synthetic: null, route_verdict: "UNKNOWN",
      route_verdict_reason: "route_not_evaluated", route_exact_model_proven: false,
      route_seat_id: null, route_verification_evaluated_at: null,
    },
    ui: {
      face: "zen", place: "conversation", facet: "chat", overlay: "none",
      keyboard_focus: "composer", navigation: canonicalNavigation(),
    },
    mission_control: {mission: {
      mission_id: "mission-1", title: "Bounded mission", status: "active",
      updated_at: "2026-08-15T09:58:00Z",
    }},
    task_board: {tasks: collection([{
      task_id: "task-1", title: "Bounded task", status: "pending", priority: "normal",
      assigned_to: null, depends_on_count: 0, blocked_by_count: 0,
      updated_at: "2026-08-15T09:58:00Z",
    }])},
    runtime_state: {sessions: collection([{
      session_id: "run-1", status: "active", current_task_id: "task-1",
      active_bundle_id: null, updated_at: "2026-08-15T09:58:00Z",
      source_runtime_epoch: "terminal-bridge:epoch-a",
    }])},
    session: {sessions: collection([{
      session_id: "chat-1", status: "active", title: "Helm chat", provider_id: "codex_text",
      model_id: "gpt-5.6-sol", total_turns: 2, updated_at: "2026-08-15T09:58:00Z",
      runtime_owner_id: "terminal-bridge:epoch-a",
    }])},
    receipts: {receipts: collection([{
      receipt_id: "receipt-1", receipt_type: "dispatch", status: "recorded", run_id: "run-1",
      task_id: "task-1", agent_id: "agent-1", created_at: "2026-08-15T09:58:00Z",
    }])},
    swarm: {
      agents: collection([{agent_id: "agent-1", name: "Agent 1", role: "worker", status: "idle",
        current_task: null, provider: "local", model: "bounded", last_heartbeat: null}]),
      tasks_pending: 1, tasks_running: 0, tasks_completed: 0, tasks_failed: 0,
      source_runtime_epoch: "terminal-bridge:epoch-a",
    },
    a2a: {contacts: collection([{
      agent_uid: "agent-1", kind: "local_agent", display_name: "Agent 1", capability_count: 2,
    }])},
    evolution: {entries: collection([{
      entry_id: "entry-1", timestamp: "2026-08-15T09:58:00Z", parent_id: null,
      component: "helm", change_type: "repair", spec_ref: null, commit_hash: null,
      evidence_tier: "synthetic", promotion_state: "held", status: "proposed",
      agent_id: "agent-1", model: "bounded", tokens_used: 10, gates_passed_count: 0,
      gates_failed_count: 0,
    }])},
    actions: {actions: collection([{
      action_id: "swarm.plan", label: "Plan a governed swarm objective", owner: "TerminalBridge",
      effects: ["construct_plan"], risk: "safe_read", requires_approval: true,
      reversible: true, cancel_action_id: "swarm.cancel",
    }])},
  };
  return structuredClone(data[region]!);
}

function buildEnvelope(): MutableEnvelope {
  const projections = Object.fromEntries(
    HELM_CONTEXT_PROJECTION_NAMES.map((region) => [region, projection(region)]),
  );
  projections.mission_control = projection("mission_control", "unavailable");
  projections.runtime_state = projection("runtime_state", "stale");
  projections.runtime_state.authority.expires_at = "2026-08-15T09:59:30Z";
  projections.actions = projection("actions", "held");
  return signEnvelope({
    schema_version: "dharma.helm.context.v1",
    generated_at: "2026-08-15T10:00:00Z",
    expires_at: "2026-08-15T10:05:00Z",
    runtime_epoch: "terminal-bridge:epoch-a",
    synthetic: true,
    provider_state_promotion: false,
    projections,
    context_digest: "",
  });
}

function mutateAndSign(mutate: (envelope: MutableEnvelope) => void): MutableEnvelope {
  const envelope = structuredClone(buildEnvelope());
  mutate(envelope);
  return signEnvelope(envelope);
}

function makeAvailable(envelope: MutableEnvelope, region: string): MutableProjection {
  const block = envelope.projections[region]!;
  block.status = "observed";
  block.authority.modality = "observed";
  block.authority.owner = "SyntheticHelmContextFixture";
  block.authority.source = `synthetic.${region}`;
  block.authority.expires_at = "2026-08-15T10:04:00Z";
  block.data = defaultRegionData(region);
  block.unavailable_reason = null;
  return block;
}

function setFreshRoute(envelope: MutableEnvelope): MutableObject {
  const data = envelope.projections.bridge_session.data;
  Object.assign(data, {
    served_provider_id: "codex_text", served_model_id: "gpt-5.6-sol",
    served_identity_source: "provider_response_via_route_evaluator",
    served_identity_observed_at: "2026-08-15T09:58:00Z",
    route_evidence_expires_at: "2026-08-15T10:04:00Z", route_evidence_freshness: "fresh",
    route_receipt_ref: "sessions/route-receipt", route_receipt_sha256: "a".repeat(64),
    route_verifier_id: "route-receipt-verifier", route_verifier_version: "1",
    route_evidence_synthetic: false, route_verdict: "ON_CALL", route_verdict_reason: "verified",
    route_exact_model_proven: true, route_seat_id: "sol-5.6",
    route_verification_evaluated_at: "2026-08-15T09:59:00Z",
  });
  return data;
}

describe("HelmContextEnvelope v1 decoder", () => {
  test("decodes the canonical Python-generated synthetic fixture", () => {
    const fixture = JSON.parse(readFileSync(new URL(
      "../../tests/fixtures/terminal_bridge/helm_context_v1.json",
      import.meta.url,
    ), "utf8"));
    const decoded = decodeHelmContextEnvelope(fixture);

    expect(decoded?.runtime_epoch).toBe("runtime-epoch-test");
    expect(decoded?.projections.ui.data.place).toBe("conversation");
    expect(decoded?.projections.mission_control.status).toBe("configured");
  });

  test("accepts the exact owner-stamped envelope without synthesizing truth", () => {
    const decoded = decodeHelmContextEnvelope(buildEnvelope());

    expect(decoded?.schema_version).toBe("dharma.helm.context.v1");
    expect(decoded?.synthetic).toBe(true);
    expect(decoded?.provider_state_promotion).toBe(false);
    expect(Object.keys(decoded?.projections ?? {})).toEqual(HELM_CONTEXT_PROJECTION_NAMES);
    expect(decoded?.projections.runtime_state.status).toBe("stale");
    expect(decoded?.projections.actions.authority.modality).toBe("held");
  });

  test("accepts an explicit unavailable owner without promoting it to unknown live state", () => {
    const decoded = decodeHelmContextEnvelope(buildEnvelope());
    const missing = decoded?.projections.mission_control;

    expect(missing?.status).toBe("unavailable");
    expect(missing?.authority.modality).toBe("unknown");
    expect(missing?.data).toEqual({});
    expect(missing?.unavailable_reason).toBe("mission_control_owner_not_injected");
  });

  test("rejects wrong versions, unknown keys, missing regions, and mismatched region labels", () => {
    expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => {
      envelope.schema_version = "dharma.helm.context.v2";
    }))).toBeUndefined();
    expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => {
      envelope.extra = true;
    }))).toBeUndefined();
    expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => {
      envelope.projections.workspace.extra = true;
    }))).toBeUndefined();
    expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => {
      delete envelope.projections.receipts;
    }))).toBeUndefined();
    expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => {
      envelope.projections.workspace.region = "runtime_state";
    }))).toBeUndefined();
  });

  test("enforces exact typed data for every available region", () => {
    const allAvailable = mutateAndSign((envelope) => {
      for (const region of HELM_CONTEXT_PROJECTION_NAMES) makeAvailable(envelope, region);
    });
    expect(decodeHelmContextEnvelope(allAvailable)).toBeDefined();
    for (const region of HELM_CONTEXT_PROJECTION_NAMES) {
      expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => {
        makeAvailable(envelope, region).data.unexpected = true;
      }))).toBeUndefined();
      expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => {
        const data = makeAvailable(envelope, region).data;
        delete data[Object.keys(data)[0]!];
      }))).toBeUndefined();
    }
    const invalid: Array<[string, (data: MutableObject) => void]> = [
      ["workspace", (data) => { data.ahead = "one"; }],
      ["bridge_session", (data) => { data.active_phase = "narrating"; }],
      ["ui", (data) => { data.face = "full"; }],
      ["mission_control", (data) => { (data.mission as MutableObject).updated_at = "today"; }],
      ["task_board", (data) => { ((data.tasks as MutableObject).items as MutableObject[])[0]!.updated_at = "today"; }],
      ["runtime_state", (data) => { ((data.sessions as MutableObject).items as MutableObject[])[0]!.updated_at = "today"; }],
      ["session", (data) => { ((data.sessions as MutableObject).items as MutableObject[])[0]!.total_turns = -1; }],
      ["receipts", (data) => { ((data.receipts as MutableObject).items as MutableObject[])[0]!.created_at = null; }],
      ["swarm", (data) => { data.tasks_running = 1.5; }],
      ["a2a", (data) => { ((data.contacts as MutableObject).items as MutableObject[])[0]!.capability_count = -1; }],
      ["evolution", (data) => { ((data.entries as MutableObject).items as MutableObject[])[0]!.tokens_used = "ten"; }],
      ["actions", (data) => { ((data.actions as MutableObject).items as MutableObject[])[0]!.requires_approval = "yes"; }],
    ];
    for (const [region, mutate] of invalid) {
      expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => {
        mutate(makeAvailable(envelope, region).data);
      }))).toBeUndefined();
    }
    for (const path of ["/srv/dharma_swarm/", "/srv//dharma_swarm"]) {
      expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => {
        envelope.projections.workspace.data.workspace_path = path;
      }))).toBeUndefined();
    }
  });

  test("rejects every place and facet pairing outside shellModel ownership", () => {
    const ownership: Record<string, readonly string[]> = {
      home: ["mission", "control"], conversation: ["chat", "sessions"],
      activity: ["agents", "evolution", "thinking", "tools", "timeline", "approvals"],
      evidence: ["repo", "ontology"], system: ["commands", "models", "runtime"],
    };
    const facets = Object.values(ownership).flat();
    for (const [place, allowedFacets] of Object.entries(ownership)) {
      for (const facet of facets) {
        const candidate = mutateAndSign((envelope) => {
          envelope.projections.ui.data.place = place;
          envelope.projections.ui.data.facet = facet;
        });
        expect(decodeHelmContextEnvelope(candidate) !== undefined).toBe(allowedFacets.includes(facet));
      }
    }
  });

  test("rejects malformed and internally inconsistent RFC3339 expiry", () => {
    expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => {
      envelope.generated_at = "2026-08-15T10:00:00";
    }))).toBeUndefined();
    expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => {
      envelope.expires_at = "2026-08-15T10:00:00Z";
    }))).toBeUndefined();
    expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => {
      envelope.expires_at = "2026-08-15T11:00:01Z";
    }))).toBeUndefined();
    expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => {
      envelope.projections.workspace.authority.expires_at = "2026-08-15T09:59:30Z";
    }))).toBeUndefined();
    expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => {
      envelope.projections.runtime_state.authority.expires_at = "2026-08-15T10:04:00Z";
    }))).toBeUndefined();
    expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => {
      envelope.projections.workspace.authority.observed_at = "2026-08-15T10:00:01Z";
    }))).toBeUndefined();
    expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => {
      envelope.projections.workspace.authority.expires_at = "2026-08-15T10:05:01Z";
    }))).toBeUndefined();
    for (const [generatedAt, expiresAt] of [
      ["0001-01-01T00:00:00+23:59", "0001-01-01T00:01:00+23:59"],
      ["9999-12-31T23:58:59-23:59", "9999-12-31T23:59:59-23:59"],
    ]) {
      expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => {
        envelope.generated_at = generatedAt;
        envelope.expires_at = expiresAt;
        for (const block of Object.values(envelope.projections)) {
          block.authority.observed_at = generatedAt;
          if (block.status === "stale") block.status = block.authority.modality = "observed";
          if (block.status !== "unavailable") block.authority.expires_at = expiresAt;
        }
      }))).toBeUndefined();
    }
  });

  test("requires current epoch for fresh authority but retains stale owner epoch", () => {
    expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => {
      envelope.projections.a2a.authority.runtime_epoch = "terminal-bridge:old";
    }))).toBeUndefined();
    expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => {
      envelope.runtime_epoch = "";
    }))).toBeUndefined();
    expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => {
      envelope.projections.runtime_state.authority.runtime_epoch = "runtime-owner:prior";
    }))).toBeDefined();
  });

  test("rejects every contradictory served-route proof state", () => {
    expect(decodeHelmContextEnvelope(mutateAndSign(setFreshRoute))).toBeDefined();
    const contradictions: Array<(data: MutableObject) => void> = [
      (data) => { data.route_exact_model_proven = false; },
      (data) => { data.route_verdict = "UNKNOWN"; },
      (data) => { data.route_evidence_synthetic = true; },
      (data) => { data.route_verdict_reason = "provider_claimed_verified"; },
      (data) => { data.route_receipt_sha256 = "not-a-sha"; },
      (data) => { data.route_evidence_expires_at = "2026-08-15T10:00:00Z"; },
      (data) => { data.served_identity_observed_at = "2026-08-15T10:00:01Z"; },
      (data) => { data.route_verification_evaluated_at = "2026-08-15T10:00:01Z"; },
      (data) => { data.served_identity_observed_at = "2026-08-15T09:59:01Z"; },
      (data) => { data.active_session_id = null; },
      (data) => { data.requested_model_id = null; },
    ];
    for (const mutate of contradictions) {
      expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => mutate(setFreshRoute(envelope))))).toBeUndefined();
    }
    for (const field of [
      "served_provider_id", "served_model_id", "served_identity_observed_at", "route_evidence_expires_at",
      "route_receipt_ref", "route_receipt_sha256", "route_verifier_id", "route_verifier_version",
      "route_evidence_synthetic", "route_seat_id", "route_verification_evaluated_at",
    ]) {
      expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => {
        setFreshRoute(envelope)[field] = null;
      }))).toBeUndefined();
    }
    for (const field of ["served_provider_id", "served_model_id", "route_receipt_ref", "route_verifier_id", "route_verifier_version", "route_seat_id"]) {
      expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => {
        setFreshRoute(envelope)[field] = "";
      }))).toBeUndefined();
    }
    const unavailableEvidence: Record<string, MutableJsonValue> = {
      served_provider_id: "provider", served_model_id: "model",
      served_identity_observed_at: "2026-08-15T09:58:00Z",
      route_evidence_expires_at: "2026-08-15T10:04:00Z", route_receipt_ref: "receipt",
      route_receipt_sha256: "a".repeat(64), route_verifier_id: "verifier", route_verifier_version: "1",
      route_evidence_synthetic: false, route_seat_id: "seat",
      route_verification_evaluated_at: "2026-08-15T09:59:00Z",
    };
    for (const [field, value] of Object.entries(unavailableEvidence)) {
      expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => {
        envelope.projections.bridge_session.data[field] = value;
      }))).toBeUndefined();
    }
    expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => {
      Object.assign(envelope.projections.bridge_session.data, {
        route_evidence_freshness: "selected_route_mismatch", route_verdict_reason: "selected_route_mismatch",
        route_seat_id: "sol-5.6", route_verification_evaluated_at: "2026-08-15T09:59:00Z",
      });
    }))).toBeDefined();
    const expired = (envelope: MutableEnvelope): MutableObject => {
      const data = setFreshRoute(envelope);
      Object.assign(data, {route_evidence_freshness: "expired", route_evidence_expires_at: "2026-08-15T09:59:59Z", route_verdict: "UNKNOWN", route_verdict_reason: "cached_route_evidence_expired", route_exact_model_proven: false});
      return data;
    };
    expect(decodeHelmContextEnvelope(mutateAndSign(expired))).toBeDefined();
    expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => { expired(envelope).route_receipt_ref = null; }))).toBeUndefined();
    expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => { expired(envelope).route_receipt_sha256 = "bad"; }))).toBeUndefined();
  });

  test("rejects owner observations after their projection or envelope observation", () => {
    const future = "2026-08-15T10:00:01Z";
    const mutations: Array<(envelope: MutableEnvelope) => void> = [
      (envelope) => { setFreshRoute(envelope).served_identity_observed_at = future; },
      (envelope) => { (makeAvailable(envelope, "mission_control").data.mission as MutableObject).updated_at = future; },
      (envelope) => { (((envelope.projections.task_board.data.tasks as MutableObject).items as MutableObject[])[0]!).updated_at = future; },
      (envelope) => { (((envelope.projections.runtime_state.data.sessions as MutableObject).items as MutableObject[])[0]!).updated_at = future; },
      (envelope) => { (((envelope.projections.session.data.sessions as MutableObject).items as MutableObject[])[0]!).updated_at = future; },
      (envelope) => { (((envelope.projections.receipts.data.receipts as MutableObject).items as MutableObject[])[0]!).created_at = future; },
      (envelope) => { (((envelope.projections.swarm.data.agents as MutableObject).items as MutableObject[])[0]!).last_heartbeat = future; },
      (envelope) => { (((envelope.projections.evolution.data.entries as MutableObject).items as MutableObject[])[0]!).timestamp = future; },
    ];
    for (const mutate of mutations) {
      expect(decodeHelmContextEnvelope(mutateAndSign(mutate))).toBeUndefined();
    }
    expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => {
      (makeAvailable(envelope, "mission_control").data.mission as MutableObject).updated_at = "2026-08-15T09:59:30Z";
    }))).toBeUndefined();
  });

  test("rejects any provider truth promotion even when the digest is otherwise valid", () => {
    expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => {
      envelope.provider_state_promotion = true;
    }))).toBeUndefined();
    expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => {
      envelope.projections.session.data.state_promotion_allowed = false;
    }))).toBeUndefined();
    expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => {
      envelope.projections.session.data.nested = {authority_stamp: {modality: "observed"}};
    }))).toBeUndefined();
    expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => {
      envelope.projections.workspace.authority.owner = "Attacker";
      envelope.projections.workspace.authority.source = "attacker.injected";
    }))).toBeUndefined();
    expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => {
      Object.setPrototypeOf(envelope.projections.workspace.data, {
        toJSON: () => ({provider_state_promotion: true, token: `sk-proj-${"x".repeat(24)}`}),
      });
    }))).toBeUndefined();
  });

  test("rejects ambiguous or unauthorized action descriptors", () => {
    const invalidActions: Array<(item: MutableObject) => void> = [
      (item) => { item.action_id = ""; },
      (item) => { item.label = ""; },
      (item) => { item.owner = ""; },
      (item) => { item.effects = []; },
      (item) => { item.effects = [""]; },
      (item) => { item.risk = "workspace_mutation"; item.requires_approval = false; },
      (item) => { item.reversible = true; item.cancel_action_id = null; },
      (item) => { item.reversible = false; item.cancel_action_id = "swarm.cancel"; },
      (item) => { item.reversible = false; item.cancel_action_id = ""; },
    ];
    for (const mutate of invalidActions) {
      expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => {
        const actions = envelope.projections.actions.data.actions as MutableObject;
        mutate((actions.items as MutableObject[])[0]!);
      }))).toBeUndefined();
    }
  });

  test("rejects secret-looking projection content but accepts an explicit redaction marker", () => {
    expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => {
      envelope.projections.bridge_session.data.authorization = "Bearer abcdefghijklmnop";
    }))).toBeUndefined();
    expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => {
      envelope.projections.bridge_session.data.note = "-----BEGIN PRIVATE KEY-----";
    }))).toBeUndefined();
    expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => {
      envelope.projections.bridge_session.data["api-key"] = "not-redacted";
    }))).toBeUndefined();
    for (const [key, value] of [
      ["OPENAI_API_KEY", "sk-proj-abcdefghijklmnopqrstuvwxyz"],
      ["client-secret", "opaque-but-sensitive"],
      ["note", "provider failed: Bearer abcdefghijklmnop"],
    ]) {
      expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => {
        envelope.projections.bridge_session.data[key] = value;
      }))).toBeUndefined();
    }
    for (const value of [
      `sk-or-v1-${"a".repeat(48)}`, `xai-${"b".repeat(48)}`, `AIza${"c".repeat(8)}`,
      ...["gho_", "ghu_", "ghs_", "ghr_"].map((prefix) => `${prefix}${"d".repeat(32)}`),
      ...["xapp-", "xoxa-", "xoxe-", "xoxr-"].map((prefix) => `${prefix}${"e".repeat(32)}`),
      ...["xoxc-", "xoxd-", "xoxs-"].map((prefix) => `${prefix}${"f".repeat(32)}`),
      "https://:password@example.invalid", "https://user:@example.invalid",
      "https://token@example.invalid", "https://user%3Apass@example.invalid",
      "https://operator:password123@example.invalid/path",
    ]) {
      expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => {
        envelope.projections.bridge_session.data.route_verdict_reason = value;
      }))).toBeUndefined();
    }
    for (const hostile of ["line\nfeed", "delete\u007f", "c1\u0085", "rtl\u202e", "ltr\u202d", "isolate\u2066", "zero\u200bwidth"]) {
      expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => {
        envelope.projections.workspace.data.branch = hostile;
      }))).toBeUndefined();
    }

    const redacted = mutateAndSign((envelope) => {
      envelope.projections.bridge_session.data.route_verdict_reason = "[REDACTED]";
    });
    expect(decodeHelmContextEnvelope(
      redacted,
    )?.projections.bridge_session.data.route_verdict_reason).toBe("[REDACTED]");
    for (const benign of ["ghu_x", "ghs_x", "ghr_x", "AKIAshort", "sk-or-v1-x"]) {
      expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => {
        envelope.projections.workspace.data.branch = benign;
      }))?.projections.workspace.data.branch).toBe(benign);
    }
  });

  test("enforces UTF-8 envelope, string, collection, and nesting bounds", () => {
    expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => {
      envelope.projections.workspace.data.branch = "界".repeat(4097);
    }))).toBeUndefined();
    expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => {
      envelope.projections.workspace.data.branch = "\uD800";
    }))).toBeUndefined();
    expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => {
      envelope.projections.workspace.data.branch = "contains\0nul";
    }))).toBeUndefined();
    expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => {
      envelope.projections.workspace.data["k".repeat(129)] = true;
    }))).toBeUndefined();
    expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => {
      const actions = envelope.projections.actions.data.actions as MutableObject;
      const base = (((defaultRegionData("actions").actions as MutableObject)
        .items as MutableObject[])[0]!);
      actions.items = Array.from({length: 65}, () => structuredClone(base));
      actions.total = 65;
    }))).toBeUndefined();
    expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => {
      (envelope.projections.actions.data.actions as MutableObject).truncated = true;
    }))).toBeUndefined();
    expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => {
      const navigation = envelope.projections.ui.data.navigation as MutableObject;
      navigation.items = new Array<MutableJsonValue>(10);
    }))).toBeUndefined();
    expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => {
      envelope.projections.workspace.data.branch = "界".repeat(22000);
    }))).toBeUndefined();
    const exactly64Effects = mutateAndSign((envelope) => {
      const actions = envelope.projections.actions.data.actions as MutableObject;
      const item = (actions.items as MutableObject[])[0]!;
      item.effects = Array.from({length: 64}, (_, index) => `effect-${index}`);
    });
    expect(decodeHelmContextEnvelope(exactly64Effects)).toBeDefined();
    expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => {
      const actions = envelope.projections.actions.data.actions as MutableObject;
      const item = (actions.items as MutableObject[])[0]!;
      item.effects = Array.from({length: 65}, (_, index) => `effect-${index}`);
    }))).toBeUndefined();
    expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => {
      const actions = envelope.projections.actions.data.actions as MutableObject;
      const base = ((actions.items as MutableObject[])[0]!);
      actions.items = Array.from({length: 64}, (_, index) => ({
        ...structuredClone(base), effects: Array.from({length: 32}, () => `effect-${index}`),
      }));
      actions.total = 64;
    }))).toBeUndefined();
    expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => {
      setFreshRoute(envelope).route_evidence_expires_at = "2026-08-16T09:58:00.000001Z";
    }))).toBeUndefined();
  });

  test("rejects non-JSON numeric values and floats so the Python digest remains reproducible", () => {
    for (const value of [1.5, Number.NaN, Number.POSITIVE_INFINITY, Number.MAX_SAFE_INTEGER + 1]) {
      expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => {
        (envelope.projections.runtime_state.data.sessions as MutableObject).total = value;
      }))).toBeUndefined();
    }
  });

  test("verifies the canonical context digest with Unicode scalar values", () => {
    const envelope = mutateAndSign((candidate) => {
      candidate.projections.workspace.data.branch = "\u{10000}\uE000";
    });
    expect(decodeHelmContextEnvelope(envelope)).toBeDefined();

    envelope.projections.workspace.data.branch = "tampered";
    expect(decodeHelmContextEnvelope(envelope)).toBeUndefined();
    envelope.context_digest = "sha256:ABCDEF".padEnd(71, "0");
    expect(decodeHelmContextEnvelope(envelope)).toBeUndefined();
  });

  test("enforces unavailable reason/data and status/modality non-coercions", () => {
    expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => {
      envelope.projections.mission_control.unavailable_reason = null;
    }))).toBeUndefined();
    expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => {
      envelope.projections.mission_control.data = {claimed_live: true};
    }))).toBeUndefined();
    expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => {
      envelope.projections.workspace.unavailable_reason = "not_relevant";
    }))).toBeUndefined();
    expect(decodeHelmContextEnvelope(mutateAndSign((envelope) => {
      envelope.projections.workspace.status = "observed";
      envelope.projections.workspace.authority.modality = "configured";
    }))).toBeUndefined();
  });

  test("decodes only an exactly correlated helm.context.result wrapper", () => {
    const event = {
      type: "helm.context.result",
      request_id: "context-1",
      envelope: buildEnvelope(),
    };
    expect(helmContextEnvelopeFromEvent(event)?.request_id).toBe("context-1");
    expect(helmContextEnvelopeFromEvent({...event, request_id: "   "})).toBeUndefined();
    expect(helmContextEnvelopeFromEvent({...event, type: "helm.context"})).toBeUndefined();
    expect(helmContextEnvelopeFromEvent({...event, payload: event.envelope})).toBeUndefined();
    expect(helmContextEnvelopeFromEvent({...event, extra: true})).toBeUndefined();
    expect(helmContextEnvelopeFromEvent({...event, request_id: "sk-proj-abcdefghijklmnopqrstuvwxyz"})).toBeUndefined();
    expect(helmContextEnvelopeFromEvent({...event, request_id: "A9._:@/-"})?.request_id).toBe("A9._:@/-");
    for (const request_id of ["日本語", "bad!id", "rtl\u202e", "ltr\u202d", "isolate\u2067", "zero\u200bwidth", "del\u007f", "c1\u0085"]) {
      expect(helmContextEnvelopeFromEvent({...event, request_id})).toBeUndefined();
    }
  });

  test("freezes a detached envelope and evaluates expiry only at use time", () => {
    const source = buildEnvelope();
    const decoded = decodeHelmContextEnvelope(source)!;
    source.projections.workspace.data.branch = "mutated input";
    expect(decoded.projections.workspace.data.branch).toBe("agent/fixture");
    expect(Object.isFrozen(decoded.projections.workspace.data)).toBe(true);
    expect(() => {
      (decoded.projections.workspace.data as MutableObject).claimed_live = true;
    }).toThrow();
    expect(helmContextEnvelopeIsUsableAt(decoded, new Date("2026-08-15T10:02:00Z"))).toBe(true);
    expect(helmContextEnvelopeIsUsableAt(decoded, new Date("2026-08-15T10:05:00Z"))).toBe(false);
    expect(helmContextEnvelopeIsUsableAt(decoded, new Date("2020-01-01T00:00:00Z"))).toBe(false);
    const routeExpiresFirst = decodeHelmContextEnvelope(mutateAndSign((envelope) => {
      setFreshRoute(envelope).route_evidence_expires_at = "2026-08-15T10:03:00Z";
    }))!;
    expect(helmContextEnvelopeIsUsableAt(routeExpiresFirst, new Date("2026-08-15T10:02:59Z"))).toBe(true);
    expect(helmContextEnvelopeIsUsableAt(routeExpiresFirst, new Date("2026-08-15T10:03:00Z"))).toBe(false);
    const projectionExpiresFirst = decodeHelmContextEnvelope(mutateAndSign((envelope) => {
      envelope.projections.workspace.authority.expires_at = "2026-08-15T10:01:00Z";
    }))!;
    expect(helmContextEnvelopeIsUsableAt(projectionExpiresFirst, new Date("2026-08-15T10:01:00Z"))).toBe(false);
  });
});
