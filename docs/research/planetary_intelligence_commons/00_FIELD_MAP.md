# PIC 00 — Field Map: the external world PIC binds (receipts, not memory)

**Series:** Planetary Intelligence Commons (PIC) research — `00_FIELD_MAP.md` (this
file, the external field) · `01_CAUSAL_ACTION_RECEIPT.md` (the CAR IR spec) ·
`02_WEDGE_AND_ROADMAP.md` (arcs, partners, objections). The *why* lives in
`docs/vision_maps/2026-07-11_planetary_intelligence_commons.md`.
**Status:** SEED (5/100). Distillation of external receipts, **not** a build. $0
revenue, no track claimed (portfolio at WIP 10/10, `docs/governance/ACTIVE_TRACK.yaml`).
**Authority:** subordinate to `docs/vision_maps/NORTH_STAR.md` and
`docs/governance/SOVEREIGN_MANIFEST.md §Telos Hierarchy`. Owns no rules, no state.
**Source discipline (citation-or-silence):** every row carries a live URL or a
`file:line` into the three research reports this distills —
`research/agentic_stack.md`, `research/nature_finance_mrv.md`,
`research/footprint_and_visions.md`. Those reports carry their own source-confidence
notes (`agentic_stack.md:185-189`; `footprint_and_visions.md:164`); items they flag
`n.a.` / source-pending stay flagged here. **Nothing below is agent-invented.**
**Anti-pattern guard:** this map exists to locate the one unoccupied position, not to
catalogue the field for its own sake. If it ever reads as a literature review no
external human transacts through, it has failed.

---

## Why a field map at all

The PIC vision braid makes one falsifiable claim: **five constitutional questions**
about any agent action — authority, material burden, telos, evidence, challenge/
reversal — are each only *partially* answered, and only *within a silo*, by the stack
already being built. This file is the evidence for that claim. If a reader can point to
one existing protocol that binds all five into one portable record with a community-held
challenge right, the vision is refuted and should be composted. No such protocol appears
below.

Two fields matter, because PIC sits at their seam:

1. **The agentic internet** — how agents talk, pay, and prove identity
   (`research/agentic_stack.md`). This answers *mechanism*.
2. **Nature-finance / MRV + the compute-footprint politics** — how ecological outcomes
   are measured, financed, and contested (`research/nature_finance_mrv.md`,
   `research/footprint_and_visions.md`). This is the first world-scale *domain* the
   receipt would serve.

---

## 1. The agentic stack — nine protocol families (2026)

The stack is **strong on communication, payment, and identity/discovery; maturing on
delegation; fragmented on evidence; weak on a portable challenge/reversal primitive**
(`research/agentic_stack.md:172-174`). Summary of the families the field map fetched
as primary specs (`agentic_stack.md:186`):

