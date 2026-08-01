# Harness · Loop · Graph — Full-Stack Humming Spec, V2

**Status:** PROPOSED (declared intent only; runtime truth stays with the code
and closure checks)
**Date:** 2026-08-01
**Supersedes:** `docs/plans/HARNESS_LOOP_GRAPH_HUMMING_SPEC_2026-08-01.md` (V1),
which remains in git history as the pinned subject of the adversarial review.
**Integrates:** the Codex adversarial review
(`docs/plans/handoffs/CODEX_HUMMING_SPEC_ADVERSARIAL_REVIEW_2026-08-01.md`,
PR #1187, verdict `PARTIAL — REQUEST_CHANGES`, 57/100, review confidence 0.91)
and the automated Codex App review on PR #1186 (22 line findings, all adopted
in V1 r2 and carried here).
**Authority:** none. This spec proposes work; it grants no edit, merge, deploy,
loop-closure, archive-fitness, or self-improvement authority. Execution of any
item requires adoption into the owning track's `next_items` in
`docs/governance/ACTIVE_TRACK.yaml` per the adoption table (§9).

**Governance position (unchanged from V1).** The portfolio is at its WIP
ceiling; this spec proposes **no new track**. Every item names its owning
track or is marked `UNOWNED — needs portfolio adoption`. BR-003/004/007/014 are
**referenced**, never added/closed/demoted.

---

## 0. What changed from V1, and why

V1's strategic center was correct and survives: **Dharma Swarm's recurring
defect is usually a dead causal edge between a producer and a later decision,
not an absent mechanism.** The adversarial review confirmed that center
(review §1) and preserved the workstreams. It rejected V1's *execution model*
on five structural grounds, each adopted here:

| V1 defect | Review finding | V2 fix |
|---|---|---|
| One universal `LIVE/EVENTED/ENFORCED/USED` predicate for every layer | F1: category error — `EVENTED` and `USED` are loop properties; a pre-action harness or a graph compiler needs neither | §2 typed per-discipline contracts |
| `ENFORCED` = "has a test + advisory CI" | F3: advisory CI never blocks; only 6 checks are required (`CI_TRUTH_CONTRACT.json`) | §3 four enforcement levels; `ENFORCED` means MERGE_BLOCKING or RUNTIME_BLOCKING |
| `USED` upgrades a loop to `CLOSED_LIVE` | F2: a caller can be a no-op; same-harness consumption is circular | §4 causal closure: producer/consumer identity + decision delta + negative control + owner criterion |
| Phase order mixed new autonomy into P0 | F6: reverses the article's harness-first order; L1/L2/E2/E3/G2 create adaptive edges before the provenance boundary they depend on | §7 corrected order; constitutional harness is P0 |
| No single enforcement boundary | §5: many wires, no constitution | §6 `ActionEnvelope` + one effect dispatcher as the campaign kernel |

Two doctrine corrections:

1. **"Consumption-or-it-didn't-happen" is kept but strengthened** (§4). A
   consumed value must cause a measurable decision delta that a negative
   control removes — a same-harness caller no longer counts.
2. **"Monitors must have actuators" is withdrawn** (review F8). It violated
   separation of duties: independent witnesses, auditors, and graders should
   often be *unable* to actuate what they evaluate. Replaced by §2.5's typed
   dispositions — an intervention-shaped output is `OBSERVATION`,
   `RECOMMENDATION`, `AUTHORIZATION_REQUEST`, or `ACTUATION`, and only an
   authorized actuator executes the last, citing the independent observation
   and authorization it consumed.

---

## 1. Verified baseline (2026-08-01) — carried from V1, unchanged

Every row verified against the working tree. This is the shipped-vs-gap map;
it is not re-litigated by the review (the review checked V1's *plan*, not its
baseline evidence, and found the baseline sound).

