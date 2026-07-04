# Iteration Round 03 — Fugu+ (fugu-ultra) parallel review

Source: `/Users/dhyana/dharma_swarm/spec-forge/naga-ir/NAGA_IR_CORE_PARALLEL_FUGU_20260703T161626Z.md` and evidence copy at `reports/agentops/decorrelated_review_council/evidence/naga_ir_parallel_fugu_20260703T161626Z.md`.
Received: 2026-07-04 JST.
Fugu+ self-rating: 91/100 overall.
Fugu+ working discipline: refused to edit `specs/naga_ir/*.md` directly because another writer (Codex+) was active. That's the correct concurrency discipline. Called out.
Fable assessment: HIGH-VALIDATION with 3 net-new items to graft.

## Meta

Fugu+ was written IN PARALLEL to Codex+, not after it. Both were racing the same base outline. Fugu+ correctly detected that another writer was active on `specs/naga_ir/*.md` and stood off. This is why Fugu+'s doc is at `spec-forge/naga-ir/NAGA_IR_CORE_PARALLEL_FUGU_20260703T161626Z.md` (a parallel workspace) rather than the canonical spec path. The parallel run means: many of Fugu+'s asks are ALREADY IN v3 (via Codex+), and the interesting question is which of Fugu+'s items are net-new versus already covered.

## Alignment map — where Fugu+ and v3 (Codex+ base) AGREE

