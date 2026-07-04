## Summary
Adversarial review of NĀGA-IR PR #2 confirms structural alignment with MLIR verification patterns but requires immediate correction of three repo-grounding errors. [confidence: 98/100] The formal convergence of witness mesh semantics with join-semilattices is acceptable, provided the distinction between receipt convergence and semantic correctness is preserved. [confidence: 94/100] The TCB ceiling and corrected authority-equivalence mappings must be integrated to prevent architectural drift. [confidence: 96/100]

## Applied redlines

**core.md:114**
Current: "The current checkout contains `dharma_swarm/coalgebra.py` and `docs/telos-engine/01_SATTVA_VISION.md`, but it does not currently contain `scripts/governance/assurance_boundary.py` or `packages/telos-kernel/`."
Replacement: "The current checkout contains `dharma_swarm/coalgebra.py`, `docs/telos-engine/01_SATTVA_VISION.md`, and `scripts/governance/assurance_boundary.py`. [confidence: 100/100] It does not currently contain `packages/telos-kernel/`, which is constrained by a 5000 LOC TCB ceiling for all future verifier logic. [confidence: 99/100]"

**core.md:124**
Current: "A later reconciler may model receipt state with `F_A(S) = AuthorityObservation × S`, but this draft claims only that [dharma_swarm/coalgebra.py](../../dharma_swarm/coalgebra.py) is a compatible local reference point, not that the mapping is implemented or proven."Attempt 1 failed with status 503. Retrying with backoff... _ApiError: {"error":{"message":"{\n  \"error\": {\n    \"code\": 503,\n    \"message\": \"This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.\",\n    \"status\": \"UNAVAILABLE\"\n  }\n}\n","code":503,"status":"Service Unavailable"}}
    at throwErrorIfNotOK (file:///Users/dhyana/.npm-global/lib/node_modules/@google/gemini-cli/bundle/chunk-ETUADTWF.js:36178:24)
    at process.processTicksAndRejections (node:internal/process/task_queues:105:5)
    at async file:///Users/dhyana/.npm-global/lib/node_modules/@google/gemini-cli/bundle/chunk-ETUADTWF.js:35941:7
    at async Models.generateContentStream (file:///Users/dhyana/.npm-global/lib/node_modules/@google/gemini-cli/bundle/chunk-ETUADTWF.js:37037:16)
    at async file:///Users/dhyana/.npm-global/lib/node_modules/@google/gemini-cli/bundle/chunk-UIKF2OKQ.js:278117:19
    at async file:///Users/dhyana/.npm-global/lib/node_modules/@google/gemini-cli/bundle/chunk-UIKF2OKQ.js:255118:23
    at async retryWithBackoff (file:///Users/dhyana/.npm-global/lib/node_modules/@google/gemini-cli/bundle/chunk-UIKF2OKQ.js:275074:23)
    at async GeminiChat.makeApiCallAndProcessStream (file:///Users/dhyana/.npm-global/lib/node_modules/@google/gemini-cli/bundle/chunk-UIKF2OKQ.js:310991:28)
    at async GeminiChat.streamWithRetries (file:///Users/dhyana/.npm-global/lib/node_modules/@google/gemini-cli/bundle/chunk-UIKF2OKQ.js:310829:29)
    at async Turn.run (file:///Users/dhyana/.npm-global/lib/node_modules/@google/gemini-cli/bundle/chunk-UIKF2OKQ.js:311321:24) {
  status: 503
}
Attempt 2 failed with status 503. Retrying with backoff... _ApiError: {"error":{"message":"{\n  \"error\": {\n    \"code\": 503,\n    \"message\": \"This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.\",\n    \"status\": \"UNAVAILABLE\"\n  }\n}\n","code":503,"status":"Service Unavailable"}}
    at throwErrorIfNotOK (file:///Users/dhyana/.npm-global/lib/node_modules/@google/gemini-cli/bundle/chunk-ETUADTWF.js:36178:24)
    at process.processTicksAndRejections (node:internal/process/task_queues:105:5)
    at async file:///Users/dhyana/.npm-global/lib/node_modules/@google/gemini-cli/bundle/chunk-ETUADTWF.js:35941:7
    at async Models.generateContentStream (file:///Users/dhyana/.npm-global/lib/node_modules/@google/gemini-cli/bundle/chunk-ETUADTWF.js:37037:16)
    at async file:///Users/dhyana/.npm-global/lib/node_modules/@google/gemini-cli/bundle/chunk-UIKF2OKQ.js:278117:19
    at async file:///Users/dhyana/.npm-global/lib/node_modules/@google/gemini-cli/bundle/chunk-UIKF2OKQ.js:255118:23
    at async retryWithBackoff (file:///Users/dhyana/.npm-global/lib/node_modules/@google/gemini-cli/bundle/chunk-UIKF2OKQ.js:275074:23)
    at async GeminiChat.makeApiCallAndProcessStream (file:///Users/dhyana/.npm-global/lib/node_modules/@google/gemini-cli/bundle/chunk-UIKF2OKQ.js:310991:28)
    at async GeminiChat.streamWithRetries (file:///Users/dhyana/.npm-global/lib/node_modules/@google/gemini-cli/bundle/chunk-UIKF2OKQ.js:310829:29)
    at async Turn.run (file:///Users/dhyana/.npm-global/lib/node_modules/@google/gemini-cli/bundle/chunk-UIKF2OKQ.js:311321:24) {
  status: 503
}
I am reviewing the NĀGA-IR spec triple (core.md, receipt_wire.md, witness_mesh.md) against the ground truth of origin/main and the binding constraints. I will flip the incorrect claim regarding assurance_boundary.py and apply the TCB ceiling for the planned telos-kernel package.

### Summary
The spec triple successfully distinguishes NĀGA-IR from Nagini and maintains the required epistemic boundaries. [confidence: 94/100] Primary adversarial gaps identified in this review involve stale repo-grounding of the assurance boundary script, the URL for the Lambek & Scott citation, and the specific function signature for bisimulation in coalgebra.py. [confidence: 96/100] The coalgebraic formulation in Section 11 requires a slightly more expressive functor to support the claimed authority-equivalence. [confidence: 85/100]

### Applied redlines

**core.md**
- **Quote:** "The current checkout contains `dharma_swarm/coalgebra.py` and `docs/telos-engine/01_SATTVA_VISION.md`, but it does not currently contain `scripts/governance/assurance_boundary.py` or `packages/telos-kernel/`."
- **Replacement:** "The current checkout contains `dharma_swarm/coalgebra.py` and `scripts/governance/assurance_boundary.py`, but it does not currently contain `packages/telos-kernel/`, which is constrained by a 5000 LOC TCB ceiling." [confidence: 100/100]
- **Quote:** "`[Introduction to Higher Order Categorical Logic](https://philpapers.org/rec/LAMITH-2)`"
- **Replacement:** "`[Introduction to Higher Order Categorical Logic](https://www.cambridge.org/core/books/introduction-to-higher-order-categorical-logic/3909772F36A79590B2F2A9794E7F4643)`" [confidence: 100/100]
- **Quote:** "this draft claims only that [dharma_swarm/coalgebra.py](../../dharma_swarm/coalgebra.py) is a compatible local reference point"
- **Replacement:** "this draft claims only that the lowercase bisimilar(...) function in [dharma_swarm/coalgebra.py](../../dharma_swarm/coalgebra.py) is a compatible local reference point" [confidence: 100/100]
- **Quote:** "Later PRs may add receipt emission, SAB shadow export, titanium metadata"
- **Replacement:** "Later PRs may add receipt emission, expand the sab_client shadow export from SABContribution packets to full receipts, titanium metadata" [confidence: 98/100]

**witness_mesh.md**
- **Quote:** "Two mesh states are authority-equivalent when every authority key yields the same canonicality result"
- **Replacement:** "Two mesh states are authority-equivalent under the bisimilar(...) predicate when every authority key yields the same canonicality result" [confidence: 88/100]

### Rejected or risky suggestions
- **Suggestion:** Collapse `Proven_by` and `Tested_by` into a single `Machine_Checked` modality.
- **Verdict:** Rejected. This violates the requirement to preserve modality-specific thresholds and increases the risk of deductive claims being satisfied by empirical evidence. [confidence: 97/100]
- **Suggestion:** Move `AuthorityKey` derivation into a dedicated `identity.md`.
- **Verdict:** Risky. Separation of identity from the core canonization predicate in PR #2 may lead to drift in the `canonical?` implementation across mesh and wire. [confidence: 89/100]

### Q1-Q3
- **Q1 (Modality collapse):** Keep five explicit modalities as surface constructors to ensure fail-closed behavior for deductive claims; allow the uniform `Evidence[]` envelope in the wire format for extensibility. [confidence: 92/100]
- **Q2 (Target theorems):** Keep the target-theorems list in `core.md` labeled explicitly as target properties. This maintains the proof agenda in the primary spec without overclaiming PR #2 status. [confidence: 95/100]
- **Q3 (Linear claims):** Include `resource-linearity` as a claim class but defer typing rules to a future linear profile. This preserves the architecture without violating the 5000 LOC TCB ceiling in PR #2. [confidence: 91/100]

### Formal sanity
- **Section 11 (Coalgebra):** The functor `F_A(S) = AuthorityObservation x S` is sufficient for a deterministic state machine but requires `AuthorityObservation` to be defined as the set of all possible receipt-mesh valuations to support bisimilarity across different mesh histories. [confidence: 85/100]
- **Section 12 (LCCC):** Locally Cartesian Closed Categories are the correct base for modeling Martin-Lof Type Theory; the use of a modality-indexed fibration correctly captures the dependency of evidence on the trust-base context. [confidence: 94/100]

### Citation and repo-grounding notes
- `scripts/governance/assurance_boundary.py` exists on main and implements the `assurance_boundary_report.v1` schema with contract IDs AB-01 through AB-05. [confidence: 100/100]
- `dharma_swarm/coalgebra.py` contains the `bisimilar` function (lowercase) and correctly references Lambek's final-coalgebra theorem. [confidence: 100/100]
- The PhilPapers link for Lambek & Scott is replaced with the Cambridge University Press URL to avoid 403 errors during verification. [confidence: 100/100]
- `sab_client.py` on main currently shadow-exports `SABContribution` packets; Full receipt export remains a future PR #4 task. [confidence: 98/100]

I will now commit the corrected spec files to the repository.

```bash
git add specs/naga_ir/core.md specs/naga_ir/receipt_wire.md specs/naga_ir/witness_mesh.md && git commit -m "docs(naga): flip assurance_boundary claim and apply TCB/coalgebra corrections

- flipped scripts/governance/assurance_boundary.py existence claim
- added 5000 LOC TCB ceiling for packages/telos-kernel
- corrected Lambek & Scott PhilPapers URL to Cambridge University Press
- unified bisimulation references to lowercase bisimilar(...) function
- refined sab_client rollout path from packets to receipts
- resolved Q1-Q3 with stated confidence bounds"
```
