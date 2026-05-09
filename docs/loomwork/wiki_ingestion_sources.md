# Wiki Ingestion Sources — World-Facing Dot-Connection Engine

**Created:** 2026-05-07
**Frame:** dharma_swarm wiki at `~/.dharma/knowledge/wiki/` (currently 249 inward atoms about altitude/contemplative-bridges/llm-cognition) is being repointed as a **supramental dot-connection layer** ingesting WHAT IS WRONG IN THE WORLD. This catalog is the seed: 70+ scrapable, queryable, RSS-able, API-able feeds across 12 wrongness-domains, with a TOP-30 priority list at the end.

**Atomization principle:** every record from every source becomes a Karpathy-style atom (frontmatter + 1-page note + bidirectional links). Cross-pollination is automatic: shared entities (companies, places, people, vessels, parcels, plumes, lawsuits) form the connective tissue.

---

## 1. ENVIRONMENTAL DESTRUCTION

| Source | URL | Access | Data | Cadence | Volume | License | Atom-fit | Cross-pollinates with | Risk | Cost |
|---|---|---|---|---|---|---|---|---|---|---|
| **GFW Integrated Disturbance Alerts (DIST-ALERT)** | data.globalforestwatch.org / `/dataset/gfw_integrated_alerts` | Open API (GET) | Pixel-level alerts (lat/lon/date/confidence) | Near-real-time, daily | ~thousands of alerts/day globally | CC-BY 4.0 | HIGH (one alert = one atom) | concession registries, OpenCorporates, Aleph, indigenous-territory layers | low-tech, low-political | free |
| **GFW GLAD-L / GLAD-S2 / RADD** | globalforestwatch.org | Open API | Tropical primary forest loss alerts | Weekly | thousands/week | CC-BY 4.0 | HIGH | DIST-ALERT, palm-oil concessions, pulp-mill registries | low | free |
| **Carbon Mapper Data Portal (Tanager-1 + EMIT)** | data.carbonmapper.org | Open API (registration), CSV/GeoJSON | Methane + CO₂ plumes with operator-attributable lat/lon, emission rate | Routine since Feb 2025 | 300+ plumes already, growing | open w/ citation | HIGH (plume → operator → facility) | EDGAR, SEC EDGAR, EPA TRI, state oil-gas registries, MethaneSAT/AIR | medium-political (oil-gas pushback) | free |
| **MethaneSAT / MethaneAIR (EDF)** | methanesat.org/data, GEE catalog | Form-gated free, Google Earth Engine, GCP Marketplace | L3 concentration grids, L4 area + point sources | Periodic releases (satellite lost contact 2025-06-20; backlog still releasing; airborne MethaneAIR continues) | 2 ppb sensitivity, 90-min cadence over O&G zones (historical) | free w/ application | HIGH | Carbon Mapper, IEA Methane Tracker, EDGAR | medium | free |
| **OpenAQ** | openaq.org | Open API | PM2.5 / NO₂ / O₃ ground-station readings worldwide | Hourly | ~10K stations, millions of records | CC-BY 4.0 | HIGH (city × pollutant × hour) | EEA, EPA AirNow, hospital admissions, refinery locations | low | free |
| **EPA Toxic Release Inventory (TRI)** | epa.gov/toxics-release-inventory-tri-program | Bulk + Envirofacts API | Facility-level chemical releases (US) | Annual reporting | ~22K facilities, billions of lbs | public domain | HIGH | OpenCorporates, SEC, environmental-justice census layers | low | free |
| **EEA EU emissions / E-PRTR** | eea.europa.eu, prtr.eea.europa.eu | Bulk + API | EU industrial pollutants | Annual | ~30K facilities | open | HIGH | Carbon Mapper, EU CSDDD filings | low | free |
| **RAISG / MapBiomas Amazon** | raisg.org, mapbiomas.org | Bulk + API | Indigenous territory maps + illegal mining + land-cover change in Amazon | Quarterly | hundreds of millions of pixels | open | MEDIUM | DIST-ALERT, GFW, mining-concession registries | medium-safety | free |
| **Allen Coral Atlas** | allencoralatlas.org | Open download | Global coral reef bleaching + benthic class | Updated as imagery available | global reef coverage | open w/ attribution | MEDIUM | Climate TRACE shipping, MPAtlas, Global Fishing Watch | low | free |
| **Global Forest Watch Drivers of Loss** | globalforestwatch.org | API | Forest-loss attribution to commodity (palm/soy/cattle/timber) | Annual | global | CC-BY | HIGH | Sourcemap, Panjiva, supply-chain disclosure | low | free |
| **IUCN Red List** | iucnredlist.org | API (registration) | Threatened species per region | Periodic | ~150K assessed species | non-commercial; CC for some layers | MEDIUM | GBIF, TRAFFIC, INTERPOL wildlife | low | free for non-commercial |
| **GBIF** | gbif.org | Open API (DOI per query) | Species occurrence records globally | Continuous | 2B+ records | CC-BY-NC / CC-BY | MEDIUM | IUCN, eBird, iNaturalist | low | free |

