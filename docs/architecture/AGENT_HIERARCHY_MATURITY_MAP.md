---
title: Agent Hierarchy And Maturity Map
path: docs/architecture/AGENT_HIERARCHY_MATURITY_MAP.md
doc_type: architecture
status: draft
created: 2026-06-24
owner_surface: semantic_commons
summary: Canonical D-level hierarchy, folder projection, comparison matrix, and build rubric for persistent agents, holon agents, and apex agents.
---

# Agent Hierarchy And Maturity Map

This document is the canonical working map for agent hierarchy and maturity in
`dharma_swarm`.

It is intentionally not a prompt taxonomy. It is a runtime and governance
taxonomy. An agent's level is earned by receipts, liveness, authority,
delegation, and verification.

## Authority Rule

The authority chain is:

1. `docs/ontology/semantic_objects.yaml` and `semantic_aliases.yaml` define
   stable names, canonical objects, aliases, lifecycle, and admission terms.
2. `docs/ops/AGENT_ADMISSION.md` defines what must be true before a persistent
   agent identity is admitted.
3. `docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md` defines live fleet contact,
   ack tiers, causality, and transport truth.
4. This file defines the D-level hierarchy and maturity gates.
5. Runtime folders are projections of that authority, not the source of truth.

If a folder and Semantic Commons disagree, Semantic Commons wins. If a transport
claim and a NATS/A2A receipt disagree, the receipt wins. If an agent narrative
and a target-owned artifact disagree, the artifact wins.

## Canonical Folder Projection

Today, agent state is spread across:

- `docs/agents/<agent_uid>/`
- `~/.dharma/agents/<agent_uid>/`
- `~/.dharma/ginko/agents/<name>/`
- `~/.dharma/external_agents/<agent_uid>/`
- `~/.dharma/a2a/cards/<callsign>.json`
- `~/.dharma/a2a_bus/inboxes/<agent_uid>/`
- `~/.dharma/shared/*holon*`
- Hermes state under `~/.hermes/`

That spread is workable for history, but it is not a stable operator map. The
canonical object is already `LivingDock` in Semantic Commons. Do not introduce a
parallel `AgentHome` object. Friendly names such as `Nest`, `Holocron`, or
`Sanctum` are aliases or subspaces of `LivingDock`, not competing authority
surfaces.

The active physical projection should stay rooted in the existing LivingDock
runtime home until a verifier proves a migration is clean:

```text
~/.dharma/agents/<agent_uid>/          # LivingDock projection
  identity.json                 # generated/admitted identity view
  semantic_ref.json             # semantic object id, aliases, lifecycle
  registration.json             # runtime admission and owner surface
  capability_card.yaml          # skills, roles, tools, transports, models
  authority_passport.json       # read/write/tool/spawn/budget scope
  a2a_card.json                 # external discovery projection
  living_agent.json             # persistent-agent state projection
  service_heartbeats.jsonl      # service/process liveness
  transport_heartbeats.jsonl    # NATS/A2A transport liveness
  wake_ledger.jsonl             # wake, lease, child wake, control events
  dialogue/                     # direct operator/peer conversation surface
    operator_sessions.jsonl
    relationship_memory.jsonl
    conversation_receipts/
  runs/
    <run_id>/
      mission_envelope.json
      run_envelope.json
      context_bundle.json
      receipts.jsonl
      artifacts/
      verifier_reports/
      operator_report.md
  memory/
    facts.jsonl
    reflections.jsonl
    promotion_proposals.jsonl
  sanctum/                      # D4+ domain-specialized private environment
    codex/                      # prompt banks, role scripts, synthesis styles
    vault/                      # private domain DBs and curated knowledge
    dojo/                       # evaluation, lessons, self-improvement loops
    ingest_gate/                # domain-specific GO/inbox/intake layer
    tools/                      # domain-scoped tools and affordances
  inbox/
  outbox/
```

