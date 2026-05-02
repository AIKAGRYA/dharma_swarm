# `~/.dharma/` Ownership Map

The `~/.dharma/` directory is the dharma_swarm runtime state root. Every file
or sub-tree under it has exactly one canonical Python owner — the module
authorized to write to that path. Non-owners must read through the owner's
public API or through `RuntimeStateStore`, never by opening files directly.

This file is the source of truth for the allowlist enforced by the Semgrep
rule `dharma.no-unauthorized-dharma-write` in
[`.semgrep/dharma-anti-slop.yml`](../../.semgrep/dharma-anti-slop.yml).
**Adding a new owner requires updating both this doc and the Semgrep
allowlist in the same PR.**

## Authority classes

Every owner is one of three classes:

- **Write** — creates new truth (events, facts, marks, atoms).
- **Project** — derives a read-only view over Write authorities.
- **Distill** — emits new authority-1 marks or authority-4 staged atoms; never
  mutates existing trusted state.

See `docs/architecture/MEMORY_SYSTEM_FUSION_MAP_2026-05-01.md#memory-authorities`
for the canonical authority table.

## Current owners (2026-05-02)

### Pre-2026-04-26 audit

| Owner module | Class | `~/.dharma/` slice | Notes |
|---|---|---|---|
| `dharma_swarm/runtime_state.py` | Write | `~/.dharma/state/runtime.db` | The runtime SQLite DB; canonical home for facts, edges, events, sessions, runs, leases, artifacts. |
| `dharma_swarm/system_rv.py` | Write | `~/.dharma/system/rv.json` | System R_V state. |
| `dharma_swarm/daemon_config.py` | Write | `~/.dharma/daemon.toml` | Daemon configuration. |
| `dharma_swarm/experiment_log.py` | Write | `~/.dharma/evolution/experiments.jsonl` | Experiment runs. |
| `dharma_swarm/pulse.py` | Write | `~/.dharma/pulse/` | Pulse / heartbeat artifacts. |
| `dharma_swarm/custodians.py` | Write | `~/.dharma/custodians/` | Custodian state. |
| `dharma_swarm/kaizen_ops_local.py` | Write | `~/.dharma/kaizen/` | Local kaizen operations. |
| `dharma_swarm/scout_report.py` | Write | `~/.dharma/scout/` | Scout reports. |
| `dharma_swarm/review_cycle.py` | Write | `~/.dharma/review/` | Review cycle state. |
| `dharma_swarm/ginko_backtest.py` | Write | `~/.dharma/ginko/backtests/` | Ginko backtest results. |
| `dharma_swarm/ginko_evolution.py` | Write | `~/.dharma/ginko/tournament_history.jsonl` | Ginko evolution tournaments. |

### Membrane owners (added 2026-05-02)

| Owner module | Class | `~/.dharma/` slice | Canary gate | Notes |
|---|---|---|---|---|
| `dharma_swarm/register_disciplines.py` | Write | `~/.dharma/stigmergy/register_marks.jsonl` | `DHARMA_CHETANA_ENABLED=1` | Closed-loop register marks (predict → resolve, gate-check, mutation, friction). Default-path writes are gated by the master canary; explicit `log_path` callers (tests, ad-hoc tooling) bypass. See `_is_canonical_register_log()` in the module for the path-equality helper used by the gate. |
| `dharma_swarm/retrieval/retrieval_effect_logger.py` | Distill | `~/.dharma/retrieval/effect.jsonl` | `DHARMA_CHETANA_ENABLED=1` | JSONL projection of `RetrievalEffect` records. The canonical telemetry always lands in `ContextBundleRecord.metadata`; the JSONL is an optional projection used by ops dashboards. Default-path writes are gated by the master canary; explicit `path=` callers (tests, tooling) bypass. |

The two membrane owners share a single canary flag so the user has one switch to
disable everything chetana introduced. See
[`docs/governance/CANONICAL_DOC_STACK.md`](CANONICAL_DOC_STACK.md) for the pointer
into the architecture map and
[`docs/architecture/MEMORY_SYSTEM_FUSION_MAP_2026-05-01.md#memory-authorities`](../architecture/MEMORY_SYSTEM_FUSION_MAP_2026-05-01.md#memory-authorities)
for the full authority table.

## Adding a new owner — checklist

1. Open a governance issue describing the new slice and class.
2. Add a row to **this file** under the appropriate section (Pre-audit /
   Membrane / future).
3. Add the owner module path to `paths.exclude` in
   [`.semgrep/dharma-anti-slop.yml`](../../.semgrep/dharma-anti-slop.yml)
   under Rule 1 `dharma.no-unauthorized-dharma-write`.
4. If the owner introduces a new state directory (not just a file under an
   existing one), document the directory layout under `## State directory
   layout` below.
5. If the owner is **gated by a canary flag**, document the flag name and the
   canonical-path helper used to discriminate gated vs ungated writes.
6. Run the allowlist test (when it exists) and the Semgrep scanner before
   opening the PR.

## State directory layout

```
~/.dharma/
├── state/
│   └── runtime.db                    # runtime_state.py
├── system/
│   └── rv.json                       # system_rv.py
├── stigmergy/
│   └── register_marks.jsonl          # register_disciplines.py (gated)
├── evolution/
│   └── experiments.jsonl             # experiment_log.py
├── pulse/                            # pulse.py
├── custodians/                       # custodians.py
├── kaizen/                           # kaizen_ops_local.py
├── scout/                            # scout_report.py
├── review/                           # review_cycle.py
├── ginko/
│   ├── backtests/                    # ginko_backtest.py
│   └── tournament_history.jsonl      # ginko_evolution.py
├── retrieval/
│   └── effect.jsonl                  # retrieval_effect_logger.py (gated)
└── daemon.toml                       # daemon_config.py
```

Streams not listed here (`~/.dharma/witness/`, `~/.dharma/replication/`,
`~/.dharma/organism_memory/`, `~/.dharma/meta/`, `~/.dharma/cost_log.jsonl`,
`~/.dharma/corpus.jsonl`, `~/.dharma/self_model/`, `~/.dharma/knowledge/`)
have authorities that have not yet been promoted into the Semgrep allowlist.
The 2026-04-26 audit captured eleven canonical owners; the remaining streams
will be audited and added to this map in a follow-up governance pass.
