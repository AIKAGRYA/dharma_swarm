# SOVEREIGN MANIFEST: SYSTEM SOURCE OF TRUTH

**Purpose**: This document is the absolute ground truth for the dharma_swarm repository. All AI agents, regardless of model or tab, MUST ingest, comprehend, and adhere to this context before outputting a single line of code.

**Generated**: 2026-04-04 | Count refresh: 2026-06-09 filesystem verification
**Prior audit**: 2026-04-04 | 5-model convergent audit (Claude, DeepSeek, GPT-OSS, Codex, RUFLO)
**Authority**: This file + `CLAUDE.md` are the two canonical governance surfaces. When they conflict, `CLAUDE.md` wins on behavioral rules; this file wins on architectural truth.

**Verification method**: Count-sensitive claims below were refreshed against the filesystem on 2026-06-09. Architecture prose still reflects the 2026-04-04 audit unless specifically marked otherwise. Recheck counts before citing them in future work.

**Substrate-nativeness status**: The current runtime is ~10–15% ontology-native; ~85–90% of runtime work bypasses substrate. See [`reports/audit/end_to_end/000_MASTER_COHERENCE_SYNTHESIS.md`](../../reports/audit/end_to_end/000_MASTER_COHERENCE_SYNTHESIS.md) for the audit that established this estimate.

**Active build tracks**: declared in [`ACTIVE_TRACK.yaml`](ACTIVE_TRACK.yaml) and surfaced by `make onboard`. Do not duplicate track names in prose here — the YAML is the single source of intent. The governing principle: the operator may run between `min_active` and `max_active` concurrent tracks (default floor 1, ceiling 10) as declared by `track_policy` in `ACTIVE_TRACK.yaml`. Opening additional tracks beyond the floor is operator discretion, not automatic — each concurrent track must have a clear owner, distinct surfaces, and non-overlapping non-goals. A portfolio of one is fine — concurrency is authorized, not mandated — and equally, opening a second co-equal track when the operator proposes new work is the expected response, never a violation of an existing track. **To open a track** (e.g. when the operator proposes a new project — treat that as a new track, never a violation): add an entry under `active_tracks:` in `ACTIVE_TRACK.yaml` with `serves:` a spine objective, `owned_surfaces:`, and acceptance criteria, then run `scripts/governance/render_active_track_includes.py`; `check_track_status.py` enforces WIP limit, spine binding, surface non-overlap, and edge/cycle validity. Rationale: with 10+ agent contributors active on the repo (387 commits in the last 30 days as of 2026-05-31), serializing all work behind one track creates unbounded queueing on the operator and on review capacity. Concurrency is gated on non-overlap, not on agent count.

<!-- ACTIVE_TRACK:START -->

<!-- This block is generated from docs/governance/ACTIVE_TRACK.yaml.
     Do not hand-edit. Run scripts/governance/render_active_track_includes.py
     after updating the YAML. -->

**Active portfolio:** 10 co-equal track(s) (WIP warn 5, max 10). A new project is a new track here, not a violation — model: 1..N co-equal active tracks; typed graph; WIP-limited; surface-owned.

**Spine objectives (each track serves one):**

- `substrate-nativeness` — Substrate nativeness — runtime flows through the ontology/spine, not around it (covered)
- `revenue-external-humans-served` — Revenue & external humans served — value leaves the house and someone acts on it (**no active track**)
- `research-depth` — Research depth — the contemplative-mechanistic bridge (R_V, geometric lens) deepens (**no active track**)

### Runtime Truth Reconciliation — operator-visible truth packets