Migration rule: existing directories stay alive as legacy mirrors until a
verifier proves every admitted agent has a complete LivingDock projection.

## D-Level Hierarchy

| Level | Name | Hard gate | What it can do | What it cannot claim |
|---|---|---|---|---|
| D0 | Model call | Prompt plus optional tools, no durable identity | Answer or call tools inside one session | Agency, persistence, liveness |
| D1 | Ephemeral worker | Assigned task, bounded context, artifact output | Produce a task artifact under a parent | Standing identity or independent authority |
| D2 | Admitted worker | Semantic identity, registration, capability card, authority passport, receipt contract | Accept typed tasks and return receipts/artifacts | Continuous operation or child spawning |
| D3 | Persistent standing agent | D2 plus wake loop, heartbeat, memory, direct dialogue ledger, inbox/outbox, bounded tools, restart story | Wake, remember, converse, act inside policy, accept A2A/NATS tasks | Fleet-level orchestration |
| D4 | Holon agent | D3 plus domain dialogue seat, decomposition, fleet selection, subagent dispatch, fan-in synthesis, verification, budget and kill gates | Speak as the domain steward and control D1-D3 agents through the control plane | Direct unchecked control of foreign runtimes |
| D5 | Apex agent | D4 plus mythic command identity, direct APEX dialogue seat, multi-holon governance, global state, policy evolution, trust scoring, operator cockpit, and self-improvement loop | Speak as APEX, command the holon fleet through the lawful control plane, and improve the system under receipts | Untethered self-modification, policy bypass, or unreceipted command |

The key distinction:

- D3 is a live agent.
- D4 is a live agent that can govern a bounded fleet mission.
- D5 is the mythic command intelligence that inhabits the control plane. The
  control plane is its lawful body: registry, leases, policy, receipts, memory,
  gates, cockpit, and holon fleet.

## Addressable Agent Seat

A persistent agent is not just a loop. The loop is metabolism: wake, heartbeat,
scan, work, receipt, sleep. The dialogue seat is the face: the operator or
another agent can address the agent directly and receive a response from that
agent's own identity, memory, current state, and policy boundary.

D3+ agents must be directly addressable. D4+ holons must be addressable as
domain stewards. D5/APEX must be addressable as the whole-system command
intelligence.

Direct dialogue requirements:

1. Address by canonical `agent_uid`, callsign, or admitted alias.
2. Load the agent's identity, LivingDock state, recent receipts, policy ceiling,
   operator relationship memory, and relevant shared swarm truth.
3. Answer as the agent seat, not as a generic model call.
4. Write a conversation receipt under the LivingDock dialogue ledger.
5. Route durable follow-up work into a `MissionEnvelope` instead of hiding work
   inside chat.
6. Promote lessons, preferences, or memory changes through governed writeback,
   not raw chat transcript accumulation.

## Modal Authority Model

Authority is not standing rank. Authority is a function of operating mode,
action class, and receipt-backed context.

This lets a domain holon become the deepest master of its field without turning
into an unchecked ruler. In its domain seam, the holon leads. In an organism
pulse or jury, the same holon becomes one expert voice among decorrelated
voices. For protected actions, action class overrides domain mastery.

| Mode | Who leads | What the holon can claim | What checks it |
|---|---|---|---|
| Domain lead mode | The domain holon for the seam | Context mastery, delegation authority, final departmental synthesis | Receipts, stewardship ledger, verifier lanes |
| Organism pulse / jury mode | The swarm process or APEX convenes the field | Expert witness in its domain | Decorrelated peers; no self-certification |
| Worker execution mode | D1-D3 workers under envelope | Artifact execution | Parent holon, receipt contract, budget, kill gate |
| Protected action mode | Operator, policy gate, or APEX-approved circuit | Proposal authority only unless explicitly approved | Reversibility ceiling and protected-action approval |

Action classes:

