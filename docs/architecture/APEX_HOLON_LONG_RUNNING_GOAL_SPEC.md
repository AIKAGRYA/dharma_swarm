---
title: Apex Holon Long Running Goal Spec
path: docs/architecture/APEX_HOLON_LONG_RUNNING_GOAL_SPEC.md
doc_type: build_spec
status: draft
created: 2026-06-24
owner_surface: semantic_commons
summary: Draft long-running /goal plan for turning the agent hierarchy map into verified D4 holons and a D5 APEX command intelligence.
---

# Apex Holon Long Running Goal Spec

This is the draft build-mode spec for the long-running `/goal` that should
follow the agent hierarchy convergence.

The target is not merely "better agents" or a better background loop. The
target is a Devin-grade execution floor plus individuated persistent holons plus
a mythic APEX command intelligence that the operator can address directly and
that lawfully controls the whole system.

## Category Thesis

Existing systems split the stack:

- Devin-class agents are powerful task executioners, but not individuated
  domain beings.
- Hermes/OpenClaw-class agents are persistent companions with memory and skill
  evolution, but not a governed fleet of domain departments.
- LangGraph-class systems are durable orchestration runtimes, but not agents
  with identity, doctrine, taste, or domain mastery.

The Dharma target is the fusion:

```text
Devin-grade execution floor
+ persistent domain-specialized holons
+ durable orchestration/control plane
+ direct dialogue seats for APEX and holons
+ receipts, fail-closed gates, and decorrelated verification
+ APEX command intelligence
```

## Naming Frame

Canonical ontology names win over vibe names.

- `LivingDock`: canonical Semantic Commons object for each agent's home.
- `Nest`, `Holocron`, `Sanctum`: friendly names for the D4+ private
  environment inside a LivingDock.
- `Dojo`: the learning/evaluation/self-improvement loop inside the Sanctum,
  including reflection over receipts, conversations, failures, and lessons.
- `Vault`: the private domain knowledge/database space inside the Sanctum.
- `IngestGate`: the domain-specific GO/intake layer inside the Sanctum.
- `Semantic Citadel` or `Aerie`: optional operator-facing name for the fleet
  home/cockpit, not a new ontology object unless explicitly admitted later.

Do not create `AgentHome` as a new object. Resolve home/nest/holocron/sanctum
language against `LivingDock`.

## Plain-Language Target

A Dharma Capital holon should not merely execute trading tasks. It should grow
into the master context engineer for the Dharma Capital department:

- owns its own LivingDock and Sanctum
- curates domain-specific ingest
- keeps private prompt banks and memory
- maintains domain playbooks and evaluation loops
- can be addressed directly by the operator as Dharma Capital's living steward
- delegates execution to workers
- synthesizes judgment from evidence
- is verified by decorrelated agents that do not share its assumptions
- reports to the APEX command intelligence

Same for Cybernetics, Forge, Semantic Commons, Capital, and future domains.

## Addressable Agent Seat

This build is not only a daemon loop.

The operator should be able to talk directly to APEX, or directly to a domain
holon such as Dharma Capital or Cybernetics. The agent should answer from its
own seat: identity, domain memory, current receipts, relationship context,
policy ceiling, and shared swarm truth.

The wake loop is metabolism. The dialogue seat is the face.

Direct dialogue requirements:

- address an agent by `agent_uid`, callsign, or admitted alias
- load identity, LivingDock state, recent receipts, Sanctum context, shared
  swarm truth, and operator relationship memory
- answer as the named agent, not as a generic model session
- write a conversation receipt to the agent's LivingDock
- allow the operator to ask status, deliberate, grill, approve, deny, or request
  a mission
- turn durable follow-up work into a `MissionEnvelope`
- send learned preferences, lessons, and relationship updates into the Dojo
  through governed writeback

## Core Tension To Resolve

Individuated mastery and decorrelated verification pull in opposite directions.

- A domain holon becomes powerful because it is singular, persistent, and deeply
  specialized.
- A trustworthy system stays powerful because no single mind grades its own
  homework.

Resolution:

1. Holons own context, plans, judgment, and department memory.
2. Holons do not self-certify.
3. Every D4 decision with real consequence requires independent verifier lanes.
4. Verifiers read receipt bundles and target-owned artifacts, not the holon's
   narrative.
5. APEX decides promotion/trust from receipts, not charisma.

