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
     newest track verified_at in source: 2026-08-27 -->

**Active portfolio — declared intent only:** 4 co-equal track(s) (WIP warn 5, max 10; scoped WIP: `mac_build` 4 active / max 4; model: 1..N co-equal active tracks; typed graph; WIP-limited; surface-owned). This stamped digest carries track identity and surface ownership, NOT runtime truth and NOT full track detail (descriptions, next-items, non-goals stay in the YAML). Declared intent comes from `docs/governance/ACTIVE_TRACK.yaml`; evaluate it with `python3 scripts/governance/check_track_status.py`. Never answer runtime or liveness questions from this block or another prose copy. Admission scopes constrain declared build authority; they do not prove where a process is running.

**Spine objectives:** `substrate-nativeness`, `revenue-external-humans-served`, `research-depth` (each covered by at least one active track)

- **`fleet-advancement-2026-08`** — Fleet advancement — Fleet Hub, Mission Control, and HELM operator surfaces (ACTIVE, serves `substrate-nativeness`, verified 2026-08-27, open blocker items: 2)
  - owns: dharma_swarm/mission_control*.py, tests/test_mission_control.py, dashboard/src/app/dashboard/cockpit/**, dashboard/src/components/cockpit/**, dashboard/src/components/operator-coherence/v2/**, terminal/**, docs/architecture/FLEET_COMMAND_OPERATOR_SURFACE.md, specs/DGC_TERMINAL_ARCHITECTURE_v1.1.md
  - admission scopes: mac_build (declared build authority; not runtime evidence)
- **`sadhana-10-day-program-2026-08`** — SADHANA — governed 10-day program (ACTIVE, serves `revenue-external-humans-served`, verified 2026-08-27, open blocker items: 2)
  - owns: deploy/sadhana/**, scripts/runtime/sadhana_release.py, tests/test_sadhana_release.py, dashboard/src/app/dashboard/sadhana/**
  - admission scopes: mac_build (declared build authority; not runtime evidence)
- **`rsi-lab-meghadharma-2026-08`** — RSI Lab — exact-code Mac and Meghadharma campaign lane (ACTIVE, serves `research-depth`, verified 2026-08-27, open blocker items: 1)
  - owns: dharma_swarm/forge_lab/**, scripts/forge_lab/**, tests/forge_lab_v1/**, docs/ops/RSI_LAB_SYNC.md
  - admission scopes: mac_build (declared build authority; not runtime evidence)
- **`sublimation-forge-2026-08`** — Sublimation Forge — offline-first governed foundry (ACTIVE, serves `research-depth`, verified 2026-08-27, open blocker items: 2)
  - owns: dharma_swarm/foundry/**, scripts/foundry/**, tests/test_foundry_*.py, docs/foundry/**, dharma_swarm/rudra/**, dharma_swarm/terminal_commands/rudra.py, tests/test_rudra_*.py, tests/fixtures/rudra/**, reports/rudra/**, dharma_swarm/dgc_cli.py
  - admission scopes: mac_build (declared build authority; not runtime evidence)

Before editing any file, check it against the `owns:` globs above — a surface owned by a track you are not serving is off-limits except through that track's own next-items. Full track detail: `docs/governance/ACTIVE_TRACK.yaml`.

**Recently closed tracks:** `loop-closure-2026-06` (SUPERSEDED, closed 2026-08-27) · `orchestration-arena-v1-2026-06` (SUPERSEDED, closed 2026-08-27) · `merge-master-mike-d4-2026-06` (SUPERSEDED, closed 2026-08-27)

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
