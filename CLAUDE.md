# dharma_swarm — Claude Code Configuration

## Before Anything Else — the single remembered gate

If you have not run `make onboard` this session, do it now — before any non-trivial Read, Grep, or Edit. It renders the current operating reality and the code-structure tools you should reach for before grep.

`make onboard` is the only command you need to remember. Everything else
(active track, live ops, broken register, axioms, tooling hints, depth
pointers) is rendered from the existing owners by that command:

```bash
make onboard
# or: python3 scripts/governance/agent_onboard.py
```

If this file disagrees with that output on anything live (track id, prereqs, recent commits), trust the onboarding output. This file owns behaviour; the onboarding command surfaces state.

<!-- ACTIVE_TRACK:START -->

<!-- This block is generated from docs/governance/ACTIVE_TRACK.yaml.
     Do not hand-edit. Run scripts/governance/render_active_track_includes.py
     after updating the YAML. -->

**Active portfolio:** 9 co-equal track(s) (WIP warn 8, max 10). A new project is a new track here, not a violation — model: 1..N co-equal active tracks; typed graph; WIP-limited; surface-owned.

**Spine objectives (each track serves one):**

- `substrate-nativeness` — Substrate nativeness — runtime flows through the ontology/spine, not around it (covered)
- `revenue-external-humans-served` — Revenue & external humans served — value leaves the house and someone acts on it (covered)
- `research-depth` — Research depth — the contemplative-mechanistic bridge (R_V, geometric lens) deepens (covered)

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
- [code] DONE 2026-07-06 (PR #798, merged): Phase 0b reconciler (Devin lane) generalized operator_bridge.recover_stale_tasks pattern to delegation_runs; boot scan owned by SwarmManager.init + tick beside reap_orphaned_tasks; recovered_at/heartbeat/quarantine semantics landed. Chaos receipt gate satisfied by tests/test_graph_chaos_receipt.py.
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

### Hyperbolic Time Chamber — afferent ingest, gym battery, Frontier Ledger

**Track id:** `hyperbolic-time-chamber-2026-07` · **Status:** ACTIVE · **Owner:** @AmitabhainArunachala
**Serves spine objective:** `research-depth` · **Verified at:** 2026-07-07 (TTL 21 days)
**Relations:** complements: organism-rewire-2026-07, orchestration-arena-v1-2026-06, loop-closure-2026-06
**Owns surfaces:** docs/vision_maps/MASTER_2026-07-07_hyperbolic_time_chamber.md, docs/plans/HYPERBOLIC_CHAMBER_PHASE0_DOSSIER_2026-07-07.md, docs/plans/HYPERBOLIC_CHAMBER_ELEVATION_SPEC_2026-07-07.md, docs/plans/INWARD_ASCENT_PHASE0_DOSSIER_2026-07-07.md, scripts/governance/inward_ascent_baseline.py, scripts/governance/frontier_ledger.py, scripts/governance/transcendence_ledger.py, dharma_swarm/chamber/**, tests/test_chamber_traces.py, tests/test_chamber_gym_git_history.py, tests/test_chamber_daily_delta.py, tests/test_chamber_predictions.py, tests/test_chamber_sandbox.py, tests/test_chamber_ledger_history.py, tests/test_transcendence_ledger.py, reports/governance/inward_ascent/**, reports/governance/chamber/**
**Moves vital signs:** eval_coverage, quality_gates

Operator-ratified chamber doctrine (vision map 2026-07-07) + elevation
spec (SEAL v2): seal the efferent edge, open the afferent edge wide,
evolve at machine speed against imported and time-lagged reality
(class-2 signal only) until the trust gate opens on measured numbers.
Phase 0 shipped the dossier + baseline scoreboard + Frontier Ledger
(PR #830). Phase 1 Slice A (ratified via plan approval 2026-07-07)
hardwires ONE environment fully alive: G1 git-history gym with the E5
chamber_gym_trace.v1 mandate, E1 transcendence decomposition
(Krogh-Vedelsby from trace rows — verified unowned gap, chamber
surfaces only), E4 causal daily delta chain, E3 micro-prediction lane
on the existing ginko_brier API, E6 velocity columns on the ledger.
All 12 disciplines + substrate ruling enforced.

**Next items:**

- [code] DONE 2026-07-07 (Phase 1 Slice A): dharma_swarm/chamber/ package — traces.py (chamber_gym_trace.v1, E5 mandate), gym_git_history.py (G1 taskpack + deterministic scorer + git-archive leak guard + fixture/live solver seam), chain.py + daily_delta.py (E4 causal chain, expect_chain-verified), predictions.py (E3 emitter/resolver, oracle rule + incident log), ledger_rows.py + ledger_history.py; transcendence_ledger.py (E1, --check replays); frontier_ledger velocity history (E6, door-drift guard per Codex review). 37 chamber tests green. End-to-end drive on REAL repo history (control arms: landed-replay vs null): 2 tasks scored in leak-free sandboxes, committed trace corpus + transcendence receipt (realized E_div=0.25, lift_vs_best=0.0; null-control exposed 1 non-discriminative task — the instrument catching a degenerate task on day one), first causal daily-delta heartbeat, zeitgeist needs_host receipt (egress 403 here). Follow-up folded into item 4: task-discriminativeness filter (drop tasks the null control passes).
- [ops] Live solver seats for G1 (needs provider keys on the running host via key_oracle.dispatchable_now) + first real evolution iteration under compute-ROI declaration. Operator: keys/compute (decision queue items 3/5). BLOCKED ON item 6: the scorer runs untrusted evolved diffs; the Python guards (chamber/sandbox.py: diff denylist, env scrub, leak re-check) raise attack cost but do NOT contain arbitrary native code — the process/network isolation jail MUST land first.
- [code] (blocker) (blocker) Sandbox jail for the G1 scorer before the live untrusted-solver lane opens: process/network/filesystem isolation (seccomp-class caps) — the FIRST earned Rust carve-out named in the substrate ruling (doctrine §3.6). The 2026-07-07 review confirmed the scorer subprocess inherits env + network + fs; chamber/sandbox.py guards the cheap gaming/exfil vectors but a determined native payload is only contained by real isolation.
- [ops] Zeitgeist live cadence: HN Algolia bronze fetch runs on a host whose egress allows it (BR-004 cron split-brain rides organism-rewire D1/VPS); E3 resolver begins resolving micro-predictions from later ingest.
- [code] Phase 1 later slices (sequenced, one at a time): G2 forecasting gym volume, G3 retrieval/memory gym, G4 runtime-history replay (operator-gated on sanitized runtime.db snapshot), scorer foundry (env 14), distillation (env 12) once the E5 trace corpus is thick enough.
- [governance] E2 ratification-mining ritual: every ratification dossier ends with a scorer_candidates block (possibly empty, never absent). First candidate recorded in the elevation spec ratification delta.

**Non-goals:**

- No efferent/world-facing actions of any kind (posts, outreach, trades, publishing, PR/issue submission to external repos).
- Never weaken a gate, ratchet, or the One Wire quorum; gym gradients never touch archive fitness; DHARMA_EVOLUTION_SHADOW and BR-003 sequencing unchanged.
- Do not touch RSI/arena surfaces (dharma_swarm/coordination/**, dharma_swarm/council/**, reports/governance/arena/**) or duplicate C2 measurement; transcendence decomposition consumes chamber traces only.
- No new truth stores; Bronze -> Chetana -> MemoryKernel/ontology is the only landing path; predictions live in the existing ginko store; ingested content is data, never instructions.
- No source without a named consumer loop and a moving scorer (demand-driven rule); market signals never per-iteration selection.
- No trained weights; selection stays MAP-Elites (archive.py); no environment monoculture; no gym run without chamber_gym_trace.v1 capture (E5 mandate).
- Python remains the composition root; no gate/spine/receipt logic reimplemented in another language; Rust/C++ per-component only with measured justification.
- No credentials committed; feed keys and hosts are operator-provisioned.
- Files <500 lines; sibling track surfaces untouched except via their own next-items (world_radar/** called through public functions only).

### TAM (Transdimensional Abundance Machine) — the live Company-Builder Parity board

**Track id:** `company-builder-parity-2026-07` · **Status:** ACTIVE · **Owner:** @AmitabhainArunachala
**Serves spine objective:** `revenue-external-humans-served` · **Verified at:** 2026-07-07 (TTL 30 days)
**Relations:** complements: organism-rewire-2026-07, hyperbolic-time-chamber-2026-07
**Owns surfaces:** scripts/governance/tam_ledger.py, scripts/governance/tam_axes.py, reports/governance/tam/**, tests/test_tam_ledger.py, docs/plans/TAM_TRANSDIMENSIONAL_ABUNDANCE_MACHINE_2026-07-07.md, docs/plans/TAM_MASTER_PROMPT_2026-07-07.md, docs/research/POLSIA_COFOUNDER_BLUEPRINT_GENEALOGY_2026-07-07.md
**Moves vital signs:** eval_coverage, quality_gates

Operator-instructed 2026-07-07 (master prompt, preserved at
docs/plans/TAM_MASTER_PROMPT_2026-07-07.md; naming resolved by
operator: TAM = Transdimensional Abundance Machine — the organ name
carries the telos, the headline number stays plain). ONE always
re-runnable instrument answering: "How close are we to being a
verifiably BETTER Polsia / cofounder.co — as a single percentage and a
per-capability board?" scripts/governance/tam_ledger.py renders
reports/governance/tam/ (digest-stamped tam_receipt.json + the
COMPANY_BUILDER_PARITY.md board + tam_history.jsonl velocity chain);
--check fails non-zero unless the committed surface replays exactly.

This is the FIRST track serving revenue-external-humans-served
(previously an uncovered spine objective) and lands the sequencing
called by organism-rewire-2026-07 next-item 8 ("Next track after this
one lands MUST serve revenue-external-humans-served"). Built as an
arena_truth_report.py sibling (the chamber Frontier Ledger landed on
main via PR #830 only mid-build-session; consolidation onto the
chamber ledger helpers is queued, not assumed).

Scope is measurement only — afferent (competitor PUBLIC data + our own
honest status owners). Efferent-closed: no outreach, no publishing, no
benchmarking claims. authority: projection_only — it owns no fact.
Honesty is the product: every competitor number carries a source URL
and a verification label (NORTH_STAR §5 source-pending rule); every
"ours" cell traces to a repo owner; unmeasured renders UNKNOWN, never
a flattering guess; UNMEASURED rows stay in the denominator so not
measuring can never inflate the headline; AHEAD requires a RUNS-grade
organ AND a cited structural exceed-vector. The honest-ARR axis
(receipted revenue no incumbent publishes third-party-verifiably) is
the headline differentiator.

First honest render (2026-07-07): parity_pct = 35.0 [RED], lanes
Behind 6 / At parity 2 / Ahead 1 / No-equivalent 2 / Unmeasured 1.
That sparse, mostly-behind board IS the day-one truth.

**Next items:**

- [governance] Operator ratification of the track home (standalone company-builder-parity-2026-07 vs folding into another lane — one-line change either way) and of the day-one axis set / scoring weights (Behind 0 / At 1 / Ahead 1.5; UNMEASURED in denominator).
- [research] DONE 2026-07-07: competitor facts refreshed from the adversarially-verified blueprint/genealogy dossier (docs/research/POLSIA_COFOUNDER_BLUEPRINT_GENEALOGY_2026-07-07.md — 100-agent deep research, 20 confirmed / 5 refuted claims). The zilla.so 4.4x ARR-gap framing was REFUTED and retired from all axis rows (replaced by 36kr's ~2.2x headline-vs-recurring decomposition + no-independent-audit finding); Polsia's engine is now citable via its own GitHub dump (Claude-CLI subprocesses on Celery Beat — commodity assembly, production parity unproven), flipping internal_architecture from UNMEASURED to measured. Second render: parity 35.0 -> 45.0 [AMBER], first velocity point on tam_history.jsonl (+10.0 pts — measurement improvement, not capability growth; annotated on the row).
- [code] Consolidation audit vs the chamber Frontier Ledger (PR #830 landed scripts/governance/frontier_ledger.py + dharma_swarm/chamber/ledger_rows.py/ledger_history.py mid-session, after this instrument was built on the arena_truth_report.py contract): if the chamber ledger_history/comparator helpers are importable without touching chamber-owned surfaces, absorb them and delete the local equivalents; else record why two siblings stay.
- [code] Optional dashboard wiring: a KanbanLane[] producer feeding the existing CoherenceKanban.tsx from the tam_receipt.json lanes; until then the COMPANY_BUILDER_PARITY.md table IS the board (governance receipt stays the source of truth).

**Non-goals:**

- No efferent action — no outreach, no publishing, no external benchmarking claims (chamber doctrine; measurement only).
- Do not overload TAM = Total Addressable Market (foundations/FIVE_FOURTEEN_A.md:49) and do not write into the Darshan-owned reports/tam/ — this machine's surface is reports/governance/tam/ only.
- No new digest/receipt/chain primitives — reuse stable_digest/utc_now (memory_kernel.write_receipts), verdict_for/parse_cell_statuses (trust_gate_status.py), and the arena_truth_report.py surface contract.
- No new truth store: authority is projection_only; every cell cites an existing owner (lane_F world dossier, VENTURE_CELL_PORTFOLIO.yaml, swarm-genome organ table) or a public URL.
- Do not weaken any gate/ratchet/One-Wire boundary; do not touch sibling-track surfaces except through their own next-items.

**Recently closed tracks:**

- `runtime-truth-spine-adoption-2026-06` — Runtime Truth Spine — Adoption (god objects flow through invoke_agent) (SHIPPED, closed 2026-07-03)
- `runtime-truth-reconciliation-2026-06` — Runtime Truth Reconciliation - operator-visible truth packets (SHIPPED, closed 2026-06-30)
- `runtime-truth-nats-2026-06` — Runtime Truth NATS - internal live transport for A2A dispatch (SHIPPED, closed 2026-06-30)

For machine-readable status, run `python3 scripts/governance/check_track_status.py` — it writes `reports/governance/active_track_evidence.md` (untracked; derived status is not committed). CI publishes the latest copy on the `generated/status` branch: `git show origin/generated/status:reports/governance/active_track_evidence.md`.

<!-- ACTIVE_TRACK:END -->

## Behavioral Rules (Always Enforced)

- Do what has been asked; nothing more, nothing less
- NEVER create files unless they're absolutely necessary for achieving your goal
- ALWAYS prefer editing an existing file to creating a new one
- NEVER proactively create documentation files (*.md) or README files unless explicitly requested
- NEVER save working files, text/mds, or tests to the root folder
- Never continuously check status after spawning a swarm — wait for results
- ALWAYS read a file before editing it
- NEVER commit secrets, credentials, or .env files
- NEVER use bash for file search — use grep/glob tools instead. bash is for execution only, not navigation.
- BEFORE opening any PR that closes / demotes / adds a BR-id, ALWAYS run `gh pr list --state open --search "BR-NNN"` for each cited BR-id. If another open PR cites the same id, coordinate (rebase / split / close-as-redundant) before pushing. The `pr-collision-detect` workflow is an after-the-fact safety net, not a substitute for this check. See `docs/governance/COHERENCE_DELTA.md` § Pre-flight check.
- **Worktree budget (enforced 2026-06-18):** open git worktrees must be <= active-track count (`docs/governance/ACTIVE_TRACK.yaml`) + 1 canonical tree + <=2 TTL-tagged scratch. Every non-canonical worktree maps to an active track; excess/unmapped worktrees are a governance violation. Compost the branch list to `~/.claude/cabinet/_compost/` first, then remove confirmed-safe worktrees. Replaces the fixed 24-lane law.
- **Naming / identity SSOT = Semantic Commons.** Do not create parallel naming schemes for concept, agent, or object names. When a branch carries Semantic Commons object and alias manifests, resolve names against those manifests before inventing a name; otherwise use the existing ADR-008 API-name grammar in `docs/architecture/ADRs/ADR-008-ontology-api-name-grammar.md` as the naming floor until the manifests land on main.
- **Runtime receipts never enter git.** `reports/a2a/*_receipts/`, `reports/model_*/e2e/`, and `reports/model_pool/` are loop-generated artifacts covered by `.gitignore`; prefer writing runtime receipts under `~/.dharma/`.

## File Organization

- NEVER save to root folder — use the directories below
- Use `dharma_swarm/` for Python source code
- Use `tests/` for test files (one test file per module: `test_foo.py` tests `foo.py`)
- Use `docs/` for documentation and markdown files
- Use `scripts/` for operator utilities and shell scripts
- Use `api/` for FastAPI routers and backend code
- Use `dashboard/` for Next.js frontend code

## Project Architecture

- Python 3.11+, Pydantic 2, async-first (aiosqlite, aiofiles)
- Follow Domain-Driven Design with bounded contexts
- Keep files under 500 lines
- Use typed interfaces for all public APIs
- Use `pytest-asyncio` with `asyncio_mode = "auto"` for testing
- Ensure input validation at system boundaries

### Key Abstractions

- **Organism** (`dharma_swarm/organism.py`): The living system. VSM, identity, memory, router, strange loop, attractor.
- **SwarmManager** (`dharma_swarm/swarm.py`): Top-level coordinator. Agent pool, task board, orchestrator.
- **DarwinEngine** (`dharma_swarm/evolution.py`): Self-improvement via gated evolution.
- **LoopEngine** (`dharma_swarm/cascade.py`): F(S)=S universal convergence loop across 5 domains.
- **DharmaKernel** (`dharma_swarm/dharma_kernel.py`): 25 immutable axioms (SHA-256 signed).
- **MemoryKernel** (`dharma_swarm/memory_kernel/`): Canonical front door for agent memory context; legacy MemoryPlane, RuntimeState facts, MemoryPalace, MemoryLattice, vector, graph, log, and wiki stores are subordinate sources, adapters, projections, or promotion feeds.
- **TelosGatekeeper** (`dharma_swarm/telos_gates.py`): the dharmic safety gate battery (AHIMSA, SATYA, CONSENT, SVABHAAVA, ...). The gate count lives in the code, not here — this file has frozen wrong counts before; read `telos_gates.py` for the live battery.
- **StigmergyStore** (`dharma_swarm/stigmergy.py`): Pheromone-trail coordination.
- **CatalyticGraph** (`dharma_swarm/catalytic_graph.py`): Autocatalytic set detection (Tarjan SCC).
- **StrangeLoop** (`dharma_swarm/strange_loop.py`): Organism self-modification engine.

## The Transcendence Principle (Engineering Axiom)

**The claim**: Diverse competent agents, with decorrelated errors and quality aggregation, provably outperform any individual agent. This is not aspirational — it is proven mathematics (Zhang et al., NeurIPS 2024; Condorcet 1785; Krogh-Vedelsby 1995; Breiman 2001).

**The mechanism**: When multiple experts each make correct decisions on their specialties but make different errors elsewhere, a system that learns the mixture distribution and concentrates toward high-confidence outputs (low-temperature sampling, majority voting, quality-weighted aggregation) will exceed every individual expert. The errors cancel. The knowledge compounds.

**Three modes of transcendence** (Abreu et al. 2025):
1. **Skill denoising** — filtering idiosyncratic errors across agents
2. **Skill selection** — routing to the best agent per sub-problem
3. **Skill generalization** — recombining capabilities beyond any single agent

**Three necessary conditions** (all must hold, or transcendence fails):
1. **Diversity of competence** — agents must have genuinely different capabilities, trained on different data, using different approaches. Same model prompted differently may NOT suffice. Different model families, different specializations, different error profiles. Measured via MAP-Elites behavioral diversity (`archive.py` `MAPElitesGrid`; `diversity_archive.py` is a deprecated shim).
2. **Error decorrelation** — agent errors must be independent. If agents fail on the same inputs in the same way, aggregation provides no benefit. Correlated errors compound; decorrelated errors cancel. This is arithmetic: `E_ensemble = E_mean - E_diversity` (Krogh-Vedelsby). The diversity term directly subtracts from ensemble error.
3. **Quality aggregation** — the mechanism that combines agent outputs must amplify agreement and suppress noise. Temperature concentration, weighted voting, Brier-scored selection, telos-gated filtering. Bad aggregation (simple averaging, loudest-voice-wins) kills the signal.

**The critical tradeoff**: Governance (Beer's VSM: coordination, control, identity) is necessary for sustained operation. But governance can reduce diversity through standardization, shared protocols, convergence pressure. **Every governance mechanism must be evaluated against its diversity cost.** Light coordination (System 2 damping) preserves diversity. Heavy control (System 3 mandates) may destroy it.

**What this means for every session**:
- When adding agents: maximize behavioral diversity, not count. The 5th agent from a different model family adds more than the 50th agent from the same family.
- When designing orchestration: route by specialty (skill selection), aggregate by quality weighting (skill denoising), recombine in cascade loops (skill generalization).
- When evolving agents: DarwinEngine MUST preserve diversity. Pure fitness pressure → convergence → transcendence death. Use diversity-preserving selection (MAP-Elites in `archive.py`).
- When measuring success: track the Krogh-Vedelsby diversity term, not just individual agent fitness. If diversity is falling, transcendence is dying regardless of individual performance.
- When governing: telos gates and VSM channels are necessary but must be LIGHT. System 2 (damping) > System 3 (mandates). The governance cost of a gate is measured in diversity loss.

**Where this lives in the codebase**:
- `archive.py` (`MAPElitesGrid`, wired into `DarwinEngine` via `EvolutionArchive`) — production diversity preservation; MAP-Elites was consolidated here (D6a, 2026-07-02) and `diversity_archive.py` is now a deprecated re-export shim; `coordination/genome.py` has the arena's own MAP-Elites variant (shared-descriptor question still open)
- `orchestrator.py` — topology-based routing (fan-out/fan-in/pipeline/broadcast)
- `evolution.py` — DarwinEngine with diversity-preserving selection
- `vsm_channels.py` — Beer's S1-S5 nervous system (light governance)
- `ginko_brier.py` — Brier scoring as aggregation quality measurement
- `signal_bus.py` — decorrelated loop-to-loop signaling (not opinion sharing)
- `handoff.py` — typed artifact handoff preserving agent independence

**Research reference**: Full 9-phase literature review at `spec-forge/transcendence-multi-agent-coordination/research/`

## Build & Test

```bash
# Run all tests
python3 -m pytest tests/ -q

# Run a single test file
python3 -m pytest tests/test_cascade.py -q

# Fast subset (10s per-test timeout, first failure stops)
make test-fast

# Standard suite (excludes slow/docker/network markers)
make test

# Static analysis / repo inventory
python3 xray.py

# Dashboard lint
npm --prefix dashboard run lint
```

- ALWAYS run tests after making code changes
- ALWAYS verify tests pass before committing

## CLI Entry Points

```bash
# Primary CLI
dgc status          # System status
dgc health          # Health diagnostics
dgc stigmergy       # Read stigmergy marks
dgc hum             # Subconscious dreams
dgc evolve trend    # Evolution fitness trend
dgc dharma status   # Kernel integrity check

# API server
uvicorn api.main:app --host 127.0.0.1 --port 8420 --reload

# Dashboard
npm --prefix dashboard run dev

# Operator launcher
bash run_operator.sh
```

## Security Rules

- NEVER hardcode API keys, secrets, or credentials in source files
- NEVER commit .env files or any file containing secrets
- Always validate user input at system boundaries
- Always sanitize file paths to prevent directory traversal

## State Directory (~/.dharma/)

- `~/.dharma/witness/` — Gate check witness logs (JSONL)
- `~/.dharma/stigmergy/marks.jsonl` — Stigmergic marks (append-only)
- `~/.dharma/evolution/archive.jsonl` — Evolution archive
- `~/.dharma/meta/recognition_seed.md` — System self-model
- `~/.dharma/meta/catalytic_graph.json` — Autocatalytic graph
- `~/.dharma/organism_memory/mutations.jsonl` — Strange loop mutations
- `~/.dharma/traces/` — Trace entries

## Navigation

See [`docs/architecture/NAVIGATION.md`](docs/architecture/NAVIGATION.md) for the full module map (770+ modules under `dharma_swarm/`, 12 architectural layers; run `python3 xray.py` for the live count).
See [`docs/MEGAFILE_INDEX.md`](docs/MEGAFILE_INDEX.md) for the ten highest-system onboarding maps and their current status.
See `README.md` for repo map and common commands.
See `foundations/` for the 10-pillar intellectual genome.

### Skills & Agent Role Registries (who reads which instruction files)

Four separate registries; do not cross-pollinate formats:

- `dharma_swarm/skills/*.skill.md` — **swarm subagent role definitions**, parsed by `dharma_swarm/skills.py` (`SkillRegistry`). Format contract: yaml-lite frontmatter ONLY (flat `key: value`, inline arrays `[a, b]`, one-level nesting for `context_weights`; block lists (`- item`) are silently dropped by the parser); first body block = description used for keyword matching; everything after = the agent's system prompt. Also discovered from `~/.dharma/skills/` and `.dharma/skills/`.
- `.agents/skills/*/SKILL.md` — testing/verification playbooks for external coding agents (Devin etc.). Standard `name`/`description` frontmatter.
- `.warp/skills/*/SKILL.md` — Warp/Oz operator skills (janitor, verifier, roast council, session-close ledger). Each declares a hard authority boundary; never widen one to "get something done".
- `dharma_swarm/chetana/claude_code_plugin/` — the chetana memory plugin (skill + slash commands + hooks).

**Gotcha:** `.claude/*` is gitignored (only `.claude/hooks/` and `.claude/settings.json` are tracked), so personal `.claude/skills/` and `.claude/agents/` never reach remote/cloud sessions. Anything an agent must see in every checkout belongs in one of the tracked registries above, not in `.claude/`.

## CRITICAL: Read Before Any Code Changes

**Build-session entrypoint:** Before any build work, read [`docs/governance/BUILD_SESSION_ENTRYPOINT.md`](docs/governance/BUILD_SESSION_ENTRYPOINT.md) and run `make onboard`. The current build **portfolio** (1–N co-equal active tracks) is declared in [`docs/governance/ACTIVE_TRACK.yaml`](docs/governance/ACTIVE_TRACK.yaml) and rendered by `make onboard` — do not name a track here in prose. Substrate-nativeness is a measured number, not a prose constant — run `python3 scripts/governance/spine_bypass_report.py` for the live dispatch-site measure instead of citing any doc's frozen percentage. When the operator proposes a new project, **open a new track** in the portfolio (`serves:` a spine objective, `owned_surfaces:`, acceptance criteria) up to the WIP limit — a new project is a new track, not a violation of an existing one.

**Highest-system map:** Read [`docs/MEGAFILE_INDEX.md`](docs/MEGAFILE_INDEX.md) before treating any large map as canonical. It points to the Attractor Closure synthesis, live ops dashboard, broken register, and missing slots.

See [`INTERFACE_MISMATCH_MAP.md`](INTERFACE_MISMATCH_MAP.md) for the complete map of every interface mismatch between modules. **This is the #1 source of runtime failures.** The map documents:
- **Live BLOCKER/DEGRADED status lives in the map itself — do not freeze a count or a dated snapshot here** (this section rotted twice by doing so: the 2026-06-22 snapshot it used to carry said NEW-14's fix was "in flight" after the map already marked it RESOLVED, and omitted NEW-12 entirely). Read `INTERFACE_MISMATCH_MAP.md` for the current tally; cite nothing from memory.
- A prioritized **Bootstrap Sequence** of fixes (most now resolved)

**Rule for all sessions:** Before fixing a bug or adding a feature, check the mismatch map first. If the module pair you're touching has a known mismatch, fix the mismatch as part of your change. Do not add new callers to broken interfaces.

**Rule for all sessions:** After fixing a mismatch, update the map. Remove the entry or mark it RESOLVED with the commit hash.

Historical model-routing notes now live at [`docs/_archive/2026-04/MODEL_ROUTING_MAP.md`](docs/_archive/2026-04/MODEL_ROUTING_MAP.md). Treat that file as stale context only; verify current provider and routing behavior directly against code before changing model calls.

See [`CYBERNETIC_LOOP_MAP.md`](CYBERNETIC_LOOP_MAP.md) for every feedback loop's sense→act→evaluate→adapt path, current closure status, and verification commands.

Before writing or debugging any code that runs a `Proposal` through `DarwinEngine.gate_check` / the telos gatekeeper (evolution, self-mod, `mutation`/`sealed_packet` proposals, or tests thereof), read [`docs/architecture/EVOLUTION_PROPOSAL_GATE_CONTRACT.md`](docs/architecture/EVOLUTION_PROPOSAL_GATE_CONTRACT.md). WS4 hard-rejects a self-mod proposal on any Tier-C advisory `REVIEW`, so a proposal must clear the whole Tier-C battery at once. Use `tests/evolution_gate_helpers.py` to build passing proposals and `scripts/diagnostics/proposal_gate_probe.py` to map which gates a candidate trips (BR-021).

Historical agent identity notes now live at [`docs/_archive/2026-04/AGENT_IDENTITY_UNIFICATION.md`](docs/_archive/2026-04/AGENT_IDENTITY_UNIFICATION.md). Treat that file as stale context only; verify current agent creation and identity behavior directly against code before changing that surface.