---

## 2. CORRUPTION / FINANCIAL CRIME

| Source | URL | Access | Data | Cadence | Volume | License | Atom-fit | Cross-pollinates | Risk | Cost |
|---|---|---|---|---|---|---|---|---|---|---|
| **OCCRP Aleph** | aleph.occrp.org | Open API + bulk; partnership for full | Entities, documents, leak archives | Continuous | 3.8B entries, 50TB, 400M+ docs across 200+ datasets | mixed (open + restricted) | HIGH | OpenCorporates, OpenSanctions, CourtListener, ICIJ leaks | medium-political (libel) | free for journalism / partnership |
| **OpenCorporates** | opencorporates.com | API (free tier 200 calls/mo, paid tiers) | Company registries from 140+ jurisdictions | Continuous | 220M+ companies | mixed; commercial use restricted | HIGH | Aleph, OpenSanctions, Sayari, beneficial-ownership leaks | low-tech | freemium ($/quota) |
| **OpenSanctions** | opensanctions.org | Open API; CC-NC; commercial = paid | PEPs + sanctions + crime-watchlists, consolidated | Daily | 480K+ entities | CC-BY-NC; commercial license required for businesses | HIGH | Aleph, OpenCorporates, ICIJ, customs records | low-tech, medium-political | free non-commercial; paid commercial |
| **ICIJ Offshore Leaks Database (Pandora/Panama/Paradise/Bahamas)** | offshoreleaks.icij.org | Bulk + search (no full API) | Beneficial owners of offshore entities from leaks | Episodic releases | 800K+ entities cumulative | open w/ attribution | HIGH | Aleph, OpenCorporates, sanctions lists | medium-political | free |
| **CourtListener / RECAP (Free Law Project)** | courtlistener.com | REST API; 5K requests/day free tier; MCP server | US federal + state opinions, dockets, briefs | Daily | ~10M+ opinions, ~15M+ RECAP docs | mixed (most public domain) | HIGH | SEC EDGAR, FTC, regulatory dockets, ProPublica | low | free for most use |
| **SEC EDGAR** | sec.gov/edgar | Bulk + Full-text search + API | Public-company filings (10-K, 8-K, proxies, enforcement) | Real-time | tens of millions of docs | public domain | HIGH | OpenCorporates, FinCEN, CourtListener, EPA TRI | low | free |
| **FinCEN BOI / SBA / OFAC** | fincen.gov, treasury.gov/ofac | OFAC list bulk download; BOI partly stalled | Sanctions, beneficial-ownership (US), specially designated nationals | Daily (OFAC) | 12K+ OFAC entries; BOI in flux | public domain | HIGH | OpenSanctions, Aleph | low | free |
| **OpenOwnership Register** | openownership.org | Bulk JSON | Beneficial-ownership disclosures from countries with public registers (UK, etc.) | Continuous | 25M+ records | open | HIGH | OpenCorporates, ICIJ, OCCRP | low | free |
| **DataReportal / Global Witness** | globalwitness.org | Reports (web), some structured data | Investigations of resource-corruption nexus | Continuous | hundreds of investigations/yr | mixed | MEDIUM | Aleph, Sayari, supply-chain | medium-political | free |

---

## 3. MODERN SLAVERY / LABOR ABUSE

