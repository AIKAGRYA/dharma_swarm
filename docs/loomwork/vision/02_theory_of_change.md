# Loomwork — Theory of Change

**Author:** worker fork (research pass), 2026-05-07
**Status:** Vision research — level-100 articulation. No code commitments.
**Frame:** Loomwork's design at level 15 is "5 hand-crafted launch revelations on a local site." Level 100 is "durable, world-impact-causing platform." This document closes the gap between *publishing a revelation* and *moving a lever in the world*.

---

## Section 1 — The Causal Chain From Atom to World-Effect

A revelation does not become a world-state change by being true. It becomes a world-state change by surviving a long chain of conversion stages, each of which has a measurable failure rate. Loomwork's architecture must be designed against the *whole* chain, not the act of publishing.

### The chain

```
RAW SIGNAL
   │  acquisition gate (legal access, API quota, paywall, source trust)
   ▼
INGESTED ATOM
   │  atomization gate (typed schema fit, dedup, provenance preservation)
   ▼
LINKED ATOM
   │  link-detection gate (entity resolution, false-positive filter)
   ▼
DOT (provisional pattern)
   │  multi-evaluator promotion gate (decorrelated reviewer agreement)
   ▼
REVELATION (cited, telos-gated)
   │  publication gate (vulnerable-person, libel, citation, disinformation)
   ▼
DISTRIBUTED PUBLICATION
   │  attention gate (algorithmic amplification, journalist pickup, RSS pull)
   ▼
ACTOR-INGESTION
   │  comprehension gate (jargon, format, length, language, embargo state)
   ▼
ACTOR-DECISION
   │  capacity gate (legal standing, budget, jurisdiction, political cover)
   ▼
ACTOR-ACTION
   │  efficacy gate (response strategy of target, counter-narrative speed)
   ▼
OUTCOME
   │  durability gate (rule changes vs one-off prosecutions)
   ▼
WORLD-STATE CHANGE
```

### Conversion losses (estimated from real cases, with sources)

