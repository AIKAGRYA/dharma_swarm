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

<!-- GENERATED — do not hand-edit.
     source-of-truth: docs/governance/ACTIVE_TRACK.yaml
     render: python3 scripts/governance/render_active_track_includes.py
     check:  python3 scripts/governance/render_active_track_includes.py --check
     checked by: .github/workflows/active-track.yml, make docops-integrity,
                 tests/test_active_track_governance.py
     newest track verified_at in source: 2026-08-10 -->

**Active portfolio — declared intent only:** 12 co-equal track(s) (WIP warn 8, max 12; model: 1..N co-equal active tracks; typed graph; WIP-limited; surface-owned). This stamped digest carries track identity and surface ownership, NOT live status and NOT full track detail (descriptions, next-items, non-goals stay in the YAML). Live state comes only from `make onboard`; if its ACTIVE PORTFOLIO section is empty or warns, run `python3 scripts/governance/check_track_status.py` — never answer portfolio questions from this block or any other .md copy.

**Spine objectives:** `substrate-nativeness`, `revenue-external-humans-served`, `research-depth` (each covered by at least one active track)

- **`loop-closure-2026-06`** — Cybernetic Loop Closure — wire all 13 loops with receipted closure checks (ACTIVE, serves `substrate-nativeness`, verified 2026-07-11, open blocker items: 3)
  - owns: reports/loop_closure/**, CYBERNETIC_LOOP_MAP.md, docs/plans/LOOP1_CLOSURE_SPEC_2026-07-11.md, scripts/governance/loop1_consumption_check.py, tests/test_loop_supervisor_tristate.py, tests/test_loop1_consumption.py, tests/test_loop1_consumption_check.py
- **`orchestration-arena-v1-2026-06`** — Orchestration Arena v1 — frozen hermetic fitness + zero-weight orchestrator + DPI (ACTIVE, serves `substrate-nativeness`, verified 2026-07-16, open blocker items: 1)
  - owns: dharma_swarm/coordination/**, dharma_swarm/council/**, scripts/governance/arena_truth_report.py, reports/governance/arena/**, tests/test_arena_v1.py, tests/test_dpi.py, tests/test_orchestration_genome.py, tests/test_orchestrator_v1.py, tests/test_council_profiles.py, tests/test_coordination_closure_checks.py, tests/test_arena_truth_report.py
- **`merge-master-mike-d4-2026-06`** — Merge Master Mike — D4 persistent always-on merge agent (ACTIVE, serves `substrate-nativeness`, verified 2026-06-24, open blocker items: 2)
  - owns: scripts/runtime/pr_merge_control.py, scripts/runtime/merge_master_mike_daemon.py, .github/workflows/automerge.yml, .github/workflows/codex-mention-router.yml, .github/workflows/merge-master-mike-backlog.yml, tests/test_pr_merge_control_github_reviews.py
- **`organism-rewire-2026-07`** — Organism Rewire — dormant organs to production, spine standing-on, external gradients (ACTIVE, serves `substrate-nativeness`, verified 2026-07-02, open blocker items: 2)
  - owns: tools/world_scout_go/**, tools/world_signal_ingestor_go/**, tools/github_ingestor_go/**, tools/evidence_ingestor_go/**, dharma_swarm/world_radar/**, dharma_swarm/organism.py, dharma_swarm/strange_loop.py, dharma_swarm/diversity_archive.py, dharma_swarm/archive.py, docker-compose.yml, Dockerfile.swarm
- **`dharmagraph-engine-2026-07`** — DharmaGraph — sovereign durable graph runtime consolidation (ACTIVE, serves `substrate-nativeness`, verified 2026-07-05, open blocker items: 1)
  - owns: dharma_swarm/graph/**, dharma_swarm/workflow.py, dharma_swarm/topology_genome.py, dharma_swarm/checkpoint.py, dharma_swarm/swarm.py, dharma_swarm/orchestrator.py, pyproject.toml, .github/workflows/langgraph-oracle.yml, tests/test_workflow.py, tests/test_topology_execution.py, tests/test_checkpoint.py, tests/test_graph_checkpoint.py, tests/test_graph_reconciler.py, tests/test_graph_durable_invoker.py, tests/test_langgraph_differential_oracle.py, docs/plans/DHARMAGRAPH_PHASED_SPEC_2026-07-05.md, docs/plans/handoffs/DHARMAGRAPH_HANDOFF_DEVIN.md, docs/plans/handoffs/DHARMAGRAPH_HANDOFF_CLAUDE.md, scripts/governance/dharmagraph_parity_gauntlet.py, tests/oracle_support/dharmagraph_gauntlet.py, tests/test_dharmagraph_parity_gauntlet.py, docs/langgraph_parity/DHARMAGRAPH_PARITY_GAUNTLET_RUBRIC_V1.json, docs/langgraph_parity/DHARMAGRAPH_PARITY_GAUNTLET_RUBRIC_V2.json, reports/governance/dharmagraph_parity/**
- **`helm-worldclass-terminal-2026-06`** — Helm — world-class operator terminal (Bun+Ink TUI) (ACTIVE, serves `substrate-nativeness`, verified 2026-07-07, open blocker items: 1)
  - owns: terminal/**
- **`sovereign-safety-tcb-2026-07`** — Sovereign Safety TCB — fail-closed evolution, graded anti-slop, verified kernel, self-gating portfolio (ACTIVE, serves `substrate-nativeness`, verified 2026-07-07, open blocker items: 1)
  - owns: dharma_swarm/evolution_safety.py, scripts/governance/check_claim_evidence_binding.py, scripts/governance/pramana_probe.py, scripts/governance/branch_janitor.py, scripts/governance/verify_corral_findings.py, scripts/governance/hygiene/**, docs/governance/hygiene/patterns/AI-M1.yaml, packages/telos-kernel/**, packages/titanium-verify/**, .github/workflows/pudgala-rigor.yml, .github/workflows/pramana-probe.yml, .github/workflows/kernel-titanium-verify.yml, .github/workflows/kernel-tests.yml, .github/workflows/branch-janitor.yml, tests/test_evolution_safety.py, tests/test_claim_evidence_binding.py, tests/test_pramana_probe.py, tests/test_pramana.py, tests/test_branch_janitor.py, tests/test_verify_corral_findings.py
- **`hyperbolic-time-chamber-2026-07`** — Hyperbolic Time Chamber — afferent ingest, gym battery, Frontier Ledger (ACTIVE, serves `research-depth`, verified 2026-07-07, open blocker items: 1)
  - owns: docs/vision_maps/MASTER_2026-07-07_hyperbolic_time_chamber.md, docs/plans/HYPERBOLIC_CHAMBER_PHASE0_DOSSIER_2026-07-07.md, docs/plans/HYPERBOLIC_CHAMBER_ELEVATION_SPEC_2026-07-07.md, docs/plans/INWARD_ASCENT_PHASE0_DOSSIER_2026-07-07.md, scripts/governance/inward_ascent_baseline.py, scripts/governance/frontier_ledger.py, scripts/governance/transcendence_ledger.py, dharma_swarm/chamber/**, tests/test_chamber_traces.py, tests/test_chamber_gym_git_history.py, tests/test_chamber_daily_delta.py, tests/test_chamber_predictions.py, tests/test_chamber_sandbox.py, tests/test_chamber_ledger_history.py, tests/test_transcendence_ledger.py, reports/governance/inward_ascent/**, reports/governance/chamber/**
- **`company-builder-parity-2026-07`** — TAM (Transdimensional Abundance Machine) — the live Company-Builder Parity board (ACTIVE, serves `revenue-external-humans-served`, verified 2026-07-07, open blocker items: 0)
  - owns: scripts/governance/tam_ledger.py, scripts/governance/tam_axes.py, reports/governance/tam/**, tests/test_tam_ledger.py, docs/plans/TAM_TRANSDIMENSIONAL_ABUNDANCE_MACHINE_2026-07-07.md, docs/plans/TAM_MASTER_PROMPT_2026-07-07.md, docs/research/POLSIA_COFOUNDER_BLUEPRINT_GENEALOGY_2026-07-07.md
- **`onboard-one-door-2026-07`** — One-door onboarding — strict, fast, deterministic session admission (ACTIVE, serves `substrate-nativeness`, verified 2026-07-14, open blocker items: 6)
  - owns: AGENTS.md, Makefile, .github/workflows/structure.yml, .github/workflows/active-track.yml, docs/governance/ANTI_SLOP_RULES.md, docs/governance/AGENTOPS.md, docs/governance/BUILD_SESSION_ENTRYPOINT.md, scripts/docops/check_docops_integrity.py, scripts/governance/agent_onboard.py, scripts/governance/orientation_graph.py, scripts/governance/trust_gate_status.py, scripts/governance/repo_status.py, scripts/governance/run_agent_work_packet.py, scripts/governance/check_track_status.py, dharma_swarm/operator_core/onboarding/**, dharma_swarm/operator_core/control_surface.py, dharma_swarm/operator_core/control_surface_models.py, dharma_swarm/operator_core/operator_coherence/git_governance.py, tests/test_agent_onboard.py, tests/test_orientation_graph.py, tests/test_trust_gate_status.py, tests/test_repo_status.py, tests/test_control_surface.py, tests/test_operator_coherence_cockpit.py, tests/test_agent_work_packet.py, tests/test_active_track_governance.py, tests/test_track_portfolio.py, tests/test_docops_integrity.py, tests/test_make_onboarding_contract.py, tests/test_onboarding_*.py, tests/properties/test_onboarding_readiness_properties.py, reports/agentops/work_packets/onboard-one-door-WP-O*.json
- **`darshan-publication-2026-07`** — Darshan — publication venture cell (multi-disciplinary voice of clear seeing) (ACTIVE, serves `revenue-external-humans-served`, verified 2026-07-12, open blocker items: 2)
  - owns: docs/plans/DARSHAN_CHARTER_2026-07-12.md, reports/darshan/**, reports/tam/**
- **`rsi-worldclass-harness-2026-08`** — RSI World-Class Harness — isolated, paired, budget-bound agent evolution (ACTIVE, serves `research-depth`, verified 2026-08-10, open blocker items: 6)
  - owns: dharma_swarm/forge_lab/**, dharma_swarm/forge_v1/forge_v2/pr_suite_execution.py, dharma_swarm/forge_v1/forge_v2/pr_suite_grader.py, dharma_swarm/forge_v1/forge_v2/pr_suite_validator.py, dharma_swarm/forge_v1/forge_v2/pr_suite_validator_runtime.py, dharma_swarm/forge_v1/forge_v2/taskbed_allocation.py, dharma_swarm/forge_v1/forge_v2/taskbed_ledger.py, dharma_swarm/forge_v1/forge_v2/taskbed_store.py, dharma_swarm/forge_v1/providers.py, dharma_swarm/dgm_loop.py, scripts/forge_lab/**, scripts/ops/systemd/rsi-lab-*, tests/forge_lab_v1/**, tests/test_forge_lab_*.py, tests/test_forge_pr_suite_*.py, tests/test_forge_taskbed_ledger.py, tests/test_dgm_loop.py, docs/ops/FORGE_LAB_V0_1_RUNBOOK.md, docs/ops/RSI_LAB_SYNC.md, specs/FORGE_LAB_V0_1_0_SPEC.md, reports/agentops/work_packets/rsi-worldclass-harness-*.json

Before editing any file, check it against the `owns:` globs above — a surface owned by a track you are not serving is off-limits except through that track's own next-items. Full track detail: `docs/governance/ACTIVE_TRACK.yaml`.

**Recently closed tracks:** `runtime-truth-spine-adoption-2026-06` (SHIPPED, closed 2026-07-03) · `runtime-truth-reconciliation-2026-06` (SHIPPED, closed 2026-06-30) · `runtime-truth-nats-2026-06` (SHIPPED, closed 2026-06-30)

For machine-readable status, run `python3 scripts/governance/check_track_status.py` — it writes `reports/governance/active_track_evidence.md` (untracked; derived status is not committed). CI publishes the latest copy on the `generated/status` branch: `git show origin/generated/status:reports/governance/active_track_evidence.md`.

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
