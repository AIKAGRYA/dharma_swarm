---
description: Promote a staged atom to trusted (gate-checked, axiom-signed).
argument-hint: "<staged_path_or_atom_id> [--auto-promote] [--confidence <0..1>]"
---

Run `python -m dharma_swarm.chetana.cli promote $ARGUMENTS` using the chetana venv.

The atom routes through `dharma_swarm.telos_gates.TelosGatekeeper` and is signed by `dharma_swarm.dharma_kernel.KernelGuard`. On BLOCK the atom moves to quarantine. On WARN it's written with `review_status='staged'` (still needs human approval before trust). On ALLOW with `--auto-promote` it's marked `auto_promoted`.

Provenance fields populated:
- `promoted_by`, `promoted_at`, `gate_check.{result, gates_*, rationale}`, `axiom_signature`, `review_status`
