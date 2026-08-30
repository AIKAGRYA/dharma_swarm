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
make onboard           # read-only session status; mandatory first command
make organism-status   # deeper read-only whole-organism orientation
make vision            # the vision: what this is FOR and which laws bend your work (read-only projection)
make agent-build-preflight PACKET=<path>  # exact edit admission
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

Start with session truth:

```bash
make onboard
# or: python3 scripts/governance/agent_onboard.py
```

`make onboard` reports whether the current checkout and session are understood
and ready. It is read-only status, not edit permission and not a complete model
of the running organism.

For the deeper cross-system view, run:

```bash
make organism-status
```

Packet-bound preflight and closeout are required when changed paths match Merge
Master Mike's `HOT_PATH_PATTERNS` in `scripts/runtime/pr_merge_control.py`; they
are optional otherwise. When a packet is required or voluntarily used, bind
the exact task and baseline before editing:

```bash
make agent-build-preflight PACKET=<path>
```

The stable boundary between session status, organism orientation, edit
admission, closeout, CI, and persistent-agent registration is documented in
[`BUILD_SESSION_ENTRYPOINT.md`](docs/governance/BUILD_SESSION_ENTRYPOINT.md).
When prose disagrees with a command's live evidence or its named owner, trust
the command and owner for their specific domain.

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
