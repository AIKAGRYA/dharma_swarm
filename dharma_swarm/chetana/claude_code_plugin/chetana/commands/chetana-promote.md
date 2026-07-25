---
description: Promote a staged atom to trusted (gate-checked, axiom-signed).
argument-hint: "<staged_path_or_atom_id> [--auto-promote] [--confidence <0..1>]"
---

Run `python -m dharma_swarm.chetana.cli promote $ARGUMENTS` using the chetana python (resolution order in the chetana SKILL.md).

This crosses the trust boundary: the atom routes through `dharma_swarm.telos_gates.TelosGatekeeper` and is signed by `dharma_swarm.dharma_kernel.KernelGuard`. Only run it when the user has named a specific atom (or explicitly approved a batch) — never sweep-promote on your own initiative.

Outcomes — report which one occurred, with the gate rationale:
- **BLOCK** → atom moved to `~/.dharma/knowledge/quarantine/`. Report the blocking gate and reason; do not retry with tweaked flags to sneak it past.
- **WARN** → written with `review_status='staged'` — still needs human approval before trust. Say so explicitly.
- **ALLOW** → promoted to `~/.dharma/knowledge/wiki/concepts/`; with `--auto-promote` it is marked `auto_promoted`.

Provenance fields populated: `promoted_by`, `promoted_at`, `gate_check.{result, gates_*, rationale}`, `axiom_signature`, `review_status`.

Report format: `promote <atom>: <ALLOW|WARN|BLOCK> · gate rationale: <one line> · now at: <path>`.