| Source | URL | Access | Data | Cadence | Volume | License | Atom-fit | Cross-pollinates | Risk | Cost |
|---|---|---|---|---|---|---|---|---|---|---|
| **Walk Free Global Slavery Index** | walkfree.org/global-slavery-index | Bulk download (CSV/PDF reports) | Country-level prevalence + sectoral G20 imports | Biennial | 160 countries | CC-BY-NC | MEDIUM (country-level, not record-level) | UN ILO, Sourcemap, Panjiva | low | free |
| **US TVPA / Trafficking in Persons Report** | state.gov/trafficking-in-persons-report | Bulk PDF | Country-tier rankings + narrative | Annual | ~190 country reports | public domain | MEDIUM | Walk Free, IJM, Polaris | low | free |
| **Polaris Project (US human-trafficking)** | polarisproject.org | Reports + dataset partnerships | Trafficking typology + hotline calls | Continuous | mixed | mixed | LOW-MEDIUM | court records, EBSCO labor cases | medium-safety | partner-required for raw |
| **IJM (International Justice Mission)** | ijm.org | Reports | Field investigations of bonded labor | Continuous | mixed | mixed | LOW | partner reports | medium-safety | partner |
| **EU CSDDD filings (2026 entry into force)** | EU TED + national registries | Scrape filings; EU TED open | Corporate due-diligence disclosures (supply chain) | Annual disclosures starting 2026-27 | thousands of large EU companies | public | HIGH | Sourcemap, Panjiva, ChainScan use-case | medium-political | free |
| **UK Modern Slavery Registry** | modernslaveryregister.gov.uk | Open search (scrape) | UK companies' MSA statements | Annual filings | ~16K statements | public | MEDIUM | Walk Free, Sourcemap | low | free |
| **Better Work (ILO/IFC)** | betterwork.org | Reports | Garment-factory compliance audits in 8 countries | Continuous | mixed | mixed | MEDIUM | Sourcemap, brand supply chains | medium-political | free |
| **Sheffield Modern Slavery & Human Rights PEC** | modernslaverypec.org | Reports + datasets | Academic studies + open data | Continuous | mixed | mixed | LOW-MEDIUM | research → atom | low | free |

---

## 4. CONFLICT / HUMAN RIGHTS / DISPLACEMENT

| Source | URL | Access | Data | Cadence | Volume | License | Atom-fit | Cross-pollinates | Risk | Cost |
|---|---|---|---|---|---|---|---|---|---|---|
| **ACLED** | acleddata.com | API (tiered: free dashboard, paid disaggregated/real-time) | Armed-conflict events (lat/lon/date/actors) | Weekly | ~2M+ events cumulative | CC-BY-NC for non-commercial; commercial license required | HIGH (event = atom) | UCDP, OHCHR, Bellingcat, ReliefWeb | medium-political | freemium ($/tier) |
| **UCDP Conflict Data** | ucdp.uu.se | Open download | Battle-deaths, organized-violence events | Annual + monthly | 100K+ events | CC-BY 4.0 | HIGH | ACLED, OHCHR, ICRC | low | free |
| **OHCHR (UN Human Rights)** | ohchr.org | Reports + databases | Treaty-body decisions, country mandates, special-rapporteur reports | Continuous | tens of thousands | mixed | MEDIUM | UCDP, ACLED, Genocide Watch | medium-political | free |
| **Bellingcat OSINT publications** | bellingcat.com | RSS + web | Investigations w/ georeferenced evidence | Continuous (~weekly) | hundreds of investigations | CC-BY-SA on many | MEDIUM | ACLED, Forensic Architecture, Aleph | medium-political | free |
| **Forensic Architecture** | forensic-architecture.org | Cases + investigations | 3D reconstructions of incidents (police violence, war crimes) | Project-based | ~80 investigations | mixed | MEDIUM | OHCHR, ACLED, Bellingcat | medium-political | free |
| **Airwars** | airwars.org | Open + API for partners | Civilian casualty allegations from airstrikes | Continuous | 50K+ allegations | mixed | HIGH | ACLED, OHCHR, Forensic Arch | medium-political | free non-commercial |
| **IOM DTM (Displacement Tracking Matrix)** | dtm.iom.int | Open + datasets via HDX | Displaced-persons flow data, 100+ countries | Periodic | millions of records | mixed (most CC) | HIGH | UNHCR, ACLED, ReliefWeb | medium-safety | free |
| **UNHCR Operational Data Portal** | data.unhcr.org | Open API + bulk | Refugee population statistics | Periodic | millions | mixed | HIGH | IOM, TBB Talent Catalog, ACLED | medium-safety | free |
| **Genocide Watch** | genocidewatch.com | Reports + alerts | 10-stage genocide tracker by country | Continuous | ~50 active alerts | open | MEDIUM | OHCHR, UCDP, ACLED | medium-political | free |
| **HDX (Humanitarian Data Exchange)** | data.humdata.org | Open API + bulk | 20K+ humanitarian datasets aggregated | Continuous | 20K+ datasets | mixed (mostly CC) | HIGH | meta-aggregator for §4 | low | free |