| Layer | Protocol / standard | What it does | Receipt |
|---|---|---|---|
| Communication | **MCP** (Model Context Protocol) | tool/resource access; RFC 8707 resource-scoped auth | [modelcontextprotocol.io](https://modelcontextprotocol.io) |
| Communication | **A2A** (Agent-to-Agent) | agent messaging; AgentCard skill/purpose declaration | [a2a-protocol.org](https://a2a-protocol.org/latest/specification/) |
| Payment | **AP2** (Agents-to-Payments) | Intent / Cart / Payment Mandates — user intent-to-pay | [ap2-protocol.org](https://ap2-protocol.org/) |
| Payment | **x402** | HTTP-native stablecoin settlement; **final by design** | [x402.org](https://www.x402.org/) |
| Payment | **Visa TAP / Mastercard Agent Pay** | tokenized agent spend + programmatic limits | [Mastercard](https://www.mastercard.com/us/en/news-and-trends/press/2026/june/mastercard-launches-agent-pay-for-machines.html) |
| Identity / discovery | **ERC-8004** | on-chain Identity + Reputation + Validation registries | [ERC-8004](https://eips.ethereum.org/EIPS/eip-8004) |
| Identity | **W3C DIDs / VCs** | decentralized identifiers + verifiable credentials | [W3C DID v1.0](https://www.w3.org/TR/did-core/) |
| Delegation | **Authenticated Delegation** (South et al.) | OIDC-anchored delegation tokens binding agent→principal | [arXiv 2501.09674](https://arxiv.org/abs/2501.09674) |
| Delegation | **OAuth token-exchange `act` chains** / agent-auth drafts | scoped, revocable delegated access; CAEP revocation | [Zylos](https://zylos.ai/research/2026-04-11-agent-authentication-delegated-access-oauth-scoped-tokens/) |
| Evidence | **C2PA 2.4** | content provenance manifests | [C2PA 2.4](https://spec.c2pa.org/specifications/specifications/2.4/specs/C2PA_Specification.html) |
| Evidence | **TEE attestation** | proves a model ran on an input | [Eco TEEs](https://eco.com/support/en/articles/14796365-tees-for-ai-agents-verifiable-compute) |
| Evidence | **Sigstore / Rekor** | tamper-evident transparency log of signatures | [Sigstore](https://docs.sigstore.dev/about/security/) |
| Telemetry | **OTel GenAI** | GenAI spans — experimental, debugging-grade | [OTel GenAI](https://github.com/open-telemetry/semantic-conventions/blob/main/docs/gen-ai/README.md) |
| Governance (draft) | **IETF ATTP / AIP / AGTP-TRUST** | graduated trust, action limits, kill switches | [datatracker](https://datatracker.ietf.org/doc/draft-sharif-attp/) |

The behavioral-trust gap in the IETF drafts (identity/limits plumbing, no *behavioral*
trust) is already this repo's named position in `NORTH_STAR.md:205-214` — PIC does not
re-litigate it; it composes on top.

## Gap analysis — the five questions, each partial and siloed

This is the load-bearing table. Rows are the five constitutional questions; the full
per-protocol detail is `research/agentic_stack.md:162-168`.

| Question | Partially addressed by | The gap (what's missing) |
|---|---|---|
| **(1) Authority** — under whose authority? | AP2 Mandates; Authenticated Delegation tokens ([arXiv 2501.09674](https://arxiv.org/abs/2501.09674)); OAuth `act` chains; ERC-8004 principal binding | **No neutral, cross-protocol delegation object** portable across MCP/A2A/payments. Authority is payment-scoped, resource-scoped, or on-chain — never one portable thing (`agentic_stack.md:164`). |
| **(2) Material burden** | AP2 budget caps; Visa/MC spend controls; EU PLD documentation duties | **Burden is expressed only for payments.** No machine-readable manifest for non-financial burden — energy, water, minerals, downstream obligation (`agentic_stack.md:165`). |
| **(3) Telos** | AP2 Intent Mandate; A2A AgentSkill; CSA purpose declaration; Chan et al. visibility ([arXiv 2401.13138](https://arxiv.org/abs/2401.13138)) | **Telos is self-asserted and unchecked** — declared descriptively, never bound to a specific action or checked against the outcome (`agentic_stack.md:166`). |
| **(4) Evidence** | AP2 mandate chain; ERC-8004 Validation (zkML/TEE); C2PA; TEE; Rekor; OTel | **No unified action-evidence receipt.** Each proves a fragment; ERC-8004 validation is **spec'd, not implemented at protocol level** ([Decipher Club](https://www.decipherclub.com/so-what-exactly-are-trustless-agents-up-to/)); OTel is debugging-grade (`agentic_stack.md:167`). |
| **(5) Challenge / reversal** | ERC-8004 feedback revocation; AP2 dispute trail; CAEP; card chargebacks; EU operator recourse | **Reversal is off-protocol and asymmetric.** CAEP revokes *future* access, not past actions; x402/on-chain is **final by design**; no portable "who can contest, on what grounds, to what effect" primitive (`agentic_stack.md:168`). |

**The stack's own synthesis independently prescribes PIC's keystone rule.** The three
whitespaces it names (`agentic_stack.md:176-179`) are exactly (1) a cross-protocol
authority object, (2) a signed accountability receipt unifying authority+telos+burden+
evidence, (3) a standard challenge/reversal primitive — and the closing instruction is
verbatim the anti-double-write law at planetary scale:

> **"Interoperate, don't duplicate:** anchor authority on OAuth/OIDC + DIDs; reuse AP2
> mandate structure for the burden/intent fields; register/discover via ERC-8004 or
> AGNTCY; carry evidence via C2PA/TEE-attestation/Rekor; emit telemetry via OTel GenAI;
> and add the genuinely missing cross-protocol **receipt + challenge/reversal**
> semantics on top." (`agentic_stack.md:181`)

That is the same rule this repo already binds internally as an ADR
(`docs/research/RECEIPT_AND_VEL_EQUIVALENCE_MATRIX.md:145-151`). Two scales, one law —
the doctrine symmetry that is Move 1 of the vision braid.

---

## 2. Nature-finance / MRV — where the capital→outcome pipe breaks

The first world-scale domain for the receipt. The demand is treaty-level: CBD Global
Biodiversity Framework **Target 19 mobilizes $200B/yr** by 2030 with IPLC benefit-sharing
floors ([CBD Target 19](https://www.cbd.int/gbf/targets/19)); the **Cali Fund** operationalizes
DSI benefit-sharing ([CBD Cali Fund](https://www.cbd.int/article/2026-CaliFund)). MRV cost
is collapsing — WRI's TerraMatch uses DINOv3 to cut monitoring cost dramatically
([WRI](https://www.wri.org/monitoring-locally-led-land-restoration-scale)). Yet the
capital→outcome pipe breaks at **every** node of what turns out to be the same nine-node
graph as the CAR (`nature_finance_mrv.md:161-178`):

| Graph node | Where it breaks | Evidence |
|---|---|---|
| **Identity** | no cross-registry identity; a site has a different ID in every system | [WRI](https://www.wri.org/monitoring-locally-led-land-restoration-scale); [Regen](https://www.regen.network/) |
| **Intention / baseline** | gameable, non-comparable baselines (the REDD+ failure mode) | [Energy Monitor](https://www.energymonitor.ai/carbon-markets/carbon-offsets-guardian-investigation-compares-apples-and-oranges-verra-ceo/) |
| **Material debit / capital** | commitments not linked to outcomes at transaction level; Cali Fund ~1 contribution | [ESG Today](https://www.esgtoday.com/just-climate-raises-375-million-for-natural-climate-solutions-strategy/) |
| **Community authority (FPIC)** | FPIC is a document/attestation, **not** a verifiable, revocable, challengeable record; no local-veto primitive | [AFi FPIC](https://accountability-framework.org/fileadmin/uploads/afi/Documents/Operational_Guidance/OG_FPIC-2020-5.pdf) |
| **Evidence (MRV)** | rich but siloed (eDNA/biomass/habitat/imagery); no common schema, no fungible metric | [Chloris](https://www.chloris.earth/carbonmarkets); [Space Intelligence](https://www.space-intelligence.com/) |
| **Capital ↔ outcome binding** | Isometric (tonne-level certs) + WRI outcome-payment are the frontier, still registry-specific | [Climate Decode/Isometric](https://climate-decode.com/insights/vcm-series/vcm-2026-era-of-integrity/isometric-science-first-removals-registry) |
| **Witnessed outcome** | verification is third-party-trusted, slow, proprietary scores — not a shared open record | [Sylvera](https://www.sylvera.com/evaluate) |
| **Challenge / reversal** | handled as pooled buffer insurance, not per-receipt challengeable events; forecast reversal-risk unlinked to sites | [Carbon to Sea/Isometric](https://www.carbontosea.org/2025/11/25/an-independent-mrv-review-of-the-first-oae-credits/); [Verra DMRV](https://verra.org/verra-approves-first-credits-under-dmrv-pilot-for-high-frequency-issuances/) |
| **Learning** | per-program, not a shared graph; failures don't propagate cross-system | [WRI](https://www.wri.org/monitoring-locally-led-land-restoration-scale) |
| **Interop / portability** | no shared receipt schema; blockchain rails (Regen/OFP) are isolated islands | [OFP](https://commons.opencivics.co/Open-Forest-Protocol-OFP-2b006d2570f280e7abe5eaa4e5ae3875) |

> **The single biggest break** (`nature_finance_mrv.md:178`): "there is **no portable,
> per-transaction record binding identity + community authority + capital + evidence +
> reversal** that travels across registries, funds, and MRV providers." That sentence
> describes the CAR's job in the nature domain, node-for-node.

**The FPIC opening is the sharpest.** FPIC is required in principle everywhere (ICVCM,
BCA, Cali Fund) but implemented as a static document, never as a **verifiable, portable,
revocable record with a local-veto primitive** (`nature_finance_mrv.md:129`). PIC's
community-authority node + challenge/reversal node are one design answer to a gap the
field states in its own words.

## Partner / competitor map (compressed; full table `nature_finance_mrv.md:184-201`)

- **Partners (demand + legitimacy):** CBD / Cali Fund / GBFF (treaty demand, $200B);
  Biodiversity Credit Alliance / IAPB (already calling for a "digitally native
  biodiversity credit market" with "digital trust infrastructure" + FPIC baked in,
  [BCA](https://www.biodiversitycreditalliance.org/)); ICVCM / VCMI (standards);
  Article 6.4 PACM / UNFCCC (compliance rail with reversal standards).
- **Partners (capital):** Just Climate (Generation IM) — explicitly funds outcome-
  verification tech ([ESG Today](https://www.esgtoday.com/just-climate-raises-375-million-for-natural-climate-solutions-strategy/)).
- **Partners (evidence suppliers):** NatureMetrics (eDNA), Chloris (biomass), Space
  Intelligence (habitat), Planet/NICFI (imagery), WRI TerraMatch (field↔satellite).
- **Coopetition (nearest philosophical competitors — build-on rails or rivals):**
  Regen Network (community-verified ecocredits + DAO — the closest existing
  receipt/graph), Open Forest Protocol, Isometric (most receipt-like registry primitive).
- **Incumbents to disintermediate on transparency:** Sylvera / BeZero (proprietary
  scores vs. open receipts), Verra / Gold Standard (closed registries).
- **Untapped reversal-risk feed:** NVIDIA Earth-2 (below).

**Positioning takeaway** (`nature_finance_mrv.md:203`): **build connective tissue, not
another registry.** The wedge is the portable receipt binding FPIC-as-revocable-record +
capital + evidence + reversal across existing rails.

---

## 3. Compute footprint & the politics of the debit

The debit side of the torus faces a live political window and a live measurement fight.

- **Scale:** global data-center electricity ~415 TWh in 2024 (~1.5% of world), projected
  ~945 TWh by 2030 ([IEA *Energy and AI*](https://www.iea.org/reports/energy-and-ai/executive-summary),
  `footprint_and_visions.md:15`).
- **Demand for a reciprocity instrument is peaking:** ~75 data-center projects (~$130bn)
  blocked or delayed in Q1 2026 amid local opposition; siting is now an electoral issue
  ([TNW](https://thenextweb.com/news/data-center-opposition-75-projects-blocked-q1-2026);
  [Guardian](https://www.theguardian.com/us-news/2026/jul/03/datacenter-recall-elections),
  `footprint_and_visions.md:18`).
- **The debit is contested at the base layer** — the hardest technical dependency PIC
  does not control: per-query energy varies **4–20×** between vendor claims and
  independent studies; Scope 2 accounting is mid-revision; water/embodied footprints
  barely standardized ([Google Gemini study](https://www.datacenterdynamics.com/en/news/google-median-gemini-prompt-uses-024-watt-hours-of-power-and-consumes-026ml-of-water/);
  [GHG Protocol S2](https://ghgprotocol.org/sites/default/files/2025-08/S2-Meeting17-Presentation-20250728.pdf),
  `footprint_and_visions.md:160`). This is why SIS ships every number inside an explicit
  p05/p95 band and labels it rebuttable (`07_SIS_MATERIAL_LEDGER.md:64-77`).
- **Standards are mid-flight — set the bar, don't inherit it:** SCI-for-AI, GHG Protocol
  Scope 2 revision, EU AI Act energy disclosure, all openly criticized as too weak
  ([GSF SCI-AI](https://greensoftware.foundation/standards/sci-ai/),
  `footprint_and_visions.md:146`).
- **Verification is now a neutral primitive to compose:** ClimateTRACE's asset-level AI
  emissions data (>744M assets, monthly) is exactly the outcome-verification oracle a
  reciprocity layer needs ([ClimateTRACE](https://climatetrace.org/news/climate-trace-data-show-global-greenhouse-gas-emissions-hit-a-new-record-high-in-2025),
  `footprint_and_visions.md:112`).

### The "legitimacy + teeth" quadrant nobody holds

The governance terrain maps to a quadrant with an empty corner
(`footprint_and_visions.md:144`):

| | No teeth (non-binding) | Teeth (binding) |
|---|---|---|
| **Legitimate** (deliberative) | Anthropic CCAI + vTaiwan — deliberation that doesn't bind; vTaiwan "stalled" precisely because consultation wasn't binding ([Designing Open Democracy](https://www.designingopendemocracy.com/blog/2026/05/25/taiwans-digital-democracy-experiment-what-it-shows-what-it-doesnt/), `:128`) | **← PIC's bid** |
| **Not legitimate** (no process) | ReFi — neither at scale ([Coinbase REGEN](https://www.coinbase.com/price/regen-network), `:92-101`) | per-MW fee bills (UW-Milwaukee, Illinois POWER Act, Virginia) — coercive, no deliberative process (`:48-52`) |

PIC's bid for the empty corner: SAB-grade witnessed deliberation (legitimacy) binding
SIS debits + GAIA outcome-gated release (teeth). The instrument sits deliberately
**between coercion and charity** (`footprint_and_visions.md:158`) — voluntary but
verifiable.

## Adjacent visions — positioning (not competitors to copy)

- **Bratton / Antikythera "planetary computation"** — the legitimizing narrative
  (compute as planetary sense-organ) but deliberately **descriptive, not operational**;
  it names the megastructure without a reciprocity mechanism. PIC positions as the
  **normative/constitutional complement**: "if planetary computation is real, it must be
  accountable to the planet it runs on" ([Noema](https://www.noemamag.com/a-new-philosophy-of-planetary-computation/),
  `footprint_and_visions.md:86`).
- **Digital Gaia ("Gaia OS")** — the **closest architectural competitor**: active-
  inference agents + cryptographic claims + "Gaianomics" is nearly the same architecture,
  but **lacks a compute-indexed funding tie** (`footprint_and_visions.md:118`). Study as
  proof-of-concept and differentiation target.
- **ReFi (Regen, Gitcoin, Kolektivo)** — the **cautionary tale**: the MRV/coordination
  substrate is real and durable, but native token-speculation funding is fragile and
  destroys trust when it collapses (REGEN ≈ −94%). PIC reuses the verification learnings
  and **explicitly rejects a native speculative token**; funding comes from compute-
  indexed obligation, not token appreciation (`footprint_and_visions.md:101`).
- **ClimateTRACE / Open Earth** — verification partners/precedent, not competitors
  (`footprint_and_visions.md:117-119`).

### NVIDIA Earth-2 — the reversal-node white space

Earth-2 is NVIDIA's climate/weather digital-twin platform (CorrDiff, FourCastNet3,
cBottle). Adoption is concentrated in weather agencies, insurance/risk, and energy —
**no fetched source shows Earth-2 forecasts tied to financed restoration or MRV/credit
systems** (`nature_finance_mrv.md:141`). That is the white space PIC's challenge/reversal
node names: forecast digital twins predicting fire/drought/flood reversal-risk on
financed sites ([NVIDIA cBottle](https://blogs.nvidia.com/blog/earth2-generative-ai-foundation-model-global-climate-kilometer-scale-resolution/)).
The "AI is already planet-positive" (Huang) objection is answered in
`02_WEDGE_AND_ROADMAP.md` § "Objections ledger", not here.

---

## What this map does NOT claim (the fence)

- **It is a distillation, not fieldwork.** Every claim traces to one of the three
  research reports or a live URL; where those reports flag a figure `n.a.` or
  source-pending (`footprint_and_visions.md:164`; `agentic_stack.md:187`), it stays
  flagged. Operator comparators are not promoted to verified market data.
- **No protocol here is an enemy.** PIC composes on all of them (interoperate, don't
  duplicate). The competitive frame applies only to trust-capture incumbents (rating
  agencies, closed registries) and the one architectural competitor (Digital Gaia).
- **The gap is a claim, not a proof.** The strongest refutation of the whole vision is a
  single existing protocol that binds all five questions with a community-held challenge
  right. This map asserts none exists as of 2026-07; if one appears, update this file and
  reassess the braid.
- **SEED 5/100 stands.** $0 revenue, no track claimed. This is the reason the wedge is
  worth building, not the build.
