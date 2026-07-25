---
id: retry-audit
version: 0.0.1
theme: 04-resilience-and-retries
status: tested
invariant: >
  A retry is a loaded gun aimed at your dependencies. Every retry MUST be
  bounded (max attempts AND total timeout), backed-off with jitter (to avoid
  synchronized retry storms), narrow in what it catches (never retry a bug), and
  idempotent at the call site (or it duplicates work). An unbounded or
  broad-catch retry is not resilience — it is an outage amplifier.
lineage:
  - "Metcalfe & Boggs 1976 — Ethernet: exponential backoff to de-correlate collisions"
  - "Nygard 2007 (Release It!) — the Circuit Breaker stability pattern"
  - "Brooker/AWS — jitter: full randomization beats fixed backoff under load"
  - "Idempotency (HTTP/REST) — a retry is only safe if the operation is repeatable"
ground_truth_tools: ["grep/AST for retry/backoff/sleep loops", "the repo's own canonical retry primitive", "call-graph to external boundaries"]
returns_clean: true
---

## Prompt

> You are auditing **retry and resilience logic**. The invariant you defend
> (Metcalfe–Boggs, Nygard): a retry must be **bounded** (max attempts *and* a
> total timeout), **backed-off with jitter**, **narrow** in what it catches, and
> **idempotent** at the call site. An unbounded or broad-catch retry is not
> resilience — under load it is a retry storm that amplifies an outage.
>
> **Hard rules:**
>
> 1. **Find the codebase's canonical retry primitive first, then measure
>    adoption.** Most repos already have one (a `RetryPolicy`, a decorator,
>    `tenacity`). The most valuable finding is usually not "no retries" — it's
>    **ad-hoc retries that bypass the canonical one.** Grep/AST for it; report how
>    many call sites use it vs hand-roll their own.
> 2. **Classify the loop, don't assume.** A `while True:` with `sleep` might be a
>    legitimate daemon/poller, not an unbounded retry. Inspect the exit condition.
>    Only flag loops that retry a *failing operation* with no attempt/time bound.
> 3. **Rank by blast radius on a real boundary.** A retry around an external
>    service call (network, DB, provider API) on a hot path is the top risk; a
>    retry around a local pure function is noise. Prioritize production paths and
>    external calls.
> 4. **Three things make a retry dangerous — name which apply per site:**
>    (a) **unbounded** (no max attempts or no total timeout),
>    (b) **broad catch** (`except Exception` / bare `except` — retries bugs, not
>    just transient faults),
>    (c) **no jitter** (synchronized clients → thundering herd), and the silent
>    fourth: **non-idempotent** call site (a retry duplicates the side effect).
> 5. **Credit correct retries.** Exponential backoff with a cap and jitter around
>    an idempotent external call is *right* — say so, don't flag it to pad.
> 6. **Return clean when clean.** If every retry is bounded, jittered, narrow, and
>    idempotent: `Retry logic is sound. N sites, all bounded/jittered/narrow.`
>
> **Output contract** — table, ranked by risk:
> | Location (file:line) | Strategy | Max attempts | Total timeout | Catches | Jitter | Circuit breaker | Idempotent? | Risk | Notes |
>
> Then: `Bypasses canonical primitive:` list, and `Correct (do not change):` list.
> **Stop when** every retry site is classified. Do not pad with daemon loops or
> correct backoff dressed up as findings.

## Why it's built this way

The kit's version lists retry mechanisms and flags "broad catch" / "no timeout"
— good instincts, but it has no notion of a *canonical primitive* or
*idempotency*, so on a real repo it misses the actual problem (fragmentation) and
the actual danger (a retry that duplicates a payment because the call wasn't
idempotent). Backoff-with-jitter is Metcalfe–Boggs (1976 Ethernet); the circuit
breaker is Nygard; "retry only if idempotent" is the REST contract. The analysis
is correct because the theory is.

## Demonstration run

**Target:** `dharma_swarm/`, 2026-06-25. Tool: AST/grep for retry primitives +
adoption count.

- **Canonical primitive exists:** `dharma_swarm/resilience.py` — `RetryPolicy`
  (`max_attempts=3`, `backoff_multiplier=2.0`, `jitter_seconds=0.05`) +
  `CircuitBreaker` (sliding window, half-open) + pluggable state store. Good design.
- **Adoption is the finding:** only **4 modules import it.** 257 retry-related
  keyword sites exist across the package — the canonical policy is **under-adopted**;
  most retry logic is hand-rolled.

| Location | Strategy | Max | Timeout | Catches | Jitter | CB | Risk | Notes |
|---|---|---|---|---|---|---|---|---|
| `providers.py:536` | exp backoff (`base × 2**attempt`) on rate-limit | bounded | — | narrow (rate-limit) | — | no | **Low** | **Correct** backoff; consider adding jitter to avoid provider-side herd |
| `damper.py:171` | exp backoff capped at `max_backoff` | bounded | — | — | — | no | **Low** | **Correct** (cap present) |
| `while True` + sleep ×8 (`file_lock`, `scout_framework`, `roaming_dispatch_daemon`, `thinkodynamic_director`, …) | loop | **UNVERIFIED** | UNVERIFIED | UNVERIFIED | — | — | **UNCONFIRMED** | must inspect each exit condition — daemon/poller (fine) vs unbounded retry (risk). Don't assume. |

**Bypasses canonical primitive:** the ad-hoc backoffs above re-implement what
`resilience.RetryPolicy` already provides — route them through it to get jitter +
circuit-breaker for free. **Correct (do not change):** `providers.py:536`,
`damper.py:171` (exponential + cap). **Honest gap:** the 8 `while True` loops need
per-site inspection before grading — flagged UNCONFIRMED, not invented as risks.

## Changelog

- **v0.0.1** (2026-06-25) — rewrite of a kit's retry-finder. Added: find-the-
  canonical-primitive-and-measure-adoption, classify-the-loop (daemon vs
  unbounded), idempotency as the silent fourth danger, credit-correct-retries,
  and return-clean. Tested against `dharma_swarm/` (found a good `RetryPolicy`
  under-adopted at 4 importers; credited 2 correct ad-hoc backoffs; flagged 8
  `while True` loops UNCONFIRMED rather than guessing).