---

## 5. REGULATORY / LOBBYING CAPTURE

| Source | URL | Access | Data | Cadence | Volume | License | Atom-fit | Cross-pollinates | Risk | Cost |
|---|---|---|---|---|---|---|---|---|---|---|
| **OpenSecrets (Center for Responsive Politics)** | opensecrets.org | Open API + bulk | US lobbying spending, campaign finance, revolving-door | Continuous | millions of records | open w/ attribution | HIGH | LobbyFacts, CourtListener, SEC | low | free |
| **LobbyFacts EU** | lobbyfacts.eu | Open API + scrape | EU Transparency Register (lobbyists ↔ MEPs) | Daily updates | ~13K orgs registered | open | HIGH | OpenSecrets, EU TED, Aleph | low | free |
| **Federal Register (US)** | federalregister.gov | Open API | Proposed/final rules + comment dockets | Daily | ~80K docs/yr | public domain | HIGH | regulations.gov, GAO, CourtListener | low | free |
| **Regulations.gov** | regulations.gov | Open API | Public-comment dockets | Daily | millions | public domain | HIGH | Federal Register, OpenSecrets | low | free |
| **EU TED (Tenders Electronic Daily)** | ted.europa.eu | Open API + bulk | EU procurement notices | Daily | hundreds of thousands/yr | open | HIGH | OpenCorporates, LobbyFacts, sanctions | low | free |
| **GAO Reports** | gao.gov | RSS + bulk | US Government Accountability Office findings | Continuous | thousands/yr | public domain | MEDIUM | regulatory dockets, OpenSecrets | low | free |
| **SEC Enforcement Actions** | sec.gov/enforce | Bulk + EDGAR | SEC press releases + litigation releases | Continuous | thousands/yr | public domain | HIGH | EDGAR filings, CourtListener, news | low | free |

---

## 6. SUPPLY CHAIN ABUSES

| Source | URL | Access | Data | Cadence | Volume | License | Atom-fit | Cross-pollinates | Risk | Cost |
|---|---|---|---|---|---|---|---|---|---|---|
| **Sayari (commercial)** | sayari.com | Paid API | Beneficial-ownership + supply-chain graph (200+ jurisdictions) | Continuous | 2.5B+ entities | proprietary | HIGH | Aleph, OpenCorporates, Panjiva | low | paid (enterprise) |
| **Panjiva / S&P** | panjiva.com | Paid API | US/global customs records, bills of lading | Continuous | tens of millions of records/yr | proprietary | HIGH | Sourcemap, ImportGenius, sanctions | low | paid |
| **ImportGenius** | importgenius.com | Paid API + free tier | US customs records | Continuous | millions/yr | proprietary | HIGH | Panjiva, Sourcemap | low | freemium |
| **Sourcemap** | sourcemap.com | Partner API | Brand → tier-N supplier maps | Continuous | thousands of brands | partner-required | HIGH | EU CSDDD, Walk Free, Panjiva | low | partner |
| **Global Trade Alert** | globaltradealert.org | Open + API | Trade restrictions & subsidies by country | Continuous | 70K+ measures | CC-BY | MEDIUM | LobbyFacts, customs records | low | free |
| **FTC Enforcement** | ftc.gov/legal-library | Bulk | Antitrust + consumer-protection cases | Continuous | thousands | public domain | MEDIUM | CourtListener, SEC, OpenSecrets | low | free |
| **Trase.earth** | trase.earth | Open API | Commodity supply-chain mapping (soy, beef, palm) | Continuous | millions of trade flows | CC-BY | HIGH | GFW Drivers, Sourcemap, EU CSDDD | low | free |

---

## 7. HEALTH CRISES

