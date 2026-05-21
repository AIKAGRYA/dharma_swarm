# ADR-0002: Trace Coverage Gate — When Missing trace_id Becomes a Hard Blocker

**Status:** Proposed
**Date:** 2026-05-21
**Deciders:** @AmitabhainArunachala
**Track context:** Closes the only remaining blocker on `trace-identity-coverage-2026-05` (track completion criterion `hard_gate_policy_adr`)
**Supersedes:** none

---

## Context

The `trace-identity-coverage-2026-05` track wired native `CorrelationContext` propagation into three truth-bearing stores:

- `dharma_swarm/operator_brief/persistence.py:32` — reads `correlation.trace_id` when present, falls back to legacy synthetic alias
- `dharma_swarm/board/event_log.py:54` — `_current_trace_id()` default for `BoardEvent.trace_id`
- `dharma_swarm/sakshi/provenance_log.py:67` — `_current_trace_id()` default for `ProvenanceEntry.trace_id`

Plus a soft Guardian DEGRADED finding for operator-brief artifacts that lack `metadata.trace_id`:

- `dharma_swarm/operator_brief/watchdog.py:115` — `check_operator_brief_trace_coverage()`

Witness report at `reports/witness/2026-05-21-trace-identity-coverage.md` confirms code-level coverage and lists the focused-suite tests that pass (83 passed).

The track explicitly defers the hard-blocker policy to this ADR. The track's `non_goals` include *"Do not make missing trace_id a hard CI gate until the ADR is written."* This ADR is that decision.

## Empirical baseline (2026-05-21)

Live state at `~/.dharma/state/runtime.db`:

| Surface | Total rows | trace_id present | `correlation_context` native | Aliased / inferred | Missing |
|---|---|---|---|---|---|
| `artifact_records` (operator-brief outputs) | 547 | 543 (99.3%) | 0 (0.0%) | 543 (99.3% via legacy/inferred path) | 4 (0.7%) |
| `economic_events` | 32 | 0 (0.0%) | 0 (0.0%) | 0 | 32 (100%) |
| `event_log` (BoardStore) | 0 | — | — | — | — |
| `session_events` | 46,430 | n/a (no `trace_id` column) | — | — | — |

Two observations are load-bearing for the gate decision:

1. **Code-level wiring is universal across the three named stores; runtime-level uptake is not.** All future writes through these stores will carry `trace_id` and `trace_id_source` defaulting from `CorrelationContext`. But the existing record pool (547 artifact_records, 32 economic_events) is dominated by records written before native wiring or written outside a CorrelationContext scope.
2. **`trace_id_source` is the load-bearing field**, not `trace_id` itself. A row with `trace_id` present but `trace_id_source = ""` came from synthetic aliasing in `dharma_swarm/trace_attractor/readers.py`, not from a CorrelationContext-scoped dispatch. The Trace Attractor projection layer can synthesize a `trace_id` from row identity even when no native context existed — useful for legacy visibility, but it is *not* causal evidence in the L4-spec sense.

## Decision

**The gate is and remains SOFT (DEGRADED finding, not BLOCKER) until two empirical conditions hold simultaneously across `operator_brief.artifact_records`, `board.event_log`, and `sakshi.provenance_log`:**

1. **Native uptake floor:** ≥ 50% of NEW records written in the trailing 7 days have `trace_id_source = "correlation_context"`.
2. **Native uptake trend:** the trailing-7-day uptake percentage has been monotonically non-decreasing for at least 14 consecutive measurement points.

When both conditions hold, the Guardian finding is upgraded from `DEGRADED` to `BLOCKER` for operator-brief artifacts specifically, and the equivalent BLOCKER finding is introduced for `board.event_log` and `sakshi.provenance_log` records that participate in value-bearing flows.

Until the conditions hold, the gate remains soft. The Guardian DEGRADED finding writes to the report and logs a warning, per `dharma_swarm/guardian_crew.py:49` — it does not fail CI, does not block PRs, does not stop merges.

## Rationale

1. **Empirical condition over date-based gate.** A date-based gate ("hard-block on 2026-06-21") would fire whether or not the substrate is ready, producing either premature CI noise (if uptake is low) or false complacency (if uptake plateaus below 100%). An uptake-percentage gate ties the policy to the substrate's actual readiness.