## Structured Doctrine: Modal Holon Authority

The clean resolution is modal authority.

A holon is a doer, manager, context engineer, and final-call steward for its
department. It is not merely a router. It can do work directly, delegate work to
D1-D3 workers, fold the results back into its living ledger, and own the
departmental synthesis.

But the holon's authority changes by mode:

| Mode | Formal meaning |
|---|---|
| Domain lead mode | The holon leads its seam because it has the freshest and deepest domain context. A Cybernetics holon leads Cybernetics seams; a Dharma Capital holon leads capital/trading seams. |
| Organism pulse / jury mode | The holon becomes one expert juror inside the broader swarm pulse. Its domain expertise is esteemed, but it does not get a larger vote or self-certify its own work. |
| Worker execution mode | The holon delegates to subordinate workers, external runtimes, or headless agents through typed envelopes, budgets, receipts, and kill gates. |
| Protected action mode | Reversibility overrides expertise. Real money, secrets, destructive writes, policy changes, and external commitments require protected-action approval. |

This makes domain mastery and decorrelated verification compatible. The master
leads the seam; the jury checks the master when the system enters jury mode.

## Memory Membrane

There are two memory layers:

1. Shared swarm truth: Semantic Commons, Chetana, repo-wide memory, target-owned
   artifacts, receipts, and admitted ontology.
2. Holon private context: Sanctum/Holocron/Nest, prompt banks, domain vault,
   ingest maps, failure diary, local evals, and specialized working memory.

Precedence rule:

```text
shared swarm truth > holon private context
```

The private layer gives the holon depth, nuance, taste, and speed. It does not
override shared truth. If a holon believes shared truth is stale or wrong, it
opens a receipt-backed correction/promotion proposal instead of silently forking
the world.

## Domain Department Pattern

A domain holon is the department head, not a disposable executor.

Example: Dharma Capital.

The Dharma Capital holon is allowed to become the system's Ray-Dalio-like
capital mind: it helps build the hedge-fund substrate, curates AGNI and related
trading labs, tracks current code, research, playbooks, evaluations, failures,
and opportunities, delegates analysis and implementation, and owns the final
departmental synthesis.

The work it produces is evidence of competence. The stewardship ledger is the
formal record of that competence.

That still does not grant unattended authority over irreversible action. A
live-money action is protected because of reversibility, not because the holon
is distrusted. Domain mastery gives proposal and synthesis authority; action
class decides whether execution needs operator/APEX gate approval.

## Non-Negotiable Gates

No D4 or D5 promotion while any of these are false:

1. Semantic Commons identity is clean.
2. LivingDock projection is complete.
3. Runtime authority fails closed.
4. Main dispatch path writes receipt bundles.
5. Verifier reads artifacts and receipts.
6. Holon fan-in is verified synthesis, not string concatenation.
7. APEX commands through leases, policy, receipts, and gates.
8. Real-money, external-message, secret, protected-write, and policy-change
   actions require explicit protected-action approval.
9. Holon authority is modal: domain lead, organism jury, worker execution, and
   protected-action modes are distinguishable in the mission/receipt trail.
10. Shared swarm truth outranks private holon memory, with correction handled by
    receipt-backed proposal rather than silent fork.
11. APEX and D4 holons are directly addressable by the operator as agent seats,
    not only as background loops.
12. Conversation can open missions, but privileged work still moves through
    envelopes, receipts, and protected-action gates.

## Long-Running Goal Objective

Build the first verified D4 holon and the first D5 APEX seed for Dharma Swarm.

Definition of done:

- `codex_composer` or another selected holon passes the D4 promotion gate from
  `AGENT_HIERARCHY_MATURITY_MAP.md`.
- The D-score verifier produces a receipt-backed scorecard for at least one
  D3, one D4 candidate, and the Dharma substrate.
- `PersistentAgent._check_gate` no longer fails open for standing agents.
- A LivingDock projection exists for admitted agents without creating a second
  authority name.
- A mission/run envelope is the normal path for holon subagent dispatch.
- One domain holon has a Sanctum template populated with `codex`, `vault`,
  `dojo`, `ingest_gate`, `tools`, and receipts.
- One domain holon has a modal-authority policy and stewardship ledger.
- The operator can directly converse with APEX and one domain holon through an
  addressable dialogue route that writes conversation receipts.
