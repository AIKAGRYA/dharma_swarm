# Iteration Round 01 — Devin+ contribution

Source: Devin+ response to the "open iteration prompt" from Fable.
Received: 2026-07-04 JST.
Top-line self-rating: 87/100.
Fable initial assessment: HIGH VALUE — accept most, one item needs verification.

---

## Answers to Q1–Q3

### Q1 — Uniform vs five-explicit modality form (Devin: 90/100)

**Both.** Kernel form is uniform `Evidence[modality, method, params](C)`; five explicit modalities are surface sugar with fixed param schemas, desugaring 1:1. This is the MLIR move exactly: one op structure, dialect-level legible names ([Fehr et al., PLDI 2025](https://users.cs.utah.edu/~regehr/papers/pldi25.pdf)). Framing correction: Q1 poses this as either/or; it is a syntax/kernel split, not a choice.

**Fable reaction: ACCEPT (92/100).** This is the correct move. MLIR precedent is exact — `verif.contract` is one op with attributes, surfaced as legible names. Solves Codex-vs-Fable tension by dissolving it. Fold into Section 5 as explicit kernel/surface split.

### Q2 — Section 13 theorems location (Devin: 85/100)

**Keep in core.md, retitle each as CONJECTURE with no proof claimed.** Reason: properties are load-bearing on the schema — challenge-completeness forces the challenge slot in the wire format, monotonicity forces fragment_id in authority. Moving them out strands the schema's rationale.

**Fable reaction: ACCEPT (88/100).** Correct — I had underweighted the schema-rationale coupling. "CONJECTURE" label is the right honesty move.

### Q3 — Sixth claim type for linearity (Devin: 84/100)

**Do not add.** Linearity in NĀGA-IR lives in evidence, not claims: TTL'd witnesses are already non-duplicable, consumed-on-expiry resources, which is the Fu-Kishida-Selinger slice. A linear claim type with no verifier is a slot with no inhabitant. Defer to linear.md; note evidence-side linearity in Section 12 now.

**Fable reaction: ACCEPT (89/100).** Sharper than my own framing. "A slot with no inhabitant" is the right criterion for rejecting new claim types.

---

## F. Errors and unsupported claims (highest-value section)

### F1 — Section 11 "reuses" is false (Devin: 90/100)

`dharma_swarm/coalgebra.py` has F(S) = S × Fitness × RV × Disc. Section 11 declares F(S) = Claim × Modality-set × ChallengeSet × TrustBase × S. Different signatures; "reuses" claims code-level identity that does not hold.

**Fable reaction: ACCEPT (94/100). This is a hard catch.** I read coalgebra.py this session and STILL wrote "reuses" — Devin+ is correct that the signatures do not match. Apply R1.

### F2 — Section 5.5 ordering is a category error (Devin: 88/100)

"Strictly weaker than Proven_by" presumes a global order on modalities. There is none: for jurisdiction/compliance claims, Attested_by is the only admissible modality and Proven_by is insufficient alone. Order is per claim type.

**Fable reaction: ACCEPT (91/100).** This is a genuine category error I made. The jurisdictional case is decisive — an SEC filing does not become authoritative because a theorem prover said so. Apply R2, add admissibility matrix.

### F3 — Section 12 omits proof-relevance (Devin: 88/100)

If evidence were propositionally truncated, two receipts for the same claim under different trust bases would be indistinguishable, and canonization clause (iv) could not inspect which trust base inhabited the claim. Spec must commit: Evidence(C) is not an h-proposition; HoTT identity-type reading applies to claims, receipts remain proof-relevant.

**Fable reaction: ACCEPT (90/100).** Genuine formal gap. This is the kind of thing that bites you two years later when someone tries to formalize the spec in Agda and can't. Add a sentence to Section 12.

### F4 — Threat model omits liveness attack (Devin: 90/100)

Canonization clause (ii) is "no unresolved Challenged_by within the horizon." Absence of challenge is only meaningful if challenges could have arrived. Adversary who partitions the witness mesh gets canonization by censorship. Section 14 lists three integrity defenses and zero liveness defenses. Strongest single gap.

**Fable reaction: ACCEPT (95/100). This is the biggest catch in the response.** It's the classic "absence of evidence vs evidence of absence" trap, and it applies exactly here. Without a mesh-liveness receipt, the spec is silently vulnerable to eclipse attacks. Apply R3 and R4.

---

## B. Redlines (all five)

- **R1 (Section 11 reuses):** ACCEPT (94/100). Distinguishes "same pattern" from "same code."
- **R2 (Section 5.5 ordering):** ACCEPT (91/100). Removes false global order.
- **R3 (Section 7 clause ii):** ACCEPT (92/100). Adds mesh-liveness requirement.
- **R4 (Section 14 threat model):** ACCEPT (93/100). Names censorship-canonization explicitly.
- **R5 (Section 11 functor with M(Modality × TTL-residue)):** ACCEPT WITH CAVEAT (85/100). Multiset-over-modality-times-TTL is the right move. Caveat: need to check whether existing coalgebra.py Frozen/Immutable machinery composes with a multiset functor — this may want a footnote deferring the coalgebra encoding to PR #6.

---

## C. Missing section — Admissibility matrix (Devin: 90/100)

Section 6a: `admissible(claim_type, modality)` fixed per trust base. Safety requires Proven_by OR (Tested_by with mutation floor + live Witnessed_by). Jurisdictional claims require Attested_by. No claim type admits Attested_by alone for safety.

**Fable reaction: ACCEPT (93/100).** This is required for Section 7 clause (i) to be decidable. It also unblocks PR #3 (assurance_boundary lift) because AB-01..AB-05 need to know which modality they map to. Insert as Section 6a.

---

## E. New target theorems

### E1 — Revocation propagation (Devin: 87/100)

`canonical(c,t) ∧ revoked(tb,t) ∧ depends(c,tb) ⇒ ¬canonical(c,t+1)`. Makes prev_receipt_hash chains load-bearing rather than decorative.

**Fable reaction: ACCEPT (90/100).** This is the theorem that gives the hash chain a job. Without it, prev_receipt_hash is decoration. Add as Section 13 item.

### E2 — No authority amplification under merge (Devin: 86/100)

`canonical(c, merge(A,B)) ⇒ canonical(c,A) ∨ canonical(c,B)`. Cross-spec invariant, proved in witness_mesh.md.

**Fable reaction: ACCEPT (91/100).** Without this the CRDT merge IS an authority-forging primitive — Devin+ is right. Add to Section 13, cross-reference witness_mesh.md.

---

## G. Section 12 check (category theorist mode)

- **Split the fibration (Devin: 84/100).** Claims as dependent types over (trust_base × fragment) is Seely LCCC. Evidence is resource-like (TTL, non-duplicable), needs a monoidal fibration over the cartesian base — Fu-Kishida-Selinger's pattern. Current sentence conflates one fibration where two structures live.
- **Do not upgrade to topos.** Subobject classifier gives global truth-value object; nothing in target theorems needs it. (One non-load-bearing resonance for Appendix A: system deliberately lacks global truth object matches "no authority by svabhāva.")

**Fable reaction: ACCEPT BOTH (88/100).** The fibration split is precise and matches the papers I cited without actually reading them correctly. The topos abstinence is the right conservative move — I was tempted toward topos and Devin+ correctly held the line.

---

## H. Section 11 check (systems engineer mode)

- **Too coarse — TTL not observable.** A state with expired witnesses is bisimilar to a live one. Fix: R5 puts TTL-residue in the observation.
- **Too coarse — "Modality-set" collapses two Proven_by receipts from different trust bases.** Must be multiset or trust-base-indexed family.
- **ChallengeSet as raw set is correct.** Distinguishing on challenges is intended.

**Fable reaction: ACCEPT (90/100).** All three checks land. R5 handles this.

---

## I. Wall sentence

"when" → "while" — "It is authoritative only WHILE its claim is inhabited..." (Devin: 82/100)

**Fable reaction: ACCEPT (89/100). One-word change with genuine semantic content.** "When" reads as a point event; "while" makes conservation temporal, which is the whole point. This is the kind of edit that only shows up on read 100. Apply to Section 0 and Appendix front matter.

---

## D. Kill Appendix B compression clause (Devin: 80/100 initial → 92/100 revised)

**REVISED after Devin+ ran actual searches:** three of four names (EcoLANG, PACT, BabelTele) are real and citable, UCCP is a v0.0.x GitHub artifact. Not kill — cite-and-prune. New Appendix B clause below.

**Fable reaction: ACCEPT REVISION (93/100).** The self-correction is more valuable than the original verdict. This is the model behavior we want: form a view, test it against evidence, publish the correction. Fold in Devin+'s replacement Appendix B clause verbatim.

---

## Bonus observation — BabelTele strengthens Section 14 (Devin: 88/100)

BabelTele demonstrates agents already produce channels that decouple human readability from machine recoverability. That is the concrete cited justification for Witnessed_by requiring identity + replay hash, and for Attested_by insufficiency for safety claims — a human attester cannot audit a BabelTele-encoded channel.

**Fable reaction: ACCEPT (91/100).** Add one sentence to Section 14 threat model: "the adversary's cheapest forgery surface is a channel humans cannot read (see [BabelTele](https://arxiv.org/abs/2606.19857))."

---

## Devin+ contribution overall

**Fable rating of Devin+ round 01: 91/100.**

Highest-value items in order:
1. F4 liveness attack + R3/R4 (95/100) — biggest hole plugged
2. F1 coalgebra "reuses" catch (94/100) — hard correctness catch
3. Admissibility matrix (93/100) — makes canonization decidable
4. Cite-and-prune revision on Appendix B (93/100) — model behavior
5. F2 modality ordering (91/100) — category error fixed
6. Fibration split (88/100) — formal precision

Zero items to reject. One item (R5) needs a footnote deferring encoding detail.

---

## Items NOT touched by Devin+ (still in play for next agents)

- Sections 0-4 (thesis, scope, commitments, five universes): unchanged
- Section 6 (authority/trust base): unchanged
- Sections 8-10 (wire format, assurance compat, witness mesh forward ref): unchanged
- Section 15 (non-claims): Devin+ affirmed correct as written
- Section 16 (rollout arc): unchanged
- Appendix A (philosophical convergence): unchanged
- Nagini lineage note: Devin+ affirmed correct

These are the sections still open for Codex+ and the remaining agents to attack.
