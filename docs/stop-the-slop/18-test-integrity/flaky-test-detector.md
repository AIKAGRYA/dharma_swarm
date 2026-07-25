---
id: flaky-test-detector
version: 0.0.1
theme: 18-test-integrity
status: tested
invariant: >
  A test must be deterministic: same input, same result, every run. Flakiness comes
  from uncontrolled nondeterminism — wall-clock time, randomness, unfrozen UUIDs,
  real network/sleep timing, test-order dependence, shared state. Each source is
  controllable (freeze the clock, seed the RNG, fake the network, isolate state). A
  flaky test is worse than no test: it trains the team to ignore red.
lineage:
  - "Dijkstra — determinism; nondeterminism is the enemy of a repeatable witness"
  - "Luo et al. 2014 — empirical study of flaky-test root causes (async, order, time)"
  - "test isolation / hermeticity — a test owns its world or it shares a flake"
ground_truth_tools: ["grep/AST for time/random/uuid/sleep/network in tests", "re-run-N-times + random-order (pytest-randomly)", "the flake history"]
returns_clean: true
---

## Prompt

> Detect **flaky tests** (nondeterminism sources). The invariant (Dijkstra): same
> input → same result, every run. Find the uncontrolled sources and name the fix:
>
> - **wall-clock** (`datetime.now`, `time.time`) → freeze it (`freezegun`/inject a clock)
> - **randomness** (`random.`, `uuid4`) → seed it / inject
> - **real timing** (`sleep`, timeouts as assertions) → fake the clock; assert events not durations
> - **network/IO** → stub it; a test that hits the network is an integration test, label it
> - **order dependence / shared state** → isolate fixtures; run with random order to expose it
>
> For each: `test:line`, the source, the fix. **Confirm by running** the suite N times
> in random order (`pytest-randomly`, `--count`) — that's the ground truth, not static
> shape. **Return clean** for tests that already control these. **Don't flag a test
> that uses `now()`/`random` but has frozen/seeded it** — that's controlled.

## Why it's built this way

Static detection finds the *sources*; only re-running (N times, random order) proves
*flakiness* — so the prompt routes to the runner for ground truth and uses the static
scan as the candidate list. The discipline is not flagging already-controlled
nondeterminism (a seeded `random` is fine).

## Demonstration run

**Target:** `dharma_swarm/tests/`, 2026-06-25.

- **Candidates:** **78** test files touch `datetime.now`/`time.time`/`random`/`uuid4`;
  **30** use `sleep`/`asyncio.sleep`. These are *sources*, not verdicts.
- **Disciplined next step (the real instrument):** run
  `pytest -p randomly --count=5` (random order, 5×) and diff results — the tests that
  change verdict are the actual flakes. Static count alone over-reports (a frozen-time
  test uses `datetime` but isn't flaky). So: 78 candidates → **confirm by re-run**,
  prioritize the 30 sleep-based ones (timing assertions are the classic flake) and any
  using `uuid4`/`now()` *without* a freeze/seed.
- Honest framing: **candidates UNCONFIRMED until the multi-run** — the prompt hands you
  the list and the command, not a fabricated flake count.

## Changelog

- **v0.0.1** (2026-06-25) — flaky-test detector (Dijkstra/Luo): enumerate
  nondeterminism sources, route to N-run-random-order for proof, don't flag controlled
  uses. Tested on `dharma_swarm/tests/`: 78 time/random candidates + 30 sleep-based —
  reported as a confirm-by-rerun candidate list, not a verdict.
