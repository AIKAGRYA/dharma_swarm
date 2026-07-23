# dharma_swarm — Claude Code Configuration

## Before Anything Else — establish session status

If you have not run `make onboard` this session, do it now — before any
non-trivial Read, Grep, or Edit. It truthfully reports the current checkout and
session verdict.

`make onboard` is session status, not permission to edit and not a complete
model of the running organism:

```bash
make onboard
# or: python3 scripts/governance/agent_onboard.py
```

Use `make organism-status` for the deeper read-only whole-organism projection.
Packet-bound preflight and closeout are required when changed paths match Merge
Master Mike's `HOT_PATH_PATTERNS` in `scripts/runtime/pr_merge_control.py`; they
are optional otherwise. A narrower lane or campaign contract may require them
more broadly. Before editing work that requires a packet, bind its baseline and
scope with `make agent-build-preflight PACKET=<path>`, then run packet-bound
closeout afterward. This file owns behaviour;
`docs/governance/BUILD_SESSION_ENTRYPOINT.md` owns the command boundaries.

**What an onboard run does and does not prove:** READY is evidence only about
the local session evaluation. It is NOT proof of edit admission, whole-organism
liveness, CI admission, merge approval, or deployment readiness. The portfolio
shown by onboarding is declared intent from `ACTIVE_TRACK.yaml`, not runtime
truth. Never fill a missing observation from this file or another prose copy.

The packet-scope check proves committed-range packet scope only; it does not
prove local preflight or closeout, packet gate execution, human approval, or
merge authority.

<!-- ACTIVE_TRACK:START -->

<!-- GENERATED — do not hand-edit.
     source-of-truth: docs/governance/ACTIVE_TRACK.yaml
     render: python3 scripts/governance/render_active_track_includes.py
     check:  python3 scripts/governance/render_active_track_includes.py --check
     checked by: .github/workflows/active-track.yml, make docops-integrity,
                 tests/test_active_track_governance.py
     newest track verified_at in source: 2026-07-17 -->

**Active portfolio — declared intent only:** 10 co-equal track(s) (WIP warn 8, max 10; model: 1..N co-equal active tracks; typed graph; WIP-limited; surface-owned). This stamped digest carries track identity and surface ownership, NOT runtime truth and NOT full track detail (descriptions, next-items, non-goals stay in the YAML). Declared intent comes from `docs/governance/ACTIVE_TRACK.yaml`; evaluate it with `python3 scripts/governance/check_track_status.py`. Never answer runtime or liveness questions from this block or another prose copy.

**Spine objectives:** `substrate-nativeness`, `revenue-external-humans-served`, `research-depth` (each covered by at least one active track)

