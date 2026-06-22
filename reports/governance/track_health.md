# Track Health — quality-aggregated, sign-off-gated grade

Generated: 2026-06-22T19:40:12+00:00

Projects two owners: `active_track_evidence.json` (file/presence grade) and `track_signoffs/*.signoff.json` (independent grader attestations). Read-only — it grades, it does not own track truth.

**Reviewer policy (operator, 2026-06-22):** auditors must be Opus 4.8+ caliber (['claude-opus']); lower-tier sign-offs are recorded but do not count. **Quorum:** 3 independent floor-meeting graders. Axes aggregated by median; attested-SHIPPABLE requires median wired>=3 AND proven>=3 AND a grader majority verdict of SHIPPABLE.

**Graders this run:** track-grader-haiku, track-grader-opus, track-grader-sonnet

## Portfolio

- Track-mean score: **58.8** · objective coverage: **0.33** (cap 84.9)
- **Portfolio grade: F (58.8)**
- Attested-SHIPPABLE: (none)
- OVERSTATED (file-green, quorum withholds): (none)

## Tracks

| Track | File | Sign-offs | Score | Grade | Consensus | Attested? |
|---|---|---|---|---|---|---|
| `runtime-truth-reconciliation-2026-06` | 11/11 ✓ | 1 (claude-opus) | 70.0 | PROVISIONAL-C | SHIPPABLE | — |
| `runtime-truth-nats-2026-06` | 2/2 ✓ | 1 (claude-opus) | 58.8 | PROVISIONAL-F | OVERSTATED | — |
| `runtime-truth-spine-adoption-2026-06` | 7/8 | 1 (claude-opus) | 55.0 | PROVISIONAL-F | IN_PROGRESS | — |
| `loop-closure-2026-06` | 10/11 | 1 (claude-opus) | 47.5 | PROVISIONAL-F | IN_PROGRESS | — |
| `truth-graph-platform-2026-06` | 15/15 ✓ | 1 (claude-opus) | 70.0 | PROVISIONAL-C | SHIPPABLE | — |
| `composer-holon-spine-longrun-2026-06` | 6/6 ✓ | 1 (claude-opus) | 43.8 | PROVISIONAL-F | OVERSTATED | — |
| `provider-routing-consolidation-2026-06` | 7/7 ✓ | 1 (claude-opus) | 66.2 | PROVISIONAL-D | SHIPPABLE | — |

### `runtime-truth-reconciliation-2026-06` — PROVISIONAL-C
- median axes: wired=3 · proven=3 · live=3 · world_class=3 · balanced=1
- consensus verdict: **SHIPPABLE**
- note: below-capability-floor sign-offs recorded but NOT counted (policy: Opus 4.8+): track-grader-haiku (claude-haiku), track-grader-sonnet (claude-sonnet)
- note: below sign-off quorum (1/3 floor-meeting graders) — grade is provisional

### `runtime-truth-nats-2026-06` — PROVISIONAL-F
- median axes: wired=2 · proven=3 · live=2 · world_class=3 · balanced=1
- consensus verdict: **OVERSTATED**
- note: below-capability-floor sign-offs recorded but NOT counted (policy: Opus 4.8+): track-grader-haiku (claude-haiku), track-grader-sonnet (claude-sonnet)
- note: below sign-off quorum (1/3 floor-meeting graders) — grade is provisional

### `runtime-truth-spine-adoption-2026-06` — PROVISIONAL-F
- median axes: wired=2 · proven=3 · live=1 · world_class=3 · balanced=1
- consensus verdict: **IN_PROGRESS**
- note: below-capability-floor sign-offs recorded but NOT counted (policy: Opus 4.8+): track-grader-haiku (claude-haiku), track-grader-sonnet (claude-sonnet)
- note: below sign-off quorum (1/3 floor-meeting graders) — grade is provisional

### `loop-closure-2026-06` — PROVISIONAL-F
- median axes: wired=2 · proven=2 · live=2 · world_class=2 · balanced=1
- consensus verdict: **IN_PROGRESS**
- note: below-capability-floor sign-offs recorded but NOT counted (policy: Opus 4.8+): track-grader-haiku (claude-haiku), track-grader-sonnet (claude-sonnet)
- note: below sign-off quorum (1/3 floor-meeting graders) — grade is provisional

### `truth-graph-platform-2026-06` — PROVISIONAL-C
- median axes: wired=3 · proven=3 · live=3 · world_class=3 · balanced=1
- consensus verdict: **SHIPPABLE**
- note: below-capability-floor sign-offs recorded but NOT counted (policy: Opus 4.8+): track-grader-haiku (claude-haiku), track-grader-sonnet (claude-sonnet)
- note: below sign-off quorum (1/3 floor-meeting graders) — grade is provisional

### `composer-holon-spine-longrun-2026-06` — PROVISIONAL-F
- median axes: wired=2 · proven=2 · live=1 · world_class=2 · balanced=1
- consensus verdict: **OVERSTATED**
- note: below-capability-floor sign-offs recorded but NOT counted (policy: Opus 4.8+): track-grader-haiku (claude-haiku), track-grader-sonnet (claude-sonnet)
- note: below sign-off quorum (1/3 floor-meeting graders) — grade is provisional

### `provider-routing-consolidation-2026-06` — PROVISIONAL-D
- median axes: wired=3 · proven=3 · live=2 · world_class=3 · balanced=1
- consensus verdict: **SHIPPABLE**
- note: below-capability-floor sign-offs recorded but NOT counted (policy: Opus 4.8+): track-grader-haiku (claude-haiku), track-grader-sonnet (claude-sonnet)
- note: below sign-off quorum (1/3 floor-meeting graders) — grade is provisional
