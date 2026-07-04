# NĀGA-IR Current State Evidence

Generated at: 2026-07-03T15:45Z

Repo root: `/Users/dhyana/dharma_swarm`

## Source brief

The user-provided brief is stored at:

`/Users/dhyana/.codex/attachments/19203ab2-e1ef-458d-81e7-67ba7b54ae37/pasted-text-1.txt`

The brief says the target outline is `specs/naga_ir/core.md`, but the current checkout had an empty `specs/naga_ir/` directory before this Codex turn wrote the PR #2 draft files.

## Current files

Confirmed present:

- `specs/naga_ir/core.md`
- `specs/naga_ir/receipt_wire.md`
- `specs/naga_ir/witness_mesh.md`
- `docs/plans/NAGA_IR_TRUST_SUBSTRATE_SEED_20260703.md`
- `spec-forge/naga-ir/NAGA_IR_TRUST_SUBSTRATE_SEED_20260703.md`
- `dharma_swarm/coalgebra.py`, 536 lines
- `docs/telos-engine/01_SATTVA_VISION.md`, 389 lines

Confirmed absent in this checkout:

- `scripts/governance/assurance_boundary.py`
- `packages/telos-kernel/`

Observed package directory:

- `packages/telos-gatekeeper/`

## Review implications

The spec drafts must not claim that `assurance_boundary.py` or `packages/telos-kernel/` are present implementation dependencies in this checkout. They may refer to those names only as prior-context or planned integration targets until a later PR lands matching files.

The spec may claim compatibility with `dharma_swarm/coalgebra.py` only at the level of shape and future integration. It must not claim that a NĀGA reconciler or receipt emitter already exists.

The spec may use `docs/telos-engine/01_SATTVA_VISION.md` as local governance context, but it must not make the welfare formula a formal proof obligation without a separate receipt or verifier.

## Persistent witness

`scripts/start_palantir_pilot_a2a_worker_tmux.sh` was run. `scripts/status_palantir_pilot_a2a_worker_tmux.sh` reported:

- `status=running`
- heartbeat file: `/Users/dhyana/.dharma/a2a_bus/worker_heartbeats/palantir-pilot.json`
- fresh heartbeat observed at `2026-07-03T15:44:46Z`

## Git state

The branch is `agent/magpie-seed`. The worktree already had many unrelated modified and untracked files before the NĀGA spec draft files were added. This task does not revert or normalize those unrelated changes.
