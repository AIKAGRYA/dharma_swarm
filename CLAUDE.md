# dharma_swarm — Claude Code Configuration

dharma_swarm is a self-improving multi-agent organism: an async Python core
(`dharma_swarm/`), a FastAPI backend (`api/`), a Next.js dashboard
(`dashboard/`), Go ingestors (`tools/`), and a governance layer whose job is
mechanical verification of claims. You are a capable agent. This file carries
only what you cannot quickly discover from the code; when prose and code
disagree — including this file — the code is the truth.

## Talking to the operator

**The operator does not write code.** Write to be understood by someone who
runs this system but does not read Python, YAML, or git plumbing. This is a
hard requirement, not a style preference — an unclear ask wastes their turn
and stalls the work.

- **Never end with a vague hand-off.** "Awaiting your call", "needs your
  decision", "let me know how you want to proceed" are all failures. If you
  want something from the operator, write the actual question, the options,
  and what happens with each.
- **One ask, one line, answerable with a word.** Good: "Do you want me to
  publish PR #1363 so it can merge? Yes or no." Bad: "#1363 remains in draft
  pending your decision on un-drafting."
- **Say the consequence, not the mechanism.** "This change is finished but
  marked draft, so GitHub will not merge it" beats "mergeable_state is clean
  but draft:true".
- **Translate the jargon or drop it.** Merge queue, rebase, conflict, CI,
  branch protection — each needs a plain-English gloss on first use in a
  reply, or a different word. Never assume the acronym landed.
- **Separate FYI from ask.** Status the operator does not have to act on goes
  in its own place, clearly labelled, and never wears question marks.
- **Decide what you can decide.** Only escalate choices that are genuinely
  theirs: spending money, publishing to the outside world, changing what the
  system is for, or anything you cannot undo. Everything else, make the call
  and say what you did.

## Session start

Run `make onboard` once (sub-second). It prints session status: checkout,
portfolio digest, broken-register tally, toolchain — plus a canonical
first-read list. Treat that list as reference surfaces to consult when your
task touches them, not a per-session reading gate; this file is the behavioral
contract and wins on behavior. Then start working — read deeper docs when your
task touches them (see "Read when relevant" below).

**What an onboard run does and does not prove:** READY is evidence about the
local session evaluation only. It is NOT proof of edit admission, CI admission,
merge approval, or whole-organism liveness — and it is not permission to edit.
Deeper read-only projection: `make organism-status`.

Packet ceremony is required only when your changed paths match
`HOT_PATH_PATTERNS` in `scripts/runtime/pr_merge_control.py`: bind scope with
`make agent-build-preflight PACKET=<path>`, close with
`make agent-build-closeout PACKET=<path>`. A narrower lane or campaign
contract may require packets more broadly (the Titanium campaign does, per
`docs/plans/TITANIUM_GRADE_REPOSITORY_HARDENING_2026-07-10.md`); when one
binds your work, it wins. Everything else: edit, test, push.
Command boundaries: `docs/governance/BUILD_SESSION_ENTRYPOINT.md`.

<!-- ACTIVE_TRACK:START -->

<!-- GENERATED — do not hand-edit.
     source-of-truth: docs/governance/ACTIVE_TRACK.yaml
     render: python3 scripts/governance/render_active_track_includes.py
     check:  python3 scripts/governance/render_active_track_includes.py --check
     checked by: .github/workflows/active-track.yml, make docops-integrity,
                 tests/test_active_track_governance.py
     newest track verified_at in source: 2026-08-04 -->

**Active portfolio — declared intent only:** 10 co-equal track(s) (WIP warn 8, max 10; model: 1..N co-equal active tracks; typed graph; WIP-limited; surface-owned). This stamped digest carries track identity and surface ownership, NOT runtime truth and NOT full track detail (descriptions, next-items, non-goals stay in the YAML). Declared intent comes from `docs/governance/ACTIVE_TRACK.yaml`; evaluate it with `python3 scripts/governance/check_track_status.py`. Never answer runtime or liveness questions from this block or another prose copy.

**Spine objectives:** `substrate-nativeness`, `revenue-external-humans-served`, `research-depth` (each covered by at least one active track)