| Layer | Live today | Gap | Evidence |
|---|---|---|---|
| Harness gates | fail-closed telos chokepoints | substring-only; `BHED_GNAN` hard-pass (BR-014); strict patterns off by default | `api/chat_tool_execution.py:208`, `dharma_swarm/ontology.py:403-431`, `dharma_swarm/autonomous_agent.py:944-967`, `telos_gates.py:432,535` |
| Kernel | 25 axioms SHA-256-signed, commit-time enforced | not consulted at agent runtime | `scripts/uplift_guards/kernel_guard.py:46`; only 7 `structured_predicate` in `dharma_kernel.py` |
| Hooks | `SessionStart` only | `hooks/telos_gate.py` not installed; and it fails **open** (see §5 H1) | `.claude/settings.json:1-13`, `hooks/telos_gate.py:130-184` |
| Context | 33K budget, middle-first trim | truncation only, no summarization | `context.py:179`, `agent_runner.py:1181-1226` |
| Verify-own-work | apply→test→rollback | `autonomous_agent` has no test step; `build_engine` executor absent | `diff_applier.py:366-456`, `build_engine.py:72-80` |
| L1 agent loop | ReAct, 25-turn cap, persisted memory | `agent_loop.sh` unbounded | `autonomous_agent.py:480-553`, `agent_loop.sh:15-88` |
| L2 verify loop | one live grader→retry; PR judge lane | best designs unwired; judge `use_llm=False` | `agent_runner.py:2321-2421`, `pr_merge_control.py:671-766`, `agent_runner_quality.py:648-657` |
| L3 event loop | ~15 workflows; fail-closed kill-switch | cron split-brain (BR-004); hourly Mike packet-only | `docs/ops/loop_control/`, `scripts/cron_unify.py`, root `cron_jobs.json` |
| L4 hill-climb | receipt→provider-reorder (live); config hill-climb (live) | trace→prompt-rewrite mechanism exists, zero live callers; `GAUNTLET_REGRESSION` **emitter is broken** (§5 E2) | `receipt_consumption.py`, `providers.py:2917-2933`, `strange_loop.py:148-306`, `strategy_reinforcer.py:337-359`, `orchestrate_live.py:1822` vs `signal_bus.py:143` |
| Loop supervision | 4-state health, 21 loops | interventions log-only | `loop_supervisor.py:59-65`, `orchestrate_live.py:419-422` |
| Graph runtime | Pregel-class engine, LangGraph oracle | self-marked test-only, 58/100 | `graph/scheduler.py:104-418`, `PARITY_MATRIX.md:1-3` |
| Graph live path | durable invoker + reconciler | live executor is DAG-only; genomes metadata-stamped | `orchestrator.py:2526-2560`, `swarm.py:702`, `workflow.py:252-255`, `orchestrator.py:227-266` |
| Approval edges | `InterruptGate` default-REJECT; human-approval merge edge | graph `interrupt()` test-only | `checkpoint.py:115-127`, `cascade.py:198-227`, `pr_merge_control.py:1440-1442` |

---

## 2. Typed closure contracts (replaces V1's universal predicate — review F1)

A layer is not "humming" against one four-part checklist. Each discipline has
its own contract; `LIVE` is a deployment qualifier on any of them, not a
predicate that changes their meaning.

**Harness contract** — a harness component is complete when:
`IN_PATH` · `PRE_ACTION` · `FAIL_CLOSED_FOR_SCOPED_RISK` · `IDENTITY_BOUND` ·
`RECEIPTED` · `NON_BYPASSABLE`. No trigger or feedback consumer is required —
a per-invocation safety gate is correct without a cron.

**Loop contract** — a loop is complete when:
`TRIGGERED` · `STATE_PERSISTS` · `BOUNDED` · `VERIFIED` ·
`OUTPUT_CHANGES_A_LATER_CYCLE`. This is where "evented" and "used" live.

**Graph contract** — a graph is complete when:
`COMPILED` · `EDGE_ENFORCED` · `STATE_DURABLE` · `INTERRUPTIBLE_WHERE_REQUIRED`
· `TERMINATION_BOUNDED`. A graph constrains a path; it need not feed a later
adaptive cycle.

**Event-lane contract** — an event lane is complete when:
`SOURCE_AUTHENTICATED` · `DELIVERY_DURABLE` · `DEDUPLICATED` ·
`CONSUMER_ACKNOWLEDGED` · `BACKPRESSURED`.

### 2.5 Typed dispositions for intervention-shaped outputs (replaces "monitors must have actuators")

Every output that looks like an intervention carries exactly one disposition:

- `OBSERVATION` — a receipt/report; no authority.
- `RECOMMENDATION` — a proposed action; no authority.
- `AUTHORIZATION_REQUEST` — asks an authority to permit an action.
- `ACTUATION` — changes system state; only an authorized actuator emits it,
  and its receipt must name the independent `OBSERVATION` and the
  `AUTHORIZATION` it consumed.

Independent witnesses/auditors/graders emit at most `RECOMMENDATION`. This is
the separation-of-duties backstop against self-approval and telemetry attack.

---

## 3. Enforcement levels (replaces V1's flat "ENFORCED" — review F3)

Four levels, named per claim. Only the last two satisfy the word *enforced*.

| Level | Meaning | Example |
|---|---|---|
| `OBSERVED` | a receipt/report is emitted | a governance script writes a JSON report |
| `CHECKED` | a deterministic checker replays the claim and **fails on a negative control** | `dharmagraph_parity_gauntlet.py --check` |
| `MERGE_BLOCKING` | a `required` context or Merge Master gate consumes the checker and blocks admission | the 6 required checks in `docs/governance/CI_TRUTH_CONTRACT.json` |
| `RUNTIME_BLOCKING` | the consequential action cannot commit when the check/warrant/lease/budget/receipt fails | telos gate at `api/chat_tool_execution.py:208` |

Current required set (verified): `docops_integrity`, `gitleaks`,
`tests_py311`, `tests_py312`, `coherence_delta`, `onboarding_session_status`.
A new advisory job can fail forever without blocking merge — so "add an
advisory CI job" is `CHECKED` at best, never `ENFORCED`. Every §8 item names
its target level, and promotion to `MERGE_BLOCKING` follows the ratchet in
`CI_TRUTH_CONTRACT.json` (advisory → stability window → required), never a
weakening.