| Class | Examples | Default permission |
|---|---|---|
| Reversible internal work | analysis, drafts, tests, local simulation, proposals | Holon may do or delegate inside budget |
| Governed internal mutation | repo edits, memory promotion, ontology proposals, runtime config | Requires authority passport, receipts, and verifier path |
| External effect | outbound email, public posts, remote API side effects, trades in paper/live systems | Requires explicit mission scope and receipt trail |
| Irreversible/protected action | live money movement, secrets, destructive writes, policy changes, external commitments | Requires protected-action approval; domain mastery is not sufficient |

Memory precedence:

1. Semantic Commons, Chetana/shared swarm memory, and target-owned artifacts are
   the shared truth layer.
2. A holon's Sanctum/Holocron/Nest stores domain nuance, private prompt banks,
   failure diaries, ingest maps, and local working memory.
3. Private memory is additive, not overriding. If a holon believes shared memory
   is wrong, it opens a receipt-backed promotion or correction proposal.

Competence evidence:

A holon earns domain trust by building the department and keeping a stewardship
ledger: what it did, what it delegated, what came back, what passed verification,
what failed, and what it learned. That work is evidence of mastery. It still
does not bypass protected-action gates, because competence and reversibility are
separate axes.

## Maturity Score

Each system or agent is scored on ten axes, 0 to 5. Maximum score: 50.

| Axis | 0 | 3 | 5 |
|---|---|---|---|
| Identity and admission | Ad hoc name | Registered identity | Semantic Commons object plus admission check |
| Canonical home | Scattered files | Mostly known home | Complete LivingDock projection |
| Runtime persistence | Session only | Wake/heartbeat partial | Restart-survivable with ledger |
| A2A/transport | None | Send/ack | Delivery, handler, domain, semantic receipts |
| Delegation hierarchy | None | Manual subagents | Typed child runs with depth/budget limits |
| Authority and policy | Prompt-only | Metadata policy | Fail-closed runtime enforcement with modal action-class gates |
| Receipts and lineage | Logs | Structured receipts | Causal trace plus artifact hashes |
| Verification | Self-report | Separate checker | Decorrelated verifier/adjudicator |
| Operator surface | Hidden | CLI/report | Direct agent dialogue plus cockpit/mobile commands with proof drilldown |
| Evolution loop | Static | Reports improvements | Dojo learns from receipts, conversations, verified self-improvement proposals, and rollback |

Score bands:

| Band | Score | Meaning |
|---|---:|---|
| D0 | 0-7 | tool/model call |
| D1 | 8-15 | ephemeral worker |
| D2 | 16-24 | admitted worker |
| D3 | 25-34 | persistent standing agent |
| D4 | 35-43 | holon-grade orchestrator |
| D5 | 44-50 | apex-grade command intelligence |

Hard gates override points. A system with fail-open authority cannot be promoted
to complete D4 or D5 even if it has many orchestration features.

## Current Dharma Agent Scores

| Agent/system | Current grade | Score | Evidence | Blockers |
|---|---:|---:|---|---|
| `codex_composer` L4 holon | D4-candidate, held at D3.8 | 38/50 | Service alive, transport reachable, bounded orchestration, live specialist execution, artifacts and verifier receipts | `model_responsive=false`, semantic inbox drain missing, domain semantic reply missing |
| `hermes_m5` | D3.7, D4-ingress candidate | 37/50 | Always-on gateway, Slack, cron, sessions DB, memory, tools, reports, dispatch-gate role | Fleet health poor by its own audit, delivery target bugs, not unified as control-plane runtime |
| `sarathi` | D5 seed, not live | 18/50 | Apex identity authored and Semantic Commons-aligned | Not breathing, no runtime, no proof loop |
| `opus_composer` | D2.6 | 24/50 | Identity, living state, prompt | No service heartbeat, no live transport proof |
| `fable_composer` | D2.2 | 21/50 | Identity and prompt | Minimal runtime evidence |
| `merge_master_mike` | D2 evidence worker | 23/50 | Registration, evidence-only authority, summon contract | No standing service proof |
| Ginko worker pool | D1-D2 | 12-22/50 | Many identities and task artifacts | Not canonicalized under admitted LivingDock projection |
| Dharma substrate as whole | D4 substrate, D5 incomplete | 40/50 | Semantic Commons, NATS spec, runtime_state, living kernel, L4 holon harness, A2A bridge | No single apex control plane, policy not universally fail-closed |

