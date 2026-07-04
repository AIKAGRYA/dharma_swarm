# Iteration Round 02 — Codex+ contribution

Source: Codex+ ran independently on user's Mac at /Users/dhyana/dharma_swarm.
Received: 2026-07-04 JST.
Codex+ self-rating: 91/100 for PR #2 spec-only scope, after adversarial + 6-defender review.
Fable assessment: HIGH-VALUE, materially stronger than Fable's v2 in most respects. Codex+ becomes the new base; Fable/Devin+ v2 items graft ONTO it, not the reverse.

## Meta

- Codex+ produced all three PR #2 files: core.md, receipt_wire.md, witness_mesh.md.
- Codex+ ran on branch `agent/magpie-seed`, which is missing `scripts/governance/assurance_boundary.py` and `packages/telos-kernel/`. Codex+ correctly noted these absences instead of pretending files exist. Fable's tree (titanium/phase-1e-ci-wiring) has both files. This branch divergence is important.
- Codex+ ran an internal adversarial + 6-defender council (per-agent scores: FM 93, Wire/Sec 92, Mesh 92, Repo/Gov 92, Philo 92, PR-readiness 91). Adversarial initial 76/100 → 91/100 after 7 blocker fixes.
- Codex+'s Ollama Cloud external council was quota-blocked; the 91/100 is native-only, honestly labeled.

## Direct comparison: Codex+ core.md vs Fable v2 core.md

### Where Codex+ WINS (accept Codex+'s version)

1. **§Canonization predicate is executable (Codex+ 96/100, Fable v2 was prose-only, 88/100).** Codex+ writes a shared `canonical?(receipt, mesh_state, current, t)` predicate as text pseudocode that all three files reference. This is a real formal move; Fable v2's Section 7 was English clauses. **Adopt Codex+.**

2. **§Admissibility matrix as claim_class × claim_strength × modality (Codex+ 94/100, Fable v2 was one-dim, 90/100).** Codex+ splits the matrix into two: strength ordering (deductive/empirical/differential/observational/attested) crossed with claim class (safety/purity/effect-boundary/contract/behavioral-equivalence/provenance/runtime-observation/resource-linearity). This is materially better than Fable v2 §6a's flat matrix, and it dissolves Devin+'s Q3 (linearity) by adding `resource-linearity` as a class with `deductive` strength "under a later linear profile". **Adopt Codex+.**

3. **§Coalgebra + type theory demoted to non-normative (Codex+ 96/100, Fable v2 was normative but weak, 82/100).** Codex+ separates "Non-normative coalgebra" and "Non-normative types" sections that explicitly label these as "target-only" until a calculus is defined. Fable v2's §11 and §12 were pretending to load-bear. Codex+ correctly identified them as formal-looking-but-not-formal. **Adopt Codex+.**

