# Forge Naming Boundary

Role: reference. The authoritative repo-level rule lives in
`docs/governance/SOVEREIGN_MANIFEST.md` under "Forge / Pudgala Naming
Boundary". This page explains the terms and points at concrete surfaces.

## Dharma Forge

`Dharma Forge` is the whole-swarm reality-reward and benchmark-hardening system.
It pits the swarm, candidate agents, and control arms against measured tasks,
external receipts, verifier loops, and arena-style benchmark runs. Its concrete
surfaces include `Dharma Forge / Hydra`, `Forge Reality Arena Hydra`, and the
`Forge Swarm Evolution Arena v0` runtime family.

Use this name for:

- whole-swarm benchmark and evolution runs
- external receipt pursuit and countersigned reality evidence
- candidate-vs-control arenas
- long-run Hydra patterns around swarm hardening

Canonical entry points include:

- `docs/ops/DHARMA_FORGE_HYDRA_ARCHAEOLOGY_2026-06-11.md`
- `docs/specs/forge_packets/FORGE_SWARM_EVOLUTION_ARENA_V0_MEASUREMENT_10H_LAUNCH.md`
- `scripts/runtime/forge_swarm_evolution_arena_v0_*`
- `tests/test_forge_swarm_evolution_arena_v0_*`

## Pudgala Autopoiesis Protostar

`Pudgala Autopoiesis Protostar` is the anti-slop governance quality mechanism.
It is not an arena, benchmark runner, Hydra, or external test system. It binds
claims to graded evidence and machine-verifiable receipts so file-existence
claims cannot masquerade as shipped work.

Use this name for:

- graded claim/evidence binding
- `min_evidence_grade` governance floors
- `VerifiedMachineReceipt` hash-chained machine receipts
- oracle-independence downgrades
- anti-slop quality gates and advisory reports

Canonical entry points include:

- `docs/governance/evidence_grades.yaml`
- `docs/governance/proposed_tracks/anti-slop-pudgala-autopoiesis-protostar-2026-06.yaml`
- `scripts/governance/check_claim_evidence_binding.py`
- `scripts/governance/check_track_status.py`
- `tests/test_claim_evidence_binding.py`

## Rule

If a surface runs the swarm against tasks, benchmarks, external receipts, or
candidate controls, it belongs to `Dharma Forge`.

If a surface grades whether a governance claim is backed by independent,
machine-checkable evidence, it belongs to `Pudgala Autopoiesis Protostar`.
