# Packet 01: Command Plane And Governance

Packet ID: `ctx.command-plane-governance`

Use when an agent is touching onboarding, orientation, active tracks, live-status
rendering, governance docs, or "what should I do next?" decisions.

Do not use as a substitute for `make onboard`. This packet explains how to use
the command plane; it does not own live state.

## Authority Model

- Intent owner: `docs/governance/ACTIVE_TRACK.yaml`
- Surface owner: `ACTIVE_SURFACE_MANIFEST.yaml`
- State owner: `docs/state/LIVE_OPS_DASHBOARD.md`, git, runtime receipts
- Projection owners: `scripts/governance/agent_onboard.py`,
  `scripts/governance/orientation_graph.py`
- Doctrine owner: `docs/governance/SOVEREIGN_MANIFEST.md`
- Proof owner: command output, tests, and receipts, not narrative prose

Core invariant: read models project truth from owners; they do not become
authority.

## Mission

Keep agents from starting in a stale or generic mental model. The command plane
must answer, quickly and honestly: where am I, what is live, what is shippable,
what is broken, what surfaces are owned, what should not be touched, and which
packet should be loaded next.

## First Reads

L0 Safety:

- `AGENTS.md`
- `CLAUDE.md`
- `make onboard` output

L1 Route:

- `docs/governance/ACTIVE_TRACK.yaml`
- `ACTIVE_SURFACE_MANIFEST.yaml`
- `docs/ontology/session_orientation.yaml`

L2 Owners:

- `scripts/governance/agent_onboard.py`
- `scripts/governance/orientation_graph.py`
- `docs/governance/CANONICAL_DOC_STACK.md`
- `docs/governance/ANTI_SLOP_RULES.md`

L3 Evidence:

- `reports/governance/active_track_evidence.md`
- `reports/governance/track_portfolio.json`
- `/Users/dhyana/.dharma/ops/onboard_receipt.json`

L4 Search:

- `rg -n "read models project truth|ACTIVE_TRACK|make onboard" docs scripts dharma_swarm`
- `rg -n "SHIPPABLE|completion_criteria|owned_surfaces" docs/governance/ACTIVE_TRACK.yaml`

L5 Seat:

- Load no named seat until the active surface is known.

## Live Probes

Run before any governance claim:

```bash
make onboard
python3 scripts/governance/orientation_graph.py --json
python3 scripts/governance/check_track_status.py
git status --short --branch
```

If preparing a PR or handoff:

```bash
make agent-build-closeout
```

## Retrieval Contract

Use retrieval only after L0-L2 route selection.

- Query: "current active track owned surfaces completion criteria"
  Source family: `docs/governance/ACTIVE_TRACK.yaml`,
  `reports/governance/active_track_evidence.*`.
  Use for deciding what is in scope.
- Query: "broken register stale docs live ops dashboard"
  Source family: `docs/state/**`, `make onboard`.
  Use for checking decay and blocked surfaces.
- Query: "agent onboarding session orientation semantic commons"
  Source family: `docs/ontology/session_orientation.yaml`, `docs/ops/**`.
  Use for admission and first-token context.

## Operating Loop

1. Run `make onboard`.
2. Identify the relevant active track or open a new one only if the operator's
   request is truly a new project.
3. Read the active track's `owned_surfaces`, `next_items`, and `non_goals`.
4. Select a more specific context packet from `CONTEXT_PACKET_INDEX.json`.
5. Act only within owned surfaces or explicitly explain overlap.
6. Verify with the narrowest meaningful governance/test command.
7. Leave changed files, verification, residual risk, and packet id used.

## Guardrails

- Do not move active tracks to closed tracks without explicit operator lifecycle
  authorization.
- Do not treat a SHIPPABLE gate as closure.
- Do not let onboarding become a new source of truth.
- Do not hand-edit generated active-track blocks in `CLAUDE.md`.
- Do not smooth over dirty worktree state.
- Do not cite stale docs without checking git and owner files.

## Context Budget

- Tiny: `make onboard` plus this packet.
- Standard: tiny plus `ACTIVE_TRACK.yaml`, `ACTIVE_SURFACE_MANIFEST.yaml`, and
  `orientation_graph.py --json`.
- Deep: standard plus active-track evidence, canonical doc stack, broken
  register, and relevant tests.

Put `make onboard` summary near the top of the prompt and non-goals near the end
to avoid long-context middle loss.

## Done Criteria

Complete means:

- the selected owner files are named;
- live state is probed;
- any edit stays inside scoped surfaces or explains overlap;
- `check_track_status.py` or a narrower relevant test is run;
- handoff says which packet was used.

## Agent Prompt Block

```text
You are working in Dharma Swarm using context packet ctx.command-plane-governance.
First run make onboard. Treat ACTIVE_TRACK.yaml as intent, ACTIVE_SURFACE_MANIFEST.yaml
as declared surface, runtime receipts/git as state, and onboarding/orientation as
read-only projections. Do not close tracks or create new authority. Identify the
relevant active track, load the specific packet for the organ, act only within
owned surfaces, verify narrowly, and leave a receipt-style handoff.
```

## Handoff Receipt Shape

```json
{
  "packet_id": "ctx.command-plane-governance",
  "onboard_head": "commit or timestamp",
  "active_track_ids": [],
  "owned_surfaces_touched": [],
  "commands_run": [],
  "verification": [],
  "claims_not_made": [],
  "next_packet": "",
  "residual_risk": ""
}
```
