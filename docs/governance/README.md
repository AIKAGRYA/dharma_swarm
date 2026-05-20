# Governance Hub

The single door into the active operating reality is the onboarding command,
not this README:

```bash
make onboard
# or: python3 scripts/governance/agent_onboard.py
```

That command reads the existing owners (ACTIVE_TRACK.yaml, LIVE_OPS_DASHBOARD.md,
BROKEN_REGISTER.md, ACTIVE_SURFACE_MANIFEST.yaml) and renders the current truth
in one screen. It does not own any fact; it surfaces what the owners say.

This README is a **depth pointer** to the governance docs you read on demand,
not in order.

## Depth Pointers (read on demand)

| Need | File |
|---|---|
| Active build track | [`ACTIVE_TRACK.yaml`](ACTIVE_TRACK.yaml) |
| Behavioural contract | [`../../CLAUDE.md`](../../CLAUDE.md), [`../../AGENTS.md`](../../AGENTS.md), [`../AGENTS.md`](../AGENTS.md) |
| Architecture & invariants | [`SOVEREIGN_MANIFEST.md`](SOVEREIGN_MANIFEST.md), [`../doctrine/`](../doctrine/) |
| Doc ownership map | [`CANONICAL_DOC_STACK.md`](CANONICAL_DOC_STACK.md) |
| Anti-slop rules | [`ANTI_SLOP_RULES.md`](ANTI_SLOP_RULES.md) |
| Coherence Delta (PR discipline) | [`COHERENCE_DELTA.md`](COHERENCE_DELTA.md) |
| Fourfold action warrant | [`FOURFOLD_ACTION_WARRANT.md`](FOURFOLD_ACTION_WARRANT.md) |
| Work loops | [`AGENTOPS.md`](AGENTOPS.md), [`KAIZENOPS.md`](KAIZENOPS.md), [`DAILY_OPERATING_BRIEF.md`](DAILY_OPERATING_BRIEF.md), [`METABOLIC_CLOCK.md`](METABOLIC_CLOCK.md) |
| Audit trail | [`REPO_GOVERNANCE_AUDIT.md`](REPO_GOVERNANCE_AUDIT.md) |
| Build-session entrypoint (depth) | [`BUILD_SESSION_ENTRYPOINT.md`](BUILD_SESSION_ENTRYPOINT.md) |
| Live state (runtime) | [`../state/LIVE_OPS_DASHBOARD.md`](../state/LIVE_OPS_DASHBOARD.md) |
| Known breakage | [`../state/BROKEN_REGISTER.md`](../state/BROKEN_REGISTER.md) |

## Why this exists

Before this convergence, agents had to read a prose "read order" across many
docs to figure out the current state, and the prose lagged the code. The
onboarding command replaced the read order with a live render. This hub
remains as a depth-pointer index for when you need to go beyond the surface.
