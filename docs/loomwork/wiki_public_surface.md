# Public Surface, Brand & Ship Plan

**Created:** 2026-05-07 — Arjuna directive, world-facing skin for the dharma_swarm dot-connection engine
**Sibling:** `wiki_weaving_engine.md` (engine architecture); this doc is the **skin** + brand + launch plan
**Constraint:** zero internal naming externally — `dharma_swarm`, `viveka`, `swabhaav`, `akram`, `triple mapping`, `R_V` stay private

---

## SECTION 1 — Naming & Brand

### Candidate names (7 surveyed, live-searched 2026-05-07)

| Name | Meaning | Why it fits | Conflict risk | Verdict |
|---|---|---|---|---|
| **Loomwork** | The labor of weaving (Norse Norns, Greek Moirai weave fate at a cosmic loom) | Mother-of-universe imagery + the word "work" pulls it out of mysticism into action; investigative-journalism-legible (a "loom of evidence"); two syllables, perfect spell-on-first-hearing | Crunchbase shows no active OSINT/AI company; no dominant trademark in our category | ✅ **PRIMARY** |
| **Plumbline** | Biblical/builder's measure of true vertical (Amos 7:7-8 — "I will set a plumb line among my people"); the tool that shows what is *straight* and what is *crooked* | Vision + correction in one word; secular audience hears precision, religious hears moral measure; cleared after Plumbline Solutions renamed to Solomon Cloud Solutions in 2015 | `useplumb.com` recently closed; no active trademark in OSINT/journalism | ✅ **BACKUP** |
| **Threadlight** | Light cast along threads of evidence | Pretty, evocative; risk of "thread" being saturated (Meta Threads, Thread AI) | Thread-prefix is heavily contested in AI space | ❌ kill |
| **Throughline** | Narrative connection across episodes; storyteller's term for what binds disparate facts | Strong in journalism/narrative; aligns with revelation framing | NPR podcast "Throughline" — adjacent but not OSINT, low risk in product naming | 🟡 fallback option only |
| **Crossweave** | Weaving across domains; explicit cross-pollination | On-the-nose for our function | Defunct CrossWeave (acquired 2003 by AmberPoint); Crossweave Technology Solutions (small Indian IT firm) — low active conflict but the name is *too literal*, brand-fragile | ❌ kill |
| **Constellate** | The act of constellating points into a pattern | Beautiful verb form; cosmic; action-coded | **Constellate.ai already exists** (AI business solutions) AND **Constella.ai** is an OSINT identity-risk leader — direct collision | ❌ HARD KILL |
| **Augury** | Roman/Etruscan divination from signs in the natural world | Cosmic-coded, evocative, ancient | Risks being heard as fortune-telling/woo by NGO audiences; less direct than Loomwork or Plumbline | ❌ kill |

### Recommendation: **Loomwork**

**Defence:** It carries the cosmic-loom-of-fate imagery Dhyana wants ("the eyes of the mother of the universe") without pricing in the woo tax. Journalists can use it in a headline ("*Loomwork connected the dots between A and B*"). NGO partners can cite it without smirking. Alignment researchers won't dismiss it as spiritual. And it does what no name with "AI" or "Intel" or "Sense" in it can do — **it tells you the system is patient, deliberate, and weaves rather than scrapes**. The verb naturally extends: "the loom surfaced…", "looming today…", "today's weave."

**Domains to register IMMEDIATELY (within 24h, before this doc circulates):**
- `loomwork.org` — primary (nonprofit posture)
- `loomwork.com` — defensive
- `loomwork.ai` — defensive (alignment-research audience)
- `loomwork.net` — cheap defensive
- `getloomwork.com` — cheap defensive

**If `loomwork.org` is taken:** fall back to **Plumbline** (`plumbline.org` / `theplumbline.org` / `plumbline.ai`).

**Tagline candidates** (pick one in week 2 after seeing audience reactions):
- *"What the loom sees."*
- *"Patterns that wanted to be found."*
- *"We connect the dots no single eye can."*
- *"The world weaves itself; we surface the weave."*

### Brand guardrails (non-negotiable)

