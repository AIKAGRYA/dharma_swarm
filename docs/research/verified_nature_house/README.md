# Verified Nature / Impact House — Seed Dossier

**Status:** SEED · maturity ~**5/100** (operator estimate, 2026-06-26). This is a
*direction seed*, not a shipped capability. Nothing here is a product, a revenue
claim, or a commitment. Lifetime external revenue remains **$0**.

**Role:** research / vision (subordinate to `docs/vision_maps/NORTH_STAR.md` and
`docs/governance/SOVEREIGN_MANIFEST.md`). This dossier owns no rules and no state.

**Branch:** `claude/monetization-strategy-team-rgn7g6` · **Authored:** 2026-06-26
via a 4-lane research fan-out (Shrikanth + book, nature-finance market, integrity
crisis + dMRV, repo organ/trace-spine inventory). External facts carry source
URLs in the body docs; vendor/self-reported figures are flagged.

---

## The one-paragraph thesis

In a world where AI makes content, claims, and analysis cheap and infinite, the
scarce asset becomes **verified truth** — provenance, decorrelated independent
verification, tamper-evident trails, value-gated. `dharma_swarm` is unusually
built to manufacture exactly that (spine receipts, telos gates, trace attractor,
multi-agent decorrelation, the welfare-ton). So the move is **not to sell the
governance/substrate** (no buyers for that). It is to make the substrate the
**nervous system of a corporation that sells verified beneficial outcomes** —
"a Palantir for doing good works" (NORTH_STAR §5). The first vertical is nature,
because that is where the repo already has organs, the telos already points, and
a real market is *starving specifically for the trust the substrate produces*.

## Why nature, and why now (the honest version)

