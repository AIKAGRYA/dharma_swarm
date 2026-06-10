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

**Active portfolio:** 2 co-equal track(s) (WIP warn 5, max 10). A new project is a new track here, not a violation — model: 1..N co-equal active tracks; typed graph; WIP-limited; surface-owned.

**Spine objectives (each track serves one):**

- `substrate-nativeness` — Substrate nativeness — runtime flows through the ontology/spine, not around it (covered)
- `revenue-external-humans-served` — Revenue & external humans served — value leaves the house and someone acts on it (**no active track**)
- `research-depth` — Research depth — the contemplative-mechanistic bridge (R_V, geometric lens) deepens (**no active track**)

### Runtime Truth Reconciliation — operator-visible truth packets

**Track id:** `runtime-truth-reconciliation-2026-06` · **Status:** ACTIVE · **Owner:** @AmitabhainArunachala
**Serves spine objective:** `substrate-nativeness` · **Verified at:** 2026-06-04 (TTL 14 days)
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

- [code] (blocker) Define the smallest read-only RuntimeTruthPacket contract in the existing operator_core owner.
- [code] (blocker) Render compact runtime truth in make onboard without making onboard an authority surface.
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

**Next items:**

- [code] Confirm NATS transport contact modules are wired and receipted end-to-end.

**Non-goals:**

- Do not introduce Redis or gRPC as part of this track.
- Do not touch the operator_core read-model surfaces owned by the reconciliation lane.
- Do not add a parallel spine-check CI workflow.

**Recently closed tracks:**

- `runtime-truth-spine-2026-06` — Runtime Truth Spine — one invariant, one invocation path, one receipt (SHIPPED, closed 2026-06-04)
- `trace-identity-coverage-2026-05` — Trace Identity Coverage — native propagation and soft coverage findings (SUPERSEDED, closed 2026-05-28)
- `trace-attractor-causal-spine-2026-05` — Trace Attractor Causal Spine — operator-visible trace packets (SHIPPED, closed 2026-05-21)

For machine-readable status, see [`reports/governance/active_track_evidence.md`](reports/governance/active_track_evidence.md) (generated by `scripts/governance/check_track_status.py`).

<!-- ACTIVE_TRACK:END -->

## Reality Check (2026-06-10 — Honest Spine v2; verify before trusting any claim below this line)

This file accreted AI-written claims faster than verification. Until the
instruction-layer consolidation completes, treat claims in this file as one of:

- **VERIFIED** — backed by a receipt, test, or measurement you can re-run.
- **ASPIRATION** — design intent; the code may not do this yet.

Known verified facts that override older prose in this file:

1. **The Transcendence Principle is an unvalidated hypothesis here, not an
   operating fact.** The only completed lift measurement (2026-06-06, run
   `20260606T0900-rerun-openai-ollama-zai` under
   `reports/forge/swarm-evolution-arena-v0-measurement/`)
   was **-0.10** (swarm below best single model; n=3, low power). Literature
   (Self-MoA arXiv:2502.00674, MAST arXiv:2503.13657) predicts exactly this
   for mixed free-model rosters. Do not cite the principle as established.
2. **The evolution archive epoch before 2026-06-10 is untrusted.** ~11,164
   records, 98.96% with no code change, 0% lineage, `status="applied"`
   without application. Do not present archive counts as evolution evidence.
3. **Fitness authority:** only external ACTED receipts via the transfer-aware
   gate may ever set `ArchiveEntry.fitness` (Forge Council invariant). Dense
   benchmark/eval scores are training signal, never fitness.
4. **A fix is not live until the executing worktree contains it.** Check the
   RUNTIME PROVENANCE section of `make onboard`. 84+ worktrees exist; live
   daemons have been observed running 312-dirty-file uncommitted code.
5. **Plan/todo files may contain false "completed" statuses** (verified
   2026-06-10: three falsely-completed items in the debt-audit plan).
   Verify in code before trusting any completion claim, including this file's.

## Behavioral Rules (Always Enforced)

