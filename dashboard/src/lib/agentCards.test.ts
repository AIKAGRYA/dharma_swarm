import assert from "node:assert/strict";
import test from "node:test";

import {
  agentCardBlocked,
  agentCardHandoffReady,
  filterAgentCards,
  uniqueAgentCardRoles,
} from "./agentCards.ts";
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
    a2a: {},
    registration: {},
    identity_invariant: {},
    authority_passport: {},
    living_dock: {},
    nats: {},
    handoff: {
      public_card_ready: true,
      extended_card_ready: true,
      operator_card_ready: true,
      suggested_subjects: [],
    },
    sources: {},
    findings: [],
    trust_grade: "verified",
    ...overrides,
  };
}

test("filterAgentCards searches identity, model, and capability fields", () => {
  const agents = [
    card({ agent_uid: "codex_composer", capabilities: ["code_authorship"] }),
    card({ agent_uid: "palantir_pilot", model: "ontology-router" }),
  ];

  assert.deepEqual(
    filterAgentCards(agents, { search: "ontology" }).map((agent) => agent.agent_uid),
    ["palantir_pilot"],
  );
  assert.deepEqual(
    filterAgentCards(agents, { search: "code_authorship" }).map(
      (agent) => agent.agent_uid,
    ),
    ["codex_composer"],
  );
});

test("filterAgentCards applies trust, role, and readiness filters", () => {
  const agents = [
    card({ agent_uid: "verified_builder", role: "builder", trust_grade: "verified" }),
    card({
      agent_uid: "blocked_reviewer",
      role: "reviewer",
      trust_grade: "quarantine",
      findings: [
        {
          severity: "error",
          check: "duplicate",
          agent_uid: "blocked_reviewer",
          path: "/tmp/card.json",
          detail: "duplicate identity",
        },
      ],
    }),
    card({
      agent_uid: "public_only",
      role: "reviewer",
      trust_grade: "registered",
      handoff: {
        public_card_ready: true,
        extended_card_ready: false,
        operator_card_ready: true,
        suggested_subjects: [],
      },
    }),
  ];

  assert.deepEqual(
    filterAgentCards(agents, { readiness: "blocked" }).map((agent) => agent.agent_uid),
    ["blocked_reviewer"],
  );
  assert.deepEqual(
    filterAgentCards(agents, { role: "reviewer", readiness: "public" }).map(
      (agent) => agent.agent_uid,
    ),
    ["blocked_reviewer", "public_only"],
  );
  assert.deepEqual(
    filterAgentCards(agents, { trustGrade: "verified" }).map(
      (agent) => agent.agent_uid,
    ),
    ["verified_builder"],
  );
});

test("agent card helpers expose handoff and blocked status", () => {
  const ready = card({ agent_uid: "ready" });
  const blocked = card({
    agent_uid: "blocked",
    trust_grade: "registered",
    findings: [
      {
        severity: "error",
        check: "schema",
        agent_uid: "blocked",
        path: "/tmp/card.json",
        detail: "invalid card",
      },
    ],
  });

  assert.equal(agentCardHandoffReady(ready), true);
  assert.equal(agentCardBlocked(blocked), true);
});

test("uniqueAgentCardRoles returns stable non-empty roles", () => {
  assert.deepEqual(
    uniqueAgentCardRoles([
      card({ role: "reviewer" }),
      card({ role: "builder" }),
      card({ role: "reviewer" }),
      card({ role: "" }),
    ]),
    ["builder", "reviewer"],
  );
});