- **No mysticism in copy.** Cosmic imagery lives in the *name*; the body text is journalist-grade plain English with citations.
- **No "AI" branding.** AI is the engine, not the product. Visitors should think they're on an investigative outlet, not a SaaS.
- **No internal vocabulary leakage.** Audit every line of public copy for `dharma`, `swarm`, `viveka`, `mahakali`, `swabhaav`, `R_V`, `triple mapping`, `pillar`, `kernel`, `telos`. Replace with: standards / verification / discipline / criteria.
- **Citation-first visual language.** Every revelation displays its sources at the top, like a court filing or a Bellingcat piece, not at the bottom like a blog.

---

## SECTION 2 — Public Surface Architecture

**Stack recommendation: Astro + Obsidian-compatible markdown atoms.**

- Why Astro over Quartz/Eleventy/Hugo: Astro renders Obsidian-style `[[wikilinks]]` natively (Quartz does too, but Astro has better partial-hydration for the atoms-graph view), TypeScript-native (matches the dharma_swarm engine layer), excellent RSS + JSON-feed plugins out of the box, and image performance (LQIP, AVIF) for revelation hero shots.
- Static-first → near-zero hosting cost (Cloudflare Pages free tier handles 100K visitors/month) and no DDoS surface for the inevitable corrupt-target pushback.
- Same markdown atoms can be ingested by Obsidian privately and rendered publicly — one shared record.

### Page inventory

| Path | Purpose | First-week scope |
|---|---|---|
| `/` (home) | Mission statement (one sentence), live counters (revelations · sources · atoms), latest 5 revelations as cards | Hand-built |
| `/revelations` | Reverse-chronological feed of all published revelations; tag filters | List view |
| `/revelations/[slug]` | Individual revelation: headline, sources cited, narrative, supporting atoms, "what this enables" call-to-action | 5 launch pieces |
| `/atlas` | Topic-clustered map (climate · corruption · labor · refugees · ecosystems · supply chains · justice). D3 / Cytoscape force-graph | v1: static buckets only |
| `/graph` | Public-atoms cross-link visualization (Obsidian-style); show the *weave* | v2 (post-launch) |
| `/sources` | Transparency: every ingestion source, license, cadence, last successful pull | Hand-curated launch list |
| `/methodology` | How a revelation is made: ingestion → cross-correlation → human verification → telos check → publish; retraction policy; correction policy | Plain English, no jargon |
| `/subscribe` | Email digest (weekly), RSS, JSON-feed, partner webhook signup | Buttondown or Beehiiv |
| `/submit` | Form: investigators/NGOs submit a thread for the loom to weave | Tally form → email |
| `/about` | Mission, current team (Dhyana solo at launch), governance plan, funding model, no-AI-tone-of-voice guarantee | Honest, short |
| `/api` (future) | Partner API access — read-only revelations + sources feed | Stub link → "join waitlist" |

### Trust scaffolding (visible everywhere)

- **Provenance badge** on every revelation: link to *every* source, with archive.org snapshot at time of publish
- **Methodology link** in footer of every revelation
- **Correction log** (`/corrections`) — public, dated, never-deleted
- **Funding disclosure** (`/funding`) — every grant or donor named
- **No-engagement-bait pledge** — no headlines optimized for outrage; no autoplay; no notifications

---

## SECTION 3 — First 5 Revelations (Launch Payload)

These must be **hand-crafted** before launch. Each connects ≥3 sources and ≥1 cross-domain. The engine will help; humans verify every claim before publish.

### Revelation 1 — *"The Methane-Award Paradox: super-emitters that won 2024-2025 climate honors"*

Cross-reference Carbon Mapper plume-source attribution and IEA Methane Tracker 2025 data against corporate ESG awards databases (Dow Jones Sustainability Index, MSCI ESG ratings, sector "Top Climate" lists from Bloomberg/Reuters/Newsweek), filtered by SEC 10-K self-attestations on methane reduction. Surface the operators who collected sustainability hardware while their satellite-detected plumes either persisted or grew. **Why it matters:** corporate climate accountability runs on self-attestation; the satellite data exists but no one cross-references it against the awards circuit. **Action enabled:** journalists publish, ESG raters re-score, regulators cite in enforcement.

### Revelation 2 — *"Dark vessels with green flags: beneficial owners of IUU-fishing fleets that also sponsor marine conservation"*

