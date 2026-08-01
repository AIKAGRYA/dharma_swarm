# Harness · Loop · Graph — Full-Stack Humming Spec

**Status:** PROPOSED (declared intent only; runtime truth stays with the code and closure checks)
**Date:** 2026-08-01
**Origin:** three-lane audit of this repository against the harness-engineering / loop-engineering / graph-engineering taxonomy, run on branch `claude/harness-loop-graph-review-o8uy5o`.
**Authority:** none. This spec proposes work; it grants no edit, merge, or deploy permission. Execution of any item requires adoption into the owning track's next-items in `docs/governance/ACTIVE_TRACK.yaml`.

**Governance position.** The portfolio is at its WIP ceiling (evaluate with
`python3 scripts/governance/check_track_status.py`; the model is declared in
`docs/governance/ACTIVE_TRACK.yaml`). This spec therefore proposes **no new
track**. Every work item names the owning track whose `owns:` globs cover its
surfaces; items on unowned surfaces are marked `UNOWNED — needs portfolio
adoption`. BR-ids are **referenced** below (BR-003, BR-004, BR-014, BR-007);
no BR-id is added, closed, or demoted by this document.

---

## 0. Objective and the definition of "humming"

The audit found a system with a strong, mostly-live harness; real L1–L3
loops; a partial, config-level L4; and a rigorous graph runtime that is
honestly self-marked test-only while the live path runs a weaker DAG
executor. The recurring defect class is not missing mechanisms — it is
**dead edges**: mechanisms that execute and receipt but whose output nothing
consumes (see §1, rows L4 and G2).

A layer is **humming** when all four predicates hold, mechanically:

1. **LIVE** — the mechanism executes on a production dispatch path, not only
   inside its own closure harness or tests.
2. **EVENTED** — something fires it without a human: webhook, cron, signal
   bus, or heartbeat.
3. **ENFORCED** — a mechanical check fails when it regresses: a test, a
   closure check consumed by `reports/loop_closure/`, or a CI gate placed
   per the ratchet policy in `docs/governance/CI_TRUTH_CONTRACT.json`.
4. **USED** — its output is consumed by another component, and the
   consumption itself is receipted. A receipt that proves a mechanism ran,
   produced by the mechanism's own harness, does not satisfy this predicate
   (the Loop 7 lesson, §1 row L4).

Predicate 4 is the one that upgrades `HARNESS_PROVEN` to `CLOSED_LIVE` in
the cybernetics codex vocabulary (`CYBERNETIC_LOOP_MAP.md:12-16` currently
reports `CLOSED_LIVE: 0/13`).

---

## 1. Verified baseline (2026-08-01)

Every row was verified against the working tree on the audit branch.

