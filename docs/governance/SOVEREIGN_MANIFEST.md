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

**Active portfolio:** 7 co-equal track(s) (WIP warn 7, max 10). A new project is a new track here, not a violation — model: 1..N co-equal active tracks; typed graph; WIP-limited; surface-owned.

**Spine objectives (each track serves one):**

- `substrate-nativeness` — Substrate nativeness — runtime flows through the ontology/spine, not around it (covered)
- `revenue-external-humans-served` — Revenue & external humans served — value leaves the house and someone acts on it (**no active track**)
- `research-depth` — Research depth — the contemplative-mechanistic bridge (R_V, geometric lens) deepens (**no active track**)

### Cybernetic Loop Closure — wire all 13 loops with receipted closure checks

**Track id:** `loop-closure-2026-06` · **Status:** ACTIVE · **Owner:** @AmitabhainArunachala
**Serves spine objective:** `substrate-nativeness` · **Verified at:** 2026-07-01 (TTL 21 days)
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

Claim boundary:
  HARNESS_PROVEN means a bounded replay/regression harness passed. It is
  not production-live closure. CLOSED_LIVE requires one live owner-surface
  criterion per loop; those criteria intentionally remain open until the
  daemon branch that actually runs proves them.

**Next items:**

- [code] (blocker) TOOL SHIPPED 2026-07-03 (execution on daemon host remains operator): scripts/runtime/dispatch_dropoff_quarantine.py — dry-run default, REQUIRED --before cutoff, --execute stamps quarantined_at/quarantine_reason on existing delegation_runs rows (idempotent ALTER, no new store, rows stay auditable) and writes a JSON receipt (counts + rowid-list sha256) under ~/.dharma/loop_closure/. Audit now reports dropoff_live=N / dropoff_quarantined_historical=M separately (cybernetics_codex excludes only explicitly-stamped rows and always reports the quarantined tally — never hides it). 7 fixture-DB tests green. REMAINING: operator runs it on the daemon host against the real runtime.db (~2191 historical rows), cutoff at/before the spine-dispatch fix timestamp.
- [governance] Future boundary: keep Loops 12/13 blocked until One Wire has N>=5, M>=3, and explicit archive-fitness authority.
- [governance] (blocker) Promote each HARNESS_PROVEN loop only after its declared live owner-surface criterion passes on the daemon branch that actually runs.

**Non-goals:**

- Do not weaken, bypass, or hard-code any telos gate to close a loop.
- Do not let internal artifacts touch archive fitness (One Wire quorum stands).
- Do not touch the operator_core read-model surfaces owned by the reconciliation lane.
- Do not commit provider API keys or any credentials.
- Do not create a new truth store, receipt system, or state owner; extend loop_supervisor and existing owners.

### Orchestration Arena v1 — frozen hermetic fitness + zero-weight orchestrator + DPI

