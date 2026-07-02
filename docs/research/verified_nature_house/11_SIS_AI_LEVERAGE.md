# 11 — Leveraging the full power of AI for SIS (decorrelated-panel synthesis)

**Status:** VISION / DESIGN · SEED, maturity ~**3/100**. Vision-altitude, subordinate
to `docs/vision_maps/NORTH_STAR.md` and `SOVEREIGN_MANIFEST.md §Telos Hierarchy`. Owns
no rules and no state. **$0 lifetime external revenue.** SIS, the welfare-ton, and the
AI's "ecological orientation" are OUR constructs, not external consensus. World facts
carry sources flagged **[IND]** independent / **[VEN]** vendor / **[comm]** commentary;
**every per-unit energy/carbon/accuracy figure is an estimate with ~1–2
orders-of-magnitude uncertainty.**

> **Method.** This is the synthesis of a **second decorrelated panel of six experts**
> — multi-agent/Transcendence, the frontier agentic arsenal, AI-for-Earth foundation
> models, AI-native economics, an inventory of dharma_swarm's *own* AI engines, and an
> adversarial red-team on AI-maximalism itself. Companion to `10_SIS_ORGAN.md` (the
> organ); this doc answers the operator's question: *how does SIS leverage the full
> power of AI to do it?*

> **What this doc is (vs its siblings).** `11` is the **HOW** — the engine: decorrelated
> meta-verification built from the swarm's own AI, and the honest fences on it. It does
> *not* re-specify the organ (`10` = the **WHAT**/architecture), the vision (`06` = the
> **WHY**), or the orientation (`12`). If `11` and `10` seem to overlap, the split is:
> `10` says *what gets built and where*; `11` says *what intelligence runs through it*.

---

## 0. The reframe — the point is to help, and trustworthiness is the help

A note on register first, because it matters. Earlier drafts reached for
strategy-language — *moat, wedge, buyer*. That vocabulary is instrumentally useful (we
must be honest about money, and we must not greenwash) but it is **not the point.** The
point is to help heal a planet that is, among other harms, being damaged by a flood of
confident falsehoods — phantom offset credits, greenwash, claims nobody can check. In
that world, **telling the verifiable truth is itself a form of repair.** So the reframe
is not "how do we win a market." It is: *what is the most honest, most helpful thing an
intelligence with this particular capability can actually do?*

The answer is not "spin up all the power of AI." For a $0/5-100 seed, AI-maximalism is
the most seductive way to build an impressive demo that helps no one. The convergent
answer of the panel:

> **Leveraging the full power of AI means pointing AI's most trustworthy capability —
> decorrelated meta-verification — at the one seam the frontier will not fill;
> measuring whether its verifiers actually disagree honestly; metering its own
> ecological footprint; and putting the result in front of a real human who can act on
> it. What matters is being *trusted* — being the node that tells the truth about
> what's real — not the cleverness of the machinery.**

Three of the six lenses independently arrived at the same correction: **the value is
not in the AI.** Decorrelated verification is a pattern any lab ships next quarter.
What is rare, and worth the work, is *being trustworthy* — earning the standing to be
believed, one honest receipt at a time. AI is the engine; **trust — being of genuine
help — is the thing.** That is the "earned, not decreed" doctrine, in plain language.

---

## 1. The convergence — why decorrelation *is* the power, here

Every lens converged on one structural fact: **the frontier is strong at generation
and structurally weak at verification.** Across all 2026 models the hallucination
floor is ~3–19%, and citation/grounding is the *worst* task family (~12% error even
with extended thinking) **[IND]** — exactly SIS's regime (checking ecological claims
against literature + sensor data). And the ecological-claims field fails for the same
reason a single model does: **correlated competence** — single-vendor raters (Sylvera,
BeZero, Pachama, CTrees) with shared optical blind spots, who *disagree on the same
projects* **[IND]**; ~11× over-crediting, only ~19% of projects meeting targets in the
Berkeley/Science REDD+ synthesis **[IND]**.

