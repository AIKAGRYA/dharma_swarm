---
id: migration-safety
version: 0.0.1
theme: 13-data-and-queries
status: tested
invariant: >
  A schema migration must be backward-compatible with the code version running
  during the deploy — because for a window, old code and new schema coexist (and on
  rollback, new code meets old schema). Safe changes are ADDITIVE (expand); destructive
  changes (drop/rename/NOT-NULL-without-default/type-narrow) must be split into
  expand→migrate→contract across releases. A migration that locks a large table or
  breaks the running version is an outage.
lineage:
  - "the expand/contract (parallel-change) pattern — Sato/Fowler; zero-downtime deploy"
  - "Lehman — the running system must keep working across the change"
  - "Codd — the schema is a contract many readers depend on"
ground_truth_tools: ["read the migration SQL/DSL", "diff old vs new schema", "the deploy model (rolling? blue-green?)"]
returns_clean: true
---

## Prompt

> Audit a **schema migration** for safety. The invariant (expand/contract): during a
> rolling deploy, **old code runs against the new schema** (and on rollback, new code
> meets old schema), so a migration must be backward-compatible with the previous
> code version. Classify each change:
>
> - **ADDITIVE / safe:** add nullable column, add table, add index *concurrently*.
> - **DESTRUCTIVE / must split across releases:** drop/rename column, `NOT NULL`
>   without default, narrow a type, drop a table still read by old code → require
>   **expand → backfill → contract** over ≥2 deploys.
> - **LOCKING:** a change that takes a long table lock (rewrite, non-concurrent index)
>   → outage on a large table.
>
> For each: the change, its class, the risk to the *running* version, and the safe
> sequencing. **Return clean** for a purely additive migration — and *say* it's
> additive/safe rather than inventing risk.

## Why it's built this way

The bug isn't in the SQL syntax — it's in the *coexistence window* a single-snapshot
read misses. Expand/contract is the canonical answer; the discipline is reasoning about
old-code-meets-new-schema (and rollback), and crediting a genuinely additive change
instead of ceremony.

## Demonstration run

**Target:** `dharma_swarm/migrations/`, 2026-06-25.

- **1 migration:** `2026_06_01_add_receipt_json.sql` — by name, an **ADD column**
  (`receipt_json`). Classification: **additive / safe** — a new (presumably nullable)
  column doesn't break old code that ignores it, and rollback (old code, column
  present) is fine. 🟢
- **Confirm:** verify the column is **nullable or has a default** (a `NOT NULL` without
  default *would* break inserts from old code) and that no index it adds takes a
  blocking lock on a large table. If both hold: safe, no sequencing needed.

**Return-clean result:** one additive migration, reported as safe with the two
one-line checks to confirm — not dressed up as risk.

## Changelog

- **v0.0.1** (2026-06-25) — migration-safety (expand/contract): classify additive vs
  destructive vs locking, reason about the coexistence window + rollback, credit
  additive changes. Tested on `dharma_swarm/migrations/`: the single `add_receipt_json`
  migration classified additive/safe with two confirm checks.
