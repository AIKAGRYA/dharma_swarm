# BUILD SESSION ENTRYPOINT

**Status:** depth doc — read after running the onboarding command.
**Owner of:** the longer-form pre-flight narrative for a build session.
**Subordinate to:** [`CLAUDE.md`](../../CLAUDE.md) (behavior), [`SOVEREIGN_MANIFEST.md`](SOVEREIGN_MANIFEST.md) (architectural truth), and [`ACTIVE_TRACK.yaml`](ACTIVE_TRACK.yaml) (current build track). When this file disagrees with any of them, they win.

## Run this first

```bash
make onboard
```

That command renders the current operating reality (active track, live ops, broken register, axioms, depth pointers) in one screen. It replaces the old hand-maintained "read order". This file is the depth narrative you read **after** the onboarding command, when you need more context than one screen.

---

## 0. What this repo is, in one paragraph

dharma_swarm is a Python multi-agent orchestration runtime with a typed ontology, an immutable kernel, gated proposal flow, an append-only witness log, and an artifact/value loop. The substrates exist. The current failure mode is that most runtime work bypasses them. Each active build track makes one seam ontology-native end-to-end; the active build portfolio (1–N co-equal, surface-disjoint tracks) is declared in [`ACTIVE_TRACK.yaml`](ACTIVE_TRACK.yaml) and surfaced by `make onboard`. Do not introduce new substrates. Wire existing ones.

Substrate-nativeness is a **measured number, not a prose constant** — different measures give different answers (dispatch-site adoption vs. spine-internal coverage), so do not cite a frozen percentage from any doc, including this one. Get the current dispatch-site measure live: `python3 scripts/governance/spine_bypass_report.py` (as of 2026-06-11: 1/7 `.submit()` sites spine-adopted, 5 on the intentional-bypass migration allowlist). Each track's goal: bring its seam to 100% native and prove it with tests, surface-disjoint from sibling tracks.

---

## 1. Depth pointers (read on demand, not in order)

The onboarding command (`make onboard`) lists the depth pointers inline. The same list, for offline reference:

- [`CLAUDE.md`](../../CLAUDE.md) — behavioural rules, key abstractions, build/test commands. *What rules govern any change I make?*
- [`docs/governance/SOVEREIGN_MANIFEST.md`](SOVEREIGN_MANIFEST.md) — domain map, axioms, verified numbers, boundary constraints. *Which domain is my change in? Which boundaries must I not cross?*
- [`reports/audit/end_to_end/000_MASTER_COHERENCE_SYNTHESIS.md`](../../reports/audit/end_to_end/000_MASTER_COHERENCE_SYNTHESIS.md) — settled truths, unresolved gaps, "do not build new, wire existing" list. *Does what I'm about to do duplicate something that already exists?*
- [`docs/governance/CANONICAL_DOC_STACK.md`](CANONICAL_DOC_STACK.md) — doc hierarchy, ownership table, anti-doc-maze rules. *Which file owns the truth I'm about to write down?*
- [`docs/governance/ANTI_SLOP_RULES.md`](ANTI_SLOP_RULES.md) — explicit do-nots backed by Semgrep rules.

If any of these contradict each other on numbers, trust SOVEREIGN_MANIFEST first, then CLAUDE.md, then the audit, then CANONICAL_DOC_STACK. Each is authoritative for the topic CANONICAL_DOC_STACK assigns it.

---

## 2. Current build track

The current build track is declared in [`ACTIVE_TRACK.yaml`](ACTIVE_TRACK.yaml) and surfaced by `make onboard`. **Do not duplicate the track name in prose here** — the YAML is the single source of intent, and any prose copy here will go stale.