| Layer | What is live today | The gap | Evidence |
|---|---|---|---|
| Harness: pre-action gates | TelosGatekeeper wired fail-closed at real chokepoints: dashboard shell (`api/chat_tool_execution.py:208`), ontology default gate (`dharma_swarm/ontology.py:403-431`), autonomous-agent side-effect tools (`dharma_swarm/autonomous_agent.py:944-967`), task path (`dharma_swarm/agent_runner.py:2232`) | Gates are substring matchers; `BHED_GNAN` is a hardcoded PASS (`dharma_swarm/telos_gates.py:535`, BR-014); strict patterns only fire in `external_strict` while the default is `internal_yolo` (`telos_gates.py:432`) | audit lane H |
| Harness: kernel | 25 axioms SHA-256-signed; commit-time enforcement via `scripts/uplift_guards/kernel_guard.py:46` | No agent execution path consults the axioms at runtime; runtime enforcement is the separate, smaller telos-gate set | audit lane H |
| Harness: hooks | `.claude/settings.json` registers only a `SessionStart` hook | `hooks/telos_gate.py` (PreToolUse gate) exists but is not installed in the tracked settings | audit lane H |
| Harness: context | 33K-char budget, middle-first trimming (`dharma_swarm/context.py:179`), priority-ordered drop list (`dharma_swarm/agent_runner.py:1181-1226`) | Compaction is truncation/section-dropping only; no summarizing or structured-playbook compaction | audit lane H |
| Harness: verify-own-work | `DiffApplier.apply_and_test` applies, tests, rolls back on fail/timeout/cancel (`dharma_swarm/diff_applier.py:366-456`) | `autonomous_agent` has no enforced test step; `build_engine` executor (`external/hermes-agent`) absent (`dharma_swarm/build_engine.py:72-80`) | audit lane H |
| L1 agent loop | ReAct loop, 25-turn cap, persisted memory, live via conductors (`dharma_swarm/autonomous_agent.py:480-553`; launched from `dharma_swarm/orchestrate_live.py:2325`) | `agent_loop.sh:15-88` is an unbounded `while true` (only a `.STOP` file stops it) | audit lane L |
| L2 verification loop | One live grader→critique→bounded-retry loop (`dharma_swarm/agent_runner.py:2321-2421`, repair request `dharma_swarm/agent_runner_quality.py:718-747`); PR judge lane with rubric + verdict posted back (`scripts/runtime/pr_merge_control.py:671-766`) | Best-designed loops unwired: `dharma_swarm/forge_v1/coding_swarm.py:94-167` and `dharma_swarm/reflexion.py` have zero live callers; the LLM-judge is instantiated `use_llm=False` (`agent_runner_quality.py:648-657`) | audit lane L |
| L3 event loop | ~15 webhook/cron workflows; fail-closed kill-switch (`docs/ops/loop_control/`); D4 daemon (`scripts/runtime/merge_master_mike_daemon.py`) | Cron split-brain: 16 of 28 declared jobs orphaned (`scripts/cron_unify.py:4-8`, BR-004); hourly Mike cron is packet-only, runs no reviewer; NATS substrate not listening locally (`make onboard` output) | audit lane L |
| L4 hill-climb loop | Production receipts reorder provider fallback, bounded and fail-open (`dharma_swarm/receipt_consumption.py:15-16`, wired `dharma_swarm/providers.py:2917-2933`); bounded config hill-climb live via heartbeat (`dharma_swarm/strange_loop.py:148-306`); experiment memory feeds proposal prompts (`dharma_swarm/evolution.py:943-1007`) | The exact trace→prompt-rewrite mechanism exists (`dharma_swarm/strategy_reinforcer.py:337-359`) and the flywheel runs live (`dharma_swarm/training_flywheel.py:109-127`), but `build_reinforced_prompt` has **zero live callers** — Loop 7's receipt proves a mechanism, not a behavior. `GAUNTLET_REGRESSION` signal has zero consumers (`dharma_swarm/orchestrate_live.py:1811-1828`). Loops 12/13 BLOCKED by One Wire (`dharma_swarm/archive.py:572-591`) and `DHARMA_SELF_IMPROVE` off by default (`dharma_swarm/self_improve.py:103`) — the block is intentional and stays | audit lane L |
| Loop supervision | 21 loops registered with a 4-state health machine (`dharma_swarm/loop_supervisor.py:59-65`; registration `orchestrate_live.py:2283-2319`) | Interventions are log lines only — `PAUSE_LOOP`/`REDUCE_SCOPE`/`ALERT_DHYANA` have no actuator (`orchestrate_live.py:419-422`); `overnight_director.py:1078-1081` marks acceptance on exit code 0 alone | audit lane L |
| Graph runtime | Pregel-class engine: versioned channels, supersteps, conditional edges, Send, Command, interrupts, checkpoint/fork (`dharma_swarm/graph/scheduler.py:104-418`, `graph/channels.py`, `graph/routing.py:73-159`, `graph/interrupts.py:127-148`); LangGraph quarantined to a test-oracle extra (`pyproject.toml:47-56`) with a nightly differential oracle (`.github/workflows/langgraph-oracle.yml`) | Self-marked `test_only` in eight module docstrings (e.g. `graph/compiler.py:21`, `graph/scheduler.py:30`); gauntlet self-grade 58/100 `NOT_FINISHED` (`reports/governance/dharmagraph_parity/PARITY_MATRIX.md:1-3`); no retry/backoff primitive (LG24) | audit lane G |
| Graph, live path | Durable invoker with idempotency keys (`dharma_swarm/orchestrator.py:2526-2560`, `dharma_swarm/graph/durable_invoker.py:78-94`) and boot/tick reconciler with a real retry/quarantine transition table (`dharma_swarm/swarm.py:702`, `swarm.py:2355`, `dharma_swarm/graph/reconciler.py:12-19`) | Live workflow executor is DAG-only: no conditional edges, cycles silently truncated (`dharma_swarm/workflow.py:252-255`), non-atomic checkpoint (`workflow.py:391-392`); topology genomes are metadata-stamped, not executed (`dharma_swarm/orchestrator.py:227-266`); the built executor bridge `execute_topology_genome_workflow` (`dharma_swarm/workflow.py:612-682`) has zero non-test callers | audit lane G |
| HITL / approval edges | Live `InterruptGate` with default-REJECT (`dharma_swarm/checkpoint.py:115-127`, wired `dharma_swarm/cascade.py:198-227`); enforced human-approval edge for HIGH/CRITICAL PRs (`scripts/runtime/pr_merge_control.py:1440-1442`) | Graph-layer `interrupt()` is test-only (LG20 graded 0/2); two HITL surfaces are unmerged | audit lanes L, G |

---

## 2. Doctrine: what we keep, what we change

**Keep, explicitly (anti-goals for this spec):**

