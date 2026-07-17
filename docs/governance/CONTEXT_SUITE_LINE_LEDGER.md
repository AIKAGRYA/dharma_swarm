# Context Suite Line Ledger — 2026-07-10

**Role:** witness (per `docs/AGENTS.md` document types) — captured evidence for the
2026-07-10 context-suite rewrite. Line numbers refer to `CLAUDE.md` and `docs/AGENTS.md`
at commit `212df1a` (pre-rewrite). This ledger is the justification record for every
deletion/conversion in that rewrite; it does not own any live fact.

**Classes:** `behavior` (timeless rule/doctrine) · `generated` (renderer-owned, CI-checked)
· `frozen` (state embedded in prose, no check) · `pointer` (reference + live-render command)
· `dead` (broken/unreachable).
**Fates:** KEEP · FIX · COMPACT (regenerate smaller with stamp) · POINTERIZE · DELETE.

**Why now (probe evidence, 2026-07):** a four-agent probe found `make onboard`'s ACTIVE
PORTFOLIO section renders empty in fresh clones (evidence JSON is untracked), and agents
silently answered portfolio questions from CLAUDE.md's full prose copy while claiming to
answer from the gate. Reproduced in this session: fresh clone → onboard prints
"WARNING: no active_track_evidence.json found." The full-body prose copy masks gate
failure; the fix here is a compact stamped projection + content assertions
(`tests/test_context_suite.py`). The onboard script itself is owned by a separate lane
and is untouched here.

## CLAUDE.md (641 lines @ 212df1a)

| Lines | Class | Verdict + evidence | Fate |
|---|---|---|---|
| 1–17 | behavior + pointer | onboard gate exists: `Makefile:437`; `scripts/governance/agent_onboard.py` present | KEEP; add the exit-0 caveat (what onboard output does NOT guarantee) |
| 18–454 | generated | `ACTIVE_TRACK:START/END` block, renderer `scripts/governance/render_active_track_includes.py`, `--check` in CI (`.github/workflows/active-track.yml:86`) — in sync with the YAML, but the FULL track bodies (descriptions, next-items, non-goals) are the probe's leak channel, and the block carried no rendered-at stamp | COMPACT: renderer now emits a stamped digest (ids, status, serves, verified_at, blocker count, owned surfaces); full detail stays in `docs/governance/ACTIVE_TRACK.yaml` |
| 456–466 | behavior | generic always-enforced rules (no new files, read-before-edit, no secrets, grep/glob not bash-find, no swarm status-polling) | KEEP |
| 467 | behavior | BR-id PR pre-flight: `.github/workflows/pr-collision-detect.yml` exists; `docs/governance/COHERENCE_DELTA.md:101` § Pre-flight check | KEEP |
| 468 | behavior | worktree budget formula matches `scripts/governance/check_worktree_budget.py:103`; compost path referenced by `scripts/governance/worktree_cleanup_2026-06-10.sh:10` | KEEP |
| 469 | behavior + pointer | ADR exists: `docs/architecture/ADRs/ADR-008-ontology-api-name-grammar.md` | KEEP |
| 470 | behavior | receipt globs confirmed in `.gitignore` | KEEP |
| 472–480 | behavior | file-organization rules | KEEP |
| 482–489 | behavior | `pyproject.toml`: `requires-python = ">=3.11"`, `pydantic>=2.0`, `asyncio_mode = "auto"` | KEEP |
| 491–502 | pointer | Key Abstractions all verified: `organism.py:117`, `swarm.py:109` SwarmManager, `evolution.py:271` DarwinEngine, `cascade.py:95` LoopEngine ("F(S) = S" `cascade.py:1`), `dharma_kernel.py:29-79` exactly 25 MetaPrinciple members + SHA-256 at `:355-361`, `memory_kernel/__init__.py`, `telos_gates.py:233` + gates `:247-252`, `stigmergy.py:96`, `catalytic_graph.py:25` (tarjan_scc `:113`), `strange_loop.py:107` | KEEP |
| 504–537 | behavior | Transcendence Principle doctrine; code pointers verified: `archive.py:354` MAPElitesGrid + `archive.py:530` EvolutionArchive (used by `evolution.py:321`), `diversity_archive.py:1-6` deprecated shim, `coordination/genome.py:83-242` arena variant, `orchestrator.py:177-190` + `models.py:99-103` topologies, `vsm_channels.py:1-17`, `ginko_brier.py:1-6`, `signal_bus.py:52`, `handoff.py:27-66` | KEEP (doctrine is not deletable for convenience) |
| 538 | dead | `spec-forge/transcendence-multi-agent-coordination/research/` does NOT exist (spec-forge/ has consciousness-computing, living-agent-kernel, micro-saas-research, self-evolving-organism only); survived docops because bare dir paths don't match `CODE_PATH_RE` | DELETE |
| 540–554, 558–563 | pointer/behavior | `make test-fast` `Makefile:142` (`--timeout=10 -x`), `make test` `Makefile:139` (excludes slow/docker/network), dashboard lint `dashboard/package.json:9` | KEEP |
| 555–556 | dead | `python3 xray.py` — no root `xray.py`; library lives at `dharma_swarm/xray.py` (no `__main__`), runnable inventory is `scripts/repo_xray.py:306` | FIX → `python3 scripts/repo_xray.py` |
| 565–584 | pointer | `dgc` entry `pyproject.toml` → `dharma_swarm/dgc_cli.py` (status `:269`, health `:532`, stigmergy `:715`, hum `:720`, evolve trend `:670`, dharma status `:705`); `api/main.py:264` FastAPI app, port 8420 `api/main.py:171`; `run_operator.sh` at root | KEEP |
| 586–591 | behavior | security rules | KEEP |
| 593–601 | frozen | all 7 `~/.dharma/` paths verified in code TODAY (`telos_gates.py:66`, `stigmergy.py:93,113`, `archaeology_ingestion.py:145`, `context.py:1316`, `catalytic_graph.py:39`, `strange_loop.py:348-350`, `traces.py:75`) — but no check catches a future move | KEEP with owner-module citations inline (the citation IS the re-verification command: read the owning module) |
| 603–608 | frozen + pointer | "770+ modules, 12 layers" understates reality (995 via `git ls-files 'dharma_swarm/*.py'`; `scripts/repo_xray.py` prints 995); NAVIGATION.md itself carries a staleness banner | FIX: drop the number, keep pointer + live command |
| 610–619 | behavior + pointer | four registries verified: `skills.py:192` SkillRegistry, yaml-lite parser `skills.py:71-105` (block lists dropped: no `:` → skipped), discovery incl. `~/.dharma/skills/` `.dharma/skills/` `skills.py:185-189`; `.claude/*` gitignore exceptions confirmed | KEEP; ADD the root-`/AGENTS.md`-is-gitignored gotcha (`.gitignore:99`) — README.md:82 pointed agents at a file absent from every fresh clone |
| 621–626 | behavior + pointer | entrypoint/megafile pointers exist; spine measure command `scripts/governance/spine_bypass_report.py` exists | KEEP |
| 627–633 | behavior + pointer | `INTERFACE_MISMATCH_MAP.md` exists at root; rules kept; the twice-rotted-snapshot history compressed to one line (the lesson, not the anecdote) | KEEP (tightened) |
| 635–641 | pointer | `CYBERNETIC_LOOP_MAP.md`, `docs/architecture/EVOLUTION_PROPOSAL_GATE_CONTRACT.md` (WS4 hard-reject confirmed at its lines 6–8), `tests/evolution_gate_helpers.py`, `scripts/diagnostics/proposal_gate_probe.py`, both `docs/_archive/2026-04/` files exist | KEEP |

