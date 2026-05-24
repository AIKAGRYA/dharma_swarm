# ADR-0002: Trace Identity Coverage Gate Policy

**Status:** Proposed
**Date:** 2026-05-21
**Deciders:** @AmitabhainArunachala
**Track context:** Completion criterion for `trace-identity-coverage-2026-05`

---

## Context

The `trace-identity-coverage-2026-05` track added native trace identity
propagation to three substrate stores:

- **BoardStore event_log** — `_current_trace_id()` defaults from
  `CorrelationContext.trace_id` (`dharma_swarm/board/event_log.py:53`).
- **Sakshi provenance_log** — same pattern
  (`dharma_swarm/sakshi/provenance_log.py:66`).
- **Operator Brief watchdog** — `check_operator_brief_trace_coverage()`
  emits DEGRADED findings for artifacts missing `metadata.trace_id`
  (`dharma_swarm/operator_brief/watchdog.py:111`).

All three stores now inherit trace metadata from `CorrelationContext` when
it exists. Legacy records that predate the propagation or run outside a
correlation scope produce empty `trace_id` fields.

The question this ADR resolves: **when should missing trace identity
become a hard CI gate (BLOCKER) vs remaining a soft diagnostic
(DEGRADED)?**

## Decision

**Missing trace identity remains DEGRADED (soft warning) for now.
It does NOT become a hard CI gate.**

### Rationale

1. **Coverage is incomplete by design.** Not all code paths run inside a
   `CorrelationContext` scope. CLI commands, cron jobs, and manual
   operator actions legitimately produce records without trace_id. Making
   missing trace_id a hard blocker would fail CI on valid workflows.

2. **The watchdog already surfaces the gap.** `check_operator_brief_trace_coverage()`
   counts artifacts missing trace_id and reports them as DEGRADED findings
   in Guardian output. This is visible in `make onboard` drift triage.
   The information is available without gating.

3. **No consumer requires trace_id yet.** Trace identity enables
   cross-store correlation (BoardStore → Sakshi → OperatorBrief for the
   same request). No production consumer currently queries by trace_id.
   Enforcing presence before demand exists is premature.

4. **Graduated enforcement is safer.** The path to a hard gate is:
   - Phase 1 (current): DEGRADED — soft warning, no CI impact
   - Phase 2 (future): DEGRADED with metric — track coverage % over time
   - Phase 3 (future): BLOCKER for new code paths — require trace_id in
     newly added store writes (grandfathering existing paths)
   - Phase 4 (future): BLOCKER for all paths — only after coverage
     reaches a threshold (e.g., >90%) and escape hatches exist for
     legitimate untraced writes

### Conditions for Escalation to BLOCKER

The gate should be revisited and potentially escalated when ANY of these
conditions are met:

- A production consumer (dashboard, API, CLI) ships that queries by
  trace_id and produces incorrect results from missing data.
- Coverage metrics show >80% of new writes carry trace_id (indicating
  the ecosystem has organically adopted it).
- A broken register item is filed citing missing trace_id as a root
  cause of a real debugging failure.

## Consequences

- Guardian continues to report DEGRADED findings for missing trace_id.
  No CI gate change.
- Developers are encouraged (not required) to wrap new store writes in
  `CorrelationContext` scope when a meaningful trace context exists.
- The `trace_id_source` field (already present in BoardStore and Sakshi)
  distinguishes "inherited from CorrelationContext" vs "empty — no context
  available," preserving audit trail for future coverage analysis.
- This ADR satisfies the `hard_gate_policy_adr` completion criterion of
  the active track without introducing a premature enforcement mechanism.

## Non-Goals

- This ADR does not add new code. It is a policy decision.
- It does not retroactively require trace_id on existing records.
- It does not close or modify any broken register item.

## References

- `dharma_swarm/correlation_context.py` — CorrelationContext class
- `dharma_swarm/board/event_log.py` — BoardStore trace propagation
- `dharma_swarm/sakshi/provenance_log.py` — Sakshi trace propagation
- `dharma_swarm/operator_brief/watchdog.py` — trace coverage check
- `reports/witness/2026-05-21-trace-identity-coverage.md` — witness report
- `docs/governance/ACTIVE_TRACK.yaml` — track definition
