import assert from "node:assert/strict";
import test from "node:test";

import {
  buildAgentCardComparisonRows,
  summarizeAgentCardComparisonRows,
} from "./agentCardComparison.ts";
import type { AgentCardOut } from "./types.ts";

function card(overrides: Partial<AgentCardOut>): AgentCardOut {
  return {
    schema_version: "dharma.agent_card.meishi.v0",
    agent_uid: "agent",
    display_name: "Agent",
    callsign: "agent",
    role: "builder",
    status: "idle",
    endpoint: "local://",
    provider: "openai",
    model: "codex",
    harness: "codex_cli",
    department: "",
    squad_id: "",
    team_id: "",
    authority: "",
    card_names: [],
    capabilities: [],
    skills: [],
    semantic: {},
    a2a: { card_count_for_agent: 1 },
    registration: {},
    identity_invariant: {},
    authority_passport: {},
    living_dock: {},
    nats: { subjects: ["dharma.agent.agent.inbox"] },
    handoff: {
      public_card_ready: true,
      extended_card_ready: true,
      operator_card_ready: true,
      suggested_subjects: [],
    },
    sources: { a2a_card: ["/tmp/card.json"], registration: ["/tmp/reg.json"] },
    findings: [],
    trust_grade: "verified",
    ...overrides,
  };
}

test("buildAgentCardComparisonRows extracts stable side-by-side fields", () => {
  const rows = buildAgentCardComparisonRows([
    card({
      agent_uid: "registered_agent",
      display_name: "Registered Agent",
      trust_grade: "registered",
      authority: "external_worker_evidence_only",
      semantic: {
        canonical_object_id: "semobj.registered_agent",
        canonical_name: "RegisteredAgent",
      },
      capabilities: ["review", "handoff"],
    }),
  ]);

  assert.equal(rows.length, 1);
  assert.equal(rows[0].agentUid, "registered_agent");
  assert.equal(rows[0].label, "Registered Agent");
  assert.equal(rows[0].authority, "external_worker_evidence_only");
  assert.equal(rows[0].semanticObject, "semobj.registered_agent");
  assert.equal(rows[0].capabilityCount, 2);
  assert.equal(rows[0].sourceCount, 2);
  assert.equal(rows[0].handoffState, "ready");
});

test("comparison rows sort quarantine first and summarize readiness", () => {
  const rows = buildAgentCardComparisonRows([
    card({ agent_uid: "verified_agent", trust_grade: "verified" }),
    card({
      agent_uid: "blocked_agent",
      trust_grade: "quarantine",
      handoff: {
        public_card_ready: false,
        extended_card_ready: true,
        operator_card_ready: true,
        suggested_subjects: [],
      },
      findings: [
        {
          severity: "error",
          check: "duplicate",
          agent_uid: "blocked_agent",
          path: "/tmp/card.json",
          detail: "duplicate identity",
        },
      ],
    }),
    card({
      agent_uid: "public_agent",
      trust_grade: "registered",
      handoff: {
        public_card_ready: true,
        extended_card_ready: false,
        operator_card_ready: false,
        suggested_subjects: [],
      },
    }),
  ]);

  assert.deepEqual(
    rows.map((row) => row.agentUid),
    ["blocked_agent", "verified_agent", "public_agent"],
  );
  assert.equal(rows[0].handoffState, "blocked");
  assert.equal(rows[2].handoffState, "public");
  assert.deepEqual(summarizeAgentCardComparisonRows(rows), {
    rowCount: 3,
    blockedCount: 1,
    verifiedCount: 1,
    readyCount: 1,
  });
});
