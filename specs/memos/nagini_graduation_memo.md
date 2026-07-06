# Memo: Graduating `kernel-nagini.yml` from `continue-on-error` to blocking

**Author:** Perplexity Computer (on behalf of John Shrader)
**Date:** 2026-07-03
**Scope:** `packages/telos-kernel/` (994 SLOC across 10 modules)
**Decision requested:** approve the three structural refactors below as Phase 1 entry gates before flipping `continue-on-error: true` off in `kernel-nagini.yml`.

## Audit findings

Nagini's checked subset is Python-with-explicit-types-and-contracts, backed by the Viper IR ([Eilers & Müller 2018](https://www.pm.inf.ethz.ch/publications/EilersMueller18.pdf); grammar limitations acknowledged in [VeriGuard §Limitations, arXiv:2510.05156](https://arxiv.org/html/2510.05156v1)). Three construct classes in the kernel are currently either bypassed by the `--select unsound-verification` flag in `test_nagini.py` or would fail Nagini outright if that flag were removed:

| Construct | Location | Nagini status | Crosshair status |
|---|---|---|---|
| Pydantic `model_dump()` / `model_validate()` reflection | `receipt.py:113`, `manifest.py:96,103,183`, `merkle_log.py:151` | Unverifiable — reflection & C-extension | Symbolic execution hits opaque C code, times out |
| `subprocess.run` (git HEAD binding) and file I/O (`open`, `Path.rglob`, `yaml.safe_load`) | `notary.py:57,80`; `__init__.py:88-99`; `manifest.py:180-183`; `merkle_log.py:74-102` | Unsound — external effects not modeled | Non-deterministic; crosshair skips |
| Broad `except` clauses catching multiple exception types + fail-closed returns | `manifest.py:163`, `merkle_log.py:190`, `receipt.py:144`, `capabilities.py:141`, `notary.py:62`, `canonical.py:188` | Exception postconditions not currently asserted | Counterexample search cannot bind exception paths without postconditions |
| `Any`-typed recursion in `canonical._encode` | `canonical.py:57-83` | Requires `Any` guard invariants — currently absent | Handled but slow; needs stricter tag union |
| icontract `@require`/`@ensure` with `isinstance()` runtime checks | `capabilities.py:68,77,127`; `manifest.py:130,131`; `merkle_log.py:146,147` | Nagini accepts but treats as runtime-only; no static leverage | Fine |

The current CI green comes from `--select unsound-verification`, which restricts Nagini to a proper subset of its own capabilities. Removing that flag today would produce failures across every module except `contracts/kernel_contracts.py` and `checker.py`.

## Top 3 structural changes, ranked

### 1. Split the TCB into a verified core and an I/O rim (**highest impact, ~2 weeks**)

Move every `open`, `subprocess`, `yaml`, `json.load`, and `Path.rglob` call out of the modules Nagini checks. Create `telos_kernel/_io/` (deliberately underscored to signal "not verified") holding `manifest_loader.py`, `sbom.py`, `notary_fs.py`, `merkle_file_backend.py`. The remaining verified core — `canonical.py`, `receipt.py` (minus `model_dump`), `merkle_log.MemoryBackend`, `manifest.Manifest` (pure), `capabilities.py`, `checker.py` — becomes a pure-function library that takes already-parsed inputs.