- **Raw → Ingested:** ICIJ's Panama Papers had **2.6 TB / 11.5M documents** ([Wikipedia](https://en.wikipedia.org/wiki/Panama_Papers)). Of those, only the subset with named beneficial owners and identifiable jurisdictions became the basis for stories. **Estimated 1-5%** of raw atoms ever reach a story.
- **Ingested → Revelation:** Investigations typically publish **dozens to hundreds** of stories from millions of documents. Conversion of atom→revelation is roughly **0.001-0.01%** by document count. Loomwork's conversion ratio is the most aggressive lever — automation can push this 100-1000× over manual investigation, BUT only if the multi-evaluator promotion gate is not gamed.
- **Revelation → Distributed reach:** ICIJ's Panama Papers reached 150+ media partners simultaneously ([ICIJ](https://www.icij.org/investigations/panama-papers/panama-papers-faq-all-you-need-to-know-about-the-2016-investigation/)). Pandora Papers had 600+ journalists across 117 countries. Reach without coordination is much lower — Snowden's individual disclosures hit different outlets at different times, fragmenting the news cycle.
- **Distributed → Actor decision:** **The actor-decision gate is the highest-loss link.** Panama Papers triggered Iceland PM Sigmundur Davíð Gunnlaugsson's resignation within **5 days** of publication ([Wikipedia](https://en.wikipedia.org/wiki/Panama_Papers)). Pandora Papers did not produce a single comparable resignation despite naming **more than twice the politicians** ([ICIJ](https://www.icij.org/investigations/pandora-papers/about-pandora-papers-leak-dataset/)). Same data type, very different outcome — the difference was political moment, target country composition, and cumulative-fatigue effects.
- **Actor decision → Outcome:** Panama Papers produced **$1.36B in tax recoveries** ([UK Fact Check](https://www.ukfactcheck.com/article/224/panama-papers-at-10-leak-linked-to-1-3bn-in-tax-recoveries-campaigners-say-loopholes-remain)). Pandora + Paradise combined produced about **$76.4M** (most of which was Spain alone) ([ICIJ](https://www.icij.org/investigations/panama-papers/hundreds-of-millions-more-dollars-recouped-by-governments-after-icij-investigations/)). **Roughly 18× difference in outcome conversion despite Pandora having more raw material.** This is the central design problem — *more atoms produce less outcome unless the publication moment is engineered.*
- **Outcome → Durable world change:** Panama Papers triggered legal reforms in multiple countries; UK's beneficial ownership register; EU AML directives. Snowden's leaks ended bulk metadata collection (USA FREEDOM Act 2015) but left bulk surveillance largely intact. Durable conversion of outcome→rule-change is the rarest stage and has the longest tail (years).

### What makes things stick (vs evaporate)

**Stick:**
- Cross-jurisdiction simultaneity (forces coordinated response)
- Embargo-coordinated drop (no first-mover dilution)
- Local-language prosecutorial-grade evidence packs (Bellingcat → JIT model)
- Pre-existing legal infrastructure ready to receive (USA FREEDOM, AMLD)
- Named individual targets (more actionable than systemic critiques)

**Evaporate:**
- Bulk-volume drops without selection (WikiLeaks Iraq War Logs)
- Fragmented coverage with no synchronicity (Pandora vs Panama)
- Systemic-only framing without named accountability targets (Exxon Knew)
- News-cycle competition with high-attention events
- Targets in jurisdictions with no enforcement capacity

**Loomwork design implication:** the primary engineering problem is not increasing the rate of atom→revelation. It is increasing the rate of revelation→outcome. This means *fewer, better-timed, coordinator-engaged* revelations, not more.

---

## Section 2 — Five Real Case Studies of Investigation → Outcome

### 2.1 Panama Papers (ICIJ, 2016)

**Dots connected:** Süddeutsche Zeitung received 2.6 TB / 11.5M documents from Mossack Fonseca. ICIJ shared with 376+ journalists across 100+ media organizations who cross-referenced offshore entity records against politicians, athletes, criminals, businesspeople ([Wikipedia](https://en.wikipedia.org/wiki/Panama_Papers)).

**Who acted:** National tax authorities (40+ countries opened investigations), prosecutors (Panama, Switzerland, Iceland raided Mossack Fonseca offices), parliaments (legal reforms in multiple countries), street protesters (Iceland: largest in Iceland's history → PM resignation in 5 days).

**Outcome:** $1.36B in tax recoveries, multiple resignations (Iceland PM, Spain Industry Minister, eventual UK PM Cameron pressure leading to disclosure of trust holdings), legal reforms in beneficial ownership transparency in UK / EU / US. Mossack Fonseca closed in 2018.

**Time:** Resignations in days. Tax recoveries over years. Legal reforms still flowing as of 10-year retrospective ([ICIJ](https://www.icij.org/investigations/panama-papers/ten-years-after-the-panama-papers-enablers-and-tax-cheats-are-still-being-brought-to-justice/)).

**Load-bearing mechanism (the THING that made this work, not the volume):**
1. **Coordinated embargo across 100+ outlets.** No single outlet had time advantage. The world-news cycle was overwhelmed simultaneously.
2. **Named-political-target framing.** Iceland's PM was named with specific entity ownership details. This is news, not abstract.
3. **Pre-existing legal infrastructure.** OECD's automatic-exchange-of-information frameworks were already negotiated. The leak provided *enforcement targets* for already-built legal machinery.
4. **Cross-jurisdiction overlap.** A name appearing in Spanish, German, and Brazilian datasets simultaneously triggered three separate national prosecutions — each one independently legitimate.

**What would have made it not work:** Sequential publication (one outlet after another), no political targets, no existing AML/AEoI infrastructure to receive the data, no cross-jurisdiction overlap.

### 2.2 Tobacco Master Settlement Agreement (1998)

**Dots connected:** Internal industry documents leaked by whistleblowers (Jeffrey Wigand, Merrell Williams) combined with state attorneys general's discovery in lawsuits. Documents proved tobacco companies internally knew about addictiveness and cancer links while publicly denying both ([Wikipedia](https://en.wikipedia.org/wiki/Tobacco_Master_Settlement_Agreement)).

**Who acted:** 46 state attorneys general coordinated, the District of Columbia, Puerto Rico, and Virgin Islands.

**Outcome:** $206 billion (initial 25-year commitment) → eventually $246B as of cumulative payments. Mandatory release of **40+ million pages** of previously confidential industry documents to the UCSF Industry Documents Library, restrictions on marketing to youth, dissolution of the Tobacco Institute.

**Time:** Negotiations took 4 years (1994 first lawsuits → 1998 MSA).

**Load-bearing mechanism:** State-level coordination was the multiplier. Any single state suing was beatable; 46 states acting in parallel was not. The leaked documents provided *common evidentiary basis* across all jurisdictions, eliminating the variance that defendants normally exploit.

**What would have made it not work:** No coordinated state AG action; documents released to academia rather than civil discovery (academic exposure has lower legal weight); single-state strategy.

### 2.3 Bellingcat MH17 Attribution (2014-2022)

**Dots connected:** Bellingcat used **publicly-posted social media imagery** (VK posts, geotagged photos) to track the specific Buk missile launcher (Buk 332, 53rd Anti-Aircraft Missile Brigade) from Russia into Ukraine, to the firing site, and back into Russia minus one missile ([CBS News 60 Minutes](https://www.cbsnews.com/news/how-bellingcat-tracked-a-russian-missile-system-in-ukraine-60-minutes-2020-02-23/), [Bellingcat](https://www.bellingcat.com/news/europe/2017/07/17/mh17-open-source-investigation-three-years-later/)).

**Who acted:** Joint Investigation Team (JIT, Dutch-led, with Australia, Belgium, Malaysia, Ukraine). The JIT's 25 May 2018 report independently confirmed Bellingcat's findings using intercepts, eyewitnesses, and forensics ([Bellingcat](https://www.bellingcat.com/resources/2023/03/28/how-open-source-evidence-was-upheld-in-a-human-rights-court/)). Dutch District Court convicted three defendants in absentia (2022).

**Outcome:** Russian state attribution; Dutch District Court conviction (2022); ECHR ruling on Russia's responsibility; sanctions; permanent attributional record.

**Time:** 3 years from investigation to JIT confirmation. 8 years to conviction.

**Load-bearing mechanism:** **Methodology-publishing transparency.** Bellingcat published its methods openly so the JIT and courts could independently reproduce the analysis. Open-source evidence's legal weight came from *reproducibility*, not authority. Loomwork must build for reproducibility from day one.

**What would have made it not work:** Closed methodology (would never have made it through Dutch evidentiary standards); no JIT counterpart willing to do the prosecutorial-grade work; investigation in a country with no capacity to extradite or prosecute.

### 2.4 Forensic Architecture's Grenfell Tower Analysis (2017-2024)

**Dots connected:** Forensic Architecture combined **public-uploaded video and photos** from the night of the fire with architectural plans, witness testimony, and material science to create a real-time interactive 3D model of how the fire spread through the cladding system ([Forensic Architecture](https://forensic-architecture.org/investigation/the-grenfell-tower-fire), [Right Livelihood](https://rightlivelihood.org/the-change-makers/find-a-laureate/forensic-architecture/)).

**Who acted:** UK Grenfell Tower Inquiry (Phase 1 2019, Phase 2 final report 2024); plaintiffs' legal teams (800 plaintiffs in one of the largest UK civil suits in history); Crown Prosecution Service (criminal investigations ongoing).

**Outcome:** Phase 2 Inquiry final report (2024) named systemic failures; building safety reforms (Building Safety Act 2022); ongoing criminal proceedings; cladding bans; **£15B+ in cladding remediation** committed by UK government and developers.

**Time:** 7 years to Phase 2 report. Reforms ongoing.

**Load-bearing mechanism:** **Counter-mapping the official narrative in court-admissible form.** When the government's initial framing emphasized resident behavior or appliance failure, Forensic Architecture's reconstructions made the cladding's role legible and undeniable. The 3D model became a teaching tool for the Inquiry itself. Loomwork's revelations should be designed to *equip the Inquiry that hasn't happened yet*.

**What would have made it not work:** Static reports rather than interactive simulations (Inquiry chairs need to walk through the evidence); no court-admissible methodology; no paired legal action team.

### 2.5 OCCRP Azerbaijani Laundromat (2017)

**Dots connected:** Banking records of $2.9B in transactions through four UK limited partnerships were leaked to Berlingske, who shared with OCCRP. OCCRP cross-referenced beneficial ownership against Azerbaijani regime figures, European politicians, and PACE delegates who'd voted on Azerbaijan resolutions ([OCCRP](https://www.occrp.org/en/project/the-azerbaijani-laundromat), [Wikipedia](https://en.wikipedia.org/wiki/Azerbaijani_laundromat)).

**Who acted:** Council of Europe (PACE independent investigation banned 14 former members from premises ([Transparency International](https://www.transparency.org/en/news/the-azerbaijani-laundromat-one-year-on-has-justice-been-served))); German prosecutors (multiple MP convictions); UK NCA (asset seizures).

**Outcome:** PACE leadership resignations within weeks; 14 banned from PACE premises; multiple national prosecutions; ongoing UK asset seizures; UK Unexplained Wealth Order reforms.

**Time:** Resignations in weeks. Convictions over years.

**Load-bearing mechanism:** **Linking financial flow to specific political votes.** OCCRP did not just publish "Azerbaijan launders money in Europe." They published "this politician received this payment 11 days before this PACE vote on Azerbaijan." The granularity of the payment-to-decision mapping made denial impossible. Loomwork must specialize in *temporal proximity patterns*, not just static ownership patterns.

**What would have made it not work:** No PACE-vote granularity (just a list of payments); no Transparency International coordinator pushing the institutional response; no German-prosecutor counterpart.

---

## Section 3 — When Investigation Does NOT Move the World

### 3.1 WikiLeaks Iraq War Logs (2010)

**391,832 SIGACTs** released. Documented previously unreported civilian casualties, torture handovers, contractor abuses. Limited US policy change. Why?

- **Volume without curation.** No one read 391,832 documents. Journalists cherry-picked; the cherry-picks were sub-stories.
- **No named-individual prosecutorial pathway.** Systemic abuses without specific named US-side defendants.
- **Source compromise dominated narrative.** Manning's prosecution and Assange's legal saga overshadowed the substance.
- **No coordinated outlet release.** Sequential publication fragmented attention.

**Loomwork lesson:** never publish in bulk without per-revelation curation. A revelation a week with a named target beats 50,000 atoms with none.

### 3.2 Snowden NSA Disclosures (2013-2014)

Bulk metadata collection ENDED via USA FREEDOM Act (June 2015) — that's a real outcome. But Section 702 surveillance, FISA Court secrecy, Five Eyes coordination, and most of the infrastructure remained intact and was reauthorized in 2018, 2024.

**Why partial:**
- Targets were US national-security agencies operating with broad public-safety legitimacy buffer
- The surveilled population (everyone) had no concentrated stake
- Counter-narrative (terrorism prevention) was institutionally pre-loaded
- Snowden himself became the story, displacing the substance in public attention

**Loomwork lesson:** when the abuse is *legible* (bulk metadata easy to explain), reform happens. When the abuse is *complex* (Section 702 vs Section 215), reform stalls. Loomwork must *engineer legibility*, not just accuracy.

### 3.3 Pandora Papers (2021) vs Panama Papers (2016)

Pandora had **more atoms, more outlets, more politicians** ([ICIJ](https://www.icij.org/investigations/pandora-papers/about-pandora-papers-leak-dataset/)) but produced a tiny fraction of the recoveries: **$76.4M (Pandora + Paradise combined) vs $1.36B (Panama)** ([ICIJ](https://www.icij.org/investigations/panama-papers/hundreds-of-millions-more-dollars-recouped-by-governments-after-icij-investigations/)).

**Why:**
- **Cumulative fatigue.** Public/political "offshore exposé" budget was spent.
- **Political-moment drift.** 2021 was COVID-saturated, attention-fragmented.
- **Target composition.** Fewer first-tier-democracy heads of state; more autocrats already insulated.
- **Pre-existing infrastructure was already deployed** — the second leak had less marginal value.
- **Shorter time since publication** — but the trajectory is still well below Panama's at the same age.

**Loomwork lesson:** repetition has diminishing returns. The N+1th investigation of the same pattern at the same scale produces less than the Nth. Loomwork must vary *pattern types* and *pressure points*, not just produce more of the same kind of revelation.

### 3.4 Carmichael / Adani Coal Mine

Decades of investigative coverage in Australia, India, environmental NGO reports, native title objections, traditional owner protests. Project went forward. First coal shipment 2021.

**Why:**
- Asymmetric financial commitment by the proponent overrode reputational damage
- Government-of-the-day political alignment (Queensland Labor → federal Coalition)
- Adani's parallel operations elsewhere insulated the company from project-specific reputation hits
- No legal vector existed (project was approved through formal channels)
- International capital boycotts (banks declining to finance) succeeded narrowly — Adani self-financed

**Loomwork lesson:** investigation cannot move what is structurally protected by deep-pocket commitment + political alignment. Loomwork must screen targets for *political/financial vulnerability*, not just *moral wrongness*. **A revelation aimed at an unmovable target is wasted material.**

### 3.5 Exxon Knew (2015)

Inside Climate News and the LA Times documented Exxon's internal climate research from the 1970s-80s alongside its public funding of climate denial. No policy reversal followed for years. Multiple state-AG investigations (NY, Massachusetts, others) launched but mostly stalled or settled narrowly. Exxon's stock price was unaffected medium-term.

**Why:**
- The fossil-fuel industry's political coalition was already mobilized to absorb such narratives
- The "knew but lied" framing required years of court process to translate into liability
- Climate denial as a political identity insulated supporters from evidence-based persuasion
- No criminal jeopardy for individual executives (statute of limitations had largely passed)

**Loomwork lesson:** revelations against industries with mobilized political defenses must be paired with active legal/regulatory counterparts ready to receive the evidence. **Publishing into a political vacuum produces a noise event, not a state change.**

### What Loomwork must NOT be

A bulk-volume aggregator with no curation. A systemic-critique generator without named-target translation. An academic record of injustice. A tool that publishes against unmovable targets and calls itself successful. **A noise machine.**

---

## Section 4 — The Audience-Action Theory

Loomwork's revelations only convert if they meet the right reader in the right format with the right ancillary scaffolding. Eight audiences:

### 4.1 Investigative journalists

**What they need:** primary-source citations, raw atoms downloadable, exclusivity windows (24-72h embargoes), named editorial contacts at Loomwork for follow-up. Format: structured JSON + human-readable narrative. Length: long-form is fine.

**Evidence:** ICIJ's Panama Papers model — 376 journalists got synchronized access with deep documentation. The synchronicity, not the volume, drove pickup.

**Loomwork action:** journalist-tier with embargoed access to revelations 24-48h before public release, with full atom-level downloadable provenance.

### 4.2 NGO advocacy directors

**What they need:** revelation framed within a campaign theory of change (this revelation supports *what next ask*?). Visual assets they can re-publish. One-page brief format. Translation pre-done into 3-5 working languages.

**Evidence:** Transparency International's role in Azerbaijani Laundromat — they didn't just receive OCCRP's revelations, they pre-built the policy-pressure campaign that received them.

**Loomwork action:** "Campaign Brief" companion artifact alongside each Tier-1 revelation — names target ask, lists relevant decision-makers, includes pre-translated press materials.

### 4.3 Public defenders / civil society lawyers

**What they need:** evidence-chain documentation, FRE 901 / similar admissibility metadata, expert-witness leads, cross-reference to existing case law. Format: legal-ready PDF with sealed metadata.

**Evidence:** Forensic Architecture's Grenfell work was admitted into the UK Inquiry because methodology was reproducible and metadata was preserved. ICIJ atoms have served as supporting evidence in 100+ legal proceedings.

**Loomwork action:** evidentiary-grade tier — every atom with cryptographic provenance, methodology documented, source chain preserved with hash anchors.

### 4.4 Regulators

**What they need:** jurisdiction-specific framing (US FTC vs EU DG-COMP vs UK CMA), pre-mapped applicable statutes, regulatory-deadline awareness, named compliance officers if applicable. Format: regulator-specific complaint draft.

**Evidence:** OCCRP's Methane work at Carbon Mapper / EDF feeds EPA enforcement queues directly. The regulator does not have time to translate journalism into regulatory action — they need pre-translated material.

**Loomwork action:** "Regulator Complaint Draft" companion — auto-generated from revelation, mapped to applicable statute and forum, ready to be filed by an appropriate party.

### 4.5 Politicians / parliamentary staffers

**What they need:** constituency-relevance hook, political-cover framing (bipartisan if possible), bullet-able talking points, scheduling-aware timing (committee hearing windows). Format: staffer brief, 2 pages max.

**Evidence:** Iceland's Panama Papers protests directly produced PM resignation because the political class had constituency cover to demand it. The same atoms in Russia produced no resignations because no constituency cover existed.

**Loomwork action:** "Political Brief" companion — maps revelation to constituencies, names staffers/committees with relevant jurisdiction, suggests question-for-the-record templates.

### 4.6 Activists / community organizers

**What they need:** local-language framing, social-media-ready assets, confrontation scripts (questions to ask at shareholder meetings, AGMs, town halls), action escalation ladder. Format: Telegram/Signal-ready short cards + image macros.

**Evidence:** Iceland's protest organizers used Panama Papers to generate signage and chants within 48h. The translation to embodied action was handled by local organizers with materials Loomwork-equivalent infrastructure pre-built.

**Loomwork action:** "Activist Card" tier — concise, image-ready, low-friction.

### 4.7 Markets

**What they need:** materiality assessment (does this revelation move the security price?), source-credibility signal, time-stamp precision (for short-selling timing), aggregate exposure mapping. Format: structured data for institutional consumption.

**Evidence:** Hindenburg-Adani 2023 short report. A research-backed revelation drove a $100B market-cap hit. Markets are extremely fast-acting when revelations are credibility-anchored.

**Loomwork action:** structured JSON-LD revelation feed with materiality tags. NOT to encourage short-selling — but to allow institutional ESG/risk processes to ingest. This is also the most morally complex audience and should have separate gating.

### 4.8 Citizens

**What they need:** local-language summary, 30-second comprehension, shareability, an action under 5 minutes (sign petition, contact MP, share). Format: web card + audio + video options.

**Evidence:** Snowden's most successful single artifact was Glenn Greenwald's Guardian video interview — a comprehensible-to-citizens 12-minute presentation. The 391,832-page Iraq War Logs had no equivalent.

**Loomwork action:** "Citizen Card" — bottom of the pyramid, accessible UI/UX.

### Cross-audience principle

Each audience needs *the same revelation in a different shape*. Loomwork's publisher must produce **N artifacts per revelation** (one per audience), not one. This is the multiplier on lever-movement.

---

## Section 5 — The Inference Architecture

What kinds of cross-source inferences actually move the world? Eight pattern classes, each with example, source-types, evaluator method, false-positive rate, action-trigger.

### 5.1 Hypocrisy patterns
**Example:** Methane Award Paradox — operator wins climate award while in top 10% of recurrent methane super-emitters.
**Source types:** ESG award databases × satellite plume data (Carbon Mapper, MethaneSAT) × annual reports.
**Evaluator method:** exact-string match on entity name + temporal-overlap of award-year with emission-year.
**False-positive rate:** Low (5-10%) if entity resolution is clean. High if name disambiguation fails.
**Action trigger:** journalist embarrassment story + investor letters.

### 5.2 Ownership patterns
**Example:** Panama Papers — politician owns offshore entity that owns shell that owns yacht.
**Source types:** corporate registries (Aleph, OpenCorporates) × leaked datasets × sanctions lists.
**Evaluator method:** entity graph traversal with ownership-chain evidence at each hop.
**False-positive rate:** Medium (15-25%) — common-name entity collisions are common.
**Action trigger:** tax authority + parliamentary inquiry + legal action.

### 5.3 Timing patterns
**Example:** Azerbaijani Laundromat — payment to politician 11 days before relevant PACE vote.
**Source types:** banking flow data × legislative voting records × calendar/scheduling data.
**Evaluator method:** temporal-window correlation with statistical significance against null distribution of unrelated payments.
**False-positive rate:** Medium (20-30%) — coincidental timing happens; Loomwork must report effect sizes, not just hits.
**Action trigger:** ethics committee + criminal prosecution + sanctions.

### 5.4 Convergence patterns (most novel and hardest)
**Example:** 5 weak signals (factory complaint, supply chain anomaly, ex-employee LinkedIn, port AIS gap, customs declaration mismatch) converging on a forced-labor facility.
**Source types:** any 3+ heterogeneous sources, none alone sufficient.
**Evaluator method:** Bayesian aggregation with explicit prior and evidence-weight per source.
**False-positive rate:** High (30-50%) without careful prior calibration. THIS IS WHERE LOOMWORK ADDS UNIQUE VALUE — single-source investigators can't produce this; only multi-source orchestrators can.
**Action trigger:** investigative deep-dive (paired with journalist) + supply-chain audit demand.

### 5.5 Contradiction patterns
**Example:** Exxon Knew — internal documents asserting climate science vs external publicity asserting denial.
**Source types:** internal-document leak × public-statement archive (annual reports, CEO speeches, lobbying filings).
**Evaluator method:** semantic contradiction detection with claim-level pairing.
**False-positive rate:** Low (5-15%) — direct contradictions are unambiguous.
**Action trigger:** litigation (especially securities-fraud), shareholder activism.

### 5.6 Geographic patterns
**Example:** PADDD-then-Deforestation — protected area downgraded, forest loss alerts within 30 days.
**Source types:** PADDD database × GFW DIST-ALERT × concession registries.
**Evaluator method:** geospatial overlap + temporal sequence + concession-holder-attribution.
**False-positive rate:** Low-medium (10-20%).
**Action trigger:** indigenous-monitor mobilization + media + international donor pressure.

### 5.7 Network patterns
**Example:** Same beneficial owner across 12 sanctioned shell companies, plus one publicly-traded entity that's not yet sanctioned.
**Source types:** beneficial-ownership registries × sanctions lists × stock filings.
**Evaluator method:** graph-centrality measures + community detection + edge-implausibility scoring.
**False-positive rate:** Medium (20-40%) — entity disambiguation is hard at network scale.
**Action trigger:** OFAC designation expansion + financial-institution KYC enforcement.

### 5.8 Temporal patterns
**Example:** Recurrent methane super-emitter — same facility crosses threshold 4× in 12 months despite 2 prior repair claims.
**Source types:** repeated satellite passes × repair/maintenance filings × regulatory filings.
**Evaluator method:** repetition counting + repair-claim verification + escalation-pattern detection.
**False-positive rate:** Very low (< 5%) — repeated detection at same coordinates is unambiguous.
**Action trigger:** EPA/regulator enforcement + media accountability story.

### Pattern-mix design

Loomwork's revelation portfolio should rotate across pattern types. Diminishing returns of any single pattern type (per Pandora analysis) means **diversity of inference type is itself a moat**. A platform that produces Hypocrisy + Network + Convergence revelations alternately is harder to fatigue or counter-narrative-ize than one that produces only Hypocrisy.

---

## Section 6 — The Honesty Architecture

The failure mode that ends Loomwork is not technical. It is **becoming the noise it claims to filter** — producing 1000 revelations a week at 80% accuracy, getting weaponized by whichever side cherry-picks. Seven mechanisms must compose:

### 6.1 Claim-vs-evidence separation (pramana tagging)

Every claim in every revelation tagged as one of: `documentary` (cited primary source), `behavioral` (observed pattern), `geometric` (statistical inference), `proxy` (correlate, not cause). Tier mismatches between claim level and evidence level are the most common honesty failure.

### 6.2 Confidence floor

A revelation with computed confidence below threshold (proposed: 0.85 on multi-evaluator consensus) does not publish — it remains a `dot`, not a `revelation`. The non-publication is itself logged so the system maintains an audit trail of "things we almost said."

### 6.3 Multi-evaluator decorrelation (Krogh-Vedelsby)

Each promotion from `dot` to `revelation` requires ≥3 evaluators from genuinely-different model families (e.g., GLM-5 + Claude + Gemini), checked for error-decorrelation against historical baseline. If diversity term collapses to zero (evaluators agreeing for the same reason), the revelation is held even if all three agree.

### 6.4 Adversarial review

External red team (paid or volunteer investigative-journalism contributors) reviews a sample of revelations pre-publication. Reviewer reputation is tracked across reviews; high-disagreement revelations get held. This is the human-in-the-loop layer that synthetic evaluation alone cannot replace.

### 6.5 Algedonic feedback

Reader-flagged inaccuracies trigger immediate auto-retraction pending review. Retraction rate is published as a public metric. The system's *willingness to retract* is the trust signal.

### 6.6 Source diversity requirements

No revelation publishes from a single source. No revelation publishes from sources that could plausibly share an upstream manipulator (e.g., two NGOs both funded by the same intelligence-adjacent foundation). Source-overlap detection is a publication gate.

### 6.7 Source-watch on the sources

Loomwork itself must monitor *who is feeding it*. Upstream PSYOPS exists. Loomwork must detect when its inputs are themselves being shaped — e.g., a leak that conveniently appears on the eve of an unrelated political event. Detection method: timing-anomaly scoring of incoming feeds against base rates.

### Avoiding the weaponization failure mode

The structural answer: **Loomwork commits to publishing revelations against its own coalition.** If 100% of revelations in a quarter target politically-aligned actors (one direction), the system has been captured. A published metric of "target political distribution" with explicit 35-65% bounds creates self-corrective pressure. This is uncomfortable but non-negotiable for legitimacy.

---

## Section 7 — When Loomwork Should Refuse

Some technically-true patterns should not publish. Refusal is a feature, not a failure.

### 7.1 Vulnerable-person exposure

Refugees, undercover labor organizers, defectors, witnesses, undocumented workers — never published with identifying details, even if technically aggregable from other sources. Loomwork's publication act cannot enable harm even where the *information* is technically already accessible.

### 7.2 Active investigation interference

When law enforcement, journalism, or NGO investigators are working a target and publication would compromise their access — Loomwork delays. Coordination with named investigative bodies (OCCRP, ICIJ, Bellingcat) becomes a refusal channel.

### 7.3 State-actor target lists

Names of dissidents, journalists, activists in countries that may use Loomwork's pattern-detection capability against them. Loomwork must detect when its outputs would functionally be intelligence products for hostile states and refuse those queries / publications.

### 7.4 Intimate-relationship details unrelated to power

A senator's tax fraud is publishable. A senator's marital affair is not, unless it directly evidences a power abuse (e.g., exchange of policy for sexual favor). Default: intimate is private; only abuse-of-power exception applies.

### 7.5 Ethnic/racial profiling patterns

Pattern-finding within demographic categories that could fuel collective stigma. Even if statistically valid, Loomwork must refuse to publish "pattern X is more common in group Y" framings. Statistical validity does not equal moral admissibility.

### 7.6 Medical condition exposure

Health conditions of named individuals — never published unless they directly evidence policy-making fitness or fraud (e.g., a director claiming illness while attending a rally). Default refusal.

### 7.7 Religious surveillance patterns

Patterns about specific religious-community behavior that could fuel surveillance/discrimination. Same logic as 7.5.

### 7.8 Civilian collateral in conflict reporting

When investigation of a conflict-zone event would identify civilians as targets through inference — Loomwork refuses the inference even if the data permits it.

### Refusal transparency (the warrant-canary equivalent)

Loomwork publishes a quarterly **Refusal Report**:

- Aggregate count of revelations refused (no specifics)
- Distribution of refusal categories (vulnerable-person / active-investigation / state-actor / intimate / profiling / medical / religious / civilian-collateral / other)
- Number of state-actor requests received (explicit warrant canary)
- Number of legal threats received and how each was resolved

If the Refusal Report stops publishing, or if the state-actor count drops to zero unexpectedly, downstream consumers know something has changed. This is the structural integrity check that survives even if individual editorial judgment is compromised.

### Refusal as design discipline

A Loomwork that publishes 100% of what it can aggregate is captured. A Loomwork that publishes 60% of what it can aggregate is exercising judgment. The refusal rate itself is a quality signal — it should be visible, audited, and defended.

---

## Closing — Why Level 100 Looks Different from Level 15

Level 15 ships 5 hand-crafted revelations on a localhost site. The substrate is real, the engine works, the demo is meaningful. But the chain from atom to world-state-change has 11 conversion stages, and the demo only proves the first 6.

Level 100 architects against the *whole* chain:

- **Section 1** — Loomwork is engineered for revelation→outcome conversion, not atom→revelation conversion.
- **Section 2** — Models the case studies that produced $1B+ outcomes (Panama, MSA, Bellingcat, Forensic Architecture, OCCRP) and learns from each load-bearing mechanism.
- **Section 3** — Avoids the patterns that produce zero outcomes (WikiLeaks-bulk, Snowden-fragmentation, Pandora-fatigue, Carmichael-target-immunity, Exxon-political-vacuum).
- **Section 4** — Produces N audience-specific artifacts per revelation (journalist + NGO + lawyer + regulator + politician + activist + market + citizen).
- **Section 5** — Specializes in inference types nobody else produces (especially Convergence patterns), rotating across pattern classes to avoid fatigue.
- **Section 6** — Composes 7 honesty mechanisms; commits to political-distribution publication discipline.
- **Section 7** — Refuses 8 publication categories as design discipline; publishes the Refusal Report.

The world doesn't need more atoms. It needs **engineered conversions of the few atoms that already exist into the world-state changes they imply.** Loomwork's level-100 ambition is to be the first system that makes this conversion legible, repeatable, and auditable — Palantir's pattern reforged for Jagat Kalyan, with the seventh pillar of *honest refusal* that no commercial intelligence platform can offer.

---

**Sources cited inline:** [Panama Papers Wikipedia](https://en.wikipedia.org/wiki/Panama_Papers), [ICIJ Panama Papers FAQ](https://www.icij.org/investigations/panama-papers/panama-papers-faq-all-you-need-to-know-about-the-2016-investigation/), [ICIJ tax recoveries article](https://www.icij.org/investigations/panama-papers/hundreds-of-millions-more-dollars-recouped-by-governments-after-icij-investigations/), [ICIJ ten-year retrospective](https://www.icij.org/investigations/panama-papers/ten-years-after-the-panama-papers-enablers-and-tax-cheats-are-still-being-brought-to-justice/), [UK Fact Check Panama at 10](https://www.ukfactcheck.com/article/224/panama-papers-at-10-leak-linked-to-1-3bn-in-tax-recoveries-campaigners-say-loopholes-remain), [ICIJ Pandora Papers dataset](https://www.icij.org/investigations/pandora-papers/about-pandora-papers-leak-dataset/), [Bellingcat MH17 three years later](https://www.bellingcat.com/news/europe/2017/07/17/mh17-open-source-investigation-three-years-later/), [Bellingcat ECHR open-source evidence](https://www.bellingcat.com/resources/2023/03/28/how-open-source-evidence-was-upheld-in-a-human-rights-court/), [CBS News 60 Minutes Bellingcat](https://www.cbsnews.com/news/how-bellingcat-tracked-a-russian-missile-system-in-ukraine-60-minutes-2020-02-23/), [OCCRP Azerbaijani Laundromat project](https://www.occrp.org/en/project/the-azerbaijani-laundromat), [Wikipedia Azerbaijani Laundromat](https://en.wikipedia.org/wiki/Azerbaijani_laundromat), [Transparency International Laundromat retrospective](https://www.transparency.org/en/news/the-azerbaijani-laundromat-one-year-on-has-justice-been-served), [Wikipedia TMSA](https://en.wikipedia.org/wiki/Tobacco_Master_Settlement_Agreement), [Forensic Architecture Grenfell investigation](https://forensic-architecture.org/investigation/the-grenfell-tower-fire), [Right Livelihood on Forensic Architecture](https://rightlivelihood.org/the-change-makers/find-a-laureate/forensic-architecture/).

*End of Section 7. ~5,200 words. Worker fork stops here.*