- **`loop-closure-2026-06`** — Cybernetic Loop Closure — wire all 13 loops with receipted closure checks (ACTIVE, serves `substrate-nativeness`, verified 2026-07-11, open blocker items: 3)
  - owns: reports/loop_closure/**, CYBERNETIC_LOOP_MAP.md, docs/plans/LOOP1_CLOSURE_SPEC_2026-07-11.md, scripts/governance/loop1_consumption_check.py, tests/test_loop_supervisor_tristate.py, tests/test_loop1_consumption.py, tests/test_loop1_consumption_check.py
- **`orchestration-arena-v1-2026-06`** — Orchestration Arena v1 — frozen hermetic fitness + zero-weight orchestrator + DPI (ACTIVE, serves `substrate-nativeness`, verified 2026-07-17, open blocker items: 1)
  - owns: dharma_swarm/coordination/**, dharma_swarm/council/**, scripts/governance/arena_truth_report.py, reports/governance/arena/**, tests/test_arena_v1.py, tests/test_dpi.py, tests/test_orchestration_genome.py, tests/test_orchestrator_v1.py, tests/test_council_profiles.py, tests/test_coordination_closure_checks.py, tests/test_arena_truth_report.py
- **`merge-master-mike-d4-2026-06`** — Merge Master Mike — D4 persistent always-on merge agent (ACTIVE, serves `substrate-nativeness`, verified 2026-07-16, open blocker items: 1)
  - owns: scripts/runtime/pr_merge_control.py, scripts/runtime/merge_master_mike_daemon.py, .github/workflows/automerge.yml, .github/workflows/codex-mention-router.yml, .github/workflows/merge-master-mike-backlog.yml, tests/test_merge_master_mike_daemon.py, tests/test_pr_merge_control.py, tests/test_pr_merge_control_github_reviews.py
- **`organism-rewire-2026-07`** — Organism Rewire — dormant organs to production, spine standing-on, external gradients (ACTIVE, serves `substrate-nativeness`, verified 2026-07-02, open blocker items: 2)
  - owns: tools/world_scout_go/**, tools/world_signal_ingestor_go/**, tools/github_ingestor_go/**, tools/evidence_ingestor_go/**, dharma_swarm/world_radar/**, scripts/runtime/github_ingestor_runner.py, tests/test_github_ingestor_runner.py, tests/test_go_evidence_ingestor_bridge.py, tests/test_go_github_ingestor_bridge.py, tests/test_go_world_signal_bridge.py, tests/test_go_receipt_identity_verify.py, tests/test_go_adapter_contracts.py, tests/test_world_radar_go_bridge.py, dharma_swarm/organism.py, dharma_swarm/strange_loop.py, dharma_swarm/diversity_archive.py, dharma_swarm/archive.py, docker-compose.yml, Dockerfile.swarm
- **`dharmagraph-engine-2026-07`** — DharmaGraph — sovereign durable graph runtime consolidation (ACTIVE, serves `substrate-nativeness`, verified 2026-07-05, open blocker items: 1)
  - owns: dharma_swarm/graph/**, dharma_swarm/workflow.py, dharma_swarm/topology_genome.py, dharma_swarm/checkpoint.py, dharma_swarm/swarm.py, dharma_swarm/orchestrator.py, pyproject.toml, .github/workflows/langgraph-oracle.yml, tests/test_workflow.py, tests/test_topology_execution.py, tests/test_checkpoint.py, tests/test_graph_checkpoint.py, tests/test_graph_reconciler.py, tests/test_graph_durable_invoker.py, tests/test_langgraph_differential_oracle.py, tests/test_graph_neutral_langgraph_oracle.py, tests/test_graph_pregel_properties.py, docs/plans/DHARMAGRAPH_PHASED_SPEC_2026-07-05.md, docs/plans/handoffs/DHARMAGRAPH_HANDOFF_DEVIN.md, docs/plans/handoffs/DHARMAGRAPH_HANDOFF_CLAUDE.md, scripts/governance/dharmagraph_parity_gauntlet.py, tests/oracle_support/dharmagraph_gauntlet.py, tests/test_dharmagraph_parity_gauntlet.py, docs/langgraph_parity/DHARMAGRAPH_PARITY_GAUNTLET_RUBRIC_V1.json, docs/langgraph_parity/DHARMAGRAPH_PARITY_GAUNTLET_RUBRIC_V2.json, docs/langgraph_parity/DHARMAGRAPH_PARITY_GAUNTLET_RUBRIC_V3.json, docs/langgraph_parity/DHARMAGRAPH_JUDGE_RATIFICATIONS_V1.json, reports/governance/dharmagraph_parity/**, docs/plans/DHARMAGRAPH_ASCENT_SPEC_2026-07-17.md, docs/plans/handoffs/DHARMAGRAPH_ASCENT_*.md, docs/plans/DHARMAGRAPH_FRONTIER_DOSSIER_*.md, docs/governance/CAMPAIGN_KERNEL.md, tests/oracle_support/scenarios.py, tests/oracle_support/outcomes.py
- **`helm-worldclass-terminal-2026-06`** — Helm — world-class operator terminal (Bun+Ink TUI) (ACTIVE, serves `substrate-nativeness`, verified 2026-07-07, open blocker items: 1)
  - owns: terminal/**
- **`sovereign-safety-tcb-2026-07`** — Sovereign Safety TCB — fail-closed evolution, graded anti-slop, verified kernel, self-gating portfolio (ACTIVE, serves `substrate-nativeness`, verified 2026-07-07, open blocker items: 1)
  - owns: dharma_swarm/evolution_safety.py, scripts/governance/check_claim_evidence_binding.py, scripts/governance/pramana_probe.py, scripts/governance/branch_janitor.py, scripts/governance/verify_corral_findings.py, scripts/governance/hygiene/**, docs/governance/hygiene/patterns/AI-M1.yaml, packages/telos-kernel/**, packages/titanium-verify/**, .github/workflows/pudgala-rigor.yml, .github/workflows/pramana-probe.yml, .github/workflows/kernel-titanium-verify.yml, .github/workflows/kernel-tests.yml, .github/workflows/branch-janitor.yml, tests/test_evolution_safety.py, tests/test_claim_evidence_binding.py, tests/test_pramana_probe.py, tests/test_pramana.py, tests/test_branch_janitor.py, tests/test_verify_corral_findings.py
- **`hyperbolic-time-chamber-2026-07`** — Hyperbolic Time Chamber — afferent ingest, gym battery, Frontier Ledger (ACTIVE, serves `research-depth`, verified 2026-07-07, open blocker items: 1)
  - owns: docs/vision_maps/MASTER_2026-07-07_hyperbolic_time_chamber.md, docs/plans/HYPERBOLIC_CHAMBER_PHASE0_DOSSIER_2026-07-07.md, docs/plans/HYPERBOLIC_CHAMBER_ELEVATION_SPEC_2026-07-07.md, docs/plans/INWARD_ASCENT_PHASE0_DOSSIER_2026-07-07.md, scripts/governance/inward_ascent_baseline.py, scripts/governance/frontier_ledger.py, scripts/governance/transcendence_ledger.py, dharma_swarm/chamber/**, tests/test_chamber_traces.py, tests/test_chamber_gym_git_history.py, tests/test_chamber_daily_delta.py, tests/test_chamber_predictions.py, tests/test_chamber_sandbox.py, tests/test_chamber_ledger_history.py, tests/test_transcendence_ledger.py, reports/governance/inward_ascent/**, reports/governance/chamber/**
- **`repository-titanium-hardening-2026-07`** — Titanium-grade repository hardening — truthful verification and clean-room closure (ACTIVE, serves `substrate-nativeness`, verified 2026-07-17, open blocker items: 13)
  - owns: Makefile, Dockerfile, .github/workflows/hermetic.yml, .github/workflows/tests.yml, .github/workflows/ci-parity.yml, .github/workflows/docops.yml, .github/workflows/docops-reconcile-main.yml, .github/workflows/pr-dedupe.yml, .github/workflows/bot-pr-limit.yml, .github/workflows/a2a-agni-live-contact.yml, docs/governance/CI_TRUTH_CONTRACT.json, scripts/governance/ci_parity_manifest.json, scripts/governance/check_ci_parity.py, scripts/runtime/ci_truth.py, scripts/governance/run_semgrep_with_ca.sh, scripts/uplift_guards/shakti_warrant_guard.py, scripts/uplift_guards/run_pre_commit.py, scripts/governance/check_shakti_warrant.py, scripts/governance/check_nats_substrate_contract.py, scripts/governance/check_nats_live_production_evidence.py, scripts/governance/run_nats_live_production_matrix.py, scripts/docops/**, dharma_swarm/build_engine.py, dharma_swarm/autonomous_agent.py, dharma_swarm/diff_applier.py, dharma_swarm/sandbox.py, docs/docops/AUTO_INVENTORY.md, api/main.py, tests/test_api_auth.py, tests/test_verify_api.py, tests/test_bootstrap_contract.py, tests/test_verifier_selfcheck_contract.py, tests/test_semgrep_wrapper.py, tests/test_uplift_guard_subprocess.py, tests/test_fast_suite_isolation.py, tests/test_diff_applier.py, tests/test_sandbox.py, tests/test_nats_verification_split.py, tests/test_nats_substrate_contract.py, tests/test_nats_live_production_evidence.py, tests/test_nats_live_contact.py, tests/governance/test_ci_parity_guard.py, tests/test_ci_truth.py, tests/test_docops_integrity.py, tests/test_docops_reconcile_workflow.py, tests/test_pr_dedupe_workflow.py, tests/test_polyglot_ci_contract.py, tests/test_hermetic_supply_chain.py, docs/plans/TITANIUM_GRADE_REPOSITORY_HARDENING_2026-07-10.md, docs/prompts/TITANIUM_HARDENING_CAMPAIGN_EXECUTOR_2026-07-17.md, reports/governance/titanium/**, dashboard/src/lib/operatorCoherence.ts, dashboard/src/components/operator-coherence/v2/cockpitV2Model.ts, dashboard/src/components/operator-coherence/v2/CockpitV2Board.tsx, dashboard/src/components/operator-coherence/v2/cockpitV2Model.test.ts
- **`darshan-publication-2026-07`** — Darshan — publication venture cell (multi-disciplinary voice of clear seeing) (ACTIVE, serves `revenue-external-humans-served`, verified 2026-07-12, open blocker items: 2)
  - owns: docs/plans/DARSHAN_CHARTER_2026-07-12.md, reports/darshan/**, reports/tam/**

Before editing any file, check it against the `owns:` globs above — a surface owned by a track you are not serving is off-limits except through that track's own next-items. Full track detail: `docs/governance/ACTIVE_TRACK.yaml`.

**Recently closed tracks:** `company-builder-parity-2026-07` (RETIRED, closed 2026-07-17) · `onboard-one-door-2026-07` (RETIRED, closed 2026-07-17) · `onboard-session-status-2026-07` (SHIPPED, closed 2026-07-17)

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
- **Citation-or-silence (operator-ratified 2026-07-10).** Every factual claim an agent writes — spec, PR body, report, conclusion — carries a `file:line` citation or a runnable command. Uncited claims carry zero weight regardless of fluency, confidence, or how many LLM passes produced them; verify by independent re-derivation from the source, never by adding polish. Prefer uncharmable mechanical checks (`make substrate-audit`, import-provenance, DocOps counts, ratcheted baselines) over human vigilance: counts only ratchet down, and regressions trip gates, not reviewer attention.

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

# Static analysis / repo inventory (live module counts come from here)
python3 scripts/repo_xray.py

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

Runtime state lives under `~/.dharma/`, never in git. Each path below is owned
by the cited module — if a path looks wrong, the module is the truth:

- `~/.dharma/witness/` — gate-check witness JSONL (`telos_gates.py`)
- `~/.dharma/stigmergy/marks.jsonl` — stigmergic marks, append-only (`stigmergy.py`)
- `~/.dharma/evolution/archive.jsonl` — evolution archive (`archaeology_ingestion.py`)
- `~/.dharma/meta/recognition_seed.md` — system self-model (`context.py`)
- `~/.dharma/meta/catalytic_graph.json` — autocatalytic graph (`catalytic_graph.py`)
- `~/.dharma/organism_memory/mutations.jsonl` — strange-loop mutations (`strange_loop.py`)
- `~/.dharma/traces/` — trace entries (`traces.py`)

## Navigation

See [`docs/architecture/NAVIGATION.md`](docs/architecture/NAVIGATION.md) for the full module map and layer structure (module counts go stale in prose — `python3 scripts/repo_xray.py` prints the live count).
See [`docs/MEGAFILE_INDEX.md`](docs/MEGAFILE_INDEX.md) for the ten highest-system onboarding maps and their current status.
See `README.md` for repo map and common commands.
See `foundations/` for the 10-pillar intellectual genome.

### Skills & Agent Role Registries (who reads which instruction files)

Four separate registries; do not cross-pollinate formats:

- `dharma_swarm/skills/*.skill.md` — **swarm subagent role definitions**, parsed by `dharma_swarm/skills.py` (`SkillRegistry`). Format contract: yaml-lite frontmatter ONLY (flat `key: value`, inline arrays `[a, b]`, one-level nesting for `context_weights`; block lists (`- item`) are silently dropped by the parser); first body block = description used for keyword matching; everything after = the agent's system prompt. Also discovered from `~/.dharma/skills/` and `.dharma/skills/`.
- `.agents/skills/*/SKILL.md` — testing/verification playbooks for external coding agents (Devin etc.). Standard `name`/`description` frontmatter.
- `.warp/skills/*/SKILL.md` — Warp/Oz operator skills (janitor, verifier, roast council, session-close ledger). Each declares a hard authority boundary; never widen one to "get something done".
- `dharma_swarm/chetana/claude_code_plugin/` — the chetana memory plugin (skill + slash commands + hooks).

**Gotcha:** `.claude/*` is gitignored except for `.claude/hooks/` and
`.claude/settings.json`; personal `.claude/skills/` and `.claude/agents/` do
not reach remote/cloud checkouts. Root `AGENTS.md` is a tracked, deliberately
minimal entrypoint that defers to this file. `docs/AGENTS.md` separately scopes
prose-layer work.

## CRITICAL: Read Before Any Code Changes

**Build-session entrypoint:** Before any build work, read [`docs/governance/BUILD_SESSION_ENTRYPOINT.md`](docs/governance/BUILD_SESSION_ENTRYPOINT.md) and run `make onboard`. The current build **portfolio** (1–N co-equal active tracks) is declared in [`docs/governance/ACTIVE_TRACK.yaml`](docs/governance/ACTIVE_TRACK.yaml) and rendered by `make onboard` — do not name a track here in prose. Substrate-nativeness is a measured number, not a prose constant — run `python3 scripts/governance/spine_bypass_report.py` for the live dispatch-site measure instead of citing any doc's frozen percentage. When the operator proposes a new project, **open a new track** in the portfolio (`serves:` a spine objective, `owned_surfaces:`, acceptance criteria) up to the WIP limit — a new project is a new track, not a violation of an existing one.

**Highest-system map:** Read [`docs/MEGAFILE_INDEX.md`](docs/MEGAFILE_INDEX.md) before treating any large map as canonical. It points to the Attractor Closure synthesis, live ops dashboard, broken register, and missing slots.

See [`INTERFACE_MISMATCH_MAP.md`](INTERFACE_MISMATCH_MAP.md) for the complete map of every interface mismatch between modules. **This is the #1 source of runtime failures.** Live BLOCKER/DEGRADED status lives in the map itself — never freeze a count or dated snapshot here (this section rotted twice by carrying one). Read the map for the current tally; cite nothing from memory.

**Rule for all sessions:** Before fixing a bug or adding a feature, check the mismatch map first. If the module pair you're touching has a known mismatch, fix the mismatch as part of your change. Do not add new callers to broken interfaces.

**Rule for all sessions:** After fixing a mismatch, update the map. Remove the entry or mark it RESOLVED with the commit hash.

Historical model-routing notes now live at [`docs/_archive/2026-04/MODEL_ROUTING_MAP.md`](docs/_archive/2026-04/MODEL_ROUTING_MAP.md). Treat that file as stale context only; verify current provider and routing behavior directly against code before changing model calls.

See [`CYBERNETIC_LOOP_MAP.md`](CYBERNETIC_LOOP_MAP.md) for every feedback loop's sense→act→evaluate→adapt path, current closure status, and verification commands.

Before writing or debugging any code that runs a `Proposal` through `DarwinEngine.gate_check` / the telos gatekeeper (evolution, self-mod, `mutation`/`sealed_packet` proposals, or tests thereof), read [`docs/architecture/EVOLUTION_PROPOSAL_GATE_CONTRACT.md`](docs/architecture/EVOLUTION_PROPOSAL_GATE_CONTRACT.md). WS4 hard-rejects a self-mod proposal on any Tier-C advisory `REVIEW`, so a proposal must clear the whole Tier-C battery at once. Use `tests/evolution_gate_helpers.py` to build passing proposals and `scripts/diagnostics/proposal_gate_probe.py` to map which gates a candidate trips (BR-021).

Historical agent identity notes now live at [`docs/_archive/2026-04/AGENT_IDENTITY_UNIFICATION.md`](docs/_archive/2026-04/AGENT_IDENTITY_UNIFICATION.md). Treat that file as stale context only; verify current agent creation and identity behavior directly against code before changing that surface.