| Source | URL | Access | Data | Cadence | Volume | License | Atom-fit | Cross-pollinates | Risk | Cost |
|---|---|---|---|---|---|---|---|---|---|---|
| **WHO EIOS (Epidemic Intelligence)** | eios.who.int | Partner-required for raw; public summaries | 80K+ sources/day → outbreak signals | Continuous | thousands of signals/day | partner | HIGH | ProMED, ECDC, ReliefWeb | low | partner-required |
| **ProMED-mail (ISID)** | promedmail.org | RSS + email + partner API | Volunteer-curated outbreak reports | Daily | thousands/yr | mixed (CC for many) | HIGH | EIOS, GIDEON, GISAID | low | free |
| **FDA FAERS (Adverse Event Reporting)** | fda.gov/drugs/fda-adverse-event-reporting-system-faers | Open API + bulk | Drug + biologic adverse events | Quarterly | tens of millions of reports | public domain | HIGH | clinical trials, RxISK, FDA enforcement | low | free |
| **NIH ClinicalTrials.gov** | clinicaltrials.gov | Open API + bulk | Registered trials w/ outcomes | Continuous | 500K+ trials | public domain | HIGH | FDA, FAERS, journals | low | free |
| **ECDC Threat Reports** | ecdc.europa.eu | Open + RSS | EU communicable-disease threats | Weekly | thousands/yr | open | MEDIUM | EIOS, ProMED | low | free |
| **GISAID (genomic surveillance)** | gisaid.org | Registration-gated API | SARS-CoV-2 + influenza + others sequences | Continuous | millions of sequences | restricted-but-open | HIGH | ProMED, ECDC, regional labs | low | free w/ registration |
| **OpenFDA** | open.fda.gov | Open API | FDA enforcement, recalls, drug labeling | Continuous | millions of records | public domain | HIGH | FAERS, courts | low | free |
| **Open Targets** | opentargets.org | Open API | Disease-target-drug evidence | Continuous | 60K+ targets | CC-BY | MEDIUM | clinical trials, papers | low | free |

---

## 8. CLIMATE ACCOUNTABILITY

| Source | URL | Access | Data | Cadence | Volume | License | Atom-fit | Cross-pollinates | Risk | Cost |
|---|---|---|---|---|---|---|---|---|---|---|
| **Climate TRACE** | climatetrace.org/data | Open bulk + beta API | Asset-level GHG emissions globally | Monthly (April 2026 release through Feb-2026 data) | 352M+ assets | CC-BY 4.0 | HIGH (asset = atom) | EDGAR, Carbon Mapper, OpenCorporates | low | free |
| **Climate Action Tracker** | climateactiontracker.org | Reports + data | Country-level NDC + 1.5°C alignment ratings | Periodic | ~40 countries | open | MEDIUM | UNFCCC, EDGAR | low | free |
| **EDGAR (JRC Emissions)** | edgar.jrc.ec.europa.eu | Bulk download | National-sectoral GHG emissions | Annual | global, 1970- | open | MEDIUM | Climate TRACE, IEA | low | free |
| **Climate Cases (Sabin Center)** | climatecasechart.com | Bulk + scrape | Climate litigation worldwide | Continuous | 2700+ cases | mixed | HIGH | CourtListener, regulatory dockets | low | free |
| **Carbon Brief** | carbonbrief.org | RSS + scrape | Climate news + analysis + datasets | Continuous | hundreds/yr | mixed (CC for some) | MEDIUM | TRACE, IEA, COP docs | low | free |
| **IEA Methane Tracker** | iea.org/reports/global-methane-tracker | Bulk download | Country/sector methane | Annual | global | mixed | MEDIUM | MethaneSAT, Carbon Mapper | low | free |
| **Net Zero Tracker** | zerotracker.net | Open API + bulk | Corporate + national net-zero pledges | Continuous | thousands of entities | CC-BY-SA | MEDIUM | OpenCorporates, SEC, Sustainalytics | low | free |

---

## 9. WILDLIFE / BIODIVERSITY CRIME

| Source | URL | Access | Data | Cadence | Volume | License | Atom-fit | Cross-pollinates | Risk | Cost |
|---|---|---|---|---|---|---|---|---|---|---|
| **TRAFFIC Wildlife Trade Portal** | trafficj.org / wildlifetradeportal.org | Open search + API | Seizures of trafficked wildlife | Continuous | tens of thousands | open | HIGH | INTERPOL, customs records, IUCN | medium-safety | free |
| **EIA (Environmental Investigation Agency)** | eia-international.org | Reports + RSS | Wildlife + forest crime investigations | Continuous | hundreds/yr | mixed | MEDIUM | TRAFFIC, customs | medium-safety | free |
| **WWF Wildlife Crime** | wwf.panda.org | Reports | Field investigations | Continuous | mixed | mixed | LOW | TRAFFIC, EIA | low | free |
| **CITES Trade Database** | trade.cites.org | Open API | Permitted trade in CITES-listed species | Annual | 23M+ records | open | HIGH | TRAFFIC, IUCN, customs | low | free |
| **Skylight (illegal fishing)** | skylight.global | Partner | Vessel-behavior anomaly alerts | Continuous | global vessel coverage | partner | HIGH | Global Fishing Watch, OpenSanctions | medium-safety | partner |
| **Global Fishing Watch** | globalfishingwatch.org | Open API | AIS + SAR vessel detections | Daily | 70K+ vessels tracked | CC-BY | HIGH | Skylight, Aleph (vessel ownership) | medium-safety | free |