- **`loop-closure-2026-06`** — Cybernetic Loop Closure — wire all 13 loops with receipted closure checks (ACTIVE, serves `substrate-nativeness`, verified 2026-07-11, open blocker items: 3)
  - owns: reports/loop_closure/**, CYBERNETIC_LOOP_MAP.md, docs/plans/LOOP1_CLOSURE_SPEC_2026-07-11.md, scripts/governance/loop1_consumption_check.py, tests/test_loop_supervisor_tristate.py, tests/test_loop1_consumption.py, tests/test_loop1_consumption_check.py
- **`orchestration-arena-v1-2026-06`** — Orchestration Arena v1 — frozen hermetic fitness + zero-weight orchestrator + DPI (ACTIVE, serves `substrate-nativeness`, verified 2026-07-17, open blocker items: 1)
  - owns: dharma_swarm/coordination/**, dharma_swarm/council/**, scripts/governance/arena_truth_report.py, reports/governance/arena/**, tests/test_arena_v1.py, tests/test_dpi.py, tests/test_orchestration_genome.py, tests/test_orchestrator_v1.py, tests/test_council_profiles.py, tests/test_coordination_closure_checks.py, tests/test_arena_truth_report.py
- **`merge-master-mike-d4-2026-06`** — Merge Master Mike — D4 persistent always-on merge agent (ACTIVE, serves `substrate-nativeness`, verified 2026-07-16, open blocker items: 1)
  - owns: scripts/runtime/pr_merge_control.py, scripts/runtime/merge_master_mike_daemon.py, .github/workflows/automerge.yml, .github/workflows/codex-mention-router.yml, .github/workflows/merge-master-mike-backlog.yml, tests/test_merge_master_mike_daemon.py, tests/test_pr_merge_control.py, tests/test_pr_merge_control_github_reviews.py
- **`organism-rewire-2026-07`** — Organism Rewire — dormant organs to production, spine standing-on, external gradients (ACTIVE, serves `substrate-nativeness`, verified 2026-08-04, open blocker items: 6)
  - owns: tools/world_scout_go/**, tools/world_signal_ingestor_go/**, tools/github_ingestor_go/**, tools/evidence_ingestor_go/**, dharma_swarm/world_radar/**, scripts/runtime/github_ingestor_runner.py, tests/test_github_ingestor_runner.py, tests/test_go_evidence_ingestor_bridge.py, tests/test_go_github_ingestor_bridge.py, tests/test_go_world_signal_bridge.py, tests/test_go_receipt_identity_verify.py, tests/test_go_adapter_contracts.py, tests/test_world_radar_go_bridge.py, dharma_swarm/organism.py, dharma_swarm/strange_loop.py, dharma_swarm/diversity_archive.py, dharma_swarm/archive.py, docker-compose.yml, Dockerfile.swarm, ACTIVE_SURFACE_MANIFEST.yaml, dharma_swarm/runtime_state.py, dharma_swarm/sarathi/**, tests/test_runtime_state.py, tests/test_sarathi_public_api.py, tests/test_sarathi_shell.py, tests/test_sarathi_import_boundaries.py, docs/README.md, docs/persistent_agents/**, reports/agentops/work_packets/organism-rewire-WP-SARATHIROOT-P0.json, dharma_swarm/mission_control.py, dharma_swarm/mission_control_contract.py, dharma_swarm/mission_control_execution.py, dharma_swarm/mission_control_execution_support.py, dharma_swarm/mission_control_lifecycle.py, dharma_swarm/mission_control_mcp.py, dharma_swarm/mission_control_mcp_mutations.py, dharma_swarm/mission_control_projection.py, dharma_swarm/mission_control_reconciliation.py, dharma_swarm/mission_control_recovery.py, dharma_swarm/mission_control_dispatch.py, dharma_swarm/mission_control_a2a.py, dharma_swarm/mission_control_sarathi.py, tests/test_mission_control.py, tests/test_mission_control_execution.py, tests/test_mission_control_mcp.py, tests/test_mission_control_dispatch.py, tests/test_mission_control_a2a.py, tests/test_mission_control_sarathi.py, api/routers/control_surface.py, tests/test_control_surface.py, tests/test_control_surface_router_threadpool.py, tests/test_control_surface_mission_sarathi.py, dashboard/src/app/dashboard/control-surface/page.tsx, dashboard/src/hooks/useMissionSarathi.ts, dashboard/src/components/cockpit/MissionSarathiStrip.tsx, dharma_swarm/operator_brief/mission_control_citations.py, tests/test_operator_brief_mission_control_citations.py, reports/agentops/work_packets/organism-rewire-WP-MISSIONCONTROL-P2-ADMISSION.json
- **`dharmagraph-engine-2026-07`** — DharmaGraph — sovereign durable graph runtime consolidation (ACTIVE, serves `substrate-nativeness`, verified 2026-07-05, open blocker items: 1)
  - owns: dharma_swarm/graph/**, dharma_swarm/workflow.py, dharma_swarm/topology_genome.py, dharma_swarm/checkpoint.py, dharma_swarm/swarm.py, dharma_swarm/orchestrator.py, pyproject.toml, .github/workflows/langgraph-oracle.yml, tests/test_workflow.py, tests/test_topology_execution.py, tests/test_checkpoint.py, tests/test_graph_checkpoint.py, tests/test_graph_reconciler.py, tests/test_graph_durable_invoker.py, tests/test_langgraph_differential_oracle.py, tests/test_graph_neutral_langgraph_oracle.py, tests/test_graph_pregel_properties.py, docs/plans/DHARMAGRAPH_PHASED_SPEC_2026-07-05.md, docs/plans/handoffs/DHARMAGRAPH_HANDOFF_DEVIN.md, docs/plans/handoffs/DHARMAGRAPH_HANDOFF_CLAUDE.md, scripts/governance/dharmagraph_parity_gauntlet.py, tests/oracle_support/dharmagraph_gauntlet.py, tests/test_dharmagraph_parity_gauntlet.py, docs/langgraph_parity/DHARMAGRAPH_PARITY_GAUNTLET_RUBRIC_V1.json, docs/langgraph_parity/DHARMAGRAPH_PARITY_GAUNTLET_RUBRIC_V2.json, docs/langgraph_parity/DHARMAGRAPH_PARITY_GAUNTLET_RUBRIC_V3.json, docs/langgraph_parity/DHARMAGRAPH_JUDGE_RATIFICATIONS_V1.json, reports/governance/dharmagraph_parity/**, docs/plans/DHARMAGRAPH_ASCENT_SPEC_2026-07-17.md, docs/plans/handoffs/DHARMAGRAPH_ASCENT_*.md, docs/plans/DHARMAGRAPH_FRONTIER_DOSSIER_*.md, docs/governance/CAMPAIGN_KERNEL.md, tests/oracle_support/scenarios.py, tests/oracle_support/outcomes.py
- **`helm-worldclass-terminal-2026-06`** — Helm — world-class operator terminal (Bun+Ink TUI) (ACTIVE, serves `substrate-nativeness`, verified 2026-07-07, open blocker items: 1)
  - owns: terminal/**
- **`sovereign-safety-tcb-2026-07`** — Sovereign Safety TCB — fail-closed evolution, graded anti-slop, verified kernel, self-gating portfolio (ACTIVE, serves `substrate-nativeness`, verified 2026-07-07, open blocker items: 1)
  - owns: dharma_swarm/evolution_safety.py, scripts/governance/check_claim_evidence_binding.py, scripts/governance/pramana_probe.py, scripts/governance/branch_janitor.py, scripts/governance/verify_corral_findings.py, scripts/governance/hygiene/**, docs/governance/hygiene/patterns/AI-M1.yaml, packages/telos-kernel/**, packages/titanium-verify/**, .github/workflows/pudgala-rigor.yml, .github/workflows/pramana-probe.yml, .github/workflows/kernel-titanium-verify.yml, .github/workflows/kernel-tests.yml, .github/workflows/branch-janitor.yml, tests/test_evolution_safety.py, tests/test_claim_evidence_binding.py, tests/test_pramana_probe.py, tests/test_pramana.py, tests/test_branch_janitor.py, tests/test_verify_corral_findings.py
- **`hyperbolic-time-chamber-2026-07`** — Hyperbolic Time Chamber — afferent ingest, gym battery, Frontier Ledger (ACTIVE, serves `research-depth`, verified 2026-07-07, open blocker items: 1)
  - owns: docs/vision_maps/MASTER_2026-07-07_hyperbolic_time_chamber.md, docs/plans/HYPERBOLIC_CHAMBER_PHASE0_DOSSIER_2026-07-07.md, docs/plans/HYPERBOLIC_CHAMBER_ELEVATION_SPEC_2026-07-07.md, docs/plans/INWARD_ASCENT_PHASE0_DOSSIER_2026-07-07.md, scripts/governance/inward_ascent_baseline.py, scripts/governance/frontier_ledger.py, scripts/governance/transcendence_ledger.py, dharma_swarm/chamber/**, tests/test_chamber_traces.py, tests/test_chamber_gym_git_history.py, tests/test_chamber_daily_delta.py, tests/test_chamber_predictions.py, tests/test_chamber_sandbox.py, tests/test_chamber_ledger_history.py, tests/test_transcendence_ledger.py, reports/governance/inward_ascent/**, reports/governance/chamber/**
- **`repository-titanium-hardening-2026-07`** — Titanium-grade repository hardening — truthful verification and clean-room closure (ACTIVE, serves `substrate-nativeness`, verified 2026-07-31, open blocker items: 4)
  - owns: Makefile, Dockerfile, .github/workflows/hermetic.yml, .github/workflows/tests.yml, .github/workflows/ci-parity.yml, .github/workflows/docops.yml, .github/workflows/docops-reconcile-main.yml, .github/workflows/pr-dedupe.yml, .github/workflows/bot-pr-limit.yml, .github/workflows/a2a-agni-live-contact.yml, docs/governance/CI_TRUTH_CONTRACT.json, scripts/governance/ci_parity_manifest.json, scripts/governance/check_ci_parity.py, scripts/runtime/ci_truth.py, scripts/governance/run_semgrep_with_ca.sh, scripts/uplift_guards/shakti_warrant_guard.py, scripts/uplift_guards/run_pre_commit.py, scripts/governance/check_shakti_warrant.py, scripts/governance/check_nats_substrate_contract.py, scripts/governance/check_nats_live_production_evidence.py, scripts/governance/run_nats_live_production_matrix.py, scripts/docops/**, dharma_swarm/build_engine.py, dharma_swarm/autonomous_agent.py, dharma_swarm/diff_applier.py, dharma_swarm/sandbox.py, docs/docops/AUTO_INVENTORY.md, api/main.py, tests/test_api_auth.py, tests/test_verify_api.py, tests/test_bootstrap_contract.py, tests/test_verifier_selfcheck_contract.py, tests/test_semgrep_wrapper.py, tests/test_uplift_guard_subprocess.py, tests/test_fast_suite_isolation.py, tests/test_agent_work_packet.py, tests/test_make_onboarding_contract.py, tests/test_diff_applier.py, tests/test_sandbox.py, tests/test_nats_verification_split.py, tests/test_nats_substrate_contract.py, tests/test_nats_live_production_evidence.py, tests/test_nats_live_contact.py, tests/governance/test_ci_parity_guard.py, tests/test_ci_truth.py, tests/test_docops_integrity.py, tests/test_docops_reconcile_workflow.py, tests/test_pr_dedupe_workflow.py, tests/test_polyglot_ci_contract.py, tests/test_hermetic_supply_chain.py, docs/plans/TITANIUM_GRADE_REPOSITORY_HARDENING_2026-07-10.md, docs/prompts/TITANIUM_HARDENING_CAMPAIGN_EXECUTOR_2026-07-17.md, reports/governance/titanium/**, dashboard/src/lib/operatorCoherence.ts, dashboard/src/components/operator-coherence/v2/cockpitV2Model.ts, dashboard/src/components/operator-coherence/v2/CockpitV2Board.tsx, dashboard/src/components/operator-coherence/v2/cockpitV2Model.test.ts
- **`darshan-publication-2026-07`** — Darshan — publication venture cell (multi-disciplinary voice of clear seeing) (ACTIVE, serves `revenue-external-humans-served`, verified 2026-07-12, open blocker items: 2)
  - owns: docs/plans/DARSHAN_CHARTER_2026-07-12.md, reports/darshan/**, reports/tam/**

Before editing any file, check it against the `owns:` globs above — a surface owned by a track you are not serving is off-limits except through that track's own next-items. Full track detail: `docs/governance/ACTIVE_TRACK.yaml`.

**Recently closed tracks:** `company-builder-parity-2026-07` (RETIRED, closed 2026-07-17) · `onboard-one-door-2026-07` (RETIRED, closed 2026-07-17) · `onboard-session-status-2026-07` (SHIPPED, closed 2026-07-17)

For machine-readable status, run `python3 scripts/governance/check_track_status.py` — it writes `reports/governance/active_track_evidence.md` (untracked; derived status is not committed). CI publishes the latest copy on the `generated/status` branch: `git show origin/generated/status:reports/governance/active_track_evidence.md`.

<!-- ACTIVE_TRACK:END -->

## Hard rules

- **No secrets in git.** No keys, credentials, or `.env` files — gitleaks
  blocks merge. Validate input and sanitize paths at system boundaries.
- **Citation-or-silence.** Every factual claim you write — spec, PR body,
  report, conclusion — carries a `file:line` citation or a runnable command.
  Uncited claims carry zero weight regardless of fluency. Prefer uncharmable
  mechanical checks (ratcheted baselines, import provenance, DocOps counts)
  over reviewer vigilance.
- **Runtime receipts never enter git.** `reports/a2a/*_receipts/`,
  `reports/model_*/e2e/`, and `reports/model_pool/` are loop-generated and
  gitignored; write runtime receipts under `~/.dharma/`.
- **No new root files.** Source in `dharma_swarm/`, tests in `tests/`
  (`test_foo.py` per module), docs in `docs/`, operator scripts in `scripts/`,
  FastAPI in `api/`, Next.js in `dashboard/`.
- **Naming floor:** the ADR-008 API-name grammar
  (`docs/architecture/ADRs/ADR-008-ontology-api-name-grammar.md`); do not
  invent parallel naming schemes for concepts, agents, or objects.
- **BR-id PRs:** before opening a PR that adds/closes/demotes a BR-id, check
  open PRs citing the same id and coordinate; the `pr-collision-detect`
  workflow is the after-the-fact net.
- **Worktree budget** is enforced by
  `scripts/governance/check_worktree_budget.py` — run it rather than counting
  from prose.

## Build & test

```bash
python3 -m pytest tests/ -q             # full suite
python3 -m pytest tests/test_cascade.py -q  # one file
make test-fast                          # 10s per-test timeout, first failure stops
make test                               # excludes slow/docker/network markers
python3 scripts/repo_xray.py            # live module inventory (never cite counts from prose)
npm --prefix dashboard run lint         # dashboard lint
```

Run the tests your change touches before committing; run the suite before
pushing.

## Where enforcement actually lives

Among CI checks, only those marked `required` in
`docs/governance/CI_TRUTH_CONTRACT.json` block merge; every other CI job is
advisory. That JSON carries the local reproduction command and autofix policy
for every gate — read it instead of guessing which red matters. Merge
admission is wider than CI: Merge Master's gate
(`scripts/runtime/pr_merge_control.py`) also blocks a green-CI PR on
conflicts, requested-changes reviews, unresolved review threads, missing
agent-review receipts, and HIGH/CRITICAL risk without human approval. Never
weaken a gate to go green, and never add prose to satisfy one; fix the thing
it measures.

## Architecture

Python 3.11+, Pydantic 2, async-first (aiosqlite, aiofiles), typed public
APIs, `pytest-asyncio` with `asyncio_mode = "auto"`.

### Key Abstractions

- **Organism** (`dharma_swarm/organism.py`) — the living system: VSM,
  identity, memory, router, strange loop, attractor.
- **SwarmManager** (`dharma_swarm/swarm.py`) — agent pool, task board,
  orchestrator.
- **DarwinEngine** (`dharma_swarm/evolution.py`) — gated self-improvement;
  selection must stay diversity-preserving (`MAPElitesGrid` in
  `dharma_swarm/archive.py`; `diversity_archive.py` is a deprecated shim).
- **DharmaKernel** (`dharma_swarm/dharma_kernel.py`) — 25 immutable axioms,
  SHA-256 signed.
- **TelosGatekeeper** (`dharma_swarm/telos_gates.py`) — the safety-gate
  battery (AHIMSA, SATYA, CONSENT, ...); the live gate count is in the code,
  never in prose.
- **MemoryKernel** (`dharma_swarm/memory_kernel/`) — canonical front door for
  agent memory; legacy stores are subordinate adapters and projections.
- **StigmergyStore** (`dharma_swarm/stigmergy.py`), **CatalyticGraph**
  (`dharma_swarm/catalytic_graph.py`), **StrangeLoop**
  (`dharma_swarm/strange_loop.py`), **LoopEngine** (`dharma_swarm/cascade.py`).

**Ensemble principle (why governance stays light):** diverse agents with
decorrelated errors and quality-weighted aggregation outperform any single
agent (`E_ensemble = E_mean - E_diversity`, Krogh-Vedelsby). Evolution must
preserve behavioral diversity, aggregation is quality-weighted
(`dharma_swarm/ginko_brier.py`), and every new gate is paid for in diversity —
prefer damping to mandates.

## Read when relevant (not before every change)

- Touching interfaces between modules → `INTERFACE_MISMATCH_MAP.md`; if the
  pair you're touching has a known mismatch, fix it as part of your change,
  then update the map.
- Touching `DarwinEngine.gate_check` / telos proposals →
  `docs/architecture/EVOLUTION_PROPOSAL_GATE_CONTRACT.md`; build passing
  proposals with `tests/evolution_gate_helpers.py`; map gate trips with
  `scripts/diagnostics/proposal_gate_probe.py`.
- Feedback loops → `CYBERNETIC_LOOP_MAP.md` (closure status + verification
  commands).
- Full module map → `docs/architecture/NAVIGATION.md`; live counts from
  `scripts/repo_xray.py`.
- Model routing / agent identity → verify directly against code; the notes in
  `docs/_archive/2026-04/` are stale context only.

## CLI entry points

```bash
dgc status           # system status
dgc health           # health diagnostics
dgc stigmergy        # read stigmergy marks
dgc hum              # subconscious dreams
dgc evolve trend     # evolution fitness trend
dgc dharma status    # kernel integrity check
uvicorn api.main:app --host 127.0.0.1 --port 8420 --reload
npm --prefix dashboard run dev
bash run_operator.sh
```

## Skills & agent-instruction registries

Four registries; do not cross-pollinate formats:

- `dharma_swarm/skills/*.skill.md` — swarm subagent roles, parsed by
  `dharma_swarm/skills.py` (`SkillRegistry`). Yaml-lite frontmatter ONLY
  (flat `key: value`, inline arrays `[a, b]`, one-level nesting for
  `context_weights`; block lists (`- item`) are silently dropped by the
  parser); first body block = keyword-matching description; the rest = the
  agent's system prompt. Also discovered from `~/.dharma/skills/` and
  `.dharma/skills/`.
- `.agents/skills/*/SKILL.md` — testing/verification playbooks for external
  coding agents (Devin etc.).
- `.warp/skills/*/SKILL.md` — Warp/Oz operator skills; each declares a hard
  authority boundary — never widen one to "get something done".
- `dharma_swarm/chetana/claude_code_plugin/` — the chetana memory plugin.

`.claude/*` is gitignored except `.claude/hooks/` and `.claude/settings.json`,
so personal skills/agents do not reach remote checkouts. Root `AGENTS.md` is a
minimal tracked pointer to this file; `docs/AGENTS.md` scopes prose-layer work.

## State directory (~/.dharma/)

Runtime state lives under `~/.dharma/`, never in git. Each path is owned by
the cited module — if a path looks wrong, the module is the truth:

- `~/.dharma/witness/` — gate-check witness JSONL (`telos_gates.py`)
- `~/.dharma/stigmergy/marks.jsonl` — stigmergic marks, append-only (`stigmergy.py`)
- `~/.dharma/evolution/archive.jsonl` — evolution archive (`archaeology_ingestion.py`)
- `~/.dharma/meta/` — self-model + catalytic graph (`context.py`, `catalytic_graph.py`)
- `~/.dharma/organism_memory/mutations.jsonl` — strange-loop mutations (`strange_loop.py`)
- `~/.dharma/traces/` — trace entries (`traces.py`)
