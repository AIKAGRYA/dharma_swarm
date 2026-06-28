# SIS Material Ledger — the debit side of the Circle (per-inference → welfare-ton)

**Status:** SEED (5/100). This is the **debit half** of the torus
(`06_THE_CIRCLE.md`) — the half that connects directly to AI energy and to Jensen
Huang's claim that energy infrastructure is the binding constraint on AI. It is a
*projection spec*, not a metering product. $0 revenue. SIS = "Silicon Is Sand"
(`SOVEREIGN_MANIFEST.md §Telos Hierarchy`): the full material cost of compute.

The credit side (GAIA restoration → welfare-tons) is specified in `02`/`03` and
`docs/telos-engine/08_SATTVA_ECONOMICS.md`. The debit side — what compute *costs*
the earth, metered and receipted — is the underbuilt half. This specs it.

---

## 1. The thesis

Intelligence has a material price. Every inference burns energy → at some grid
carbon intensity → emits gCO₂; the broader SIS footprint adds water, chips,
minerals, fabs, land, and e-waste. Today that debit is **invisible at the unit of
work** — labs buy bulk RECs and make press-release "carbon neutral" claims with no
per-dispatch provenance and no link to *verified* restoration. The membrane's job
on this side is to **meter the debit per dispatch, receipt it, and reconcile it
against verified welfare-ton credits** — turning "trust us, we offset" into a
tamper-evident, decorrelated-verified statement.

## 2. The wiring elegance — it's a projection, not a new store

`dharma_swarm/spine/receipt.py::EvidenceReceipt` **already** carries everything the
debit needs: `provider`, `model`, `input_tokens`, `output_tokens`, `cost_usd`, and
a free-form `attributes: dict`. Every production dispatch through `invoke_agent`
emits exactly one receipt. Therefore:

