# How a Welfare-Ton Claim Is Traced and Verified Through dharma_swarm

**Status:** SEED (5/100). Architecture scope, grounded in a repo-symbol inventory
(2026-06-26). Cites real classes/files. Separates REUSABLE-AS-IS from MUST-BUILD.
Creates no new truth store; projects over `spine.EvidenceReceipt` + the GAIA ledger.

---

## 1. The claim we trace

> *"1 hectare of mangrove was restored, community-led, in Bayou Lafourche —
> worth N welfare-tons."*

This is a high-stakes external claim: someone may pay or stake reputation on it.
It must survive Shrikanth's five rules (additionality, leakage, permanence,
outcomes-after-counterfactual, credible biodiversity proxy — *paraphrased pending
the primary text; see `01` §boundary*) and emit a
tamper-evident, decomposable receipt.

## 2. The pipeline (real symbols)

```
  EXTERNAL WORLD                                          OWNER (file:symbol)
  ─────────────                                          ──────────────────
  field report / satellite / sensor / community attest
        │
        ▼
  [1] SENSE      project + evidence intake        gaia_platform.py : GaiaProject
        │                                           (hectares, carbon_potential,
        │                                            labor, verification_channels)
        ▼
  [2] INTERPRET  classify + frame the claim        gaia_platform.py : GaiaPlatform
        │                                           assessment / recommendation
        ▼
  [3] CONSTRAIN  behavioral gate (ZERO-KILL)       telos_gates.py : TelosGatekeeper
        │         AHIMSA(no harm) · SATYA(truth)     → GateDecision{status, reason,
        │         · JAGAT_KALYAN(welfare)              evidence, severity}
        │         block if any zero-kill factor=0
        ▼
  [4] VERIFY     decorrelated quorum (the V factor) gaia_verification.py :
        │         5 oracle types, 3-of-5 threshold     VerificationOracle /
        │         satellite·IoT·human·community·model  VerificationSession
        │         final_confidence = mean(agreeing)    coordination/dpi.py (DPI:
        │         decorrelation gated on correctness   decorrelation_bonus)
        ▼
  [5] RECEIPT    immutable attestation              spine/receipt.py : EvidenceReceipt
        │         trace_id, claim_id, claim_status,    (frozen) ; spine/invoke.py :
        │         status, cost; to_dict/to_otel        invoke_agent (blessed path)
        ▼
  [6] LEDGER     append-only, hash-chained           gaia_ledger.py (BLAKE2b chain;
        │         5 unit types, conservation laws       ComputeUnit/OffsetUnit/
        │                                               FundingUnit/LaborUnit/
        │                                               VerificationUnit)
        ▼
  [7] PROJECT    provenance / value read model       trace_attractor/models.py :
        │         linked IDs, ValueSummary,             AttractorPacket
        │         ProvenanceGraph (PROV), to_jsonld
        ▼
  [8] MINT       welfare-ton issued ONLY above       (MUST-BUILD: external
                 external countersigned quorum         countersignature gate)
```

## 3. Step-by-step, with the five-rules tie

1. **SENSE** — `GaiaProject` (`gaia_platform.py`) captures hectares,
   `carbon_potential`, labor, and declared verification channels. *Reusable.*
2. **INTERPRET** — `GaiaPlatform` assessment frames and ranks the claim. *Reusable
   (scaffold).*
3. **CONSTRAIN** — `TelosGatekeeper` (`telos_gates.py`, 11 gates across 3 tiers)
   returns a `GateDecision{status: ok|warn|block, reason, evidence, severity}`. The
   **zero-kill** check lives here: if biodiversity (B) or community-agency (A)
   resolves to zero, the gate blocks — no laundering carbon over social/ecological
   harm. *Reusable as the gate; the zero-kill predicate is MUST-BUILD.*
4. **VERIFY** — `VerificationOracle` / `VerificationSession` (`gaia_verification.py`)
   runs a **3-of-5 oracle quorum** (satellite, IoT, human auditor, community,
   statistical model), `final_confidence = mean(agreeing verdicts)`. This is the
   **V** factor and the structural answer to Shrikanth's "credits only after
   outcomes" + the raters'-disagreement problem: independent, error-decorrelated
   verifiers with no shared failure mode. The DPI (`coordination/dpi.py`) gates the
   decorrelation bonus on *actual correctness*, so disagreement can't be gamed into
   credit. *Reusable; cross-family decorrelation is partial → MUST-BUILD.*
5. **RECEIPT** — every dispatch through `invoke_agent` (`spine/invoke.py`) emits an
   `EvidenceReceipt` (`spine/receipt.py`, frozen dataclass: trace_id, claim_id,
   claim_status, status, cost, OTel export). *Reusable — BUT see the gap below.*
6. **LEDGER** — `gaia_ledger.py` appends BLAKE2b-hash-chained entries across five
   unit types with conservation laws (this is the genuinely tamper-evident store
   today; the Bayou pilot's `ledger.jsonl` is a real instance). *Reusable.*
7. **PROJECT** — `AttractorPacket` (`trace_attractor/models.py`) collects linked
   IDs, a `ValueSummary`, and a PROV-compatible `ProvenanceGraph`, with a JSON-LD
   stub for interchange. *Reusable.*
8. **MINT** — the welfare-ton is issued. This is where the invariant binds (§5).

## 4. Reusable-as-is vs Must-build

**Reusable today (the verification spine is real):**
`EvidenceReceipt`, `invoke_agent`, `TelosGatekeeper` (11 gates), `VerificationOracle`
3-of-5 quorum, `gaia_ledger` BLAKE2b chain, `AttractorPacket` projection, the GAIA
fitness scorer, the JK credibility gates.

**Must-build (the 5/100 part):**
1. **Welfare-ton engine** — `W = C×E×A×B×V×P` is doc-only; `gaia_platform.py`
   computes a proxy (`carbon × verification_bonus × community_bonus`). Code the full
   factorization with E-density caps, A-veto, B-weighting, P-risk.
2. **Tamper-evident receipts** — `EvidenceReceipt` is *immutable but not signed*.
   The GAIA ledger hash-chains; the spine receipt does not. Add BLAKE2b chaining +
   signature so the receipt itself is court-grade, not just the ledger.
3. **Cross-family decorrelation** — verification must use genuinely different model
   families (decorrelated errors), not one model in different roles. This is the
   Transcendence Principle's hard requirement and the competitive white space.
4. **External countersignature / One Wire** — a REST surface for external auditors
   to submit verdicts above quorum (N≥5, M≥3), so minting depends on the world, not
   on internal artifacts.
5. **Real external feeds** — production satellite (Sentinel-2/Planet) and IoT/soil
   pipelines replacing the pilot's mocks (this is the long pole; see raters/dMRV).

## 5. The minting invariant (non-negotiable)

> **A welfare-ton is minted ONLY from countersigned external verification above
> quorum. Internal artifacts never mint value.**

This is the existing One Wire / loop-closure doctrine (`loop-closure-2026-06`:
"only countersigned external acted receipts above quorum touch archive fitness")
applied to economic value. It is also the literal implementation of Shrikanth's
"issue only after outcomes are demonstrated against an unbiased counterfactual."
The trace can run end-to-end internally for *rehearsal*, but the mint at step [8]
is gated on an external countersignature — otherwise the welfare-ton is a number we
told ourselves, which is exactly the failure mode the whole market is dying of.
