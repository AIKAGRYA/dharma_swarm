# Sarathi Apex / Holon System Build History

Status: **collapse base landed on main; Sarathi is not yet a durable living
service**. This folder preserves the Sarathi-specific design and build sequence.
It no longer owns the ecosystem-wide source or readiness verdict.

Start with [`../SARATHI.md`](../SARATHI.md). It is the current subject doorway
and distinguishes the Sarathi seat, shared Holon substrate, adjacent runtime
families, and external Hermes/OpenClaw lanes. The July
[`estate map`](../architecture/HOLON_RUNTIME_FULL_ESTATE_MAP.md) remains a dated
deep reference. Onboarding and `docs/state/LIVE_OPS_DASHBOARD.md` still own live
state.

## Read order

1. [Canonical subject doorway](../SARATHI.md) — locked terms, family map,
   current high-level state, and evidence routes.
2. [Dated estate map](../architecture/HOLON_RUNTIME_FULL_ESTATE_MAP.md) — deep
   July snapshot; do not use its counts as current truth.
3. [`00_START_HERE.md`](00_START_HERE.md) — Sarathi thesis and original baseline.
4. [`02_CODEBASE_RUNTIME_BOUNDARY.md`](02_CODEBASE_RUNTIME_BOUNDARY.md) — dated
   repo/runtime boundary detail; defer to current code/tests, the census, and
   the subject doorway on conflicts.
5. [`05_SARATHI_APEX_MAP.md`](05_SARATHI_APEX_MAP.md) — Sarathi-specific intent.
6. [`06_PROOF_GATES.md`](06_PROOF_GATES.md) — original gate design.
7. [`07_BACKLOG.md`](07_BACKLOG.md) — dated closure packets; check PR/code state.
8. [`08_CURRENT_STATE_SARATHI_AUTONOMY_2026-07-30.md`](08_CURRENT_STATE_SARATHI_AUTONOMY_2026-07-30.md)
   — superseded drift-reconciliation snapshot for the 2026-07-30 autonomy build
   (`docs/prompts/SARATHI_AUTONOMY_BUILD_2026-07-30.md`).
9. [`90_ANTI_SPRAWL_HARNESS.md`](90_ANTI_SPRAWL_HARNESS.md) and
   [`91_SPRAWL_HARNESS_RUNBOOK.md`](91_SPRAWL_HARNESS_RUNBOOK.md) — anti-fork
   policy and enforcement.

`01_CURRENT_STATE.md`, `03_HOLON_SYSTEM_CODE_MAP.md`, and
`04_PERSISTENT_AGENT_RELATION.md` are useful dated lane captures, not current
estate authorities.

## Dated orientation captured by this build history

1. PR #821 landed the collapse base on 2026-07-09 at merge `0beef7584`
   (`git show -s --format='%H %cs %s' 0beef7584`).
2. The repo-root `holon/` fork is gone from current main; the sprawl guard is
   clean (`test ! -d holon`; `PYTHONPATH=$PWD python3 scripts/governance/sprawl_guard.py`).
3. `dharma_swarm/holon_system/` is a thin facade/navigation package, not a new
   runtime body (`find dharma_swarm/holon_system -type f -name '*.py' -print0 | xargs -0 wc -l`).
4. The proposal runner does not execute its proposed action, acquire an execution
   lease, connect live cost accounting, or bind an independent verifier receipt.
5. The installed `dgc` talk/run path imports top-level `scripts`, while packaging
   excludes `scripts*`; the estate map records the exact failing probe.
6. Sarathi's source projections keep `wake_loop_active` and `alive_claim` false.
7. Local commit `e7856fed9` contains additional Sarathi work but is not on main
   and is not product truth.
8. At this snapshot, the proposed next work was the three closure packets in
   `07_BACKLOG.md`, starting with a typed, lease-backed, budgeted real effect and
   receipt. Current work must be re-established from code, PR state, and track
   ownership rather than inferred from this history.

This build-history file makes no current process claim; run onboarding and read
Live Ops for that state. Reproduce the landed, packaging, and source-tree
observations above with the estate map's Sections 8–9 and these anchors:
`scripts/holon_run.py:32-87`, `pyproject.toml:58-64`,
`dharma_swarm/terminal_commands/agents.py:101-127`, and
`dharma_swarm/holon_system/sarathi/gateway.py:15-24`. Reproduce the local-only
branch claim with `git branch -a --contains e7856fed9`.

## Non-negotiable boundaries

- Repo source owns implementation; `~/.dharma` owns mutable runtime evidence.
- `~/.hermes` is a parallel product/compatibility boundary, not Sarathi's body.
- Reuse the existing provider, Living Agent Kernel, authority, A2A, and receipt
  owners; do not introduce another runtime stack.
- A process, heartbeat, identity, pulse, or model response cannot promote its
  own liveness claim.
- Target rule: only the proposed `DurableServiceProven` level should permit an
  alive flag. Current two-boolean/tmux promotion code does not yet enforce it
  (`dharma_swarm/holon_system/observability/proof_gates.py:6-11`;
  `scripts/runtime/codex_composer_wake_loop.py:1213-1257`).