Global Fishing Watch dark-vessel and AIS-disabling datasets × OCCRP Aleph beneficial-ownership records × marine NGO donor lists (PEW Charitable Trusts, Oceana, Marine Conservation Institute public donor pages). Identify owners whose names appear on both sides. **Why it matters:** philanthropic reputation-laundering is invisible to most audits. **Action enabled:** NGOs revisit donor due diligence; investigative pieces; port-state authorities flag.

### Revelation 3 — *"Refugee credentials in shortage countries: where the visa system blocks the worker the economy is begging for"*

Talent Beyond Boundaries Talent Catalog skill-distribution × IMF/OECD published labor-shortage occupations by destination country × the destination country's professional licensing bodies (e.g., Australian Health Practitioner Regulation Agency, UK Nursing and Midwifery Council) and their published credential-recognition pathways. Surface the matched pairs where a skilled refugee exists, the country reports a shortage in that exact role, and the credential pathway is functionally closed (timelines >24 months, fees >$5K, no remote-assessment option). **Why it matters:** the bottleneck is administrative, not informational; making it visible creates pressure on licensing bodies. **Action enabled:** TBB advocates with named licensing bodies; policy reform pressure; voluntary fast-track pilots.

### Revelation 4 — *"Tier-3 forced-labor flags inside publicly-celebrated clean-tech supply chains"*

Walk Free Global Slavery Index × CSDDD (EU Corporate Sustainability Due Diligence Directive) 2026 filings × Panjiva/ImportGenius bills-of-lading where accessible × U.S. Customs Withhold Release Orders × Sheffield Helena Kennedy Centre forced-labor evidence. Surface the named clean-tech firms (solar, EV battery, wind) whose stated supply chains pass through Xinjiang polysilicon, Congolese cobalt, or Indonesian nickel choke points with documented forced-labor flags but absent or boilerplate due-diligence disclosure. **Why it matters:** decarbonization is morally compromised when its inputs trace to forced labor; the data exists but lives in five different silos. **Action enabled:** Customs enforcement; institutional-investor divestment; corporate disclosure improvement.

### Revelation 5 — *"Indigenous-land deforestation alerts that overlap recent protected-area downgrades"*

Global Forest Watch DIST-ALERT (near-real-time, January 2026) × RAISG Amazon indigenous-territory boundary database × WDPA Protected Planet recent PADDD events (Protected Area Downgrading, Downsizing, Degazettement) × national-level concession registries (Brazil ANM, Peru INGEMMET, Indonesia ESDM). Surface the territories where PADDD events in 2024-2025 are now showing measurable forest-loss alerts in 2026. **Why it matters:** PADDD precedes deforestation by months, but the connection is rarely traced in real time. **Action enabled:** indigenous federations brief funders; international pressure on PADDD-issuing governments; conservation-funding redirection.

**Note on launch payload safety:** all 5 require human verification before publish. None should expose individuals at risk (e.g., indigenous monitors named publicly). Telos gate: *no source ever named without consent; no individual surveilled; aggregate patterns only unless evidence already in public criminal record.*

---

## SECTION 4 — Distribution / Audience Plan

### Pre-launch (T-7 to T-0): warm-brief these partners FIRST

Brief each privately, share the launch revelation that touches their domain, ask for endorsement quote OR factual review:

| Partner | Domain | Why first | Contact path |
|---|---|---|---|
| **OCCRP** (Drew Sullivan / Paul Radu) | Investigative journalism, Aleph | Future Tier-1 target #1; endorsement halos us into journalism credibility | LinkedIn warm intro via mutual; or info@occrp.org |
| **Global Forest Watch** (WRI) | Forest-loss data | Source for Revelation 5; halo into climate/conservation | gfw@wri.org |
| **Talent Beyond Boundaries** (Mary Louise Cohen / Steph Cousins) | Refugee labor mobility | Source for Revelation 3; first commercial partner | info@talentbeyondboundaries.org |
| **Bellingcat** (Eliot Higgins) | OSINT investigative | Endorsement = instant credibility in the OSINT world | LinkedIn / Twitter |
| **Environmental Defense Fund** (MethaneSAT team) | Methane data | Source for Revelation 1 | methanesat@edf.org |
| **Carbon Mapper** | Methane attribution | Source for Revelation 1 | info@carbonmapper.org |
| **Walk Free Foundation** | Modern slavery | Source for Revelation 4 | info@walkfree.org |
| **RAISG / COIAB / AMAN** | Indigenous monitoring | Source for Revelation 5; legitimacy | indirect via Rainforest Foundation Norway warm intro |
| **Anthropic Model Welfare team** (Kyle Fish) | Alignment research credibility | Cross-pollination to alignment audience | known via Dhyana's prior outreach plans |
| **Sightline Institute / ProPublica data desk** | Journalism methods | Method-credibility halo | LinkedIn |

