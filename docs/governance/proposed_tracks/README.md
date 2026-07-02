# Proposed Tracks

This directory holds draft track blocks that are **not yet active**.

A file here is a proposal — a complete track block that an operator (or another
agent at the operator's direction) may move into `ACTIVE_TRACK.yaml` as the
next strategic `active_track:` once two conditions hold:

1. **Doctrine permits the strategic transition.** The proposal must have
   non-overlapping surfaces and non-goals with the current active track, or the
   operator must explicitly close/supersede the current track first.
2. **Parallel work is declared as a lane first.** Work may proceed before
   promotion only as an explicit lane under `parallel_lane_policy`: owner,
   branch/worktree or work packet, allowed surfaces, verification command, and
   receipt path.

## Rules

- A proposal here is **draft only**. It does not constitute a declared track;
  CI does not gate against it, `make onboard` does not surface it as strategic
  intent, and no agent should treat it as load-bearing until promoted into
  `ACTIVE_TRACK.yaml` or declared in the parallel lane map.
- A proposal must declare an `owner` and a non-empty `completion_criteria`
  list using the same `{id, kind, file, pattern}` shape the live checker
  accepts (`file_exists`, `file_contains`, `pr_merged`).
- A proposal that sits here for >30 days without being promoted should either
  be promoted, withdrawn (deleted by its author), or explicitly extended in a
  comment at the top of the file.
- Authorship: any agent or human contributor may add a proposal. The operator
  decides when (and whether) to promote.

## Current proposals

- `signal-synthesis-desk-2026-07.yaml` — a standing research-ingestion desk:
  clusters world_radar signals into themes over a rolling window, debates
  significance with a genuinely provider-diverse panel (gated by the new
  `panel_diversity.py` fail-closed diversity check), and writes DRAFT
  `proposed_tracks/*.yaml` entries only — never memory, never ACTIVE
  promotion. Grew out of a live 4-lens adversarial research trial
  (`reports/research/2026-07-01_signal_synthesis_live_run/DIGEST.md`) that
  caught a real hallucinated paper mid-research and found its own panel
  construction reproduced the exact same-model-no-diversity failure it was
  meant to judge. Serves `research-depth` (currently zero active tracks),
  not a 5th `substrate-nativeness` track. Named to avoid colliding with the
  existing arena `Council` (different job: trace verification, not
  significance judgment). Authored by claude-code, 2026-07-01.
- `agentic-design-patterns-cognition-2026-07.yaml` — makes the intra-agent
  reasoning loop first-class. Deep-read of Antonio Gulli's *Agentic Design
  Patterns* (21 chapters) mapped against the substrate: 13 patterns already
  STRONG (the multi-agent/infrastructure layer), 2 deliberately out of scope
  (Learning/Adaptation is zero-weight by design → arena track; MCP → A2A/NATS
  lanes), and one coherent PARTIAL cluster remaining — Reflection, Reasoning
  (CoT/self-consistency), Planning, Prompt-Chaining. Ships a new surface-disjoint
  `dharma_swarm/cognition/` package + a Slot-4 patterns atlas, benchmarked under
  budget parity. DRAFT (not a 5th ACTIVE substrate track) pending the three
  promotion preconditions in the file. Authored by claude-code, 2026-07-01.
- `spine-adoption-2026-06.yaml` — successor to `runtime-truth-spine-2026-06`
  (which shipped 13/13 by the letter but has zero callers outside the spine
  package and tests as of 2026-05-31). Migrates the five god objects
  (agent_runner, orchestrator, swarm, thinkodynamic_director, telos_substrate)
  onto `invoke_agent()`. Authored by perplexity-computer per the 2026-05-31
  A2A handoff from claude-code.
- `perplexity-a2a-bus-bridge-2026-06.yaml` — extends Codex's local A2A
  contact pattern (`a2a_core_contact.py` + NATS) to cloud-resident agents
  via a new `a2a_cloud_contact.py` webhook → NATS bridge. Brings
  perplexity-computer (and future cloud agents like Devin) onto the same
  bus the three local composers read, so the honest fleet score's
  denominator matches the operational population and inter-agent messages
  stop transiting through the operator as manual copy/paste. Authored by
  perplexity-computer; proposed owner is Codex (he owns the transport seam).
  Gated on: (1) PR #396 doctrine amendment merged — ✅ merged 2026-05-31,
  (2) Codex's NATS substrate PR landing on main, (3) Claude's multi-track
  schema PR landing on main.

## Why not just put proposals in `ACTIVE_TRACK.yaml` as inactive entries?

The schema does not have an "inactive" or "proposed" track state. A track in
`ACTIVE_TRACK.yaml` is either ACTIVE (current work, TTL counts down),
SHIPPED/SUPERSEDED (in `closed_tracks`, append-only history), or absent.
Holding draft proposals as a separate filesystem surface keeps the YAML clean
of speculative state while preserving the proposal as a reviewable artifact.