---

## 4. Causal closure (replaces V1's "USED ⇒ CLOSED_LIVE" — review F2)

A loop closes to `CLOSED_LIVE` only when **all** hold:

1. **producer receipt** with source identity and output digest;
2. **consumer receipt** naming the producer receipt or consumed trace ids
   (shared causal identity — not merely "a consumer exists");
3. **later-cycle / post-restart read** when persistence is part of the claim;
4. **decision delta** — the consumed value causes a non-empty change in a
   later decision or action;
5. **negative control / ablation** — removing, staling, invalidating, or
   substituting the value removes the delta;
6. the **loop-specific owner criterion** from `live_owner_surface_criteria`
   in `CYBERNETIC_LOOP_MAP.md:70-107` (served-provider truth, real production
   memory, production scheduler state, non-synthetic trajectories, live
   roster materialization, or external quorum — different per loop).

This preserves V1's insight while making a one-line caller insufficient. The
committed `latest_audit.json` ran against a missing runtime DB, so **no loop
holds this today** and the honest current count is `CLOSED_LIVE: 0/13`
(`CYBERNETIC_LOOP_MAP.md:12-16`).

---

## 5. Workstream corrections (per review §3 dispositions and 22 App findings)

Format — **What / Contract level / Correction / Acceptance / Owner**. Only the
items the review changed materially are expanded; unchanged items cite V1.

### Harness

**H1 → split into H1a (harden) + H1b (install) — review F4.**
The hook fails open today: tier-A/B denial `return`s *before* the witness
block (verified `hooks/telos_gate.py:138-165`), empty/malformed input and the
top-level catch-all all `sys.exit(0)` (allow), and only Bash/Write/Edit inputs
are inspected — a gated tool like `NotebookEdit` passes with empty content.
Installing it unchanged adds the *appearance* of a fail-closed gate.
- **H1a — harden:** strict input schema; unknown/`GATED_TOOLS` member on
  parse-error/exception/empty ⇒ **deny with a receipt written before return**;
  the denial receipt goes to `~/.dharma/quarantine/` (V1 claimed this path but
  the hook only writes `~/.dharma/witness/`); no catch-all allow for
  consequential tools; sabotage tests per `GATED_TOOLS` member.
- **H1b — install:** register in `.claude/settings.json` + an end-to-end
  Claude Code hook test, only after H1a's fail-closed and receipt tests pass.
- Scope: this is a **seat-specific** Claude Code hook, explicitly **not** the
  universal effect boundary — that is §6.
- Level: `RUNTIME_BLOCKING` (H1b). Owner: UNOWNED; nearest
  `sovereign-safety-tcb-2026-07`.

**H2 → deterministic capability/provenance first; judge may deny, never grant — review F5.**
CaMeL's contribution is deterministic control/data-flow separation *outside*
the model (arXiv:2503.18813), not authority granted by a second stochastic
model. So:
- **H2a (P0):** a typed provenance/capability layer decides which effects are
  structurally possible; external text may fill data fields but may never
  choose the capability, destination, authority class, or graph edge; a
  timeout/unavailable judge must not widen capability.
- **H2b (P3):** an optional judge tier may add a denial, abstention, or
  escalation — never upgrade denied/unproven → authorized.
- This is expressed through the `ActionEnvelope` (§6), not provenance tags in
  receipt metadata.
- Acceptance: end-to-end case where fetched/inbox content attempts to change
  the selected side-effect tool and the **deterministic** layer blocks it with
  the judge disabled. Level: `RUNTIME_BLOCKING`. Owner: UNOWNED, merge-CRITICAL.

**H3 — one shell policy, both consumers.** Unchanged from V1 r2; disposition
`SUPPORTED_WITH_FINDINGS`. Add a frozen policy digest + sabotage parity tests.
Owner: split — Titanium owns `autonomous_agent.py`/`sandbox.py`/`api/main.py`;
`api/chat_tool_execution.py` and the new module are **UNOWNED** (§9).

**H4 — kernel bridge; "degrade to current behavior" is shadow, not enforced — review disposition PARTIAL.**
Per-principle compiler coverage (`compiled` | `uncompilable(reason)`), a
published coverage report, and an explicit fail-closed *promotion* step: the
bridge is `OBSERVED`/`CHECKED` until a named principle set reaches
`RUNTIME_BLOCKING`; it is never declared "live" on one seeded block. Only 7
principles carry a `structured_predicate` today, so full coverage is a
compiler-design task. Owner: UNOWNED, merge-CRITICAL.

**H5 — replace non-shrink with held-out capability + integrity — review F9.**
ACE warns of *context collapse*; TiMem shows value partly by **reducing**
recalled memory while keeping utility (arXiv:2601.02845) — so a never-shrink
rule rewards bloat and is Goodhartable. Replace with: answer/retrieval success
on frozen context-eval cases; source-attribution and contradiction rate;
stale-claim rejection; token/latency budget; semantic coverage of protected
facts; a curation receipt for any deletion/supersession; and an **ablation**
showing the playbook beats raw recall. Cite the real hook path
`dharma_swarm/chetana/claude_code_plugin/chetana/scripts/pre_compact.sh`.
Owner: UNOWNED + chetana.

