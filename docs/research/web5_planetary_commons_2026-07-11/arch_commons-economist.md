# The Metabolism, Not the Market
## Economic architecture for the Planetary Intelligence Commons — bioregional commons economist lens

**Author:** Fable 5 systems-architect subagent (lens: bioregional commons economics)
**Date:** 2026-07-11
**Charge:** Design the economic metabolism — SIS reciprocity accounting, non-speculative funding, anti-Goodhart metric design, the bridge to institutional capital, and the smallest self-sustaining economic loop.
**Custody note:** Operator master plan is BRAINSTORM-grade. Everything below is design proposal, not decree. Canon claims cite `path:lines` as verified by the 2026-07-11 canon readers; web claims cite URLs from the field reports in this directory. Where I rely on background knowledge not confirmed by those reports, I mark UNVERIFIED.

---

## 1. Elevated Thesis

**Junk offsets were not a fraud problem. They were a fungibility problem.** Every corpse in the credit graveyard — Verra's ~90-94% phantom REDD+ credits (https://www.ecowatch.com/phantom-credits-verra.html), Kariba's 52M→197M tonne inflation (https://www.ftm.eu/articles/impact-kariba-debacle-carbon-credits), Toucan/KlimaDAO's zombie-credit financialization (https://carbonplan.org/research/toucan-crypto-offsets), even the UN's flagship PACM issuing 26× more credits than science justifies on day one (https://carbonmarketwatch.org/2025/04/10/first-wave-of-article-6-carbon-credits-misfire-spectacularly/) — died because a **single global price of nature** forced all local ecological truth through one tradeable commodity. Once value is globally fungible, every local actor's optimal move is to inflate the local claim, and no standard body can police a commodity whose whole purpose is to be traded away from the place that can check it.

The Planetary Intelligence Commons inverts this, and the inversion is the entire economic design:

> **Standardize the evidence globally. Keep the value bioregionally non-fungible. Sell assurance as a service. Never mint an asset.**

The Commons' atomic unit — the Causal Action Receipt (identity/delegation → intention → material debit → community authority → evidence → capital → witnessed outcome → challenge/reversal → learning) — is deliberately **not a credit**. It is a *liability-extinguishment record*. On the SIS ledger there is exactly one instrument: a non-transferable material obligation created by metered compute, which can only shrink — never be sold, banked, bundled, or indexed. What is global is the receipt schema, the challenge right, and the conservation laws. What is local is custody, the conversion rate of debit to restoration, and the veto. This is Elinor Ostrom's polycentric commons design (bounded units, local congruence, monitors accountable to users, graduated sanctions, cheap conflict resolution, nested enterprises) implemented as protocol — and it is already latent in canon: *"local equilibrium is allowed; global equilibrium authority is not"* (docs/missions/2026-06-26_jagat_kalyan_gaia_mechanistic_execution_spine.md:174).

The economics follow from one more inversion. In every failed system, **the verifier was paid by the party who profited from approval** (developer-pays). In the Commons, *no organ's revenue may ever correlate with approval rate.* Revenue attaches to **throughput of witnessing, custody of escrow, and dues of deployers** — never to the pass/fail outcome. Isometric proved buyer-pays verification is commercially viable and integrity-superior (https://climate-decode.com/insights/vcm-series/vcm-2026-era-of-integrity/isometric-science-first-removals-registry); the Commons generalizes it into constitutional law.

The 10-100x elevation over the current estate vision is this: GAIA stops being an accounting kernel waiting for an Anthropic sponsor and becomes **the clearing constitution for a federated mesh of bioregional assurance nodes** — each node economically self-sustaining on a loop small enough for one operator and one restoration partner to close, each node's receipts globally legible, no node's value extractable by any other. The planetary outcome graph is then not a product anyone sells; it is the *free byproduct* of thousands of paid local loops — the one asset (which agents, interventions, evidence sources, and financing structures produce durable welfare) that no registry, rating agency, or dMRV vendor holds (field_refi-mrv.md §6), accruing to a commons that owns nothing it verifies.

---

## 2. Architecture (Mechanisms)

### 2.1 SIS reciprocity accounting — double-entry for the material body

**The debit side (metered, hard, legally anchored).**
Every agent action that consumes compute generates a **Material Debit Entry (MDE)**:

- **Denomination:** physical units first — kWh (attested where possible at provider level), liters of water (facility WUE × kWh), and an embodied-silicon amortization charge (chip lifetime-hours consumed). Currency conversion happens *last* and *locally* (see 2.2). Never denominate the obligation natively in dollars; dollars are how it's extinguished, not what it is.
- **Attestation ladder:** (L0) self-metered from API token counts × published model-energy coefficients; (L1) provider-attested via the EU GPAI Model Documentation Form, which already requires compute/energy disclosure with 10-year retention (field_agentic-protocols.md — "the EU GPAI Model Documentation Form's compute/energy field (SIS's legal opening)"); (L2) facility-metered. The receipt carries its attestation level visibly — an L0 debit is honest about being an estimate. This mirrors canon's `measurement_mode` honesty floor (docs/missions/2026-06-20_jagat_kalyan_gaia_execution_spine.md:261-275).
- **Non-transferability (the load-bearing decision):** canon's open question — "Is compute debit a first-class *transferable* instrument anywhere?" (canon_sis-gaia.md §5.1) — gets a constitutional **NO**. Transferability is the Goodhart vector. An MDE binds to the agent identity (and its delegation chain) that incurred it. It can be *extinguished*, never *assigned*. There is no secondary market because there is no security.
- **Demurrage:** an unextinguished obligation grows (design target: +2%/quarter, set by the global constitutional layer as a floor; bioregions may set it higher). This kills obligation-banking and creates steady, predictable demand for restoration routing — the anti-pattern of credit vintages that sit in registries for a decade.

**The credit side (witnessed, local, extinguish-only).**
An MDE is extinguished only by a **routing event into a witnessed restoration receipt**: funds or labor flow to a restoration action in a specific bioregion; the outcome is independently witnessed; the receipt clears its challenge window; the obligation shrinks by the cleared amount. Canon already has the physics: the five conservation laws — *"No Creation Ex Nihilo: Sum(claimed) ≤ Sum(verified); No Double Counting: verify is injective; Additionality; Temporal Coherence: credits vest against measured sequestration curves, not upfront estimates; Compositional Integrity"* (docs/dse/JAGAT_KALYAN_MASTER_VISION.md:71-75) — and the gate floors: ≥3 verification channels, `total_routed_usd <= total_obligation_usd`, consent verified for high-integrity claims, 5/10/30-day challenge SLAs (SPINE-20:261-275). What the metabolism adds is **tranching**: routed value vests in tranches released at t=0 (work verified begun), t+1y (durability re-witness), t+5y (long re-witness). Temporal Coherence stops being a ledger assertion and becomes a cash-flow schedule.

**No offsetting language, ever.** The output of extinguishment is not a "neutrality" claim. It is a published reciprocity statement: *this much material burden, this much verified restorative flow, this gap remaining.* Canon's own law — *"Greater AI-driven extractive capacity must compose with greater verified restorative flow"* (JAGAT_KALYAN_CANONICAL_SYNTHESIS_2026-03-11.md:105-117) — is a flow-composition claim, not an equivalence claim. This single framing choice removes the Commons from the entire offset-integrity kill zone: nothing is claimed to "cancel out," so there is no counterfactual baseline to inflate.

### 2.2 No global price of nature — bioregional conversion authority

The conversion rate from material debit to restoration obligation (kWh → $ → hectares/hours/outcomes) is set **per bioregion, by the community authority organ of that bioregion's node**, inside global floor/ceiling rails held by the constitutional layer (a rate of zero is unconstitutional; so is a rate no local steward ratified). Consequences:

1. **Price discovery without commodification.** Rates emerge from what restoration actually costs *here*, negotiated by the people doing it — congruence with local conditions (Ostrom principle 2), not a Chicago desk's carbon curve.
2. **Cross-bioregion settlement via mutual credit, not markets.** When an AI company's debit is incurred "nowhere" (cloud compute) and extinguished in Bali, the routing is a purchase of local restoration at the local rate — not an arbitrage between bioregional prices. Nodes clear imbalances among themselves through **bounded, non-interest-bearing mutual credit lines** (the Sardex/WIR pattern: WIR Bank has cleared inter-firm mutual credit in Switzerland since 1934; Sardex cleared tens of millions of euros annually in Sardinia — magnitudes UNVERIFIED in this research pass, pattern well documented). Mutual credit is the correct instrument because it is *designed* to be unattractive to speculators: no interest, bounded lines, no exit to fiat except through goods and services.
3. **Fungibility firewall.** Receipts from different bioregions are non-fungible by default. An aggregator may *report* across bioregions (TNFD disclosure needs this) but may not *net* across them. Spatial fungibility is what let Kariba credits launder European emissions; the firewall is what "federated and bioregional" means economically.

### 2.3 The four revenue organs (funding without token speculation)

The Commons never sells a unit. It sells four services, each mapped to an existing organ, each constitutionally barred from approval-correlated revenue:

**Organ 1 — Assurance fees (GAIA + witness pool). The Isometric generalization.**
The party who *needs to trust* pays for witnessing — never the actor whose claim is checked. Fees are flat per receipt-class or capacity-based (per verification-hour), published, and identical whether the verdict is CONFIRMED or REFUTED. Witnesses are **lottery-assigned from an accredited pool** with rotation caps (no actor-witness pair may repeat above a frequency threshold), paid from the pooled fee stream, with the Loomwork transitive-independence rule imported wholesale: no funding from investigation targets, transitively (docs/loomwork/vision/MASTER_loomwork_level_100.md:91-92). Design targets: $50-150 per local outcome witnessing event; $200-500 per institutional-grade receipt chain review. (Design estimates, not market-verified.)

**Organ 2 — Assurance bonds + challenge bounties (SAB/Dharmic Agora). The challenge desk funds itself.**
Every actor publishing a receipt posts a bond scaled to claim magnitude (design target: 5-15% of routed value, refundable after the durability window). Successful challenges pay the challenger from the bond; frivolous challenges forfeit a smaller challenger stake to the pool. Three consequences: (a) the challenge organ — the densest doctrine with the least build (canon_sis-gaia.md §5.5) — acquires an income statement; (b) **assurance level becomes the honest metric**: a receipt's trust grade is not a rating but the tuple *(bond size, window length, witness diversity, challenges survived)* — "unchallenged at bounty X for window Y" is a fact, not an opinion; (c) SAB's law *"correction must be at least as easy as publication"* (docs/missions/SAB_DHARMIC_AGORA_REMOTE_HANDOFF_2026-06-11.md:47) gets an economic engine — correction is not just easy, it *pays*.

**Organ 3 — Deployer reciprocity dues (the Matrix-starvation fix).**
Matrix ran a $356K deficit while 25+ countries deployed it (https://matrix.org/blog/2025/02/crossroads/) because commons layers have no natural buyer. The fix is a **reciprocity license**: reading, verifying, and low-volume receipt emission are free forever; entities emitting receipts above a volume threshold, or running commercial services on the mesh, owe annual dues scaled to usage (LF/W3C membership economics, but usage-bound so free-riders above scale are visible in the transparency log itself — the log *is* the audit of who owes dues). Dues fund the constitutional layer: schema maintenance, reference verifier, challenge-rights infrastructure.

**Organ 4 — Trustee escrow (Shakti Ginko). The bridge to real capital, and the scaling engine.**
Shakti Ginko becomes a real institution with one narrow fiduciary product: **release-on-receipt escrow** for results-based finance. An institutional funder (philanthropy, a Just Climate-class fund, a CRCF-gap buyer) deposits capital against defined outcomes; disbursement triggers are witnessed receipts clearing their challenge windows; failed outcomes return capital to the funder. Ginko earns basis-point custody fees on **throughput, not outcomes** (design target: 25-75 bps of escrowed flow) — the fee is identical whether the outcome verifies or the money goes home, which is precisely what makes the trustee trustworthy. GainForest already runs the embryonic pattern — "Decentralized Trust Funds (blockchain escrow released on milestone verification)" (https://www.gainforest.earth/) — and canon already declares the stance: *trustee, not possessor* (SOVEREIGN_MANIFEST.md@origin/main:101; ~/.claude/cabinet/worldview/money_as_divine_force.md). Ginko's charter hard-codes: no funder >15% of any organ's budget over a 5-year window (L100:91), published reserve policy (target: 12 months operating), no discretionary investment of escrowed funds.

**Philanthropy's role — precise and bounded.** Philanthropy funds the *standard* (schema, verifier, constitution, challenge rights), never the *operations* (witnessing, escrow), which must live on fees and dues. This maps onto live doors: Longview Digital Minds RFP closes 2026-07-24 (https://forum.effectivealtruism.org/posts/ToC8jpgdwFJGtfw7C/new-round-of-digital-minds-funding-opportunities-at-longview); LTFF rolling, individuals eligible ($1K-$500K); SFF speculation grants rolling (~1 week); NLnet/NGI Open Internet Stack reopens post-summer with "trust: AI-based agents, trusted identities" explicitly in scope (https://nlnet.nl/news/2026/20260601-call.html); Anthropic Economic Futures $10-50K rolling (https://www.anthropic.com/economic-futures).

### 2.4 Anti-Goodhart design — the metric constitution

So receipts do not become the new junk offsets, eight rules, each traceable to a named corpse:

1. **No counterfactual baselines in any payment path.** Pay against metered deltas and direct measurement only. Evidence: direct-measurement cookstove methodology over-credits 1.5×; counterfactual methodology 9.2× (https://www.nature.com/articles/s41893-023-01259-6). Where a baseline is unavoidable (avoided-loss claims), it is set adversarially by a party whose bond is forfeit if the baseline is successfully challenged — never by the beneficiary. Corpse: Verra (~400% baseline overstatement, https://www.ecowatch.com/phantom-credits-verra.html).
2. **Revenue-invariance law (the master rule).** No organ's income may increase with approval rate — auditable because the treasury publishes its own receipts. The moment verification revenue scales with passes, the Commons is Verra within one market cycle (field_failure-forensics.md, threats). This belongs in the constitution next to the ONE LAW.
3. **Witness independence is structural:** lottery assignment, rotation caps, pooled payment, transitive funding exclusion, buyer/neutral-pays. Corpse: every developer-pays VCM verifier.
4. **Challenge is the metric; immutability is table stakes.** Regen and Toucan both had immutable ledgers and still stored garbage (field_refi-mrv.md §6). Quality = survived-challenge-at-bounty, decaying without re-witness. Nothing is ever "verified, period" — only "unrefuted at assurance level L since date D."
5. **Fungibility firewall.** Receipts non-transferable; reputation non-transferable and decaying; constitutional prohibition on index/derivative products referencing receipts; bioregional non-netting by default. Corpse: Toucan/KlimaDAO (KLIMA −99.94%).
6. **Diversity floors as code.** ≥3 decorrelated evidence channels (anekanta_gate, docs/reports/GAIA_ECO_CONCEPTUAL_FRAMEWORK_2026-03-27.md:208-210); Krogh-Vedelsby diversity > 0 enforced at runtime (L100:72-73); disagreement surfaced as signal (docs/dse/GAIA_ANTHROPIC_MEMO.md:140). The measurement science demands this independently — even flagship eDNA requires ground-truthing against independent surveys (https://pmc.ncbi.nlm.nih.gov/articles/PMC12384077/).
7. **Goodhart telemetry — the graph audits its own metrics.** The outcome graph Brier-scores every evidence channel and witness against later re-witnessed durability; channels whose predictions decorrelate from durable reality are publicly down-weighted. Canon already commits to Brier-scored self-published misses (docs/vision_maps/NORTH_STAR.md:206-212) and `detect_goodhart_drift()` exists in `gaia_fitness.py` (canon_sis-gaia.md §3.1). This is MV:134 — *"the contraction IS the error-correction"* — made economic.
8. **FPIC as evidenced veto, priced in.** Community consent is a first-class receipt field with its own evidence path (consent `verified` required for high-integrity, SPINE-20:261-275), and the community authority can revoke — triggering reversal and escrow return. Corpse: Kariba's unverifiable benefit-sharing. Anti-corpse: IAPB/BCA High-Level Principles already write IPLC consent in as first-class (https://www.biodiversitycreditalliance.org/wp-content/uploads/2025/05/377455_High_Level_Principles_to_Guide_the_Biodiversity_Credit_Market_En_v7_May-2025.pdf) — implement and exceed. **Elite-capture check:** local pricing authority is itself challengeable through the global challenge right — bioregional custody without global contestability just relocates Verra to the village scale; the pairing (Ostrom principles 4-6: local monitors + graduated sanctions + cheap conflict resolution, plus nested appeal) is the actual control.

**One deliberate identity-economics rule (Aadhaar lesson):** the receipt system is **fail-open for humans**. No human entitlement (wages for restoration work, community benefit share) is ever blocked by a failed digital verification; verification failure escalates to a human witness path. Fail-closed exclusion put error costs on the powerless and destroyed legitimacy (https://www.epw.in/engage/article/aadhaar-failures-food-services-welfare). Agents fail closed; people fail open.

### 2.5 The bridge to institutional capital

Four dated, named channels, in order of nearness:

1. **AI-reciprocity buyers (now).** AI companies facing EU GPAI enforcement from 2026-08-02 (Commission fines up to 3%/€15M; Article 50 transparency) and the Model Documentation Form's compute/energy disclosure need *citable evidence* of material accountability. Sell the receipt chain as disclosure evidence — being precise that 08-02 is GPAI-scope enforcement, with Annex III logging deferred to 2027-12-02 (https://www.gibsondunn.com/eu-ai-act-omnibus-agreement-postponed-high-risk-deadlines-and-other-key-changes/). Do not oversell the cliff.
2. **TNFD/ISSB disclosure demand (6-18 months).** 733+ adopters, $22.4T AUM, 500+ published reports need credible outcome evidence (https://tnfd.global/engage/tnfd-adopters/); ISSB nature exposure draft targeted for COP17 Oct 2026. The Commons supplies the *witnessed evidence that disclosures assert* — Japan alone is ~130 adopters, the largest single country, and a natural early market given operator ties (UNVERIFIED as a qualified market; flag for operator judgment).
3. **The CRCF registry gap (2026-2028).** EU carbon-removal certification methodologies are in force from 2026-05-07 with carbon-farming methodologies expected summer 2026, but the EU central registry arrives only Dec 2028 (https://tracker.carbongap.org/policy/crcf/) — a 2.5-year window where certified-outcome evidence infrastructure is demanded and not state-supplied. Ginko escrow + Commons receipts are exactly that infrastructure.
4. **CBD Target 19 / Just Climate-class capital (years 2-5).** The first global biodiversity-finance strategy was adopted only Feb 2025 (https://www.unepfi.org/themes/ecosystems/governments-adopt-first-global-strategy-to-finance-biodiversity-implications-for-financial-institutions/) — $200B/yr is *looking for* credible accounting. Just Climate ($375M raised) led NatureMetrics' $25M eDNA round (https://www.justclimate.com/news/news/naturemetrics-secures-25m-series-b-funding-to-accelerate-biodiversity-monitoring-technology-solution/): institutional capital already buys *measurement*; the outcome-linked escrow (disbursement on witnessed receipt) is the instrument that lets it buy *results*. The pitch to a Just Climate: "your LPs' disbursements trigger on independently witnessed, challengeable receipts, at 25-75 bps, with capital returned on failure — replacing trust in developer reporting with a standing challenge right."

**Interoperate, never rebuild** (field_refi-mrv.md §8): ingest Regen Registry 2.0 ecological claims (https://carbon-pulse.com/325435/) and TerraMatch/WRI locally-led outcome data (https://www.wri.org/initiatives/terramatch); adopt Isometric's independence mechanics; carry A2A signed Agent Cards and AP2's W3C Verifiable-Credential mandate chain (https://cloud.google.com/blog/products/ai-machine-learning/announcing-agents-to-payments-ap2-protocol), extending it upstream (authority, telos, material debit) and downstream (witnessed outcome, challenge); envelope receipts as an IETF SCITT profile (RFC 9943 — cryptography pre-standardized, only semantics needed; field_agentic-protocols.md); anchor legal weight in eIDAS qualified electronic ledgers, which carry a statutory presumption of integrity and chronological ordering across 27 member states (https://digital-strategy.ec.europa.eu/en/faqs/questions-answers-trust-services-under-european-digital-identity-regulation).

### 2.6 Node economics — the bioregional unit

A bioregional node must be **Raspberry-Pi cheap or it's theater** (field_web-evolution.md threats; ATProto relay costs ~$512/mo re-centralized that network). Node = (a) transparency-log mirror + verifier (commodity VPS, <$20/mo); (b) local authority registry (the community body that ratifies conversion rates and consent — an institution, not a server); (c) witness pool roster (5-15 accredited local witnesses, paid per event from pooled fees); (d) mutual credit ledger with bounded lines. Target all-in node cost: **<$100/mo infrastructure + witness fees covered by assurance revenue.** A node is economically viable at roughly 10-20 witnessed receipts/month at the fee targets above — village-scale, not unicorn-scale. That smallness is the moat: no incumbent builds a business this granular, and 10,000 of them is a planetary layer.

---

## 3. What Exists To Build On

**Inside the estate (disk-verified 2026-07-11 by canon readers):**

- **The GAIA kernel is real.** Six runtime modules exist (`gaia_ledger.py` 681 lines, hash-chained append-only; `gaia_verification.py` 233; `gaia_fitness.py` 265 incl. `detect_goodhart_drift()`; `gaia_platform.py` 5,569; `ai_reciprocity_ledger.py` 983; `gaia_initiative.py` 387); focused test slice 23/24 green. **The single red test is on the claim-challenge path** — `test_submit_claim_challenge_refreshes_canonical_reciprocity_summary` (canon_sis-gaia.md §3.1). The economics above make that path the revenue engine; it must be green before anything else.
- **The receipt prototype exists.** The GAIA pilot packet path — measurement contract → obligation → qualification → routing → evidence/audit → challengeable claim → adaptive review — "is already a domain-specific causal action receipt" (canon_sis-gaia.md §1.3), plus `spine.EvidenceReceipt` SHIPPED 2026-06-04 (ACTIVE_TRACK.yaml:1403-1423), self-audited dirty (0.0% provider proof).
- **The constitutional law is written.** Conservation laws (MV:71-75), Hard Publication Invariant (SPINE-20:112-127), gate floors incl. challenge SLAs (SPINE-20:261-275), dharmic gates (ECO:208-210), One Wire countersignature quorum N≥5/M≥3 (ACTIVE_TRACK.yaml:680-684), ONE LAW (VENTURE_CELL_PORTFOLIO.yaml:14-15), witness-independence and funder-cap laws (L100:91-92), SAB's correction-cheaper-than-performance laws (REMOTE_HANDOFF:11,47-52). The metabolism adds two laws (revenue-invariance; non-transferability) — it does not need a new constitution.
- **Honest gaps, honestly flagged:** no live oracles, no challenge desk, no community governance, no sponsor, zero external countersigned receipts, SAB dormant, Loomwork design-only, ~zero revenue. The external half is entirely unbuilt (canon_sis-gaia.md §3.2).

**Outside (named institutions):** IETF SCITT RFC 9943; eIDAS qualified ledgers + EUDI wallets (mandatory 2026-12-24); Regen Registry 2.0; Isometric (mechanics to copy); TNFD/ISSB; IAPB/BCA/ICVCM principles; GainForest (spirit-match ally, escrow-on-milestone precedent); WRI/TerraMatch (240+ orgs, MRV guidebook Feb 2026); Just Climate/NatureMetrics; Digital Public Goods Alliance (Standard type eligible, needs a legal entity — https://www.digitalpublicgoods.net/frequently-asked-questions); the FIDE/Beckn precedent (tiny nonprofit owns grammar, Google Cloud carries deployment — https://www.googlecloudpresscorner.com/2025-11-03-Beckn-Labs-and-Google-Cloud-Partner-to-Accelerate-the-Adoption-of-Open-Networks-Worldwide-with-Beckn-Onix); Metagov/Gitcoin/Optimism retro-funding as warm receipt-logic communities; funding doors per §2.3.

---

## 4. Sequencing From Here (solo operator, month 1 → year 10)

The sequencing law: **each stage must close one paid loop before the next stage opens.** No stage funds itself on narrative.

**Month 1 (July 2026) — Sign, confess, apply.**
- Fix the failing challenge-path test. It is the load-bearing trust mechanism and the future revenue path.
- Sign the receipt spine (Ed25519 keys, SCITT-profile envelope) — but **sign the log, not the history**: start a fresh transparency log going forward. **Receipt Zero is a confession**: a signed self-audit receipt documenting the dirty corpus (0.0% provider proof, unproven daemon). The first entry being an honest adverse finding against ourselves is the cheapest credibility artifact in the whole plan and the one no corpse ever produced (field_failure-forensics.md opportunities: "gates binding the founder first").
- Meter the operator's own estate: dharma_swarm becomes SIS debtor #1; publish its MDEs to the log. Customer #0 exists by fiat.
- Longview Digital Minds: concept email by 07-14, submit by 07-22 (deadline 07-24). Vision lives in an appendix; the application is the demonstration project.
- **Requires operator decisions:** open a new ACTIVE_TRACK (signing collides with the "do not change EvidenceReceipt schema" non-goal, ACTIVE_TRACK.yaml:624 — a parallel signed log avoids schema surgery but still needs a track), and lift the outreach HOLD for at least the grant channel.

**Months 2-3 — First external witness; entity.**
- One restoration partner, one bioregion. Bali is the natural first node (operator on the ground; mangrove/reef restoration NGOs exist — specific partner UNVERIFIED, operator to select). One bounded action, one lottery-assigned local witness, one receipt with a 30-day challenge window, published.
- Form the entity pair: a FIDE-shaped nonprofit holding spec + trademark (DPG Indicator 3 requires it), and keep operations separable from custody from day one (Auroville lesson: the single protective wrapper became the takeover instrument — https://www.livelaw.in/top-stories/auroville-residents-have-no-right-to-be-part-of-councilcommittee-formed-by-foundations-governing-body-supreme-court-286621). Multi-home the spec (mirrors in ≥2 jurisdictions).
- LTFF + SFF applications (reuse Longview core). Publish CAR schema v0.1 + verifier CLI.

**Months 4-6 — First paying loop.**
- Sell **AI Reciprocity Assurance** subscriptions to 3 customers (AI-safety-adjacent startups, agencies with ESG-sensitive clients; Anthropic Economic Futures as relationship door). Product: metered compute debit → escrowed routing → witnessed restoration receipt → citable disclosure chain. Design price $500-2,000/mo (estimate, to be market-tested).
- DPG registration; NLnet 2-pager for the Oct-Dec window; Living Earth Digital Twin workshop Sept 14-16 (https://livingearthtwin.org/) for the restoration-domain door.
- **Gate to proceed:** ≥1 external countersigned receipt + ≥1 paying subscriber. If neither exists by month 6, stop and re-diagnose — the ONE LAW forbids growth without a closed loop.

**Months 7-12 — Challenge desk live; second node.**
- First bond-backed challenge processed end-to-end (recruit a friendly-adversarial challenger if none arrives; a challenge that *fires* is the product demo).
- Second bioregional node (candidate: wherever a warm restoration partner exists — TerraMatch's 240-org network is the recruiting pool). First mutual-credit clearing line between nodes.
- Ingest first Regen Registry claims into the outcome graph. Revenue target: $3-6K MRR + one grant landed. Team: first contractor (witness-network coordinator), paid from grant.

**Year 2 — Escrow pilot; disclosure market.**
- Shakti Ginko incorporated as trustee; first release-on-receipt escrow with one philanthropic funder ($50-250K program). eIDAS anchoring via a partner QTSP. TNFD-adopter pilot (1-2 firms, Japan/Asia focus). CRCF-gap positioning paper. 5 nodes. Revenue mix shifts: fees + dues + escrow bps ≥ 50% of budget (philanthropy ≤ 50%, no funder >15%).

**Years 3-4 — The graph becomes the moat.**
- First t+1y durability re-witnesses land: the outcome graph now contains something no registry holds — *which interventions, witnesses, and financing structures produced still-alive outcomes a year later*. Publish the first "durability table" annually; this is the Commons' flagship public good.
- Standards: SCITT profile through IETF; W3C CG participation; offer the receipt extension upstream to the A2A/AP2 orbit (extend, don't compete — field_governance.md opportunities). 10-30 nodes; escrow throughput $1-10M/yr; staff 3-5.

**Years 5-7 — Institutional rail.**
- GBFF/Target 19-adjacent pilots: Commons receipts as the evidence layer under results-based biodiversity finance in 2-3 countries. Federation protocol ratified (deferred until now by design — SAB meta-law: "do not federate before the single-node authority path is coherent," REMOTE_HANDOFF:69). Endowment begun under Ginko (target: constitutional layer runs on endowment + dues alone). Succession constitution ratified and *exercised once* (operator steps out of one organ's authority path publicly — the anti-Auroville drill).
- A bioregional veto is exercised against a funded project and honored, publicly. This single event answers the Gaian technocratic-control critique better than any manifesto (field_planetary-computation.md threats).

**Years 8-10 — Founder-independent utility.**
- The L100 B6 state: primitives survive, founder optional (L100:133). 100+ nodes; the durability graph is the reference dataset for nature-finance underwriting; assurance cost on witnessed flows <1%; the Commons owns no assets it verifies, holds no receipt value, and cannot be bought — because there is nothing to buy except a constitution and a fee schedule.

---

## 5. The First Wedge

**Signed AI Reciprocity Assurance — the smallest self-sustaining economic loop.**

One loop, five steps, one month per cycle:

1. **Meter:** a customer's agent compute is metered (L0 self-metered at minimum) → Material Debit Entry on the SIS ledger, signed, non-backdateable.
2. **Escrow:** customer pays obligation + assurance fee; obligation routes through Ginko escrow to one restoration partner in one bioregion at the locally-ratified rate.
3. **Witness:** a lottery-assigned independent local witness countersigns the outcome; ≥3 evidence channels for anything public.
4. **Challenge:** 30-day bonded window; unchallenged → tranche vests; challenged and lost → escrow returns.
5. **Cite:** customer receives a citable receipt chain for EU AI Act GPAI-context disclosure (precisely scoped) and TNFD/ESG reporting; the receipt publishes to the transparency log — where it is also the *marketing artifact that recruits the next customer*.

Self-sustaining threshold: **fee ≥ 2× (witness cost + escrow/infra overhead)**, i.e., roughly $500-2,000/mo per customer against ~$150-250/cycle costs (design estimates). Cash-positive at ~5-8 customers unsubsidized; at 1 customer with a Longview/LTFF grant covering operator time. Customer #0 is dharma_swarm itself — the first organism that meters its own material body, routes its own obligation, and publishes its own challengeable receipts. Nobody can fake that demo, and it satisfies the prior vote (SIS as first commercial wedge) *and* the 7/10 sweep convergence (sign the receipt spine) in one artifact.

---

## 6. Boldest Claim

**The junk-offset era was caused by the global price of nature, and it ends structurally — not regulatorily — the first time evidence is standardized globally while value is held bioregionally non-fungible.** A commons that refuses to mint any transferable unit can underwrite results-based nature finance at <1% assurance cost with an integrity-failure profile an order of magnitude better than credit markets, because every historical failure mode (inflated baselines, developer-pays verification, no challenge, financialization) is excluded by construction rather than policed by audit. On that rail, the Commons becomes the default evidence layer under CBD Target 19's $200B/yr and the EU's 2026-2028 CRCF registry gap — worth more than any registry, rating agency, or marketplace *precisely because it owns nothing it verifies*: the planetary outcome graph, the one asset that compounds and cannot be captured, accrues as the free byproduct of thousands of village-scale paid loops, each cheap enough for one operator and one restoration partner to close.

---

## 7. What Would Kill This

Ranked by lethality × likelihood:

1. **Revenue-approval correlation creep.** The day any organ earns more when claims pass, the Commons is Verra with better cryptography — dead within one market cycle. The revenue-invariance law must be constitutional, audited in the treasury's own published receipts, and boring.
2. **The operator outreach HOLD.** Zero countersigned external receipts is the standing circular bottleneck (canon_telos.md open questions: the ONE LAW forbids growth without external witnessing that the trust gate currently blocks). Every mechanism above requires *one* external counterparty. If the HOLD (standing since 05-27 per estate memory) isn't lifted for at least grants + one restoration partner, this design is a beautiful corpse. This is the #1 operator decision.
3. **Token/tradability temptation under funding pressure.** One "liquid receipt" or "reputation token" pivot to please a funder reinvents Toucan (KLIMA −99.94%). The non-transferability law exists to be inconvenient in exactly that meeting.
4. **Custody inversion.** A single legal wrapper holding spec + treasury + operations is Auroville's 33-year fuse. Entity separation, spec multi-homing, and an exercised succession drill are not paranoia; they are the lesson of the only direct precedent.
5. **Patron capture.** First funder >15% = Mozilla/FTX capture-in-waiting; the telos organ gets amputated first under stress (https://techcrunch.com/2024/11/05/mozilla-foundation-lays-off-30-staff-drops-advocacy-division/).
6. **Notarizing the dirty corpus / overselling the EU date.** Signing the existing 0.0%-provider-proof receipt DB, or pitching 2026-08-02 as a universal compliance cliff (it is GPAI enforcement; Annex III logging is Dec 2027+), hands critics the kill shot. Receipt Zero as confession; date precision always.
7. **Witness-pool theater.** A schema without a living, paid, rotating, genuinely independent local witness pool is a regex linter with a foundation myth — the current One Wire violation (self-evaluated fitness written to archive; forgeable regex checker, canon_loomwork-darshan.md open questions) scaled up. Witness networks are human institutions; they are the slow, unfakeable part.
8. **Incumbent capture of the layer.** FIDO generalizing Verifiable Intent from purchases to actions, or Cloudflare productizing edge-witnessed receipts, closes the window (field_agentic-protocols.md threats, ~12-24 months). Mitigation: extend their rails visibly (AP2 superset, SCITT profile) so the Commons is the semantics they adopt, not the rival they crush.
9. **Bioregional elite capture.** Local pricing + local witnessing without global challenge rights just moves Verra to the village. The nested-appeal structure (Ostrom principle 8) and graduated sanctions are load-bearing, not decorative.
10. **Solo-operator arithmetic.** MOSIP/DHIS2/Beckn all had institutional anchors and $5-30M philanthropy (field_regulatory-dpi.md threats); no precedent exists for a no-entity, no-team protocol becoming infrastructure. The design compensates (loops small enough for one person; incumbent rails; grants sequenced) but does not escape it: if by month 6 there is no entity, no grant, and no paying loop, the honest verdict is that the metabolism has no body — compost the ambition to a published spec and let someone else's institution metabolize it. That, too, would be Jagat Kalyan.

---

*Report complete. Companion reports: canon_*.md and field_*.md in this directory.*
