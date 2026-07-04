# NAGA-IR Elevation Round 1 Seat Contributions

## Fable seat

Tasks A-I were performed against `specs/naga_ir/core.md`, `receipt_wire.md`, and `witness_mesh.md`. [confidence: 98/100]

Applied redlines:

- Replaced the Thesis opening with the full wall sentence: "A code change is not authoritative because it exists, or because an agent produced it, or because CI passed. It is authoritative only when its claim is inhabited by admissible evidence, under a known trust base, inside a live context, without unresolved challenge." [confidence: 97/100]
- Added `Related work` paragraphs that explicitly fold MLIR verif, Viper, and Nagini related work into existing sections rather than leaving the Appendix B absence silent. [confidence: 91/100]
- Replaced the dead PhilPapers Lambek and Scott citation with the Cambridge University Press excerpt PDF that resolves with urllib. [confidence: 99/100]
- Added explicit Q1, Q2, and Q3 decisions in `core.md / Open decisions`: five surface modalities remain, target properties stay in core as targets only, and resource-linearity remains a claim class with proof rules deferred. [confidence: 95/100]
- Reconciled the core receipt field list with the wire schema by adding `schema_version` and `receipt_id` to `core.md / Wire reference`. [confidence: 96/100]
- Flipped the stale `assurance_boundary.py` absence claim: origin/main contains `scripts/governance/assurance_boundary.py`, with `assurance_boundary_report.v1`, AB-01 through AB-05, and exit codes 0, 1, 2. [confidence: 99/100]
- Added the `packages/telos-kernel/` future-only `<= 5000 LOC` TCB ceiling next to the telos-kernel mention. [confidence: 98/100]
- Clarified `core.md / Non-normative coalgebra` so the receipt functor is a future PR #6 design sketch, not the same functor as `dharma_swarm/coalgebra.py`, while referencing only lowercase `bisimilar(...)`. [confidence: 96/100]
- Added a fibration guardrail: the type-theory sketch becomes load-bearing only after it names base category, fibers, reindexing maps, substitution laws, and fail-closed authority-transfer rule. [confidence: 94/100]
- Stated that current `dharma_swarm/connectors/sab_client.py` exports `SABContribution` packets, not NAGA receipts, and that receipt export is future PR #4 work. [confidence: 98/100]
- Added a `Witnessed_by` required-body-field table in `receipt_wire.md`. [confidence: 94/100]
- Marked the wire example non-canonical not only because hashes and signatures are placeholders, but also because `Attested_by` cannot discharge a `deductive` claim without `Proven_by` evidence. [confidence: 96/100]
- Added the wire challenge-state set to `witness_mesh.md` and raised the non-normative authority-equivalence note from 84/100 to 91/100 by bounding it to finite snapshots, fixed challenge base, bounded horizon, and diagnostic observation instants. [confidence: 94/100]

Rejected or sharpened:

- Did not adopt Gemini's wording that mesh authority-equivalence is "under the `bisimilar(...)` predicate," because the repo `bisimilar(...)` function belongs to the evolution coalgebra and should not be imported as a mesh implementation. [confidence: 96/100]
- Did not adopt Codex's proposed wall sentence "Authority is not authored; it is checked, scoped, fresh, and defeasible" because the two required wall sentences are already stronger and contractually required. [confidence: 90/100]
- Did not collapse modalities into a generic machine-checked modality, because that would weaken the fail-closed distinction between deductive and empirical evidence. [confidence: 97/100]

## Codex seat

Raw successful output: `reports/naga_elevation/round_1/codex_last.md`. [confidence: 100/100]

Codex findings integrated:

- Fix `core.md / Local integration` so assurance boundary is present and telos-kernel is future-only with the TCB ceiling. [confidence: 99/100]
- Replace the PhilPapers citation with a live Lambek and Scott source. [confidence: 95/100]
- Explicitly say current SAB client emits packets, not NAGA receipts. [confidence: 97/100]
- Add LCCC and fibration guardrails before the type-theory sketch becomes load-bearing. [confidence: 94/100]
- Keep Q1 five modalities, Q2 target properties in core, and Q3 resource-linearity as a claim class with later proof rules. [confidence: 95/100]

Codex findings rejected or modified:

- Codex proposed `F_A(S) = S × AuthorityObservation` and a finite authority observation record. The synthesis adopted the finite-record part but kept a clear "future design sketch" boundary and avoided any proof claim. [confidence: 94/100]
- Codex proposed a diagnostic `canonical_status`; the synthesis adopted it as implementation diagnostic only, not as a replacement for the normative fail-closed boolean predicate. [confidence: 92/100]

Codex execution notes:

- First codex attempt timed out after 300 seconds and wrote `codex_raw.md`, which mostly contains the prompt trace. [confidence: 100/100]
- Retry used `codex exec --sandbox read-only --ephemeral --output-last-message` and exited 0. [confidence: 100/100]

## Gemini and Qwen seat

Gemini produced a substantive partial review in `gemini_raw_attempt1.md` before returning persistent 503 high-demand errors. [confidence: 94/100] Qwen fallback was attempted and failed with a 401 authentication error; the error output is preserved in `qwen_raw.md` and `gemini_or_qwen_raw.md`. [confidence: 100/100]

Gemini findings integrated:

- Flip `assurance_boundary.py` from absent to present and add the telos-kernel TCB ceiling. [confidence: 100/100]
- Replace the dead PhilPapers citation with a Cambridge source. [confidence: 100/100]
- Mention lowercase `bisimilar(...)` in the coalgebra reference. [confidence: 100/100]
- Clarify SAB export from current packets to future receipts. [confidence: 98/100]
- Keep Q1 five modalities plus uniform wire envelope, keep Q2 target properties in core, and keep Q3 resource-linearity as a claim class with proof rules deferred. [confidence: 95/100]

Gemini findings rejected or modified:

- The proposed witness sentence "authority-equivalent under the `bisimilar(...)` predicate" was not adopted because it would falsely imply the mesh equivalence is implemented by the evolution-coalgebra helper. [confidence: 96/100]
- The proposed Cambridge Core page returned HTTP 500 under urllib, so the synthesis used the Cambridge assets excerpt PDF URL that returned HTTP 200. [confidence: 99/100]