- Gates fail closed; never weaken a gate to go green (`CLAUDE.md` hard rule).
- One Wire fitness authority stays fail-closed (`dharma_swarm/archive.py:572-591`).
  Loops 12/13 unblock only by earning quorum, never by loosening it.
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

**Change (the two doctrine deltas):**

1. **Consumption-or-it-didn't-happen.** A loop-closure receipt is valid only
   if the consuming component is outside the closure harness. Concretely:
   `scripts/loop7_training_flywheel_closure_run.py` calling
   `build_reinforced_prompt` itself no longer counts as Loop 7 closure.
2. **Monitors must have actuators.** Any supervisor state that names an
   intervention (`PAUSE_LOOP`, `REDUCE_SCOPE`) must either actuate it with
   bounded authority and a receipt, or be renamed to an observation.

---

## 3. Workstreams

Item format — **What / How / Enforcement / Acceptance (runnable) / Owner**.

### WS-H — Harness

**H1. Install the PreToolUse gate in the tracked Claude Code settings.**
What: register `hooks/telos_gate.py` as a `PreToolUse` hook in
`.claude/settings.json` (currently `SessionStart` only), preserving its
`SAFE_TOOLS`/`GATED_TOOLS` split (`hooks/telos_gate.py:57-60`).
How: hook denies on gate BLOCK, logs to `~/.dharma/witness/`.
Enforcement: a test asserting the hook is registered and denies a seeded
dangerous tool call.
Acceptance: `python3 -m pytest tests/test_claude_hooks.py -q` (extend) and a
recorded denial receipt under `~/.dharma/quarantine/`.
Owner: UNOWNED (`.claude/settings.json`) — needs portfolio adoption;
nearest track `sovereign-safety-tcb-2026-07`.

**H2. Two-tier semantic gating with control/data-flow separation.**
What: keep the pattern tier (fast, deterministic) and add a judge tier for
side-effect tools, plus CaMeL-style separation: tool *arguments* derived
from untrusted content (fetched pages, inbox messages, PR comments) carry a
provenance tag and cannot alter which tool runs — only a trusted planner
output can (Debenedetti et al., *Defeating Prompt Injections by Design*,
arXiv:2503.18813; policy-enforcement family incl. Progent surveyed in
arXiv:2606.26479).
How: provenance tags ride `runtime_state` receipts; the gate tier consults
them at the existing chokepoints (`api/chat_tool_execution.py:208`,
`autonomous_agent.py:944-967`). Judge tier is budgeted and fails closed on
timeout, mirroring the shell-gate semantics already in
`api/chat_tool_execution.py:216-245`.
Enforcement: seeded injection corpus test (extend
`telos_gates.py` INJECTION_PATTERNS fixtures) must show the pattern tier
unchanged and the judge tier catching ≥1 case the pattern tier misses.
Acceptance: `python3 -m pytest tests/test_telos_gates* -q`.
Owner: `dharma_swarm/telos_gates.py` is UNOWNED and merge-CRITICAL
(`scripts/runtime/pr_merge_control.py:630-665`) — requires human-approved PR
by construction. BHED_GNAN's hard-pass (BR-014) closes only via
`GateRegistry.propose()` (`telos_gates.py:170`, `:267-281`), per the
register's own closure path.

**H3. One shell-command policy module, two consumers.**
What: unify `autonomous_agent.py:44-49` `_DANGEROUS_PATTERNS` and the API
regex list (`api/chat_tool_execution.py:130-151`) into a single policy
module both import, ending the drift risk between two hand-maintained lists.
Enforcement: a parity test that both entry points refuse an identical
seeded corpus.
Acceptance: `python3 -m pytest tests/test_sandbox.py tests/test_api_auth.py -q`
plus the new parity test.
Owner: `repository-titanium-hardening-2026-07` (owns
`dharma_swarm/autonomous_agent.py`, `dharma_swarm/sandbox.py`, `api/main.py`).

**H4. Kernel→gate bridge.**
What: compile the axioms' `formal_constraint` strings
(`dharma_swarm/dharma_kernel.py:103`) into predicates consulted by
`check_action` (`telos_gates.py:805`), so the SHA-256-signed kernel is
enforced at runtime, not only at commit time
(`scripts/uplift_guards/kernel_guard.py:46`).
How: additive only — bridge failures degrade to current behavior; no
existing gate weakens.
Acceptance: `dgc dharma status` shows kernel consulted; new test asserts at
least one axiom predicate blocks a seeded violation.
Owner: UNOWNED, merge-CRITICAL surface — human-approved PR required.

