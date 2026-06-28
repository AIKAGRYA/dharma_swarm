---
id: race-condition-audit
version: 0.0.1
theme: 19-concurrency
status: tested
invariant: >
  Shared mutable state crossed by concurrent paths is a bug until proven serialized.
  The defect is a read-modify-write (or check-then-act) on state reachable by two
  coroutines/threads with no lock, no atomicity, and no single-owner discipline.
  But concurrency is subtle: state that is write-once-at-init then read-only, or
  owned by a single task, is fine — flag the genuinely-shared mutation, not every
  global.
lineage:
  - "Lamport 1978 — happens-before; without an ordering edge, two events are concurrent"
  - "Dijkstra — critical sections & mutual exclusion (the semaphore)"
  - "the check-then-act / read-modify-write hazard (TOCTOU)"
ground_truth_tools: ["AST: module/instance mutable state mutated inside async/threaded paths", "lock/atomic coverage", "ThreadSanitizer-style reasoning"]
returns_clean: true
---

## Prompt

> Audit for **race conditions**. The invariant (Lamport): without an ordering edge,
> two accesses are concurrent; a read-modify-write or check-then-act on shared
> mutable state with no lock/atomicity is a race. **Discipline:** state that is
> write-once-at-init-then-read-only, or single-task-owned, is **not** a race — flag
> the genuinely-shared mutation, not every global.
>
> **Find:** shared mutable state (module globals, instance fields, caches) **mutated**
> on a path reachable by ≥2 coroutines/threads, with no `Lock`/atomic guard. For
> each: `file:line`, the state, the concurrent paths, the hazard (lost update?
> TOCTOU?), and the fix (lock the critical section / make it single-owner / use an
> atomic). Rank by how-hot and how-corrupting.
>
> **Confirm, don't assert:** recommend a stress/concurrency test or
> ThreadSanitizer-style run. **Return clean** where state is init-once or
> lock-guarded — and credit existing locks rather than re-flagging guarded state.

## Why it's built this way

Races are the hardest bug class to *see* statically and the easiest to *over-report*
(every global looks scary). The discipline is Lamport's distinction — is there an
ordering edge? — plus crediting init-once and lock-guarded state, so the output is
the few real hazards, not a wall of globals.

## Demonstration run

**Target:** `dharma_swarm/`, 2026-06-25. Heavily async (1,671 `async def`).

- **Surface:** ~**202** module-level mutable-global candidates; **1,671** async
  functions; but only **12** files use `asyncio.Lock`/`Semaphore`. That ratio is the
  headline: a large shared-mutable surface, heavy concurrency, sparse explicit
  locking.
- **Disciplined output (not "202 races"):** this is a **surface**, not a verdict.
  The audit must per-site classify each mutated global: write-once-at-import (safe),
  single-event-loop-owned (safe-ish in cooperative async), or genuinely
  concurrently-mutated (race). Cooperative asyncio reduces *thread* races but **not**
  await-interleaving races (a `check → await → act` across an await point is a TOCTOU).
  Priority probes: the 202 globals that are **written** inside an `async def` and read
  across an `await` — those are the real candidates. UNCONFIRMED until traced; flagged
  as surface, not fabricated as findings.

## Changelog

- **v0.0.1** (2026-06-25) — race audit (Lamport/Dijkstra/TOCTOU): flag genuinely-
  shared mutation incl. await-interleaving, credit locks/init-once, confirm via stress
  test. Tested on `dharma_swarm`: 202 mutable globals × 1,671 async / 12 lock-files =
  a real surface, reported as surface-to-trace (await-crossing writes first), not a
  fabricated count.