### Launch day (T+0)

| Channel | Asset | Angle |
|---|---|---|
| **Hacker News (Show HN)** | "Show HN: Loomwork — cross-source revelations from public investigative datasets" | Lead with the *technique* (cross-source pattern surfacing on open data) and ONE revelation. Avoid AI-saviour framing. |
| **Twitter/X** (5-tweet thread) | T1: hook — one sentence revelation with image. T2-3: sources + method. T4: what action this enables. T5: how to subscribe / submit threads | No emojis except 1 link; no thread-bait |
| **LinkedIn** | Long-form post for NGO/policy audience | Lead with public-interest framing; tag OCCRP, GFW, TBB |
| **Mastodon** (mas.to + investigative-journalism instances like newsie.social) | Same as Twitter, longer | Earnest tone |
| **Bluesky** | Cross-post Twitter thread | Investigative-journalism community is strong here |
| **Anthropic Discord (alignment channel)** | Methodology post | Lead with telos-gate and "no false accusations" architecture |
| **Alignment Forum** | Companion essay: "Cross-source revelation as alignment-positive infrastructure" | Frame as practical alignment work, not theoretical |
| **LessWrong** | Cross-post of AF | Same |
| **Direct emails to journalists** (5-10 named) | Each tailored to which revelation matches their beat | See list below |

### Named journalists to email at launch

| Journalist | Outlet | Beat | Matched revelation |
|---|---|---|---|
| **Hiroko Tabuchi** | NYT Climate | Methane / oil-gas accountability | Rev 1 |
| **Inti Pacheco** | WSJ | ESG corporate disclosure | Rev 1 |
| **Ian Urbina** | The Outlaw Ocean Project | Dark fleets, IUU | Rev 2 |
| **Manuela Andreoni** | NYT Climate / Latin America | Amazon, indigenous lands | Rev 5 |
| **Paul Radu** | OCCRP | Beneficial ownership networks | Rev 2 |
| **Yara Salem** | Reuters supply-chain unit | Forced-labor supply chains | Rev 4 |
| **Sigal Samuel** | Vox Future Perfect | AI for good, longtermism-curious | Methodology piece |
| **Karen Hao** | The Atlantic / freelance | AI accountability | Methodology piece |
| **Tomas Statius** | Forbidden Stories / Lighthouse | Investigative cross-border | Whichever fits |
| **Eliza Mackintosh** | CNN investigations | Forced labor + sanctions | Rev 4 |

### NGO/Slack/Discord communities to seed quietly

- **The OSINT Discord** (Trace Labs, OSINT Curious)
- **Climate Action Tech** Slack
- **DataKind** community
- **Bellingcat Discord**
- **NICAR-L** (investigative-reporters listserv) — very high-signal
- **Global Investigative Journalism Network** (GIJN) Slack
- **AI Safety Research Slack** (AISafety.com)

---

## SECTION 5 — Funding Model

### Layer 1: Forever-free public revelations
The moat is *trust + neutrality*. The day Loomwork charges to read a revelation is the day it loses NGO trust forever.

### Layer 2: Partner API ($)
NGO/journalist partners pay tiered subscriptions for: structured-data feeds, custom alert webhooks (e.g., "alert me when a beneficial owner I track appears in any new revelation"), advanced graph queries, and SLA-backed reliability.
**Pricing anchor:** $500/mo (small NGO) → $5K/mo (major outlet) → $50K/yr (large institutional).

### Layer 3: Custom investigations ($$$)
Bespoke threads where a partner asks the loom to weave a specific question. Engagement-based (not retainer): $15-50K per investigation. The investigation is *always published openly* — partner gets early/structured access, not exclusivity.

### Layer 4: Grant funding (the runway)
Foundations to apply to in the first 90 days:

