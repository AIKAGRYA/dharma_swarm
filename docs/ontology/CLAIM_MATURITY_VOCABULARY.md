# Claim Maturity Vocabulary

Status: advisory vocabulary for the anti-slop promotion membrane.

This document separates two things agents often collapse:

1. **Workflow status** — where a track sits in the portfolio.
2. **Claim maturity** — what the evidence is strong enough to say.

A track may be `ACTIVE` and still have only `declaration-complete` evidence.
A track may pass all manifest criteria and still be forbidden from saying
"runtime verified", "loop closure complete", or "system shippable".

## Workflow status

These describe portfolio movement only:

| Status | Meaning |
| --- | --- |
| `ACTIVE` | admitted work currently in the portfolio |
| `PAUSED` | admitted work intentionally not moving |
| `SHIPPED` / `CLOSED` | moved out of active work after an accepted closeout |
| `SUPERSEDED` | replaced by another track or surface |
| `BLOCKED` | cannot move without an external decision or failed prerequisite |

Workflow status is owned by `docs/governance/ACTIVE_TRACK.yaml` and projected by
`check_track_status.py` / `make onboard`.

## Claim maturity

These describe evidence strength only:

| Maturity | Evidence floor | Allowed claim |
| --- | ---: | --- |
| `file present` | 0 | a named file exists |
| `declaration-complete` | 1 | manifest/prose criteria are present |
| `command-receipted` | 2 | a command, merge, or landed commit is receipted |
| `behavior-verified` | 3 | a positive behavior test passes |
| `adversarial-verified` | 4 | a failure-mode / negative test passes |
| `runtime-verified` | 5 | a runtime/integration receipt proves the named path |
| `independently-reproduced` | 6 | another role/system reproduced the result |
| `promoted` | 7 | reproduction plus rollback/caveats and owner signoff |

## Forbidden overclaim language

Unless the maturity floor supports it, agents must downgrade these phrases:

- `loop closure complete`
- `runtime verified`
- `system shippable`
- `platform complete`
- `truth reconciled`
- bare `shippable` when the proof is only file/prose-backed

Use `declaration-complete` or `manifest-complete` when the evidence is only
`file_exists` / `file_contains`.

## Operator rule

Promotion language must be conjunctive. One strong criterion must not hide weak,
malformed, or unsupported criteria elsewhere in the same track. The conservative
claim is bounded by the weakest required criterion, plus any explicit caveats.
