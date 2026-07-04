# ForgeRSILab Workspace Corral - 2026-07-04

Purpose: make the current Dharma Forge lane unambiguous without deleting
historical worktrees or unrelated user work.

## Canonical Active Lane

- Active track: `forge-rsi-lab-swebench-2026-07`
- Local worktree: `/Users/dhyana/ds_forge_spine_v0`
- Branch: `feat/rsi-lab`
- Head used for latest evidence: `569187fac07aa9d4bbc9ea670cc4d126a249ca44`
- Remote evidence conductor: `meghadharma:/root/ds_forge_spine_v0`
- Native worker candidate: `agni:/root/ds_forge_spine_v0`
- GitHub PR for `feat/rsi-lab`: none open at audit time.

## Historical / Reference Worktrees

These are not the active Forge lane. Keep them read-only unless an operator
explicitly reopens one as a new active track.

- `/Users/dhyana/ds_forge_nvidia_foundry_mvp_20260701` — historical NVIDIA-foundry exploration lane.
- `/Users/dhyana/ds_forge_prod_contracts_20260701` — historical production-contract lane.
- `/Users/dhyana/ds_forge_proving_ground_10_10_20260626` — historical ForgeProvingGround lane.
- `/Users/dhyana/ds_forge_proving_ground_droid_10_10_20260626` — historical droid ForgeProvingGround lane.
- `/Users/dhyana/ds_forge_v1_scoreboard` — historical Forge v1 scoreboard lane.
- `/Users/dhyana/ds-wt-arena-lane` — historical arena parity/control lane.

## Runtime Artifact Policy

- Source canon lives in git under `docs/ops/`, `docs/governance/`, `dharma_swarm/forge_v1/`, `scripts/runtime/forge_*.py`, `tests/test_forge_*.py`, and `reports/forge_rsi_lab/`.
- Large/noisy runtime logs remain in `~/.dharma/forge_v1` or `/root/.dharma/forge_v1` on the remote host.
- Git receives summarized closeouts, strict validated task rows, and human-readable receipts only.
- Do not commit provider keys, GitHub tokens, tmux logs with environment exports, taskbed SQLite files, cloned benchmark repos, or temporary validator work roots.

## Current Remote State

- Meghadharma completed `megha_pr_suite_controlsplit_auth_20260704T031305Z`; no active tmux or harvest process remained when checked after closeout.
- Agni had no active harvest tmux/process when checked; it remains the preferred host for exact-ID native grade packets.

## Next Open Forge Lane

One open Forge lane remains:

1. Run exact-ID grade-only native packets for:
   - `pytest-dev/pytest#14647`
   - `pytest-dev/pytest#14588`
   - `pytest-dev/pytest#14624`
2. Sync grade receipts into `reports/forge_rsi_lab/`.
3. Only then run a model-powered solver/evolution pass with explicit model/provider chain, budget controls, and E4 gating.
