---
id: deadlock-lock-order
version: 0.0.1
theme: 19-concurrency
status: tested
invariant: >
  Deadlock requires all four Coffman conditions; the one you control is circular wait —
  break it by acquiring locks in a single global order, everywhere. Two code paths that
  take locks A→B and B→A can deadlock under interleaving. Also: never hold a lock across
  an await/blocking call you don't control (lock + I/O = held-lock latency and deadlock
  risk). A consistent lock order is a provable property, not a hope.
lineage:
  - "Coffman 1971 — the four deadlock conditions; deny circular wait"
  - "Dijkstra — resource hierarchy / ordered acquisition (dining philosophers)"
  - "don't hold a lock across I/O — lock scope must be minimal"
ground_truth_tools: ["find multi-lock acquisitions; check global order consistency", "locks held across await/blocking calls", "lock-ordering lints"]
returns_clean: true
---

## Prompt

> Audit **lock ordering / deadlock risk**. The invariant (Coffman, Dijkstra): deny
> circular wait by acquiring every lock in one global order. Find: (1) code paths that
> acquire **2+ locks** — do they all use the same order? An A→B here and B→A there is a
> deadlock. (2) any lock **held across an `await` / blocking I/O** — minimize scope.
> For each: the paths, the inconsistency, the fix (impose an order; shrink the critical
> section). **Return clean** if there's a single consistent order and locks wrap only
> CPU-bound critical sections. Single-lock code can't deadlock on order — don't flag it.

## Why it's built this way

Deadlock is a property of *order across paths*, invisible in any single function;
Coffman/Dijkstra give the cure (one global order). The second rule — no lock across I/O
— is where async code quietly deadlocks or stalls. The discipline is checking
multi-lock paths for order consistency, not flagging every lock.

## Demonstration run

**Target:** `dharma_swarm/`, 2026-06-25. **15** files use `Lock`/`RLock`/`Semaphore`.

- **Disciplined scope:** single-lock files (most of the 15) **cannot** deadlock on
  order — excluded. The audit targets the subset acquiring **2+ locks** in one path
  (the genuine circular-wait candidates) and any `async with lock:` that wraps an
  `await` on network/subprocess (held-lock-across-I/O).
- **Output:** for each multi-lock path, list the acquisition order and confirm it's
  globally consistent; for each lock-across-await, recommend moving the I/O outside the
  critical section. With only 15 lock-files and cooperative asyncio, the realistic
  result is a **short, specific** list — likely return-clean-leaning — not a deadlock
  scare. Confirm with a lock-order lint or a stress test.

## Changelog

- **v0.0.1** (2026-06-25) — deadlock/lock-order audit (Coffman/Dijkstra): global-order
  consistency on multi-lock paths + no-lock-across-I/O, exclude single-lock code. Tested
  on `dharma_swarm`: 15 lock-files → scoped to the multi-lock subset, short specific
  list expected.
