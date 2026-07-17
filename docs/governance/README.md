# Governance Hub

Start with read-only session status, not this README:

```bash
make onboard
# or: python3 scripts/governance/agent_onboard.py
```

`make onboard` reports whether the current checkout and session are ready. It
does not authorize editing and does not claim to render the whole organism.
Use `make organism-status` for the deeper read-only cross-system projection.
Packet-bound preflight and closeout are required when changed paths match Merge
Master Mike's `HOT_PATH_PATTERNS` in `scripts/runtime/pr_merge_control.py`; they
are optional otherwise. When a packet is required or voluntarily used, run
`make agent-build-preflight PACKET=<path>` before editing to bind the exact
baseline and scope. `BUILD_SESSION_ENTRYPOINT.md` owns these command boundaries.

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
| Session-entry command contract | [`BUILD_SESSION_ENTRYPOINT.md`](BUILD_SESSION_ENTRYPOINT.md) |
| Live state (runtime) | [`../state/LIVE_OPS_DASHBOARD.md`](../state/LIVE_OPS_DASHBOARD.md) |
| Known breakage | [`../state/BROKEN_REGISTER.md`](../state/BROKEN_REGISTER.md) |

## Why this exists

Before this convergence, agents had to read a prose "read order" across many
docs to find the relevant owner, and the prose lagged the code. Session status
and organism orientation now come from explicit read-only commands. This hub
remains a depth-pointer index; it is not another status surface.