> **The SIS debit ledger is a read-model projection over `EvidenceReceipt`.**
> It creates no new truth store, no daemon, no second receipt — honoring the
> reconciliation-lane doctrine ("read models project truth from owners; they do not
> become authority"). A SIS projector reads receipts, attaches an energy/carbon
> estimate to `attributes`, and aggregates. That's it.

This is the same architectural move as the rest of the Verified Nature House:
project over the spine, never mint a parallel owner.

## 3. The metering chain (seed numbers are real, sourced, and flagged)

```
  receipt(model, in_tokens, out_tokens)
        │   model→energy table (Wh/inference or Wh/1k tok)
        ▼
   energy_Wh ──×PUE──×grid_gCO2/kWh──▶ gCO2 per dispatch
        │                                    │
        └──────── aggregate over session/day/org ───────▶ gross tCO2 SIS debit
```

Seed constants (from `docs/telos-engine/08_SATTVA_ECONOMICS.md`, which cites a
per-inference *Carbon Attribution Feasibility Study* that currently lives at
`/Users/dhyana/jagat_kalyan/CARBON_ATTRIBUTION_FEASIBILITY.md` — **a seed on the
operator's Mac, not yet metabolized to this repo; that file must reach main, or be
labeled seed-status, per the canon-metabolism rule**):

- Per-inference energy: **Claude 3 Haiku ≈ 0.22 Wh → Opus ≈ 4.05 Wh** (model-tiered).
- A typical Sonnet query ≈ **0.19 gCO₂** (0.95 Wh × 1.15 PUE × 175 gCO₂/kWh ÷ 1000).
- At **$17.80/welfare-ton** that is ≈ **$0.0000034/query**; at **1B queries/day ≈
  $1.24M/yr** — negligible per call, meaningful as a restoration revenue stream.
- **Uncertainty band (binding on every point estimate above):** independent
  studies find per-query energy contested by **~10×** (≈0.3 vs ≈2.9 Wh for a single
  query) and spread **~65×** across deployed models. The point numbers above are
  *central anchors only* — every one must ship inside an explicit p05/p95 band
  (which `dharma_swarm/gaia_sis_projection.py` enforces in code), never as a settled
  figure. The Haiku/Opus/Sonnet constants trace to the un-metabolized Mac file
  (below), so they stay hard-labeled SEED until that source reaches main.
- Sector scale: AI inference ≈ **15 TWh / ~6 MtCO₂ (2025)** → **~347 TWh / ~121
  MtCO₂ (2030, projected)**.

These are **estimates with declared uncertainty (±~40–50%)**, because provider
energy telemetry is private and grid intensity varies by datacenter and time. The
ledger must label every debit *rebuttable* (the OpenET posture: decision-useful,
explicitly not legal-grade) — never a hidden precise number. Standards seam:
EcoLogits, ISO/IEC 21031 (Software Carbon Intensity), GSF SCI-for-AI.

## 4. Reconciliation — debit meets credit at the throat

```
   SIS debit (gross tCO2, this org/period)   ◀── projection over EvidenceReceipts
            ─ minus ─
   GAIA credit (welfare-tons of VERIFIED restoration, minted above external quorum)
            ─ equals ─
   net SIS position  (carbon-negative when credit > debit, e.g. the Bayou pilot's
                      verified −254.2 tCO2e net)
```

Two units, deliberately not fungible: the **debit is gross carbon** (what was
emitted); the **credit is welfare-tons** (verified restoration with social/
biodiversity/permanence co-benefits, `W = C×E×A×B×V×P`). The membrane reconciles
them with a declared conversion and a receipt — it does **not** pretend a gross ton
emitted equals a welfare-ton restored. The premium between them *is* the integrity
signal (a welfare-ton is worth more than a REC precisely because it carries V and
the co-benefits the field can't verify — see `05`).

## 5. The fundable surface — "verifiable compute offsets"

This is the half a buyer actually pays for, and the demand is already on the record:
Microsoft contracted 45M tonnes of removal; Anthropic pledged to cover datacenter
electricity-price increases (`08_SATTVA_ECONOMICS.md`). What none of them can buy
today is a **per-workload, receipted, decorrelated-verified** offset tied to a
*specific verified restoration outcome* rather than a bulk certificate. That is the
product: an AI lab gets a tamper-evident statement — "this inference workload's
estimated SIS debit was offset by N welfare-tons of restoration verified by an
independent decorrelated quorum, receipt `sha…`" — i.e. a credible **"beyond carbon
neutral"** claim that survives the scrutiny the bulk-REC market is dying under.

The ready-made first engagement (already drafted in `08_SATTVA_ECONOMICS.md §4.1`):
**tag 10,000 real API calls with per-inference carbon, offset via welfare-ton
credits from one pilot restoration, measure the welfare-ton output** → a publishable
case study and the first external acted receipt.

## 6. The Jensen connection, made exact

Energy is the binding constraint on AI scaling. The constraint is not just *amount*
— it is increasingly *license*: grid pressure, local opposition, and emissions
scrutiny gate where datacenters can be built. A lab that can show its compute-debit
is **verifiably** offset into real ecological + social restoration (not greenwash)
has a stronger social license to draw power. The membrane converts AI's energy
problem from a pure cost into a **circulating credit**: the energy that powers the
model funds the restoration that offsets it, *with a receipt*. That is the torus
closing on the debit side — and it is the part of the Circle a CFO signs.

## 7. Architecture (where it plugs — no owned-surface collisions)

- **Source (unchanged):** `invoke_agent` → `EvidenceReceipt` (already emits
  provider/model/tokens/cost). Owned by spine-adoption; **we do not modify it.**
- **New (this seed):** a SIS projector module (proposed `dharma_swarm/sis/` or under
  the GAIA organs) that (a) reads receipts, (b) joins a `model→energy` table, (c)
  applies PUE + grid intensity, (d) writes a per-dispatch `sis_debit_gco2` into the
  receipt's `attributes` projection (not the receipt itself), (e) aggregates to a
  SIS debit ledger, (f) reconciles against `gaia_ledger` welfare-ton credits.
- **Owner discipline:** projection only; no new receipt type; no edits to
  spine/**, providers.py, orchestrator.py, agent_runner.py (owned by active
  tracks). The `model→energy` table is the one genuinely new artifact, seeded from
  public estimates and labeled as such.

## 8. The honest fence (5/100)

- The energy table is seeded from **public estimates, not provider telemetry** —
  ±~40–50%, rebuttable, never legal-grade. Say so on every number.
- The welfare-ton engine is still a **proxy** (`03`); the conversion debit→credit is
  declared, not certified.
- SIS v1 meters **energy→carbon only** — the tractable, dominant, fundable slice.
  Water, chips, minerals, fabs, land, and **e-waste** are the declared SIS frontier,
  *not faked*. Naming them and not measuring them is the honest posture; pretending
  to meter them would be the lie.
- This is a **projection spec**, not a shipped meter. No revenue.

## 9. The one move (n=1, and it's recursive)

The cleanest first proof of the debit side is for **the swarm to meter its own
compute**: run a SIS projector over this very session's `EvidenceReceipt`s, price
the dispatches in welfare-tons, route the debit to one verified restoration outcome,
and receipt it. The system that prices compute prices *its own* compute — the strange
loop showing up as accounting, not metaphysics. That n=1 (the swarm's own inference
debit, offset by one verified welfare-ton, externally countersigned) is the debit
half of the torus proven once. Everything above is the reason it's worth metering.