**H5. ACE-style context playbooks.**
What: replace pure truncation with structured, incremental context
evolution: a per-agent playbook that accumulates and curates strategies
instead of being rewritten wholesale, avoiding the paper's documented
"context collapse" failure (*Agentic Context Engineering*,
arXiv:2510.04618).
How: the chetana `PreCompact` recovery manifest
(`dharma_swarm/chetana/claude_code_plugin/scripts/pre_compact.sh`) becomes
the ingestion event; playbook sections join the existing priority-ordered
drop list (`agent_runner.py:1181-1226`) *above* raw recall blocks.
Enforcement: extend `memory_kernel` context-eval cases
(`dharma_swarm/memory_kernel/context_eval_cases.py`) with a
collapse-detection case (playbook length and key-count must not shrink
across N compactions without an explicit curation receipt).
Acceptance: `python3 -m pytest tests/ -q -k "context"`.
Owner: context surfaces are UNOWNED; chetana plugin dir is UNOWNED —
nearest tracks `loop-closure-2026-06` (Loop 4 consolidation) and portfolio
adoption.

**H6. LocalSandbox resource limits.**
What: add rlimits (CPU, memory, file size) and default-deny network to
`LocalSandbox.execute` (`dharma_swarm/sandbox.py:118`), closing the gap its
own docstring admits (`sandbox.py:1-6`).
Acceptance: `python3 -m pytest tests/test_sandbox.py -q` with new
limit-enforcement tests.
Owner: `repository-titanium-hardening-2026-07`.

### WS-L — Loops

**L1. Wire `StrategyReinforcer` into the live prompt builder (the P0 item).**
What: `autonomous_agent._build_system_prompt`
(`autonomous_agent.py:1218-1239`) calls
`StrategyReinforcer.build_reinforced_prompt`
(`strategy_reinforcer.py:337-359`), bounded (top-k ≤ 3, char-capped inside
the existing context budget), with an injection receipt naming the strategy
ids used.
Why first: the flywheel already extracts and persists strategies every 30
minutes (`training_flywheel.py:109-127`); this is a one-hop wire that
converts Loop 7 from mechanism-proof to behavior-proof.
Enforcement: Loop 7 closure check re-pointed at the *live* prompt builder;
the closure harness calling `build_reinforced_prompt` itself no longer
counts (doctrine delta 1).
Acceptance:
`rg -n "build_reinforced_prompt" dharma_swarm/ --glob '!strategy_reinforcer.py'`
returns ≥1 live caller; `python3 -m pytest tests/ -q -k "reinforc"`.
Owner: `loop-closure-2026-06` (Loop 7; closure surfaces under
`reports/loop_closure/**`). `autonomous_agent.py` is owned by
`repository-titanium-hardening-2026-07` — cross-track coordination required.

**L2. Turn the judge on, then optimize it with GEPA.**
What: (a) enable the LLM-judge tier of `quality_gates` for designated task
types (currently always `use_llm=False`,
`agent_runner_quality.py:648-657`), budgeted, with Brier-calibrated
aggregation via the existing `dharma_swarm/ginko_brier.py` machinery so
judge weight tracks calibration; (b) run GEPA-style reflective evolution
over the grader rubrics and repair prompts offline — GEPA outperforms GRPO
by ~10% with up to 35× fewer rollouts and beats MIPROv2 (arXiv:2507.19457,
ICLR 2026 oral) — with candidate rubrics scored in the arena before
promotion (frozen-rubric discipline preserved: a rubric version is frozen
*before* it grades anything that counts).
Judge-reliability caveat: rubric verification by LLM judges is itself
error-prone under long contexts (RUVER-BENCH, arXiv:2606.29920) — keep
deterministic checks primary, judges secondary, per the existing scorer
doctrine (`dharma_swarm/coordination/arena/scorer.py:22-47`).
Acceptance: judge decisions logged with Brier scores;
`python3 -m pytest tests/ -q -k "quality"`.
Owner: `orchestration-arena-v1-2026-06` (arena scoring) +
`loop-closure-2026-06` (Loop 2/6 surfaces).

**L3. Give the supervisor a sprinkler.**
What: implement the `PAUSE_LOOP` actuator — a per-loop pause flag honored
by loop bodies at tick, written with a receipt and an expiry — replacing
the log-only branch at `orchestrate_live.py:419-422`. `REDUCE_SCOPE` and
`ALERT_DHYANA` either gain actuators (scope knob; push notification) or are
renamed observations (doctrine delta 2).
Enforcement: `tests/test_loop_supervisor_tristate.py` extended: a loop that
hits the dead-cycle escalation threshold must be observably paused within
one tick.
Acceptance: `python3 -m pytest tests/test_loop_supervisor_tristate.py -q`.
Owner: `loop-closure-2026-06`.

