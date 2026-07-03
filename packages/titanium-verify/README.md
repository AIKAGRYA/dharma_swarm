# titanium-verify

A bespoke sound verifier for the `telos-kernel` TCB dialect.

## Why not Nagini or CrossHair?

- **Nagini** ([ETH Zürich, Eilers & Müller 2018](https://link.springer.com/chapter/10.1007/978-3-319-96145-3_33))
  translates Python to Viper. It targets Python 3.10 only, its trust base is
  Nagini + Viper + Z3 (~200k LOC), and it flags common patterns
  (Pydantic reflection, `Any` recursion) that would need substantial refactoring
  and specification overhead ([VeriGuard §Limitations](https://arxiv.org/html/2510.05156v1)).
- **CrossHair** is a *symbolic testing* tool, not a sound verifier. It finds
  counterexamples but does not prove absence.
- **Deal / icontract** are runtime contract libraries. They give no static
  guarantee.

For the ≤5000-LOC TCB in `packages/telos-kernel/`, a tightly scoped
first-party verifier lets us:

1. Support the subset of Python we actually use (frozen dataclasses,
   Pydantic v2 with `to_canonical_dict`, `Result[T, E]` ADT, no `Any`
   recursion, no reflection).
2. Speak directly about *effects*: `@effect(FS_READ)`, `@effect(SUBPROCESS)`,
   etc. — the rim/core distinction from PR #1c is a first-class citizen.
3. Keep the trust base small: `titanium-verify` (~1400 LOC) + Z3
   (~150k LOC but battle-tested) vs. Nagini + Viper + Z3 (~350k LOC).

## What titanium-verify proves

Phase 1 checks:

1. **Purity of the core.** For every function in `telos_kernel/` outside
   `_io/`, statically prove that its dependency closure contains no
   effectful operation (open, subprocess.run, os.\*, socket, etc.) unless
   reached through a call whose target carries a matching `@effect(...)`
   tag and lives in `_io/`.

2. **Fail-closed error propagation.** For every function returning
   `Result[T, E]`, prove that every `except` clause returns `Err(...)`
   with a matching `KernelError` code (no swallowed exceptions, no
   silent `Ok(None)`).

3. **Signature-path canonicalization.** Prove that any bytes fed to
   `hmac.new`, `Ed25519PrivateKey.sign`, or their `verify` counterparts
   flow through `canonicalize()` — never through `Pydantic.model_dump`
   or `str.__repr__`.

Phase 2 will add functional correctness for Merkle chain contracts and
K-of-N quorum arithmetic.

## Trust base

- `titanium_verify/frontend.py` — Python AST → typed IR (~300 LOC).
- `titanium_verify/effects.py` — effect analysis (~250 LOC).
- `titanium_verify/vc.py` — VC generator, SMT-LIB 2.6 (~350 LOC).
- `titanium_verify/solvers.py` — Z3 dispatch + optional CVC5 (~200 LOC).
- `titanium_verify/axioms/crypto.py` — UF axioms for HMAC/SHA-256/Ed25519 (~50 LOC).
- Solver: **Z3** (upstream, unmodified). Optional **CVC5** portfolio.

We do *not* attempt to prove the correctness of the crypto primitives
themselves — they enter the model as uninterpreted functions with
axiomatic collision-resistance ([Rogaway & Shrimpton 2004](https://eprint.iacr.org/2004/035)).

## Usage

```
$ python -m titanium_verify.cli verify --package telos_kernel --property purity
titanium-verify 0.1.0
package: telos_kernel (11 modules, 47 functions)
property: purity
result: VERIFIED (47/47 functions, 0 counterexamples)
time: 0.83s
```

## Non-goals

- Not a general-purpose Python verifier. It rejects anything it cannot
  reason about (unsound-would-be constructs give an explicit
  `ANALYSIS_REJECTED` verdict, not a silent pass).
- No fixpoint reasoning over recursion. Recursion in the kernel must be
  bounded by an explicit termination measure.
- No aliasing analysis for mutable state — the TCB is frozen-dataclass
  only. Attempts to mutate raise `AttributeError` at runtime; we assert
  this statically.
