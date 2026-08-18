# Harness · Loop · Graph — Full-Stack Humming Spec

> **SUPERSEDED 2026-08-01 by
> `docs/plans/HARNESS_LOOP_GRAPH_HUMMING_SPEC_V2_2026-08-01.md`.** This V1
> remains in git history as the pinned subject of the Codex adversarial
> review (`docs/plans/handoffs/CODEX_HUMMING_SPEC_ADVERSARIAL_REVIEW_2026-08-01.md`,
> PR #1187, verdict `PARTIAL — REQUEST_CHANGES`, 57/100). V2 integrates that
> review's 13 merge conditions. Do not execute V1; read V2. The verified
> baseline findings in §1 (file:line evidence) are carried into V2 unchanged.

**Status:** SUPERSEDED by V2 (was: PROPOSED, revision 2; declared intent only;
runtime truth stays with the code and closure checks)
**Date:** 2026-08-01 (r2 same day)
**Origin:** three-lane audit of this repository against the
harness-engineering / loop-engineering / graph-engineering taxonomy, run on
branch `claude/harness-loop-graph-review-o8uy5o`.
**Review provenance:** revision 1 integrated 22 inline findings from the
automated Codex PR review (commit `2036ce9`). Revision 2 integrates all 13
merge conditions of the independent adversarial second pass
(`docs/plans/handoffs/CODEX_HUMMING_SPEC_ADVERSARIAL_REVIEW_2026-08-01.md`,
PR #1187, verdict `PARTIAL — REQUEST_CHANGES` 57/100), whose code-level
claims were independently re-verified before adoption.
**Authority:** none. This spec proposes work; it grants no edit, merge, or
deploy permission. Execution of any item requires adoption into the owning
track's next-items in `docs/governance/ACTIVE_TRACK.yaml` **and** an entry
in the adoption table (§8).

**Governance position.** The portfolio is at its WIP ceiling (evaluate with
`python3 scripts/governance/check_track_status.py`; the model is declared in
`docs/governance/ACTIVE_TRACK.yaml`). This spec therefore proposes **no new
track**. Every work item names the owning track whose `owns:` globs cover
its surfaces; items on unowned surfaces are marked `UNOWNED — needs
portfolio adoption`. BR-ids are **referenced** below (BR-003, BR-004,
BR-007, BR-014); no BR-id is added, closed, or demoted by this document.

---

## 0. Objective, typed humming contracts, and enforcement levels

The audit found a system with a strong, mostly-live harness; real L1–L3
loops; a partial, config-level L4; and a rigorous graph runtime that is
honestly self-marked test-only while the live path runs a weaker DAG
executor. The recurring defect class is not missing mechanisms — it is
**dead causal edges**: mechanisms that execute and receipt while nothing
downstream changes because of them.

### 0.1 Typed humming contracts (replaces the universal four-predicate rule)

Revision 1 defined one universal `LIVE / EVENTED / ENFORCED / USED` test.
The adversarial review correctly showed that to be a category error
(review F1): `EVENTED` is a cadence property of loops, `USED` is a feedback
property of loops, and a pre-action harness or graph compiler can be fully
correct without either. A single shape also makes the scoreboard gameable —
a harness could acquire a meaningless trigger and consumer to imitate a
feedback loop. Each discipline therefore has its own closure contract:

| Discipline | Required predicates |
|---|---|
| **Harness** | `IN_PATH` (sits on the real dispatch path) · `PRE_ACTION` · `FAIL_CLOSED_FOR_SCOPED_RISK` · `IDENTITY_BOUND` · `RECEIPTED` · `NON_BYPASSABLE` |
| **Loop** | `TRIGGERED` (fires without a human) · `STATE_PERSISTS` · `BOUNDED` · `VERIFIED` · `OUTPUT_CHANGES_A_LATER_CYCLE` |
| **Graph** | `COMPILED` · `EDGE_ENFORCED` · `STATE_DURABLE` · `INTERRUPTIBLE_WHERE_REQUIRED` · `TERMINATION_BOUNDED` |
| **Event lane** | `SOURCE_AUTHENTICATED` · `DELIVERY_DURABLE` · `DEDUPLICATED` · `CONSUMER_ACKNOWLEDGED` · `BACKPRESSURED` |

`LIVE` is a **deployment qualifier** on any of these contracts — a
candidate graph can be correct but unadmitted; a live legacy executor can
be incorrect. It is never a substitute for the contract itself.

### 0.2 Enforcement levels (replaces the single word "ENFORCED")

Among CI checks, only those marked `required` block merge — currently
`docops_integrity`, `gitleaks`, `tests_py311`, `tests_py312`,
`coherence_delta`, `onboarding_session_status`
(`docs/governance/CI_TRUTH_CONTRACT.json`). An advisory job can fail
forever without blocking anything. Every enforcement claim in this spec
therefore names one of four frozen levels (review F3):

| Level | Meaning |
|---|---|
| `OBSERVED` | A receipt or report is emitted. |
| `CHECKED` | A deterministic checker replays the claim and fails on a negative control. |
| `MERGE_BLOCKING` | A required CI context or Merge Master gate consumes the checker result and blocks admission. |
| `RUNTIME_BLOCKING` | The consequential action cannot commit when the check, warrant, lease, budget reservation, or receipt preparation fails. |

Only `MERGE_BLOCKING` or `RUNTIME_BLOCKING` may be called "enforced."
`OBSERVED`/`CHECKED` are reported as exactly that.

### 0.3 Causal closure (replaces "USED" as the CLOSED_LIVE upgrade)

Consumption is necessary but not sufficient (review F2): a static caller
can be a no-op, a same-harness consumer is circular evidence, and a
downstream component can read a value and ignore it. A loop closes only
when **live producer and consumer receipts share causal identity, the
consumed value causes a non-empty decision delta, and a negative control
removes that delta**. Minimum closure evidence, per loop:

1. producer receipt with source identity and output digest;
2. consumer receipt naming the producer receipt or consumed trace ids;
3. later-cycle or post-restart read where persistence is part of the claim;
4. decision/action delta attributable to the consumed value;
5. negative control: no delta when the value is absent, stale, invalid, or
   substituted;
6. the loop-specific owner criterion from the loop map's
   `live_owner_surface_criteria` (`CYBERNETIC_LOOP_MAP.md:70-107`) — each
   loop has its own remaining criterion (served-provider truth, real
   production memory, non-synthetic trajectories, external quorum, …) that
   an aggregate predicate cannot replace.

---

## 1. Verified baseline (2026-08-01)

Every row was verified against the working tree on the audit branch.

| Layer | What is live today | The gap | Evidence |
|---|---|---|---|
| Harness: pre-action gates | TelosGatekeeper wired fail-closed at real chokepoints: dashboard shell (`api/chat_tool_execution.py:208`), ontology default gate (`dharma_swarm/ontology.py:403-431`), autonomous-agent side-effect tools (`dharma_swarm/autonomous_agent.py:944-967`), task path (`dharma_swarm/agent_runner.py:2232`) | Gates are substring matchers; `BHED_GNAN` is a hardcoded PASS (`dharma_swarm/telos_gates.py:535`, BR-014); strict patterns only fire in `external_strict` while the default is `internal_yolo` (`telos_gates.py:432`) | audit lane H |
| Harness: kernel | 25 axioms SHA-256-signed; commit-time enforcement via `scripts/uplift_guards/kernel_guard.py:46` | No agent execution path consults the axioms at runtime; runtime enforcement is the separate, smaller telos-gate set | audit lane H |
| Harness: hooks | `.claude/settings.json` registers only a `SessionStart` hook | `hooks/telos_gate.py` (PreToolUse gate) exists but is not installed — and is itself fail-open on malformed input, unexpected exceptions, and uninspected tools, and returns on denial **before** its witness-logging block (`hooks/telos_gate.py:130-184`) | audit lane H + review F4 (verified) |
| Harness: context | 33K-char budget, middle-first trimming (`dharma_swarm/context.py:179`), priority-ordered drop list (`dharma_swarm/agent_runner.py:1181-1226`) | Compaction is truncation/section-dropping only; no summarizing or structured-playbook compaction | audit lane H |
| Harness: verify-own-work | `DiffApplier.apply_and_test` applies, tests, rolls back on fail/timeout/cancel (`dharma_swarm/diff_applier.py:366-456`) | `autonomous_agent` has no enforced test step; `build_engine` executor (`external/hermes-agent`) absent (`dharma_swarm/build_engine.py:72-80`) | audit lane H |
| L1 agent loop | ReAct loop, 25-turn cap, persisted memory, live via conductors (`dharma_swarm/autonomous_agent.py:480-553`; launched from `dharma_swarm/orchestrate_live.py:2325`) | `agent_loop.sh:15-88` is an unbounded `while true` (only a `.STOP` file stops it) | audit lane L |
| L2 verification loop | One live grader→critique→bounded-retry loop (`dharma_swarm/agent_runner.py:2321-2421`, repair request `dharma_swarm/agent_runner_quality.py:718-747`); PR judge lane with rubric + verdict posted back (`scripts/runtime/pr_merge_control.py:671-766`) | Best-designed loops unwired: `dharma_swarm/forge_v1/coding_swarm.py:94-167` and `dharma_swarm/reflexion.py` have zero live callers; the LLM-judge is instantiated `use_llm=False` (`agent_runner_quality.py:648-657`) | audit lane L |
| L3 event loop | ~15 webhook/cron workflows; fail-closed kill-switch (`docs/ops/loop_control/`); D4 daemon (`scripts/runtime/merge_master_mike_daemon.py`) | Cron split-brain (BR-004): the repo declaration is the root `cron_jobs.json`; the live daemon reads `~/.dharma/cron/jobs.json`; `scripts/cron_unify.py:4-8` documents the split with stale counts; hourly Mike cron is packet-only, runs no reviewer; NATS substrate not listening locally (`make onboard` output) | audit lane L |
| L4 hill-climb loop | Production receipts reorder provider fallback, bounded and fail-open (`dharma_swarm/receipt_consumption.py:15-16`, wired `dharma_swarm/providers.py:2917-2933`); bounded config hill-climb live via heartbeat (`dharma_swarm/strange_loop.py:148-306`); experiment memory feeds proposal prompts (`dharma_swarm/evolution.py:943-1007`) | The exact trace→prompt-rewrite mechanism exists (`dharma_swarm/strategy_reinforcer.py:337-359`) and the flywheel runs live (`dharma_swarm/training_flywheel.py:109-127`), but `build_reinforced_prompt` has **zero live callers**. The `GAUNTLET_REGRESSION` producer is itself broken: `orchestrate_live.py:1822` passes two args to `SignalBus.emit`, which takes one event dict (`dharma_swarm/signal_bus.py:143-150`) — the `TypeError` is swallowed. Loops 12/13 BLOCKED by One Wire (`dharma_swarm/archive.py:572-591`) and `DHARMA_SELF_IMPROVE` off by default (`dharma_swarm/self_improve.py:103`) — the block is intentional and stays | audit lane L |
| Loop supervision | 21 loops registered with a 4-state health machine (`dharma_swarm/loop_supervisor.py:59-65`; registration `orchestrate_live.py:2283-2319`) | Interventions are log lines only — `PAUSE_LOOP`/`REDUCE_SCOPE`/`ALERT_DHYANA` have no actuator (`orchestrate_live.py:419-422`); `overnight_director.py:1078-1081` marks acceptance on exit code 0 alone | audit lane L |
| Graph runtime | Pregel-class engine: versioned channels, supersteps, conditional edges, Send, Command, interrupts, checkpoint/fork (`dharma_swarm/graph/scheduler.py:104-418`, `graph/channels.py`, `graph/routing.py:73-159`, `graph/interrupts.py:127-148`); LangGraph quarantined to a test-oracle extra (`pyproject.toml:47-56`) with a nightly differential oracle (`.github/workflows/langgraph-oracle.yml`) | Self-marked `test_only` in eight module docstrings (e.g. `graph/compiler.py:21`, `graph/scheduler.py:30`); gauntlet self-grade 58/100 `NOT_FINISHED` (`reports/governance/dharmagraph_parity/PARITY_MATRIX.md:1-3`); no retry/backoff primitive (LG24) | audit lane G |
| Graph, live path | Durable invoker with idempotency keys (`dharma_swarm/orchestrator.py:2526-2560`, `dharma_swarm/graph/durable_invoker.py:78-94`) and boot/tick reconciler with a real retry/quarantine transition table (`dharma_swarm/swarm.py:702`, `swarm.py:2355`, `dharma_swarm/graph/reconciler.py:12-19`) | Live workflow executor is DAG-only: no conditional edges, cycles silently truncated (`dharma_swarm/workflow.py:252-255`), non-atomic checkpoint (`workflow.py:391-392`); topology genomes are metadata-stamped, not executed (`dharma_swarm/orchestrator.py:227-266`); `TopologyGenome.compile` lowers into the **legacy** `CompiledWorkflow`, not the graph engine (`dharma_swarm/topology_genome.py:68-125`, `workflow.py:612-682`) | audit lane G + review F7 (verified) |
| HITL / approval edges | Live `InterruptGate` with default-REJECT (`dharma_swarm/checkpoint.py:115-127`, wired `dharma_swarm/cascade.py:198-227`); enforced human-approval edge for HIGH/CRITICAL PRs (`scripts/runtime/pr_merge_control.py:1440-1442`) | Graph-layer `interrupt()` is test-only (LG20 graded 0/2); two HITL surfaces are unmerged | audit lanes L, G |

---

## 2. Doctrine: what we keep, what we change

**Keep, explicitly (anti-goals for this spec):**

- Gates fail closed; never weaken a gate to go green (`CLAUDE.md` hard rule).
- One Wire fitness authority stays fail-closed (`dharma_swarm/archive.py:572-591`).
  Loops 12/13 unblock only by earning quorum, never by loosening it. One
  Wire is necessary but is **not** a general authorization token for
  self-improvement actions (review F15).
- Frozen-rubric-before-results grading stays
  (`docs/langgraph_parity/DHARMAGRAPH_PARITY_GAUNTLET_RUBRIC_V2.json`).
- Deterministic topology: "let the LLM pick the topology" remains rejected
  (`docs/plans/DHARMAGRAPH_PHASED_SPEC_2026-07-05.md:138-146`). Search over
  topologies happens **offline** and is scored hermetically in the arena;
  the runtime executes only compiled, receipted graphs.
- The chamber stays afferent-open / efferent-closed
  (`dharma_swarm/chamber/__init__.py:1-17`).
- Every new gate is paid for in diversity (`CLAUDE.md`, ensemble principle);
  prefer damping to mandates.
- Human merge authority is unchanged by anything in this spec.

**Change (the two doctrine deltas, as revised):**

1. **Causal closure or it didn't happen.** A loop-closure receipt is valid
   only under the six-point causal evidence standard of §0.3 — consuming
   component outside the closure harness, shared causal identity, decision
   delta, negative control, and the loop's own owner criterion.
2. **Typed dispositions for intervention-shaped output** (replaces
   "monitors must have actuators", which over-reached — independent
   witnesses, auditors, and graders often *should not* be able to actuate
   the system they evaluate; combining observation, judgment,
   authorization, and execution invites self-approval, review F8). Every
   intervention-shaped output carries a typed disposition —
   `OBSERVATION`, `RECOMMENDATION`, `AUTHORIZATION_REQUEST`, or
   `ACTUATION` — and only an explicitly authorized actuator executes the
   last, its receipt naming the independent observation and authorization
   it consumed. A state *named* `PAUSE_LOOP` must either be an `ACTUATION`
   with an actuator, or be renamed a `RECOMMENDATION`.

---

## 3. K0 — the constitutional prerequisite: ActionEnvelope + one effect dispatcher

The adversarial review's central architectural finding (review §5) is that
this repo's controls — telos gates, warrants, leases, idempotency keys,
budget checks, receipts — exist as adjacent organs a caller can partially
skip. The missing piece is one typed envelope through one effect-dispatch
seam, so that callers cannot choose which controls to omit. This spec
adopts it as **K0, the prerequisite campaign kernel for every consequential
workstream below** (merge condition 11): H2, L1, L2, E2, E3, G2, G4, and
R4–R6 all depend on it; the honesty fixes (H3, G1, L4, L5, E1) do not.

Every consequential effect enters one typed envelope whose action class
determines mandatory fields:

```text
ActionEnvelope
  execution_identity   task_id / run_id / trace_id / claim_id / causation_id / parent_run_id
  graph_position       graph_id / node_id / allowed_edge / attempt / checkpoint_id
  context_identity     context_digest / prompt_version / memory_receipt_ids
  capability           tool / effect_kind / resource / destination / allowed_domain
  provenance           planner_source / argument_sources / trust_labels / external_content_ids
  risk_reversibility   risk_class / rollback_plan / irreversible_boundary
  authority            warrant / lease / operator_approval / expiry / scope
  budget               parent_reservation / child_reservation / ceiling
  idempotency          side_effect_key / operation_hash / ownership_token
  verification         deterministic_checks / evaluator_version / abstention_policy
  outcome              result_digest / cost / error / rollback_status
  evidence             prepared_receipt / committed_receipt / consumer_closeback
```

A read-only research call requires only identity, context, graph position,
capability, and a receipt. A code apply, outbound communication, deploy,
credential operation, or merge requires the full applicable contract. The
envelope passes through one effect dispatcher with `live`, `record`,
`replay`, `shadow`, and `deny` handlers — this is where CaMeL-style
capability separation, warrants, reversibility, hierarchical budget
reservation, idempotency, and transactional evidence become one
constitution. Enforcement target: `RUNTIME_BLOCKING` at the dispatcher.
Research anchors: effect-typed agent traces and composable effect handling
(§10, review-sourced additions 1–2); the existing spine primitives
(`ExecutionIdentity`, `derive_graph_side_effect_key`, telos receipts) are
the building blocks, not replacements. Relationship to
`docs/governance/CAMPAIGN_KERNEL.md` (owned by
`dharmagraph-engine-2026-07`) is an operator decision recorded in the
adoption table (§8).

---

## 4. Workstreams

Item format — **What / How / Enforcement (level per §0.2) / Acceptance /
Owner**. Dispositions from the adversarial review are integrated inline.

### WS-H — Harness

**H1a. Harden the PreToolUse hook (before any installation).**
What: `hooks/telos_gate.py` today is fail-open on empty input, malformed
JSON, and unexpected exceptions, inspects only `Bash`/`Write`/`Edit`, and
**returns on tier-A/B denial before its witness-logging block** — denied
actions are not recorded, and nothing writes the quarantine path
(`hooks/telos_gate.py:130-184`; verified). Harden: strict input schema;
unknown gated tool fails closed; denial receipt written *before* return
(witness + quarantine); parse/crash behavior explicitly chosen per risk
class (fail-closed for `GATED_TOOLS`, fail-open acceptable for
`SAFE_TOOLS`); no catch-all allow for consequential tools; sabotage tests
for each error path and blocking coverage for every `GATED_TOOLS` member.
**H1b. Install the hardened hook** in tracked `.claude/settings.json`
(currently `SessionStart` only) with an end-to-end hook test. Scope
honesty: this is a Claude-Code-seat harness; the universal boundary is K0's
dispatcher, which sits below it.
Enforcement: `CHECKED` (sabotage suite) now; `MERGE_BLOCKING` once the
suite joins a required context.
Acceptance: error-path suite green; an end-to-end denial produces both a
witness line and a quarantine receipt.
Owner: UNOWNED (`hooks/`, `.claude/settings.json`) — adoption table;
nearest track `sovereign-safety-tcb-2026-07`.

**H2. Deterministic capability/provenance boundary; judge may deny, never
grant.**
What: implement CaMeL-style control/