**L4. Earned acceptance for overnight runs.**
What: `overnight_director.py:1078-1081` stops equating exit code 0 with
acceptance; route outcomes through the existing semantic acceptance gate
(`agent_runner_quality.py:609-715`).
Acceptance: a seeded produce-nothing-exit-0 run is recorded FAILED.
Owner: UNOWNED — portfolio adoption; nearest `loop-closure-2026-06`.

**L5. Bound the unbounded loop.**
What: `agent_loop.sh:15-88` gains `MAX_CYCLES` and a cumulative token/cost
ceiling alongside the existing `.STOP` file.
Acceptance: shellcheck-clean; a dry-run with `MAX_CYCLES=2` exits 0 after 2.
Owner: UNOWNED root script — portfolio adoption.

**L6. The CLOSED_LIVE campaign.**
What: re-run the cybernetics codex audit against a **live** runtime DB (the
committed `reports/loop_closure/cybernetics_codex/latest_audit.json`
records `runtime DB missing` — every HARNESS_PROVEN verdict rests on
bounded replay), then promote loops to `CLOSED_LIVE` one at a time as their
consumption edges land (L1 closes Loop 7; E2 closes the gauntlet→DGM edge;
H5 strengthens Loop 4). Target: ≥5 of 13 loops `CLOSED_LIVE`.
Acceptance: `latest_audit.json` shows `runtime.exists: true` and
`CLOSED_LIVE ≥ 5`; `CYBERNETIC_LOOP_MAP.md` summary regenerated.
Owner: `loop-closure-2026-06`.

**L7. Wire the orphaned verification loops.**
What: route `self_improve` proposal validation through
`forge_v1/coding_swarm.run_coding_swarm` (`coding_swarm.py:94-167` — real
test exit codes as ground truth, cross-model-family diagnosis, max 3
rounds, currently demo-only), and inject `reflexion` memory
(`dharma_swarm/reflexion.py`) into semantic repair requests so repeated
failures carry prior-attempt reflections.
Guards preserved: `self_improve` stays behind `DHARMA_SELF_IMPROVE`
(`self_improve.py:103`) and its proposal/LLM budgets
(`self_improve.py:46-47`); One Wire untouched.
Acceptance: `rg -n "run_coding_swarm" dharma_swarm/ --glob '!forge_v1/*'`
returns ≥1 caller; new integration test.
Owner: UNOWNED (`forge_v1/`, `reflexion.py`) — portfolio adoption; nearest
`sovereign-safety-tcb-2026-07` (owns `evolution_safety` surfaces).

### WS-G — Graph

**G1. Make the live DAG executor honest (smallest fixes first).**
What: `workflow.py` cycle detection raises instead of `logger.error` +
truncate (`workflow.py:252-255`); checkpoint write becomes atomic
tmp+rename+fsync (`workflow.py:391-392`), matching
`graph/checkpoint.py:65`'s existing discipline.
Acceptance: `python3 -m pytest tests/test_workflow.py -q` with new
cycle-raise and crash-during-checkpoint tests.
Owner: `dharmagraph-engine-2026-07`.

**G2. Execute evolved topologies (close the one-hop gap).**
What: `Orchestrator._dispatch_topology_genome`
(`orchestrator.py:227-266`) stops metadata-stamping and invokes the
already-built `execute_topology_genome_workflow` (`workflow.py:612-682`,
currently zero non-test callers), behind a feature flag defaulting to the
current behavior until the arena scores the executed path at parity.
Acceptance: `rg -n "execute_topology_genome_workflow" dharma_swarm/`
returns ≥1 non-test caller; `python3 -m pytest tests/test_topology_execution.py -q`.
Owner: `dharmagraph-engine-2026-07` (workflow/orchestrator) with
`orchestration-arena-v1-2026-06` (scoring).

**G3. Gauntlet ascent to the bar.**
What: close the production-relevant zeros in the parity matrix
(`PARITY_MATRIX.md`): retry/backoff primitive (LG24), interrupt facets
(LG19/LG20 — the module exists, `graph/interrupts.py:127-148`, but is
unproven at facet level), then re-run the gauntlet toward the
judge-signed bar the track's closeout is blocked on.
Acceptance: `python3 scripts/governance/dharmagraph_parity_gauntlet.py --check`
green; matrix score strictly increases with each landed facet.
Owner: `dharmagraph-engine-2026-07`.

**G4. Agents as nodes.**
What: a `NodeCallable` adapter wrapping `agent_runner.run_task` so a graph
node can be a full agent run, fenced by the already-live durable invoker's
idempotency keys (`graph/durable_invoker.py:122`,
`orchestrator.py:2526-2560`). This is the article-wave capability the
runtime is architecturally ready for and does not yet use.
Acceptance: one compiled graph in tests where a node is a real (mocked
provider) agent run, resumable across a simulated crash.
Owner: `dharmagraph-engine-2026-07`.

