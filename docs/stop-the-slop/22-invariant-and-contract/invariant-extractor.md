---
id: invariant-extractor
version: 0.0.1
theme: 22-invariant-and-contract
status: tested
invariant: >
  Every function relies on unstated preconditions (what must be true of its inputs/
  state to work) and guarantees postconditions (what it ensures on return). These
  invariants exist whether or not they're written down; bugs live where an unstated
  precondition is violated by a caller. Surfacing them — and asserting the load-bearing
  ones — converts implicit assumptions into checked contracts.
lineage:
  - "Hoare 1969 — axiomatic basis: {P} code {Q}; pre/postconditions are the contract"
  - "Meyer — Design by Contract: make the assumptions explicit and enforced"
  - "Ernst (Daikon) — invariants can be inferred from code/observed behavior"
ground_truth_tools: ["read the function: what must inputs satisfy? what does it guarantee?", "call sites (do they uphold the precondition?)", "Daikon-style dynamic inference"]
returns_clean: true
---

## Prompt

> Extract the **implicit invariants** of a function/module. The invariant (Hoare,
> Meyer): code is `{P} body {Q}` — it assumes preconditions P and guarantees
> postconditions Q whether or not they're documented. Surface them:
>
> 1. **Preconditions** — what must be true of the args/state for this to be correct?
>    (non-null, sorted, within range, called-after-init, holds-the-lock, idempotent
>    caller…). Name each, and whether it's **checked** or merely **assumed**.
> 2. **Postconditions / guarantees** — what does it ensure on return? (monotone,
>    idempotent, never-loosens, total ordering preserved…).
> 3. **Caller check** — do the actual call sites uphold each precondition? An *unstated,
>    unchecked* precondition that a caller can violate is a latent bug.
> 4. Recommend asserting the **load-bearing** ones (guard clause / `assert` / type) —
>    not every triviality.
>
> **Return clean** for code whose contract is already explicit and enforced; credit it.

## Why it's built this way

Hoare gives the form ({P} code {Q}); Meyer says make P/Q explicit and enforced; Daikon
shows they're inferable. The bug class this catches — a caller violating an unstated
precondition — is invisible until it isn't. The discipline: surface assumptions and
assert only the load-bearing ones (over-asserting is its own noise).

## Demonstration run

**Target:** `scripts/governance/hygiene/ratchet.py::tighten`, 2026-06-25 — a function
that *documents* its invariants (a model to extract from).

- **Preconditions (extracted):** "Must only be called on a **green** run; regressions
  are the caller's responsibility to reject first" — this is an **unchecked, stated**
  precondition. The function does not itself verify greenness; if a caller passes
  regressions, it would loosen a bound. **Caller check:** `main()` does gate on
  `regressions` before calling `tighten` → the precondition is upheld *by the caller*,
  not the function. That's a latent edge if a *future* caller forgets.
- **Postconditions (extracted/documented):** **idempotent** (tightening twice with the
  same readings is a no-op) and **monotone** (never loosens a bound). These are the
  load-bearing guarantees.
- **Recommendation:** the monotone/idempotent postconditions are well-stated; the
  *precondition* (green-only) is the assumption to harden — either assert no-regressions
  inside `tighten`, or encode it in the type (accept only a `GreenComparisons` value) so
  a future caller can't violate it. Credit: this function is unusually contract-explicit
  already.

## Changelog

- **v0.0.1** (2026-06-25) — invariant extractor (Hoare/Meyer/Daikon): surface pre/post,
  check call sites, assert load-bearing only. Tested on `ratchet.tighten`: extracted its
  green-only precondition (stated, caller-enforced, not self-checked) and monotone/
  idempotent postconditions; recommended encoding the precondition in the type.