- Do what has been asked; nothing more, nothing less
- NEVER create files unless they're absolutely necessary for achieving your goal
- ALWAYS prefer editing an existing file to creating a new one
- NEVER proactively create documentation files (*.md) or README files unless explicitly requested
- NEVER save working files, text/mds, or tests to the root folder
- Never continuously check status after spawning a swarm — wait for results
- ALWAYS read a file before editing it
- NEVER commit secrets, credentials, or .env files
- BEFORE opening any PR that closes / demotes / adds a BR-id, ALWAYS run `gh pr list --state open --search "BR-NNN"` for each cited BR-id. If another open PR cites the same id, coordinate (rebase / split / close-as-redundant) before pushing. The `pr-collision-detect` workflow is an after-the-fact safety net, not a substitute for this check. See `docs/governance/COHERENCE_DELTA.md` § Pre-flight check.

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

See [`docs/architecture/NAVIGATION.md`](docs/architecture/NAVIGATION.md) for the full module map (500+ modules, 12 architectural layers).
See [`docs/MEGAFILE_INDEX.md`](docs/MEGAFILE_INDEX.md) for the ten highest-system onboarding maps and their current status.
See `README.md` for repo map and common commands.
See `foundations/` for the 10-pillar intellectual genome.

## CRITICAL: Read Before Any Code Changes

**Build-session entrypoint:** Before any build work, read [`docs/governance/BUILD_SESSION_ENTRYPOINT.md`](docs/governance/BUILD_SESSION_ENTRYPOINT.md) and run `make onboard`. The current build **portfolio** (1–N co-equal active tracks) is declared in [`docs/governance/ACTIVE_TRACK.yaml`](docs/governance/ACTIVE_TRACK.yaml) and rendered by `make onboard` — do not name a track here in prose. Substrate-nativeness is currently estimated at ~10–15% per [`reports/audit/end_to_end/000_MASTER_COHERENCE_SYNTHESIS.md`](reports/audit/end_to_end/000_MASTER_COHERENCE_SYNTHESIS.md). When the operator proposes a new project, **open a new track** in the portfolio (`serves:` a spine objective, `owned_surfaces:`, acceptance criteria) up to the WIP limit — a new project is a new track, not a violation of an existing one.

**Highest-system map:** Read [`docs/MEGAFILE_INDEX.md`](docs/MEGAFILE_INDEX.md) before treating any large map as canonical. It points to the Attractor Closure synthesis, live ops dashboard, broken register, and missing slots.

See [`INTERFACE_MISMATCH_MAP.md`](INTERFACE_MISMATCH_MAP.md) for the complete map of every interface mismatch between modules. **This is the #1 source of runtime failures.** The map documents:
- 0 BLOCKER mismatches (all 3 original BLOCKERs resolved)
- 4 DEGRADED mismatches remaining (MM-05 private coupling, NEW-05 guarded, NEW-07/08 partial)
- 55 module pairs verified, 11 resolved, 6 new entries added and fixed
- A prioritized **Bootstrap Sequence** of fixes (most now resolved)

**Rule for all sessions:** Before fixing a bug or adding a feature, check the mismatch map first. If the module pair you're touching has a known mismatch, fix the mismatch as part of your change. Do not add new callers to broken interfaces.

**Rule for all sessions:** After fixing a mismatch, update the map. Remove the entry or mark it RESOLVED with the commit hash.

Historical model-routing notes now live at [`docs/_archive/2026-04/MODEL_ROUTING_MAP.md`](docs/_archive/2026-04/MODEL_ROUTING_MAP.md). Treat that file as stale context only; verify current provider and routing behavior directly against code before changing model calls.

See [`CYBERNETIC_LOOP_MAP.md`](CYBERNETIC_LOOP_MAP.md) for every feedback loop's sense→act→evaluate→adapt path, current closure status, and verification commands.

Historical agent identity notes now live at [`docs/_archive/2026-04/AGENT_IDENTITY_UNIFICATION.md`](docs/_archive/2026-04/AGENT_IDENTITY_UNIFICATION.md). Treat that file as stale context only; verify current agent creation and identity behavior directly against code before changing that surface.