**G5. One HITL surface.**
What: bridge the live `InterruptGate` (`checkpoint.py:78-181`) and the
graph-layer `interrupt()` (`graph/interrupts.py:127-148`) so a graph
interrupt surfaces through the same filesystem request/response protocol
operators already have, keeping default-REJECT (`checkpoint.py:115-127`).
Acceptance: `python3 -m pytest tests/test_checkpoint.py tests/test_graph_checkpoint.py -q`.
Owner: `dharmagraph-engine-2026-07`.

### WS-E — Events

**E1. Cron unification (BR-004).**
What: one schema, one authority: reconcile `dharma_swarm/cron_jobs.json`
(28 declared, 16 orphaned) with the live daemon's `~/.dharma/cron/jobs.json`
via `scripts/cron_unify.py` (`cron_unify.py:4-8` documents the split), and
add a parity check so the split cannot silently reopen.
Acceptance: `python3 scripts/cron_unify.py --check` (add flag) exits 0;
orphan count 0.
Owner: UNOWNED — portfolio adoption; register progress against BR-004.

**E2. Consume `GAUNTLET_REGRESSION`.**
What: the signal emitted at `orchestrate_live.py:1811-1828` (currently zero
consumers) opens a targeted `self_improve` cycle scoped to the regressing
components, subject to all existing L4 guards (budgets, protected files,
One Wire). This is the event-driven hill-climb edge: eval regression →
automatic, bounded repair attempt → receipt.
Acceptance: seeded regression in a test emits the signal and produces a
`self_improve` cycle receipt naming the regressing component.
Owner: `loop-closure-2026-06` + `sovereign-safety-tcb-2026-07`.

**E3. A real reviewer in the hourly loop.**
What: the Mike backlog cron is packet-only with merge off
(`merge-master-mike-backlog.yml` defaults; reviewer invocation guarded by
`packet_only` in `pr_merge_control.py:2724`) because runners lack reviewer
binaries; the live quorum already comes from GitHub-App reviews bridged via
the trusted-login map (`pr_merge_control.py:1013-1032`). Formalize that:
document App reviews as the cloud reviewer lane, and add a
`workflow_dispatch` reviewer job (hosted `claude -p --max-turns 8`, the cap
already in `pr_merge_control.py:741-746`) behind the existing kill-switch
(`docs/ops/loop_control/`), so review capacity is an event application, not
an operator-laptop dependency.
Acceptance: one PR receives a receipted review verdict from the hosted lane
end-to-end; kill-switch halt test stays green
(`python3 -m pytest tests/test_loop_killswitch_workflows.py -q`).
Owner: `merge-master-mike-d4-2026-06`.

**E4. NATS afferent wiring.**
What: stand the substrate up per
`docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md` (onboard currently reports
`127.0.0.1:4222 not listening`, filesystem mirrors absent) and route Go
ingestor output (`tools/*_go/**`, runner
`scripts/runtime/github_ingestor_runner.py`) through JetStream to organism
afferents, replacing filesystem-mirror compatibility mode. Live-production
evidence goes through the existing checks
(`scripts/governance/check_nats_live_production_evidence.py`) — no prose
claims of liveness.
Acceptance: `python3 scripts/governance/check_nats_substrate_contract.py`
and the live-evidence matrix pass on the deployment host.
Owner: `organism-rewire-2026-07` (ingestors, organism) +
`repository-titanium-hardening-2026-07` (NATS checks).

### WS-R — Bleeding-edge research integrations

Each item names the mechanism it upgrades. Adoption rule: research lands as
a *scored candidate* in existing evaluation surfaces (arena, chamber,
gauntlet) before touching a live path.

**R1. GEPA — reflective prompt/rubric evolution (arXiv:2507.19457, ICLR
2026 oral).** Sample-efficient replacement for hand-tuned prompt edits in
`self_improve` and for grader rubrics (see L2). Fits the existing shape:
`evolution.py:943-1007` already reflects on experiment memory; GEPA adds
Pareto-frontier candidate selection and system-trajectory reflection.
Integration point: an offline optimizer whose winning candidates enter the
arena as genomes.

**R2. ACE — agentic context engineering (arXiv:2510.04618).** Structured
incremental context playbooks with explicit collapse avoidance; the
research basis for H5. Directly addresses our truncation-only compaction.

**R3. CaMeL / policy-enforcement security (arXiv:2503.18813; adaptive
evaluation arXiv:2606.26479).** Control-flow/data-flow separation and
capability policies enforced *outside* the model — the research basis for
H2. Aligns with our existing doctrine that enforcement lives in
deterministic code, not model vigilance.

