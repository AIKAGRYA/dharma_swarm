# ADR-009: Idempotency-Key Origin Standard

> **Date:** 2026-07-19
> **Status:** PROPOSED (awaiting operator ratification)
> **Decision:** A consequential intent mints **exactly one idempotency key at origin** (the moment the intent object is created), and every downstream layer **propagates** that key — none re-mints. New intent-carrying surfaces MUST carry an origin key from day one (enforced by the ADR-009 contract tests in `tests/test_intent_router.py`). The existing per-layer *claim/fence* keys (deterministic, content-addressed) are a **different role** and stay: a fence key answers "is this exact side effect already done?", an origin key answers "which request caused it?".

---

## Context

The repo grew (at least) five parallel idempotency-key schemes, each minted at a different layer:

| # | Scheme | Where minted | Form | Cite |
|---|--------|--------------|------|------|
| 1 | Board facade mint | board ingress | `idem_<hex>` via `_new_id("idem")` | `dharma_swarm/board/facade.py:96,180` |
| 2 | A2A send adapter | outbound adapter | `a2a_send:<stable_payload_hash(...)>` | `dharma_swarm/board/adapters/a2a_send_adapter.py:339` |
| 3 | Durable-invoker claim | dispatch fence | `sek_<sha256(side_effect_key)>` | `dharma_swarm/graph/durable_invoker.py` (`claim_idempotency_key`) |
| 4 | Spine identity default | identity mint fallback | `idem_<run_id>` | `dharma_swarm/spine/identity.py:82` |
| 5 | Diff-apply fence | self-mod apply | `sek_<sha256("self_mod:apply:...")>` | `dharma_swarm/diff_applier.py` (`_fence_claim_key`, PR #1060) |

Meanwhile the intent layer — where a consequential request is *born* (`dharma_swarm/intent_router.py` `TaskIntent`, re-exported via `dharma_swarm/holon_system/orchestration/intent.py`) — carried **no key at all**. Every layer below it therefore mints its own, and no key traces back to the originating request. That is the root of the proliferation: absent an origin key, each layer's mint is locally rational.

## The standard

Two distinct roles, named and kept separate:

1. **Origin key** (`intent_<hex16>`, minted by `mint_intent_idempotency_key()` in `intent_router.py`). One per intent *instance*, minted when the intent is created. Two submissions of the same text are two intents with two keys. Downstream layers thread it into `ExecutionIdentity.idempotency_key` (surfacing in receipts as `dispatch_idempotency_key`) and **never overwrite it**. Layer-4's `idem_<run_id>` fallback (`spine/identity.py:82`) is what fires when no origin key was propagated — under this standard that fallback becomes a *measurable gap*, not a design.

2. **Fence/claim key** (`sek_<sha256>`, content-addressed and deterministic). Minted *at the effect*, from the side-effect content, so that N dispatchers — including crash-requeued ones holding re-minted identities — race on the same `(idempotency_key, side_effect_key)` row. Schemes 3 and 5 are this role and are correct as-is. Scheme 2 is a hybrid (content-addressed origin for a send) and acceptable: it is minted at that effect's origin.

**Rules going forward:**

- New intent-shaped objects MUST carry an origin idempotency key minted at construction (default_factory, not caller discipline).
- Downstream layers accept and propagate origin keys; they mint only their own *fence* keys, using the `sek_` convention.
- Do NOT bulk-rewire schemes 1-5 in one pass; each rewire is its own reviewed slice with a failing-first propagation test.

## Enforcement

`tests/test_intent_router.py::TestIdempotencyKeyOrigin` — the contract: origin mint present, one key per mint, distinct keys across sub-tasks, key survives serialization (propagation, not re-mint). A new intent surface without an origin key fails review against this ADR.

## Options considered

| Option | Verdict |
|---|---|
| Content-address the origin key (same text → same key) | ✗ collapses two legitimate submissions into one; content-addressing is the *fence's* job at the effect, with effect-scoped inputs |
| Bulk-unify all 5 schemes now | ✗ five reviewed surfaces in one PR; violates one-concern-per-change; fence and origin roles would blur |
| **Origin mint at intent creation + propagate; fences stay content-addressed (CHOSEN)** | ✓ smallest true invariant; makes the `idem_<run_id>` fallback a measurable gap; leaves each rewire its own slice |