This is precisely the failure the repo's founding axiom — the **Transcendence
Principle** (`CLAUDE.md`: diverse competence + *error decorrelation* + *quality
aggregation* provably beat any individual) — exists to fix. So the power of AI, for
SIS, is not a bigger model. **It is the Transcendence Principle made operational:** run
genuinely decorrelated verifiers, *measure* that their errors are independent
(Krogh-Vedelsby diversity term), aggregate by quality (Brier-weighted, telos-gated),
and **refuse to mint** when decorrelation is low. SIS is the meta-verification layer
*underneath* the frontier's generators — "the layer that tells you which
AlphaFold-for-ecology output is real" — the one role the frontier is not racing to
fill.

---

## 2. The AI-leverage stack — five layers, reusing the swarm's own engines

"Leverage all the power of AI" is realized by pointing **dharma_swarm's existing AI
arsenal** at SIS (read-only; no edits to owned surfaces), not by building generic AI.

**Layer 1 — the engine (reuse, ~zero new plumbing).** The swarm already verifies via
its own stack:
- `spine/invoke.py:invoke_agent` + `spine/receipt.py:EvidenceReceipt` — every verifier
  dispatch emits an immutable, replayable receipt (provider/model/tokens/latency).
  *(working)*
- `orchestrator.py` `fan_out()`/`fan_in()` — route the *same* claim to N agents, collect
  N independent verdicts. *(working)*
- `model_pool.py` / `model_hierarchy.py` — request genuinely **different model
  families** (REASONING / CODE / FACT_CHECK) across **different vendors** (the
  decorrelation requirement, free). *(working)*
