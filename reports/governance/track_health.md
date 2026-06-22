# Track Health — quality-aggregated, sign-off-gated grade

Generated: 2026-06-22T19:49:23+00:00

Projects two owners: `active_track_evidence.json` (file/presence grade) and `track_signoffs/*.signoff.json` (independent grader attestations). Read-only — it grades, it does not own track truth.

**Reviewer policy (operator, 2026-06-22):** auditors must be Opus 4.8+ caliber (['claude-opus']); lower-tier sign-offs are recorded but do not count. **Quorum:** 3 independent floor-meeting graders. Axes aggregated by median; attested-SHIPPABLE requires median wired>=3 AND proven>=3 AND a grader majority verdict of SHIPPABLE.

**Graders this run:** opus-run-A, opus-run-B, opus-run-C

## Portfolio

- Track-mean score: **46.4** · objective coverage: **0.33** (cap 84.9)
- **Portfolio grade: F (46.4)**
- Attested-SHIPPABLE: ['provider-routing-consolidation-2026-06', 'runtime-truth-reconciliation-2026-06']
- OVERSTATED (file-green, quorum withholds): ['composer-holon-spine-longrun-2026-06', 'runtime-truth-nats-2026-06', 'truth-graph-platform-2026-06']

## Tracks

| Track | File | Sign-offs | Score | Grade | Consensus | Attested? |
|---|---|---|---|---|---|---|
| `runtime-truth-reconciliation-2026-06` | 11/11 ✓ | 3 (claude-opus) | 66.2 | D | SHIPPABLE | ✅ |
| `runtime-truth-nats-2026-06` | 2/2 ✓ | 3 (claude-opus) | 13.7 | F | OVERSTATED | ⚠️ overstated |
| `runtime-truth-spine-adoption-2026-06` | 7/8 | 3 (claude-opus) | 51.2 | F | IN_PROGRESS | — |
| `loop-closure-2026-06` | 10/11 | 3 (claude-opus) | 36.2 | F | IN_PROGRESS | — |
| `truth-graph-platform-2026-06` | 15/15 ✓ | 3 (claude-opus) | 55.0 | F | IN_PROGRESS | ⚠️ overstated |
| `composer-holon-spine-longrun-2026-06` | 6/6 ✓ | 3 (claude-opus) | 36.2 | F | OVERSTATED | ⚠️ overstated |
| `provider-routing-consolidation-2026-06` | 7/7 ✓ | 3 (claude-opus) | 66.2 | D | SHIPPABLE | ✅ |

### `runtime-truth-reconciliation-2026-06` — D
- median axes: wired=3 · proven=3 · live=3 · world_class=2 · balanced=1
- consensus verdict: **SHIPPABLE**

### `runtime-truth-nats-2026-06` — F
- median axes: wired=1 · proven=0 · live=0 · world_class=1 · balanced=1
- consensus verdict: **OVERSTATED**
- note: file-grade says SHIPPABLE but quality quorum does NOT attest it (OVERSTATED): presence passed, capability not proven live

### `runtime-truth-spine-adoption-2026-06` — F
- median axes: wired=2 · proven=3 · live=1 · world_class=2 · balanced=1
- consensus verdict: **IN_PROGRESS**

### `loop-closure-2026-06` — F
- median axes: wired=1 · proven=2 · live=1 · world_class=2 · balanced=1
- consensus verdict: **IN_PROGRESS** · dissent: ['opus-run-B:OVERSTATED']

### `truth-graph-platform-2026-06` — F
- median axes: wired=2 · proven=3 · live=2 · world_class=2 · balanced=1
- consensus verdict: **IN_PROGRESS**
- note: file-grade says SHIPPABLE but quality quorum does NOT attest it (OVERSTATED): presence passed, capability not proven live

### `composer-holon-spine-longrun-2026-06` — F
- median axes: wired=1 · proven=2 · live=1 · world_class=2 · balanced=1
- consensus verdict: **OVERSTATED** · dissent: ['opus-run-C:IN_PROGRESS']
- note: file-grade says SHIPPABLE but quality quorum does NOT attest it (OVERSTATED): presence passed, capability not proven live

### `provider-routing-consolidation-2026-06` — D
- median axes: wired=3 · proven=3 · live=2 · world_class=3 · balanced=1
- consensus verdict: **SHIPPABLE**