## docs/AGENTS.md (89 lines @ 212df1a)

| Lines | Class | Verdict + evidence | Fate |
|---|---|---|---|
| 1–3 | behavior | scope statement (prose layer) | KEEP; sharpen consumer scoping vs CLAUDE.md |
| 5–17 | behavior (duplicate) | onboard gate duplicated from CLAUDE.md §1 | POINTERIZE (CLAUDE.md owns the gate) |
| 19–21 | pointer (duplicate) | MemoryKernel front-door duplicated from CLAUDE.md Key Abstractions | POINTERIZE |
| 23–52 | behavior | authority model + document types; owner `docs/governance/CANONICAL_DOC_STACK.md` exists | KEEP (owned here, not duplicated) |
| 54–74 | behavior | cleanup rules + deprecation format | KEEP |
| 76–89 | behavior | A2A semantic-experiment rules | KEEP |

## Adjacent fixes in the same pass

- `README.md:82` pointed at root `AGENTS.md` — absent in every fresh clone
  (`.gitignore:99`). FIXED to name the tracked files.
- `scripts/governance/agent_onboard.py:1567` has the same stale pointer — owned by the
  separate onboard-fix lane; NOT touched here (recorded for that lane).
- `Makefile` `docops-integrity` target now also runs the renderer `--check`, so the
  staleness test ("generated block matches renderer output") fails locally, not only in
  `active-track.yml` CI.
- `tests/test_context_suite.py` (new) encodes the probe-regression quiz as content
  assertions: stamp present, full-body leak copy gone, exit-0 caveat present,
  ownership-lookup instruction present, docs/AGENTS.md scoped.

## Token accounting (chars/4)

Measured 2026-07-10 with the command in CONTEXT_SUITE_MAP.md §Re-measure.

| File | Before (tokens / lines) | After (tokens / lines) |
|---|---|---|
| `CLAUDE.md` | 14,182 / 641 | 5,997 / 251 (−58%) |
| `docs/AGENTS.md` | 921 / 89 | 871 / 79 |
| `docs/governance/BUILD_SESSION_ENTRYPOINT.md` | 12,245 / 536 | 968 / 86 (stable Session Entry Contract, 2026-07-17) |
| `docs/governance/SOVEREIGN_MANIFEST.md` | 18,062 / 902 | ~8,560 / 448 (compact block + deduped count table) |