**Track id:** `runtime-truth-reconciliation-2026-06` · **Status:** ACTIVE · **Owner:** @AmitabhainArunachala
**Serves spine objective:** `substrate-nativeness` · **Verified at:** 2026-06-23 (TTL 14 days)
**Relations:** complements: runtime-truth-nats-2026-06
**Owns surfaces:** dharma_swarm/operator_core/**, scripts/governance/agent_onboard.py, dharma_swarm/runtime_state.py
**Moves vital signs:** quality_gates, memory_persistence

The Runtime Truth Spine substrate is merged and shippable. This track moves
from substrate existence to read-only reconciliation: operator-visible
runtime truth packets that separate heartbeat, readiness, artifact progress,
completion, authority, projection/cache, mutation, and external-gated proof.

The track must not create a new truth store, daemon, receipt system, or
authority surface. It projects from existing owners only:
spine.EvidenceReceipt for in-flight dispatch proof, runtime_state.RuntimeReceipt
for persisted runtime receipts, IdempotencyRecord for exactly-once substrate,
and existing operator/onboard/control-surface rows for read-only rendering.

Doctrine line that must hold:
  Read models project truth from owners; they do not become authority.

**Next items:**

- [code] SHIPPED: read-only RuntimeTruthPacket contract in operator_core (dharma_swarm/operator_core/contracts.py:125; tests/test_operator_core_contracts.py 7 passed).
- [code] SHIPPED: compact runtime truth rendered in make onboard (scripts/governance/agent_onboard.py) as a read model, not an authority surface.
- [test] Protect A2A single-persistence invariant while adding runtime truth projections.

**Non-goals:**

- Do not create a new daemon, database, event log, truth store, or receipt system.
- Do not mint a second RuntimeReceipt for A2A or paths with an inner runtime owner.
- Do not mutate external systems, live processes, archive fitness, payments, or gateways.
- Do not broadly refactor orchestrator.py, agent_runner.py, swarm.py, providers.py, or SwarmManager.
- Do not build Verified Experiment Loop runtime in this track.
- Do not create standalone BetCard, Experiment, SwarmRun, DecisionRecord, LineageRecord, WikiUpdate, or cost-tracker classes.

### Runtime Truth NATS — internal live transport for A2A dispatch

**Track id:** `runtime-truth-nats-2026-06` · **Status:** ACTIVE · **Owner:** @codex
**Serves spine objective:** `substrate-nativeness` · **Verified at:** 2026-06-07 (TTL 21 days)
**Relations:** complements: runtime-truth-reconciliation-2026-06
**Owns surfaces:** docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md, dharma_swarm/a2a/a2a_nats_contact.py, dharma_swarm/a2a/a2a_core_contact.py
**Moves vital signs:** tool_coverage

The concurrent Codex transport lane. NATS was scoped out of the global
prohibition by the 2026-05-31 doctrine amendment and runs as a concurrent
scoped track with non-overlapping surfaces (transport layer only). This
track wires the internal live transport so A2A dispatch can travel at
broker speed, distinct from the reconciliation lane's read-model surfaces.

Surface separation is the safety boundary: this track owns the NATS
transport contact modules and the master spec; it does not touch the
operator_core read models the reconciliation lane owns.

Closure for this track means offline substrate wiring is test-backed and
governance-visible. It is not a production live-readiness claim. Live ACL
proof, cross-host broker proof, and semantic liveness/domain-receipt proof
remain separate operator-runtime gates.

**Next items:**

- [code] Confirm NATS transport contact modules are wired and receipted end-to-end.

**Non-goals:**

- Do not introduce Redis or gRPC as part of this track.
- Do not touch the operator_core read-model surfaces owned by the reconciliation lane.
- Do not add a parallel spine-check CI workflow.
- Do not claim production live readiness without live ACL, cross-host broker, and semantic liveness proof.

### Runtime Truth Spine — Adoption (god objects flow through invoke_agent)

**Track id:** `runtime-truth-spine-adoption-2026-06` · **Status:** ACTIVE · **Owner:** @AmitabhainArunachala
**Serves spine objective:** `substrate-nativeness` · **Verified at:** 2026-06-10 (TTL 21 days)
**Relations:** complements: runtime-truth-reconciliation-2026-06, runtime-truth-nats-2026-06
**Owns surfaces:** dharma_swarm/spine/**, dharma_swarm/a2a/a2a_bridge.py, dharma_swarm/orchestrator.py, dharma_swarm/agent_runner.py, scripts/uplift_guards/check_spine_ownership.py
**Moves vital signs:** quality_gates, tool_coverage

spine-adoption ships end-to-end: every production dispatch flows through
invoke_agent() and emits exactly one EvidenceReceipt. This track migrates
the god objects (agent_runner.py, orchestrator.py, a2a_bridge.py) onto
the shipped spine substrate. Target: 3 production callers outside the
spine package, zero bypass paths. Substrate-nativeness moves toward 30%+.

Ported 2026-06-10 from the v1 declaration (opened 2026-06-06 on the
qwen/spine-adoption lane, commit c28951d5b, which closed reconciliation
in v1) into the v2 portfolio while merging origin/main. In the v2
multi-track model it runs as a co-equal peer of the reconciliation and
NATS lanes rather than requiring their closure; reconciliation's open
status is main's standing declaration and is left to the operator.

**Next items:**

- [code] (blocker) Wire a2a_bridge.submit_via_spine into production dispatch (ingest_trishula_inbox bypass at a2a_bridge.py:307 — Slice 2 per scripts/governance/spine_bypass_report.py).
- [code] (blocker) orchestrator.py dispatch through invoke_agent behind DHARMA_SPINE_DISPATCH (landed via #557; operator confirms one live EvidenceReceipt on a real dispatch = GATE 1).
- [code] (blocker) Migrate agent_runner.py run_task through invoke_agent(). Largest surface, last.
- [code] (blocker) Drain the intentional-bypass allowlist (node_gateway submit endpoints, a2a_client._dispatch_local) and enable allow-list-at-zero in uplift_guards CI.
- [docs] Author docs/architecture/SPINE_ADOPTION_NARRATIVE.md

**Non-goals:**

- Do not create new spine sub-modules. Adopt invoke/receipt/routing/persistence.
- Do not decompose agent_runner.run_task beyond invoke_agent() routing.
- Do not change EvidenceReceipt schema; adopt shipped types unchanged.
- Do not introduce NATS, Redis, or gRPC in this track (transport belongs to the NATS lane).
- Do not broadly refactor swarm.py, providers.py, or SwarmManager.

### Cybernetic Loop Closure — wire all 13 loops with receipted closure checks

**Track id:** `loop-closure-2026-06` · **Status:** ACTIVE · **Owner:** @AmitabhainArunachala
**Serves spine objective:** `substrate-nativeness` · **Verified at:** 2026-06-11 (TTL 21 days)
**Relations:** complements: runtime-truth-reconciliation-2026-06
**Owns surfaces:** reports/loop_closure/**, CYBERNETIC_LOOP_MAP.md
**Moves vital signs:** quality_gates, eval_coverage

Operator-instructed campaign (2026-06-11 master prompt): wire all 13
cybernetic loops in CYBERNETIC_LOOP_MAP.md until each runs
sense->interpret->constrain->act->adapt on real data with receipts to
its declared owner surface and an automated closure check.

Phase 0 (research dossier, no build code) ships first. Phases proceed
in dependency-lattice order: Loop 1 trunk (provider chain + dispatch),
then the fed cascade (6,2,5,9 -> 3,4,7 -> 8,10,11), then Loops 12/13
gated behind the One Wire external-receipt quorum (N>=5, M>=3).

Invariant that must hold throughout:
  Internal artifacts never touch archive fitness; only countersigned
  external acted receipts above quorum do.

**Next items:**

- [code] (blocker) Phase 1a: provider chain hardening — separate failure state classes, fallback ordering, honest smoke receipts (no real key required).
- [ops] CORRECTED 2026-06-23: NO operator key is required to close Loop 1. Dispatch is keyless via the claude_code lane (live whenever the claude binary is present; key_oracle.dispatchable_now()). The old 'one real provider key (OPENROUTER recommended)' item was the propagated 'no provider' lie — a key only widens the roster.
- [code] Phase 1b: Loop 1 closure under orchestrate_live with DHARMA_SPINE_DISPATCH=1, dispatch_dropoff receipted, closure check in make orient.

**Non-goals:**

- Do not weaken, bypass, or hard-code any telos gate to close a loop.
- Do not let internal artifacts touch archive fitness (One Wire quorum stands).
- Do not touch the operator_core read-model surfaces owned by the reconciliation lane.
- Do not commit provider API keys or any credentials.
- Do not create a new truth store, receipt system, or state owner; extend loop_supervisor and existing owners.

### Truth Graph Platform v1 — repo context + receipted A2A presence

**Track id:** `truth-graph-platform-2026-06` · **Status:** ACTIVE · **Owner:** @codex
**Serves spine objective:** `substrate-nativeness` · **Verified at:** 2026-06-23 (TTL 21 days)
**Relations:** complements: runtime-truth-reconciliation-2026-06, runtime-truth-nats-2026-06 · depends_on: orientation-graph-2026-06
**Owns surfaces:** scripts/governance/orientation_graph.py, scripts/governance/truth_graph_nats_e2e_demo.py, scripts/governance/run_truth_graph_nats_e2e_demo.sh, tests/test_orientation_graph.py, tests/test_truth_graph_repo_context.py, dharma_swarm/a2a/task_receipt.py, dharma_swarm/a2a/agent_presence.py, tests/test_a2a_gate.py, tests/test_agent_registry_presence.py, reports/orientation/**
**Moves vital signs:** quality_gates, tool_coverage, memory_persistence

Operator directive 2026-06-12: move dharma_swarm toward a single truth
graph that every agent reads, with an advanced A2A layer and fast
coordination across many registered agents. This track absorbs the
completed orientation graph and turns it into one generated repo context
artifact plus receipts-only A2A gate helpers and agent heartbeat
projection.

The track creates NO new truth store and NO authority surface. It
projects from the existing owners only: foundations/THE_ORGANISM.md
and docs/vision_maps/NORTH_STAR.md (identity),
docs/governance/VENTURE_CELL_PORTFOLIO.yaml (organs),
docs/governance/ACTIVE_TRACK.yaml (tracks),
docs/docops/assertions.yaml canonical_guard.registered + the worktree
(custody), ~/.dharma/ops/parallel_lane_map.json (lanes),
~/.dharma/a2a_bus/agents.json and ~/.dharma/agents/* (agent presence),
the live ops census receipt (liveness), ~/.dharma/ops/deploy_receipt.json
(body state), A2A bus receipt roots, and docs/state/BROKEN_REGISTER.md
(broken).

Doctrine line that must hold (same as the reconciliation lane's):
  Read models project truth from owners; they do not become authority.

A2A ingress must reject unstructured essays where this track owns the
boundary. The schema is deliberately plain:
claim, evidence, verdict, next_action, files_changed.

**Next items:**

- [code] SHIPPED: repo_context artifacts committed on origin/main (reports/orientation/repo_context.{json,md}, commit ea793d3bd); make orient wired.
- [test] SHIPPED: NATS CLI e2e demo ran; receipt renders in repo_context (reports/orientation/nats_e2e_receipt.json, commit 936d365db).

**Non-goals:**

- Do not create a new daemon, database, vector store, event log, or truth store.
- Do not mutate live A2A registry owners from this repo track.
- Do not duplicate make onboard's state rendering; repo_context is a generated projection.
- Do not touch operator_core/** or runtime_state.py.
- Do not touch scripts/runtime/a2a_send.py or scripts/runtime/autonomy_spine.py.
- Do not claim full future NATS spec compliance from the CLI demo alone.

### Composer Holon Spine Longrun — fable/codex pair over verified command receipts

**Track id:** `composer-holon-spine-longrun-2026-06` · **Status:** ACTIVE · **Owner:** @AmitabhainArunachala
**Serves spine objective:** `substrate-nativeness` · **Verified at:** 2026-06-23 (TTL 14 days)
**Relations:** complements: runtime-truth-reconciliation-2026-06, runtime-truth-nats-2026-06 · depends_on: runtime-truth-spine-adoption-2026-06
**Owns surfaces:** docs/sovereign_holons/**, reports/sovereign_holons/**, dharma_swarm/holon_*.py, scripts/holon_*.py, tests/test_holon_*.py
**Moves vital signs:** quality_gates, tool_coverage, memory_persistence

Build A from the composer convergence: merge Verified Composer Command
Spine v1 with the Sovereign Holon Orchestrator target, bringing
fable_composer and codex_composer up as the first read-only composer
holon pair. The track is active as a scoped longrun lane, not as a new
receipt owner. Command receipts are projections of spine.EvidenceReceipt.

The clean GitHub-main mirror remains the merge target; the active build
lane currently lives on qwen/spine-adoption because that lane contains
the holon docs, modules, and verifier tests. The lane must reconcile back
to main through the normal review path before it is called shipped.

**Next items:**

- [test] SHIPPED: frozen Build A verifier set runs green on origin/main (tests/test_holon_bridge.py + test_holon_runtime.py; 103 passed/1 skipped 2026-06-23).
- [runtime] SHIPPED: unattended fable_composer + codex_composer wakes witnessed with fresh state files (reports/sovereign_holons/COMPOSER_WAKE_WITNESSED.md, 2026-06-11).
- [code] SHIPPED: living_agent_kernel on origin/main (dharma_swarm/operator_core/living_agent_kernel.py); import green.
- [governance] SHIPPED: holon substrate reconciled to main via PR #585 (commit 9c76b210, 2026-06-12).

**Non-goals:**

- Do not create a new durable receipt store; project over spine.EvidenceReceipt.
- Do not send outreach, deploy, push, or open PRs in this track without a later explicit lease.
- Do not claim unattended 90% confidence until fable and codex both leave fresh wake receipts.
- Do not merge holon substrate to main without the frozen verifier runbook passing.

### Provider Routing Consolidation — one power-first router, explicit-wins, first-party paths

**Track id:** `provider-routing-consolidation-2026-06` · **Status:** ACTIVE · **Owner:** @AmitabhainArunachala
**Serves spine objective:** `substrate-nativeness` · **Verified at:** 2026-06-22 (TTL 21 days)
**Relations:** complements: runtime-truth-spine-adoption-2026-06, loop-closure-2026-06
**Owns surfaces:** dharma_swarm/providers.py, dharma_swarm/provider_policy.py, dharma_swarm/model_hierarchy.py, dharma_swarm/model_pool.py, dharma_swarm/model_defaults.py, dharma_swarm/runtime_provider.py, dharma_swarm/router_v1.py, dharma_swarm/smart_router.py, dharma_swarm/decision_router.py, docs/ops/PROVIDER_ROUTING_ARCHITECTURE.md
**Moves vital signs:** quality_gates, tool_coverage, cost_efficiency

Operator directive 2026-06-21: consolidate the LLM provider/model routing
subsystem into one coherent, malleable, intelligent router. RESOLVED — all
five stages landed on origin/main 2026-06-21; this records what was fixed,
not open work. The DECISION layer had drifted: an explicit provider/model
request was treated only as a constraint, not a selection (provider_policy
did not read context["preferred_provider"]); the two rank systems disagreed
(model_hierarchy.CANONICAL_SEED_ORDER free-first vs model_pool._PROVIDER_RANK
first-party-first); and ~8 router files stacked reorder passes with no single
documented precedence. All three are now fixed: provider_policy.py pins an
explicit provider (pin + safe fallback), selection is power-first with
CANONICAL_SEED_ORDER demoted to historical fallback, and the single
precedence is documented in docs/ops/PROVIDER_ROUTING_ARCHITECTURE.md and
locked by an invariant test.

The data/registry half (model_hierarchy -> model_pool -> model_defaults,
keys in api_keys) was already consolidated and is preserved; this track
fixed the decision half and the wiring gaps, converging on the existing
registries (no new truth store).

Four operator decisions are LOCKED (2026-06-21):
  1. Default selection = POWER-FIRST (most capable model by default; cost
     is an opt-in nudge). Reverses today's free-tier-first default.
  2. Explicit request = PIN + SAFE FALLBACK (exact provider/model wins;
     fall back to the ranked chain only if down / no live key).
  3. Architecture = UNIFY, KEEP SMARTS (keep session-affinity, EWMA memory,
     reward learning, canary; collapse them under ONE documented precedence).
  4. New first-party path = z.ai / Zhipu / GLM direct (Moonshot/Kimi stays
     via OpenRouter for now).

Precedence the router must follow, documented in one place:
  explicit > capability/power > malleable overlays (cost/path/lang/tooling)
  > learned (affinity/EWMA/reward/canary) > availability prune (first-party
  preferred, OpenRouter last) > fallback chain walk.

**Next items:**

- [docs] SHIPPED: docs/ops/PROVIDER_ROUTING_ARCHITECTURE.md — the one precedence + module map + migration.
- [code] SHIPPED (commit e7e0e55d): Stage 1 — provider_policy consults context['preferred_provider'] as SELECTION (pin + safe fallback).
- [code] SHIPPED (commit 508be78f): Stage 2 — unified power-first, first-party-preferred order; CANONICAL_SEED_ORDER demoted to historical fallback.
- [code] SHIPPED (commits ccffd12b/bf8ee7cf): Stage 3 — z.ai/Zhipu first-party provider (enum + resolution + factory + ZhipuProvider, default glm-5.2).
- [code] SHIPPED (commit bc110d84): Stage 4 — single precedence locked with an invariant test.
- [code] SHIPPED (commit 04711efb): Stage 5 — env templates + deferred drift recorded in PROVIDER_ROUTING_ARCHITECTURE.md §7 (AgentConfig.model literal, per-model config literals, providers_extended.py — scoped out, not blockers).

**Non-goals:**

- Do not create a new truth store, registry, or model catalog; converge on model_hierarchy / model_pool / model_defaults / api_keys.
- Do not change the EvidenceReceipt schema or the spine dispatch path (owned by spine-adoption).
- Do not edit agent_runner.py / orchestrator.py routing wiring beyond what is unavoidable; honor context["preferred_provider"] inside provider_policy instead (avoids spine-adoption surface overlap).
- Do not wire Moonshot/DeepSeek/Perplexity first-party in this track (only z.ai/Zhipu).
- Do not commit provider API keys or any credentials.
- Do not remove the learning overlays (affinity/EWMA/reward/canary); unify them under one precedence.

### Orchestration Arena v1 — frozen hermetic fitness + zero-weight orchestrator + DPI

**Track id:** `orchestration-arena-v1-2026-06` · **Status:** ACTIVE · **Owner:** @AmitabhainArunachala
**Serves spine objective:** `substrate-nativeness` · **Verified at:** 2026-06-23 (TTL 21 days)
**Relations:** complements: provider-routing-consolidation-2026-06, loop-closure-2026-06
**Owns surfaces:** dharma_swarm/coordination/**, dharma_swarm/council/**, tests/test_arena_v1.py, tests/test_dpi.py, tests/test_orchestration_genome.py, tests/test_orchestrator_v1.py, tests/test_council_profiles.py, tests/test_coordination_closure_checks.py
**Moves vital signs:** eval_coverage, quality_gates

Governance admission for the Arena/Orchestration substrate that LANDED on
main (PRs #670 and adjacent) but was not yet represented in the active-track
portfolio. The DGM substrate must be governance-visible: the system needs to
know its own fitness function exists, is frozen/hermetic/replayable, and is
not yet making production capability claims.

This is the keystone fitness layer for any future Dharma Forge: a frozen
verifiable taskpack + deterministic scorer + zero-weight heuristic
orchestrator over a MAP-Elites archive + a Decorrelation-Power-Index (DPI)
that gates a decorrelated-correctness bonus on actual correctness, plus a
minimal Council that verifies orchestration traces.

Doctrine that must hold: capability leads, trust multiplies (not the
headline); only CANONICAL_ORIGIN_MAIN facts feed fitness; v1 carries ZERO
trained weights — training is earned only after the arena produces labels.

**Next items:**

- [code] Wire arena scorecard + DPI receipts into a governance-visible report surface (read-only).
- [code] (blocker) Add best-single-model controls + budget-parity proof to every arena run before any capability claim.
- [code] Connect arena winners to a cold-start trace corpus (no training yet; corpus only).

**Non-goals:**

- Do not make production capability claims; arena reports candidate lift only with budget-parity controls and significance gating.
- Do not introduce trained weights / SFT / GRPO in v1; this track is zero-weight by design.
- Do not let dirty/local/candidate state feed arena fitness; only canonical origin/main.
- Do not couple admission to the full world-ingestion (#662) seam.

### Merge Master Mike — D4 persistent always-on merge agent

**Track id:** `merge-master-mike-d4-2026-06` · **Status:** ACTIVE · **Owner:** @AmitabhainArunachala
**Serves spine objective:** `substrate-nativeness` · **Verified at:** 2026-06-24 (TTL 21 days)
**Relations:** complements: runtime-truth-reconciliation-2026-06
**Owns surfaces:** scripts/runtime/pr_merge_control.py, scripts/runtime/merge_master_mike_daemon.py, .github/workflows/automerge.yml, .github/workflows/codex-mention-router.yml, .github/workflows/merge-master-mike-backlog.yml, tests/test_pr_merge_control_github_reviews.py
**Moves vital signs:** quality_gates, tool_coverage

Operator directive 2026-06-24: make Merge Master Mike a D4-level
PERSISTENT, always-on merge agent — up independently of any operator
machine, responsive both reactively (@mention) and proactively (every
PR event), with a reviewer quorum that is satisfiable in the cloud.

Diagnosis (this session): Mike-the-merger is already cloud event-driven
(automerge.yml on pull_request / check_suite / review + an hourly sweep,
and the router on @mention). Mike-the-reviewer-LANE is not: the cloud
router runs packet->gate->merge against an ephemeral RUNNER_TEMP state
dir but NEVER runs the reviewer lanes (run-agent), so the required
claude/copilot receipt FILES are never written in the cloud. Result: bot
PRs flow (the bot-pr label WAIVES receipts) but HUMAN PRs can never
auto-merge in the cloud — the gate always finds the receipts missing. The
only producer today is the Mac daemon's review cycle-mode (which defaults
to dry-run) or a manual `make pr-run-claude`. That machine dependency is
the real clean-merge bottleneck.

The fix is a reviewer-receipt SOURCE that exists in the cloud with no
credential: teach the gate to count the native GitHub reviews it already
receives (the Codex App review = codex; a requested Copilot review =
copilot) as receipts, and demote claude to the deep/backup lane (built
later as a credentialed cloud Action). Then auto-enroll every non-draft
PR so Mike acts proactively, and give Mike a cloud heartbeat so his
living-agent presence is continuous rather than Mac-bound.

Doctrine that MUST hold (the gate's safety floor is never weakened):
  Add receipt SOURCES, never remove gate checks. CI green, no conflict,
  no unresolved blocking threads, and reviewDecision != CHANGES_REQUESTED
  stay hard. Mike never silent-merges, never approves, never pushes
  source, never bypasses governance. A native GitHub review counts as a
  receipt ONLY from a trusted installed reviewer-App login.

**Next items:**

- [code] (blocker) Slice 1 (blocker): bridge native GitHub reviews -> Mike receipts in the pr_merge_control gate (Codex App = codex, Copilot = copilot), trusted-login-gated and ADDITIVE (never removes a check). + tests.
- [code] Slice 2: auto-enroll every non-draft PR into the automerge/Mike evaluate lane (not only bot-pr / automerge-labeled).
- [code] Slice 3 (operator-gated): cloud Claude reviewer GitHub Action that runs run-agent and posts a claude receipt on PR open/sync (needs an ANTHROPIC API credential as a repo secret — decision D4).
- [code] Slice 4: Mike cloud heartbeat (scheduled wake / living-agent receipt) so D4 presence is continuous and machine-independent; keep the Mac daemon as an optional local mirror.
- [governance] (blocker) Operator ratification of decisions D1-D4 before any merge-authority behavior changes.

**Non-goals:**

- Do not weaken or remove any existing gate check (CI green, conflict, unresolved threads, CHANGES_REQUESTED stay hard).
- Do not let Mike silent-merge, approve PRs, push source, or bypass governance.
- Do not commit provider/API credentials; the credentialed Claude reviewer Action is operator-provisioned.
- Do not accept a "review" from an untrusted login as a receipt; only trusted installed reviewer-App logins.
- Do not create a new merge authority or receipt store; extend pr_merge_control and the existing workflows.

### Filesystem-Native Context Substrate — folder-as-contract + portable knowledge graph

**Track id:** `filesystem-native-substrate-2026-06` · **Status:** ACTIVE · **Owner:** @AmitabhainArunachala
**Serves spine objective:** `substrate-nativeness` · **Verified at:** 2026-06-24 (TTL 21 days)
**Relations:** complements: truth-graph-platform-2026-06, runtime-truth-spine-adoption-2026-06
**Owns surfaces:** docs/research/FILESYSTEM_AS_AGENT_SUBSTRATE_RESEARCH.md, docs/research/FILESYSTEM_SUBSTRATE_SLICE_A_SPEC.md, docs/research/palantir-ontology/ONTOLOGY_PROPOSAL_LOG.md, dharma_swarm/fs_substrate/**, tests/test_stage_contracts.py, tests/test_okf_projection.py, tests/test_semantic_fs.py, tests/test_organizer.py, tests/test_fs_substrate_e2e.py
**Moves vital signs:** context_efficiency, tool_coverage, memory_persistence

Operator directive 2026-06-24: consolidate four convergent "filesystem-as-
agent-substrate" sources into one substrate power and wire it into the swarm.
The four: LSFS (arXiv 2410.11843, semantic syscalls over a vector index),
LlamaFS (iyaja/llama-fs, self-organizing propose-then-apply), Van Clief's
ICM/MWP (arXiv 2603.16021, numbered folders as pipeline stages + CONTEXT.md
contracts + token-firewall folders), and Google's OKF v0.1 (2026-06-12,
portable markdown knowledge graph: required `type`, index.md/log.md, links).

This is a Tier-1 substrate/organizer power (NORTH_STAR.md §4), realizing
self-organs the genome already names (THE_ORGANISM.md ③: self-onboarding,
self-ontology-maintenance, self-memory-curation) and grounding the
categorical-systems-theory pillar (genome ①) physically: CONTEXT.md
Inputs/Outputs tables are morphism declarations; OKF `type`+links are
objects+morphisms — compositional interfaces the organism can read and
rewrite without losing coherence.

The track creates NO new truth store and NO authority surface. Every slice
projects from / converges on existing owners: the spine (invoke_agent /
EvidenceReceipt), the orchestrator + TaskBoard DAG, handoff.py, and the
MemoryKernel front door + surface registry.

Doctrine line that must hold (inherited from reconciliation + truth-graph):
  Read models project truth from owners; they do not become authority.

Anti-pattern guard (THE_ORGANISM.md needle): this must not become "a paper
about our own architecture." The outward licence is OKF interchange — making
the swarm's knowledge portable to external humans and agent systems
(NORTH_STAR.md §6 noosphere propagation; §8 trust-gate auditability).

**Next items:**

- [docs] SHIPPED: single-location research dossier consolidating LSFS, LlamaFS, ICM/MWP, OKF with the organism tie (docs/research/FILESYSTEM_AS_AGENT_SUBSTRATE_RESEARCH.md).
- [code] SHIPPED (2026-06-24): Slice A — read-only CONTEXT.md stage-contract reader (dharma_swarm/fs_substrate/{stage_contracts,stage_executor}.py). Numbered stage-folders -> Task.depends_on DAG; each stage dispatched through invoke_agent(); stage output -> handoff -> next stage. Reuses spine/TaskBoard/handoff/skills; no new orchestrator. tests/test_stage_contracts.py: 8 passed, 1 skipped.
- [code] SHIPPED (2026-06-24): Slice B — OKF projector (dharma_swarm/fs_substrate/okf.py). write_bundle/read_bundle (tolerant consumer) + project_semantic_objects() projects docs/ontology/semantic_objects.yaml to a portable OKF bundle (required `type` from each object's kind, index.md/log.md, cross-links). 13 ontology objects round-trip. tests/test_okf_projection.py: 6 passed. The outward/Arjuna licence: the knowledge graph is now portable.
- [code] SHIPPED (2026-06-24): Slice C — LSFS-style semantic-query facade (dharma_swarm/fs_substrate/semantic_fs.py): keywords_retrieve/semantic_retrieve/group_semantic/integrated_retrieve + a parse_query LSFS-Parser analog, all delegating to the MemoryKernel front door (iter_memory_atoms). No new vector DB; lexical proxy with an embedding seam noted. tests/test_semantic_fs.py: 5 passed.
- [code] SHIPPED (2026-06-24): Slice D — propose-then-apply organizer (dharma_swarm/fs_substrate/organizer.py): propose_organization (pure dry-run, by-family classification) + apply_proposal (GATED: refuses without confirm=True; write_ok predicate is the MemoryWritePolicy seam; never overwrites/escapes root). Watch-mode + LLM-summary deferred. tests/test_organizer.py: 5 passed.

**Non-goals:**

- Do not create a new daemon, database, vector store, event log, or truth store.
- Do not mint a second receipt type; project over spine.EvidenceReceipt.
- Do not mutate files without a dry-run proposal + operator approval (Slice D); writes go through MemoryWritePolicy.
- Do not broadly refactor orchestrator.py, agent_runner.py, or swarm.py; plug in at dispatch_next()/TaskBoard, honoring spine-adoption's owned surfaces.
- Do not touch operator_core/** or runtime_state.py.
- Do not duplicate the truth-graph-platform repo_context projection; this owns the portable on-disk interchange format, not the in-repo render.
- Do not commit provider API keys or any credentials.

**Recently closed tracks:**

- `orientation-graph-2026-06` — Orientation Graph — whole-system view served on token one (SHIPPED, closed 2026-06-12)
- `runtime-truth-spine-2026-06` — Runtime Truth Spine — one invariant, one invocation path, one receipt (SHIPPED, closed 2026-06-04)
- `trace-identity-coverage-2026-05` — Trace Identity Coverage — native propagation and soft coverage findings (SUPERSEDED, closed 2026-05-28)

For machine-readable status, see [`reports/governance/active_track_evidence.md`](../../reports/governance/active_track_evidence.md) (generated by `scripts/governance/check_track_status.py`).

<!-- ACTIVE_TRACK:END -->

---

## GLOBAL AXIOMS

These are immutable engineering laws for this repository. Violation = architectural regression.

### A1: NO FLAT-PACKAGE GROWTH
The `dharma_swarm/` package currently has **389 files at its top level (58.7% of 663 total Python modules)** (V). No new .py file may be added to the top level. New modules must go into an appropriate subdirectory. Existing top-level files will be organized over time.

### A2: NO DUPLICATE IMPLEMENTATIONS
Before creating a new file for routing, bridging, adapting, or orchestrating, check if one already exists. The repo currently has **26 bridge files** (V), **3 model_routing copies** (2 are identical, 1 is different) (V), **4 orchestrators** (V), **21 adapter files across 8 locations** (V), and **14 router files** (V). Do not add more without deprecating an existing one.

### A3: NO UNDOCUMENTED SEAMS
If your code creates a new interface between domains (a bridge, adapter, or protocol), you must update `NAVIGATION.md` with its purpose, entry point, and boundary constraints. Undocumented seams become invisible coupling.

### A4: NO VIBE-CODING
If a seam, type, protocol, state contract, or API is missing from your context, **STOP and find the exact file** before proceeding. Do not guess imports. Do not assume module locations. Do not infer API shapes from naming conventions.

### A5: NO GOD OBJECTS
No single file should exceed 3,000 lines. Current violations (V):
- `dgc_cli.py`: 6,979 lines
- `thinkodynamic_director.py`: 5,167 lines
- `telos_substrate.py`: 4,423 lines
- `evolution.py`: 3,227 lines
- `swarm.py`: 3,119 lines
- `agent_runner.py`: 3,023 lines
- `providers.py`: 2,938 lines (approaching limit)

**148 files exceed 500 lines; 39 exceed 1,000; 7 exceed 3,000** (V). These must be decomposed over time, not grown further.

### A6: DOCS DECAY -- CHECK BEFORE CITING
All numerical claims in docs become stale within weeks. Before citing module counts, test counts, or line counts from any doc (including this one), verify against the actual filesystem. See `REPO_GOVERNANCE_AUDIT.md` for the current staleness log. The current DocOps inventory reports **405 Markdown files containing at least one reserved trust-language term** (V). Treat these as authority-scope review candidates, not confirmed repo-wide authority.

### A7: NO CIRCULAR IMPORTS
The repo has **9 verified circular dependency chains** (V). The worst:
1. **6-module evolution cycle** (evolution ↔ landscape ↔ meta_evolution ↔ dse_integration ↔ jikoku_fitness) -- has direct module-level imports
2. **4-module routing cycle** (router_v1 → provider_policy → smart_router → router_v1) -- mitigated by TYPE_CHECKING
3. **api ↔ dharma_swarm bidirectional** -- api imports dharma_swarm at module level; dharma_swarm imports api lazily

All 9 cycles were independently confirmed with exact import lines. Most are mitigated by lazy imports but remain architectural debt. **New code must not create circular imports.**

### A8: FRONTMATTER DISCIPLINE
Do not inject machine-readable YAML frontmatter into governance or architecture docs unless explicitly requested. Current state: **219 of 894 Markdown files start with YAML frontmatter; 15 of 43 docs/architecture Markdown files do so** (V). Long frontmatter remains an authority/noise risk even when the prose is useful.

---

## VERIFIED NUMBERS (2026-06-24 COUNT REFRESH)

These are the ground-truth metrics. All other documents citing different numbers are stale.

| Metric | Value | Verification |
|--------|-------|-------------|
| Total Python modules | **787** | find dharma_swarm -name "*.py" -type f |
| Top-level (flat) modules | **414 (53.1%)** | find dharma_swarm -maxdepth 1 -name "*.py" -type f |
| Total Python LOC | **319,298** | wc -l across dharma_swarm Python modules |
| Test files | **768** | find tests -name "*.py" -type f |
| Test functions | **12,043 `def test_` occurrences under tests/** | rg "def test_" tests |
| Test files | **768** | find tests -name "*.py" -type f |
| Test functions | **12,043 `def test_` occurrences under tests/** | rg "def test_" tests |
| Tests collected (pytest) | **Needs write-permitted refresh** | not run during this DocOps count pass |
| Collection errors | **Historical: 16 on 2026-04-04** | refresh before relying on this count |
| Markdown files | **1162** | find . -name "*.md" -type f |
| Markdown total lines | **258,995** | wc -l across all .md |
| Markdown files | **1162** | find . -name "*.md" -type f |
| Markdown total lines | **258,995** | wc -l across all .md |
| Top-level (flat) modules | **414 (52.7%)** | find dharma_swarm -maxdepth 1 -name "*.py" -type f |
| Total Python LOC | **320,713** | wc -l across dharma_swarm Python modules |
| Test files | **768** | find tests -name "*.py" -type f |
| Test functions | **12,043 `def test_` occurrences under tests/** | rg "def test_" tests |
| Tests collected (pytest) | **Needs write-permitted refresh** | not run during this DocOps count pass |
| Collection errors | **Historical: 16 on 2026-04-04** | refresh before relying on this count |
| Markdown files | **1162** | find . -name "*.md" -type f |
| Markdown total lines | **258,995** | wc -l across all .md |
| Bridge files | **26** | find dharma_swarm -name "*bridge*.py" -type f |
| Adapter files | **25** | find dharma_swarm -type f | rg -i "adapter" |
| Router files | **16** | find dharma_swarm -type f | rg -i "rout" |

## SYSTEM TOPOGRAPHY

### Domain 1: Schema & Configuration

- **Path**: `dharma_swarm/models.py`, `dharma_swarm/config.py`, `dharma_swarm/profiles.py`
- **Global Role**: All shared Pydantic types, enums, and configuration
- **Primary Entry Points**: `models.py` (types), `config.py` (settings), `profiles.py` (agent profiles)
- **State Management**: `config.py` reads env vars -> `DEFAULT_CONFIG` singleton
- **Volatility Level**: LOW
- **Boundary Constraints**:
  - ALLOWED: Everything may import from here
  - FORBIDDEN: These files must NOT import from any other dharma_swarm module
- **Boundary Status**: **PASS** (V) -- no violations found
- **Notes for Agents**: This is the foundation. Changes here ripple everywhere. ProviderType enum has 18 values (not 9 as some docs claim).

### Domain 2: Governance (S5 Identity + S3 Control)

- **Path**: `dharma_swarm/dharma_kernel.py`, `telos_gates.py`, `guardrails.py`, `identity.py`, `policy_compiler.py`, `agent_constitution.py`, `pramana.py`, `samvara.py`, `anekanta_gate.py`, `dogma_gate.py`, `steelman_gate.py`
- **Global Role**: Immutable axioms, safety gates, constitutional constraints, epistemology
- **Primary Entry Points**: `dharma_kernel.py` (axioms), `telos_gates.py` (gate checks)
- **State Management**: `~/.dharma/witness/` (gate check logs, JSONL append-only)
- **Key numbers**: 25 kernel axioms (SHA-256 signed) (V), 11 telos gates (V), 3 tiers (V)
- **Volatility Level**: LOW (kernel is immutable; gates change via proposal protocol only)
- **Boundary Constraints**:
  - ALLOWED: May import from Schema domain
  - FORBIDDEN: Must NOT import from Runtime, Intelligence, or Evolution domains
- **Boundary Status**: **PASS** (V) -- no violations found
- **Notes for Agents**: `dharma_kernel.py` is SHA-256 signed. Do not modify. Gates are added via `GateRegistry.propose()`, not by editing `telos_gates.py` directly. Parent `~/CLAUDE.md` says "10 axioms" -- this is WRONG; actual count is 25.
- **Named operator role (merge authority)**: **Merge Master Mike (MMM)** is the registered conditional-merge coordinator agent for this domain. Charter: [`MMM_CHARTER.md`](MMM_CHARTER.md). Operational manual: [`../ops/PR_REVIEW_CONTROL.md`](../ops/PR_REVIEW_CONTROL.md). Registration: [`../../examples/agents/merge_master_mike.registration.json`](../../examples/agents/merge_master_mike.registration.json).

### Domain 3: Runtime Core (S1 Operations + S2 Coordination)

- **Path**: `dharma_swarm/swarm.py` (3,119 lines), `orchestrator.py` (2,272 lines), `agent_runner.py` (3,023 lines), `providers.py` (2,938 lines), `message_bus.py`, `signal_bus.py`, `task_board.py`, `handoff.py`
- **Global Role**: Agent lifecycle, task routing, LLM provider management, async messaging
- **Primary Entry Points**: `swarm.py` (facade), `orchestrator.py` (task->agent dispatch), `agent_runner.py` (execution + provider routing)
- **State Management**: `~/.dharma/` (SQLite via aiosqlite), in-memory task board
- **Volatility Level**: MEDIUM
- **Boundary Constraints**:
  - ALLOWED: Schema, Governance (for gate checks)
  - FORBIDDEN: Must NOT import from TUI/Terminal domain directly. Use bridges.
- **Boundary Status**: **PASS** (V) -- no violations found
- **The Routing Call Chain** (V):
  ```
  SwarmManager.dispatch_next()
    -> Orchestrator.dispatch() [task->agent assignment]
      -> AgentRunner._invoke_provider()
        -> ModelRouter.complete_for_task() [providers.py:2535]
          -> ProviderPolicyRouter.route() [provider_policy.py]
            -> DecisionRouter.route() [REFLEX/DELIBERATIVE/ESCALATE]
          -> model_hierarchy.py [tier selection]
          -> SmartRouter [cost optimization]
          -> provider.complete() [actual LLM API call]
  ```
- **Notes for Agents**: Orchestrator does task->agent assignment, NOT provider selection. Provider routing happens in AgentRunner via ModelRouter. `orchestrate.py` has orchestration logic; `orchestrate_live.py` runs the 5-loop live system. `ginko_orchestrator.py` is Ginko-specific.

### Domain 4: Intelligence (S4)

- **Path**: `dharma_swarm/thinkodynamic_director.py` (5,167 lines), `telos_substrate.py` (4,423 lines), `context.py` (1,387 lines), `context_compiler.py`, `context_agent.py`, `zeitgeist.py`, `active_inference.py`, `decision_ontology.py`, `decision_router.py`, `intent_router.py`, `routing_memory.py`
- **Global Role**: Task scoring, context injection, routing decisions, environmental scanning
- **Primary Entry Points**: `thinkodynamic_director.py` (brain), `context.py` (orientation)
- **State Management**: `routing_memory.py` persists routing outcomes via EWMA scoring
- **Volatility Level**: HIGH (most active development area)
- **Boundary Constraints**:
  - ALLOWED: Schema, Governance, Runtime Core
  - FORBIDDEN: Must NOT import from TUI/Terminal or Evolution directly
- **Notes for Agents**: `thinkodynamic_director.py` is 5,167 lines -- a god object. Be careful. `telos_substrate.py` (4,423 lines) is imported only by `swarm.py` (lazy) -- possibly a zombie god object. `decision_router.py` is called via ProviderPolicyRouter, not directly. `intent_router.py` is NOT in the main dispatch path -- only used for CLI skill composition.

### Domain 5: Evolution & Learning

- **Path**: `dharma_swarm/evolution.py` (3,227 lines), `cascade.py`, `meta_evolution.py`, `diversity_archive.py`, `selector.py`, `ucb_selector.py`, `smart_seed_selector.py`, `landscape.py`, `jikoku_fitness.py`, `dse_integration.py`
- **Global Role**: DarwinEngine, F(S)=S cascade, meta-evolution, diversity preservation
- **Primary Entry Points**: `evolution.py` (DarwinEngine), `cascade.py` (LoopEngine)
- **State Management**: `~/.dharma/evolution/archive.jsonl`, `~/.dharma/evolution/merkle_log.json`
- **Volatility Level**: MEDIUM
- **Circular Dependency WARNING**: 6-module cycle exists (evolution ↔ landscape ↔ meta_evolution ↔ dse_integration ↔ jikoku_fitness) with direct module-level imports (V)
- **Boundary Constraints**:
  - ALLOWED: Schema, Governance (for gate checks), Runtime Core (for agent dispatch)
  - FORBIDDEN: Must NOT import from TUI/Terminal
- **Notes for Agents**: Evolution is gated by telos gates. `diversity_archive.py` implements MAP-Elites -- do not remove diversity pressure. The 6-module circular dependency is the highest-risk architectural debt in the codebase.

### Domain 6: Bridges (Integration Layer)

**26 bridge files** (V), **11,910 total LOC**:

| Bridge | Lines | Importers | Status |
|--------|-------|-----------|--------|
| terminal_bridge.py | 2,539 | 2 | ALIVE |
| operator_bridge.py | 1,819 | 15 | ALIVE |
| vault_bridge.py | 885 | 2 | ALIVE |
| bridge_registry.py | 842 | 15 | ALIVE (infra) |
| bridge.py | 583 | 78 | ALIVE (core) |
| semantic_memory_bridge.py | 518 | 2 | ALIVE |
| world_radar/go_bridge.py | 457 | 2 | ALIVE |
| bridge_coordinator.py | 450 | 3 | ALIVE (infra) |
| instinct_bridge.py | 377 | 4 | ALIVE |
| fractal/room_bridge.py | 490 | 2 | ALIVE |
| trishula_bridge.py | 347 | 1 | STALE |
| session_event_bridge.py | 311 | 2 | ALIVE |
| a2a/a2a_bridge.py | 310 | 2 | ALIVE |
| review_bridge.py | 224 | 4 | ALIVE |
| roaming_operator_bridge.py | 202 | 3 | ALIVE (boundary violation) |
| skill_bridge.py | 202 | 2 | ALIVE |
| optimizer_bridge.py | 191 | 8 | ALIVE |
| ecosystem_bridge.py | 170 | 3 | ALIVE |
| revenue/telic_bridge.py | 340 | 3 | ALIVE |
| operator_core/go_github_bridge.py | 198 | 1 | ALIVE |
| operator_core/go_evidence_bridge.py | 113 | 1 | ALIVE |
| operator_core/world_radar/receipt_bridge.py | 248 | 2 | INCUBATING |
| ginko_bridge.py | 94 | 1 | ALIVE |

- **Primary Entry Points**: `terminal_bridge.py` (Bun<->Python), `bridge.py` (core abstraction)
- **State Management**: Bridges are stateless translators (mostly)
- **Volatility Level**: HIGH (most duplication risk area)
- **Boundary Constraints**:
  - ALLOWED: May import from any domain they bridge between
  - FORBIDDEN: Bridges must NOT import from other bridges (no bridge chains)
- **Boundary Status**: **FAIL** (V) -- `roaming_operator_bridge.py:14` imports `operator_bridge` directly; `bridge_coordinator.py` imports `bridge_registry` via late imports (6 locations)
- **4 zombie bridges deleted** in PR #95: math_bridges, flywheel_bridge, offline_training_bridge, runtime_bridge

### Domain 7: Terminal / TUI

- **Path**: `dharma_swarm/tui/`, `dharma_swarm/terminal_adapters/`, `dharma_swarm/terminal_routing/`, `dharma_swarm/terminal_engine/`, `dharma_swarm/terminal_commands/`
- **Global Role**: Bun/Ink terminal UI and its Python backend
- **Primary Entry Points**: `terminal_bridge.py` (JSON stdio protocol), `tui/` (Bun app)
- **State Management**: Stateless (session state in terminal, not Python)
- **Volatility Level**: HIGH (recent Bun TUI rewrite)
- **Boundary Constraints**:
  - ALLOWED: Schema, bridges (terminal_bridge.py only)
  - FORBIDDEN: Must NOT import from Runtime Core, Intelligence, or Evolution directly
- **Boundary Status**: **PASS** (V) -- no violations found
- **Adapter duplication**: `terminal_adapters/` and `tui/engine/adapters/` have identical file structure (base.py, claude.py, codex.py, ollama.py, openrouter.py) but **different implementations** (V). All 5 corresponding files differ.
- **Dead routing copies**: `tui/model_routing.py` and `terminal_routing/model_routing.py` are **identical to each other but different from the original** `dharma_swarm/model_routing.py` (V). Neither is imported in the main dispatch path -- both are dead code.

### Domain 8: API / Backend

- **Path**: `api/`
- **Global Role**: FastAPI REST endpoints for dashboard and external access
- **Primary Entry Points**: `api/main.py`
- **State Management**: Delegates to Runtime Core
- **Volatility Level**: LOW
- **Boundary Constraints**:
  - ALLOWED: Schema, Runtime Core (via imports)
  - FORBIDDEN: Must NOT import from TUI/Terminal
- **Circular Dependency WARNING**: api ↔ dharma_swarm bidirectional imports exist (V). `api_key_audit.py` and `provider_smoke.py` import from `api.routers` lazily.
- **Notes for Agents**: The API is a thin layer over the Python core. Don't put business logic here.

### Domain 9: Dashboard / Frontend

- **Path**: `dashboard/`
- **Global Role**: Next.js web dashboard
- **Primary Entry Points**: `dashboard/src/app/page.tsx`
- **State Management**: React state + API calls to backend
- **Volatility Level**: LOW (underactive)
- **Boundary Constraints**:
  - ALLOWED: Communicates with API only (HTTP)
  - FORBIDDEN: No direct Python imports (it's JavaScript/TypeScript)
- **Notes for Agents**: The dashboard exists but is not the primary interface. The Bun TUI is the active frontend.

### Domain 10: Ontology

- **Path**: `dharma_swarm/ontology.py` (1,822 lines), `ontology_runtime.py`, `ontology_hub.py`, `ontology_agents.py`, `ontology_adapters.py`, `ontology_query.py`
- **Global Role**: Palantir-pattern typed object system (ObjectType, OntologyObj, Links, Actions)
- **Primary Entry Points**: `ontology.py` (1,822 lines -- the foundation)
- **State Management**: SQLite-backed (`~/.dharma/ontology.db`, 1.3 MB)
- **Volatility Level**: MEDIUM
- **Boundary Constraints**:
  - ALLOWED: Schema
  - FORBIDDEN: Should not import from Terminal or Evolution
- **Notes for Agents**: The ontology is positioned as "THE foundation" in NAVIGATION.md but its relationship to the simpler Pydantic models in `models.py` is unclear. Two competing type systems coexist.

### Domain 11: State & Memory (NEW -- not in prior manifest)

- **Path**: 11 memory modules (5,848 LOC), 8 context modules (5,828 LOC)
- **Global Role**: Persistent memory, context assembly, state management
- **Key numbers**: 49 modules use SQLite (V), 126 modules write JSONL (V), 113 modules write to filesystem (V)
- **State Directory**: `~/.dharma/` with 74 subdirectories, 10+ SQLite databases (V)
- **Key databases**: memory_plane.db (58 MB), messages.db (3.6 MB), runtime.db (3.1 MB), ontology.db (1.3 MB)
- **Volatility Level**: HIGH
- **Notes for Agents**: This is the highest-entropy zone for state. 126 modules write JSONL and 49 use SQLite with no unified data access layer. State writes are scattered across the codebase.

---

## SHARED INVARIANTS

### State Mutation Discipline
- All persistent state lives in `~/.dharma/` (SQLite, JSONL, JSON)
- No Python module may write to the filesystem outside `~/.dharma/` during runtime
- Gate check results must be witnessed to `~/.dharma/witness/` (append-only)
- Evolution archive is append-only (`~/.dharma/evolution/archive.jsonl`)
- Stigmergy marks are append-only (`~/.dharma/stigmergy/marks.jsonl`)
- **Reality check**: 113 modules write to filesystem, 126 write JSONL (V). Enforcement is cultural, not technical.

### Event / Schema Discipline
- All shared types in `models.py` (Pydantic 2)
- Message bus: `message_bus.py` (async SQLite pub/sub, for agent communication)
- Signal bus: `signal_bus.py` (in-process events, for loop-to-loop signaling)
- These are DIFFERENT systems. Do not confuse them.

### Routing / Model Selection Truth
- **Canonical routing hub**: `ModelRouter.complete_for_task()` in `providers.py:2535` (V)
- **Decision path**: ProviderPolicyRouter -> DecisionRouter (REFLEX/DELIBERATIVE/ESCALATE)
- **Provider hierarchy**: `model_hierarchy.py` (TIER_FREE -> TIER_CHEAP -> TIER_PAID)
- **Cost optimization**: `smart_router.py`
- **Signal generation**: `router_v1.py` (language detection, complexity, tokens) -- ACTIVE, not legacy (V)
- **Learning**: `routing_memory.py` (EWMA scores from ~100 events)
- **Dead copies**: `tui/model_routing.py` and `terminal_routing/model_routing.py` are unused (V)
- **18 provider types** in enum (V), **19 provider classes** including abstract base (V)

### Naming Conventions
- Python: snake_case everywhere, PEP 8
- Files: descriptive, no abbreviations except established ones (dgc, tui, vsm, a2a)
- Tests: `tests/test_<module_name>.py` mirrors `dharma_swarm/<module_name>.py`
- Config: environment variables override defaults in `config.py`
- **Known inconsistency**: "bridge" vs "adapter" vs "connector" all mean "interface between systems". "orchestrator" vs "orchestrate" vs "director" all mean "coordinate work". "routing" vs "router" vs "selector" all mean "choose where to send".

### Legacy Quarantine Rules
- Files in `docs/archive/` are dead. Do not reference them as current.
- `swarmlens_app.py` is the old TUI (zero importers) (V). The current TUI is Bun/Ink in `tui/`.
- `specs/DGC_TERMINAL_ARCHITECTURE.md` (v1.0) is superseded by v1.1.
- `router_v1.py` is **NOT legacy** -- it is actively used in the routing chain for signal generation (V). The manifest previously labeled it "legacy" incorrectly.
- **4 zombie bridges** deleted in PR #95: `math_bridges.py`, `verify/flywheel_bridge.py`, `offline_training_bridge.py`, `runtime_bridge.py`

### Test / Verification Expectations
- `python3 -m pytest tests/ -q` must pass before any commit
- **16 collection errors** are KNOWN (V): 10 missing numpy, 2 missing textual, 1 missing typer, 1 missing pytest_asyncio, 1 missing yaml, 1 missing tui.app module
- Test file naming: `tests/test_<module>.py`
- Async tests use `pytest-asyncio` with `asyncio_mode = "auto"`
- **300-second timeout** per test (conftest.py)

---

## ACTIVE LEDGER

**COMMON OPERATING PICTURE: MULTI-TAB LOCKS**

*Human Orchestrator: Update this list before pasting into a new tab.*

- LOCKED DOMAINS (currently in-flux by other agents): *None*
- AVAILABLE DOMAINS: *All*

*Last updated: 2026-04-04 by fresh filesystem-verified re-audit*

---

## MANDATORY AGENT BOOT SEQUENCE

**PRE-FLIGHT CHECKLIST FOR ALL AGENTS:**

Before you begin your task, you must verify:

1. You have mapped your task to a specific domain in the Topography above.
2. You confirm your domain is NOT in the Active Ledger Locked list.
3. You have read the Boundary Constraints for your domain and will not generate imports or logic that violate them.
4. You will not rely on vibe coding. If a seam, type, protocol, state contract, or API is missing from context, you will STOP and find the exact file before proceeding.
5. You will treat this manifest as repo-wide canon, not model-specific suggestion.
6. You will check `REPO_GOVERNANCE_AUDIT.md` for known contradictions before relying on any doc's numerical claims.
7. You understand that parent `~/CLAUDE.md` has stale numbers (says "10 axioms", "9 providers", "370 modules") -- trust THIS manifest's verified numbers instead.

---

## CORRECTIONS TO PRIOR AUDIT (2026-04-04)

This re-audit found errors in the earlier 5-model audit:

| Error in prior audit | Corrected value |
|---------------------|----------------|
| "codex_overnight.py is 10K lines" | **1,008 lines** (V) |
| "17 bridge files" / "19 bridge files" (self-contradicting) | **26 bridge files** (V) |
| "16 TUI test errors" | **16 total errors: 10 numpy, 2 textual, 1 typer, 1 pytest_asyncio, 1 yaml, 1 tui.app** -- only 3 are TUI-specific (V) |
| "10 pillars" with "PILLAR_04 missing, PILLAR_11 present" | **10 pillar files exist** (PILLAR_01-03, 05-11; PILLAR_04 never created). Sparse numbering, not 11. (V) |
| "router_v1.py is LEGACY" | **router_v1.py is ALIVE** -- actively used by providers.py for signal generation (V) |
| "18 provider classes" (VIVEKA) | **19 classes** (including abstract LLMProvider base); **18 ProviderType enum values** (V) |
| "engine/ is legacy duplicate of tui/engine/" | **Both are ALIVE** -- engine/ has 41 importers, tui/engine/ has 31 importers. Different purposes. (V) |
| Bridge count of "30" (Phase 3A) | **26 actual bridge files** -- the "30" counted test files and non-bridge files with "bridge" in name (V) |

---

## GOVERNANCE FILE RELATIONSHIPS

```
SOVEREIGN_MANIFEST.md (this file)
    |- Defines: axioms, domains, invariants, boot sequence, verified numbers
    |- Enforced by: CLAUDE.md (behavioral rules)
    |- Audited by: REPO_GOVERNANCE_AUDIT.md (contradiction log)
    |- Organized by: CANONICAL_DOC_STACK.md (doc hierarchy)
    |- Detailed by: docs/architecture/NAVIGATION.md (module-level map)
```

---

## WHAT SHOULD HAPPEN TO CLAUDE.md?

**Recommendation: RETAIN and SHARPEN.**

`CLAUDE.md` is the most effective governance surface in the repo:
- Actually read by agents (loaded automatically by Claude Code)
- Actively maintained (last updated 2026-04-04)
- Contains real architectural truth (5-layer model, key abstractions, build commands)

**Stale numbers to fix**:
- "~1,700 lines" for swarm.py -> **3,119** (V)
- References NAVIGATION.md which claims "500 modules" -> current filesystem count **532 dharma_swarm Python modules** (V)
- No mention of the 17 bridges, 13 routers, 16 adapters, or their hierarchy
- Provider list says 9 -> should acknowledge **18 types** (V)

**Do NOT**:
- Rename to AGENTS.md (CLAUDE.md is the Claude Code standard)
- Split it (it's already the right size at 148 lines)
- Mirror it (one source of truth per topic)
- Add the full domain topography (that belongs here in the manifest)

**DO**:
- Add a pointer to this SOVEREIGN_MANIFEST.md for architectural truth
- Fix stale numbers
- Add a note that parent `~/CLAUDE.md` has different (stale) numbers