4. **§Wire schema is real (Codex+ 94/100, Fable v2 didn't have receipt_wire.md yet).** Codex+ shipped a receipt_wire.md with 14 required fields, five modality body schemas, JCS canonicalization ([RFC 8785](https://www.rfc-editor.org/rfc/rfc8785)), RFC 3339 timestamps, ed25519 signature policy, non-authoritative challenge_state summary, and a complete non-canonical example receipt. This is production-quality wire spec work. **Adopt Codex+.**

5. **§Mesh is join-semilattice, not vague CRDT (Codex+ 90/100, Fable v2 said "CRDT-like" without saying what, 78/100).** Codex+'s witness_mesh.md gives `MeshState = ORMap[AuthorityKey, EventSet]` with subset partial order and deterministic union join — an actual join-semilattice specification. Six event types with per-event merge thresholds. **Adopt Codex+.**

6. **§Confidence ratings inline (Codex+ per-sentence, Fable v2 per-section only).** Codex+ attaches `[confidence: N/100]` to individual claims. This is the per-claim discipline Fable had asked for. **Adopt Codex+.**

7. **§claim_hash + authority_key derivation (Codex+ 95/100, Fable v2 didn't have this at all).** Codex+ resolved a hidden hole Fable and Devin+ both missed: `claim_id` is user-chosen string, so an authority_key built from `claim_id` can be swapped by keeping the id and changing the statement. Fix: `claim_hash` is derived (SHA-256 over JCS of the claim object), and `authority_key` uses `claim_hash`, not `claim_id`. This is a real security fix. **Adopt Codex+.**

8. **§Clock skew as first-class (Codex+ 92/100, absent in Fable v2).** Codex+ has explicit `clock` field with `observed_at`, `clock_uncertainty_ms`, `max_clock_skew_ms`, and predicate returns `unknown` (not `canonical`) when skew exceeds bound. Handles TTL freshness properly. **Adopt Codex+.**

9. **§challenge_base + challenge_state split (Codex+ 96/100, absent in Fable v2).** This is Codex+'s answer to Devin+'s F4 liveness attack, and it's SHARPER than Devin+'s R3. Instead of "mesh-liveness receipt," Codex+ splits: `challenge_base` is the normative event base (mesh_id + query key + evidence horizon + base_snapshot_hash), `challenge_state` is a cached summary explicitly marked `authoritative: false`. Canonicality REQUIRES a query against `challenge_base`, not trust in the receipt-self-reported summary. This is stronger than the mesh-liveness receipt idea because it makes the query itself the primitive. **Adopt Codex+.**

10. **§"When" vs "while" — Codex+ used "when" (Devin+/Fable had "while").** Codex+ 92/100 uses "authoritative only when its claim is inhabited." The temporal semantics are handled by TTL + clock skew + mesh query, so "when" is legitimate here. Fable's "while" edit was aesthetic; Codex+'s wire-level temporal handling is more robust. Fable withdraws the "while" edit — Codex+'s architecture makes it unnecessary.

### Where Fable v2 / Devin+ WIN or ADD (graft onto Codex+)

1. **Wall sentence lineage note (Fable v2 90/100).** Fable v2's lineage note explicitly opens: "NĀGA-IR is a dialect-level assurance IR in the MLIR verif family sense; it is not a rename of, and does not compete with, ETH's Nagini." Codex+ has this as `## Lineage` section but folded into a paragraph. Fable's phrasing is slightly cleaner for the top-of-file lineage. Minor preference — Codex+ is fine as-is. NO-OP.

2. **BabelTele in threat model (Devin+ bonus 91/100).** Codex+'s §Threat model lists forgery paths but doesn't cite the "channel humans cannot read" surface. Devin+'s bonus insight: BabelTele-encoded channels are the cheapest forgery surface. **GRAFT: add one sentence to Codex+'s §Threat model citing BabelTele.**

3. **EcoLANG/PACT/BabelTele citations for compression line (Devin+ D-revised 93/100).** Codex+ doesn't have an Appendix B / Related work section at all. This is arguably fine (Codex+'s "Rollout" and lineage handle it), but the compression-line citations Devin+ verified are load-bearing motivation for the challenge modality. **GRAFT: add a brief "Related work" section OR cite these inline in §Threat model.**

4. **Explicit "no isomorphism" language for dharma (Codex+ has §Dharma boundary, 98/100).** Codex+'s §Dharma boundary is *stronger* than Fable v2's §15. Codex+ wins here. **Adopt Codex+.** No graft.

5. **Six target theorems C1-C6 (Fable v2 + Devin+ E1/E2, 87/100).** Codex+'s §Target theorems lists five: modality-indexed validity, canonicality decidability, monotonicity under narrowing, non-monotonicity under widening/trust-base substitution, challenge completeness. **Missing from Codex+: Devin+'s E1 revocation propagation and E2 no-authority-amplification-under-merge.** These are load-bearing on `prev_receipt_hash` and mesh merge, respectively. **GRAFT: add C6 revocation propagation and C7 no authority amplification to Codex+'s target theorems list.**

6. **§9 assurance_boundary_report.v1 compat (Fable v2 91/100, Codex+ missing).** Codex+'s tree doesn't have `assurance_boundary.py`; Fable's tree does. Codex+ correctly declined to write a compatibility section without the file present. **On Fable's branch (titanium/phase-1e-ci-wiring), this section MUST be added back** because on that branch it's true. But it should be gated: "when this spec is merged onto a branch containing scripts/governance/assurance_boundary.py, PR #3 will emit dharma.naga_receipt.v1 alongside the existing assurance_boundary_report.v1 verdict." **GRAFT with branch-conditional framing.**

7. **§Rollout arc PRs #2-#7 (Fable v2 90/100, Codex+ has abbreviated rollout).** Codex+'s §Rollout says "later PRs may add receipt emission, SAB shadow export, titanium metadata, coalgebraic reconciliation, and arena design" without numbering. Fable's numbered arc is more actionable. **GRAFT: replace Codex+'s prose rollout with numbered PR#2-#7 arc (Fable's version).**

### Where Codex+ is WRONG or WEAK

1. **§Local integration claims files absent that ARE present on Fable's branch (Codex+ 99/100 within its own tree, but branch-specific).** Codex+ wrote: "the current checkout... does not currently contain scripts/governance/assurance_boundary.py or packages/telos-kernel/." True on `agent/magpie-seed`; FALSE on `titanium/phase-1e-ci-wiring`. **FIX: rephrase as branch-conditional statement, and note that the merge target for PR #2 must select a branch that either has these files or explicitly names them as planned integration targets.**

2. **Nothing else genuinely wrong.** The adversarial-review-then-patch process closed the real holes.

## Comparative confidence

| File | Fable v2 (pre-Codex+) | Codex+ standalone | Fable v3 (Codex+ base + grafts) |
|---|---|---|---|
| core.md | 92/100 | 91/100 | 94/100 |
| receipt_wire.md | not yet drafted | 92/100 | 93/100 |
| witness_mesh.md | not yet drafted | 92/100 | 93/100 |

Codex+ is standalone-lower than Fable v2 by 1 point because it lacks the assurance_boundary compat + numbered rollout + revocation/merge theorems. But its wire and mesh work more than compensate. **Merging the two produces the strongest artifact of the round.**

## Fable's decision

**Base: Codex+ core.md, receipt_wire.md, witness_mesh.md verbatim.**

**Grafts onto core.md:**
- G1: BabelTele sentence in §Threat model
- G2: Add C6 revocation propagation + C7 no-authority-amplification-under-merge to §Target theorems
- G3: Add branch-conditional §Assurance boundary compatibility (with fragment_version guard so it doesn't false-claim on branches without the file)
- G4: Replace prose §Rollout with numbered PR#2-#7 arc
- G5: Correct §Local integration to be branch-conditional, not tree-specific

**No grafts to receipt_wire.md or witness_mesh.md.** Codex+'s versions are cleaner than anything Fable/Devin+ would have written.

## Items to raise with next agent (round 03)

- Q11: Codex+'s claim strengths are five (deductive/empirical/differential/observational/attested). Should there be a sixth for `causal` (provenance-only)? Codex+ merged provenance into a claim CLASS, not a strength.
- Q12: The JCS canonicalization ([RFC 8785](https://www.rfc-editor.org/rfc/rfc8785)) is the load-bearing choice for signature input. Is there a stronger alternative (e.g. COSE Sign1 / CBOR canonicalization)? JCS is JSON-native and simpler; CBOR would be smaller and stricter. Trade-off.
- Q13: `evidence_horizon: P14D` in Codex+'s example is arbitrary. Should the spec constrain horizon to min/max bounds? A 1-second horizon defeats the point; a 10-year horizon is meaningless.
- Q14: Codex+'s §Non-normative bisim in witness_mesh.md is downgraded correctly, but it might still be worth capturing as a target theorem C8 (mesh authority-equivalence) rather than a design note.
- Q15: Redaction policy in mesh (`privacy_rule`) is present but under-specified. What are the admissible redaction methods? (hash-only, encrypted-body-with-key-escrow, tombstone?)

## Devin+ items status against Codex+

- Devin+ Q1 (kernel/surface split): Codex+ handles this in §Evidence modalities: "five explicit modalities stay in the core spec as surface constructors, while the wire schema may store them in a uniform envelope of `Evidence[modality, method, params](C)`." SATISFIED, 93/100.
- Devin+ Q2 (theorems location): Codex+ keeps them in core.md under §Target theorems, labeled as target-only, not proven. SATISFIED, 92/100.
- Devin+ Q3 (linearity claim type): Codex+ adds `resource-linearity` as a claim CLASS with `deductive` strength "under a later linear profile." STRONGER than Devin+'s "defer to linear.md" — Codex+ makes the slot exist without inhabiting it prematurely. 94/100.
- Devin+ F1 (coalgebra "reuses" false): Codex+ demoted coalgebra to §Non-normative coalgebra. SATISFIED, 96/100.
- Devin+ F2 (modality ordering): Codex+ makes admissibility a claim-class-specific relation. SATISFIED, 95/100.
- Devin+ F3 (proof-relevance): Codex+ demoted type-theory to non-normative, avoiding the issue rather than committing to proof-relevance. WEAKER than Devin+'s fix, but appropriate for PR #2 scope. 90/100.
- Devin+ F4 (liveness attack): Codex+'s challenge_base + non-authoritative challenge_state solution is STRONGER than Devin+'s R3. SATISFIED, 96/100.
- Devin+ E1 (revocation propagation): NOT PRESENT in Codex+. **GRAFT this.**
- Devin+ E2 (no authority amplification under merge): NOT PRESENT in Codex+. **GRAFT this.**
- Devin+ G (fibration split): Codex+ demoted the whole type-theory section to non-normative, so the fibration split becomes moot. RESOLVED by demotion, 88/100.
- Devin+ H (functor correction): Codex+ demoted coalgebra to non-normative and doesn't state the functor at all. RESOLVED by demotion, 88/100.
- Devin+ I ("when" → "while"): Codex+ handles temporal semantics via TTL + clock + mesh query, so "when" is fine. Fable withdraws this. RESOLVED, 91/100.
- Devin+ D-revised (EcoLANG/PACT/BabelTele): Codex+ has no Appendix B. **GRAFT: cite these in §Threat model or as a brief §Related work.**

Net: **8 of Devin+'s items are subsumed or improved by Codex+, 2 items need to be grafted (E1, E2), 1 more needs to be grafted for citations (D-revised).**

## Fable rating of Codex+ round 02: 95/100

Highest-value items in order:
1. challenge_base + non-authoritative challenge_state (96/100) — the sharpest response to F4 possible
2. Executable canonicality predicate shared across all three files (96/100)
3. claim_hash derivation solves a hidden security hole (95/100)
4. Wire schema with JCS + RFC 3339 + explicit signature policy (94/100)
5. Two-dimensional claim_class × claim_strength admissibility matrix (94/100)
6. Correct demotion of coalgebra + type theory to non-normative (96/100)
7. Join-semilattice mesh state (90/100)
8. Adversarial + 6-defender native council with truthful 91/100 label (92/100)

Zero rejects. Two grafts required (E1 revocation, E2 merge). Three minor grafts (BabelTele, rollout numbering, assurance_boundary branch-conditional).

Codex+ delivered production-quality spec work. Fable's v3 will incorporate ~95% of Codex+ verbatim.
