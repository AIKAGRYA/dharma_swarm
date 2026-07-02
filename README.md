# DHARMA SWARM

DHARMA SWARM is the operator-facing swarm runtime and control-plane codebase behind DHARMA COMMAND.
It combines a Python orchestration core, a FastAPI backend, a Next.js dashboard, and a large research/spec layer that informs the runtime.

## Repo Map

- `dharma_swarm/`: primary Python runtime, swarm coordination, providers, evolution, monitoring, TUI, and operator logic
- `api/`: FastAPI application and routers for the dashboard/control plane
- `dashboard/`: Next.js frontend for DHARMA COMMAND
- `tests/`: pytest coverage for runtime, API, dashboard routers, and TUI flows
- `scripts/`: operator utilities, maintenance tasks, demos, and `repo_xray.py`
- `docs/`: implementation and subsystem documentation
  - see `docs/README.md` for the documentation ontology, archive rules, and cleanup map
- `reports/`: generated analysis, architecture packets, and audit artifacts
- `specs/`: formal and working specs
- `foundations/`: conceptual and research foundation documents

## Entry Points

- Python package: `dharma-swarm`
- CLI: `dgc`
- API server: `uvicorn api.main:app --host 127.0.0.1 --port 8420 --reload`
- Canonical backend launcher: `bash run_operator.sh`
- Dashboard dev server: `npm --prefix dashboard run dev`

## Common Commands

```bash
make help              # full curated target list
make onboard           # mandatory first command for any agent or operator
make install           # pip install -e .[dev]
make test-fast         # fast subset of pytest
make test              # full pytest suite
make lint              # ruff
make hygiene-audit     # non-blocking vibe-code hygiene scan
make hygiene-check     # verify hygiene catalogue / generated docs integrity
make docops-integrity  # machine-verifiable documentation checks
make governance-all    # full governance suite
```

See `make help` for the complete, authoritative target list — it is regenerated alongside the Makefile and never drifts.

## Cybernetic Ratchet Loop

A 5-stage governance pipeline (`scripts/governance/loop/`) that audits code for slop, triages findings, remediates with anti-gaming enforcement, re-audits with a fresh verifier, and ratchets CI gates to prevent recurrence. Core invariant: **LLM proposes, deterministic oracle disposes** — no LLM opinion is ever recorded as truth.

This is separate from the 13 runtime cybernetic loops in `CYBERNETIC_LOOP_MAP.md`. Current runtime-loop status is projected by `scripts/governance/cybernetics_codex_audit.py --json`: 4/13 bounded-replay closed, 7 partial, 2 blocked, and 0/13 all-history daemon clean as of 2026-07-01.

**Stages:** `prompt_audit_run` (Auditor) → `prompt_audit_triage` (deterministic triage) → `prompt_audit_remediate` (Implementer + §8 anti-gaming) → `prompt_audit_reaudit` (Verifier, falsification-first) → `prompt_audit_learn` (Ratcheter, drives existing ratchet engine)

**Run the loop:**
```bash
PYTHONPATH=. /Users/dhyana/dharma_swarm/.venv/bin/python scripts/governance/loop/prompt_audit_run.py --help
```

**Test the loop:**
```bash
PYTHONPATH=. /Users/dhyana/dharma_swarm/.venv/bin/python -m pytest tests/governance/loop/ -q
```

**Agent backends:** `LOOP_AGENT_BACKEND=stub|droid|api` (default: stub). The droid backend shells out to the `droid` CLI for role-separated Auditor/Implementer/Verifier invocations with heterogeneous verifier routing.

**CI integration:** `.github/workflows/loop-ratchet-gates.yml` runs the cheap-tier governance gates on push, pull_request, and merge_group. `wire_ci_gate.py` adds new ratcheted gates from the learn stage.

See `scripts/governance/loop/README.md` for the full module reference.

## What The Inventory Says

For a current static snapshot of the repo (module/test counts, hotspots, coupling, language mix), run the DocOps inventory pass:

```bash
make docops-report
```

The generated JSON/Markdown reports under `docs/docops/` answer:

- how many Python modules and tests exist
- which files are the largest hotspots
- which local modules have the highest coupling
- what the repo language mix looks like

## Working Notes

- The codebase is split across active runtime code and a large documentation/spec corpus; not every markdown file describes shipped behavior.
- The most coupled runtime surfaces currently sit in the Python core, especially `dharma_swarm/dgc_cli.py`, `dharma_swarm/swarm.py`, `dharma_swarm/agent_runner.py`, and `dharma_swarm/evolution.py`.
- Dashboard and API development are active; expect local changes in `dashboard/`, `api/`, and resident-operator code during ongoing work.

## Before Writing Any Code

One command. Run it. Read its output. That is the entire pre-flight.

```bash
make onboard
# or: python3 scripts/governance/agent_onboard.py
```

`agent_onboard.py` is the **single door** into the current operating reality. It does not own any fact — it renders the current truth from the existing owners:

| What you need | Owner (the only place this fact lives) |
|---|---|
| Active build track | [`docs/governance/ACTIVE_TRACK.yaml`](docs/governance/ACTIVE_TRACK.yaml) |
| Live runtime / merge state | [`docs/state/LIVE_OPS_DASHBOARD.md`](docs/state/LIVE_OPS_DASHBOARD.md) |
| Declared surfaces / routers / nav | [`ACTIVE_SURFACE_MANIFEST.yaml`](ACTIVE_SURFACE_MANIFEST.yaml) |
| Known broken / stale surfaces | [`docs/state/BROKEN_REGISTER.md`](docs/state/BROKEN_REGISTER.md) |
| Behavioural contract | [`CLAUDE.md`](CLAUDE.md), [`AGENTS.md`](AGENTS.md), [`docs/AGENTS.md`](docs/AGENTS.md) |
| Architecture / doctrine | [`docs/governance/SOVEREIGN_MANIFEST.md`](docs/governance/SOVEREIGN_MANIFEST.md), [`docs/doctrine/`](docs/doctrine/) |
| Doc ownership map | [`docs/governance/CANONICAL_DOC_STACK.md`](docs/governance/CANONICAL_DOC_STACK.md) |
| Anti-slop rules | [`docs/governance/ANTI_SLOP_RULES.md`](docs/governance/ANTI_SLOP_RULES.md) |

If any prose in any doc disagrees with `make onboard`, **trust `make onboard`**, the filesystem, and `git log`. The onboarding output is informational — it never gates merges — but it is the freshest read of reality.

## First Places To Look

- Start at [api/main.py](api/main.py) for the API lifecycle and router registration.
- Start at [run_operator.sh](run_operator.sh) for the canonical local backend boot path.
- Start at [dashboard/package.json](dashboard/package.json) for frontend commands.
- Start at [scripts/repo_xray.py](scripts/repo_xray.py) for repo-wide static indexing.
- **Keys & model routing — THE ONE WAY:** [docs/ops/MODEL_KEY_ROUTING.md](docs/ops/MODEL_KEY_ROUTING.md). One key home (`~/.dharma/agent_keys.env` + `dkeys`), one resolver door (`runtime_provider.resolve_runtime_provider_config`), Anthropic→Max plan. Read before any key or model call.

## GAIA Docs

- `docs/dse/GAIA_UI.md`: current user manual for the tracked GAIA runtime surface
- `docs/dse/GAIA_TRAINING_WORKBOOK.md`: hands-on onboarding exercises for new GAIA users
- `docs/dse/GAIA_FACILITATOR_GUIDE.md`: facilitator notes, review keys, and assessment rubric
