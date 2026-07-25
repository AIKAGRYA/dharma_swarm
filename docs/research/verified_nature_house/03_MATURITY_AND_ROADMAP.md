# Maturity & Roadmap — Honest 5/100

**Status:** SEED. The operator's "5/100" is correct *for the business/credibility
product*. The *verification spine* is materially further along; the *welfare-ton
math and external feeds* are the early part. Scores below are this-dossier
estimates from the repo-organ inventory and market research, not audited metrics.

---

## 1. Component scoring (0–100)

| Component | Score | Justification |
|---|---:|---|
| Trace/verification spine (receipt, gates, quorum, attractor) | **70** | Working & reusable: `EvidenceReceipt`, `TelosGatekeeper` (11 gates), `VerificationOracle` 3-of-5 quorum, `AttractorPacket`, BLAKE2b ledger. The real asset. |
| GAIA pilot proof (Bayou Lafourche) | **40** | One genuine end-to-end pilot: real `ledger.jsonl`, 4-of-5 oracle quorum, 304→258.4 tCO2e verified, community participation tracked. One proof, not ten; feeds were partly mocked. |
| MRV core (ledger/verification/fitness) | **35** | Scaffold: data models + consensus algorithm work; production satellite/IoT integration is mock. |
| Welfare-ton formula `W = C×E×A×B×V×P` | **20** | Excellent ~1,200-line spec; code is a proxy (`carbon × verification_bonus × community_bonus`), not the real factorization. |
| Tamper-evident receipt (crypto) | **30** | Ledger hash-chains (BLAKE2b); the spine `EvidenceReceipt` is immutable but **unsigned**. Gap to court-grade. |
| Cross-family decorrelated verification | **25** | DPI + council exist (`coordination/dpi.py`); genuine cross-*family* error decorrelation is not yet wired into MRV. |
| Buyer / GTM / first receipt | **5** | $0 revenue, no external human has acted on a welfare-ton, no buyer conversation. **This is the 5/100 the operator means.** |
| Shrikanth alignment (credibility narrative) | **15** | Strong, sourced thesis; zero contact, no validation against his five rules on a real project. |

**Composite for the *product/business*: ~5/100. For the *verification
substrate*: ~50/100.** Both are true; do not average them into a comforting middle.

## 2. Staged path

**Stage 0 → first verifiable external receipt (the only thing that matters next).**
- Code the welfare-ton engine (full `C×E×A×B×V×P`), replacing the proxy.
- Add BLAKE2b chain + signature to `EvidenceReceipt`.
- Re-run the Bayou pilot **scored against Shrikanth's five rules**, soft factors
  (E, A, B) through decorrelated verifiers, minting gated on an external
  countersignature (One Wire).
- Put the resulting receipt in front of **one** real external human (nature-fund
  analyst / assurance reviewer / project developer). *Exit: they act on it.*
- This is the move from 5/100 to ~6/100. It is small on purpose.

**Stage 1 → first credible buyer conversation.**
- Validate the scorecard against the five rules on 1–2 *real* projects with a
  domain expert (ideally the Shrikanth-style ask in `01_SHRIKANTH_ALIGNMENT.md`).
- Position to the *paying* part of the market: integrity premium + assurance/
  disclosure demand — **not** biodiversity-credit procurement.
- Replace mocked feeds with one production satellite source.

**Stage 2 → repeatable verified outcomes.**
- 5–10 pilots; external quorum REST surface live; cross-family decorrelation wired.
- Only here does "verified nature house" become more than a seed.

## 3. The three hardest blockers (name them so they don't hide)

1. **The external feed / counterfactual wall.** dMRV *structurally cannot* verify
   additionality, permanence, soil carbon, or biodiversity from satellites — the
   exact factors we claim. Our edge is adjudicating the *soft* judgments with
   decorrelated verifiers + community ground-truth, but that needs real field data
   pipelines, which are expensive and slow. This is the long pole, not the math.
2. **The buyer/distribution wall (the operator's standing "no buyers").** Even the
   *paying* segments (assurance, integrity premium) require a sales motion a $0,
   one-operator + swarm does not have. The first receipt must be reachable
   *without* a sales pipeline — i.e. one warm expert review, not enterprise
   procurement.
3. **The credibility/self-minting trap.** The entire market is dying of numbers
   actors told themselves. If we ever mint a welfare-ton from internal artifacts,
   we become the disease. The One Wire invariant (`02_TRACE_ARCHITECTURE.md` §5) is
   the discipline that must never be weakened to make a demo look finished.

## 4. What this seed is NOT claiming

Not a product. Not revenue. Not a Shrikanth endorsement of the welfare-ton. Not
that biodiversity credits are a market (they are not). Not that the welfare-ton
math is built (it is a proxy). Not that the receipt is court-grade (it is unsigned).
It is a *direction* with a real verification spine under it and a single, honest,
reachable next step.