The research delivered one correction that reshapes everything: **do not sell
biodiversity credits.** That market is a mirage — under ~$2M cumulative global
sales as of Sept 2024, ~20 sub-$50k transactions, supply massively exceeding
demand, with Nestlé and Unilever explicitly declining (BCG calls it "corporate
conservation philanthropy"; see `00_CORPORATION_SPEC.md` §buyer-reality).

Where money *actually* flows, and where the substrate is a moat not a tax:
1. **The integrity premium.** ICVCM CCP-labelled credits carry a ~25% premium
   and are supply-constrained; removals priced ~381% over avoidance in 2024.
   Buyers now pay *more per credit for trust*.
2. **Disclosure / measurement / assurance.** TNFD 700+ adopters; ISSB absorbing
   nature reporting (Nov 2025); Big Four nature practices billing real fees.
3. **The un-satellite-able layer.** Digital MRV verifies the physical "what"
   (forest cover, canopy) at >95% accuracy but **structurally cannot** verify
   additionality/counterfactual, permanence, soil/below-canopy carbon,
   biodiversity, or social co-benefits — and the rating agencies (Sylvera,
   BeZero, Calyx) **openly disagree** precisely on those soft judgments. Those
   are exactly the welfare-ton's E, A, B, P factors. The welfare-ton does not
   compete with LiDAR; it scores what LiDAR can't see and raters fight over.

## The keystone: this operationalizes Shrikanth's own published demand

Siddarth Shrikanth (Investment Director, Natural Climate Solutions, **Just
Climate** / Generation Investment Management — *not* General Atlantic, a
correction surfaced in research) wrote *The Case for Nature* (Duckworth, 2023;
Al Gore–endorsed). His peer-reviewed 2026 paper *"Five rules for
scientifically-credible nature markets"* (Nature Ecology & Evolution) finds that
**every major nature market fails on additionality, leakage, and permanence**,
and argues credits should be issued **only after outcomes are demonstrated
against an unbiased counterfactual.** That is the verification thesis, stated by
the anchor person himself. We are not adding to his argument — we are building
the credibility substrate he says is missing. See `01_SHRIKANTH_ALIGNMENT.md`
(including the strict boundary on what is *his* vs *ours*).

## What's actually in the repo (calibrating the 5/100)

| Organ | Maturity | Evidence |
|---|---|---|
| Welfare-ton formula `W = C×E×A×B×V×P` | **doc-only (~20% coded)** | `docs/telos-engine/08_SATTVA_ECONOMICS.md`; proxy in `gaia_platform.py` |
| GAIA Bayou Lafourche pilot (420 ha) | **working, one proof** | `reports/gaia_eco_pilot_20260327/...` — real `ledger.jsonl`, BLAKE2b chain, 4-of-5 oracle quorum, 304→258.4 tCO2e verified |
| MRV core (verification/ledger/fitness) | **scaffold** | `gaia_ledger.py`, `gaia_verification.py`, `gaia_fitness.py` |
| Trace/verification spine | **working, reusable** | `spine/receipt.py` (EvidenceReceipt), `telos_gates.py` (11 gates), `trace_attractor/models.py`, `spine/invoke.py` |

So "5/100" is fair for the *business/credibility-product*, but the *verification
spine is real*. The 5/100 part is the welfare-ton math and the external feeds.
Full breakdown: `03_MATURITY_AND_ROADMAP.md`.

## The documents

- **`00_CORPORATION_SPEC.md`** — the emerging corporation at both altitudes
  (narrow Verified Nature House + broad Palantir-shaped Verified-Intelligence
  House), buyer reality, and the single first verifiable receipt to chase.
- **`01_SHRIKANTH_ALIGNMENT.md`** — supporting *The Case for Nature*: his core
  messages mapped to capabilities, the five-rules bridge, honest boundaries, and
  a modest credible collaboration shape.
- **`02_TRACE_ARCHITECTURE.md`** — how a welfare-ton claim is traced and verified
  through the spine, citing real symbols; reusable-as-is vs must-build; the
  minting invariant.
- **`03_MATURITY_AND_ROADMAP.md`** — 0–100 component scoring and the staged path
  to a first verifiable external receipt, then a first paying buyer.
- **`04_LANDSCAPE_MAP.md`** — the field mapped: ~90 actors across 8 clusters
  (authors, standards, integrity, MRV/nature-tech, finance, NGOs, AI-for-nature,
  market operators), each with its blind spot. From a 7-lane parallel research scan.
- **`05_INVARIANTS_AND_BRIDGE.md`** — **the centerpiece.** The twelve cross-cluster
  invariants, the one diagnosis under all of them (the field is a textbook failure
  of the three Transcendence conditions — diverse competence, but no error
  decorrelation and no quality aggregation), and the bridge: decorrelated
  aggregation + a provenance/commensurability ledger + the welfare unit, with an
  honest fence around what we are *not*.

---

## Proposed active track (NOT yet opened — WIP is at 10/10)

The portfolio is at `max_active: 10` (CI errors above it). This direction would
fill the **`revenue-external-humans-served`** spine objective, which currently
has **no active track** (a standing declared gap). To open it, the operator
moves the block below into `active_tracks:` in
`docs/governance/ACTIVE_TRACK.yaml` **and** closes one SHIPPABLE substrate track
to stay within WIP (candidates: `provider-routing-consolidation-2026-06` or
`truth-graph-platform-2026-06`, both rigor-backed SHIPPABLE). This dossier does
**not** edit the portfolio, by governance.

```yaml
  - id: verified-nature-house-2026-06
    name: Verified Nature House — credibility substrate for nature claims (seed)
    status: ACTIVE
    opened_at: "2026-06-26"
    verified_at: "2026-06-26"
    ttl_days: 21
    owner: "@AmitabhainArunachala"
    serves: revenue-external-humans-served   # first track to serve this objective
    complements:
      - orchestration-arena-v1-2026-06        # decorrelation/DPI is the verification engine
      - loop-closure-2026-06                  # One Wire external-receipt quorum
    owned_surfaces:
      - docs/research/verified_nature_house/**
      - dharma_swarm/gaia_*.py
      - dharma_swarm/jk_*.py
      - reports/gaia_eco_pilot_*/**
    moves_vital_signs:
      - eval_coverage
      - quality_gates
    description: |
      SEED (5/100). Make natural-capital claims verifiable — operationalizing
      Shrikanth's published "five rules for scientifically-credible nature
      markets" (additionality, leakage, permanence, outcomes-after-counterfactual,
      credible biodiversity proxy) as a computable, receipted, decorrelated-
      verified welfare-ton scorecard over the existing spine. NOT selling
      biodiversity credits (dead market); the wedge is the integrity/co-benefit
      layer that dMRV and raters cannot do. Creates NO new truth store; projects
      over spine.EvidenceReceipt + the GAIA ledger.
    non_goals:
      - Do not claim revenue, buyers, or a shipped product; this is a seed.
      - Do not sell or originate biodiversity credits in this track.
      - Do not let internal artifacts mint a welfare-ton; only countersigned
        external verification above quorum mints value (One Wire invariant).
      - Do not create a new receipt store; project over spine.EvidenceReceipt.
      - Do not overclaim Shrikanth's endorsement of the welfare-ton or "zero-kill".
    next_items:
      - id: 1
        what: "Code the W = C×E×A×B×V×P engine (currently a proxy in gaia_platform.py)."
        kind: code
        blocker: true
      - id: 2
        what: "Add BLAKE2b hash-chain + signature to EvidenceReceipt for tamper-evidence (gaia_ledger already chains; spine receipt does not)."
        kind: code
        blocker: true
      - id: 3
        what: "Re-run the Bayou pilot as a five-rules-scored, externally-countersigned welfare-ton verification = first verifiable external receipt."
        kind: runtime
        blocker: true
```