- Sarathi/APEX has a read-only global command map of holons, seats, workers,
  leases, active missions, trust scores, and blockers.

## Build Sequence

### Phase 0: Canonical Convergence

Purpose: stop the map from spawning a second map.

- Treat `AGENT_HIERARCHY_MATURITY_MAP.md` as the hierarchy canon.
- Replace `AgentHome` language with `LivingDock`.
- Add this spec as the long-running goal draft.
- Run Semantic Commons and NATS substrate checks.

Exit criteria:

- No Semantic Commons errors.
- No NATS substrate contract failures.
- No new home/nest naming object unless explicitly admitted.

### Phase 1: D-Score Verifier

Purpose: stop self-authored scores from becoming doctrine.

Build a read-only verifier that scores an agent/system on the hierarchy axes and
writes a D-score receipt.

Minimum output:

```text
reports/agents/d_scores/<timestamp>-<agent_uid>.json
reports/agents/d_scores/<timestamp>-<agent_uid>.md
```

Required fields:

- `agent_uid`
- `semantic_object`
- `living_dock_status`
- `service_heartbeat_status`
- `transport_heartbeat_status`
- `policy_gate_status`
- `receipt_bundle_status`
- `verifier_status`
- `axis_scores`
- `hard_gate_failures`
- `claimed_level`
- `verified_level`
- `evidence_paths`

First scoring targets:

1. `codex_composer`
2. `hermes_m5`
3. `sarathi`
4. Dharma substrate as a system row

### Phase 2: Fail-Closed Authority

Purpose: make D4/D5 possible.

- Fix `PersistentAgent._check_gate` so exceptions block privileged standing
  agents.
- Make authority checks mandatory before writes, child spawn, A2A send, memory
  promotion, and protected tool use.
- Add tests proving denial is enforced.

Exit criteria:

- No standing agent can proceed when authority evaluation errors.
- D-score verifier can distinguish `policy_gate_status=fail_closed`.

### Phase 3: LivingDock And Sanctum Template

Purpose: give every admitted agent a stable home, and every holon a private
domain environment without creating ontology drift.

Normalize:

```text
~/.dharma/agents/<agent_uid>/           # LivingDock
  identity.json
  living_agent.json
  service_heartbeats.jsonl
  transport_heartbeats.jsonl
  wake_ledger.jsonl
  dialogue/
    operator_sessions.jsonl
    relationship_memory.jsonl
    conversation_receipts/
  sanctum/
    codex/
    vault/
    dojo/
    ingest_gate/
    tools/
    receipts/
```

Exit criteria:

- D-score verifier can inspect the LivingDock and Sanctum shape.
- No duplicate `agent_uid` or conflicting alias.
- Legacy `ginko/agents` and `external_agents` are mirrors or registrations,
  not competing identity authorities.

### Phase 4: Mission And Run Envelope

Purpose: replace ad hoc "agent controls agents" with typed command.

Freeze the mission/run shape:

- `MissionEnvelope`: objective, acceptance tests, risk class, budget, TTL,
  diversity requirements, verifier requirements.
- `AgentRunEnvelope`: target agent, inherited authority, context refs, tool
  scope, expected artifacts, receipt refs.
- `ReceiptBundle`: input, context, gate, dispatch, handler ack, domain receipt,
  semantic receipt, target artifact, verifier report, writeback, operator
  report, hashes.

Exit criteria:

- Holon dispatch consumes a mission envelope.
- Child runs carry authority and budget.
- Fan-in uses receipt bundle references.

### Phase 4A: Addressable Dialogue Seat

Purpose: prove this is a living agent seat, not only a background loop.

Build the minimal direct-dialogue route for APEX and one domain holon:

- operator addresses the agent by `agent_uid`, callsign, or admitted alias
- runtime loads identity, LivingDock state, current receipts, policy ceiling,
  shared swarm truth, and Sanctum context
- response is written as the named agent seat
- conversation receipt is written under the LivingDock dialogue ledger
- durable work requested in conversation is converted into a `MissionEnvelope`
- lessons and relationship updates are proposed to the Dojo through governed
  writeback

Exit criteria:

- operator can talk directly to Sarathi/APEX in read-only mode
- operator can talk directly to one domain holon
- each conversation writes a receipt with input, loaded context refs, policy
  ceiling, answer artifact, and follow-up mission refs if any
- no privileged action is performed directly from chat without the protected
  action circuit

