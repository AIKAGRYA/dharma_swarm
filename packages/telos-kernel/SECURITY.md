# telos-kernel — Security & Trust Boundary

Merge-blocking policy artifact. Every PR that touches `packages/telos-kernel/` must preserve every clause below.

## 1. Trusted Computing Base (TCB)

The TCB is exactly the Python source under `packages/telos-kernel/telos_kernel/*.py` **excluding** the `tests/` subtree. CI enforces:

- Total TCB LOC ≤ **5 000** (`test_tcb_loc.py`).
- Import transitive closure ⊆ **allow-list** (`test_import_boundary.py`).
- No AST nodes for `eval`, `exec`, `__import__`, `compile`, `getattr` on module objects, `setattr` on module objects, or dynamic attribute mutation of any imported symbol (`test_import_boundary.py`).
- Every public function annotated with `icontract` or equivalent pre/post-condition (`test_contract_coverage.py`).

## 2. Verifier stack

1. **titanium-verify** — bespoke sound purity and effect verifier for the TCB dialect. Runs on every core module in `telos_kernel/` (excluding the `_io` rim). Uses least-fixpoint dataflow analysis (Kildall 1973) plus Z3 SMT validation. CI blocks merge on any refutation. See `packages/titanium-verify/README.md`. Replaces Nagini as of Phase 1: Nagini required a Viper/silicon/JVM stack, rejected the TCB dialect (Pydantic, dataclass methods, icontract), and returned unknown on most core functions. References: [Kildall 1973](https://dl.acm.org/doi/10.1145/512927.512945), [Z3](https://github.com/Z3Prover/z3).
2. **Crosshair** — SMT-guided counterexample finder against `icontract` pre/post-conditions. Runs in CI on the full kernel surface. Complementary to titanium-verify (which proves purity/effects; Crosshair searches for value counterexamples). Reference: [pschanely/CrossHair](https://github.com/pschanely/CrossHair).
3. **Hypothesis** — property-based tests on `MerkleLog.append/verify` round-trip, canonicalization round-trip, macaroon attenuation monotonicity, receipt sign/verify.

Any verifier disagreement blocks merge. If titanium-verify refuses a construct required for correctness, we restructure the code, not the verifier.

## 3. Cryptographic primitives

- **Signatures:** Ed25519 via `cryptography.hazmat.primitives.asymmetric.ed25519`. No custom curves. No RSA. Reference: [RFC 8032](https://datatracker.ietf.org/doc/html/rfc8032).
- **Hashes:** SHA-256 (wire format, Merkle chain). BLAKE3 available for hot-path digests when p95 constraints demand it. Reference: [FIPS 180-4](https://csrc.nist.gov/publications/detail/fips/180/4/final), [BLAKE3 spec](https://github.com/BLAKE3-team/BLAKE3-specs).
- **Canonicalization:** RFC 8785 JSON Canonicalization Scheme (JCS) for every signed payload. In-tree implementation to keep the trust surface tight. Reference: [RFC 8785](https://datatracker.ietf.org/doc/html/rfc8785).
- **No** `pickle`, `marshal`, `shelve`, or `dill` anywhere in the TCB.

## 4. Capability tokens (macaroon-shaped)

Object-capability discipline per Miller 2006 *Robust Composition* ([reference](https://worrydream.com/refs/Miller_2006_-_Robust_Composition.pdf)). Attenuation is a first-class caveat append, not a re-mint — this makes attenuation strictly monotone (never widens authority). Reference pattern: [Birgisson et al., NDSS 2014 — Macaroons](https://research.google/pubs/pub41892/).

Ambient authority is banned inside the kernel:

- No global process-level tool registry importable from `telos_kernel`.
- Every kernel-side action requires an explicit capability argument.

## 5. Falsification benchmarks

Every U-invariant ships with a red-team falsification test under `benchmarks/telos_redteam/`. Phase 0 seeds the harness with the U5 leaf-tamper test. Later phases add tests per §8 of the spec. Regression in any bypass rate blocks merge (`.github/workflows/redteam-gate.yml`, Phase 7).

## 6. Signer set

The K=3/N=5 quorum for U-invariant manifest edits is defined in `kernel/manifest.yaml`. **Phase 0 ships with stub entries.** Real Ed25519 public keys must replace the stubs before U2 transitions to `enforced` in Phase 1. Until then, the kernel emits a `WARN` boot receipt with `capability_signature_status: STUB` and refuses any manifest edit that would attempt to activate U2 enforcement.

## 7. Notary anchoring

Per §U5 of the spec, the Merkle root is periodically anchored to an external notary. Phase 0 ships a `LocalFileAnchor` (append-only file bound to `git rev-parse HEAD`). Phase 1+ swaps in RFC 3161 timestamping or an OpenTimestamps adapter. Reference: [RFC 3161](https://datatracker.ietf.org/doc/html/rfc3161), [OpenTimestamps](https://opentimestamps.org/).

## 8. Reporting

Trust-boundary regressions should be filed as GitHub issues with label `titanium-tcb`. Do not file publicly if the regression is exploitable — email the maintainer with subject `[titanium-tcb] private disclosure`.
