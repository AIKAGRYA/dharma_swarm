# Loomwork — Frontier Landscape

**Author:** worker fork (research pass), 2026-05-07 (retry of rate-limited prior run)
**Status:** Vision research — level-100 articulation. No code commitments.
**Frame:** Where does Loomwork actually fit in the 2026 ecosystem of dot-connection / pattern-surfacing / OSINT-supramental-layer platforms? What's been tried, what failed, what's defensible.

---

## Section 1 — The Field at 2026: Who Is Building This

Loomwork's adjacency space is wider than "another investigative platform." It overlaps with investigative consortia, OSINT/forensics shops, climate-accountability data orgs, wildlife/ocean monitoring, conflict/atrocity tracking, modern-slavery research, civil-society defense, refugee-mobility, public-health surveillance, indigenous-rights mapping, and commercial intelligence platforms. **No single existing organization spans the union.** Each has a slice; Loomwork's claim to existence is the cross-pollination layer the slices cannot build for themselves.

### Investigative consortia (network model)

- **ICIJ — International Consortium of Investigative Journalists** ([icij.org](https://www.icij.org/)). 280 investigative journalists, 140+ media orgs, 100+ countries; produced Panama (2016), Paradise (2017), Pandora (2021), Cyprus Confidential (2023). Database surface: [Offshore Leaks DB](https://offshoreleaks.icij.org/). **What they can't see:** patterns BETWEEN their leaks and the public-source landscape (sanctions, supply chains, satellite). Their consortium model is human-coordinated, not engine-coordinated. **Loomwork gain:** continuous cross-pollination between ICIJ's leaked corpus and live public sources surfaces patterns ICIJ would otherwise need a 600-journalist project to find.

- **OCCRP — Organized Crime and Corruption Reporting Project** ([occrp.org](https://www.occrp.org)). Aleph database: 3.8B+ entries, 50+ TB, 400M+ documents, 200+ datasets. Launched [Observatorio Transfronterizo de la Corrupción](https://www.icij.org/news/2025/01/new-platform-draws-on-investigative-journalism-to-identify-cross-border-patterns-of-corruption/) in 2025 — explicit cross-border pattern platform. **What they can't see:** automated cross-source correlation at machine speed; their pattern detection is reporter-driven. **Loomwork gain:** an upstream layer that surfaces dot-candidates before reporters search. Aleph as ingestion source, Loomwork as inference layer.

- **Bellingcat** ([bellingcat.com](https://www.bellingcat.com/)). Open-source visual forensics consortium; published [Online Investigation Toolkit](https://bellingcat.gitbook.io/toolkit/). MH17 Buk-332 attribution → Dutch JIT 2018 confirmation → 2022 conviction in absentia. **What they can't see:** patterns across the OSINT corpus beyond what their reporters work on; no atom-graph layer. **Loomwork gain:** their published work as ingestion source; their methodology validated by JIT as legal-grade evidence — Loomwork can extend that validation to non-conflict domains.

- **Forbidden Stories** ([forbiddenstories.org](https://forbiddenstories.org)). Carries on the work of murdered/threatened journalists. Pegasus Project (2021), Cartel Project, Forever Lobbying Project. **What they can't see:** what suppression patterns predict next assassination. **Loomwork gain:** a pattern-detection layer that flags suppression signal escalation before kinetic outcome.

- **GIJN — Global Investigative Journalism Network** ([gijn.org](https://gijn.org)). 244 member orgs in 90+ countries; capacity-building, training, resource hub. **What they can't see:** they're a federation of investigators, not a federation of evidence. **Loomwork gain:** reverse — Loomwork is evidence federation that GIJN orgs would consume.

- **Source Material UK** ([source-material.org](https://www.source-material.org)). Small but high-yield model — climate, fossil capital, supply chain. **What they can't see:** scaling beyond the small-team output. **Loomwork gain:** they become a high-trust partner+citation source.

### OSINT/forensics shops (commercial + nonprofit)

- **Forensic Architecture** (Goldsmiths, [forensic-architecture.org](https://forensic-architecture.org/)). Architectural-grade reconstruction of human rights violations; Grenfell Tower, Russian war crimes. ICC submissions. **What they can't see:** patterns at population scale beyond their case-by-case bandwidth. **Loomwork gain:** atom feed of state-violence indicators that triggers Forensic Arch case prioritization.

- **Airwars** ([airwars.org](https://airwars.org)). Tracks civilian harm in airstrikes (US/UK/Russia/Israel/Coalition). Source-of-record for monitoring orgs and journalists. **What they can't see:** non-airstrike harm correlated with airstrike data (displacement, infrastructure collapse). **Loomwork gain:** cross-source linking of airstrike harm with downstream displacement/health/economic patterns.

- **SITU Research** ([situ.nyc/research](https://situ.nyc/research/)). Spatial analysis for ICC, UN. **What they can't see:** automated pattern-flag pipelines; case-driven not corpus-driven. **Loomwork gain:** corpus layer feeding case selection.

- **C4ADS — Center for Advanced Defense Studies** ([c4ads.org](https://c4ads.org/)). Sanctions, conflict, illicit networks; hybrid commercial-research. **Limit:** US-policy adjacent; some funding signals. **Loomwork gain:** parallel evidence with different funding base + non-Western angles.

- **Sayari Labs** ([sayari.com](https://sayari.com)). Commercial OSINT — corporate networks, beneficial ownership, sanctions. Closed-source, $$$/seat. **What they can't see:** what non-paying journalists/regulators/NGOs need. **Loomwork gain:** open-source alternative with explicit non-commercial use covered.

- **Maltego** ([maltego.com](https://www.maltego.com/)) and **ShadowDragon** ([shadowdragon.io](https://shadowdragon.io/)). Investigation graph platforms — operator tools, not corpus engines. **What they can't see:** they're glass-on-investigator-desk, not autonomous-pattern-surfacing. **Loomwork gain:** a corpus layer that produces leads Maltego/ShadowDragon operators investigate.

### Climate accountability

- **Climate TRACE** ([climatetrace.org/data](https://climatetrace.org/data)). Coalition; emissions inventory by source. Hyper-resolved attribution. **What they can't see:** non-emission consequences (regulatory dockets, ESG claims, financial flows of polluters). **Loomwork gain:** Climate TRACE as ingestion → cross-link with corporate filings, ESG awards, lobbying records → "Methane-Award Paradox" pattern class.

- **Carbon Mapper** ([carbonmapper.org](https://carbonmapper.org/)). Methane plume detection (Tanager-1 + airborne); facility-level resolution. **What they can't see:** operator attribution beyond facility — corporate parent, financial flows, regulatory history. **Loomwork gain:** plume detection → operator graph → regulator/journalist/NGO routing.

- **MethaneSAT** (EDF, [methanesat.org](https://www.methanesat.org/)). 2 ppb sensitivity, 90-min cadence, >80% O&G coverage. **Same gap as Carbon Mapper.** **Loomwork gain:** same cross-pollination layer; sensor independence (different orbital, different frequency) → corroboration.

- **Global Forest Watch** ([globalforestwatch.org](https://www.globalforestwatch.org/)). DIST-ALERT integrated alerts (Jan 2026); near-real-time disturbance globally. **What they can't see:** which alert is on indigenous-claimed land, which concession, which enforcement contact, which media pressure point. **Loomwork gain:** alert → contextualized actionable bundle → defender/journalist routing.

- **Trase** ([trase.earth](https://trase.earth)). Commodity supply-chain to deforestation. **What they can't see:** beyond commodity flows — financial flows funding the commodity flows. **Loomwork gain:** Trase as source + finance corpora cross-linked.

### Wildlife / ocean

- **Global Fishing Watch** ([globalfishingwatch.org](https://globalfishingwatch.org/)). Vessel tracking; AIS-disabling hotspots, dark vessel detection via SAR. **What they can't see:** beneficial ownership of dark fleets in offshore registries. **Loomwork gain:** dark vessel → corporate registry trace via Aleph/OpenCorporates → "Dark-Vessel Green-Flags" pattern.

- **EJF — Environmental Justice Foundation** ([ejfoundation.org](https://ejfoundation.org/)). IUU fishing + labor abuse. **Loomwork gain:** EJF investigations as ingestion + atom-level cross-linking.

- **OceanMind** (commercial; satellite + AI for fisheries enforcement). **Loomwork gain:** complementary nonprofit cousin.

- **TRAFFIC** ([traffic.org](https://www.traffic.org)). Wildlife trade monitoring. **Loomwork gain:** TRAFFIC reports as ingestion + cross-linking with sanctions/customs data.

### Conflict / atrocity

- **ACLED — Armed Conflict Location & Event Data Project** ([acleddata.com](https://acleddata.com/)). Real-time conflict event geocoding. Used by US/EU/UN. **What they can't see:** the political/financial sphere around events — funding chains for armed groups, narrative-shaping coordination. **Loomwork gain:** ACLED events × sanctions × corporate filings × media-narrative analysis.

- **UCDP — Uppsala Conflict Data Program** ([ucdp.uu.se](https://ucdp.uu.se/)). Long-form historical conflict dataset. **Loomwork gain:** historical context atomized + cross-linked with current ACLED events.

- **Center for Civilians in Conflict (CIVIC)**. Civilian harm policy. **Loomwork gain:** policy claims as testable atoms against actual harm.

### Modern slavery / labor

- **Walk Free** ([walkfree.org](https://www.walkfree.org)). Global Slavery Index — ~50M people in modern slavery (2023). **What they can't see:** tier-3+ supplier specifics; their estimates aggregate. **Loomwork gain:** supply-chain cross-linking surfaces specific facility flags.

- **IJM — International Justice Mission** ([ijm.org](https://www.ijm.org)). Field-operational; rescue + prosecution support. **Loomwork gain:** their casework as anchor for atom-level corroboration of slavery patterns.

- **Polaris Project**. Human trafficking hotline data. **Loomwork gain:** hotline patterns as input.

- **Talent Beyond Boundaries** ([talentbeyondboundaries.org](https://www.talentbeyondboundaries.org/)). Refugee labor mobility, 150K+ skilled candidates. IOM partnership 2026. **What they can't see:** destination-country labor-shortage signal + credential-bottleneck patterns at scale. **Loomwork gain:** "Refugee Credentials in Shortage Countries" pattern class — direct partnership target.

### Civil society defense

- **AccessNow** (digital rights), **EFF** (US/global), **Citizen Lab** (Toronto — surveillance research, Pegasus, NSO), **AlgorithmWatch** (Berlin — algorithmic accountability), **Mozilla Foundation** (Trustworthy AI program). **Loomwork gain:** these are partners and citation chains, not competitors. Loomwork's atoms feed their advocacy work; their reports feed Loomwork's ingestion.

### Refugee / migration

- **UNHCR Project Jetson** (predictive displacement). **IOM** (operational migration). **Loomwork gain:** displacement-prediction × labor-shortage × credential-bottleneck cross-pollination.

### Health / pandemic

- **WHO EIOS — Epidemic Intelligence from Open Sources**. 80,000+ sources/day scanned. Limited to WHO partners. **Loomwork gain:** parallel, broader-source, public-facing pattern surface.

- **ProMED**. Volunteer-curated outbreak intelligence; gold standard but bottlenecked. **Loomwork gain:** machine-augmentation of curation; non-English coverage expansion.

### Indigenous rights

- **RAISG — Amazon Geo-Referenced Socio-Environmental Information Network** ([raisg.org](https://www.raisg.org)). Amazon basin indigenous mapping. **Loomwork gain:** PADDD events × deforestation alerts × indigenous-territory overlap → "PADDD-then-Deforestation on Indigenous Lands" pattern.

- **AMAN** (Indonesia indigenous alliance), **COIAB** (Brazil indigenous coordinator). **Loomwork gain:** community defenders as routing endpoints, not just data sources.

### Commercial platforms (the moat-defining comparison)

- **Palantir Foundry / Gotham** ([palantir.com](https://www.palantir.com/platforms/gotham/)). The explicit reference dharma_swarm's `ontology.py` line 3 quotes: *"Palantir built this pattern for supply chains and kill chains. We take the engineering and reforge it for Jagat Kalyan."* Gotham serves defense/intelligence; Foundry serves enterprise. Both share the typed-Ontology pattern: ObjectType → OntologyObj instances → Link → ActionDef. Both are closed, expensive, capture-prone. ([Palantir Ontology docs](https://www.palantir.com/platforms/ontology)). **What they can't see / serve:** civil-society use cases at zero seat-cost; nonprofit accountability work; partners who refuse Palantir on principle. **Loomwork gain:** the architecture pattern is correct; the customer base is the inversion. Loomwork = Foundry-for-public-good.

- **Recorded Future** (commercial threat intel) — same closed/expensive pattern.

- **Dataminr** (real-time event detection). Same.

### What the field at 2026 *does not have*

- **No public, open-source, typed-Ontology platform** for civil-society pattern surfacing. There are graphs (Wikidata, Aleph), there are tools (Maltego), there are corpora (ICIJ leaks), there are sensor networks (Carbon Mapper, GFW). **There is no platform that ingests across all of these into a typed atom-and-link substrate with publication-grade telos gates.** That's the gap.

- **No platform trained on the cross-pollination problem.** Existing platforms specialize. Loomwork's claim is generalist atom-cross-pollination is its primary product, not a side effect.

- **No platform that operationalizes Akram-grounded refusal.** Telos-gated publication that can refuse to publish a true revelation when publication harms vulnerable persons — this is doctrine in dharma_swarm; it is implemented nowhere else.

---

## Section 2 — What Has Been Tried, What Failed

### Sunlight Foundation (US, 2006-2020)
Lobbying transparency, OpenCongress, Influence Explorer. Sunset 2020 due to funding model (foundation grants without sustainable revenue), strategic drift (broadened from open-government to "civic tech" generally), and the rise of competitor platforms (OpenSecrets, GovTrack, ProPublica). **Portable lesson:** mission-narrow + revenue-honest beats mission-broad + grant-dependent. Loomwork must guard against scope creep into "civic tech in general."

### WikiLeaks (2006-present, peak 2010)
Cablegate (Nov 2010) was peak influence; transformative. Decline factors: editorial-vs-publication tension (Manning data → Iraq War Logs published in bulk); Assange's personal capture (asylum, extradition); financial deplatforming (Visa/MasterCard/PayPal cutoff Dec 2010 — broken via Bitcoin lifeline); coalition fragmentation (Greenwald/Poitras split for Snowden, ICIJ outcompeted on infrastructure); reputational capture (state-actor sourcing accusations 2016+). **Portable lesson:** distributed mirroring works; individual-figure capture is fatal; financial sovereignty is non-optional; editorial process is what differentiates publication from leak-dump. Loomwork must have all four built in from day 1.

### DARPA Total Information Awareness (2002-2003)
Defunded by Congress (Sept 2003) after public outcry. Key components migrated to NSA classified programs (revealed by Snowden 2013). **Portable lesson:** "everything-aggregator" framings provoke immediate political resistance even when the technical architecture is sound. Loomwork's frame must be specifically pro-accountability, with refusal categories explicit, or it triggers TIA-class backlash regardless of intent.

### OpenCorporates ([opencorporates.com](https://opencorporates.com))
Beneficial ownership data at scale. Survives via tiered access (free for journalists/researchers; paid API for commercial/enterprise). **Portable lesson:** the unit economics of corporate-data scraping at world-scale are difficult; tiered access works when paid users genuinely need machine-readable data. Loomwork-as-API-tier for partner orgs is a viable revenue model post-v2.

### Sayari Labs
Commercial OSINT consolidation. Reportedly grew through US-government contracts (Treasury/State/DOJ). **Portable lesson:** government-contract revenue creates capture risk for nonprofit work — Sayari serves who pays. Loomwork must explicitly refuse government-contract revenue (or accept only with strong editorial firewall).

### InfluenceMap ([influencemap.org](https://influencemap.org))
Corporate climate lobbying tracking. High-quality output, modest scale. **Portable lesson:** focused vertical with rigorous methodology can produce outsized influence per atom. Loomwork's pattern-classes (8 inference patterns from theory-of-change research) should be similarly focused.

### Snowden disclosures (2013-2014, via Greenwald/Poitras/Gellman)
Transformative impact: Section 215 bulk metadata collection ended (USA FREEDOM Act 2015); global encryption norms shifted; Snowden granted asylum in Russia. Failure modes: bulk surveillance largely unchanged structurally; Snowden personally captured; intra-source-team conflict (First Look Media drama). **Portable lesson:** journalist-collaboration with strong editorial process beats publication-only model; source protection is non-negotiable; even successful disclosure rarely produces structural rule change without pre-existing legal framework readiness.

### ICIJ predecessors (Center for Public Integrity, IRE, Pulitzer-funded individual investigations)
Built the network model that ICIJ formalized. **Portable lesson:** the cross-border consortium model required two decades of trust-building — Loomwork should not expect to build equivalent partner trust faster than 5+ years of consistent shipping.

### Center for Investigative Reporting → Reveal → CIR Studios
Multiple rebrands; podcast-and-documentary pivot. Successful in audience but not in fundamental new-tooling investment. **Portable lesson:** tooling investment is its own discipline; news orgs that try to build platforms typically don't, and platforms that try to do journalism dilute. Loomwork's discipline is platform; its content is partner-supplied.

### Aggregator platforms that died (general pattern)
Google Reader (2013), pre-Mastodon RSS readers, Diigo's social bookmarking, Storify's curation. **Portable lesson:** aggregators without a clear non-substitutable value proposition decay; Loomwork's typed atom layer + telos gates + cross-pollination engine is the non-substitutable layer.

---

## Section 3 — Adjacencies Loomwork Should Inherit From

### Wikipedia (governance, citation discipline, scale)
Wikipedia's governance evolved over 23 years from BDFL to elected board to Foundation governance. Edit-war resolution: discussion-page → mediation → arbitration committee. Citation discipline: WP:V (verifiability) and WP:RS (reliable sources) operationalized at scale. **Loomwork inherits:** explicit reliable-source policy; transparent edit-history; arbitration mechanism for atom disputes. **Loomwork rejects:** the deletionist-vs-inclusionist culture (Loomwork has explicit refusal architecture so deletion is principled, not factional); pseudonymous editing (Loomwork attestations are partner-org-signed, not pseudonymous).

### Wikidata (typed knowledge graph at scale)
Wikidata 2025 strategic direction ([Wikidata Development Plan 2025-2028](https://www.wikidata.org/wiki/Wikidata:Development_plan/Wikidata_2025-2028)) explicitly addresses **federated SPARQL** across Wikibase instances and **graph splitting** for scale (WikiCite split from main graph in 2025 — over 50% of triples). Their query service has hit Blazegraph scaling limits. **Loomwork inherits:** federated query model; explicit graph-split discipline at scale-band B4. **Loomwork rejects:** SPARQL-only access (too narrow for the cross-pollination layer); over-broad item creation policy (Loomwork atoms must pass telos gates).

### Schema.org (federation of typed objects)
Schema.org's success: minimal central authority, sponsored by major search engines, voluntary adoption. **Loomwork inherits:** typed-object schemas designed for federation from B0; conservative core schema with extension points; clear versioning. **Loomwork rejects:** the search-engine-centric design (Loomwork's audiences are journalists/NGOs/regulators, not search engines).

### Internet Archive (sovereignty against takedown)
Mirror network, multi-jurisdiction, consistent-takedown-policy publication. The 2024 hachette-vs-IA ruling shows the limits of fair-use defense for archival; **Loomwork's parallel risk** is libel and beneficial-owner privacy claims rather than copyright. **Loomwork inherits:** mirror network, multi-jurisdiction posture, transparent takedown policy with warrant-canary structure. **Loomwork rejects:** the "everything must be saved" maximalism — Loomwork's refusal architecture is constitutive.

### CourtListener / RECAP (community + legal data)
[CourtListener API](https://www.courtlistener.com/help/api/) makes federal court records queryable; RECAP browser extension liberates PACER documents into the public domain via volunteer contribution. **Loomwork inherits:** community-contribution to ingestion; clean separation of "public-domain document" from "Loomwork analysis"; clear API surface for downstream consumers. **Loomwork rejects:** US-only scope; volunteer-only pipeline (Loomwork is engine + community).

### C2PA / Adobe Content Authenticity (provenance)
[C2PA](https://c2pa.org) cryptographic content provenance; widely adopted by Adobe, Microsoft, OpenAI, Google. **Loomwork inherits:** C2PA for image/video atoms from day 1; signing with Loomwork's organizational key for published artifacts. **Loomwork rejects:** corporate-only governance — Loomwork's partner orgs need attestation paths.

### Tor / Signal (adversarial deployment context)
Tor's threat model: state-level adversaries, multi-jurisdictional. Signal's: device + user + protocol verification. **Loomwork inherits:** explicit adversarial-architecture from day 1 (covered in 03_adversarial_architecture.md when retried); operator security hygiene as documented norm; no single-point-of-failure for publication.

---

## Section 4 — Loomwork's Unique Position

### What only Loomwork claims to be

1. **Telos-gate-protected publication.** Palantir's Ontology has security policies (per-object, per-field, role-based) but no doctrinal telos gates. Bellingcat has editorial gates but they're personal-judgment, not formalized. Wikipedia has WP:NPOV but it's a community norm, not a publish-time check. **Loomwork uniquely operationalizes 7 publication-time telos gates: vulnerable-person, libel, citation-retrievability, disinformation-source, pramana provenance, confidence-floor, staleness.**

2. **Multi-evaluator decorrelation as a publishing constraint.** The Krogh-Vedelsby diversity term must be > 0 for `dot → revelation` promotion (≥3 evaluators from distinct model families with decorrelated errors). No comparable platform has this discipline. Single-model AI summarization is the norm; Loomwork rejects it as Brier-bad.

3. **Pramana provenance tagging.** Every claim tagged proxy / behavioral / geometric / documentary. Wikipedia's WP:V is binary (cited or not). Wikidata's references are typed but flat. Loomwork's pramana taxonomy is an explicit epistemic discipline — knowing what *kind* of evidence we have.

4. **Free-models-first economics.** GLM-5 (Ollama Cloud free tier) carries baseline; Sonnet only on edge cases. ~$60-200/mo at v0. Sayari/Recorded Future/Palantir charge $$$/seat — Loomwork's unit economics is incompatible with their capture model.

5. **Open-source substrate.** Code, schema, evaluator weights (eventually), revelation history all open. The platform itself is auditable. No commercial OSINT platform offers this; Wikidata and OCCRP partial.

6. **Akram-grounded contemplative spine as immune system.** This is genuinely unique. Witness/viveka/pramana/identity-coherence as runtime safety primitives, not philosophical decoration. The 7 telos gates are operationalizations of contemplative discrimination; the refusal architecture is operationalization of `mahakali`-class strike-function. **No comparable platform has a contemplative immune system; this is what prevents Loomwork from becoming weaponizable.**

7. **Outcome-engineering layer.** Audience multiplexer (≥3 artifact shapes per revelation), coordinated-drop infrastructure (Panama Papers model), named-target priority, legal-infrastructure registry. Per the theory-of-change research, this is the difference between Pandora ($76M outcome) and Panama ($1.36B outcome) — same data type, 18× different result. **No platform engineers for the revelation→outcome chain; existing platforms optimize atom→revelation.**

### Why Anthropic / Google / Palantir won't build this

- **Anthropic** is a lab, not a publication platform. Even if Anthropic built investigative tooling, the editorial-decision risk (libel, vulnerable-person exposure) is incompatible with their corporate posture; they'd need to spin out a new entity. Their constitutional-AI work is closer to telos gates than Loomwork's, but they're targeting model behavior, not platform behavior.

- **Google** is an advertising company; investigative tooling that exposes advertisers is a structural conflict. Search has been Google's core product; pattern-surfacing-in-public-revelation is competitive with that. Google's Jigsaw subsidiary funds journalism but doesn't build platforms.

- **Palantir** is the explicit antithesis. Their customer is governments and enterprises — entities Loomwork is structurally accountable AGAINST. A Palantir-for-civil-society would be an internal contradiction.

- **Meta / Apple / Microsoft** — none have the partner-org trust required, and all have advertiser/enterprise conflicts.

The moat is **partner-org trust + open-source substrate + telos-gate doctrine + contemplative immune system + outcome-engineering layer.** None of those is replicable by capital alone. Trust takes years; doctrine takes a tradition; immune systems require an architectural commitment Big Tech wouldn't make.

### What Dhyana brings that they don't

24 years of Akram contemplative practice → load-bearing telos discipline. R_V research lineage → architectural rigor for self-reference. dharma_swarm substrate already built (542 modules, 9882 tests, ontology.py self-declaring "Palantir reforged for Jagat Kalyan"). Solo operator with no shareholder/board capture vectors yet. **Bali base** removes some US-corporate-pressure surface (and adds different pressures, addressed in 03_adversarial_architecture).

---

## Section 5 — Honest Frontier Position

### Are we early, late, or on time?

**On time, leaning early.** The window:

- **Open:** AI tooling at 2026 capability is finally adequate to atomize world-data at scale and run multi-evaluator decorrelation at marginal cost. Pre-2024 this would have required $10M+/yr in compute. GLM-5/DeepSeek/Kimi free-tier inference makes the unit economics work for the first time.
- **Open:** civil society's appetite for AI-augmented investigation is rising (Bellingcat AI tools, ICIJ's Observatorio Transfronterizo de la Corrupción 2025, OCCRP investing in pattern platforms). The audience exists.
- **Open:** AI safety + AI welfare + alignment discourse provides intellectual cover for an Akram-grounded telos-gated platform; in 2018 this framing would have read as woo, in 2026 it reads as mainstream alignment work.
- **Closing risk:** Big Tech investigative-AI ventures could enter the space within 18-24 months once the unit economics become obvious to them. The window before commodification is 12-24 months.
- **Closing risk:** state-actor disinformation injection at LLM-fabrication scale is rising fast (covered in 03_adversarial_architecture); platforms not architected for this from day 1 will be poisoned.
- **Closing risk:** EU AI Act + similar regulation may impose compliance overhead that disadvantages new entrants vs incumbents.

**Strategic implication:** ship within 12 months at meaningful capability or risk losing the open window. The 14-day v0 + 90-day v1 trajectory is defensible against this clock.

### What kills the window?

1. **Trust capture event** — a Loomwork-class platform publishes a false revelation with reputational consequence; the entire category gets discredited. Mitigation: telos gates, multi-evaluator, conservative confidence floor, 35-65% political distribution discipline.

2. **State-actor disinformation breakthrough** — perfect deepfake-leak fabrication overwhelms verification. Mitigation: C2PA from day 1, partner-attestation chain, conservative source-diversity requirement.

3. **Big Tech enclosure** — Anthropic/Google/Microsoft launch competing product with subsidized economics. Mitigation: trust + doctrine + open-source moat (capital can't replicate trust on a 12-month timeline).

4. **Regulatory crackdown** — EU/UK SLAPP-style legislation against investigative-AI. Mitigation: jurisdiction architecture, fiscal sponsor structure, distributed mirror network from B2 onwards.

---

## Section 6 — Naming Recommendation

### Loomwork

Quick check on competitive collision (2026): the OSINT-tools listicles ([Lampyre 2026](https://lampyre.io/blog/top-paid-osint-tools-in-2025/), [ProjectOSINT 2026](https://projectosint.com/osint-market-2026-platforms-tools/), [ShadowDragon 2026](https://shadowdragon.io/blog/best-osint-tools/)) do not list a Loomwork — confirms no major existing platform under this name in the OSINT/investigative space.

**Strengths:**
- Cosmic-loom imagery (weaving threads, the metaphor literal to the platform's function)
- Verb extends naturally ("Loomwork wove…", "Loomwork's loom of…")
- Two syllables, hard consonants, easy in headlines
- Journalist-legible (no Sanskrit decoder ring required)
- Engine name `dharma_swarm` stays internal — Loomwork is the public skin
- **No detected collision** with active OSINT/investigative platforms in 2026

**Weaknesses:**
- "Loom" has fabric/textile primary association; some confusion at first read possible
- The work suffix is generic; "Loomwork" might be initially mis-read as a craft platform
- Corporate squatter risk on .com — verify before commitment

**Domain availability — must verify directly via registrar (this fork did not have ICANN/whois access):** Loomwork.com, Loomwork.org, Loomwork.ai. If any are taken (likely .com, possibly .org), fall back to alternatives below.

### Three alternatives if Loomwork has issues

1. **Plumbline** ([plumbline.com appears available since Plumbline Solutions renamed 2015](https://www.solomoncloudsolutions.com/plumbline-solutions.html); useplumb.com closed). Biblical "measure of truth" connotation; vision + correction. Strong for the accountability frame. Risk: small risk of confusion with Plumbline Innovations (not OSINT-related).

2. **Truestack**. Plain-English; conveys layered investigation. Risk: more generic, less memorable.

3. **Ariadne** (Greek mythology — the thread out of the labyrinth). Cosmic-thread imagery, classical-but-not-orientalist, journalist-legible. Risk: name has been used by various small projects (verify); Ariadne Labs (Harvard health) is the largest collision but a different domain.

**Hard-killed:** Constellate (collides with Constellate.ai + Constella.ai). Fathom (Fathom.io is active investigative-AI commercial). CrossWeave (defunct but trademark may be alive).

### Recommendation

**Lock Loomwork** pending domain verification. Backup: Plumbline. If both blocked, brainstorm a fresh option informed by the partner-launch list (whichever framing resonates with the first 5 NGO partner conversations).

---

## Notes for Parent

- Worker fork executed within ~5 WebSearch budget cap; deeper named-individual partner contact research was deferred to `06_partner_governance_funding.md` to avoid duplication and rate-limit re-trigger.
- Out-of-scope flag (one line, per directive): the chetana plugin load failure and bare-mode cron auth failures noted in the parent transcript are unrelated to this frontier-landscape research and remain unresolved separately.
- One file written: `/Users/dhyana/dharma_swarm/docs/loomwork/vision/01_frontier_landscape.md`. No commits made.
