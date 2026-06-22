# Track Health — quality-aggregated, sign-off-gated grade

Generated: 2026-06-22T15:48:18+00:00

Projects two owners: `active_track_evidence.json` (file/presence grade) and `track_signoffs/*.signoff.json` (independent grader attestations). Read-only — it grades, it does not own track truth.

**Sign-off quorum:** 3 independent graders across 2+ model families. Axes aggregated by median; attested-SHIPPABLE requires median wired>=3 AND proven>=3 AND a grader majority verdict of SHIPPABLE.

**Graders this run:** track-grader-haiku, track-grader-opus, track-grader-sonnet

## Portfolio

- Track-mean score: **57.7** · objective coverage: **0.33** (cap 84.9)
- **Portfolio grade: F (57.7)**
- Attested-SHIPPABLE: ['provider-routing-consolidation-2026-06', 'runtime-truth-reconciliation-2026-06', 'truth-graph-platform-2026-06']
- OVERSTATED (file-green, quorum withholds): ['composer-holon-spine-longrun-2026-06', 'runtime-truth-nats-2026-06']

## Tracks

| Track | File | Sign-offs | Score | Grade | Consensus | Attested? |
|---|---|---|---|---|---|---|
| `runtime-truth-reconciliation-2026-06` | 11/11 ✓ | 3 (claude-haiku/claude-opus/claude-sonnet) | 70.0 | C | SHIPPABLE | ✅ |
| `runtime-truth-nats-2026-06` | 2/2 ✓ | 3 (claude-haiku/claude-opus/claude-sonnet) | 51.2 | F | OVERSTATED | ⚠️ overstated |
| `runtime-truth-spine-adoption-2026-06` | 7/8 | 3 (claude-haiku/claude-opus/claude-sonnet) | 58.8 | F | IN_PROGRESS | — |
| `loop-closure-2026-06` | 10/11 | 3 (claude-haiku/claude-opus/claude-sonnet) | 43.8 | F | IN_PROGRESS | — |
| `truth-graph-platform-2026-06` | 15/15 ✓ | 3 (claude-haiku/claude-opus/claude-sonnet) | 70.0 | C | SHIPPABLE | ✅ |
| `composer-holon-spine-longrun-2026-06` | 6/6 ✓ | 3 (claude-haiku/claude-opus/claude-sonnet) | 43.8 | F | OVERSTATED | ⚠️ overstated |
| `provider-routing-consolidation-2026-06` | 7/7 ✓ | 3 (claude-haiku/claude-opus/claude-sonnet) | 66.2 | D | SHIPPABLE | ✅ |

### `runtime-truth-reconciliation-2026-06` — C
- median axes: wired=3 · proven=3 · live=3 · world_class=3 · balanced=1
- consensus verdict: **SHIPPABLE** · dissent: ['track-grader-sonnet:IN_PROGRESS']

### `runtime-truth-nats-2026-06` — F
- median axes: wired=2 · proven=3 · live=1 · world_class=2 · balanced=1
- consensus verdict: **OVERSTATED** · dissent: ['track-grader-haiku:SHIPPABLE']
- note: file-grade says SHIPPABLE but quality quorum does NOT attest it (OVERSTATED): presence passed, capability not proven live

### `runtime-truth-spine-adoption-2026-06` — F
- median axes: wired=2 · proven=3 · live=2 · world_class=3 · balanced=1
- consensus verdict: **IN_PROGRESS**

### `loop-closure-2026-06` — F
- median axes: wired=2 · proven=2 · live=1 · world_class=2 · balanced=1
- consensus verdict: **IN_PROGRESS** · dissent: ['track-grader-sonnet:OVERSTATED']

### `truth-graph-platform-2026-06` — C
- median axes: wired=3 · proven=3 · live=3 · world_class=3 · balanced=1
- consensus verdict: **SHIPPABLE** · dissent: ['track-grader-sonnet:IN_PROGRESS']

### `composer-holon-spine-longrun-2026-06` — F
- median axes: wired=2 · proven=2 · live=1 · world_class=2 · balanced=1
- consensus verdict: **OVERSTATED** · dissent: ['track-grader-haiku:SHIPPABLE']
- note: file-grade says SHIPPABLE but quality quorum does NOT attest it (OVERSTATED): presence passed, capability not proven live

### `provider-routing-consolidation-2026-06` — D
- median axes: wired=3 · proven=3 · live=2 · world_class=3 · balanced=1
- consensus verdict: **SHIPPABLE** · dissent: ['track-grader-sonnet:IN_PROGRESS']
