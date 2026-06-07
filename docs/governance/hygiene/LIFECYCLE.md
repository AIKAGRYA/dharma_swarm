# Hygiene Lifecycle

Every pattern moves through one explicit stage:

| Stage | Meaning | Merge effect |
|---|---|---|
| `observed` | Seen in practice, detector may be manual. | None |
| `measured` | Detector exists and baseline can be trended. | None |
| `advisory` | Reviewers should consider it during PR review. | None unless a separate gate exists |
| `enforced` | A Semgrep rule, workflow, or script gate blocks regressions. | Blocking |
| `resolved` | Current baseline is clean, but the id remains active for relapse checks. | None |
| `archived` | Pattern is stale or obsolete and lives in `archive/`. | None |

## Promotion Criteria

A pattern can move to `enforced` only when all are true:

1. The detector is deterministic and cheap enough for CI.
2. False positives are below 5 percent across at least two review cycles.
3. The enforcement rule has a named owner and a rollback plan.
4. The pattern file points to the enforcement rule in `enforcement.rule`.
5. `ANTI_SLOP_RULES.md`, Semgrep, workflow, or a script gate owns the actual
   blocking behavior.

## Review Cadence

Every active pattern has `last_verified` and `next_review`. Stale patterns are
not silently deleted; they are either reverified, marked `resolved`, or moved to
`archive/` with `archived_reason` filled in.