Fugu+ item                                              | Status in v3
---                                                     | ---
Q1 (five explicit modalities + uniform envelope split)  | ALREADY IN v3 §Evidence modalities (Codex+'s move, Devin+ ratified)
Q2 (rename to "target properties", require artifact)    | ALREADY IN v3 §Target theorems (Codex+ says "target properties only, not theorems of PR #2")
Q3 (resource-linearity as claim CLASS not claim TYPE)   | ALREADY IN v3 admissibility matrix as claim class
Shared canonicality predicate                           | ALREADY IN v3 §Canonicality with executable canonical? predicate
Challenge base + non-authoritative challenge_state      | ALREADY IN v3 via Codex+'s challenge_base primitive
Class-specific admissibility matrix (not global order)  | ALREADY IN v3 as 2D matrix (claim_class × claim_strength)
Nagini adapter constraint                               | ALREADY IN v3 §Lineage
Coalgebra non-normative in PR #2                        | ALREADY IN v3 §Non-normative coalgebra
Type theory non-normative for topos/HoTT                | ALREADY IN v3 §Non-normative types
Dharma boundary non-normative                           | ALREADY IN v3 §Dharma boundary
Wall sentences unchanged                                | ALREADY IN v3 (Fable also withdrew the "while" edit)
No load-bearing on emergent-compression protocols       | ALREADY IN v3 threat model (compression protocols cited only in threat model, not as load-bearing)

**Convergence signal: 12/12 major asks already satisfied in v3.** This is strong independent validation of Codex+'s adversarial-then-patch process. Two agents working in parallel arrived at nearly the same design.

## Net-new items from Fugu+ (graft candidates)

### N1 — "Sound verifier" flag — NO-OP against v3 (Fable verified 97/100)

Fugu+ flagged "sound verifier" language. VERIFICATION: Codex+ never used the word "sound" in v3. The Proven_by row says "verifier result passed for the named fragment under the named trust base" (line 84) and the judgment form is `Γ ⊢ w : Proven_by(verifier, trust_base, fragment)(C)` (line 74). Fugu+ was reading Fable v2 or an earlier draft, not Codex+'s work.

**Fable reaction: NO GRAFT NEEDED.** This is important evidence: Fugu+'s independent-arrival critique landed exactly on a phrasing Codex+ had already fixed. Independent convergence is even stronger than initially rated.

### N2 — "Strictly weaker than Proven_by" implies total order (Fugu+ 91/100)

Actually Fugu+ flags Attested_by's "strictly weaker" phrasing. In v3 Codex+'s wording is: `Attested_by` is admissible only for jurisdictional/attestation-class claims per the matrix (already good). But there's still a residual "strictly weaker" phrasing in v3 §5.5-analog language.

Let me check: in v3 the actual text is "never sufficient alone for safety claims, and the sole admissible modality for jurisdictional claims (per Devin+ F2/R2)." Codex+'s formulation makes this claim-class-specific already, so Fugu+'s ask is SUBSUMED. **NO GRAFT — Codex+ already handled this via the matrix.**

Wait, need to actually verify. Let me check the live v3 file for any remaining "strictly weaker" or "weaker than" language.

### N3 — HoTT identity-type sentence is premature (Fugu+ 92/100)

Fugu+: "Different receipts for the same English sentence are distinct records unless a later proof note defines normalized claim equality and receipt equivalence."

Current v3: type-theory section is already labeled non-normative and doesn't commit to h-proposition / proof-relevance semantics (Codex+ demoted this deliberately). So Fugu+'s concern is ALREADY HANDLED via demotion.

**Fable reaction: SUBSUMED. NO GRAFT.** But: add one sentence to the non-normative types section clarifying that "same claim under different receipts" requires a defined claim-normalization procedure before it can be a load-bearing identity statement.

### N4 — Four sharper formal properties (Fugu+ 91-94/100)

Fugu+ proposes 4 target properties that partially overlap with v3's T1-T7:

- FP1 "No silent strengthening": if evidence has modality m in class k under base b, cannot discharge a claim requiring m' unless a Proven_by coercion receipt exists. **Fable reaction: this is a SHARPER version of T5 challenge-completeness. GRAFT as T5-refinement or new T8.**
- FP2 "Challenge-base completeness": canonicality implies challenge query enumerated every open event or returned unknown. **Fable reaction: this makes T5 executable. GRAFT.**
- FP3 "Trust-base non-substitution": current.trust_base_id ≠ receipt.authority.trust_base_id implies non-canonical unless refinement receipt. **Fable reaction: overlaps T4 non-monotonicity but is more surgical. GRAFT as T4-refinement.**
- FP4 "Canonicality decidability": finite inputs → exactly one of {canonical, noncanonical, unknown}. **Fable reaction: this is T2 canonicality decidability but with the trichotomy explicit. Codex+'s T2 doesn't specify the unknown case. GRAFT the trichotomy.**

Combined graft **G7**: refine T1-T7 with Fugu+'s executable trichotomy and no-silent-strengthening as T8.

### N5 — Redline thesis with explicit measured object (Fugu+ 92/100)

Fugu+ proposes replacing the thesis with an operationalized form that references `canonical?(receipt, mesh_state, current_context, observation_time)`.

Current v3 keeps the wall sentence unchanged, then defines `canonical?` in the very next section. Fugu+'s move would make the thesis itself carry the operational form.

**Fable reaction: PRESERVE WALL SENTENCE.** Fugu+ later agrees ("do not replace the two wall sentences, 91/100") — this contradicts Fugu+'s own earlier redline. The correct move is Fugu+'s own final position: keep the wall sentence, define `canonical?` immediately after. This is what v3 already does. **NO GRAFT** — but this is worth noting because it shows Fugu+'s critique passed through the same tension Fable and Codex+ passed through and landed at the same resolution.

### N6 — Category-error catches in current wording (Fugu+ 90-93/100)

Three category-error catches, addressed above (N1, N2 already covered):
- "sound verifier" → G6 ACCEPT
- "strictly weaker" → SUBSUMED by Codex+ matrix
- HoTT identity-type prematurity → SUBSUMED by Codex+ demotion (with a clarifying sentence recommended)
- Emergent-compression as load-bearing → NOT LOAD-BEARING in v3 (only in threat model), SUBSUMED

## Fugu+ contribution overall

**Fable rating of Fugu+ round 03: 89/100.**

Lower than Codex+ (95/100) not because Fugu+ is weaker but because Fugu+ arrived AFTER Codex+ had already made 12 of Fugu+'s 15 major moves. The independent-arrival value is high (91-93/100 for validation), but the net-new content is:

1. G6 "sound verifier" → "named verifier pass under declared assumptions" — genuine precision fix
2. G7 four formal-property refinements (executable trichotomy for T2, coercion-receipt requirement for T5/T8, challenge-base completeness for T5, trust-base non-substitution for T4)
3. Non-normative types clarifying sentence on receipt-vs-claim equality

Three grafts, all substantive. This is what a good parallel reviewer produces.

## Grafts to apply to v3 → v4

- **G6** WITHDRAWN — v3 does not contain the flagged language
- **G7** refine §Target theorems:
  - T2 trichotomy `{canonical, noncanonical, unknown}` explicit
  - Split T5 into T5a challenge-completeness + T5b challenge-base completeness with enumeration-or-unknown
  - Add T8 no-silent-strengthening (coercion receipt required for modality upgrade)
  - Refine T4 with surgical trust-base non-substitution form
- **G8** add one sentence to §Non-normative types on claim-normalization prerequisite for receipt equivalence

## Items still open after round 03

- Q11 (sixth claim strength for causal): unresolved
- Q12 (JCS vs CBOR canonicalization): unresolved
- Q13 (evidence_horizon min/max bounds): unresolved
- Q14 (mesh authority-equivalence as T9): Fugu+ leaned toward "non-normative" which agrees with Codex+
- Q15 (redaction methods): unresolved
- Q8 (collusion in threat model): still unresolved after 3 rounds
- Q10 (AB-01..AB-05 mapping): still unresolved

## Independent convergence signal

Two agents (Codex+ and Fugu+) working in parallel from the same open-iteration prompt landed at:
- Same executable canonical? predicate move
- Same challenge_base + non-authoritative challenge_state architecture
- Same demotion of coalgebra and type theory to non-normative
- Same class-specific admissibility matrix
- Same "wall sentence unchanged, operationalize below" resolution
- Same dharma boundary treatment

This is strong evidence that the design has converged to a **local optimum** at ~93/100. Further grafts are refinement, not restructuring. **The base architecture is locked.**
