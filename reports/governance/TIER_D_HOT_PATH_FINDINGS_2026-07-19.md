# Tier-D Findings — Hot-Path Spine Work Requiring an Operator Packet

**Date:** 2026-07-19 · **Author:** coherence-weave session (autonomous run)
**Status:** FINDINGS ONLY — no hot file was edited. Each item below names the
evidence, the proposed fix, and exactly why it is operator-gated (every listed
surface matches `HOT_PATH_PATTERNS` in `scripts/runtime/pr_merge_control.py`
and therefore trips the AgentOps packet-scope gate).

Context: the non-hot prerequisite work shipped this session as draft PRs —
observability for unfenced dispatches (#1056 finishing slice), the
self-modification and MCP surfaces joined to the spine (#1060, #1061), the
Episode Ledger schema (#1062), the widened store_sync projection (#1063), the
idempotency-key origin standard ADR-009 (#1064), and the trace front door
(#1065). The three items below are the hot-path continuations those slices
deliberately stopped short of.

---

## D1. Fail-CLOSED dispatch at the orchestrator fence

**Current state (cited):**
- The durable fence wraps the WHOLE provider call via `wrap_invoker`
  (`dharma_swarm/orchestrator.py:2538-2545`) and is documented fail-open:
  "Fail-open passthrough when store/identity is missing"
  (`orchestrator.py:2534`).
- The invoker's fail-open branches are: no capable store
  (`dharma_swarm/graph/durable_invoker.py:414-424`), incomplete identity
  (`:427-435`), begin raised (`:494-504` on PR #1056's branch), and
  begin-lost-unreclaimed (final return, stamped in #1056's `1c9caaf`).
- Fail-open is DELIBERATE doctrine: "dispatch must never break for lack of
  the store" (`durable_invoker.py:415-416`).

**Prerequisite now in place:** every unfenced dispatch is stamped
`unprotected_dispatch=True` with a reason (`no_capable_store`,
`incomplete_identity`, `idempotency_begin_failed`, `begin_lost_unreclaimed`)
once PR #1056 merges — the blind spot is countable fleet-wide.

**Proposed fix (data-driven, two steps):**
1. Measure: run the fleet ≥1 week post-#1056; aggregate
   `unprotected_dispatch` receipts by reason (the receipts land in
   `delegation_runs.receipt_json` via `persist_evidence_receipt`,
   `orchestrator.py:2560`).
2. Decide per reason: reasons with ~zero frequency can flip fail-closed
   cheaply (raise instead of passthrough); a high-frequency reason indicates
   a real store/identity availability gap that must be fixed FIRST or the
   flip converts silent risk into loud outage.

**Why operator-gated:** edits `orchestrator.py` (hot; owned by
`dharmagraph-engine-2026-07`); changes dispatch availability semantics —
the fail-open doctrine is an explicit operator decision to reverse.
A related, larger slice — per-child-effect fencing instead of one fence
around the whole AgentRunner loop — is noted in the prior session's
lessons and is NOT proposed here.

## D2. Origin-minted idempotency key wired into dispatch

**Current state (cited):**
- ADR-009 (PR #1064) establishes the origin key:
  `TaskIntent.idempotency_key` minted at intent creation
  (`dharma_swarm/intent_router.py`, `mint_intent_idempotency_key`).
- Dispatch identity today falls back to `idem_{run_id}` when no key is
  propagated (`dharma_swarm/spine/identity.py:82`) — under ADR-009 that
  fallback firing is a measurable propagation gap.
- The dispatch attributes already carry `idempotency_key` and
  `side_effect_key` (`orchestrator.py:2516-2517`).

**Proposed fix:** thread the origin key from the intent/task metadata into
`ensure_execution_identity` so `ExecutionIdentity.idempotency_key` carries
the ADR-009 origin key instead of the `idem_{run_id}` fallback; count
fallback firings (same observability-before-enforcement pattern as D1).
The `sek_` claim-key derivation is unaffected (fence role stays
content-addressed).

**Why operator-gated:** the wiring sites are `runtime_state.py` /
`orchestrator.py` / `runtime_lifecycle`-adjacent (hot); identity-field
semantics feed every receipt and idempotency row — a wrong propagation
changes dedup behavior fleet-wide.

## D3. Retire the `legacy_no_identity_allowed` escape hatch

**Current state (cited):**
- The flag defaults False but is explicitly enabled at
  `dharma_swarm/runtime_state.py:1054` (`"legacy_no_identity_allowed": True`)
  and threaded through record paths at `:1971,1986` and `:2116,2131`.
- The spine metric intentionally classifies this surface `legacy`
  (`tools/spine_adoption_metric.py:298-310`) — it is the last `legacy`
  surface in the 16-surface map (14 joined + 1 adapter-ready pending
  #1060/#1061 merges + this).

**Proposed fix:** inventory callers that reach the record paths without
identity (the invariant test named in the metric,
`fail_closed_without_identity_unless_flagged`, shows the intended end
state); migrate or explicitly quarantine each; then delete the flag and
let `require_for_dispatch` fail closed unconditionally.

**Why operator-gated:** `runtime_state.py` is hot AND the flag is listed in
the coherence backlog as "an operator decision" — deleting it is
irreversible for any still-dependent legacy producer; the inventory must
come first.

---

**Suggested sequencing:** D1-measure (already landing with #1056) → D2
(origin-key threading, gives D1's data cleaner identity) → D1-flip (per
reason) → D3 (retire the hatch once the map shows zero legacy producers).
Each step is its own packet with its own failing-first tests.
