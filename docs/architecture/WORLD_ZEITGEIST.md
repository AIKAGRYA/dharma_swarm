---
title: World Zeitgeist Radar
path: docs/architecture/WORLD_ZEITGEIST.md
doc_type: architecture
status: active
summary: External-world sensing, scout cascade, R&D incubation, and Shakti promotion path.
---

# World Zeitgeist Radar

Zeitgeist is external-world sensing. It is not repo health, test health, or internal pressure. Those signals live in `dharma_swarm/internal_pressure.py`.

This is also not the same thing as Active Manifest work. The radar feeds the strategy window: what the world is doing, what breakthroughs or companies are appearing, and what should be incubated before the swarm acts.

## Runtime Path

1. Public observations enter `world_operator_drops.jsonl`, `world_scout_observations.jsonl`, or `world_radar_observations.jsonl`.
2. `tools/world_scout_go` fetches public sources only when `DHARMA_WORLD_SCOUT_FETCH=1`.
3. `tools/world_signal_ingestor_go` normalizes raw observations into strategic signal rows.
4. `dharma_swarm/world_radar_go_bridge.py` builds `world_signal_board.json` and `world_signal_brief.md`.
5. Weak high-upside signals go through a 3-pass incubator under `meta/world_radar/incubations/`.
6. Only promotion-ready signals are copied into `world_zeitgeist_inbox.jsonl`.
7. `zeitgeist.py` reads that inbox and Shakti can promote those rows as `ecosystem_scan`.

## Promotion Rule

A signal is promotion-ready only if it has:

- two independent public sources, or
- an operator drop plus one concrete evidence URL/source.

Single-source high-upside signals do not promote directly. They enter incubation.

## Incubation

Each incubation has three passes:

- Verify: prove the source, date, URL, and claim are real.
- Connect: map adjacent companies, repos, papers, docs, funding/news, and competitors.
- Evolve: brainstorm prototype angles, research paths, governance risks, and how the signal serves Dharma growth.

The canonical human surface is `world_signal_brief.md`. The canonical agent surface is `world_signal_board.json`.

## Guardrails

The radar may collect, normalize, brief, incubate, and propose internal research. It must not send external outreach, spend money, form partnerships, or change core architecture without human approval.
