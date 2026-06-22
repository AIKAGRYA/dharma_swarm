# Criterion smell report

Generated: 2026-06-22T20:48:50+00:00

Static lint of `ACTIVE_TRACK.yaml` completion criteria: would each criterion, *if it passed*, actually prove the capability? Read-only projection — it does not evaluate pass/fail (that is `check_track_status.py`).

**2 HIGH · 0 MED** smells across 7 active tracks.

| Track | criteria | smells | HIGH |
|---|---|---|---|
| `runtime-truth-reconciliation-2026-06` | 11 | 0 | 0 |
| `runtime-truth-nats-2026-06` | 3 | 2 | 2 |
| `runtime-truth-spine-adoption-2026-06` | 9 | 0 | 0 |
| `loop-closure-2026-06` | 11 | 0 | 0 |
| `truth-graph-platform-2026-06` | 15 | 0 | 0 |
| `composer-holon-spine-longrun-2026-06` | 7 | 0 | 0 |
| `provider-routing-consolidation-2026-06` | 7 | 0 | 0 |

## Findings

### HIGH

- **missing_owned_surface** · `runtime-truth-nats-2026-06` / `owned_surface:dharma_swarm/a2a/a2a_nats_contact.py` — declared owned surface 'dharma_swarm/a2a/a2a_nats_contact.py' does not exist on disk
- **missing_owned_surface** · `runtime-truth-nats-2026-06` / `owned_surface:dharma_swarm/a2a/a2a_core_contact.py` — declared owned surface 'dharma_swarm/a2a/a2a_core_contact.py' does not exist on disk