**H6 — rlimits are not a network boundary — review F10.**
POSIX rlimits bound CPU/memory/file size but do **not** create a network
namespace. Options, stated honestly per receipt: (a) require
Docker/namespace/seccomp for untrusted or network-denied work and **fail
closed** if unavailable; (b) an OS sandbox with a tested network-deny; or (c)
keep `LocalSandbox` as a weak subprocess tier and **name that limitation in
every receipt**. Owner: `repository-titanium-hardening-2026-07`.

### Loops

**L1 — StrategyReinforcer behind H2a, via shadow/canary — review F11.**
Moves out of P0 to **after** H2a (it injects trace-derived text into the
system prompt — a provenance edge). `_distill_prompt_fragment` copies raw
task-prompt text (`strategy_reinforcer.py:280-291`), so fragments are
untrusted data. Requirements: receipt-grounded, source-classified strategies
only; injection scan + top-k/char budget; strategy ids + prompt digest in the
dispatch receipt; **no** strategy text may alter capability/authorization
fields; a counterfactual paired run without the strategy; rollback switch +
invalid-strategy negative control; Loop 7's **owner-surface** criterion, not
grep. Level: `RUNTIME_BLOCKING` (injection scan) + causal closure (§4). Owner:
`loop-closure-2026-06` × Titanium (`autonomous_agent.py`).