---

## 10. TECH / AI HARM

| Source | URL | Access | Data | Cadence | Volume | License | Atom-fit | Cross-pollinates | Risk | Cost |
|---|---|---|---|---|---|---|---|---|---|---|
| **AI Incident Database (AIID)** | incidentdatabase.ai | GraphQL API (read-only) + GitHub bulk | AI-system real-world harms | Continuous | 1361+ incidents (Jan 2026) | CC-BY-SA | HIGH | OECD AI, AlgorithmWatch, FTC AI cases | low | free |
| **OECD AI Incidents Monitor** | oecd.ai | Open + dashboards | OECD-curated incidents subset | Continuous | thousands | open | MEDIUM | AIID, EU AI Act registry | low | free |
| **AlgorithmWatch** | algorithmwatch.org | RSS + reports | EU automated-decision-system investigations | Continuous | hundreds/yr | mixed (CC for many) | MEDIUM | AIID, EU AI Act, FTC | low | free |
| **Mozilla *Privacy Not Included** | foundation.mozilla.org/en/privacynotincluded | Reports + scrape | Consumer-tech privacy reviews | Periodic | hundreds of products | open | MEDIUM | EFF, FTC, AlgorithmWatch | low | free |
| **EFF Atlas of Surveillance** | atlasofsurveillance.org | Open + bulk | US police surveillance-tech deployments | Continuous | 11K+ data points | CC-BY | HIGH | court records, ACLU, FOIA | medium-political | free |
| **FTC AI / Tech Cases** | ftc.gov | Bulk | FTC enforcement of AI / dark patterns | Continuous | thousands cumulative | public domain | MEDIUM | CourtListener, OpenSecrets | low | free |
| **MIT AI Risk Repository** | airisk.mit.edu | Bulk + API | Taxonomy + 800+ AI risks from literature | Periodic | 800+ entries | mixed | MEDIUM | AIID, OECD | low | free |

---

## 11. DISASTER / CRISIS EARLY WARNING

| Source | URL | Access | Data | Cadence | Volume | License | Atom-fit | Cross-pollinates | Risk | Cost |
|---|---|---|---|---|---|---|---|---|---|---|
| **GDACS (Global Disaster Alert Coordination)** | gdacs.org | Open RSS + API | Earthquake/tsunami/cyclone/flood alerts | Real-time | thousands/yr | open | HIGH | USGS, NOAA, ReliefWeb | low | free |
| **ReliefWeb** | reliefweb.int | Open API + RSS | Humanitarian reports + jobs + situation analyses | Continuous | hundreds/day | open | HIGH | IOM, UNHCR, ACLED | low | free |
| **FEWS NET (Famine Early Warning)** | fews.net | Bulk + scrape | Country food-security classifications + outlooks | Monthly | 30+ countries | public domain | HIGH | IPC, UNHCR, ACLED, climate | low | free |
| **IPC (Integrated Food Security Phase Classification)** | ipcinfo.org | Open + GeoNode | Food-insecurity phase mapping | Periodic | 30+ countries | open | HIGH | FEWS NET, FAO | low | free |
| **USGS Earthquake Hazards** | earthquake.usgs.gov | Open API + RSS | Seismic events globally | Real-time | thousands/day | public domain | HIGH | GDACS, INGV, EMSC | low | free |
| **NOAA NWS / Hurricane Center** | nhc.noaa.gov, weather.gov | Open API | Tropical storms + warnings | Continuous (storm season) | events/yr | public domain | HIGH | GDACS, ECMWF | low | free |
| **Copernicus Emergency Management Service** | emergency.copernicus.eu | Open + API | Rapid-mapping + early-warning for EU + global | Event-based | hundreds/yr | open | HIGH | ECMWF, GDACS | low | free |
| **ECMWF / Copernicus Climate** | ecmwf.int / climate.copernicus.eu | API (registration) | Forecasts + reanalyses | Continuous | terabytes | open | MEDIUM | NOAA, FEWS NET | low | free w/ registration |

---

## 12. INVESTIGATIVE JOURNALISM FEEDS

