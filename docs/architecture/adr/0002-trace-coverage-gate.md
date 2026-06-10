# ADR-0002: Trace Coverage Gate Policy

Date: 2026-05-28
Status: Accepted

## Context

The active track `trace-identity-coverage-2026-05` closes the Trace Attractor
causal spine and wires trace identity into new operator-facing records. The
current substrate has `CorrelationContext`, DGC trace-attractor wiring,
operator brief persistence, BoardEvent defaults, Sakshi provenance defaults,
guardian soft coverage, and a witness report.

The unresolved policy question is whether missing `trace_id` should become a
hard CI or runtime gate immediately. That would make the substrate stricter, but
it would also risk blocking legacy, synthetic, migration, and archaeology
records before the new trace-bearing surfaces have enough witness evidence.

## Decision

Missing trace identity remains a DEGRADED finding, not a hard gate, for this
track.

A future hard gate may block only new value-bearing runtime records on native
surfaces when a live `CorrelationContext.trace_id` exists and the record omits
trace metadata. This applies to new operator-brief artifacts, BoardEvent records,
and Sakshi provenance records created by current runtime flows.

The hard gate must not retroactively fail legacy records, synthetic fixtures,
archaeology imports, migration aliases, or records created outside a live
correlation context.

The hard gate may be enabled only by an explicit follow-up change that includes
witness evidence, scoped tests, and a governance manifest update. This ADR does
not authorize an automatic CI flip from warning to blocking.

## Consequences

The current guardian trace-coverage check stays load-bearing as a soft signal.
Operators can inspect DEGRADED findings without blocking unrelated work.

The next hardening step is narrower: prove the value-bearing runtime path emits
trace metadata consistently, then add an explicit hard-gate change with tests
for that path.

This keeps the track shippable while preserving the policy boundary: substrate
identity is mandatory as telos, but enforcement tightens only where the runtime
contract is proven.