## Peer-System Comparison

Scores are architecture maturity for the requested use case: one operator
orchestrating several role-distinct agents with hierarchy, receipts, and cross
runtime control. They are not benchmark scores.

| System | Best-fit level | Score | Strongest feature | Weakness versus Dharma target |
|---|---:|---:|---|---|
| Dharma Swarm current | D4 substrate / D5 incomplete | 40 | Broadest local mix of Semantic Commons, NATS, runtime receipts, living kernel, holon harness, A2A edge | Needs canonical home, fail-closed policy, semantic reply, apex control plane |
| Hermes local | D3.7 / D4 ingress | 37 | Always-on operator substrate with Slack, cron, memory, tools, session search, reports | Observation-heavy, not unified as fleet authority |
| OpenClaw Secure local | D2.5 | 26 | Strong sandbox profile, six access-split agents, VM mode | OpenClaw not installed here; gateway/tool boundary only, not fleet holon |
| AGNTCY / Internet of Agents | D5 infrastructure, not a specific agent | 43 | Agent discovery, interoperable composition, secure messaging, identity, observability goals | Not your standing operator/holon runtime by itself |
| A2A protocol | D4 edge protocol | 36 | Agent cards, tasks, streaming, push notification, security schemes | Protocol only; does not prove liveness, domain truth, or operator hierarchy |
| LangGraph / LangSmith | D4 runtime framework | 39 | Durable stateful orchestration, persistence, HITL, memory, tracing/deployment | No native Dharma identity, NATS receipts, or A2A fleet semantics |
| CrewAI | D3-D4 workflow framework | 32 | Crews, tasks, hierarchical manager, flows, memory, usage metrics | Less focused on standing persistent agents and verified cross-runtime control |
| AutoGen / Magentic-One / MAF lineage | D4 task-team framework | 35 | Orchestrator-specialist pattern, modular agents, benchmarks, AgentTool/team patterns | AutoGen now maintenance mode; less Dharma-style semantic commons and receipts |
| OpenHands | D3.5 software-agent runtime | 34 | Sandboxed dev-agent execution, lifecycle control, model routing, human workspaces | Developer-agent focus, not apex multi-holon governance |
| Sakana Conductor/Fugu pattern | D4.5 learned orchestrator pattern | 41 | Learned workflow routing, model pool selection, access-list context control | Research/orchestrator pattern, not a persistent governed operator system |

## External Benchmarks Worth Copying

Do not copy product shape. Copy operating invariants:

- AGNTCY: discover, compose, deploy, evaluate across frameworks and vendors;
  agent identity and directory are first-class.
- A2A: Agent Cards, task status, artifacts, task list/cancel/subscribe, push
  notifications, and declared security schemes.
- LangGraph: durable execution, persistence, HITL, memory, and traceable state
  transitions.
- CrewAI: explicit crews, tasks, manager process, async kickoff, task output,
  usage metrics, memory.
- Magentic-One: one orchestrator plans, tracks progress, replans after errors,
  and directs specialist agents for browser/files/code.
- OpenHands: sandboxed execution, lifecycle control, local-to-remote execution,
  multi-LLM routing, human workspaces.
- Sakana Conductor/Fugu: orchestrator emits structured workflow steps, model
  selection, subtasks, and access lists; workers see only the permitted prior
  context.

## D4 Holon Promotion Gate

A holon is not D4-complete until a verifier can prove:

1. Semantic identity admitted.
2. Canonical LivingDock projection complete.
3. Fresh service heartbeat.
4. Fresh transport heartbeat.
5. Mission envelope accepted.
6. Subtasks decomposed.
7. At least two decorrelated agents selected by model/provider/host/tool
   surface where possible.
8. Child run envelopes include inherited authority and bounded budgets.
9. Subagent dispatch goes through NATS/A2A/runtime adapters, not direct blind
   subprocess control.
10. Fan-in uses target-owned artifacts and receipts.
11. Synthesis is live or explicitly labeled deterministic.
12. Policy gate fails closed.
13. Kill/pause/cancel path works.
14. Domain receipt and semantic receipt exist.
15. Decorrelated verifier signs a pass/fail adjudication.
16. Mission/receipt trail declares the active authority mode: domain lead,
    organism jury, worker execution, or protected action.
17. Holon maintains a stewardship ledger for direct work, delegated work,
    synthesis, failures, and lessons.
18. Holon private memory obeys the memory precedence rule: shared swarm truth
    outranks Sanctum/Holocron/Nest context.
19. Operator can directly address the holon and receive a seat-specific response
    grounded in identity, current receipts, Sanctum context, and policy ceiling.
20. Dialogue follow-up work becomes mission/run envelopes rather than hidden
    unreceipted background action.

## D5 Apex Promotion Gate

An apex agent is not D5 until it can prove all D4 gates plus:

1. Maintains a global map of logical seats, live workers, work units, and
   interventions.
2. Coordinates at least two D4 holons without collapsing their authority
   boundaries.
3. Owns an operator cockpit/mobile command surface with proof drilldown.
4. Scores trust, cost, and delivery across the fleet.
5. Opens implementation tasks when audits converge without action.
6. Proposes policy/schema/runtime changes as reviewable artifacts.
7. Runs independent verification before memory or ontology promotion.
8. Supports rollback or quarantine after failed self-improvement.
9. Keeps human approval mandatory for protected writes, secrets, governance,
   money movement, external communications, and policy changes.
10. Can survive restart and recover active missions from receipts.
11. Expresses a stable command identity: the APEX is not just a scheduler. It
    has a persistent seat, memory, taste, doctrine, and judgment surface.
12. Commands through lawful mechanisms only: no private backdoor around policy,
    leases, receipts, or verifier gates.
13. Enforces modal authority across the fleet so domain mastery, organism jury
    participation, worker execution, and protected-action approval remain
    distinguishable.
14. Separates competence trust from reversibility permission: a master holon may
    own synthesis, but protected actions still require the protected-action
    circuit.
15. Operator can directly address APEX and ask for fleet state, holon status,
    mission proposals, blockers, trust scores, and next actions.
16. APEX dialogue writes receipts and routes commands through lawful envelopes;
    it does not smuggle privileged work through conversation.

## Build Roadmap

### Phase 0: Canonicalize The Map

- Adopt this file as the D-level grading contract.
- Keep `LivingDock` as the canonical per-agent home object. Do not add
  `AgentHome`; resolve `home`, `nest`, `holocron`, and `sanctum` as aliases or
  subspaces of `LivingDock`.
- Treat `docs/ontology/semantic_objects.yaml`,
  `docs/ontology/semantic_aliases.yaml`, and
  `docs/ontology/session_orientation.yaml` as the official naming/loading
  homes. This draft explains D-level maturity only; it does not own alias
  mutation or L-level context-loading routes.
- Add a read-only verifier that scores one agent and writes a D-score receipt.

### Phase 1: LivingDock Projection

- Generate or normalize `~/.dharma/agents/<agent_uid>/` as the LivingDock
  projection for each active admitted agent.
- Mirror existing `agents`, `ginko`, `external_agents`, and `a2a/cards` into
  the projection.
- Refuse promotion if identity exists in only one legacy place.

### Phase 2: Fail-Closed Authority

- Fix `PersistentAgent._check_gate` so exceptions block privileged standing
  agents.