The governing principle: each track ships **one seam, end-to-end, with gates and witness load-bearing**. Multiple co-equal tracks may run concurrently (up to `track_policy.max_active`) as long as they have **non-overlapping `owned_surfaces`** — that surface-disjointness, not a single-track mutex, is what keeps the substrate-nativeness measurement clean. When the operator proposes a new project, **declare a new track** under `active_tracks:` in `ACTIVE_TRACK.yaml` (with `serves:`, `owned_surfaces:`, acceptance criteria) — a new project is a new track, not a violation. The failure mode the audit flagged is *undeclared, surface-overlapping* cross-track work, which CI now flags as a conflict — not concurrency itself.

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

### ForgeRSILab SWE Benchmark Spine — fresh PR-suite taskbed and grade-only proof

**Track id:** `forge-rsi-lab-swebench-2026-07` · **Status:** ACTIVE · **Owner:** @AmitabhainArunachala
**Serves spine objective:** `substrate-nativeness` · **Verified at:** 2026-07-04 (TTL 7 days)
**Relations:** complements: provider-routing-consolidation-2026-06, loop-closure-2026-06
**Owns surfaces:** dharma_swarm/forge_v1/**, scripts/runtime/forge_*.py, tests/test_forge_*.py, docs/ops/DHARMA_FORGE_*.md, reports/forge_rsi_lab/**, reports/governance/rsi_lab_*.md
**Moves vital signs:** eval_coverage, quality_gates

Current Dharma Forge line for real SWE-style benchmark preparation. This
track metabolizes the older ForgeRealityArena / Orchestration Arena naming
into the active ForgeRSILab v2.2 spine: repo-native PR-suite harvesting,
fail-to-pass validation, taskbed import, exact-ID grade-only execution, and
evidence receipts.

Current canonical lane:
  worktree: /Users/dhyana/ds_forge_spine_v0
  branch: feat/rsi-lab
  head: 569187fac07aa9d4bbc9ea670cc4d126a249ca44
  remote conductor used for latest pass: meghadharma

The 2026-07-04 Meghadharma pass was deterministic harness work, not an LLM
solve. It harvested post-cutoff PRs, deduped candidates, ran fail-to-pass
validation, imported three strict valid pytest tasks, and refused live
apply/source mutation/archive fitness mutation/official score claims.

Historical names remain valid as lineage only:
  ForgeRealityArena = older arena/Hydra measurement line.
  Orchestration Arena v1 = earlier frozen hermetic fitness/DPI substrate.
  ForgeRSILab = current v2.2 SWE benchmark and RSI lab line.

Doctrine that must hold: task generation and grading may produce benchmark
evidence; only a controlled solver run with budget-matched controls can
support an evolution or capability-lift claim.

**Next items:**

- [evidence] Closeout ingested: Meghadharma 2026-07-04 PR-suite pass produced 32 cycles, 2230 raw candidate observations, 50 validated candidates, and 3 strict imported pytest tasks.
- [runtime] (blocker) Run exact-ID grade-only native packets for the 3 imported pytest tasks and sync receipts into reports/forge_rsi_lab/.
- [runtime] (blocker) Launch the model-powered solver/evolution phase only after grade-only task packets are sealed; record model/provider chain separately from deterministic harness evidence.
- [governance] Retire or relabel old local Forge/Arena worktrees as historical references; keep /Users/dhyana/ds_forge_spine_v0 on feat/rsi-lab as the canonical active worktree.

**Non-goals:**

- Do not claim solver capability lift from a harvest/validation run.
- Do not claim autonomous self-evolution until budget-matched solver controls and E4 significance gates pass.
- Do not mutate source code, live apply, archive fitness, or official benchmark state from harvest loops.
- Do not let Fugu/provider semantic-responder failures overwrite Forge benchmark evidence.
- Do not merge historical ForgeRealityArena/Hydra runtime logs into source canon; summarize them through receipts.
- Do not commit provider API keys, GitHub tokens, tmux logs with secrets, or local runtime databases.

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

## 3. What "ontology-native" means for this repo

A flow is ontology-native when **every** statement below is true:

1. The flow's outputs are typed `OntologyObj` instances persisted via `OntologyRegistry`, not loose dicts or JSON files written to arbitrary paths.
2. Side effects that change shared state go through `ActionDef` executions recorded in `ActionExec`, not raw function calls.
3. Every gateable step writes a `GateDecisionRecord` linked to a `WitnessLog` entry. ALLOW, BLOCK, and REVIEW outcomes are all witnessed.
4. Generated artifacts are linked from `KnowledgeArtifact` to their producing `Experiment`, `ResearchThread`, or `ActionProposal`, and to the `WitnessLog` entries that gated their creation.
5. Value-bearing outcomes emit a `ValueEvent`; agent-attributable contributions emit a `Contribution` linked to the producing `AgentIdentity`.
6. The flow's failure modes (gate block, missing input, schema violation) are visible in artifacts and witness, not silent.
7. The flow has a test that fails if any of points 1–6 regress. "Best effort, never blocks" is not acceptable for a track-1 seam.

If your change satisfies fewer than all seven for the seam it touches, it is not ontology-native yet. Do not claim otherwise in the PR description.

---

## 4. What you must not do

These are direct from `SOVEREIGN_MANIFEST.md` axioms and the audit's "do not build new" list. Reread them at the source if you need detail:

- Do not add files to the top level of `dharma_swarm/` (axiom A1).
- Do not create a duplicate bridge, router, adapter, or orchestrator (axiom A2).
- Do not introduce a new event ledger, work ledger, artifact registry, fact memory store, context bundle table, provider hierarchy, routing memory, Shakti queue, or telemetry read model. Use the canonical substrates listed in audit §6.
- Do not create new top-level markdown files. New docs go under `docs/plans/`, `docs/governance/`, `docs/architecture/`, or `reports/`. The canonical doc stack already says "max 5 governance docs"; this file is justified as a pointer layer and identifies the four it points to. Do not add a sixth governance doc casually.
- Do not promote a new identity schema by docs alone (audit §5 finding 10).
- Do not write to the filesystem outside `~/.dharma/` at runtime.

---

## 5. What "done" looks like for a seam track (template)

Each track defines its own acceptance criteria in `ACTIVE_TRACK.yaml` (`completion_criteria:`), enforced by `scripts/governance/check_track_status.py`. The pattern below — taken from the historical operator-brief seam as a worked **example**, not the current track — is the shape a substrate-native seam track should aim for; adapt it per track:

1. The seam's artifact is created on the canonical path (e.g. a `KnowledgeArtifact` row on each scheduler tick), never by a side path.
2. That artifact links to its witness/proposal/gate-decision/outcome/value rows (e.g. `WitnessLog`, `ActionProposal`, one `GateDecisionRecord` per applied gate, `Outcome`, `ValueEvent`).
3. The applied gates are evaluated, and a BLOCK on any one prevents materialisation. The block is itself witnessed.
4. No code path produces the artifact by writing JSON to disk without going through the ontology and gates.
5. A failing gate or missing input produces a visible error artifact, not silent success.
6. The seam runs from a single scheduler entry and a single new module under `dharma_swarm/` (in an existing subdirectory, not the flat top level).
7. The seam adds zero new bridges, routers, adapters, ledgers, or memory stores.

When a track's `completion_criteria` all pass, the substrate-nativeness estimate moves measurably; that track flips SHIPPABLE and can close while sibling tracks keep running.

---

## 6. Where to record what you find

- New architectural truth → `SOVEREIGN_MANIFEST.md` (edit, don't fork).
- New behavioral rule → `CLAUDE.md` (edit, don't fork).
- New plan → `docs/plans/<date>-<slug>.md` (the existing convention).
- Drift you discover in old docs → log it in `docs/governance/REPO_GOVERNANCE_AUDIT.md`. Do not silently fix without logging.
- Build-session pointers → this file. Keep it short. If it grows past one screen of read-order plus current track, split the bloat back into the canonical docs it should live in.
