# telos-kernel

Titanium Telos Gates v3 — hardened safety-kernel substrate.

Companion package to [`../telos-gatekeeper/`](../telos-gatekeeper/). Where the gatekeeper is the SDK surface, `telos-kernel` is the Trusted Computing Base (TCB): the small, contract-verified, import-boundary-enforced core that every gate check ultimately routes through.

## Trust boundary

- **TCB LOC target:** ≤ 5 000 across `telos_kernel/*.py` (CI-enforced).
- **Import allow-list:** stdlib + `pydantic`, `cryptography`, `pyyaml`, `icontract`. Later phases extend under quorum-signed manifest edits.
- **Forbidden constructs:** `eval`, `exec`, `__import__`, dynamic module loading, monkey-patching entry points. AST-checked in CI.
- **Verifier gates:** `titanium-verify` blocks merge on kernel purity/effect certification. Crosshair runs SMT counterexample search on the wider contract surface, with runtime contracts kept where they are still useful.

## Phase 0 status

- Enforced invariants: `U5` (Merkle chain tamper-evidence, boot receipt).
- Declared but not yet enforced (per [`../../kernel/manifest.yaml`](../../kernel/manifest.yaml)): U0, U1, U2, U3, U4, U6, U7, U8, U9, U10, U11. Each lands in its phase per [`../../specs/TITANIUM_TELOS_GATES_SPEC_v3.md`](../../specs/TITANIUM_TELOS_GATES_SPEC_v3.md) §8.

## Signer set

**Phase 0 ships with stub signer entries.** Every U-invariant manifest edit (per U2) requires K=3/N=5 Ed25519 signatures. Before Phase 1 lands enforcement, real public keys must replace the placeholders in [`../../kernel/manifest.yaml`](../../kernel/manifest.yaml). The kernel emits a `WARN` boot receipt while stubs are in place and refuses to transition U2 to `enforced` until real keys are present.

See [`SECURITY.md`](./SECURITY.md) for the full trust-boundary discipline.