- Read `autonomy_policy` and `authority_passport` before writes, tool calls,
  child spawn, A2A send, and memory promotion.
- Add tests for policy denial in each runtime path.

### Phase 3: Mission And Run Envelopes

- Promote `MissionEnvelope`, `AgentRunEnvelope`, `AuthorityPassport`, and
  `ReceiptBundle` into one schema home.
- Make holon orchestration consume and emit those envelopes.

### Phase 4: Addressable Dialogue Seats

- Add a direct operator dialogue route for APEX and D4 holons.
- Conversation must load identity, LivingDock state, recent receipts, policy
  ceiling, shared swarm truth, and Sanctum context.
- Conversation must write receipts and convert durable follow-up into mission
  envelopes.
- Dojo writeback may learn from conversation, but only through governed
  promotion rules.

### Phase 5: Runtime Adapter Interface

- Add adapters for local provider worker, Codex/Codex-like CLI, Hermes, A2A
  remote, NATS inbox worker, and future cloud agents.
- Each adapter must expose `dispatch`, `status`, `cancel`, `collect_receipts`,
  and `health`.

### Phase 6: D4 Holon Proof

- First target: `codex_composer`.
- Required closure: unattended semantic inbox drain, model-authored target
  artifact, typed reply publish, domain receipt, semantic receipt.
- Do not count handler ack or deterministic orchestration as semantic cognition.

### Phase 7: D5 Apex Seed

- First target: `sarathi` or `hermes_m5`, but only after D4 proof is green.
- Start with read-only global map, then dispatch gate, then multi-holon mission.
- Human retains protected-action authority.

### Phase 8: Learned Orchestration

- Import the Conductor/Fugu idea only after the proof substrate is reliable.
- The local extension should optimize model/agent routing under receipt-aware
  reward: correctness, cost, latency, verifier pass rate, and policy safety.

## Anti-Patterns

- Do not create another queue.
- Do not create another receipt store.
- Do not count an A2A card as liveness.
- Do not count handler ack as semantic reply.
- Do not let a D4 agent directly shell into 10 other agents and call that
  orchestration.
- Do not reduce a persistent agent to a daemon loop; D3+ agents need an
  addressable dialogue seat.
- Do not promote an agent above D3 while policy can fail open.
- Do not let audit loops spawn more audits after convergence without an
  implementation artifact.
- Do not make folder existence the source of truth.

## Source Ledger

Local:

- `docs/ontology/SEMANTIC_COMMONS.md`
- `docs/ops/AGENT_ADMISSION.md`
- `docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md`
- `docs/sovereign_holons/HOLON_ORCHESTRATOR_BUILD_SPEC.md`
- `docs/sovereign_holons/STATE_OF_TRUTH.md`
- `reports/sovereign_holons/L4_HOLON_SUBSTRATE_HYGIENE_AND_SMOKE_20260618.md`
- `reports/a2a/codex_holon_always_live_upgrade.md`
- `.hermes/reports/hermes_power_audit_2026-06-18.md`
- `.hermes/reports/apex_holon_trust_kernel_2026-06-20.md`
- `openclaw-secure/README.md`

External:

- AGNTCY: `https://docs.agntcy.org/`
- A2A protocol: `https://a2a-protocol.org/latest/specification/`
- LangGraph: `https://docs.langchain.com/oss/python/langgraph/overview`
- CrewAI crews and flows: `https://docs.crewai.com/en/concepts/crews`,
  `https://docs.crewai.com/en/concepts/flows`
- AutoGen / Magentic-One lineage: `https://github.com/microsoft/autogen`,
  `https://arxiv.org/abs/2411.04468`
- OpenHands: `https://arxiv.org/abs/2407.16741`,
  `https://arxiv.org/abs/2511.03690`
- Sakana Conductor/Fugu local synthesis:
  `docs/architecture/LEARNED_AUDITABLE_ORCHESTRATOR_SPEC.md`
