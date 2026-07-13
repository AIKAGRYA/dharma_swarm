# Decorrelated review request: Hyperbolic Chamber Proof Membrane V0

Review the attached specification, implementation, tests, replay bundle,
verification receipt, research ledger, and governed work packet as an
adversarial senior reviewer. This is a bounded `HARNESS_PROVEN` claim, not a
request to declare Dharma production-ready.

This is a new review of repaired bytes. Round 2 reached five approvals and one
revision request. Do not inherit any prior approval. The new tests literally
construct a copied verification object, a copied claim object, a serialized
authority-shaped dictionary, and the private authorization dataclass shape;
none may create provenance, permission, or an effect without the live witnesses
and evaluator registry state. The research ledger names the repairs and limits.

PM0-10 is the result of this council process and therefore cannot already be
true while the round is running. Assess PM0-1 through PM0-9, the implementation
boundaries, and criterion 10 below. Your recorded vote contributes to PM0-10;
do not reject solely because the unfinished round has not approved itself.

## Required decision

Return the council JSON schema exactly:

- `verdict`: `pass`, `approve`, `revise`, `reject`, `blocked`, `failed`, or
  `insufficient_context`
- `score`: integer 0-100
- `summary`: concise result
- `blockers`: concrete blockers
- `required_changes`: exact changes needed for 100/100
- `evidence_checked`: paths, commands, or claims actually checked
- `explicit_disagreement`: non-empty if you reject any premise

Approve at 100 only if all of these are supported by the attached bytes:

1. MiroFish and other stochastic/social engines are confined to untrusted
   scenario generation and cannot supply verifier or promotion authority.
2. V0 executes the committed `graph/types.py` bytes and source-exact
   `RunCheckpoint.fork` method without importing the broad graph initializer or
   modifying sibling-owned graph code.
3. `WorldV1` and `ReplayBundleV1` accept registered data only, bind the complete
   declared repository-source scope, validate direct Python objects as strictly
   as JSON, and reject tampering, unknown properties, widened imports, and
   declared nondeterminism.
4. The preserved current defect yields `Refutes<fork_parent_isolated>` while a
   corrected deep-copy control satisfies the property.
5. 100 separately spawned, unique-PID processes agree semantically on the exact
   bundle; the receipt records replay/environment digests, source bytes, Git,
   PATH, timing, exits, and stdout/stderr hashes without claiming OS attestation.
6. Candidate identity and scenario/control arm come from the bundle, not the
   caller. A reproduced violation cannot promote; control evidence cannot be
   relabeled as production; `ParityScore(52)` cannot discharge
   `ProductionReady`; serialized authority-shaped data cannot become an
   operational capability.
7. The positive synthetic gate is narrow and honest: the registry-backed
   capability is bound to evaluator instance, principal, candidate, evidence
   arm, proposition, effect-binding ID, required properties, source revision,
   bundle, and scope. Duplicate mint and reuse fail. The only handler records a
   test invocation; no handler-code attestation or production mutation is
   claimed.
8. The implementation explicitly treats arbitrary in-process Python and the
   local filesystem as trusted. It does not claim cryptographic provenance,
   arbitrary-code sandboxing, interpreter/OS attestation, universal
   determinism, automatic RCA, live closure, or product readiness.
9. The documented tests and receipts are internally consistent. Checksums and
   model agreement are described as integrity/review evidence, never truth or
   standing.
10. The next step remains ordinary DharmaGraph repair followed by a new exact-
    manifest `Satisfies` replay; V0 does not expand into a scheduler, provider,
    broker, MiroFish runtime, or Antithesis clone.

## Attack questions

- Can JSON or a directly constructed dataclass smuggle a callable, path escape,
  candidate relabel, modality, or operational authority through the bundle?
- Can a capability for candidate A/arm A authorize candidate B/arm B, a
  different proposition/effect-binding/scope, another evaluator instance, a
  second mint, or a second effect?
- Does the worker execute any repository source outside its declared set? Do
  loaded-byte digests, child semantics, and environment records match the
  committed bundle, or are they superficial self-assertions?
- Is the corrected control genuinely discriminating?
- Can the `Refutes` result be mislabeled as `Satisfies` or production closure?
- Is any research statement stronger than its primary source and inspection
  scope?
- Does any prose still overstate trusted-process conventions as a hostile-code,
  transactional, durable, or OS-level guarantee?
- Are there acceptance items in Part IV that lack executable evidence?

Do not award points for prose volume, repository popularity, checksums, passing
models, or consensus. Cite exact attached file/line or receipt fields for every
blocker. If there is a real issue, return `revise` even when the overall design
is promising.