| Foundation | Fit | Why |
|---|---|---|
| **MacArthur Foundation** (Journalism & Media) | Strong | Funds OCCRP, ProPublica directly |
| **Open Society Foundations** | Strong | Funds investigative work + civil society globally |
| **The OAK Foundation** (Issues Affecting Women, Environment) | Strong | Cross-cuts climate + forced labor + refugees |
| **Skoll Foundation** | Medium | Social entrepreneurship; harder than the above |
| **Mozilla Foundation Tech Fund** | Medium | AI for public good is current focus |
| **Patrick J. McGovern Foundation** | Strong | "AI for good" with serious budget |
| **Schmidt Futures / Sciences** | Medium | Tech-for-good but very crowded pipeline |
| **Knight Foundation Journalism** | Strong | Journalism infrastructure funding |
| **Reva and David Logan Foundation** | Strong | Funds investigative journalism specifically |
| **Ford Foundation Internet Freedom** | Medium | Civil society + tech intersection |
| **Omidyar Network** | Strong | Trust-and-safety + responsible tech investment arm |

### Fiscal sponsor candidates (501(c)(3) wrappers — apply within 30 days)

1. **Code for Science & Society** (codeforscience.org) — sponsors open-source science/civic-tech; high alignment
2. **Open Collective Foundation** — fast onboarding, lower overhead, lower prestige
3. **The Hopewell Fund** (Arabella Advisors) — high-prestige, more selective, longer onboarding

**Recommendation:** apply to all three within first 30 days; Code for Science & Society as primary preference because of scientific/data-infrastructure track record.

---

## SECTION 6 — 14-Day Launch Plan