**R4. Sleep-time compute for memory consolidation (Letta lineage; temporal
hierarchies e.g. TiMem, arXiv:2601.02845).** The organism already has idle
surfaces (`dgc hum`, subconscious, chetana decay/gap scans). Formalize a
consolidation cron: off-peak reflection over `~/.dharma/` stores that
rewrites agent memory blocks and playbooks (H5) with receipts — offline
policy improvement over data already collected. Owner: Loop 4
(`loop-closure-2026-06`) + chetana surfaces.

**R5. Automated workflow/architecture search feeding the arena (AFlow,
arXiv:2410.10762, ICLR 2025; MaAS agentic supernet, arXiv:2502.04180;
EvoAgentX, arXiv:2507.03616).** MCTS/supernet search over code-represented
workflows becomes the *generator* for `TopologyGenome` candidates
(`topology_genome.py:35` is currently a serialization format with no
generator). The zero-weight doctrine holds: search runs offline, the arena
scores hermetically (`coordination/orchestrator_v1.py:1-12`), the council
verifies custody (`council/council.py:94-116`), and only compiled winners
execute (G2). Owner: `orchestration-arena-v1-2026-06`.

**R6. Self-improvement lineage + adversarial evaluators (Darwin Gödel
Machine, arXiv:2505.22954, ICLR 2026; Huxley-Gödel Machine CMP metric,
arXiv:2510.21614; Red Queen co-evolving evaluators, arXiv:2606.26294;
group experience sharing, arXiv:2602.04837).** Three upgrades to
`DarwinEngine`/`dgm_loop` (which already cites DGM,
`dharma_swarm/dgm_loop.py:9-13`): (a) sample the MAP-Elites archive by
clade metaproductivity (CMP) rather than individual fitness — descendants'
aggregate success, not the parent's score; (b) co-evolve the *evaluators*
under the same custody discipline as the gauntlet, our structural answer to
the DGM Appendix F telemetry-attack risk the phased spec already quotes
(`DHARMAGRAPH_PHASED_SPEC_2026-07-05.md:121-125`); (c) share experience
across agent lineages through the existing stigmergy/archive substrate.
All behind One Wire; none of this unblocks Loops 12/13 by itself.

**R7. MAST failure taxonomy as audit rubric (arXiv:2503.13657).** The
14-failure-mode taxonomy (specification, inter-agent misalignment, task
verification) becomes a standing audit lens over our own traces: a
governance script classifies dispatch failures from `runtime_state`
receipts into MAST categories and reports the distribution, giving L6's
CLOSED_LIVE campaign an external, literature-grounded failure vocabulary.
Owner: `loop-closure-2026-06`.

---

## 4. Enforcement matrix

Every wire in §3 lands with all three of:

1. **A test** in `tests/` (per-module convention).
2. **A closure or governance check** whose receipt is consumed outside the
   producing harness (doctrine delta 1) — under `reports/loop_closure/**`
   or `scripts/governance/`.
3. **A CI placement** per the ratchet policy: new checks enter advisory,
   promote to `required` in `docs/governance/CI_TRUTH_CONTRACT.json` only
   after a stability window, and are never weakened to go green (the
   contract carries the local reproduction command for every gate).

Merge admission stays wider than CI: HIGH/CRITICAL-risk changes (anything
touching `dharma_kernel.py` / `telos_gates.py` — items H2, H4) require
human approval by the existing gate (`pr_merge_control.py:1440-1442`).
That is not friction to route around; it is the approval edge working.

---

## 5. Phasing

Dependencies flow downward; each phase is independently shippable.

**P0 — one-hop wires and honesty fixes (target: ~2 weeks of track time).**
L1 (StrategyReinforcer wire), G1 (workflow cycle-raise + atomic
checkpoint), L4 (earned acceptance), L5 (bounded shell loop), H3 (one shell
policy), H1 (PreToolUse hook). Everything here is additive, small-diff, and
individually revertible.

**P1 — verification and events (~weeks 2–5).**
L2a (judge tier on, Brier-weighted), L3 (supervisor actuator), L7
(coding_swarm + reflexion lanes), E1 (cron unification), E2
(GAUNTLET_REGRESSION consumer), E3 (hosted reviewer lane). Requires P0's
L1/L4 receipts as the consumption-evidence pattern.

**P2 — graph ascent (~weeks 4–8, overlaps P1).**
G3 (LG24 retry/backoff, LG19/20 facets), G2 (topology execution behind
flag), G5 (one HITL surface), then G4 (agents-as-nodes). Gauntlet score is
the ratchet; the flag flips only at scored parity.

**P3 — compounding loops and research (~weeks 6–12).**
H5+R2 (context playbooks), R4 (sleep-time consolidation cron), L2b+R1
(GEPA rubric evolution through the arena), R5 (workflow search →
genome generator), R6 (CMP sampling, evaluator co-evolution), R7 (MAST
audit), E4 (NATS afferents), H4 (kernel bridge), H6 (sandbox limits), L6
(CLOSED_LIVE promotions, running throughout as edges land).