2. **50% threshold matches the cost-of-mistake asymmetry.** A 100% threshold makes the gate unreachable in practice (legacy records, manual-trace inputs, and out-of-scope dispatch paths will always produce some non-native writes). A 0% threshold gates nothing. 50% is the inflection where blocking begins to filter signal from noise: by that point, the operator can see at a glance whether a missing `trace_id_source` represents a regression or just an unscoped dispatch.

3. **14-point non-decreasing trend prevents flapping.** Without a trend check, a one-day uptake spike could trigger gate-on / gate-off oscillation as later days regress. The 14-point requirement matches the track TTL window in `ACTIVE_TRACK.yaml` and matches the cron cadence implied by the `LEDGER_WATCHER` finding's natural sampling rate.

4. **`trace_id_source` distinguishes evidence from inference.** The L4 spec landed 2026-05-20 (`docs/plans/2026-05-20-l4-persistent-agent-spec-forge-master-plan.md`) is explicit: evidence chains must be substrate-native, not inferred. A synthetic alias is inference; a `correlation_context` source field is substrate evidence. Gating on `trace_id` presence alone would let inferred traces satisfy the gate; gating on `trace_id_source` requires real provenance.

5. **Three stores must clear together.** Gating only on `operator_brief.artifact_records` would let `board.event_log` and `sakshi.provenance_log` regress unobserved. The track wired all three; the gate must observe all three.

6. **Soft gate is the right default until the substrate metabolizes.** Per the active track's non-goal — *"Do not make missing trace_id a hard CI gate until the ADR is written"* — the operator already chose soft-first. This ADR codifies *when* soft becomes hard, without front-running readiness.

## Consequences

**Immediate (no implementation work required):**

- The existing DEGRADED finding stays as-is — it already writes to report and logs warning per `guardian_crew.py:49`.
- The active track `trace-identity-coverage-2026-05` flips to SHIPPABLE (this ADR was its sixth completion criterion).
- Operators reading the Guardian report will see a DEGRADED line about `operator_brief_trace_coverage` and will know that this is a soft gate by policy, not by oversight.

**Required follow-up work (separate tracks):**

- **CWT-track:** add equivalent DEGRADED checks for `board.event_log` and `sakshi.provenance_log` so the three stores are observed symmetrically. The CWT v0 collector (`scripts/runtime/cwt_collect.py`, commit `98ec4c43`) already inventories agent-level evidence; the trace-coverage scorecard dimension belongs there.
- **Telemetry plane:** add a `trace_coverage_history` table (or extend an existing one) that records the trailing-7-day uptake percentage per store, sampled at a fixed cadence (e.g. once per Guardian sweep). The 14-point trend check requires history; without history the trend cannot be evaluated.
- **CI flip:** when the empirical conditions hold, a single PR flips the `severity` field in `check_operator_brief_trace_coverage()` and equivalents from `"DEGRADED"` to `"BLOCKER"`, plus adds the gate to the docops or governance-all bundle. The flip is one-line per store, but should reference this ADR in the commit message.

**Risks:**

- The 50% / 14-point thresholds are operator-set; they have no independent justification beyond the rationale above. If a future operator finds they are too lax or too strict, they should be revised by a subsequent ADR rather than tweaked in-place.
- A long period with no records in a store (e.g. `board.event_log` shows 0 rows today) makes the uptake percentage either undefined or trivially 100%. The implementation should treat `total_rows = 0` as "not yet evaluable" rather than as a satisfied condition.

## Non-decisions

This ADR does NOT decide:

- Whether legacy records should be backfilled with synthetic `correlation_context` provenance. They should not, per the L4 spec's `inherit_success: false` lineage discipline. Legacy records keep their non-native provenance; new records earn native provenance through real CorrelationContext-scoped dispatch.
- Whether the Trace Attractor's synthetic alias path should be removed once native uptake clears the threshold. It should not. Legacy records still need projection. Alias path stays as a fallback for records that genuinely cannot be traced natively (cross-process boundaries, external integrations).
- The exact format of the per-store `trace_coverage_history` table. That's an implementation decision for the follow-up track.

## Open questions for the operator

None requiring a decision before this ADR is approved. The thresholds, trend window, and three-store-symmetry are all defensible from the empirical baseline. A reviewer who wants stricter or looser values should propose them via revision rather than block the ADR's status flip.

---

*This ADR completes the sixth completion criterion of `trace-identity-coverage-2026-05`. It does not introduce new code, new schema, or new runtime behavior. It encodes the operator's already-stated soft-first policy and specifies the empirical conditions that flip it to hard.*
