# dharma_swarm — Claude Code Configuration

## Behavioral Rules (Always Enforced)

- Do what has been asked; nothing more, nothing less
- NEVER create files unless they're absolutely necessary for achieving your goal
- ALWAYS prefer editing an existing file to creating a new one
- NEVER proactively create documentation files (*.md) or README files unless explicitly requested
- NEVER save working files, text/mds, or tests to the root folder
- Never continuously check status after spawning a swarm — wait for results
- ALWAYS read a file before editing it
- NEVER commit secrets, credentials, or .env files

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

## Build Governance

Canonical repo-wide build-governance surfaces:

- `dharma_swarm/build_authority.py` — authority matrix for who may create, assign, submit, verify, quarantine, promote, and roll back
- `dharma_swarm/build_registry.py` — append-only canonical record of build intent, tranche scope, runs, decisions, evaluations, incidents, and rollbacks
- `scripts/build_registry_ctl.py` — agent-agnostic CLI for the same registry

These pair with the repo rule surfaces in `README.md`, `CLAUDE.md`, and `AGENTS.md`.
Fast orientation shortcut: `REPO_RULES.md`. Terminal call: `python3 scripts/repo_rules.py`.

Rules for unattended or multi-hour build work:

- Record build intent before substantive write phases.
- Record tranche scope and compatibility mode before schema or contract changes.
- Workers may submit outputs; they do not self-certify.
- Verifier or higher-authority lanes record evaluations, quarantines, incidents, and rollback outcomes.
- Prefer the canonical registry over ad hoc markdown notes for build lineage.

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

See `NAVIGATION.md` for the full module map (500 modules, 12 architectural layers).
See `README.md` for repo map and common commands.
See `foundations/` for the 10-pillar intellectual genome.

## CRITICAL: Read Before Any Code Changes

See [`INTERFACE_MISMATCH_MAP.md`](INTERFACE_MISMATCH_MAP.md) for the complete map of every interface mismatch between modules. **This is the #1 source of runtime failures.** The map documents:
- 3 BLOCKER mismatches that prevent the system from executing any task
- 9 DEGRADED mismatches that silently lose data or crash specific subsystems
- 55 module pairs verified (42 correct, 13 with issues)
- A prioritized **Bootstrap Sequence** of 9 fixes in the order they should be applied

**Rule for all sessions:** Before fixing a bug or adding a feature, check the mismatch map first. If the module pair you're touching has a known mismatch, fix the mismatch as part of your change. Do not add new callers to broken interfaces.

**Rule for all sessions:** After fixing a mismatch, update the map. Remove the entry or mark it RESOLVED with the commit hash.

See [`MODEL_ROUTING_MAP.md`](MODEL_ROUTING_MAP.md) for the complete model routing architecture — all 18 providers, 3 calling surfaces (swarm/CLI/dashboard), 5 inconsistencies between them, the HuggingFace blocker fix, and the minimum viable path to getting one LLM call working. **Any change to how models are called must check this map first.**

See [`CYBERNETIC_LOOP_MAP.md`](CYBERNETIC_LOOP_MAP.md) for every feedback loop's sense→act→evaluate→adapt path, current closure status, and verification commands.

See [`AGENT_IDENTITY_UNIFICATION.md`](AGENT_IDENTITY_UNIFICATION.md) for the spec to unify the 4 agent identity schemas into one canonical model. **Any change to agent creation or identity must follow this spec.**

## Semantic Investigation Discipline (enforced)

Grep is the last resort. In this repo, structural awareness is ALWAYS more valuable than string matching, because the same symbol may live in 5 worktrees with drifted interfaces.

**Before investigating any symbol:**
1. `mcp__contextplus__get_blast_radius("<symbol>")` — count worktree copies and callers.
2. `mcp__contextplus__get_file_skeleton("<path>")` — learn a file's API without reading it end to end.
3. `wiki show <concept>` or `wiki search <term>` — 115-article Karpathy wiki, check if the concept is already codified.
4. Only then `Read` / `Grep` / `Glob`.

**Before editing any hot-path symbol (`swarm.py`, `orchestrate_live.py`, `orchestrator.py`, `frontier_council.py`, `task_board.py`):**
1. Check `get_blast_radius` — decide explicitly whether to patch all worktree copies or note the drift.
2. Consult `INTERFACE_MISMATCH_MAP.md` — if the symbol is listed, fix the mismatch as part of the change.
3. After the patch: trigger `dual-audit` (Claude + Codex) before declaring done.
4. Write the decision and outcome to the memory graph (`mcp__plugin_everything-claude-code_memory__create_entities`).

## Cross-Worktree Ground Truth (verified 2026-04-17)

`_complete_deferred_startup` exists in 5 worktree copies. Likewise most other hot-path symbols. Treat this as the default assumption unless proven otherwise:
- `/Users/dhyana/dharma_swarm/` (primary)
- `/Users/dhyana/dharma_swarm_lf5/` (live fire — this repo)
- `/Users/dhyana/dharma_swarm_lf5_operator/`
- `/Users/dhyana/dharma_swarm_dashboard_skill_worktree/`
- `/Users/dhyana/migration_delta/dharma_swarm_old/`

Rule: when shipping a patch to the hot path, state which worktrees it lands in and which it doesn't. Silent per-worktree drift is the exact rot that `TaskBoard(state_dir=...)` / missing `ConceptGraph` / `TelosGraph.get_by_name` came from (see `INTERFACE_MISMATCH_MAP.md`).

## Runtime Floor (shipped 2026-04-17)

The runtime-floor seam is sealed. These invariants must not regress:

- **SwarmManager.init() is non-blocking** — schedules `_complete_deferred_startup` as a background task, returns so `run_swarm_loop` can start ticking immediately. Tests/tooling that need ready state must call `await swarm.wait_until_bootstrap_ready(timeout=60.0)`.
- **Bootstrap wall-clock budget** at `SwarmManager._read_bootstrap_budget_seconds` — `DHARMA_BOOTSTRAP_BUDGET_S` (default 600s). Exceeded → `bootstrap_failed` + `boot_stall`.
- **Tick wall-clock budget** at `orchestrate_live._invoke_swarm_tick` — `DHARMA_TICK_BUDGET_S` (default min(180, 3×SWARM_TICK)). Exceeded → circuit-breaker failure, loop continues.
- **Liveness watchdog** at `orchestrate_live.run_swarm_liveness_watchdog` — self-declares `boot_stall` in-process, publishes `~/.dharma/meta/swarm_liveness.json` every 20s. If process looks alive but watchdog timestamps are stale, the event loop is pinned.
- `_init_optional_subsystems` sync hotspots at `swarm.py:668,672,677` now use `*_async` wrappers (`discover_async`, `load_all_async`, `build_index_async`). Other sync calls in that function are NOT yet audited — likely culprits for the next wedge include `KernelGuard.load`, `DharmaCorpus.load`, `Organism` init, `Director` init, LanceDB first-connect, `context_agent` builder-notes distillation.

Any work that touches these areas must preserve or strengthen these invariants, never relax them.

## Self-Evolution Trigger for this Repo

Every session that touches dharma_swarm should, on completion:

1. Add/update memory graph entities for any new symbol, incident, or design decision (not per-line details; only reusable signal).
2. If a pattern has now recurred 3+ times — wrap it in a skill or hook. Examples worth watching:
   - "sync call pins event loop inside async" → recurrence → write an `async_safety` skill.
   - "interface drift between worktrees" → recurrence → write a `worktree-drift-check` skill that runs `get_blast_radius` on changed symbols.
   - "bootstrap phase doesn't progress" → watchdog already catches; recurrence means fix the underlying sync blocker.
3. If a wiki article is stale (check `stale_after` in its frontmatter) and you're in its domain — refresh it as part of the work. Don't let the wiki rot.

## Reuse Over Rewrite

Before writing any new orchestration, supervisor, watchdog, evaluator, or gate — grep the repo for existing versions, then query `get_blast_radius` on candidate names. The repo has ~30 subsystems that each tend to re-implement their own version of these primitives; adding a fifth version is the failure mode. See the `reuse > rewrite` rule in `GNANI_LODESTONE.md` if it exists, or use `catalytic` / `consciousness-archaeology` skills to find existing implementations.

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **dharma_swarm_lf5** (27173 symbols, 70724 relationships, 300 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## When Debugging

1. `gitnexus_query({query: "<error or symptom>"})` — find execution flows related to the issue
2. `gitnexus_context({name: "<suspect function>"})` — see all callers, callees, and process participation
3. `READ gitnexus://repo/dharma_swarm_lf5/process/{processName}` — trace the full execution flow step by step
4. For regressions: `gitnexus_detect_changes({scope: "compare", base_ref: "main"})` — see what your branch changed

## When Refactoring

- **Renaming**: MUST use `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` first. Review the preview — graph edits are safe, text_search edits need manual review. Then run with `dry_run: false`.
- **Extracting/Splitting**: MUST run `gitnexus_context({name: "target"})` to see all incoming/outgoing refs, then `gitnexus_impact({target: "target", direction: "upstream"})` to find all external callers before moving code.
- After any refactor: run `gitnexus_detect_changes({scope: "all"})` to verify only expected files changed.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Tools Quick Reference

| Tool | When to use | Command |
|------|-------------|---------|
| `query` | Find code by concept | `gitnexus_query({query: "auth validation"})` |
| `context` | 360-degree view of one symbol | `gitnexus_context({name: "validateUser"})` |
| `impact` | Blast radius before editing | `gitnexus_impact({target: "X", direction: "upstream"})` |
| `detect_changes` | Pre-commit scope check | `gitnexus_detect_changes({scope: "staged"})` |
| `rename` | Safe multi-file rename | `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` |
| `cypher` | Custom graph queries | `gitnexus_cypher({query: "MATCH ..."})` |

## Impact Risk Levels

| Depth | Meaning | Action |
|-------|---------|--------|
| d=1 | WILL BREAK — direct callers/importers | MUST update these |
| d=2 | LIKELY AFFECTED — indirect deps | Should test |
| d=3 | MAY NEED TESTING — transitive | Test if critical path |

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/dharma_swarm_lf5/context` | Codebase overview, check index freshness |
| `gitnexus://repo/dharma_swarm_lf5/clusters` | All functional areas |
| `gitnexus://repo/dharma_swarm_lf5/processes` | All execution flows |
| `gitnexus://repo/dharma_swarm_lf5/process/{name}` | Step-by-step execution trace |

## Self-Check Before Finishing

Before completing any code modification task, verify:
1. `gitnexus_impact` was run for all modified symbols
2. No HIGH/CRITICAL risk warnings were ignored
3. `gitnexus_detect_changes()` confirms changes match expected scope
4. All d=1 (WILL BREAK) dependents were updated

## Keeping the Index Fresh

After committing code changes, the GitNexus index becomes stale. Re-run analyze to update it:

```bash
npx gitnexus analyze
```

If the index previously included embeddings, preserve them by adding `--embeddings`:

```bash
npx gitnexus analyze --embeddings
```

To check whether embeddings exist, inspect `.gitnexus/meta.json` — the `stats.embeddings` field shows the count (0 means no embeddings). **Running analyze without `--embeddings` will delete any previously generated embeddings.**

> Claude Code users: A PostToolUse hook handles this automatically after `git commit` and `git merge`.

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
