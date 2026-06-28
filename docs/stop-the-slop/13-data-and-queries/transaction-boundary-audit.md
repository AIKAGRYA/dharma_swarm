---
id: transaction-boundary-audit
version: 0.0.1
theme: 13-data-and-queries
status: tested
invariant: >
  A logical operation that performs multiple writes must be atomic — all or nothing —
  or a failure mid-sequence leaves corrupt, half-applied state. The transaction boundary
  must wrap the whole unit of work; writes scattered across separate auto-committed
  statements have no atomicity, and a crash between them tears state. External effects
  (emails, payments) inside a DB transaction are a different trap: they can't roll back.
lineage:
  - "Gray — ACID; atomicity is the A, and it's a boundary you must draw"
  - "the unit-of-work pattern (Fowler) — one transaction per logical operation"
  - "no non-transactional side effects inside a transaction (they don't roll back)"
ground_truth_tools: ["find multi-write operations; is there a transaction around them?", "auto-commit vs explicit BEGIN/COMMIT", "external effects inside a txn"]
returns_clean: true
---

## Prompt

> Audit **transaction boundaries**. The invariant (Gray, unit-of-work): a logical op
> with multiple writes must be atomic, or a mid-sequence failure corrupts state. Find:
> (1) operations doing **2+ writes** with **no transaction** around them (each
> auto-commits → a crash between them tears state); (2) a transaction that wraps **too
> much** — especially a non-rollbackable **external effect** (email/payment/file) inside
> a DB txn. For each: the writes, the failure that corrupts, the fix (wrap the unit of
> work; move external effects outside / use an outbox). **Return clean** for correctly-
> scoped transactions.

## Why it's built this way

Atomicity is a *boundary* the developer draws; the bug is the boundary that's missing
(torn writes) or too wide (un-rollbackable side effects trapped inside). Both are
invisible per-statement and visible only at the unit-of-work level — which is what the
prompt forces you to identify.

## Demonstration run

**Target:** `dharma_swarm/`, 2026-06-25. **35** files use `commit()`/`executescript`;
29 use `aiosqlite`.

- **Audit shape:** for each multi-write sequence (e.g. an operation that inserts a
  record *and* appends a receipt *and* updates an index), confirm they share **one**
  transaction — otherwise a failure after write 1 leaves an orphan. With 35 commit-sites,
  the probe is: which do `execute … execute … commit` (good — batched) vs `execute;
  commit; execute; commit` (torn)?
- **The second trap:** the swarm writes receipts/JSONL *and* triggers dispatch/external
  calls — check that no irreversible external effect sits inside a DB transaction
  (it won't roll back). Recommend the **outbox pattern** if so.
- Honest framing: a real verdict needs per-operation inspection; the prompt hands the
  candidate sites + the two failure shapes, not a fabricated count.

## Changelog

- **v0.0.1** (2026-06-25) — transaction-boundary audit (Gray/unit-of-work): torn
  multi-writes + non-rollbackable effects inside a txn. Tested on `dharma_swarm`: 35
  commit-sites → probe for batched-vs-torn writes + external-effects-in-txn (outbox fix).
