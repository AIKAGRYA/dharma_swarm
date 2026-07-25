---
id: n-plus-one-query-scan
version: 0.0.1
theme: 13-data-and-queries
status: tested
invariant: >
  A database round-trip inside a loop over rows is O(n) trips where 1 (a join or a
  WHERE-IN batch) would do — the canonical ORM performance bug. But "a query in a
  loop body" is NOT automatically n+1: a single query whose RESULTS you iterate is
  fine. The defect is issuing a NEW query PER iteration. Distinguish the two before
  flagging, and confirm against query logs.
lineage:
  - "Codd 1970 — the relational model; the join is the set operation, not a loop"
  - "the ORM lazy-loading anti-pattern (Fowler, PoEAA — lazy load surprises)"
  - "route to ground truth: query logs / EXPLAIN, not just static shape"
ground_truth_tools: ["AST: DB call inside a loop body", "query logs / echo=True", "EXPLAIN for the suspected join"]
returns_clean: true
---

## Prompt

> Scan for **N+1 query** patterns. The invariant (Codd): the join is a set
> operation; a query issued **per row** in a loop is O(n) round-trips where one
> batched query (JOIN / WHERE id IN (...)) suffices. **Critical discipline:**
> distinguish a genuine N+1 (a *new* query each iteration) from a single query whose
> results you iterate — the latter is fine and must not be flagged.
>
> **For each candidate:** `file:line` of the loop + the in-loop query, whether it's
> a *new* query per iteration (N+1) or result iteration (OK), the table/relation,
> and the fix (JOIN, eager-load, or a single `WHERE IN` batch). Rank by loop size ×
> per-call latency.
>
> **Confirm, don't assume:** recommend enabling query logging / `EXPLAIN` to verify
> trip count before refactoring. **Return clean** if every DB call in a loop is
> actually single-query-iteration.

## Why it's built this way

The naive scan greps "query inside for-loop" and floods you with false positives —
result iteration looks identical to N+1 statically. The discipline is the
**distinction** (new-query-per-iter vs iterate-results) plus routing to the query
log for proof, because trip count is the ground truth, not source shape.

## Demonstration run

**Target:** `dharma_swarm/`, 2026-06-25. Tool: AST loop+DB-call scan.

- **False positives (correctly NOT flagged):** `ontology_hub.py:610` /`:622` —
  `for row in self._conn.execute("SELECT * FROM objects").fetchall()`. This is **one**
  query, results iterated. Not N+1. A naive scanner flags it; this one clears it.
- **Real candidate:** `dharma_context_mcp.py:442` — `conn.execute("DELETE FROM
  code_chunks WHERE file_path = ?", (fpath,))` appears within a per-file loop →
  **one DELETE per file = N+1 writes.** Fix: a single `DELETE ... WHERE file_path IN
  (?, ?, …)` batch (or a temp-table join) — confirm by counting statements with
  `echo`/query log first.

**Verdict:** of the loop+DB candidates, the `ontology_hub` ones are benign result
iteration; the `dharma_context_mcp` per-file DELETE is the genuine N+1 to batch.
Confirm trip count via query logging before changing.

## Changelog

- **v0.0.1** (2026-06-25) — N+1 scan with the key discipline: separate new-query-
  per-iteration from result-iteration (the #1 false-positive source) and route to
  query logs/EXPLAIN for proof. Tested on `dharma_swarm/`: cleared `ontology_hub`
  (single query iterated), flagged `dharma_context_mcp:442` (per-file DELETE).
