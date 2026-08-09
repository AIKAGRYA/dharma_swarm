---
title: Seeing — where every knowledge/state store lives, and how full it is
status: seed
provenance: CLAUDE.md §State directory; reports/operator_debrief_2026-08-09/; sqlite inspection of ~/.dharma on 2026-08-09 (commands inline)
updated: 2026-08-09
---

# Seeing the organism's memory

The organism cannot claim self-knowledge it cannot enumerate. This page
names every knowledge/state store, who owns it, and how to measure its
fullness in one command.

## The stores

Runtime state lives under `~/.dharma/`, never in git; each path is owned by
the cited module (CLAUDE.md §"State directory (~/.dharma/)"):

| Store | Path | Owner / reader |
|---|---|---|
| Ontology objects | `~/.dharma/ontology.db` (`objects`, `links` tables) | ontology runtime (`tests/test_ontology_hub.py`) |
| Agent memory atoms | `~/.dharma/agent_memory/memories.db` (`memories`) | MemoryKernel front door (`dharma_swarm/memory_kernel/`) |
| Knowledge propositions | `~/.dharma/state/knowledge.db` (`propositions`, `prescriptions`) | knowledge ops |
| Vector documents | `~/.dharma/vectors.db` (`vec_documents`) | vector projection layer |
| Task board | `~/.dharma/board/event_log.sqlite3` (`board_events`) | SwarmManager / command API |
| Witness JSONL | `~/.dharma/witness/` | `telos_gates.py` |
| Stigmergy marks | `~/.dharma/stigmergy/marks.jsonl` | `stigmergy.py` |
| Evolution archive | `~/.dharma/evolution/archive.jsonl` | `archaeology_ingestion.py` |
| Strange-loop mutations | `~/.dharma/organism_memory/mutations.jsonl` | `strange_loop.py` |
| Traces | `~/.dharma/traces/` | `traces.py` |
| Canonical wiki | `docs/wiki/*.md` (this directory, in git) | reviewed text — see `README.md` |

## What was found empty on 2026-08-09

Observed in the operator-debrief checkout on 2026-08-09 (reproduce with the
fullness check below):

- **`~/.dharma/ontology.db` — 0 objects, 0 links.** The "one shared
  world-model" organ has never written an object here.
- **`~/.dharma/state/knowledge.db` — 0 rows** in `propositions`,
  `prescriptions`, and `concept_index`.
- **`~/.dharma/vectors.db` — 0 documents** in `vec_documents`.
- **`docs/wiki/` — previously nonexistent.** No wiki directory existed in
  git history before this seed (`git log --all --oneline -- docs/wiki` was
  empty before this commit).

The same day's debrief corroborates the pattern from the runtime side:
cost ledger never created (F7), `~/.dharma/shared/` empty after 16+ agent
runs (F20, `reports/operator_debrief_2026-08-09/day2/DAY2_ADDENDUM.md`),
Go ingestors with no bronze receipts and DarwinEngine with no fitness data
(`reports/operator_debrief_2026-08-09/OPERATOR_DEBRIEF.md` §3). Almost the
only stores with content were the task board, traces, witness, and a
handful of agent-memory rows.

An organism whose knowledge stores are empty is not remembering; it is
re-deriving itself every session. That is the emptiness this wiki and the
Darshan Pack exist to close.

## The one-command fullness check

```bash
python3 scripts/governance/darshan_pack.py
```

Prints the Darshan Pack: identity, active tracks, and live row counts for
every sqlite store above (0/absent when missing) plus a task-board
snapshot. `make onboard` also prints a `KNOWLEDGE STORES` section with the
same counts, so a fresh clone announces its emptiness instead of hiding it.
