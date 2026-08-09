---
title: Organ map — declared status vs observed runtime
status: seed
provenance: docs/vision_maps/NORTH_STAR.md §7; reports/operator_debrief_2026-08-09/OPERATOR_DEBRIEF.md §3
updated: 2026-08-09
---

# The organs — honest status, one glance

Two views, deliberately side by side: the **declared** organ table
(vision-level, 2026-06-11) and what a real operator **observed running**
on 2026-08-09. Statuses are owned by
`docs/governance/VENTURE_CELL_PORTFOLIO.yaml` and the swarm-genome
organ-health table; both tables below are projections — if they drift,
trust the owners (`docs/vision_maps/NORTH_STAR.md` §7, lines 124–127).

## Declared organs (NORTH_STAR §7, statuses of 2026-06-11)

| Organ | Lane | Declared status |
|---|---|---|
| Agentic-OS substrate | guides everything | ACTIVE (2 spine tracks) |
| Darshan | noosphere / publication | ACTIVE_SEASON_0 |
| GoodWorks DGM | MRV core | ACTIVE_BUILD_TRACK |
| Revenue wedge | self-funding discovery | INCUBATING |
| Shakti Ginko / Capital Lab | trading (self-funding) | INCUBATING (paper-only, hard-gated) |
| Campaign X-Ray | advisory | HELD (gauntlet 28/100) |
| Loomwork | media / civil-society Palantir | DESIGN_ONLY |
| Vwrite | writing master (feeds Darshan) | PROPOSED (design memo) |
| Dharma Forge / Hydra | reality-reward membrane | STOPPED-HONESTLY (2026-06-02) |
| SAB Dharmic Agora | propagation basin / agent society | DORMANT (zero sparks) |
| GAIA reciprocity, Web-4.0 trust | accounting / market position | ENVISIONED |
| R_V research program | mech interp | OPEN (RESEARCH_PROGRAM.md, 2026-06-03) |

Source: `docs/vision_maps/NORTH_STAR.md` §7 (lines 129–142). Note the
declared date — these statuses are ~2 months older than the runtime
observation below.

## Runtime organs observed on 2026-08-09

A full operator day in a fresh checkout
(`reports/operator_debrief_2026-08-09/OPERATOR_DEBRIEF.md` §3) split the
runtime organs into alive and dead **by observation, not declaration**:

**Alive (participated in real work):** `agent_onboard.py` (onboard),
`api/main.py` + routers (FastAPI on :8420), `swarm.py` SwarmManager,
`orchestrator.py` (routing/dispatch/timeout), `agent_runner.py` +
`providers.py` ClaudeCodeProvider ("the one working brain"),
`stigmergy.py` (2 marks written), witness JSONL, jikoku span log,
conversation_log, `observability.py` (dispatch traces),
`world_radar/cli.py` (ran; network-failed), the Bun/Ink TUI (launches),
the Next.js dashboard (serves after workaround), latent-gold task spawner.

**Dead / never fired that day:** `evolution.py` DarwinEngine ("No fitness
data yet"), `dharma_kernel.py` ("Kernel not initialized"), the HUM ("No
dreams yet"), NATS substrate (port 4222 not listening, 0/5 mirrors), all
Ollama/keyed API providers, Go ingestors (no bronze receipts under
`~/.dharma`), `graph_nexus.ConceptGraph` (import error), the
orchestrate-live daemon (never started), cost ledger (file never created).

Both lists quoted from
`reports/operator_debrief_2026-08-09/OPERATOR_DEBRIEF.md` §3
(lines 104–128); friction codes F1–F14 in §2 of the same file carry the
receipts.

## Reading the gap

The declared table says what the organism intends; the debrief says what
fired. Where an organ is declared ACTIVE but observed dead (DarwinEngine,
kernel, Go ingestors, NATS), the gap itself is the work item — do not
paper over it in either direction. Delegation scorecard for the same day:
1 of 4 todo items succeeded through the swarm (debrief §4), and 0 of 8 on
day 2 (`reports/operator_debrief_2026-08-09/day2/DAY2_ADDENDUM.md`).
