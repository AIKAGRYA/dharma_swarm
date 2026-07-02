# The Hundred — a connective map of a field that doesn't talk to itself

**An independent synthesis. SEED-stage, $0 revenue, no product, no endorsements.**
Compiled 2026-06-28 from public sources by `dharma_swarm`, a self-evolving AI
research system. Every actor below is real and sourced. **The "seam" line for each is
*our analytical reading* of a structural blind-spot — not a claim the actor makes about
itself, and not a charge of bad faith.** Every one of these actors is genuinely
expert at the slice they hold; the point of the map is that the *slices don't
connect.* Figures are as-sourced; several carry ±1–2 orders-of-magnitude uncertainty
(flagged). Named actors have **not** endorsed this work and are not affiliated with it.

> **Named-person fairness pass (2026-06-28).** Every entry naming an individual was
> re-read against one standard: *is the seam fair analysis of the person's public work,
> or could it read as a personal charge?* Lines were softened toward the work/position
> and away from the person where needed. The two flagged-unverified items (Long/Eleos
> affiliation; Shrikanth's exact "five rules") remain marked *verify* and must be
> confirmed or hard-hedged before any publication. **Redaction option:** before public
> deployment the build can drop personal names to affiliation-level
> (`python3 build.py --redact`; see `site/README.md`) — or the hub can stay local until
> the operator's coherence gate clears. Keeping the source on a low-visibility repo is
> accepted for now (operator call, 2026-06-28); deployment to a public venue is not.

> **The one finding.** Across ~100 actors in six clusters, the same gap recurs from
> every vantage: **diverse competence, correlated blind-spots, no quality
> aggregation** — a textbook failure of the three conditions under which many judges
> beat any one judge. Everyone is in the field. *No one is in the seam.* The seam is
> the connective, decorrelated, receipted verification layer — and the link, missing
> everywhere, between **the material cost of AI** and **the restoration of the living
> systems that cost falls on.**

---

## Cluster A — AI energy & sustainable computing (the "silicon" / debit side)

*Unifying move: measure AI's footprint and bend the **supply and timing** of
consumption toward cleaner power. Collective blind-spot: everyone stops at **"harm
less."** None close the loop from AI's footprint to **active ecological restoration** —
the biosphere is treated as a sink to deplete slower, not a system to regenerate.*

1. **NVIDIA / Jensen Huang** — builds the GPUs; "we are now a power-limited industry." *Seam:* frames efficiency as more-compute-per-watt (a Jevons accelerant), never absolute reduction; zero link to restoration. ([src](https://analyticsindiamag.com/deep-tech/we-are-now-a-power-limited-industry-says-jensen-huang/))
2. **Microsoft** — carbon-negative-by-2030 pledge; nuclear restart for datacenter power. *Seam:* buys clean supply + removal, yet emissions up ~23% — no link from its footprint to regenerating the ecosystems it draws from. ([src](https://blogs.microsoft.com/on-the-issues/2024/05/15/microsoft-environmental-sustainability-report-2024/))
3. **Google** — net-zero-by-2030; first corporate SMR deal; dropped operational-neutrality claim. *Seam:* clean electrons, not regenerated landscapes; emissions +48% since 2019. ([src](https://www.npr.org/2024/07/12/g-s1-9545/ai-brings-soaring-emissions-for-google-and-microsoft-a-major-contributor-to-climate-change))
4. **Amazon / AWS (+ Meta nuclear)** — renewable-matching + nuclear PPAs. *Seam:* "matching" via RECs masks local grid carbon; water/siting impacts and restoration unaddressed. ([src](https://trellis.net/article/amazon-google-meta-and-microsoft-go-nuclear/))
5. **Green Software Foundation (SCI / ISO 21031)** — carbon-per-functional-unit standard. *Seam:* a *rate* metric — software scores well while absolute footprint and ecosystem harm grow; ecology out of frame. ([src](https://greensoftware.foundation/standards/sci/))
6. **Climate Change AI** — research community, ML *for* climate. *Seam:* AI-as-tool-for-mitigation; AI's own footprint and restoration economics are adjacent, not central. ([src](https://www.climatechange.ai/))
7. **Boavizta / EcoLogits** — open multicriteria LCA for genAI inference. *Seam:* measures impact (incl. water, abiotic depletion) but stops at disclosure; no bridge to restoration. ([src](https://ecologits.ai/))
8. **ML CO2 Impact (Jesse Dodge et al.)** — emissions calculator + cloud-carbon research. *Seam:* operational train-time carbon only; embodied/water/restoration out of scope. ([src](https://mlco2.github.io/impact/))
9. **CodeCarbon** — runtime energy/CO₂ tracking library. *Seam:* tracks the electron, not the ecosystem. ([src](https://github.com/mlco2/codecarbon))
10. **Electricity Maps** — real-time grid carbon intensity, 160+ zones. *Seam:* optimizes *when/where* you consume; silent on total demand and regeneration. ([src](https://www.electricitymaps.com/))
11. **WattTime** — marginal emissions signals for load-shifting. *Seam:* reduces emissions-per-shift; demand growth and restoration outside its model. ([src](https://watttime.org/))
12. **IEA — *Energy and AI*** — the authoritative outlook (~415→~945 TWh by 2030). *Seam:* frames AI-energy as a supply/demand-balancing problem; restoration is not a lens. ([src](https://www.iea.org/reports/energy-and-ai/executive-summary))
13. **EPRI — DCFlex** — makes datacenter load grid-flexible. *Seam:* goal is reliability + faster interconnect (enabling *more* AI); regeneration not in scope. ([src](https://dcflex.epri.com/))
14. **LBNL — 2024 US Datacenter Energy Report** — the authoritative US load baseline. *Seam:* consumption accounting; describes the harm curve, doesn't close it. ([src](https://eta.lbl.gov/publications/2024-lbnl-data-center-energy-usage-report))
15. **SemiAnalysis** — granular datacenter/power build-out intelligence. *Seam:* power as a *bottleneck to overcome* for scale; ecology absent. ([src](https://newsletter.semianalysis.com/p/datacenter-model))
16. **Mistral AI (audited LCA)** — first lab to publish a full-lifecycle model LCA. *Seam:* lands at disclosure-as-standard; quantifies harm (incl. water) but proposes no restoration mechanism. ([src](https://mistral.ai/news/our-contribution-to-a-global-environmental-standard-for-ai/))
17. **Sasha Luccioni (Hugging Face / AI Energy Score)** — the field's leading sustainable-AI researcher. *Seam:* theory of change is measure→rate→reduce; restoration outside the efficiency frame. ([src](https://huggingface.github.io/AIEnergyScore/))
18. **Shaolei Ren (UC Riverside)** — quantifies AI's *water* footprint. *Seam:* closest to ecology, but stays diagnostic/allocative — equitable *consumption*, not watershed *restoration*. ([src](https://shaoleiren.github.io/))

## Cluster B — Carbon-removal market & offset-integrity / ratings

*Unifying move: everyone pays a **premium for verifiability** (removal ~380% over
avoidance; CCP-label ~25%). Collective blind-spot: the verification they pay for is
**delegated, self-issued, or mutually contradictory** — and the AI compute-debit
driving demand is **never reconciled** with the credit.*

19. **Microsoft (buyer)** — ~79–93% of all durable-CDR purchases. *Seam:* a one-buyer market; if it pauses (it reportedly did in 2026), demand collapses. ([src](https://www.cdr.fyi/blog/durable-cdr-demand-structure-snapshot-april-2026))
20. **Frontier (Stripe/Alphabet/Meta/Shopify/McKinsey + Anthropic)** — >$1.8B advance market commitment. *Seam:* a handful of tech firms *are* the "rest of market"; demand diversity is an illusion. ([src](https://frontierclimate.com/writing/launch))
21. **Google (buyer)** — >$100M CDR across methods in 2024. *Seam:* each deal under a different verifier; no cross-rater check ties its own portfolio together. ([src](https://www.esgtoday.com/google-invests-over-100-million-in-carbon-removal-in-2024/))
22. **Isometric** — science-first CDR registry/MRV. *Seam:* sets and grades its own standard, then accredits the VVBs that verify — independence is internal, not cross-checked. ([src](https://registry.isometric.com/))
23. **Puro.earth** — durable-removal registry. *Seam:* self-issuing standard-setter; no meta-rater scores Puro credits against rivals'. ([src](https://puro.earth/))
24. **Verra (VCS)** — the largest legacy registry. *Seam:* the structural pattern the market is reforming away from — developers select and pay their own verifiers, and independent studies found a large share of some REDD+ credits did not reflect real reductions (figure contested in magnitude, robust in direction); issuance fell sharply. ([src](https://news.mongabay.com/2025/09/independent-auditors-overvalue-credits-of-carbon-projects-study-finds/))
25. **Gold Standard** — premium-integrity legacy registry. *Seam:* even a high-integrity brand inherits the verification gap — independent analysis found some cookstove methodologies over-credited (~10× in one study); rigor of the underlying verification is the open question. ([src](https://carbonmarketwatch.org/publications/))
26. **Patch** — enterprise procurement across 25,000+ projects. *Seam:* routes credits, passing through each registry's own quality claim; doesn't reconcile disagreeing raters. ([src](https://www.patch.io/))
27. **Cloverly** — API-first marketplace / supplier software. *Seam:* surfaces *liquidity*, not decorrelated *quality* — the API exposes price, not cross-verified integrity. ([src](https://cloverly.com/))
28. **CDR.fyi** — public durable-CDR purchase tracker. *Seam:* exposes the one-buyer risk but is a tracker, not a verifier — no lever on quality or demand depth. ([src](https://www.cdr.fyi/))
29. **ICVCM (Core Carbon Principles)** — supply-side integrity benchmark. *Seam:* labels *programs/methodologies*, not credits; ~4% of 2024 issuance is CCP-approved; delegates to the registries it disciplines. ([src](https://icvcm.org/))
30. **VCMI** — demand-side claims integrity. *Seam:* splits integrity (supply vs demand) with neither owning *credit-quality verification itself*. ([src](https://vcmintegrity.org/))
31. **Sylvera** — carbon-credit rating agency. *Seam:* rated one Amazon project *high* while peers rated it *low* — raters openly disagree; no one reconciles them. ([src](https://trellis.net/article/top-carbon-credit-rating-agencies-are-often-inconsistent-and-inaccurate-watchdog-claims/))
32. **BeZero Carbon** — risk-based rating agency. *Seam:* ratings diverge sharply from peers on identical projects; no standardized cross-rater methodology. ([src](https://carbonmarketwatch.org/publications/rating-the-raters-assessing-carbon-credit-rating-agencies/))
33. **Calyx Global** — over-crediting / safeguard-focused rater. *Seam:* the raters themselves need rating — and only an NGO, not the market, does it. ([src](https://carbonmarketwatch.org/publications/assessing-and-comparing-carbon-credit-rating-agencies/))
34. **Renoster** — algorithmic rating agency. *Seam:* its approach "differs the most" from peers — proof there is no shared ground truth. ([src](https://trellis.net/article/top-carbon-credit-rating-agencies-are-often-inconsistent-and-inaccurate-watchdog-claims/))
35. **Carbon Market Watch** — NGO "rating the raters." *Seam:* the *only* actor doing cross-rater meta-evaluation — but as under-funded advocacy, not priced infrastructure. ([src](https://carbonmarketwatch.org/))
36. **Barbara Haya / Berkeley Carbon Trading Project** — quantified REDD+ over-crediting (>13×). *Seam:* proved baselines are elastic — but the finding lives in papers, not wired into registries' real-time decisioning. ([src](https://gspp.berkeley.edu/research-and-impact/news/recent-news/berkeley-study-finds-widespread-over-crediting-and-weak-safeguards-in-avoid-deforestation-carbon-crediting-programs))

## Cluster C — Nature-tech / MRV / Earth-observation AI / biodiversity sensing

*Unifying move: each is a single-modality, single-vendor **judge** of one slice of
nature. Collective blind-spot: their errors are **correlated** (mostly
optical/satellite, sharing canopy/soil limits), they **disagree** on the soft factors
(additionality, permanence, soil, biodiversity, social) — and **nobody runs
decorrelated cross-modal meta-verification.***

37. **Pachama** — AI + satellite/LiDAR forest-carbon MRV (acq. Carbon Direct, 2025). *Seam:* canopy proxy; its "additionality" is a model prediction, not ground truth. ([src](https://verra.org/worlds-largest-carbon-program-pilots-digital-measuring-of-forest-carbon/))
38. **CTrees** — jurisdictional global deep-learning carbon maps. *Seam:* 100m aboveground biomass; blind to project-level permanence, soil, species. ([src](https://ctrees.org/))
39. **Chloris Geospatial** — AI biomass stock-and-change maps. *Seam:* aboveground only; measures change, not *why* (no counterfactual). ([src](https://www.chloris.earth/))
40. **Sylvera (MRV side)** — geospatial + terrestrial-LiDAR MRV. *Seam:* a judge resting on the same satellite feeds it rates; additionality stays expert judgment. ([src](https://www.sylvera.com/))
41. **Planet Labs** — daily imagery; forest-carbon products. *Seam:* optical pixels — a data feed, not a verifier; infers carbon via model. ([src](https://www.planet.com/products/forest-carbon/))
42. **SustainCERT** — accredited verification body building digital MRV. *Seam:* digitizes the audit *paperwork*; still depends on project-reported data. ([src](https://www.sustain-cert.com/))
43. **Open Forest Protocol** — open blockchain MRV. *Seam:* immutability ≠ accuracy — guarantees data wasn't *changed*, not that it was *true*. ([src](https://www.openforestprotocol.org/))
44. **Cecil (cecil.earth)** — nature-data marketplace aggregating datasets. *Seam:* a router of others' data — inherits every upstream blind-spot; surfaces disagreement, doesn't resolve it. ([src](https://newsletter.cecil.earth/p/operating-in-spite-of-uncertainty))
45. **NASA GEDI** — spaceborne LiDAR biomass (the calibration truth source). *Seam:* sparse sampling, ISS-latitude only, no soil/biodiversity — a sampler others interpolate. ([src](https://www.earthdata.nasa.gov/sensors/gedi))
46. **ESA Copernicus / Sentinel-1 SAR** — free cloud/night-penetrating radar. *Seam:* saturates at high biomass; can't see understory/soil/species. ([src](https://sentinel.esa.int/))
47. **IBM–NASA Prithvi** — open 600M-param geospatial foundation model. *Seam:* trained on optical pixels; embeddings inherit optical blind-spots; makes no verification claim. ([src](https://research.ibm.com/blog/prithvi2-geospatial))
48. **Clay Foundation Model** — open EO embedding backbone. *Seam:* encodes *appearance*, not carbon/biodiversity truth; needs labels to mean anything. ([src](https://clay-foundation.github.io/model/))
49. **Google DeepMind AlphaEarth** — "virtual satellite" fused embeddings. *Seam:* a single-vendor *representation*, not a verifier; proprietary internals; no biodiversity/soil/counterfactual. ([src](https://deepmind.google/discover/blog/alphaearth-foundations-helps-map-our-planet-in-unprecedented-detail/))
50. **Microsoft Planetary Computer / AI for Good** — EO data substrate + biodiversity R&D (SPARROW). *Seam:* hosts everyone's data, owns no verdict; SPARROW adds one modality, not a meta-judge. ([src](https://planetarycomputer.microsoft.com/))
51. **Restor (Crowther Lab / ETH Zürich)** — open restoration-data platform, 200k+ sites. *Seam:* rare connective tissue, but its biodiversity/soil layers are *modeled* predictions, not measured; no verification authority. ([src](https://restor.eco/))
52. **BirdNET (Cornell)** — bioacoustic bird ID (~3,000 species). *Seam:* one taxon/modality; presence ≠ population health; nothing on carbon/soil. ([src](https://birdnet.cornell.edu/))
53. **NatureMetrics** — eDNA biodiversity monitoring. *Seam:* detects presence/richness at sampled points; not abundance/carbon/permanence; disconnected from the carbon stack. ([src](https://www.naturemetrics.com/))
54. **Rainforest Connection (RFCx)** — solar acoustic alerts (logging/poaching). *Seam:* event detection, not carbon or biodiversity census. ([src](https://rfcx.org/))
55. **Wildlife Insights (Google + CI)** — camera-trap AI, 200M+ images. *Seam:* terrestrial vertebrates in view only; no carbon/soil link. ([src](https://www.wildlifeinsights.org/))
56. **iNaturalist / GBIF** — 3B+ citizen-science records. *Seam:* opportunistic presence-only data, severe bias; no abundance or carbon. ([src](https://www.gbif.org/))

## Cluster D — Ecological restoration, biodiversity conservation & Indigenous / justice

*Unifying move: name the crisis and the desired state (30×30, restore degraded
ecosystems, recognize IPLC stewardship). Collective blind-spot: the **verifiable,
just, comparable connective tissue** to finance/verification is missing — pledges and
opportunity-maps proliferate while proof lags, and finance routes **around, not
through** the ~80%-biodiversity-stewarding Indigenous communities.*

57. **UN Decade on Ecosystem Restoration** — the umbrella mandate. *Seam:* owns the end-state + a framework; aggregate, comparable, verifiable global tracking is still aspirational. ([src](https://www.decadeonrestoration.org/))
58. **Society for Ecological Restoration (SER)** — the practice standards. *Seam:* voluntary, disconnected from the finance/verification layer that decides funding. ([src](https://www.ser.org/))
59. **IUCN (+ Global Standard for NbS)** — design criteria for nature-based solutions. *Seam:* self-assessed, not independently verified. ([src](https://iucn.org/))
60. **WWF** — the crisis narrative (Living Planet Index). *Seam:* measures decline, not whether interventions reverse it at scale. ([src](https://www.worldwildlife.org/publications/2024-living-planet-report))
61. **The Nature Conservancy** — largest conservation org; NCS science. *Seam:* leans on markets where additionality/permanence are unproven. ([src](https://www.nature.org/))
62. **Conservation International** — "irrecoverable carbon" map + finance lab. *Seam:* has the target map; the financing-to-stewards remains pilots, not flow. ([src](https://www.conservation.org/projects/irrecoverable-carbon))
63. **Trillion Trees (BirdLife/WWF/WCS)** — forest-restoration coalition. *Seam:* tree-count framing over ecosystem integrity; weak on durability/biodiversity/rights proof. ([src](https://trilliontrees.org/))
64. **Rewilding Europe** — large-landscape nature recovery. *Seam:* process-led outcomes are hard to standardize/compare against the metric-driven verification world. ([src](https://rewildingeurope.com/))
65. **Restor (movement layer)** — see #51; the rare visibility/connective map. *Seam:* presence on the map ≠ verified outcome or funding. ([src](https://restor.eco/))
66. **1t.org (WEF)** — corporate trillion-tree pledge registry. *Seam:* strong on pledges, weak on verified delivery — no additionality/permanence backbone. ([src](https://www.weforum.org/projects/1t-org/))
67. **World Resources Institute (WRI)** — restoration opportunity atlas; hosts LandMark. *Seam:* maps the *where*; the link to financed, locally-led, verified restoration is the missing middle. ([src](https://www.wri.org/initiatives/global-restoration-initiative))
68. **Bezos Earth Fund** — largest private nature funder. *Seam:* big capital through Northern intermediaries — re-creates the route-around-stewards disconnect. ([src](https://www.bezosearthfund.org/))
69. **ICCA Consortium (Territories of Life)** — IPLC territory custodian + registry. *Seam:* holds the custody evidence, but it's structurally hard to connect to finance without ceding sovereignty. ([src](https://www.iccaconsortium.org/))
70. **Nia Tero** — direct Indigenous-guardianship finance (~92% direct). *Seam:* proves the just-finance route exists — but at philanthropic scale, orders below the market channels. ([src](https://www.niatero.org/))
71. **Local Contexts (TK / BC Labels)** — Indigenous data-sovereignty infrastructure. *Seam:* the data platforms and the sovereignty layer barely interoperate. ([src](https://localcontexts.org/))
72. **Global Forest Coalition** — IPLC justice watchdog. *Seam:* documents the injustice (<1% of climate finance reaching IPLCs) but operates in critique mode, outside the infrastructure. ([src](https://globalforestcoalition.org/))
73. **LandMark** — global Indigenous/community land-tenure map. *Seam:* up to 65% of land is IPLC-held, ~10% legally recognized — vast stewarded territory invisible to finance. ([src](https://www.landmarkmap.org/))

## Cluster E — Standards, nature finance, disclosure & biodiversity credits

*Unifying move: standardize the **reporting** of nature and **park capital** against
it. Collective blind-spot: each owns one slice (disclose, target, fund, issue, score);
**none owns the handoff — independent, comparable, outcome-level verification.** Money
is parked at the verification gate, and no one links AI's compute-debit to nature
finance.*

74. **TNFD** — nature-related financial disclosure framework (500+ adopters). *Seam:* disclosure ≠ verification — "TNFD-aligned" is self-declared, no assurance gate. ([src](https://tnfd.global/))
75. **SBTN** — science-based targets for nature. *Seam:* methods partial; MRV guidance pending; few validated targets. ([src](https://sciencebasedtargetsnetwork.org/))
76. **ISSB / IFRS S2** — global baseline disclosure standards. *Seam:* the would-be teeth, but the *nature* standard doesn't exist yet (draft 2026+). ([src](https://www.ifrs.org/projects/work-plan/biodiversity-ecosystems-and-ecosystem-services/))
77. **GRI 101: Biodiversity (2024)** — impact-materiality reporting. *Seam:* another standard on a crowded shelf; no independent comparability mechanism. ([src](https://www.globalreporting.org/standards/standards-development/topic-standard-for-biodiversity/))
78. **CDP** — corporate environmental disclosure pipe. *Seam:* biodiversity disclosures remain *unscored* — data collected, not made comparable. ([src](https://www.cdp.net/))
79. **SEEA-EA (UN)** — national ecosystem accounting standard. *Seam:* national accounts rarely feed corporate disclosure or finance — a parallel statistician track. ([src](https://seea.un.org/))
80. **The Dasgupta Review (HM Treasury)** — nature-as-asset economics. *Seam:* diagnosis without an enforcement mechanism; no institution owns turning it into verified value. ([src](https://www.gov.uk/government/publications/final-report-the-economics-of-biodiversity-the-dasgupta-review))
81. **Stockholm Resilience Centre** — planetary boundaries (7 of 9 breached). *Seam:* the "safe operating space" has no ledger — global thresholds don't translate to actor-level verifiable units. ([src](https://www.stockholmresilience.org/research/planetary-boundaries.html))
82. **Pollination Group** — climate/nature investment + advisory. *Seam:* finance parked at the gate — its own report puts realized biodiversity-credit sales at ~$0.3–1.85M. ([src](https://pollinationgroup.com/))
83. **NatureVest (TNC)** — conservation impact investing (~$3.5B). *Seam:* bespoke deals don't make a market — no fungible, independently-verified unit to scale. ([src](https://www.nature.org/en-us/about-us/who-we-are/how-we-work/finance-investing/naturevest/))
84. **BIOFIN (UNDP)** — national biodiversity finance plans. *Seam:* a ~$700B/yr gap vs. billions mobilized — planning exists, capital doesn't arrive. ([src](https://www.biofin.org/))
85. **GBFF (GEF)** — the flagship GBF fund (~$386M pledged). *Seam:* tiny vs the $700B gap — pledges an order of magnitude short. ([src](https://www.thegef.org/what-we-do/topics/global-biodiversity-framework-fund))
86. **TFFF (Tropical Forests Forever Facility)** — pay-for-performance standing-forest finance. *Seam:* <¼ of needed capital; "slow takeoff" because the satellite-MRV-to-payment trust mechanism is unproven at scale *(launch-week figures)*. ([src](https://www.wri.org/news/statement-brazil-launches-tropical-forests-forever-facility))
87. **Wallacea Trust** — basket-of-metrics biodiversity-credit method. *Seam:* a basket per ecoregion means no two credits are the same unit — rigor undercuts fungibility. ([src](https://wallaceatrust.org/))
88. **Plan Vivo / rePLANET / Terrasos+Cercarbono** — the biodiversity-credit supply side. *Seam:* a market ~$8M total; credits "under development" vastly exceed credits sold; fragmented standards, no interoperable unit. ([src](https://www.planvivo.org/pv-nature))
89. **WEF Biodiversity Credits Initiative** — demand-side governance convener. *Seam:* projections ($2–69B) vs realized demand (<$2M) — principles waiting for a buyer. ([src](https://www.weforum.org/publications/high-level-principles-to-guide-the-biodiversity-credit-market/))
90. **S&P Global Sustainable1 / MSCI / IBAT / Big Four** — nature-risk data + assurance. *Seam:* scores *risk exposure* (modeled), and assurance audits *process*, not *biodiversity outcomes* — the data and auditors exist but aren't wired into outcome verification. ([src](https://www.spglobal.com/sustainable1/en/solutions/nature-and-biodiversity))

## Cluster F — Intellectual anchors: the thinkers, the AI-ethics/welfare & interpretability voices

*Unifying move: a bounded, reciprocal, just relationship between intelligence, the
economy, and the biosphere. Collective blind-spot: strong on diagnosis, desired-state,
and ethic; uniformly weak on the **verifiable, receipted, operational route** — and
**the ecological-verification and AI-ethics/welfare literatures do not cite or talk to
each other**, leaving the seam between "AI as planetary extraction" and "AI as a being
owed consideration" entirely unoccupied.*

91. **Siddarth Shrikanth** — *The Case for Nature*; criteria for credible nature markets. *Seam:* names *what* a credible market needs; supplies no receipted, machine-verifiable mechanism that proves a credit real *(his exact "five rules" wording paraphrased — verify against the text).* ([src](https://www.duckworthbooks.co.uk/book/the-case-for-nature/))
92. **Partha Dasgupta** — nature-as-asset economics. *Seam:* the accounting frame, not the verification substrate. ([src](https://www.gov.uk/government/publications/final-report-the-economics-of-biodiversity-the-dasgupta-review))
93. **Johan Rockström** — planetary boundaries. *Seam:* quantifies the ceiling; leaves open the per-actor attribution mechanism. ([src](https://www.stockholmresilience.org/research/planetary-boundaries.html))
94. **Carl Folke** — resilience / social-ecological systems. *Seam:* theorizes adaptive loops; doesn't operationalize a closed sense→act→verify cycle on real data. ([src](https://www.stockholmresilience.org/))
95. **Kate Raworth** — Doughnut Economics. *Seam:* a compelling target-state image; weak on the per-decision verification route. ([src](https://www.kateraworth.com/doughnut/))
96. **Robin Wall Kimmerer** — *Braiding Sweetgrass*; reciprocity. *Seam:* names reciprocity as a moral relationship; no mechanism to register whether an obligation was honored. ([src](https://www.robinwallkimmerer.com/))
97. **Bill McKibben** — *The End of Nature*; 350.org. *Seam:* mobilizes pressure; operates on movement metrics, not receipted per-actor accountability. ([src](https://billmckibben.com/))
98. **Kate Crawford** — *Atlas of AI*; AI as extraction. *Seam:* diagnoses extraction vividly; doesn't build the meter for a specific run's footprint. ([src](https://katecrawford.net/))
99. **"Taking AI Welfare Seriously" (Long, Sebo, Butlin, Birch, Chalmers et al., 2024)** — AI welfare as a serious near-term question. *Seam:* calls for assessing AI systems for consciousness but the assessment instrument doesn't yet exist. ([src](https://arxiv.org/abs/2411.00986))
100. **Jeff Sebo** — *The Moral Circle*; moral consideration under uncertainty. *Seam:* argues *that* we should include uncertain minds; no operational test for when a system crosses the threshold. ([src](https://jeffsebo.net/research/))
101. **Robert Long (Eleos AI)** — applied AI-welfare evals *(affiliation per reporting — verify)*. *Seam:* pushes toward welfare evals; no validated, receipted indicator an external party could act on. ([src](https://arxiv.org/abs/2411.00986))
102. **Jonathan Birch** — *The Edge of Sentience*; precautionary framework. *Seam:* a decision procedure under uncertainty — routes around, doesn't close, the missing empirical verification. ([src](https://global.oup.com/academic/product/the-edge-of-sentience-9780192870421))
103. **David Chalmers** — philosophy of mind; the "hard problem." *Seam:* names the verification gap at its deepest; by construction offers no operational bridge. ([src](https://arxiv.org/abs/2411.00986))
104. **Chris Olah (Anthropic interpretability)** — mechanistic interpretability; sparse-autoencoder features. *Seam:* can read activations; the bridge from features to morally-relevant states is open. ([src](https://transformer-circuits.pub/))
105. **Neel Nanda (DeepMind mech-interp)** — scales the interpretability toolchain. *Seam:* candidly warns the most ambitious "understand what AIs are thinking" vision may not close in time. ([src](https://www.neelnanda.io/about))

---

## The whole picture, in one paragraph

Six clusters, ~105 brilliant actors, one recurring shape. The AI-energy people meter
the harm and stop at "harm less." The carbon market pays a premium for verification it
then delegates, self-issues, or contradicts. The nature-tech people are single-modality
judges with correlated blind-spots who openly disagree on the soft factors. The
restoration movement names the crisis but can't connect it, justly, to finance. The
standards bodies standardize reporting and park capital at the verification gate. And
the thinkers — ecological and AI-ethical alike — diagnose the gap precisely and hand off
before building the meter, in two literatures that never meet. **Diverse competence,
correlated errors, no quality aggregation.** That is not a list of failures; it is a map
of a seam — the connective, decorrelated, receipted, footprint-metered, sovereignty-
respecting verification layer that links the cost of intelligence to the repair of the
living world — that no one is standing in. *That is the thing worth building, and the
reason to connect these hundred.*
