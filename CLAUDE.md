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

**Active portfolio:** 4 co-equal track(s) (WIP warn 5, max 10). A new project is a new track here, not a violation — model: 1..N co-equal active tracks; typed graph; WIP-limited; surface-owned.

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

**Recently closed tracks:**

- `runtime-truth-reconciliation-2026-06` — Runtime Truth Reconciliation - operator-visible truth packets (SHIPPED, closed 2026-06-30)
- `runtime-truth-nats-2026-06` — Runtime Truth NATS - internal live transport for A2A dispatch (SHIPPED, closed 2026-06-30)
- `truth-graph-platform-2026-06` — Truth Graph Platform v1 - repo context + receipted A2A presence (SHIPPED, closed 2026-06-30)

For machine-readable status, see [`reports/governance/active_track_evidence.md`](reports/governance/active_track_evidence.md) (generated by `scripts/governance/check_track_status.py`).

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
- **TelosGatekeeper** (`dharma_swarm/telos_gates.py`): 11 dharmic safety gates.
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
1. **Diversity of competence** — agents must have genuinely different capabilities, trained on different data, using different approaches. Same model prompted differently may NOT suffice. Different model families, different specializations, different error profiles. Measured via MAP-Elites behavioral diversity (`diversity_archive.py`).
2. **Error decorrelation** — agent errors must be independent. If agents fail on the same inputs in the same way, aggregation provides no benefit. Correlated errors compound; decorrelated errors cancel. This is arithmetic: `E_ensemble = E_mean - E_diversity` (Krogh-Vedelsby). The diversity term directly subtracts from ensemble error.
3. **Quality aggregation** — the mechanism that combines agent outputs must amplify agreement and suppress noise. Temperature concentration, weighted voting, Brier-scored selection, telos-gated filtering. Bad aggregation (simple averaging, loudest-voice-wins) kills the signal.

**The critical tradeoff**: Governance (Beer's VSM: coordination, control, identity) is necessary for sustained operation. But governance can reduce diversity through standardization, shared protocols, convergence pressure. **Every governance mechanism must be evaluated against its diversity cost.** Light coordination (System 2 damping) preserves diversity. Heavy control (System 3 mandates) may destroy it.

**What this means for every session**:
- When adding agents: maximize behavioral diversity, not count. The 5th agent from a different model family adds more than the 50th agent from the same family.
- When designing orchestration: route by specialty (skill selection), aggregate by quality weighting (skill denoising), recombine in cascade loops (skill generalization).
- When evolving agents: DarwinEngine MUST preserve diversity. Pure fitness pressure → convergence → transcendence death. Use diversity-preserving selection (MAP-Elites in `diversity_archive.py`).
- When measuring success: track the Krogh-Vedelsby diversity term, not just individual agent fitness. If diversity is falling, transcendence is dying regardless of individual performance.
- When governing: telos gates and VSM channels are necessary but must be LIGHT. System 2 (damping) > System 3 (mandates). The governance cost of a gate is measured in diversity loss.

**Where this lives in the codebase**:
- `diversity_archive.py` — MAP-Elites quality-diversity optimization
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

# Smoke test (fast subset)
make test-smoke

# Full test suite
make test-all

# Static analysis / repo inventory
make xray

# Dashboard lint
make dashboard-lint
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

See [`docs/architecture/NAVIGATION.md`](docs/architecture/NAVIGATION.md) for the full module map (770+ modules under `dharma_swarm/`, 12 architectural layers; run `make xray` for the live count).
See [`docs/MEGAFILE_INDEX.md`](docs/MEGAFILE_INDEX.md) for the ten highest-system onboarding maps and their current status.
See `README.md` for repo map and common commands.
See `foundations/` for the 10-pillar intellectual genome.

## CRITICAL: Read Before Any Code Changes

**Build-session entrypoint:** Before any build work, read [`docs/governance/BUILD_SESSION_ENTRYPOINT.md`](docs/governance/BUILD_SESSION_ENTRYPOINT.md) and run `make onboard`. The current build **portfolio** (1–N co-equal active tracks) is declared in [`docs/governance/ACTIVE_TRACK.yaml`](docs/governance/ACTIVE_TRACK.yaml) and rendered by `make onboard` — do not name a track here in prose. Substrate-nativeness is a measured number, not a prose constant — run `python3 scripts/governance/spine_bypass_report.py` for the live dispatch-site measure instead of citing any doc's frozen percentage. When the operator proposes a new project, **open a new track** in the portfolio (`serves:` a spine objective, `owned_surfaces:`, acceptance criteria) up to the WIP limit — a new project is a new track, not a violation of an existing one.

**Highest-system map:** Read [`docs/MEGAFILE_INDEX.md`](docs/MEGAFILE_INDEX.md) before treating any large map as canonical. It points to the Attractor Closure synthesis, live ops dashboard, broken register, and missing slots.

See [`INTERFACE_MISMATCH_MAP.md`](INTERFACE_MISMATCH_MAP.md) for the complete map of every interface mismatch between modules. **This is the #1 source of runtime failures.** The map documents:
- **Live BLOCKER/DEGRADED status lives in the map itself — do not freeze a count here** (that duplication is exactly how this section rotted). Read `INTERFACE_MISMATCH_MAP.md` for the current tally. As of 2026-06-22 the recent `NEW-14` blocker (world-model loop ↔ `WorldModelAgent` API mismatch, which crashed the loop on every daemon boot) has a fix in flight; the 3 original BLOCKERs are resolved; `NEW-05` (guarded) and `NEW-07/08` (partial+) remain DEGRADED.
- A prioritized **Bootstrap Sequence** of fixes (most now resolved)

**Rule for all sessions:** Before fixing a bug or adding a feature, check the mismatch map first. If the module pair you're touching has a known mismatch, fix the mismatch as part of your change. Do not add new callers to broken interfaces.

**Rule for all sessions:** After fixing a mismatch, update the map. Remove the entry or mark it RESOLVED with the commit hash.

Historical model-routing notes now live at [`docs/_archive/2026-04/MODEL_ROUTING_MAP.md`](docs/_archive/2026-04/MODEL_ROUTING_MAP.md). Treat that file as stale context only; verify current provider and routing behavior directly against code before changing model calls.

See [`CYBERNETIC_LOOP_MAP.md`](CYBERNETIC_LOOP_MAP.md) for every feedback loop's sense→act→evaluate→adapt path, current closure status, and verification commands.

Before writing or debugging any code that runs a `Proposal` through `DarwinEngine.gate_check` / the telos gatekeeper (evolution, self-mod, `mutation`/`sealed_packet` proposals, or tests thereof), read [`docs/architecture/EVOLUTION_PROPOSAL_GATE_CONTRACT.md`](docs/architecture/EVOLUTION_PROPOSAL_GATE_CONTRACT.md). WS4 hard-rejects a self-mod proposal on any Tier-C advisory `REVIEW`, so a proposal must clear the whole Tier-C battery at once. Use `tests/evolution_gate_helpers.py` to build passing proposals and `scripts/diagnostics/proposal_gate_probe.py` to map which gates a candidate trips (BR-021).

Historical agent identity notes now live at [`docs/_archive/2026-04/AGENT_IDENTITY_UNIFICATION.md`](docs/_archive/2026-04/AGENT_IDENTITY_UNIFICATION.md). Treat that file as stale context only; verify current agent creation and identity behavior directly against code before changing that surface.
