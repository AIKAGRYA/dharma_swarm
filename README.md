---
title: DHARMA SWARM
path: README.md
slug: dharma-swarm
doc_type: readme
status: reference
summary: DHARMA SWARM is the operator-facing swarm runtime and control-plane codebase behind DHARMA COMMAND. It combines a Python orchestration core, a FastAPI backend, a Next.js dashboard, and a large research/spec layer that...
source:
  provenance: repo_local
  kind: readme
  origin_signals:
  - run_operator.sh
  - dharma_swarm/dgc_cli.py
  - dharma_swarm/swarm.py
  - dharma_swarm/agent_runner.py
  - dharma_swarm/evolution.py
  cited_urls: []
  generated_hint: human_or_agent_authored_repo_doc
disciplines:
- multi_agent_systems
- software_architecture
- knowledge_management
- research_methodology
- verification
- frontend_engineering
inspiration:
- verification
- operator_runtime
- product_surface
- research_synthesis
connected_python_files:
- dharma_swarm/dgc_cli.py
- dharma_swarm/swarm.py
- dharma_swarm/agent_runner.py
- dharma_swarm/evolution.py
- api/main.py
connected_python_modules:
- dharma_swarm.dgc_cli
- dharma_swarm.swarm
- dharma_swarm.agent_runner
- dharma_swarm.evolution
- api.main
connected_relevant_files:
- run_operator.sh
- dharma_swarm/dgc_cli.py
- dharma_swarm/swarm.py
- dharma_swarm/agent_runner.py
- dharma_swarm/evolution.py
improvement:
  room_for_improvement:
  - Keep entry points and commands aligned with the current runtime.
  - Add sharper cross-links into the most active specs, tests, and dashboards.
  - Make shipped behavior vs. exploratory material explicit.
  - Review whether this file should stay in `.` or be consolidated elsewhere.
  next_review_at: '2026-04-01T00:43:19+09:00'
pkm:
  note_class: readme
  vault_path: README.md
  retrieval_terms:
  - operator
  - facing
  - runtime
  - control
  - plane
  - codebase
  - behind
  - command
  - combines
  - python
  - orchestration
  - core
  evergreen_potential: high
stigmergy:
  meaning: This file is a shared environmental trace in the DHARMA corpus. Its path, recency, and linked surfaces guide future agent attention; its frontmatter now adds machine-readable coordination cues.
  state: canonical
  semantic_weight: 0.95
  coordination_comment: DHARMA SWARM is the operator-facing swarm runtime and control-plane codebase behind DHARMA COMMAND. It combines a Python orchestration core, a FastAPI backend, a Next.js dashboard, and a large research/spec layer that...
  levels:
    sematectonic:
      what_it_is: The document itself is the mark. Its existence, filename, location, and revision history attract or repel future work.
      access_mark: Opening, linking, and revising README.md reinforces its salience without needing a separate message.
    marker_based:
      what_it_is: The frontmatter is an explicit annotation layer on top of the document.
      semantic_mark: Semantic weight, improvement prompts, related files, and provenance comments tell later agents how to use this document.
  trace_role: coordination_trace
curation:
  last_frontmatter_refresh: '2026-04-01T00:43:19+09:00'
  curated_by_model: Codex (GPT-5)
  source_model_in_file: 
  future_model_handoffs:
  - GPT-5 Codex
  - Claude
  - Gemini
  - Local evaluator
  schema_version: pkm-phd-stigmergy-v1
---
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
- CLI: `dgc` (no-args launches TUI)
- TUI terminal: **`dgc tui`** (canonical)
- API server: `uvicorn api.main:app --host 127.0.0.1 --port 8420 --reload`
- Canonical backend launcher: `bash run_operator.sh`
- Dashboard dev server: `npm --prefix dashboard run dev`

## Common Commands

```bash
make xray
make compile
make test-smoke
make test-all
make dashboard-lint
make dashboard-build
```

## What The Inventory Says

Use the built-in static inventory pass to get a current snapshot:

```bash
make xray
```

That report is the fastest way to answer:

- how many Python modules and tests exist
- which files are the largest hotspots
- which local modules have the highest coupling
- what the repo language mix looks like

## Working Notes

- The codebase is split across active runtime code and a large documentation/spec corpus; not every markdown file describes shipped behavior.
- The most coupled runtime surfaces currently sit in the Python core, especially `dharma_swarm/dgc_cli.py`, `dharma_swarm/swarm.py`, `dharma_swarm/agent_runner.py`, and `dharma_swarm/evolution.py`.
- Dashboard and API development are active; expect local changes in `dashboard/`, `api/`, and resident-operator code during ongoing work.

## Current Operator Surface Status

- `terminal/` is the active Bun operator shell.
- `dharma_swarm/tui/` is the legacy Textual operator surface and still matters for some runtime/session flows.
- `terminal-v2/` exists as an experimental newer Bun surface, but it is not yet the canonical operator shell. Treat it as migration work, not the default place to land new features, unless a task explicitly targets it.
- `dharma_swarm/terminal_bridge.py` is the transport seam between the Python runtime and Bun terminal surfaces. It should move structured state and events, not invent shell-local policy.

## Agent Orientation Shortcut

If you want a human or agent to orient quickly, do not rely on the phrase `REPO RULES` by itself.
Use this instead:

```text
Read docs/governance/README.md, then CLAUDE.md, before touching code.
```

That sends the reader to:

- `docs/governance/README.md` for the active governance hub and read order
- `CLAUDE.md` for behavioral rules and repo-wide engineering constraints
- the touched code files after that, rather than broad doc wandering

## Before Writing Any Code

- **Read [`CLAUDE.md`](CLAUDE.md)** — system genome, key abstractions, behavioral rules, the Transcendence Principle.
- **Read [`docs/MEGAFILE_INDEX.md`](docs/MEGAFILE_INDEX.md)** — the canonical onboarding index. Reserves 10 onboarding slots (vision, doctrine, roadmap, limbs, wiring, live ops, broken register, runbook, agent contract, contemplative spine). Reading order 1→10. Points to all existing substrate.
- **Read [`docs/governance/README.md`](docs/governance/README.md)** — the active governance hub and recommended orientation order for humans and agents.
- **Read [`INTERFACE_MISMATCH_MAP.md`](INTERFACE_MISMATCH_MAP.md)** — every known interface mismatch between modules, with exact line numbers, root causes, and fixes. This is the primary source of runtime failures. Follow the Bootstrap Sequence to unblock the system.
- **Run `make xray`** — generates a live module map across all architectural layers with line counts (replaces the former static NAVIGATION.md).
- **Read [`MODEL_ROUTING_MAP.md`](MODEL_ROUTING_MAP.md)** — how every LLM call flows through the system. 18 providers, 3 calling surfaces, 5 inconsistencies, the HuggingFace fix, and the minimum viable path to first LLM call.

## First Places To Look

- Start at [api/main.py](api/main.py) for the API lifecycle and router registration.
- Start at [run_operator.sh](run_operator.sh) for the canonical local backend boot path.
- Start at [dashboard/package.json](dashboard/package.json) for frontend commands.
- Start at [scripts/repo_xray.py](scripts/repo_xray.py) for repo-wide static indexing.

## GAIA Docs

- `docs/dse/GAIA_UI.md`: current user manual for the tracked GAIA runtime surface
- `docs/dse/GAIA_TRAINING_WORKBOOK.md`: hands-on onboarding exercises for new GAIA users
- `docs/dse/GAIA_FACILITATOR_GUIDE.md`: facilitator notes, review keys, and assessment rubric
