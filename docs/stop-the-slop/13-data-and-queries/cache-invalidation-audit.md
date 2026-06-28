---
id: cache-invalidation-audit
version: 0.0.1
theme: 13-data-and-queries
status: tested
invariant: >
  Every cache needs a correct, bounded invalidation — staleness is a correctness bug,
  and unbounded growth is a memory leak. For each cache: what writes the underlying
  data, and does that write invalidate/update the cache? An unbounded cache (no TTL, no
  max size) on per-request keys grows forever. "It's just a cache" is how stale reads
  and OOMs ship.
lineage:
  - "Phil Karlton — the two hard things: cache invalidation and naming"
  - "the cache-coherence problem — a cached copy must be invalidated when the source changes"
  - "bounded resources — a cache without eviction is an unbounded resource"
ground_truth_tools: ["find caches (memo decorators, dicts-as-caches, external cache)", "trace the write path → is it invalidated?", "TTL/maxsize bounds"]
returns_clean: true
---

## Prompt

> Audit **cache invalidation & bounds**. The invariant (Karlton): a cache needs correct
> invalidation (or it serves stale) and a bound (or it leaks). For each cache —
> memoization decorators, dict-as-cache, external store — answer: (1) **what writes the
> source data, and does that path invalidate/update the cache?** (a write that doesn't
> bust the cache = stale reads). (2) **Is it bounded** (TTL / max size / eviction), or
> does it grow with unique keys? For each gap: the cache, the stale/leak risk, the fix.
> **Return clean** for caches that are correctly invalidated *and* bounded; don't flag a
> deliberate immutable/process-lifetime memo.

## Why it's built this way

The bug is the *missing edge* between the write path and the cache (coherence), plus the
*missing bound* (leak) — both invisible if you only read the cache code. The discipline
is tracing the source-write→invalidation edge and checking for eviction, while sparing
genuinely-immutable memoization.

## Demonstration run

**Target:** `dharma_swarm/`, 2026-06-25.

- **Small cache surface:** only **2** `@lru_cache`/`@cache` decorators in the package —
  and `lru_cache` is *bounded by default* (maxsize) and used for process-lifetime
  immutable computations (the common safe case). 🟢 on the memo caches.
- **The real audit target:** **dict-as-cache** patterns (module-level `_CACHE = {}`
  populated on read) — these are the ones to check for (a) invalidation on the source
  write and (b) an eviction bound. Cross-refs the race-audit's 202 mutable globals: a
  global dict cache that grows per-key with no eviction is both a leak *and* (if
  mutated across awaits) a race. Probe those; the decorator caches return clean.

## Changelog

- **v0.0.1** (2026-06-25) — cache-invalidation audit (Karlton/coherence/bounded-
  resources): source-write→invalidation edge + eviction bound, spare immutable memos.
  Tested on `dharma_swarm`: 2 `lru_cache` (bounded, clean); flagged dict-as-cache globals
  as the invalidation+bound probe.