| Source | URL | Access | Data | Cadence | Volume | License | Atom-fit | Cross-pollinates | Risk | Cost |
|---|---|---|---|---|---|---|---|---|---|---|
| **GIJN (Global Investigative Journalism Network)** | gijn.org | RSS + bulk | Investigation roundups + tools + methods | Weekly | hundreds of stories/yr | mixed | MEDIUM | meta-pollinator across all categories | low | free |
| **ProPublica Datastore** | projects.propublica.org | Open APIs (Nonprofit Explorer, Represent, etc.) + bulk | Nonprofits, Congress, COVID-bailout, etc. | Continuous | millions of records | mixed (most open) | HIGH | OpenSecrets, SEC, IRS-990 | low | free / freemium |
| **DocumentCloud (Free Law / MuckRock)** | documentcloud.org | Open API | Public-records uploads from journalists | Continuous | 5M+ docs | mixed | HIGH | FOIA, courts, news | low | free |
| **MuckRock** | muckrock.com | Open + scrape | FOIA requests + responsive docs | Continuous | hundreds of thousands | mixed | HIGH | DocumentCloud, FBI vault | low | free |
| **Bellingcat (#1 OSINT)** | bellingcat.com | RSS + tools | Open-source investigations | Weekly | hundreds/yr | mixed | MEDIUM | ACLED, Forensic Architecture, Aleph | medium | free |
| **OCCRP Investigations** | occrp.org | RSS | Cross-border crime investigations | Weekly | hundreds/yr | mixed | MEDIUM | Aleph, OpenSanctions | medium-political | free |
| **FrontLine Investigations** | frontlinedefenders.org | Reports | At-risk human-rights defenders | Continuous | thousands/yr | mixed | MEDIUM | OHCHR, Genocide Watch | medium-safety | free |

---

## 🎯 TOP-30 PRIORITY LIST (ranked: signal-density × atomization-fit × cross-pollination × cost-efficiency − political-radioactivity)

1. **GFW Integrated Disturbance Alerts** — global, near-real-time, free, perfect atom shape, the preferred first ingest. Cross-pollinates with everything land-based.
2. **OCCRP Aleph** — 50TB / 3.8B entries / 200+ datasets in one API. Single most pollinatable corruption substrate on Earth.
3. **Carbon Mapper Data Portal** — facility-attributable plumes, free, daily atoms feeding EDGAR / Climate TRACE / Aleph cross-links.
4. **Climate TRACE** — 352M+ asset-level emissions records, CC-BY, monthly cadence, beta API. Each asset = one atom.
5. **OpenSanctions** — 480K entities, free for our use case (journalism/non-commercial), CC-BY-NC, daily refresh.
6. **OpenCorporates** — 220M+ companies, freemium API. The directory backbone.
7. **CourtListener / RECAP** — 10M+ opinions, MCP server already exists, 5K req/day free. Direct doc-to-atom.
8. **SEC EDGAR** — public-domain bulk, the corporate-disclosure substrate; cross-links to OpenCorporates, FTC, OpenSecrets, EPA TRI.
9. **ACLED (free dashboard tier first)** — 2M+ conflict events, perfect atom shape (lat/lon/date/actors). Upgrade tier when funded.
10. **HDX (Humanitarian Data Exchange)** — 20K+ humanitarian datasets in one bulk API. Meta-pollinator for crisis work.
11. **Federal Register + Regulations.gov** — daily public-domain US rulemaking + comments. Lobbying-influence cross-link bedrock.
12. **OpenSecrets** — US lobbying + campaign finance, free API. Pollinates with EDGAR, FTC, regulations.gov.
13. **AI Incident Database (AIID)** — 1361+ AI harms via GraphQL, CC-BY-SA, the primary AI-harm substrate.
14. **Trase.earth** — commodity supply-chain flows, CC-BY API. Connects deforestation atoms to corporate buyers.
15. **MethaneSAT / MethaneAIR (via GEE)** — free w/ application, complements Carbon Mapper, satellite-lost but backlog still releasing.
16. **GDACS** — disaster alerts via RSS/API, real-time, public domain. Crisis-spine.
17. **ReliefWeb** — humanitarian situation reports, free API. Pollinates with ACLED, IOM, UNHCR.
18. **EPA TRI / EnviroFacts** — facility-level US toxic releases, public domain. Environmental-justice substrate.
19. **FEWS NET + IPC** — famine early-warning + classification, free, cross-pollinates with ACLED + climate.
20. **Climate Cases (Sabin Center)** — 2700+ climate-litigation cases, atomizable. Bridges environmental atoms to courts.
21. **CITES Trade Database** — 23M+ legal-trade records of CITES species, free API. Wildlife-crime cross-references.
22. **Bellingcat OSINT publications** — methodology + investigations, mostly CC. Provides investigative-method atoms (instructive cross-pollinator).
23. **OpenAQ** — global air-quality data, hourly, free API. Pollinates with EPA TRI, hospital data, refinery loc.
24. **ICIJ Offshore Leaks** — bulk downloadable beneficial-ownership leaks. Aleph supplement.
25. **FDA FAERS / OpenFDA** — adverse events + recalls + enforcement, public domain. Health-harm spine.
26. **Forensic Architecture** — case-based 3D reconstructions, mixed-license. Highest-quality atom shape, low volume.
27. **EU TED + LobbyFacts EU** — EU procurement + lobbying transparency, open. Cross-pollinates with OpenCorporates, sanctions.
28. **Net Zero Tracker** — corporate + national pledges, CC-BY-SA. Climate accountability cross-link.
29. **Atlas of Surveillance (EFF)** — 11K+ US surveillance-tech deployments, CC-BY. Domestic civil-liberties spine.
30. **Global Fishing Watch** — vessel detections, AIS + SAR, free API. Ocean-crime substrate.

---

## CROSS-POLLINATION DOCTRINE

Every atom in this wiki carries **cross-link metadata** in frontmatter:

```yaml
entities:
  - companies: [OpenCorporates IDs]
  - vessels: [IMO numbers]
  - persons: [OpenSanctions IDs / Aleph IDs]
  - places: [admin-1 codes, lat/lon, parcel IDs]
  - permits: [concession IDs, CITES IDs]
sources: [list of source-atom URIs]
hashes: [content hash for dedup]
emergence_score: 0.0-1.0  # weighted by # cross-source confirmations
```

Atoms with shared entities auto-link bidirectionally. The **emergence_score** ranks atoms where multiple independent feeds confirm the same event/entity — this is the dot-connection signal. The wiki front page is a live-ranked view of highest-emergence-score atoms across all 12 categories, refreshed by the metabolic clock.

---

## IMPLEMENTATION NOTES (out-of-strict-scope, but visible)

- **30 sources are free + open API.** Deferred-paid: Sayari, Panjiva (commercial-only).
- **5 sources require partnerships** (WHO EIOS, Sourcemap, Skylight, Better Work, IJM raw data) — pursue post-MVP.
- **Bulk-first ingestion** is cheaper than streaming for 22/30 top sources — schedule daily/weekly cron, not webhooks.
- **Three sources hit safety walls** (Bellingcat for legal review, Forensic Architecture for likeness rights, IUCN Red List for non-commercial). Wrap in pramana provenance + exposure gate.
- **Three sources (ACLED, OpenSanctions, CourtListener)** are *freemium* — start free, upgrade per usage.
- **Total estimated free-tier API cost for v1:** $0 across 25/30 top sources. Compute-cost dominated by Ollama-Cloud LLM atomization (~$50-200/month at moderate volume).

The fork ends. Catalog is at `/Users/dhyana/.claude/cabinet/strategy/wiki_ingestion_sources.md`.

Sources verified (2026-05-07):
- [GFW DIST-ALERT integrated alerts (Jan 2026)](https://www.globalforestwatch.org/blog/data-and-tools/integrated-deforestation-alerts/)
- [Carbon Mapper data portal](https://data.carbonmapper.org/) and [Tanager-1 launch](https://carbonmapper.org/articles/new-tanager-1-methane-data)
- [MethaneSAT data access via GEE](https://developers.google.com/earth-engine/datasets/publisher/edf-methanesat-ee) (satellite lost contact 2025-06-20; backlog releasing)
- [OpenSanctions licensing](https://www.opensanctions.org/licensing/) (CC-NC; commercial = paid)
- [CourtListener API rate limits](https://www.courtlistener.com/help/api/) (5K req/day free)
- [Climate TRACE data downloads](https://climatetrace.org/data) (CC-BY 4.0, beta API, 352M+ assets)
- [AI Incident Database](https://incidentdatabase.ai/) (GraphQL, 1361+ incidents Jan 2026)
- [ACLED API tiers](https://acleddata.com/acled-api-documentation) (free dashboard, paid disaggregated)
