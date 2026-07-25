---
id: assertion-quality-audit
version: 0.0.1
theme: 18-test-integrity
status: tested
invariant: >
  An assertion must pin a SPECIFIC, MEANINGFUL property — the exact output, the precise
  error, the invariant — not a tautology. Weak assertions (`assert result`,
  `assert x is not None`, `assert len(x) > 0`, asserting a mock was called) pass for the
  wrong reasons and let bugs through while showing green. The strength of a suite is the
  strength of its assertions, not their count.
lineage:
  - "Goodenough & Gerhart 1975 — test data adequacy: the oracle must be precise"
  - "the test oracle problem — a weak oracle accepts wrong outputs"
  - "mutation testing — weak assertions let mutants survive"
ground_truth_tools: ["AST: classify each assert (exact-value vs truthy/not-none/len>0/called)", "mutation testing survival", "assertion-per-test density"]
returns_clean: true
---

## Prompt

> Audit **assertion quality** (the oracle). The invariant (Goodenough, oracle problem): an
> assertion must pin a specific property, not a truthy tautology. Classify each test's
> assertions: **strong** (exact value/structure, precise exception, a real invariant) vs
> **weak** (`assert result`, `is not None`, `len > 0`, only `mock.assert_called`, asserting
> a constant the code also defines). Flag tests whose *only* assertions are weak — they
> pass for the wrong reason. For each: the test, the weak assertion, the stronger one it
> should make (assert the actual expected output for the input). **Ground truth = mutation
> testing**: weak assertions let mutants survive — recommend it. **Return clean / credit**
> tests with precise oracles.

## Why it's built this way

Sibling to `test-mirrors-implementation` but orthogonal: mirroring is *what* you assert
(behavior vs internals); this is *how strong* the assertion is (exact vs truthy). Both are
forms of the oracle problem; mutation testing is the shared ground truth. The discipline:
classify assertion strength, don't just count them.

## Demonstration run

**Target:** `dharma_swarm/tests/`, 2026-06-25.

- **Cheap classifier (the pre-filter):** scan assertions for the weak shapes
  (`assert <single-name>`, `is not None`, `len(...) >= 0/`, lone `assert_called`). These
  are the candidate weak oracles; a test whose *every* assertion is weak is the flag.
- **Ground truth:** run **`mutmut`** on a high-stakes module (e.g. `telos_gates.py`,
  `ratchet.py`) — surviving mutants are the proof that some assertion is too weak to catch
  a behavior change. The static classifier narrows where to look; mutation testing
  confirms.
- **Honest framing:** `dharma_swarm`'s suite is strong on *presence* (0 no-assert in
  `tests/`); assertion *strength* is **UNASSESSED** until the mutation run — stated, not
  assumed. Output = the weak-assertion candidate list + the `mutmut` target.

## Changelog

- **v0.0.1** (2026-06-25) — assertion-quality audit (Goodenough/oracle/mutation): classify
  strong vs weak oracles, confirm via mutation testing, credit precise assertions. Tested
  on `dharma_swarm/tests/`: presence strong, strength UNASSESSED pending `mutmut` on the
  high-stakes modules — honestly flagged, not faked.