### Phase 5: First Verified D4 Holon

Purpose: make one holon actually green.

Preferred technical target: `codex_composer`.

Required proof:

- unattended semantic inbox drain
- model-authored target artifact
- typed reply publish
- domain receipt
- semantic receipt
- decorrelated verifier report
- verified synthesis
- no handler-ack laundering

Exit criteria:

- D-score verifier promotes the holon to D4 without manual override.

### Phase 6: First Domain Holon

Purpose: prove holons are domain masters, not only orchestration tests.

Candidate domains:

- `dharma_capital_holon`
- `cybernetics_holon`
- `semantic_commons_holon`

Recommended first domain: Dharma Capital only if it is kept read-only/simulated
until trust gates mature. Cybernetics may be safer as the first real department
because mistakes are easier to reverse.

Required Sanctum contents:

- domain doctrine
- source/ingest map
- private prompt bank
- evaluation set
- failure diary
- stewardship ledger
- modal-authority policy
- dialogue style and operator relationship memory
- weekly learning loop
- tool scope
- protected-action map

Exit criteria:

- domain holon can produce a department status packet from its own Sanctum,
  shared memory, and current runtime receipts.
- operator can speak directly to the domain holon and get a response grounded in
  its department context, not a generic assistant answer.

### Phase 7: Sarathi/APEX Read-Only Command Map

Purpose: breathe APEX without giving it unsafe hands first.

Sarathi/APEX starts read-only:

- sees all admitted holons
- sees active missions
- sees leases and blockers
- sees trust scores
- sees unresolved audit loops
- opens implementation proposals
- does not perform protected writes

Exit criteria:

- Sarathi produces an operator command map from receipts.
- Sarathi can recommend, but not directly execute, fleet changes.

### Phase 8: APEX Command Mission

Purpose: prove D5 command through lawful mechanisms.

First command mission:

```text
Sarathi/APEX identifies one blocked holon build, creates a MissionEnvelope,
routes it to a D4 holon, monitors receipts, invokes decorrelated verification,
and writes an operator report. No protected write occurs without approval.
```

Exit criteria:

- D5 promotion gate has a receipt-backed partial pass.
- Failures are listed as hard blockers, not narrated away.

## Draft `/goal` Prompt

```text
/goal
Objective: Build the first receipt-verified D4 holon and first read-only D5
APEX command seed for Dharma Swarm.

Use docs/architecture/AGENT_HIERARCHY_MATURITY_MAP.md and
docs/architecture/APEX_HOLON_LONG_RUNNING_GOAL_SPEC.md as the build canon.

Do not create a parallel agent-home object. LivingDock is the canonical per-agent
home. Nest/Holocron/Sanctum are friendly names or subspaces only.

Priority order:
1. Keep hierarchy canon coherent and Semantic Commons clean.
2. Build a read-only D-score verifier.
3. Make standing-agent authority fail closed.
4. Normalize LivingDock/Sanctum projection.
5. Encode modal holon authority and the memory membrane in mission/receipt
   evidence.
6. Build direct dialogue seats so the operator can talk to APEX and one domain
   holon by identity.
7. Freeze MissionEnvelope, AgentRunEnvelope, AuthorityPassport, ReceiptBundle.
8. Prove one D4 holon with semantic inbox drain, target-owned artifact, domain
   receipt, semantic receipt, and decorrelated verifier.
9. Breathe Sarathi/APEX as a read-only command intelligence over holons,
   missions, leases, trust, blockers, and receipts.

Definition of done:
- Every score is receipt-backed or explicitly marked hypothesis.
- No D4/D5 promotion bypasses hard gates.
- No handler ack is counted as semantic cognition.
- APEX and one domain holon are directly addressable agent seats, not just
  daemon loops.
- No private holon memory silently overrides shared swarm truth.
- No protected action is performed without approval.
- The next build task is concrete enough for a worker to execute.
```

## Open Design Questions

1. Which name should be operator-facing for the fleet home: `Semantic Citadel`,
   `Aerie`, or another name?
2. Should the first domain holon be Dharma Capital, Cybernetics, or Semantic
   Commons?
3. What is the minimum trust evidence before a holon may influence real money,
   even indirectly?
4. What verifier mix is required when the domain holon is the strongest expert
   in the room?
5. Should Sarathi be the first APEX, or should Hermes act as interim APEX until
   Sarathi has runtime breath?