**Track id:** `orchestration-arena-v1-2026-06` · **Status:** ACTIVE · **Owner:** @AmitabhainArunachala
**Serves spine objective:** `substrate-nativeness` · **Verified at:** 2026-06-23 (TTL 21 days)
**Relations:** complements: provider-routing-consolidation-2026-06, loop-closure-2026-06
**Owns surfaces:** dharma_swarm/coordination/**, dharma_swarm/council/**, scripts/governance/arena_truth_report.py, reports/governance/arena/**, tests/test_arena_v1.py, tests/test_dpi.py, tests/test_orchestration_genome.py, tests/test_orchestrator_v1.py, tests/test_council_profiles.py, tests/test_coordination_closure_checks.py, tests/test_arena_truth_report.py
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

- [code] DONE 2026-07-03: arena scorecard + DPI receipts wired into a read-only governance surface — scripts/governance/arena_truth_report.py renders reports/governance/arena/ (digest-stamped receipt + ARENA_TRUTH.md + corpus), seeded/deterministic; --check fails if the committed surface does not replay byte-for-byte. Criterion arena_truth_receipt_valid verifies it.
- [code] (blocker) HERMETIC CONTROLS SHIPPED (runner.run always executes best_single_full_budget gate + budget-parity ledger for every arm + seeded bootstrap significance; proven by arena_v1_controls_tests_pass). REMAINING (the blocker's live edge): any future live-lane arena run (DHARMA_ARENA_LIVE seam in fixtures.py) must inherit the SAME control arms before any capability claim — the hermetic lift on the fixture taskpack is a control-machinery existence proof, never a capability claim (non-goal 1). C2 stays owned by real benchmark evidence.
- [code] DONE 2026-07-03: arena winners connected to the cold-start trace corpus — coordination/arena/corpus.py emits labeled winner traces (positive_lift_candidate only, scorer-labeled, deterministic) to reports/governance/arena/cold_start_corpus.jsonl, sha256-pinned in the report receipt. Labels only; zero training (v1 doctrine).

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

### Organism Rewire — dormant organs to production, spine standing-on, external gradients

**Track id:** `organism-rewire-2026-07` · **Status:** ACTIVE · **Owner:** @AmitabhainArunachala
**Serves spine objective:** `substrate-nativeness` · **Verified at:** 2026-07-02 (TTL 21 days)
**Relations:** complements: runtime-truth-spine-adoption-2026-06, loop-closure-2026-06, orchestration-arena-v1-2026-06
**Owns surfaces:** tools/world_scout_go/**, tools/world_signal_ingestor_go/**, tools/github_ingestor_go/**, tools/evidence_ingestor_go/**, dharma_swarm/world_radar/**, dharma_swarm/organism.py, dharma_swarm/strange_loop.py, dharma_swarm/diversity_archive.py, dharma_swarm/archive.py, docker-compose.yml, Dockerfile.swarm
**Moves vital signs:** quality_gates, eval_coverage

Operator-ratified 2026-07-02 from the verified full-organism sweep
(29 agents: 9 scanners, 16 adversarial verifiers, 3 judges; dossier in
the sweep session). Converts the sweep's confirmed findings into wiring:
the truth spine becomes standing-on (invariant provenance, not policy),
the Go sense organs become known-working and closure-checked, the
dormant organs (Organism/StrangeLoop via composition root, MAP-Elites
consolidation, living-agent kernel earn-in) reach production, and the
operator gains a felt, live view of the spine (receipt tail + cockpit
pulse). Fitness doctrine ratified alongside: a PORTFOLIO of external
gradients (verified benchmarks for high-iteration autoresearch loops,
market P&L as funding + slow-horizon term only, paid human work as the
C3 leg) — diversity of objective functions on the same math as
diversity of agents.

**Next items:**

- [code] (blocker) D1 (blocker): CODE+DOCS DONE (docker-compose.yml swarm service carries DHARMA_SPINE_DISPATCH=1 standing; Mac plist env path documented in docs/ops/RUNBOOK.md §3d). REMAINING: operator observation that Loop-1 closure reads LIVE persistently on the daemon host (make orient on the host that actually runs; blocked on daemon host / VPS item 4).
- [code] DONE 2026-07-03: `dgc spine tail` (operator_core/spine_tail.py, landed earlier) + read-only cockpit pulse panel now RENDERED in Cockpit V2 (dashboard SpinePulsePanel.tsx: receipts/hour, last-receipt age with LIVE/QUIET chip, dropoff count; reads /api/control-surface/rows/spine.pulse, refreshes 15s, graceful not-live-on-this-host state).
- [code] DONE 2026-07-03: Go sense-organ hardening + Loop 5b complete. Most had landed via #755 (per-source errors → go.world_radar_health cockpit row; github_ingestor live trigger go-g04 via cron_jobs.json:github_ingestor_inbox; host-aware loop5b_world_radar_closure_run with NEEDS_HOST). This session closed the last gap: toolchain-checked invocation in world_radar/go_invoke.py (no binary AND no `go` on PATH → structured needs_host per-source error naming `make go-build`, never an exception into the caller loop; cockpit gap code go_world_radar_needs_host). Verified live: loop5b closure run → LOOP5B_CLOSED=yes; 126 tests green.
- [ops] VPS shift: daemon (compose swarm service + NATS + litestream state replication) onto an always-on VPS; Mac demotes to dev seat/mirror. Operator provisions host + secrets.
- [docs] D2 spec-first: memory position earned by evidence class (receipt-backed+TTL facts may go first-token), routing-time memory (kernel informs seat selection), diversity-preserving kernel sampling for worker seats. Spec then canary before flipping C5.
- [code] D6a: consolidate MAP-Elites on archive.MAPElitesGrid; retire/absorb diversity_archive.py; arena keeps its genome-descriptor variant only if descriptors are shared.
- [code] D5: Organism as composition root over SwarmManager (review + harden to EARN god-module status); StrangeLoop gains a production entry point.
- [docs] External-gradient portfolio spec (dedicated session): >=6 autoresearch nodes (arena/genome, router policy, prompt/policy evolution, memory promotion policy, gate calibration, AND the R_V/self-reference-attractor research lane — NORTH_STAR §2's measurable-awareness claim gets an owned, receipted eval loop again after the COLM calendar death) each with frozen eval + mutation operator + diversity-preserving selection + receipts; benchmark loops iterate at volume, market P&L funds but never selects per-iteration. Next track after this one lands MUST serve revenue-external-humans-served (NORTH_STAR §11 90-day: 'funds itself totally').
- [code] (blocker) D4 (sequenced LAST): BR-003 mechanism test (one canonical run, DHARMA_EVOLUTION_SHADOW=0, rollback receipt), standing unlock only after items 1+8 provide ungameable selection signal.
- [code] D6b: living_agent_kernel earn-in — activate 2-3 kernels post-D1 (receipted wakes visible in presence), monitor, individually graduate to always-on.

**Non-goals:**

- Do not weaken, remove, or bypass any telos gate or ratchet to wire an organ (gates are hardest exactly when revenue/deadline pressure arrives).
- Do not let market P&L act as per-iteration selection signal; funding + slow-horizon term only.
- Do not unlock DarwinEngine standing apply before the external-gradient signal exists (item 9 sequencing is doctrine).
- Do not broadcast identical first-token memory to worker seats; decorrelation of priors is preserved by design.
- Do not touch surfaces owned by the four sibling tracks except through their own next-items.

### DharmaGraph — sovereign durable graph runtime consolidation

**Track id:** `dharmagraph-engine-2026-07` · **Status:** ACTIVE · **Owner:** @AmitabhainArunachala
**Serves spine objective:** `substrate-nativeness` · **Verified at:** 2026-07-05 (TTL 21 days)
**Relations:** complements: loop-closure-2026-06, orchestration-arena-v1-2026-06, organism-rewire-2026-07
**Owns surfaces:** dharma_swarm/graph/**, dharma_swarm/workflow.py, dharma_swarm/topology_genome.py, dharma_swarm/checkpoint.py, dharma_swarm/swarm.py, dharma_swarm/orchestrator.py, pyproject.toml, .github/workflows/langgraph-oracle.yml, tests/test_workflow.py, tests/test_topology_execution.py, tests/test_checkpoint.py, tests/test_graph_checkpoint.py, tests/test_graph_reconciler.py, tests/test_graph_durable_invoker.py, tests/test_langgraph_differential_oracle.py, docs/plans/DHARMAGRAPH_PHASED_SPEC_2026-07-05.md, docs/plans/handoffs/DHARMAGRAPH_HANDOFF_DEVIN.md, docs/plans/handoffs/DHARMAGRAPH_HANDOFF_CLAUDE.md
**Moves vital signs:** quality_gates, eval_coverage

Operator-ratified 2026-07-05 from the engine audit + four-lane research
convoy (spec: docs/plans/DHARMAGRAPH_PHASED_SPEC_2026-07-05.md). The
sovereign LangGraph-class campaign: consolidate 5+ executors, 3
checkpoint mechanisms, and 3 workflow compilers onto ONE crash-resumable
graph engine in dharma_swarm/graph/, built on snapshot-per-superstep
durability over the existing runtime.db tables (zero new truth stores),
with the spine receipt log as the side-effect journal.

Phase order is doctrine: 0a dead-engine deletion; 0b run-level
crash-resume + exactly-once dispatch (chaos receipt is the gate for
everything downstream); 1 differential oracle vs real langgraph 1.2.4 +
DST harness BEFORE migration; 2 crown CompiledWorkflow / strangle the
god-classes; 3 channels+cycles+Send+fork; 4 receipt unification and
in-toto/Merkle/witness rungs (EU AI Act Art. 12 applicable 2026-08-02);
5 honest ratchet re-baseline; 6 evolution hook behind the zero-weight
wall.

Two agents run simultaneously on disjoint file lanes (Devin: 0a + 0b
reconciler; Claude instance: 0b durable_invoker + 1 oracle). Briefs in
docs/plans/handoffs/. Daemon host decision: ONE VPS for now (the
existing DigitalOcean droplet per RUNBOOK section 3e); a second host is
not justified until the daemon + oracle CI both run green on the first.

**Next items:**

- [code] Phase 0a (Devin lane): delete workflow_graph.py + test; absorb durable_execution.py atomic checkpoint/restore + _record_runtime_receipt hook into dharma_swarm/graph/checkpoint.py, then delete. Brief: docs/plans/handoffs/DHARMAGRAPH_HANDOFF_DEVIN.md
- [code] (blocker) Phase 0b reconciler (Devin lane): generalize operator_bridge.recover_stale_tasks pattern to delegation_runs; boot scan owned by SwarmManager.init + tick beside reap_orphaned_tasks; write recovered_at; heartbeat cadence; quarantine per loop_closure_quarantine convention. Chaos receipt (kill -9 -> reconcile -> zero double-execution) is the phase gate.
- [code] DONE 2026-07-05 (56743da, PR #799): Phase 0b durable_invoker (Claude lane) — dharma_swarm/graph/durable_invoker.py wraps _orch_invoker with memo-check + begin/complete idempotency on the existing runtime_state machinery. Review-hardened: deterministic claim key (all identities race on ONE PK row), CAS re-claim for stale/failed/declined takeover (runtime_state.try_reclaim_idempotent_side_effect, exactly one of N concurrent claimants executes), type-exact JSON result memo (unmemoizable results decline replay and re-execute — never truncated/null). orchestrator.py seam SHRANK the file 3220 -> 3210. Joint chaos receipt with the #798 reconciler landed as tests/test_graph_chaos_receipt.py (criterion phase0b_chaos_receipt): kill -9 sim -> boot reconcile -> requeue/quarantine per failure_code vocabulary -> retry executes exactly once -> replay memoizes across re-minted identity -> receipts intact; seeded-deterministic via graph/effects.
- [code] DONE 2026-07-05 (b58cd31, PR #800): Phase 1 (Claude lane) — differential oracle: [test-oracle] extra pins langgraph==1.2.4 (oracle only, never core dep), 13 scenarios dual-run through the dharma clone AND real langgraph with semantic diff + JSON report artifact; 1 real divergence found and adjudicated (DEV-1 receipts-first deviation, LANGGRAPH_PARITY_CONTRACT.md; a test fails if it goes stale). CI job langgraph-oracle.yml ADVISORY (flips to blocking after a green week — that flip + operator go gate Phase 2). DST seed: graph/effects.py injectable clock/rng/dispatch-order, wired into durable_invoker staleness; seeded fault replays are trace-exact.
- [ops] Operator: provision the ONE daemon VPS (existing droplet, RUNBOOK section 3e) so the Phase 0b reconciler runs against a live daemon; second VPS deferred until daemon + oracle CI green.

**Non-goals:**

- Do not adopt langgraph as the runtime engine; it is reference semantics and a differential-test oracle only.
- Do not create any new truth store; durability lives on existing runtime.db tables + the CheckpointStore atomic-write pattern.
- Do not weaken any gate, ratchet, or the spine-ownership guard; new sqlite-touching modules carry spine headers where required.
- Do not wire arena elites into production routing (zero-weight doctrine; Phase 6 wall is an operator capability decision, sequenced per organism-rewire D4).
- Do not edit orchestrator.py beyond the minimal seam call (module-budget ceiling); new logic goes in dharma_swarm/graph/.
- Do not touch surfaces owned by sibling tracks except through their own next-items.

### Helm — world-class operator terminal (Bun+Ink TUI)

**Track id:** `helm-worldclass-terminal-2026-06` · **Status:** ACTIVE · **Owner:** @AmitabhainArunachala
**Serves spine objective:** `substrate-nativeness` · **Verified at:** 2026-07-07 (TTL 21 days)
**Relations:** complements: merge-master-mike-d4-2026-06
**Owns surfaces:** terminal/**
**Moves vital signs:** tool_coverage, context_efficiency

Stranded-track admission (2026-07-07 reconcile). The operator TUI
(terminal/, a Bun+Ink TypeScript project) shipped a real behavioral suite
on origin/main but owned no active track; its prior gate on
agent/magpie-seed was 7x file_exists (rubber-stamp) and 6 of those 7 files
exist ONLY on magpie-seed (a false positive on main). This admits the
LANDED core with an honest, re-runnable behavioral gate.

Claim boundary: the command_passes gate proves the operator TUI's GENERAL
shipped behavior (527 green), NOT the golden-frame / compact-viewport /
tmux-receipt verification LANE — that lane is genuinely unmerged
(branch-only) and remains open work below; it must NOT be gated by
file_exists.

**Next items:**

- [code] (blocker) (blocker) Golden-frame verification lane (golden_capture.sh / ratchet.sh / 120x40 golden / compactShell.test.tsx + closeout+tmux receipts) is unmerged — lives only on agent/magpie-seed. This is the track's world-class differentiator and keeps it ACTIVE (not shippable). Split that branch into reviewable PRs; do NOT gate it by file_exists.

**Non-goals:**

- Do not gate this track on the golden-frame/tmux-receipt file_exists criteria that live only on agent/magpie-seed.
- Do not touch surfaces owned by sibling tracks except through their own next-items.

### Sovereign Safety TCB — fail-closed evolution, graded anti-slop, verified kernel, self-gating portfolio

**Track id:** `sovereign-safety-tcb-2026-07` · **Status:** ACTIVE · **Owner:** @AmitabhainArunachala
**Serves spine objective:** `substrate-nativeness` · **Verified at:** 2026-07-07 (TTL 21 days)
**Relations:** complements: loop-closure-2026-06, merge-master-mike-d4-2026-06, organism-rewire-2026-07
**Owns surfaces:** dharma_swarm/evolution_safety.py, scripts/governance/check_claim_evidence_binding.py, scripts/governance/pramana_probe.py, scripts/governance/branch_janitor.py, scripts/governance/verify_corral_findings.py, scripts/governance/hygiene/**, docs/governance/hygiene/patterns/AI-M1.yaml, packages/telos-kernel/**, packages/titanium-verify/**, .github/workflows/pudgala-rigor.yml, .github/workflows/pramana-probe.yml, .github/workflows/kernel-titanium-verify.yml, .github/workflows/kernel-tests.yml, .github/workflows/branch-janitor.yml, tests/test_evolution_safety.py, tests/test_claim_evidence_binding.py, tests/test_pramana_probe.py, tests/test_pramana.py, tests/test_branch_janitor.py, tests/test_verify_corral_findings.py
**Moves vital signs:** quality_gates, security_guardrails

Governance admission for the SAFETY / GOVERNANCE substrate that LANDED
on main this week (2026-07-04..07) but owned no active-track. This is
the Trusted Computing Base for the whole organism's self-modification
and claim-shipping surface, made governance-visible so the system knows
its own safety floor exists, is enforced, and is not a forgeable local
receipt.

Shipped work this track owns:
  - Pudgala anti-slop + AI-M1 graded claim/evidence binding (PR #781):
    a claim ships only when its strongest passing evidence meets the
    required grade; a self-owned green test is downgraded (not
    independent). Stage-driven ratchet flips advisory->enforced via
    scripts/governance/hygiene/promote.py with NO code change.
  - Pramana probe phantom-gate fix (PR #779): the tiered verification
    conductor refuses to run a registry with phantom targets and exits
    3 (config error, no verdict) rather than emitting a false verdict.
  - PR-001 fail-closed evolution safety (PR #803): polarity inversion —
    live mutation of the running organism is impossible by default;
    verify_promotion is the one-door sole live-apply arbiter; a missing
    OR writable evaluator yields NO promotion grade; blocked mutations
    write receipts (dharma_swarm/evolution_safety.py).
  - titanium-verify blocking TCB gate (PRs #767/#768) over the
    telos-kernel (PR #763): every public function in
    packages/telos-kernel is proven PURE or carries an honest
    @effect(...) declaration, certified by a least-fixpoint dataflow
    analysis independently validated by Z3 SMT (kernel-titanium-verify.yml).
  - De Bug Corral / evidence-gated branch janitor (PR #784): the branch
    cleanup campaign converted into a standing evidence-gated gate
    (branch_janitor.py + verify_corral_findings.py).

Doctrine that must hold: add gate SOURCES, never weaken a check; a local
~/.dharma witness receipt proves integrity (author can produce it), NOT
authenticity — only the trusted-CI re-run counts as a merge signal;
every gate is fail-closed (missing/malformed config reads as the SAFE /
advisory default, never as pass).

**Next items:**

- [governance] (operator) Ratify this track; then decide the AI-M1 flip: promote docs/governance/hygiene/patterns/AI-M1.yaml stage advisory->enforced via scripts/governance/hygiene/promote.py (turns the graded-binding gate's teeth on with no code change) and/or mark pudgala-rigor a required status check in branch protection.
- [code] (blocker) (blocker) PR-001 live-host edge: one canonical daemon-host observation that live-checkout mutation is denied by default (read-only source mount + DHARMA_EVOLUTION_SHADOW), with a rollback receipt. Sequenced with organism-rewire D4; keep evolution fail-closed until then.
- [ops] De Bug Corral: schedule branch-janitor.yml against real branch sprawl and confirm verify_corral_findings evidence-gate blocks an unverified corral finding on a live run.

**Non-goals:**

- Do not weaken, bypass, or hard-code any telos gate, ratchet, or the one-door verify_promotion arbiter to make a gate green.
- Do not treat a local ~/.dharma witness receipt as a merge signal; only the trusted-CI re-run counts (integrity != authenticity).
- Do not auto-escalate AI-M1 from advisory to enforced from inside the gate; escalation is a deliberate, readable operator promotion.
- Do not add trained weights, capability claims, or production-live closure claims to this track; it certifies the SAFETY floor only.
- Do not touch surfaces owned by sibling tracks except through their own next-items.

**Recently closed tracks:**

- `runtime-truth-spine-adoption-2026-06` — Runtime Truth Spine — Adoption (god objects flow through invoke_agent) (SHIPPED, closed 2026-07-03)
- `runtime-truth-reconciliation-2026-06` — Runtime Truth Reconciliation - operator-visible truth packets (SHIPPED, closed 2026-06-30)
- `runtime-truth-nats-2026-06` — Runtime Truth NATS - internal live transport for A2A dispatch (SHIPPED, closed 2026-06-30)

For machine-readable status, run `python3 scripts/governance/check_track_status.py` — it writes `reports/governance/active_track_evidence.md` (untracked; derived status is not committed). CI publishes the latest copy on the `generated/status` branch: `git show origin/generated/status:reports/governance/active_track_evidence.md`.

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

## VERIFIED NUMBERS (2026-07-03 COUNT REFRESH)

These are the ground-truth metrics. All other documents citing different numbers are stale.
One row per metric — refreshes REPLACE this table (never append; the 2026-06/07
append-style refreshes quadruplicated rows and broke `make docops-integrity`).

| Metric | Value | Verification |
|--------|-------|-------------|
| Total Python modules | **887** | find dharma_swarm -name "*.py" -type f |
| Top-level (flat) modules | **436 (49.2%)** | find dharma_swarm -maxdepth 1 -name "*.py" -type f |
| Total Python LOC | **343,077** | wc -l across dharma_swarm Python modules |
| Test files | **841** | find tests -name "*.py" -type f |
| Test functions | **12,710 `def test_` occurrences under tests/** | rg "def test_" tests |
| Tests collected (pytest) | **12,674 (measured 2026-07-03)** | python3 -m pytest tests/ --collect-only -q |
| Collection errors | **0 (measured 2026-07-03)** | python3 -m pytest tests/ --collect-only -q |
| Markdown files | **1,324** | find . -name "*.md" -type f |
| Markdown total lines | **282,623** | wc -l across all .md |
| Bridge files | **26** | find dharma_swarm -name "*bridge*.py" -type f |
| Adapter files | **26** | find dharma_swarm -type f | rg -i "adapter" |
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

### Forge / Pudgala Naming Boundary
- **Dharma Forge** names the whole-swarm evolution, benchmark, external-receipt,
  candidate-control, Hydra, and arena family.
- **Pudgala Autopoiesis Protostar** names the anti-slop governance mechanism for
  graded claim/evidence binding, `min_evidence_grade` floors,
  `VerifiedMachineReceipt` chains, oracle-independence downgrades, and advisory
  quality gates.
- Do not use Forge names for anti-slop governance mechanisms. Historical
  receipts may preserve old branch names, but live docs and tracked surfaces
  must use the boundary above.

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