---

## 6. Acceptance — the humming scoreboard

"Done" for this spec is all of the following, each mechanically checkable:

| # | Criterion | Check |
|---|---|---|
| 1 | Loop 7 behavior-proof | `rg -n "build_reinforced_prompt" dharma_swarm/ --glob '!strategy_reinforcer.py'` ≥1 live caller |
| 2 | `CLOSED_LIVE ≥ 5/13`, audited against a live runtime DB | `reports/loop_closure/cybernetics_codex/latest_audit.json` (`runtime.exists: true`) |
| 3 | No named intervention without an actuator | `tests/test_loop_supervisor_tristate.py` extended suite green |
| 4 | Zero dead signal edges | every `SignalBus.emit` topic has ≥1 registered consumer or an explicit `observation_only` marker; enforced by a new governance check |
| 5 | Gauntlet strictly above 58/100 with LG24 non-zero | `python3 scripts/governance/dharmagraph_parity_gauntlet.py --check` |
| 6 | Topology genomes executed, not stamped | `rg -n "execute_topology_genome_workflow" dharma_swarm/` non-test caller; arena parity receipt |
| 7 | Cron orphan count 0 | `python3 scripts/cron_unify.py --check` |
| 8 | Judge tier live with calibration | Brier-scored judge receipts present in `runtime_state`; deterministic checks still primary |
| 9 | No gate weakened | `git diff` over `telos_gates.py` gate table shows tiers/patterns monotonically non-weakened; BHED_GNAN closed only via `GateRegistry.propose` |
| 10 | All new checks placed per ratchet | `docs/governance/CI_TRUTH_CONTRACT.json` diff reviewed; no check deleted or demoted |

---

## 7. Risks

- **Goodharting the graders.** Once graders feed back (L2, E2), producers
  optimize against them. Mitigations: deterministic scorers stay the sole
  correctness authority (`coordination/arena/scorer.py:22-47`); judge
  rubrics evolve only through frozen-version arena scoring (R1); evaluator
  co-evolution (R6b) under gauntlet-style custody.
- **Telemetry attack by self-modifying code.** Already documented from DGM
  Appendix F in `DHARMAGRAPH_PHASED_SPEC_2026-07-05.md:121-125`. R6b is
  the structural answer; One Wire and protected-file lists
  (`self_improve.py:38-43`) remain the hard backstop.
- **Prompt-injection surface grows with consumption edges.** Every new
  consumer of external content (E2–E4, R4) inherits H2's provenance
  tagging; until H2 lands, new consumers treat external text as data-only.
- **Diversity tax.** New gates and judges are paid for in ensemble
  diversity (`CLAUDE.md`, Krogh-Vedelsby). Prefer bounded damping
  (receipt_consumption's reorder-never-filter pattern,
  `receipt_consumption.py` docstring) over hard filters everywhere a choice
  exists.
- **WIP ceiling.** Ten active tracks is the max; this spec adds none.
  Items on UNOWNED surfaces wait for portfolio adoption rather than
  spawning shadow work.

## 8. Research bibliography

- GEPA: Reflective Prompt Evolution Can Outperform Reinforcement Learning — arXiv:2507.19457 (ICLR 2026 oral)
- Darwin Gödel Machine: Open-Ended Evolution of Self-Improving Agents — arXiv:2505.22954 (ICLR 2026)
- Huxley-Gödel Machine: Human-Level Coding Agent Development by an Approximation of the Optimal Self-Improving Machine — arXiv:2510.21614
- The Red Queen Gödel Machine: Co-Evolving Agents and Their Evaluators — arXiv:2606.26294
- Group-Evolving Agents: Open-Ended Self-Improvement via Experience Sharing — arXiv:2602.04837
- Agentic Context Engineering: Evolving Contexts for Self-Improving Language Models — arXiv:2510.04618
- Defeating Prompt Injections by Design (CaMeL) — arXiv:2503.18813
- Adaptive Evaluation of Out-of-Band Defenses Against Prompt Injection in LLM Agents — arXiv:2606.26479
- AFlow: Automating Agentic Workflow Generation — arXiv:2410.10762 (ICLR 2025)
- Multi-agent Architecture Search via Agentic Supernet (MaAS) — arXiv:2502.04180
- EvoAgentX: An Automated Framework for Evolving Agentic Workflows — arXiv:2507.03616
- Why Do Multi-Agent LLM Systems Fail? (MAST) — arXiv:2503.13657
- Can LLM-as-a-Judge Reliably Verify Rubrics in Agentic Scenarios? (RUVER-BENCH) — arXiv:2606.29920
- TiMem: Temporal-Hierarchical Memory Consolidation for Long-Horizon Conversational Agents — arXiv:2601.02845