| Day | Domain & infra | Engine & content | Outreach | Risk gate |
|---|---|---|---|---|
| **D1 (Thu)** | Register `loomwork.org` + `.com` + `.ai`. Set up Cloudflare Pages + DNS. Create GitHub repo `loomwork/site` (private until launch). | Sketch atom schema (frontmatter: title, sources[], tags[], date, status). Decide Astro template. | Draft Bellingcat + OCCRP warm-brief emails (don't send yet) | Domain available? If not → fall back to Plumbline. |
| **D2 (Fri)** | Astro skeleton up; home + revelations + about routes empty | Hand-write Revelation 1 (Methane-Award Paradox) — full draft with all sources cited and archive.org links | — | Source verification gate: every source link works + has archive snapshot |
| **D3 (Sat)** | RSS + JSON-feed wired; Buttondown email signup form | Hand-write Revelation 2 (Dark Vessels Green Flags) | — | — |
| **D4 (Sun)** | `/sources` page with 25 ingestion sources documented (license + cadence) | Hand-write Revelation 3 (Refugee Credentials) | — | — |
| **D5 (Mon)** | `/methodology` page; correction policy; telos-gate description in plain English | Hand-write Revelation 4 (Forced Labor in Clean Tech) | Send warm-brief emails to OCCRP, GFW, TBB, Bellingcat — request review feedback by D11 | Legal-risk gate: any named individuals? Lawyer-eyeball for libel before publish |
| **D6 (Tue)** | Atlas page (static buckets, no force-graph yet) | Hand-write Revelation 5 (Indigenous PADDD) | Warm-brief emails to EDF/Carbon Mapper/Walk Free | — |
| **D7 (Wed)** | Submit form (Tally → email forward) | Edit pass on all 5 revelations; second-eye review | — | Voice gate: any internal vocabulary leaked? Audit. |
| **D8 (Thu)** | 25 more sources documented (50 total) | Begin connecting wiki engine to publish pipeline (wiki atom → Astro markdown → site) | Warm-brief emails to RAISG, indigenous federation contacts (via Rainforest Foundation Norway intro) | — |
| **D9 (Fri)** | Performance + accessibility audit (Lighthouse, axe-core) | Hand-write *About* page + governance + funding-model | — | — |
| **D10 (Sat)** | Mastodon, Bluesky, Twitter accounts created; bios + linked | Final copy edit pass | Apply to fiscal sponsors (Code for Science & Society + Open Collective + Hopewell) | — |
| **D11 (Sun)** | Buffer / contingency day — fix what's broken | Incorporate partner-review feedback into revelations | Confirm 3+ partner endorsement quotes for launch press | Endorsement gate: zero endorsements → delay launch by 7 days |
| **D12 (Mon)** | Email digest #0 ready (preview to test list) | Final fact-check pass on all 5 revelations | Send embargoed press release to 10 named journalists (T+2 launch) | — |
| **D13 (Tue)** | Last DNS / SSL / RSS sanity checks; analytics (Plausible) | "Soft launch" post to Anthropic Discord + Alignment Forum + LessWrong (T-1) | Schedule Twitter/Mastodon/Bluesky/HN posts | — |
| **D14 (Wed) — LAUNCH** | Site live | Publish all 5 revelations | Show HN; Twitter thread; LinkedIn long-form; emails to journalists (now unembargoed) | Crisis gate: rapid-response plan if a named target threatens legal action |

### What "launched" means

- ✅ `loomwork.org` live with home + 5 revelations + atlas + sources + methodology + about + subscribe + submit
- ✅ 50+ ingestion sources documented (license, cadence, last successful pull)
- ✅ RSS + JSON-feed working, Buttondown email digest with ≥10 subscribers
- ✅ 3+ named partner endorsements live on About page
- ✅ Fiscal sponsor applications submitted (3 of 3)
- ✅ HN front page attempted (success not guaranteed)
- ✅ ≥1 journalist replies expressing interest in covering or following up

### Failure modes to pre-bake responses for

- **Legal threat from a named target.** Pre-write a response: "All sources are public; archive snapshots attached; corrections welcome and prominently displayed; no individuals named except those already in the public criminal/regulatory record."
- **Accusation of AI-generated slop.** Methodology page is the answer; show the human verification step explicitly.
- **An NGO partner objects to having been named.** Have a 24-hour takedown clause baked into outreach: any named source can request anonymization within 7 days of launch.
- **Hacker News dunks on the AI angle.** Don't lead with AI. Lead with cross-source data work.

---

## What this does to the dharma_swarm internal stack

**Nothing visible to it changes.** The engine name stays `dharma_swarm` internally. Loomwork is the **skin** — a static site that publishes atoms the engine produces. Every revelation pulls from the wiki at `~/.dharma/knowledge/wiki/` (the existing 300-atom Karpathy wiki) plus new world-facing atoms produced by the weaving engine described in `wiki_weaving_engine.md`. The contemplative-spine vocabulary stays internal where it belongs; the world meets a quiet, citation-first investigative outlet.

The kill list (`arjuna_kill_list.md`) and the targets list (`arjuna_targets.md`) stay aligned: most of what was flagged for KILL is *still* candidate for KILL, but with a new criterion — *does this skill or atom contribute to a Loomwork revelation in the next 90 days?* If yes, redirect. If no, kill stays on the table.

---

## Out-of-scope flags (noted, not pursued)

- The chetana plugin load failure mentioned in parent context is unrelated to this brief — separate fix.
- The TBB outreach draft from the parent (`tbb_intro_v1.md`) should be *paused* until D5 of this plan: warm-brief them as a Revelation-3 partner first, then convert to TalentRouter conversation later. That sequence builds more credibility than cold-pitching them on TalentRouter alone.
- The Mirror Experiment artifacts in `_archive_navel/` stay archived; this plan does not touch them.

Sources cited inline. Live availability searches done 2026-05-07; user must re-verify domain availability at registration time.

---

**Sources:**
- [OSINT Industries](https://www.osint.industries/)
- [Maltego](https://www.maltego.com/)
- [Plumbline Solutions / Solomon Cloud Solutions name change 2015](https://www.solomoncloudsolutions.com/plumbline-solutions.html)
- [Plumb (closed)](https://useplumb.com/)
- [Constella Intelligence (OSINT identity risk)](https://constella.ai/)
- [Constellate AI (business solutions)](https://constellate.ai/)
- [CrossWeave (defunct, acquired 2003)](https://www.crunchbase.com/organization/crossweave)
- [Crossweave Technology Solutions India](https://in.linkedin.com/company/crossweave-technology-solutions)
- [Fathom.io](https://fathom.io/) and adjacent Fathom-named platforms (heavy Fathom-prefix saturation)
- [Voyager Labs (AI investigation)](https://www.voyager-labs.com/)
- [ShadowDragon](https://shadowdragon.io/)
- [Cylect.io](https://cylect.io/)