**L2 — separate producer/evaluator epochs — review F12.**
Do not let one optimization loop rewrite producer + repair prompt + rubric +
judge on the same data. Require: immutable versioned holdout tasks/outcomes;
producer and evaluator epochs separated (the Red Queen Gödel Machine's fixed
evaluation epochs, arXiv:2606.26294, are the model here, not "co-evolve
both"); deterministic checks stay authoritative; externally-grounded
calibration labels; **Brier only for explicit probability forecasts against
independently known outcomes** (`ginko_brier.py:133-168` needs a resolved
binary outcome); abstention + expected-calibration-error tracking; an
old/new/adversarial evaluator ensemble before promotion; the evaluator
candidate has **no write access to its own held-out evidence**. GEPA
(arXiv:2507.19457) optimizes prompts against an *external* metric — it does not
license a self-rewriting grader. Owner: `orchestration-arena-v1-2026-06` ×
`loop-closure-2026-06`.

**L3 — typed pause actuator — review F8.**
Implement an expiring, bounded `PAUSE_LOOP` **actuator** consuming an
independent supervisor `RECOMMENDATION` (the supervisor emits recommendation,
not actuation). Loop bodies honor a pause flag at tick with a receipt and
expiry; `REDUCE_SCOPE`/`ALERT_DHYANA` gain actuators or are renamed
`OBSERVATION`. Negative controls: pause honored within one tick, resume works,
observer cannot self-authorize. Owner: `loop-closure-2026-06`.

**L4 — earned acceptance.** Disposition `SUPPORTED`. Keep V1 r2:
route through the semantic gate **and** bind to declared artifacts + worktree
delta + test receipts (`agent_runner.py:2428-2434`); seeded empty-success run
recorded FAILED. Owner: UNOWNED; nearest `loop-closure-2026-06`.

**L5 — cycle/wall-clock bounds now, cost only with a hierarchical ledger — review F13.**
Sarathi's lesson: a parent loop can enqueue work whose downstream provider
cost never reaches the parent's direct-spend ledger. So L5 claims **only**
cycle and wall-clock bounds until a lineage-aware budget source charges
parent + children + retries + fallback providers + tool-mediated calls; a cost
bound must reserve from an authoritative hierarchical ledger before dispatch
and reconcile receipts after (this is the `budget` field of the
`ActionEnvelope`, §6). Owner: UNOWNED root script.

**L6 — named milestones, not an aggregate count — review F14.**
Drop `CLOSED_LIVE ≥ 5` as a terminal target (it invites easy-loop selection).
Named dependency-critical milestones, each with its owner criterion:
1. Loop 1's existing closure campaign + host-bound proof;
2. one memory/context loop with real external work and later served-context
   consumption (Loop 4 via H5+R4);
3. one verification loop whose verdict changes later routing/admission
   (Loop 2/6 via L2);
4. one event loop with durable delivery + consumer ack + backpressure
   (via E4);
5. any further loop only after its owner criterion is named here.
These are milestones, not a production-readiness claim. Owner:
`loop-closure-2026-06`.

**L7 — wire behind promotion boundaries, in an isolated worktree — review F11-adjacent + App finding.**
`run_coding_swarm` rewrites `task.workdir/task.edit_file` in place
(`coding_swarm.py:107,139`) — it must run in a disposable worktree/sandbox,
never the self-improvement checkout, and its output compared to the exact
proposal digest before promotion. Prove real callers and result consumption.
`self_improve` stays behind `DHARMA_SELF_IMPROVE`. Owner: UNOWNED; nearest
`sovereign-safety-tcb-2026-07`.

### Graph

**G1 — DAG honesty fixes.** Disposition `SUPPORTED`. Cycle → raise (not
truncate), atomic checkpoint tmp+rename+fsync (`workflow.py:252-255,391-392`).
Owner: `dharmagraph-engine-2026-07`.

**G2 — compile to the neutral engine, not the legacy DAG — review F7.**
V1's G2 invoked `execute_topology_genome_workflow`, which compiles to the
**legacy** `CompiledWorkflow` (`workflow.py:612-682`, `topology_genome.py:68-125`)
— cementing the exact split the spec diagnoses. Replace with:
1. define a `TopologyGenome` → **neutral DharmaGraph** compiler
   (`graph/schema.py:223-290`, `graph/compiler.py:188-437`);
2. **shadow-run** legacy and neutral engines on the same genome; diff semantic
   outcomes;
3. require durable receipts, negative controls, parity acceptance;
4. flip **one** scoped production lane only after the neutral engine passes;
5. retire/demote the legacy bridge after migration.
A caller grep is not evidence. Level: `CHECKED` (differential) → scoped
`RUNTIME_BLOCKING`. Owner: `dharmagraph-engine-2026-07` × arena.

**G3 — gauntlet ascent.** `SUPPORTED_WITH_FINDINGS`. LG24 retry/backoff,
LG19/20 interrupt facets; a governance assertion reads the receipt and
requires total > 58 **and** LG24 > 0 (the CLI `--check` only verifies
replay-vs-stored equality, `dharmagraph_parity_gauntlet.py:1231-1259`). Frozen
rubric + judge custody stay independent. Owner: `dharmagraph-engine-2026-07`.

**G4 — agent-as-node with effect fencing — review F7-adjacent + App finding.**
The durable invoker fences the **outer** dispatch (`orchestrator.py:2526-2560`);
the graph scheduler has no `wrap_invoker`, so resume re-runs a node from the
top. Each agent node needs a side-effect key from
(run_id, superstep, node_id, attempt) — the shape
`derive_graph_side_effect_key` provides (`graph/durable_invoker.py:122`) —
wired into node dispatch; acceptance asserts **exactly one** provider
invocation across a mid-superstep crash. Owner: `dharmagraph-engine-2026-07`.

**G5 — one HITL protocol.** `SUPPORTED`. Default-REJECT, durable
request/response identity. Owner: `dharmagraph-engine-2026-07`.

### Events

**E1 — cron unification (BR-004).** `SUPPORTED`. One authority; the repo
declaration is the **root** `cron_jobs.json` (`cron_unify.py:31`; the
docstring's "17 jobs" and `dharma_swarm/cron_jobs.json` path are stale — fix
them); `--check` computes the orphan count from files it reads. Add durable
schedule receipts. Owner: UNOWNED; register against BR-004.

**E2 — repair the emitter, then default to propose-only — review F15 + App finding.**
The emitter is broken: `orchestrate_live.py:1822` calls
`SignalBus.get().emit("GAUNTLET_REGRESSION", {...})` with two args, but
`emit(event: dict)` takes one (`signal_bus.py:143`) — the `TypeError` is
swallowed, so the signal has **never** fired. Step 1: convert to
`emit({"type": "GAUNTLET_REGRESSION", ...})`. Step 2: the first live edge is
`regression → deduplicated incident → diagnosis/proposal → deterministic
reproduction → existing promotion authority`, **not** `regression → mutation
loop`. Add event identity, cooldown, dedup, causal component attribution,
immutable reproduction, budget reservation, propose-only default. One Wire is
necessary but is not a general authorization token. Acceptance: a test through
the **real producer path** (not a seeded bus event). Owner:
`loop-closure-2026-06` × `sovereign-safety-tcb-2026-07`.

**E3 — a real authenticated reviewer service — review F16.**
`pr_merge_control.py:746-747` strips `ANTHROPIC_API_KEY` by default, and a
GitHub runner has no CLI binary/entitlement/receipt transport — so a hosted
`claude -p` job is under-specified, and `workflow_dispatch` is manual (not an
event loop). Before counting E3, specify: executable service boundary,
authentication owner, secret scope, timeout, concurrency, dedup, kill-switch
behavior, receipt schema, commit pin, and an **automatic** (scheduled or
webhook) trigger. The live cloud reviewer today is the native Codex GitHub App
via the trusted-login map (`pr_merge_control.py:1013-1032`) — document that as
the reviewer lane. Owner: `merge-master-mike-d4-2026-06`.

**E4 — NATS afferents.** `SUPPORTED_WITH_FINDINGS`. Host evidence + durable
consumer acknowledgement + dedup + backpressure; no prose liveness (checks:
`check_nats_substrate_contract.py`, `check_nats_live_production_evidence.py`).
Owner: `organism-rewire-2026-07` × Titanium.

---

## 6. Missing architecture — the constitutional ActionEnvelope (review §5, condition 11)

V1 added many wires but no single enforcement boundary. Every consequential
effect enters one typed envelope whose action class determines mandatory
fields; callers may not choose which controls to omit:

```text
ActionEnvelope
  execution_identity  task_id / run_id / trace_id / claim_id / causation_id / parent_run_id
  graph_position      graph_id / node_id / allowed_edge / attempt / checkpoint_id
  context_identity    context_digest / prompt_version / memory_receipt_ids
  capability          tool / effect_kind / resource / destination / allowed_domain
  provenance          planner_source / argument_sources / trust_labels / external_content_ids
  risk_reversibility  risk_class / rollback_plan / irreversible_boundary
  authority           warrant / lease / operator_approval / expiry / scope
  budget              parent_reservation / child_reservation / currency / token_ceiling
  idempotency         side_effect_key / operation_hash / ownership_token
  verification        deterministic_checks / evaluator_version / required_abstention_policy
  outcome             result_digest / cost / error / rollback_status
  evidence            prepared_receipt / committed_receipt / consumer_closeback
```

A read-only research call requires only identity, context, graph position,
capability, and a receipt. A code apply, outbound message, payment, deploy,
credential op, or merge requires the full applicable contract. The envelope
passes through **one effect dispatcher** with live / record / replay / shadow /
deny handlers — where CaMeL-style capability separation (H2a), runtime warrants
(H4), reversibility, hierarchical budget reservation (L5), idempotency (G4),
and transactional evidence become one constitution rather than optional
adjacent organs. This composes with the repo's existing `ExecutionIdentity` /
`tool_registry` spine (`dharma_swarm/tool_registry.py:29-34`) rather than
replacing it.

**This is the campaign kernel: every consequential workstream (H1b, H2, H4,
L1, L7, E2, G2, G4) targets the dispatcher rather than a bespoke check.** It is
a prerequisite, and it is the one genuinely new build V2 adds beyond V1.

Research anchor: ETAS, *An Effect-Typed Language for Agent Systems*
(arXiv:2607.17780, HKUST, Jul 2026) formalizes exactly this — tracking each
computation with an escaping effect row and a persistent abstraction of the
typed action trace it may request. Composable effect handling for LLM scripts
(arXiv:2507.22048, ACM LMPL 2025) supplies the live/record/replay/deny handler
pattern.

---

## 7. Corrected execution order (review §6, condition 6)

The article's order — harness first; then simplest loop + grader; then graph
for known decisions; then event/hill-climb — restored.

**P0 — constitutional harness before new autonomy**
1. Typed closure contracts (§2) + enforcement levels (§3).
2. `ActionEnvelope` + single scoped effect dispatcher (§6).
3. H3 shell policy (frozen digest + sabotage tests).
4. H1a harden hook → H1b install (fail-closed + receipt tests first).
5. H2a deterministic provenance/capability; **no** positive judge authority.
6. H6 resource limits + honest isolation-tier contract.
7. Hierarchical parent/child budget reservation, or prohibit cost claims (L5).

**P1 — simplest bounded loop + deterministic grader**
1. L4 earned acceptance (empty-success negative control).
2. L5 cycle/wall-clock bounds; cost only when authoritative.
3. L1 StrategyReinforcer in shadow/canary **after H2a**, causal + ablation.
4. L3 one typed expiring pause actuator.
5. L7 one orphaned verifier behind existing promotion authority.

**P2 — graph only where the path is known.** Minimal production macrograph,
with open-ended work retained inside one agentic node (the article's
"don't over-graph" rule):

```text
ADMIT → COMPILE_CONTEXT → EXECUTE_AGENTIC_NODE → VERIFY → DECIDE
      → AUTHORIZE_EFFECT → COMMIT_EFFECT_AND_RECEIPT → CONSUME_CLOSEBACK
      → COMPLETE | RETRY | ESCALATE
```

Then: G1 honesty fixes; neutral-DharmaGraph shadow seam + differential (G2);
G5 one default-reject HITL; G4 agent-as-node with durable identity + effect
fencing; G2 genomes compile to the neutral engine; G3 gauntlet ascent + scoped
promotion.

**P3 — event and hill-climbing loops**
E1 durable schedule + drift check; E4 durable afferents + ack/backpressure;
E2 regression → incident/proposal (propose-only default); E3 authenticated
automatic reviewer; L2/H2b judge canary with immutable labels + calibration;
GEPA/ACE/HarnessX/workflow-search candidates through separated evaluator
epochs; named `CLOSED_LIVE` promotions as each owner criterion passes; only
then consider evaluator evolution or broader self-improvement.

---

## 8. Non-charmable scoreboard (review §7, condition 9)

Every V1 grep/existence/prose criterion replaced with executed, receipted,
negative-control evidence.

| # | Criterion | Non-charmable check |
|---|---|---|
| 1 | Loop 7 causally closed | live-canary receipt names strategy ids + prompt digest; counterfactual run omitting the strategy removes the decision delta; invalid strategy rejected |
| 2 | Named live milestones (not a count) | each L6 milestone: host binding + causal consumer receipt + negative control + non-author review |
| 3 | Supervisor pause honored | runtime actuator receipt + loop tick proving pause honored, expiry/resume works, observer cannot self-authorize |
| 4 | No dead signal edges | typed topic registry + delivery receipt + consumer ack + no-op/failed-consumer negative control + explicit observation-only topics; every `emit` call type-checks against `emit(event: dict)` |
| 5 | Gauntlet ascent | frozen rubric + exact candidate SHA + judge custody + mutation/sabotage proof + row-level semantic delta (total > 58, LG24 > 0) |
| 6 | Topology on the neutral engine | shadow execution through neutral DharmaGraph on representative genomes + semantic differential + checkpoint/retry/idempotency proof |
| 7 | Cron orphan 0 | `cron_unify.py --check` derives the count from the files it reads |
| 8 | Judge calibrated | probability forecasts on immutable independently-labeled outcomes; Brier/ECE/coverage/abstention reported by version |
| 9 | No gate weakened | frozen machine-readable policy manifest + mutation tests that weaken each protected rule and prove the gate fails (a table diff is not acceptance) |
| 10 | Checks enforced, not just present | each new check appears in a `required` context or is consumed by Merge Master; advisory status reported as `CHECKED`, not `ENFORCED` |
| 11 | Effect boundary real | a consequential action with a missing/invalid `ActionEnvelope` field cannot commit (RUNTIME_BLOCKING negative control) |

---

## 9. Adoption / ownership table (review F17, condition 12)

"No new track" is discipline only if the work is actually admitted by existing
owners. No item below is executable until its row is adopted into the owning
track's `next_items`.

| Item | Changed-file globs | Owning track(s) | Cross-track ack | Merge-risk | Operator-only |
|---|---|---|---|---|---|
| §6 kernel | new `dharma_swarm/effects/**` (proposed), `tool_registry.py` | UNOWNED → portfolio | Titanium (spine) | HIGH | envelope schema ratification |
| H1a/b | `hooks/telos_gate.py`, `.claude/settings.json` | UNOWNED | safety-TCB | MEDIUM | — |
| H2a | `telos_gates.py`, `api/chat_tool_execution.py`, effects module | UNOWNED, merge-CRITICAL | Titanium | CRITICAL | human-approved PR |
| H3 | `autonomous_agent.py`, `sandbox.py`, `api/chat_tool_execution.py`, new module | Titanium + UNOWNED | portfolio | MEDIUM | — |
| H4 | `dharma_kernel.py`, `telos_gates.py` | UNOWNED, merge-CRITICAL | safety-TCB | CRITICAL | `[kernel-amendment]` |
| L1 | `autonomous_agent.py`, `strategy_reinforcer.py`, `reports/loop_closure/**` | Titanium × loop-closure | both | HIGH | — |
| L2 | `agent_runner_quality.py`, `quality_gates.py`, `ginko_brier.py`, arena | arena × loop-closure | both | HIGH | — |
| L3/L4/L6 | `loop_supervisor.py`, `orchestrate_live.py`, `overnight_director.py`, closure surfaces | loop-closure | — | MEDIUM | — |
| L5 | `agent_loop.sh`, budget ledger | UNOWNED | Titanium | LOW | — |
| L7 | `forge_v1/**`, `reflexion.py`, `self_improve.py` | UNOWNED | safety-TCB | HIGH | `DHARMA_SELF_IMPROVE` |
| G1–G5 | `dharma_swarm/graph/**`, `workflow.py`, `orchestrator.py`, `topology_genome.py` | dharmagraph × arena | arena | HIGH | — |
| E1 | `cron_unify.py`, `cron_jobs.json` | UNOWNED | — | LOW | BR-004 |
| E2 | `orchestrate_live.py`, `signal_bus.py`, `self_improve.py` | loop-closure × safety-TCB | both | HIGH | — |
| E3 | `.github/workflows/**`, `pr_merge_control.py` | merge-master | — | MEDIUM | secret scope |
| E4 | `tools/*_go/**`, NATS checks | organism-rewire × Titanium | both | MEDIUM | host |

---

## 10. Research (review §4, condition 13)

**Sources V1 read correctly (retained):** GEPA (arXiv:2507.19457) — reflective
prompt evolution against an *external* metric, not a license for self-rewriting
graders; ACE (arXiv:2510.04618) — structured context playbooks, not monotonic
growth; CaMeL (arXiv:2503.18813) — deterministic separation outside the model;
DGM/HGM/Red Queen/Group-Evolving (arXiv:2505.22954, 2510.21614, 2606.26294,
2602.04837) — candidate generators, custody unchanged; MAST (arXiv:2503.13657)
— post-run taxonomy needing a labeled validation set; RUVER-BENCH
(arXiv:2606.29920) — long-context judges stay noisy.

**Additions the review surfaced (verified where checked):**
1. **ETAS — Effect-Typed Language for Agent Systems** (arXiv:2607.17780,
   verified) — the research analogue of §6's ActionEnvelope.
2. **Composable Effect Handling for LLM Scripts** (arXiv:2507.22048, ACM
   LMPL 2025) — the effect-dispatcher handler pattern.
3. **Agent libOS** (arXiv:2606.03895) — explicit capabilities/runtime
   primitives over prompt-level gates.
4. **HarnessX** (arXiv:2606.14249) — trace-driven harness foundry for L4;
   candidates must pass immutable evaluations before promotion.
5. **Agent Lightning** (arXiv:2508.03680, verified — Microsoft Research) —
   decoupled execution/training + hierarchical credit assignment; addresses
   the parent-loop/child/retry/tool credit problem behind L5.
6. **ADAS / Meta Agent Search** (arXiv:2408.08435, verified — Hu, Lu, Clune) —
   foundational prior work that should precede AFlow/MaAS/EvoAgentX in R5's
   lineage.
7. **AgentSentry** (arXiv:2602.22724) — counterfactual re-execution at
   tool-return boundaries; a stronger "did untrusted data change a later
   action?" test than caller grep.
8. **AgentDyn / AutoDojo** (arXiv:2602.03117, 2606.15057) — adaptive injection
   evaluation to complement the fixed seeded corpus.
9. **SHADE-Arena / BashArena / constitutional black-box monitoring**
   (arXiv:2506.15740, 2512.15688, 2603.00829) — privileged-agent sabotage
   detection and monitor-overfitting risk.
10. **Causal Past Logic for distributed agent runtimes** (arXiv:2605.20923) —
    causal closure receipts across asynchronous consumers (directly relevant
    to §4).

Items 3, 4, 7, 8, 9, 10 are carried on the Codex review's 0.91-confidence
attribution pending independent verification; items 1, 5, 6 were verified
against arXiv during V2 authoring.

**Adoption rule (replaces V1's generic rule).** A research mechanism enters a
live path only after: (1) candidate generated in an isolated lane; (2)
immutable evaluator version chosen before candidate results are known; (3)
hermetic replay + adaptive/adversarial cases; (4) counterfactual/ablation
evidence for the claimed benefit; (5) no candidate access to held-out labels,
evaluator internals, or promotion credentials; (6) independent review +
current-track ownership; (7) scoped canary with rollback; (8) no One Wire,
chamber, safety-TCB, or human-authority relaxation.

---

## 11. Merge conditions status (review §8)

The review set 13 conditions for PR #1186. V2 addresses each:

| # | Condition | V2 location |
|---|---|---|
| 1 | Typed harness/loop/graph/event contracts | §2 |
| 2 | Enforcement levels observed/checked/merge-blocking/runtime-blocking | §3 |
| 3 | Causal consumption + decision delta + negative control + owner criterion | §4 |
| 4 | Split H1; remove false quarantine/fail-closed implications | §5 H1a/H1b |
| 5 | H2 deterministic first; no judge-granted authority | §5 H2a/H2b |
| 6 | Reorder phases; constitutional harness before L1/L2/E2/E3/G2 | §7 |
| 7 | G2 neutral-DharmaGraph compiler + differential shadow | §5 G2 |
| 8 | Named milestones, not aggregate `CLOSED_LIVE ≥ 5` | §5 L6 |
| 9 | Executed/receipted/negative-control acceptance everywhere | §8 |
| 10 | Separate producer/rubric/evaluator epochs + immutable holdouts | §5 L2 |
| 11 | ActionEnvelope / effect-dispatch boundary as kernel | §6 |
| 12 | Exact surface-owner/adoption table | §9 |
| 13 | Effect-system / capability / harness-evolution / credit / security / AI-control research | §10 |

## 12. Risks (carried + sharpened)

- **Goodharting graders** — deterministic scorers stay sole correctness
  authority (`arena/scorer.py:22-47`); evaluator custody per §5 L2/R6.
- **Telemetry attack by self-modifying code** (DGM App. F,
  `DHARMAGRAPH_PHASED_SPEC:121-125`) — immutable evaluator outside
  co-evolution; One Wire + protected-file lists remain the backstop.
- **Injection surface grows with consumption edges** — every external-content
  consumer (L1, E2–E4, R4) routes through H2a's `ActionEnvelope` provenance;
  no such edge ships before H2a (the P0 reordering enforces this).
- **Constitution risk** — a single effect dispatcher is itself a
  merge-CRITICAL surface; it lands additively behind the existing spine, is
  fail-open only where an action is provably read-only, and every consequential
  path fails closed on a missing envelope field.
- **WIP ceiling** — ten active tracks is the max; V2 adds none. Unowned items
  wait for adoption (§9).

## 13. Provenance

- V1: `docs/plans/HARNESS_LOOP_GRAPH_HUMMING_SPEC_2026-08-01.md` (SUPERSEDED).
- Review: `docs/plans/handoffs/CODEX_HUMMING_SPEC_ADVERSARIAL_REVIEW_2026-08-01.md`
  (PR #1187), verdict 57/100, confidence 0.91.
- Automated App review: PR #1186, 22 line findings (all adopted in V1 r2).
- This V2 grants no authority; adoption is per §9 through the owning tracks.