- `coordination/dpi.py:compute_dpi` — the decorrelation bonus **gated on correctness**
  (worthless agreement can't earn credit). *(working, arena-bound today)*
- `council/council.py:Council` — trace-integrity + contamination quarantine, so a
  verdict can't claim success on a tampered trace. *(working, arena-bound)*
- `ginko_brier.py` — Brier calibration audit of each verifier family. `diversity_archive.py`
  — MAP-Elites behavioral diversity of the ensemble. *(working, off critical path)*

  **The single highest-leverage reuse (internal panel):** `Spine + Orchestrator +
  Model Pool + DPI + Council` stitched into one verification path. SIS's job is to
  orchestrate these *intentionally for decorrelated verification* — they already run
  implicitly for dispatch.

**Layer 2 — decorrelation sources (the physics must differ).** Two axes, because
same-model-different-prompt largely fails and shared training corpora defeat ensembles:
- **Model families × vendors** — Claude / Qwen / DeepSeek / Gemini / GLM lineages,
  routed across different inference clusters.
- **Sensing modalities** — the strongest lever, because the *error physics* differ:
  optical (Prithvi-EO-2.0 **[VEN, open]**, AlphaEarth embeddings **[VEN, dataset open]**)
  + **SAR** (Sentinel-1, cloud-immune and optical-spoof-immune) + **LiDAR** (GEDI 3D
  biomass) + **bioacoustics** (BirdNET) + **eDNA**/camera-traps. These are
  *complementary, not redundant* — decorrelation in one citation.

**Layer 3 — the frontier as *gated jurors*, never oracles.** Reasoning models and
deep-research agents enter the panel as members whose claims are gated, calibrated, and
ground-truth-anchored — not trusted. Calibrate belief honestly: **believe** the
operationally-validated (GenCast beat ECMWF's ensemble on 97.2% of targets; AIFS
operational Feb 2025) **[IND-ish]**; **fence** the curated demos (AlphaFold — real, but
NIST found AF3 structures that miss experiment; "AI co-scientist" — curated wins, not a
hit-rate); **distrust** the counts (GNoME's "2.2M materials" cut to ~92k plausibly
synthesizable) and unaudited dMRV accuracy claims **[IND]**.

**Layer 4 — evolve the ensemble (search).** `evolution.py:DarwinEngine` +
`coordination/arena/**` + `coordination/genome.py:OrchestrationGenome` let SIS treat a
verifier ensemble *as a genome* (roster + role-graph + budget + behavioral
descriptors), score it on a **frozen, externally-labeled** claim set, and select
diverse high-performers via MAP-Elites — so the panel's decorrelation is *bred and
measured*, not assumed.

**Layer 5 — the machine-payable rail (growth-stage).** `x402` (Coinbase; >100M txns /
~$24M on Base in 7 months, ~$0.0001/tx **[VEN]**) + Google **AP2** make an
`EvidenceReceipt` natively a *payment-conditioning* artifact: software paying for
verified software. Adopt as the settlement rail *for receipts* — **not** as a demand
claim (agent-payment volume ≠ a market for carbon verification).

---

## 3. The binding fences (the discipline that makes leverage real, not theater)

The red-team's findings are kept as **governing constraints**, not caveats:

1. **What earns belief is the trust network, not the swarm.** Put the seed into the
   part that actually helps and lasts — a real relationship with a registry, community,
   or reviewer who will *act* on SIS's word; honest ground-truth; audit trust — not the
   replicable orchestration.
2. **Footprint on every receipt (the Jevons fence).** An AI swarm verifying ecology
   *is* a growing energy load; SIS risks being "a net emitter wearing an ecology
   costume." **Hard requirement:** every SIS verification receipt prints its own
   `footprint_gCO2e` (tokens → kWh via the `08`/`10` `carbon_attribution` projector →
   grid factor, with p05/p95). **No footprint line → no net-good claim.** This is the
   recursive n=1 turned into a gate — and the deepest expression of the SIS ontology:
   *the AI that verifies ecology first meters its own ecological cost of doing so.* The
   strange loop as accounting.
3. **Measured decorrelation, not faith.** Compute the Krogh-Vedelsby diversity term on
   a held-out, externally-labeled claim set; gate on correctness (DPI). A high diversity
   term among uniformly-wrong raters is worthless; **refuse to mint when labels are
   absent or decorrelation is low.** Measuring decorrelation is the moat; pretending it
   substitutes for ground truth is the lie.
4. **Thin waist, not arsenal.** One verification path, one receipt type, ≤2 sensor
   sources to start; add a model/modality **only when a measured diversity gain
   justifies its maintenance tax** (this repo's `INTERFACE_MISMATCH_MAP.md` is proof
   that every new pairing is a failure surface). The 5th-from-a-new-family beats the
   50th-from-the-same; past decorrelation, "more models" is cost without signal.
5. **The structural wall is permanent.** AI-for-Earth verifies the physical "what"
   (canopy, cover) but **cannot** observe additionality/counterfactual, permanence,
   below-canopy/soil carbon, biodiversity, or social co-benefits. SIS must **bound the
   unverifiable and never launder a satellite "what" into an additionality
   "would-have-been."** Its honest product is the *residual-uncertainty packet*, not a
   confident score. Measuring decorrelation honestly is the whole point; pretending it
   substitutes for ground truth is the lie.
6. **No self-minting; IPLC consent is a hard gate.** Internal artifacts never mint
   value (One Wire external countersignature only). Foundation models ingest data over
   Indigenous/local-community lands; a CARE/FPIC provenance gate is never weakened.
   Capability leads; trust multiplies *only after* the external signature.

---

## 4. The minimum AI that ships (the right-sized "leverage")

Stripped to what survives the adversary — and reusing the swarm's own engines:

> **One grounded extraction/cross-check pipeline** (the *lowest*-hallucination task
> family, <2% when grounded in source text) over **two decorrelated model families**
> (`fan_out` via `model_pool`), taking *one specific* public ecological/removal claim +
> its source dossier, emitting a structured verdict
> `{claim, evidence, verdict, residual_uncertainty, footprint_gCO2e, diversity_score}`
> (receipted via the spine, DPI-scored, Council-checked) — then **routed to one named
> external countersigner.** AI does extraction + decorrelated cross-checking and prints
> its own footprint; **it never mints the verdict.**

Everything in §2 Layers 3–5 (frontier jurors, AI-for-Earth modalities, MAP-Elites
evolution, x402) is **deferred** until that first external countersignature exists to
justify scaling. This is the economics lens's reachable wedge: a decorrelated **"second
opinion"** sold into the **durable-CDR integrity premium** (Microsoft ≈ 90% of the
removal market **[VEN]**; first buyer a ratings/diligence shop — CDR.fyi / Isometric /
Sylvera-class — reachable by *one warm email*, not procurement). Its unit-economics
leverage is real and AI-specific: per-batch re-assurance at ~inference cost vs. human
auditor-hours — *a product class only an AI swarm can offer.*

