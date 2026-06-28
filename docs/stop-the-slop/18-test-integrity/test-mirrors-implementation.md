---
id: test-mirrors-implementation
version: 0.0.1
theme: 18-test-integrity
status: tested
invariant: >
  A test must assert BEHAVIOR (observable contract), not restate the implementation.
  A test that mocks everything and checks "the function called the mock" passes even
  when the behavior is wrong — it's a tautology, the test-theater form of AI slop.
  The witness: change the implementation's internals without changing its contract;
  a good test survives, a mirror test breaks. Coverage % counts these as covered;
  they cover nothing.
lineage:
  - "Goodenough & Gerhart 1975 — test data adequacy: tests must constrain behavior"
  - "Beck (TDD) — test the interface/contract, not the internals"
  - "mutation testing — a test suite that survives a behavior mutation is theater"
ground_truth_tools: ["read the assertions (do they check outputs or call-counts?)", "mutation testing (mutmut/cosmic-ray)", "assert presence + quality"]
returns_clean: true
---

## Prompt

> Audit tests for **mirroring the implementation** instead of asserting behavior. The
> invariant (Goodenough, Beck): a test constrains the observable contract; a test
> that mocks everything and asserts "the mock was called" is a tautology that passes
> when the behavior is broken — and coverage % counts it as covered.
>
> **Find:** tests with **no assertions**; tests whose only assertions are
> `mock.assert_called*` / structural identity (asserting the code did what the code
> does); tests that re-encode the implementation's constants. For each: `file:line`,
> what it actually verifies (often: nothing), and the behavioral assertion it should
> make (assert the *output/effect* for a known input). **The real proof is mutation
> testing** — recommend it: a suite that survives a behavior mutation is theater.
> **Return clean** for suites that assert real behavior — and *credit* them; don't
> manufacture doubt.

## Why it's built this way

"Tests exist" and "tests pass" are not "behavior is verified." Mutation testing is
the ground truth (does the suite catch a deliberate behavior change?), and the
assertion-shape heuristic (outputs vs call-counts) is the cheap pre-filter. This is
the sharpened version of the audit's earlier "I checked for assert *presence*, not
quality" caveat — now the quality is the target.

## Demonstration run

**Target:** `dharma_swarm/`, 2026-06-25.

- **Assertion presence (cheap pre-filter):** the real `tests/` suite is strong — **0**
  test files without assertions; the 15 no-assertion files are out-of-suite *scripts*
  (`scripts/*test*`, `.semgrep/` fixtures), not the pytest suite. 🟢 on presence.
- **The deeper axis (mirroring):** presence ≠ behavior. The honest next step is
  **mutation testing** (`mutmut run` on a target module) — only that proves the
  assertions constrain behavior rather than restate it. Without it, this axis is
  **UNASSESSED for mirroring** (presence GREEN, behavior-verification unproven) —
  stated honestly, not asserted clean.
- Recommended probe: run `mutmut` on `telos_gates.py` (high-stakes logic) and report
  the surviving-mutant rate; survivors = mirror/weak tests.

## Changelog

- **v0.0.1** (2026-06-25) — test-mirrors-implementation audit (Goodenough/Beck/
  mutation testing). Assertion-shape pre-filter + mutation-testing ground truth.
  Tested on `dharma_swarm`: presence GREEN (0 no-assert in `tests/`); mirroring axis
  honestly UNASSESSED pending a `mutmut` run — not faked clean.
