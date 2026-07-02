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

**Active portfolio:** 5 co-equal track(s) (WIP warn 5, max 10). A new project is a new track here, not a violation — model: 1..N co-equal active tracks; typed graph; WIP-limited; surface-owned.

**Spine objectives (each track serves one):**

- `substrate-nativeness` — Substrate nativeness — runtime flows through the ontology/spine, not around it (covered)
- `revenue-external-humans-served` — Revenue & external humans served — value leaves the house and someone acts on it (**no active track**)
- `research-depth` — Research depth — the contemplative-mechanistic bridge (R_V, geometric lens) deepens (**no active track**)

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

- [code] DONE 2026-07-02: a2a_bridge.submit_via_spine wired into production dispatch — ingest_trishula_inbox (Slice 2) now dispatches through submit_via_spine (invoke_agent + exactly one EvidenceReceipt per ingest); the a2a_bridge.py:307 allowlist entry removed from scripts/governance/spine_bypass_report.py (intentional bypasses 5→4) and the spine_bypass_entries ratchet baseline lowered to 4.
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

- [code] (blocker) D1 (blocker): DHARMA_SPINE_DISPATCH=1 standing in docker-compose swarm service (+ documented Mac plist env path); Loop-1 closure reads LIVE persistently on the daemon host.
- [code] Spine visibility: `dgc spine tail` (live EvidenceReceipt stream) + read-only cockpit pulse panel (receipts/hour, last-receipt age, dropoff count) so the operator can SEE and FEEL the spine working.
- [code] Go sense-organ hardening + Loop 5b: compiled-binary or toolchain-checked invocation, per-source errors surfaced to cockpit, github_ingestor live trigger (go-g04), and a host-aware closure check covering the Go chain in the loop map.
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

**Recently closed tracks:**

- `runtime-truth-reconciliation-2026-06` — Runtime Truth Reconciliation - operator-visible truth packets (SHIPPED, closed 2026-06-30)
- `runtime-truth-nats-2026-06` — Runtime Truth NATS - internal live transport for A2A dispatch (SHIPPED, closed 2026-06-30)
- `truth-graph-platform-2026-06` — Truth Graph Platform v1 - repo context + receipted A2A presence (SHIPPED, closed 2026-06-30)

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