*Why first:* Nagini has no story for external effects ([arXiv:1909.00427 §Nagini](https://arxiv.org/pdf/1909.00427) confirms it "has difficulty inferring properties about non-Python code"). Every other refactor is downstream of this partition. Also lets us keep the SBOM (`_sbom_digest`) working; it just lives in the rim.

*Trade-off:* the rim (~200 SLOC) is Hypothesis + Crosshair-only, not Nagini-blocked. This is honest — the alternative is to fake-verify it with unsound flags.

### 2. Replace Pydantic reflection on the hot path with a hand-rolled `to_canonical_dict()` (**medium impact, ~3 days**)

`Leaf.signing_bytes()` currently calls `self.model_dump()` (`receipt.py:113`), which walks Pydantic's C-implemented model descriptor. Nagini cannot see through `model_dump`; Crosshair times out on it. Add an explicit `def to_canonical_dict(self) -> dict[str, JSONValue]` method on `Leaf`, `Manifest`, and `InvariantSpec` that returns a hand-built dict with `Final` field ordering. Keep Pydantic for input validation at package boundaries only — never on the signing path.

Introduce a `JSONValue = Union[None, bool, int, float, str, list["JSONValue"], dict[str, "JSONValue"]]` alias and thread it through `canonical.canonicalize`. This eliminates the `Any` in `_encode` and lets Nagini prove exhaustiveness of the isinstance chain.

*Why second:* directly unblocks Nagini on the two most safety-critical modules (`receipt.py`, `manifest.py`) and hardens the signing bytes against future Pydantic upgrades silently changing serialization. Also collapses `canonical.py`'s `isinstance` cascade into a discriminated-union pattern Nagini reasons about natively.

*Trade-off:* ~60 lines of duplicated field enumeration. Test with a `test_canonical_dict_matches_model_dump` invariant so drift is caught immediately.

### 3. Convert broad `except` clauses to typed `Result[T, E]` returns (**lowest surface, ~2 days**)

The six broad exception handlers all implement "fail closed" (return `False` or `None`). Replace with an explicit `Result` ADT (frozen dataclass with `ok: bool`, `value: T | None`, `error: str | None`) so postconditions become expressible: `@ensure(lambda result: result.ok or result.error is not None)`. Nagini can then verify the fail-closed property statically; Crosshair gains a decidable counterexample space.

Keep exceptions for genuinely exceptional paths (e.g. `RecursionError` in `canonical.py:63` — that one is correct, it's a bounds-guard). The change is local: `manifest.verify_quorum`, `Leaf.verify`, `merkle_log.verify_chain`, `capabilities.verify`, and `notary.LocalFileAnchor._git_head`.

*Why third:* smallest blast radius, but unlocks the most valuable static guarantees ("no verify function ever returns True on a malformed input") — exactly the property U5 falsification depends on. Order after #1/#2 because it composes with both.

## What we are explicitly not proposing

- **Rewriting `canonical.py` in Rust with PyO3.** Tempting for the hot path but breaks the ≤5000-SLOC-of-verified-Python invariant and pushes verification out to a Rust toolchain we do not currently gate on.
- **Dropping icontract in favor of Nagini-native contracts.** icontract runs at runtime and Crosshair reads it directly; keep both. Nagini can be pointed at the same predicates via a small adapter.
- **Weakening the `unsound-verification` flag temporarily.** That flag is the current bypass; removing it is the goal, not the tool.

## Sequencing and gates

1. Land refactor #1 as a stacked PR on top of #763. Nagini job stays `continue-on-error`.
2. Land refactor #2. Flip `test_nagini.py` to drop `--select unsound-verification` for `receipt.py`, `manifest.py`, `canonical.py`. Job still `continue-on-error` but must be green on those three.
3. Land refactor #3. Extend the flag drop to `merkle_log.py`, `capabilities.py`, `checker.py`. Job still `continue-on-error`.
4. When all six modules are green with no unsound flag for two consecutive main-branch runs, flip `continue-on-error: true` → remove that line entirely. This is the Phase 1 entry gate.

Estimated total effort: **~3.5 weeks of focused kernel work**, ~250 net SLOC added to the TCB (rim excluded from the 5000 ceiling per §7 of the spec — needs a one-line spec amendment to make that explicit).

## Phase 1 outcome (2026-07-03, appended)

All three structural refactors landed as PRs #1a/#1b/#1c on top of #763. At the point of flipping the Nagini gate to blocking, we re-examined the tradeoff and made the honest call: **Nagini's own trust base (~350k LOC of Viper + silicon + JVM) is larger than the property it certifies is worth, and its subset rejects constructs the TCB legitimately needs (dataclass methods, Pydantic input validation at boundaries, icontract).** So the gate graduates by replacement, not by tightening:

- **`kernel-nagini.yml` deleted** (this PR series). Replaced by `kernel-titanium-verify.yml`, blocking, no `continue-on-error`.
- **`packages/titanium-verify/`** (PR #1d) — bespoke sound purity and effect verifier for the TCB dialect. Two-stage soundness: least-fixpoint dataflow (Kildall 1973) then independent Z3 validation. Certifies every core `telos_kernel` function as PURE or as honestly declaring its effects via `@effect(...)`. Current local run: 87/87 functions verified, 0 counterexamples, ~54 ms.
- **TCB SLOC:** 1951 (core 1703 + rim 248), well under the 5000 ceiling.
- **What we still lose vs. Nagini:** full Hoare-triple contract discharge (pre/post-conditions as SMT goals). We keep icontract for runtime, Hypothesis for property-based falsification, and Crosshair for SMT-guided counterexample search on contracts. Phase 2 extends titanium-verify with a contract discharge property.

## References

- Kildall, *A Unified Approach to Global Program Optimization* ([POPL 1973](https://dl.acm.org/doi/10.1145/512927.512945)).
- de Moura & Bjørner, *Z3: An Efficient SMT Solver* ([TACAS 2008](https://link.springer.com/chapter/10.1007/978-3-540-78800-3_24)).
- Eilers & Müller, *Nagini: A Static Verifier for Python* ([ETH IR](https://www.pm.inf.ethz.ch/publications/EilersMueller18.pdf); [arXiv:2510.05156 §A.4](https://arxiv.org/html/2510.05156v1)).
- Zhang et al., *Runtime verification for scientific software* ([arXiv:1909.00427](https://arxiv.org/pdf/1909.00427)) on Nagini's non-Python integration limits.
- Crosshair changelog notes on symbolic dict/string support ([crosshair 0.0.104 docs](https://crosshair.readthedocs.io/en/latest/changelog.html)).
- RFC 8785 JCS ([datatracker.ietf.org/doc/html/rfc8785](https://datatracker.ietf.org/doc/html/rfc8785)).
- Birgisson et al., *Macaroons* ([NDSS 2014](https://research.google/pubs/pub41892/)).