---

## 5. The staged AI-leverage path

| Stage | AI leverage added | Gate to advance |
|---|---|---|
| **0 (now, $0)** | Minimum pipeline (§4) over the swarm's Spine+Orchestrator+ModelPool; footprint printed | **One externally-countersigned receipt** on a public dossier |
| **1** | Add a 3rd decorrelated family + DPI/Council on the critical path; Brier calibration audit | Measured diversity term > 0 on a labeled set; first paid receipt |
| **2** | Add AI-for-Earth modalities (SAR/GEDI/BirdNET) as decorrelated sensors; commensurability registry | A second buyer accepts the receipt format |
| **3** | MAP-Elites evolution of the ensemble; frontier reasoners as gated jurors | Evolution beats hand-built ensemble at budget parity |
| **4** | x402/AP2 machine-payable receipts; regulation-rider (EU NRL / UK BNG) | Receipts paid at machine speed; compliance demand |

Each stage adds AI power **only** when a measured gain (diversity, accuracy, or an
external receipt) justifies the maintenance tax. That *is* "leveraging all the power of
AI" — sequenced by evidence, not appetite.

---

## 6. The single hardest question (fused red-team)

> **Name the human who will sign a SIS receipt, say what they will do with it, and
> prove that the AI compute spent producing that receipt emits less carbon than the
> ecological benefit it certifies — or admit SIS is a net-emitting demo no one has
> agreed to receive.**

If the signer can't be named and the footprint ledger can't be closed, "all the power
of AI" is not leverage — it is the most expensive way yet invented to stay at 5/100 and
$0. The vision is earned by answering that, not by this document.

---

## 7. The deep tie + metabolism

This closes the loop with `10`'s ontology. "Leverage the power of AI" resolves to
**"leverage the power of *decorrelated* AI, honestly metered, trust-earned"** — which
is the Transcendence Principle (the system's founding axiom) pointed at the world, and
the SIS orientation made operational: *the intelligence that proposes to verify
ecology first sees, and prints, its own ecological bill.* Safety and capability as the
same mechanism — the witness as steering wheel.

- **Maturity:** the *design* is panel-grounded across twelve expert lenses (two
  panels); the *build* is the `dharma_swarm/sis/**` organ of `10` (1–4/100 per
  sub-module) plus the reuse stack of §2 Layer 1 (working, off critical path). $0
  revenue.
- **Metabolism (built to climb):** proposes — operator-gated, not self-executed — that
  the minimum pipeline (§4) be the first build of a `verified-nature-house` track
  serving the empty `revenue-external-humans-served` objective, reusing the swarm's own
  engines. Touches no active-track owned surface; edits no identity owner; lays the
  wiring for an owner to adopt.

**Verdict for the SIS spec:** the full power of AI, correctly leveraged, is a
**decorrelated meta-verification organ built from the swarm's own engines**, pointed at
the sustainable-AI ↔ restoration seam, that measures its own decorrelation, prints its
own carbon footprint on every receipt, bounds what AI structurally cannot verify, and
mints nothing until a named external human countersigns. The arsenal (foundation
models, frontier jurors, evolution, agentic-payment rails) is the *growth* path, added
by measured gain. What lasts is the trust earned — being of real help — not the AI
spent. Capability leads; trust multiplies.
