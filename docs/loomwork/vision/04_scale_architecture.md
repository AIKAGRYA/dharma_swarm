# Loomwork Scale Architecture — Level 15 to Level 100

**Status:** Vision document, level-100 horizon
**Created:** 2026-05-07
**Anchor:** This document maps Loomwork's evolution from a single-operator local prototype (level 15) through six scale bands to a multi-decade public-utility substrate (level 100). Each band names its data model, technology stack, governance, funding, and threat model. Every claim grounded in a real-world precedent (OCCRP Aleph, Wikidata, ICIJ Pandora Papers, Mastodon federation, ClickHouse, Vespa) where possible; speculation is marked.

The premise of the document: **scale is not a knob you turn at the end. It is a sequence of phase transitions, each of which kills the previous architecture if not anticipated.** The naive failure mode is to build for level 100 on day one (collapse under complexity) or to build for level 15 forever (collapse under success). The right move is to build the simplest thing that *survives the next phase transition* — and to be explicit about which decisions are forward-compatible vs. lock-in.

---

## SECTION 1: Scale Bands and Their Constraints

Seven bands. Each is a phase transition, not a knob.

### Band 0 — Single-operator local (level 15)

**Numbers.** ~10⁴ atoms total, ~50 atoms/day ingest, ~5 revelations/week, single curator, single machine.

**Stack.** M5 Mac (M-series Apple Silicon, 128GB RAM); SQLite or DuckDB for the ontology store; Astro static site rendered to localhost; ripgrep + SQLite FTS for search; Ollama Cloud GLM-5 free-tier for inference; Obsidian-compatible markdown atoms with YAML frontmatter; existing dharma_swarm primitives (FractalRoom, TelosGatekeeper, SignalBus, witness logs).

**Cost.** $0–200/mo. Free GLM-5 carries inference; Cloudflare deferred to next band.

**Governance.** Dhyana decides everything. The system has zero downstream consumers; the only audit is self-audit.

**Threat model.** None external. Risks are internal: scope creep, atom-schema lock-in, evaluator monoculture, drift away from Jagat Kalyan fitness. The only adversary is yourself.

**What lives here today.** This is the current Loomwork v0 design (`docs/loomwork/02_loomwork-design.md`). The 14-day ship gate.

**Survival question.** Will this band's atom schema survive the next 1000x? Will the FractalRoom composition survive 10⁵ atoms?

### Band 1 — Single-operator hosted (level 25)

**Numbers.** ~10⁵ atoms, ~500 atoms/day, ~20 revelations/week, ~10 named partners (NGOs/journalists granted API access), single operator + 0–2 contributors.

**Stack.** DuckDB → Postgres 16 + pgvector 0.9; S3 (Cloudflare R2 for egress-free) for atom backups + content blobs; Astro SSG + serverless API endpoints (Cloudflare Workers or Vercel Edge); BM25 + dense vectors hybrid search; Ollama Cloud + paid Sonnet for telos-gate review; static Cloudflare Pages or Vercel; Tailscale for ops access.

**Cost.** $500–1500/mo. Postgres-managed (Supabase, Neon, RDS small) ~$300; R2 storage ~$50; CDN ~$50; paid inference for high-confidence telos gates ~$300; ops + monitoring ~$100; ~$200 buffer for spikes.

**Governance.** Dhyana + advisory board (3–5 names). Per-revelation review still single-operator; partner inputs treated as advisory not authoritative. Capture risk: still zero (single-funder doesn't exist yet).

**Threat model.** First adversaries arrive: SEO spam, low-effort harassment, occasional cease-and-desist letter from a shell-company target. Real but manageable. Need: a documented retraction policy, a public methodology page, a no-PII-of-vulnerable-persons gate that's already proven (carry from Band 0).

**Migration trigger.** When daily atom ingest exceeds DuckDB's healthy ceiling (~10M rows on M-class hardware) OR when a journalist partner asks "can I query your data programmatically?" — that's the threshold to hosted.

### Band 2 — Small-team operated (level 40)

**Numbers.** ~10⁶ atoms, ~5K atoms/day, ~50 revelations/week, ~100 partners, 3–5 staff, peer review on all revelations.

**Stack.** Postgres + Citus (or AlloyDB / Aurora) for sharded OLTP; Apache Iceberg on S3 for the warm-tier atom warehouse; ClickHouse Cloud for analytics queries; **NATS or Redpanda** (NOT Kafka — operational overhead too high for team-size) for scout-pipeline events; pgvector for ≤50M vectors, swap to Vespa or Qdrant when crossing that threshold; Astro SSR + edge functions; mix of free-tier Ollama + paid Anthropic + paid open-router fine-tunes; basic role-based access (RLS in Postgres).

**Cost.** $5K–20K/mo. Inference is the dominant line ($3–10K depending on revelation volume + telos-gate strictness); Postgres + ClickHouse + storage ~$2K; CDN + edge ~$500; observability (OpenTelemetry → Honeycomb or Grafana Cloud) ~$300; security ~$500; ops/staff platform ~$1K. **Note:** ClickHouse benchmarks show 1B rows query in ~23s for $0.67 on 9 nodes, so analytical workloads are cheap once you cross to columnar — the cost driver is inference, not storage.

**Governance.** Formal board (5 directors), fiscal sponsor (501(c)(3) or international equivalent — see Section 5 for candidates). Editorial committee separate from board. Conflict-of-interest policy. Public retraction log.

**Threat model.** Real adversaries. Coordinated harassment campaigns. State-actor probing (especially if Loomwork has surfaced anything on a sovereign target). Provider-level pressure (Cloudflare deplatforming risk after 2017–2026 history of selective deplatforming). Mitigation: multi-CDN posture, encrypted backups in 2+ jurisdictions, journalist-shield legal counsel on retainer, tiered classifier-based publication gate that catches "this looks like a state-actor target" and routes to higher human review.

**Migration trigger.** When peer review becomes the bottleneck (revelation queue depth grows faster than reviewer capacity) — that's when you need Band 3's automated decorrelated-evaluator pipeline AND you need a board, not just a sponsor, because liability is now real.

### Band 3 — NGO-tier production (level 60)

**Numbers.** ~10⁷–10⁸ atoms, ~50K atoms/day, ~200 revelations/week, ~1000 partner orgs, 15–40 staff, full board governance, multi-region for sovereignty.

**Stack.** Sharded Postgres (Citus, Aurora, or vanilla 16+ partitioned) for hot-tier; Iceberg + ClickHouse for warm/cold-tier (the lakehouse pattern is mature here); Vespa or distributed Milvus for vector search at this scale (pgvector becomes the bottleneck above ~50M vectors per the 2026 benchmarks); event bus on NATS JetStream (cluster mode) or Redpanda; Kubernetes for service orchestration (managed: GKE/EKS); **multi-region replication** for sovereignty (EU, US, one Global South region — Singapore or São Paulo); ensemble inference with automated decorrelation scoring; in-house fine-tuned classifiers for high-volume pattern types (e.g., methane-emitter attribution, beneficial-ownership chain reconstruction).

**Cost.** $50K–200K/mo. Inference still dominant ($20–80K depending on automation level). Multi-region storage + egress ~$10K. Compute ~$15K. Compliance + auditing ~$5K. Security retainer + bug bounty ~$10K. Engineering platform ~$10K. **Real-world anchor:** OCCRP at this band ran on USAID + a few foundation grants pre-2025; Aleph holds 400M+ documents from 200+ datasets serving 25,000 journalists. Their per-document cost model shows the Band 3 economics: ingest is cheap, *curation is expensive* — most cost is human review, not machine compute.

**Governance.** Independent 501(c)(3) (US) or charitable foundation (NL stichting, UK CIC, German gGmbH). Full executive team. Editorial board chaired independently of operations. Whistleblower-protection policy. SOC 2 Type II (for partner-API trust). Red-team annual exercises. Public funding diversification report.

**Threat model.** State-actor adversaries directly; corporate adversaries with seven-figure legal budgets; coordinated disinformation injection at the source-feed level (poisoning OCCRP Aleph or GFW DIST-ALERT upstream); insider risk (a staff member compromised). Mitigation: defense-in-depth across the existing 7 telos gates + cryptographic source provenance (signed atom imports from each partner) + adversarial-disinformation tests in CI + clearance levels for high-risk topic queues. Crucially: **the funding-capture problem becomes acute here**. Section 5 below.

**Migration trigger.** When >1 nation-state actor is documented as having attempted disruption AND the federation surface area becomes a force-multiplier rather than a liability.

### Band 4 — Federation (level 80)

**Numbers.** ~10⁹ atoms across federation, ~500K atoms/day aggregate, ~1000 revelations/week (federated), 1M+ readers, peer Loomwork instances run by partner orgs (Bellingcat-equivalent, EU-investigative-equivalent, Latin-American-investigative-equivalent), shared schema, federation council.

**Stack.** Federation protocol — **NOT ActivityPub directly** (ActivityPub's known scaling pathologies — DDoS-shaped reply-fan-out, missing-replies, OpenGraph storms — make it a poor fit for atom-class structured data); instead, a **purpose-built protocol** that composes ActivityPub-style server-to-server messaging with:
- **Decentralized identifiers (DIDs)** for atom authorship (every atom carries a verifiable provenance signature from its publishing instance);
- **Content-addressed identifiers (CIDs)** in the IPFS/IPLD sense for atom content (so the same revelation surfacing on two federated instances has the same identifier);
- **JSON-LD typing** anchored in a published, versioned ontology (Schema.org-class extensibility);
- **Federation-level evaluator decorrelation registry** — peer instances publish their evaluator stack and the federation council monitors for evaluator-stack convergence (Krogh-Vedelsby diversity term as a federation-level governance metric, not just a single-instance one).

Per-instance: ClickHouse + Iceberg lakehouse continues; vector search via Vespa (proven at billion-vector scale); each instance publishes a federation manifest declaring its scope, evaluator stack, and threat-model class.

**Cost split across federation members.** Each instance ~$100–500K/mo depending on regional scope and revelation volume. Federation council operations (governance, schema evolution, dispute resolution) funded by federation dues — a fixed percentage of each instance's annual budget, capped to prevent any single instance from having outsized governance vote.

**Governance.** Federation council with peer-org governance. Constitutional document defining: schema-evolution process (must pass 2/3 federation vote), atom-revocation process, dispute resolution between instances, dissolution clauses, succession of any individual instance. Council-of-councils pattern: the federation council is itself audited by a separate body (think Wikimedia Foundation board + community elections).

**Threat model.** Federation creates new attack surfaces: a compromised instance becomes an injection vector. Mitigation: per-instance atom signatures with revocable keys; cross-instance integrity audits; a federation-level "isolation" status that lets the federation cut off a compromised peer without losing historical atoms. State-actor capture of an entire federation member is now a real risk; multi-jurisdictional spread (EU + US + neutral) is the structural defense.

**Migration trigger.** When federation makes the math work: the marginal cost of adding a new federation member is much less than running an equivalent expansion in-house, AND the federation aggregate surface area is large enough that no single nation-state actor can compromise it without compromising 3+ jurisdictions simultaneously.

### Band 5 — Substrate (level 95)

**Numbers.** ~10¹⁰+ atoms, used by infrastructure layer (downstream AI training, government accountability dashboards, journalist tooling, citizen apps), Wikidata-class scale (Wikidata as of early 2025 had 1.65B item statements). Public good infrastructure. ~$100M+ deployed in operating + endowment.

**Stack.** Standards-anchored. The atom schema is now a published RFC-class spec; the federation protocol has IETF / W3C draft status; the public query interface is a federated SPARQL endpoint plus a GraphQL federation gateway (the two pattern languages of large knowledge graphs). Inference fabric includes a small-model foundation-class LLM trained on Loomwork's own corpus (provenance-clean, telos-gated training data is itself a public good). Long-term storage on multi-region object stores with cryptographic integrity proofs; at this scale, atom-content is sharded geographically (jurisdictional sovereignty per atom: a Brazilian indigenous-land atom is mirrored in EU + Brazil + a neutral third).

**Cost.** Endowment-grade. **Real-world anchor:** Wikimedia Foundation's FY24-25 budget was ~$185M with a $130M+ endowment; Wikidata-specific funding was $1M from endowment + $100k from grants — a sliver of the broader Wikimedia spend, but the Wikimedia infrastructure carries it. Loomwork at Band 5 needs either an analogous parent-org cost-sharing structure OR ~$50–100M in standalone annual operating, ~$500M endowment to be succession-proof.

**Governance.** Multi-stakeholder governance. Five constituency seats minimum: NGO partners; foundation funders (capped seats); reader/citizen representatives (elected); technical advisory council; mission-trustees (legal-protected role with veto on mission-drift). Conflict-of-interest is now structural, not just declared — funders cannot serve on editorial committee, technical decisions cannot override editorial decisions, etc.

**Threat model.** At this band, Loomwork becomes a target *because* of its substrate role. Risks: AI vendor capture (downstream models trained on Loomwork data create dependency, the substrate becomes captured-by-downstream); foundation capture (the bigger the budget, the bigger the funders, the more pressure to soften certain investigations); legitimacy attacks (a coordinated campaign claiming Loomwork is biased or compromised, designed to delegitimize its atoms in court or in public discourse). Defense: published, audited evaluator-stack composition; periodic external audits by independent journalism academics; legal-protected mission constitution with mandatory reportable-events disclosures.

**Migration trigger.** When the federation's aggregate corpus exceeds what any individual member could practically replicate, AND the standards bodies (W3C, IETF) are willing to consider Loomwork's protocol as a candidate standard — that's when the move from "federation of orgs" to "substrate of the field" becomes structural rather than aspirational.

### Band 6 — Public utility (level 100)

**Numbers.** Multi-decade durability. Atom count continues growing but the *meaningful unit* is no longer atoms — it's the field of recognized patterns and the institutional memory those patterns constitute. The original founder is no longer involved (Dhyana retired or deceased). Standards-track. Self-sustaining. Resilient to individual nation-state pressure.

**Stack.** The stack of 2050 is not knowable; what's knowable is the *interface*. The atom schema spec; the federation protocol spec; the telos-gate composability spec; the source-provenance spec; the evaluator-decorrelation governance spec — these survive multiple stack rewrites. The implementations don't.

**Cost.** Permanent endowment-funded. Loomwork-the-utility runs on a $1B+ endowment producing operating funding + matched annual contributions from federation members + a tiny fraction of usage fees from commercial entities (the "commercial tier" pays; the public tier remains free forever).

**Governance.** Public-utility governance. Legal-protected mission (constitutional charter that requires supermajority of independent stakeholders to amend). Succession mechanisms for every role (no role has a single point of failure). Multi-decade plan (analogous to Long Now Foundation's framing — the architecture is for a 100-year horizon, with explicit handoff plans every 25 years).

**Threat model.** The threat model itself becomes generational. Risks: civilizational events (climate displacement of operating regions, political upheaval, pandemic disruption); slow capture across decades (a foundation that grows from 5% to 40% of funding over 20 years quietly steers the org); technical obsolescence (the storage substrate of 2026 is unreadable in 2050 unless migration was continuous). Defense: jurisdictional diversity treated as architectural; funding diversification audited as a governance metric (no funder >15% over any 5-year window); migration is a continuous practice, not an event.

**Migration trigger.** None. This is the steady state.

---

## SECTION 2: Data Model Evolution

The atom schema must evolve as scale grows. The forward-compatibility decisions made at Band 0 determine what's possible at Band 6.

### Band 0 — YAML frontmatter + markdown, single Ontology registry

Atoms are markdown files with YAML frontmatter. Stored in an SQLite/DuckDB ontology registry (the existing dharma_swarm `ontology.py` schema). Each atom has a UUID, a typed kind (`event`, `entity`, `pattern`, `dot`, `revelation`, `actor`, `dataset`, `claim`, `question`), provenance fields, telos-gate fields, links to other atoms.

**Forward-compatible decisions to make NOW:**
- **UUIDs not auto-incrementing IDs.** Auto-increment is dead at federation. UUID v7 (time-ordered) is the right call — sortable for hot-path queries, federation-safe.
- **Versioning at atom-level from day one.** Even at Band 0, every atom has a `schema_version` and a `revision_history`. Cheap now; impossible to retrofit at Band 4.
- **Content-hash field reserved.** Don't compute it yet, but reserve the field. At Band 4, content-addressing becomes the federation backbone.
- **Provenance as first-class.** Every atom carries `source_dataset`, `ingest_timestamp`, `ingest_evaluator_stack`. At Band 5, this is the auditable trail.
- **Avoid hardcoding any storage path in the atom itself.** Atoms reference other atoms by UUID + (optional) federation instance, not by file path.

**Lock-in to AVOID:**
- Encoding atom rendering in the atom itself (HTML, formatting). At Band 1+ the renderer must be free to change.
- Hardcoding evaluator names in atom content (e.g., "GLM-5 said this looks suspicious"). Use evaluator IDs that resolve through a registry.
- Mixing claim text with claim metadata. Separate the human-readable revelation prose from the structured `claim` atoms it cites.

### Band 1 — Postgres schema, GraphQL API, atom versioning

Migrate the SQLite ontology registry to Postgres. Add a GraphQL API with persisted queries (avoid arbitrary client queries — too easy to DoS). Atom versioning becomes auditable via a `revisions` table.

**Decision:** stay schemaless-where-possible. Use a `payload_jsonb` column for atom-kind-specific fields, keep the typed columns minimal (id, kind, schema_version, ingest_timestamp, content_hash, federation_origin). Postgres jsonb + GIN indexes handle the long tail.

### Band 2 — Event-sourcing (atoms are events), CQRS, materialized views

The atom *log* becomes the source of truth. Mutations are append-only events; the queryable atom-state is a materialized view computed from the log. This is the move that makes Band 3's hot/warm/cold tiering and Band 4's federation possible — federation is fundamentally about replicating event logs across instances.

**Decision:** event log on Postgres logical replication or a dedicated event store (EventStoreDB, or just Postgres with ordering guarantees). Materialized views in ClickHouse for analytics; in pgvector for vector search; in OpenSearch or Quickwit for full-text; the read-side is whatever fits the query, the write-side is one log.

### Band 3 — Columnar storage for analytics, hot/warm/cold tiering

Hot tier (last 90 days): Postgres + Vespa. Warm tier (90 days–5 years): Iceberg on S3 + ClickHouse. Cold tier (5+ years): Iceberg on S3 + Glacier/Deep Archive, indexed but not query-active without rehydration.

**Decision:** Iceberg as the warm-tier substrate is the right call (open format, multi-engine, supports schema evolution, used by Netflix/Apple/Airbnb at petabyte scale). Avoids vendor lock to ClickHouse Cloud while still using ClickHouse as compute.

### Band 4 — Federated identifiers (DIDs), content-addressed atoms (CIDs), JSON-LD

Each atom becomes:
- **DID-authored:** the publishing instance signs the atom with its DID. Verifiable cross-instance.
- **CID-content-addressed:** the same atom on multiple instances has the same CID; cross-references work even if an instance goes offline.
- **JSON-LD typed:** the atom's properties are linked-data, anchored in a published ontology vocabulary. SPARQL-queryable across the federation.

This is the move from "Loomwork's atoms" to "atoms of a kind that any system can produce and consume." It's irreversible once committed — but if the schema decisions in Band 0 reserved the right fields, it's not catastrophic.

### Band 5 — Schema.org-class typology, federated query

The atom ontology graduates to a published vocabulary that other organizations can extend (sub-vocabularies for specific domains: `loomwork:env`, `loomwork:corruption`, `loomwork:labor`). The Schema.org governance model (Google + Microsoft + community + standards process) is the precedent.

Federated query: SPARQL endpoint per instance; a global query layer (think Wikidata Query Service, but federated) that joins across instances. Performance: hard. The Wikidata Query Service has documented scaling pain at 1.65B statements; Loomwork at Band 5 must either accept similar pain or invest in better federated query infrastructure (a real research problem, not a deployment problem).

### Band 6 — Standards-track schemas, backward-compatible evolution forever

The schema spec becomes an RFC. Schema evolution is governed (every change requires a published rationale, a backward-compatibility analysis, a migration period). Atoms from 2026 are still queryable in 2050. The technology underneath has changed three or four times.

**The schema decisions made at Band 0 that survive to Band 6:**
- UUID v7 atom IDs (still valid forever)
- Content hashing scheme (SHA-256 → maybe Blake3, but the field exists)
- Provenance as first-class (audit trail across decades)
- Telos-gate fields as schema, not implementation (the gate logic changes; the gate-passed/failed metadata persists)
- Multilingual atom content (i18n decisions made at Band 0 don't survive if not made; retrofitting at Band 5 is brutal)

---

## SECTION 3: Inference Architecture Evolution

The "find a dot, link to others, promote to revelation" pipeline.

### Band 0 — Single-model GLM-5 over all atoms, naive vector search

GLM-5 (free tier on Ollama Cloud) handles atomization, linking, pattern detection, and revelation drafting. SQLite FTS for full-text. Optional: a small embedding model (BGE-M3 or similar) for vector search.

**Why it works at Band 0:** atoms are 10⁴; reviewer is human (Dhyana); errors have human catchpoints. Single-model is acceptable because the *human* is the second evaluator.

**Why it stops working:** at 10⁵+, human review can't keep up. You need the evaluator-pool architecture.

### Band 1 — Hybrid search (BM25 + dense vectors), evaluator pool

Query-time: BM25 for lexical, dense vectors for semantic. Promotion-time: ≥2 evaluators (different model families) per dot-to-revelation decision. Krogh-Vedelsby kicks in.

**Critical decision:** the evaluator-stack is **versioned per atom**. Every revelation records the exact evaluator stack used. This becomes auditable forever.

### Band 2 — Custom fine-tuned classifiers per pattern type, GPU inference

For high-volume pattern detection (e.g., "is this satellite plume attributable to operator X?"), fine-tune small classifiers on the curated labels Loomwork has produced. Cheap to run, fast, and decorrelated from the general LLMs (a fine-tuned BERT-class model has different failure modes than GLM-5).

**Stack:** in-house fine-tunes on RunPod, Modal, or self-hosted A100s. Inference behind a typed API.

### Band 3 — Multi-model ensemble, automated evaluator-decorrelation

Five+ evaluators per high-stakes promotion. Automated decorrelation scoring: when two evaluators agree more than 95% of the time across a held-out set, they're flagged as redundant. The system actively maintains diversity by rotating evaluators in/out.

**Anchored in the dharma_swarm Transcendence Principle:** Krogh-Vedelsby is enforced as a runtime metric, not just a design aspiration. If diversity drops below threshold, new revelations require human review until diversity recovers.

### Band 4 — Federated inference (peer Loomworks contribute evaluators)

Each federation member contributes evaluators to a shared registry. A high-stakes revelation can recruit evaluators from peer instances. This *increases* decorrelation (different orgs use different models, different prompts, different fine-tunes) — but creates a new attack surface (a compromised peer's evaluator becomes an injection point). Mitigation: evaluator output signatures + per-evaluator track record + automated reputation scoring.

### Band 5 — Foundation-model-class trained on Loomwork corpus

Loomwork's corpus is now large and curated enough to train a domain-specialist foundation model. This model becomes one evaluator among many, NOT the central evaluator. The diversity discipline must hold.

**The "AI swallowing the org" risk.** When the in-house foundation model becomes the dominant evaluator, decorrelation collapses. Defense: structural rule that the in-house model can never exceed a fixed percentage (e.g., 30%) of the evaluator pool weight. This is governance, not technology.

### Band 6 — Self-improving inference fabric

The inference fabric continuously trains, evaluates, retires, and replaces evaluators. The *governance* of this fabric — who decides when a model is fit, when it's retired, when its outputs are auditable — is what survives the multi-decade horizon. The technology beneath changes; the audit trail and the diversity discipline persist.

**Maintaining Krogh-Vedelsby at Band 5+ when models converge:** the deep risk. By 2030+, there's a real chance most strong models converge in their failure modes (trained on overlapping data, similar architectures). Defense: deliberate diversity injection — fund and incorporate evaluators from non-mainstream lineages (smaller open-source labs, non-Western training corpora, alternative architectures); run "diversity audits" annually; treat decorrelation as a budget line, not a free byproduct.

---

## SECTION 4: Governance Evolution

### Band 0 — Dhyana decides everything

Single-operator. Decisions are: which atoms to ingest, which dots to promote, which revelations to publish, which sources to trust. Conflict-resolution: introspection. Drift-detection: the operator notices.

### Band 1 — Dhyana + 1–2 contributors, advisory board

Advisory board (3–5 people, unpaid, named publicly). Their role: read everything Loomwork publishes, flag mission drift, vote on contested calls. Not a legal board — an editorial conscience.

### Band 2 — Small team, formal board, fiscal sponsor

5-director board, fiscal-sponsor (Code for America, Mozilla Foundation, NEO Philanthropy, Tides Foundation are common 501(c)(3) wraps for early-stage projects). Editorial committee separate from board. Conflict-of-interest declarations published. Whistleblower hotline.

**Conflict-resolution mechanism:** a tiered decision rights matrix. Operational decisions: executive director. Editorial decisions: editorial committee. Strategic decisions: board. Existential decisions (mission change, dissolution): board + sponsor + member supermajority.

**Mission-drift detection:** quarterly "are we still doing what we said" audit, published.

### Band 3 — Independent 501(c)(3), full governance

Independent legal entity. Bylaws governing every constituency. Annual audited financials. SOC 2 Type II. Whistleblower-protection policy. Editorial independence covenant in bylaws (board cannot direct editorial decisions; only direct the editorial framework).

**Real-world anchor:** OCCRP, ICIJ, ProPublica all live at this band. Their bylaws are public. The pattern is mature; it's not novel — but it requires real legal counsel.

### Band 4 — Federation council with peer-org governance

The federation needs its own governance. A constitution that defines: schema-evolution voting, atom-revocation procedure, dispute resolution between instances, voting weight (one-instance-one-vote? weighted by atom count? weighted by funding contribution?). The voting weight question is the hard one — it's where mission-drift creeps in.

**Recommendation:** one-instance-one-vote on schema and protocol; weighted-by-atom-count-and-quality-score on operational federation decisions; veto-able by mission-trustees on anything touching the editorial covenant.

### Band 5 — Multi-stakeholder governance

NGO partners + funders + readers + technical advisors. Five seats minimum. Capped seats per constituency (no constituency has a majority alone). Mission-trustee role: legally distinct from board, with veto over editorial-covenant changes.

**The Wikimedia Foundation pattern is the precedent here**, with adjustments. Wikimedia has community-elected board seats; Loomwork at Band 5 should have analogously elected reader/citizen seats.

### Band 6 — Public-utility governance

Legal-protected mission. Constitutional charter. Multi-decade succession plans for every role. Generational governance — the board reviews succession explicitly every 5 years.

**Long Now Foundation's framing is the precedent:** governance designed for a 100-year horizon means *every decision asks "how does this look in 50 years?"*

---

## SECTION 5: Funding Architecture Evolution

The capture problem is the deepest governance problem. **Three-quarters of nonprofit news orgs are foundation-funded; the median nonprofit news org gets the majority of revenue from foundations** (Shorenstein Center). The capture happens slowly: project-based funding gets you doing what funders want; year-over-year, you investigate what funders fund.

### Band 0 — Self-funded (Dhyana)

No funders, no capture. Total budget: ~$0–2K/yr (some compute, some domain registration if/when public).

### Band 1 — Small grants ($10–50K each)

First grants from Fund for Investigative Journalism (typical $5–10K), Logan Foundation, Reporters Committee for Freedom of the Press grants, Knight Foundation small-grants. Total: $50–150K/yr. **Diversification rule from day one: no funder >25% of revenue. Capture-resistance starts at the first $10K grant.**

### Band 2 — Mid grants ($100K–1M), partner contracts

MacArthur, Open Society, Knight, Hewlett, Mozilla, Patrick J. McGovern Foundation, Omidyar Network, Ford Foundation. Total: $500K–3M/yr. **Diversification rule tightens: no funder >20%, no funder family (e.g., all USAID-affiliated programs counted as one) >30%.**

Partner contracts: NGOs paying for custom investigations (not bulk Loomwork data — that's free — but specific tailored work). Revenue from partner contracts caps capture risk if foundation funding shifts.

### Band 3 — Foundation funding diversification (10+ funders, no >20%)

10+ active foundation relationships. **Real-world cautionary tale:** OCCRP's pre-2025 dependency on USAID (~50% of funding) created a structural vulnerability that materialized when the Trump administration defunded USAID in early 2025; OCCRP sued. Loomwork at Band 3 must already have learned this lesson — no funder >20%, ever.

Paid API tiers for partner orgs (NGOs and journalists keep free access; commercial entities pay). Revenue diversification: 60% foundations, 25% partner contracts, 15% paid API.

### Band 4 — Endowment seeding, paid API tiers

Endowment seeding begins. Target: $20–50M endowment. Revenue: 40% foundations, 20% partner contracts, 20% paid API, 20% endowment income.

**Funders that enter at this band:** the larger foundations (Ford, OSF, Hewlett, MacArthur — already there). New: civic-tech-aligned (Patrick J. McGovern, Knight, Omidyar Network at scale). Climate-aligned (Bloomberg Philanthropies, ClimateWorks, Hewlett climate program). AI-safety-aligned where mission-fits (Future of Life Institute, Open Philanthropy). Philanthropic individuals where vetted (this is where the most capture risk exists; treat individual donors with suspicion proportional to their gift size).

### Band 5 — Endowment-funded ($100M+)

$100–500M endowment. Revenue: 30% endowment income, 30% foundations, 20% partner+commercial, 20% federation contributions.

**Real-world anchor:** Wikimedia Endowment was ~$130M in FY24-25, providing $1M to Wikidata and broader operational support. Loomwork at Band 5 needs an endowment of similar order to be operationally insulated from foundation cycles.

### Band 6 — Permanent endowment + public-utility funding

$1B+ endowment. Operational funding from endowment income (~$40–50M/yr at 4–5% drawdown). Federation contributions, partner contracts, commercial tier supplement. Foundations remain a minority of revenue.

**Capture-resistance strategy that survives Band 6:**
1. **Funder diversification audited as a governance metric.** No funder >15% over any 5-year window.
2. **Funder-recusal rule.** Any investigation touching a funder's known interests requires the funder to recuse from any operational role for the duration; published explicitly.
3. **Independent editorial covenant.** Funders cannot direct editorial decisions, only fund the editorial framework. Violations are public events.
4. **Reader/citizen seats on the board.** Constituencies that fund nothing have voting power, structurally.
5. **Transparency reports.** Annual published report listing every funder, every recusal, every "we declined funding because of conflict" event.

The strategy that prevents Walmart Foundation from rejecting investigative work into Walmart is structural: **never accept funding from a target.** Loomwork's investigations of corporate corruption mean Loomwork cannot accept funding from for-profit corporations as a class — only from foundations whose missions are aligned and whose funding conflicts can be transparently declared.

---

## SECTION 6: Compute Cost Trajectory

Every band, monthly cost broken into five buckets.

| Band | Inference | Storage | Network | Compute | Compliance | Total/mo |
|---|---|---|---|---|---|---|
| 0 (level 15) | $0–100 (free GLM-5) | $0 (local) | $0 | $0 (M5 sunk) | $0 | $0–200 |
| 1 (level 25) | $300 (mostly free + paid telos gates) | $50 (R2) | $50 | $200 (managed Postgres) | $0 | $500–1,500 |
| 2 (level 40) | $3,000–10,000 (volume × strictness) | $1,000 (Postgres + Iceberg + ClickHouse warm) | $500 | $1,500 (k8s + observability) | $500 (audits, security retainer) | $5,000–20,000 |
| 3 (level 60) | $20,000–80,000 (in-house fine-tunes reduce cost vs. pure-cloud) | $10,000 (multi-region, hot+warm+cold) | $5,000 | $15,000 (k8s + observability + Vespa) | $5,000 (SOC 2, bug bounty, red-team) | $50,000–200,000 |
| 4 (level 80) | $80,000–250,000 (federated reduces cost via shared evaluator pool) | $25,000 | $15,000 (federation egress) | $40,000 (multi-region k8s + Vespa + federation services) | $20,000 (per-instance cert + cross-instance audit) | $250,000–1M (per instance, federation aggregate ~$5–20M) |
| 5 (level 95) | $500K–1.5M (in-house foundation-class + ensemble) | $100K (10¹⁰ atoms × multi-region × cold) | $50K | $200K | $100K | $1M–4M (single-instance, federation aggregate ~$30–80M) |
| 6 (level 100) | continues with continuous re-architecture | proportional | proportional | proportional | proportional | $50–100M/yr operating + endowment income |

**Breaking points where the cost model has to change:**

1. **Free-tier exhaustion at ~10⁴ atoms/day.** Free Ollama Cloud GLM-5 has rate limits; once Loomwork crosses ~5K telos-gate decisions/day, paid tiers (Anthropic Sonnet, Llama-3.1-405B on managed inference) enter. This is the Band 1→2 cost jump.
2. **pgvector → Vespa at ~50M vectors.** pgvector benchmarks (2026) confirm degradation above 10–50M vectors. The migration is non-trivial; budget 4–8 weeks of engineering.
3. **Single-region → multi-region at Band 3.** Egress costs become substantial; choose providers (R2 over S3 for egress savings) accordingly. Multi-region storage replication is ~3x single-region cost for the same data.
4. **Cloud-only → in-house fine-tunes at Band 2/3.** Once Loomwork has labeled training data at scale, in-house fine-tunes for high-volume classifiers are 10–100x cheaper per inference than calling frontier models. The capital cost (training, MLOps team) pays back quickly above ~10⁵ classifier calls/day.
5. **Federation cost-share at Band 4.** Federation reduces per-instance cost because evaluators, schema work, and infrastructure are shared. But it increases governance cost and inter-instance audit cost. Net: federation is cheaper per atom processed but more expensive per unit of governance.

---

## SECTION 7: Technology Stack Recommendations

For each band, the canonical stack and the defense for each choice.

| Layer | B0 | B1 | B2 | B3 | B4 | B5 | B6 |
|---|---|---|---|---|---|---|---|
| **Atom DB** | SQLite | Postgres + pgvector | Postgres + Iceberg + ClickHouse | Sharded Postgres + Vespa + Iceberg + ClickHouse | Same + DID/CID layer | Federated SPARQL + GraphQL Federation | Standards-track |
| **Compute** | M5 Mac | Single-region managed | Managed K8s | Multi-region K8s | Federated K8s peers | Federated peers | Continuous re-arch |
| **Search** | ripgrep + SQLite FTS | BM25 + pgvector hybrid | Vespa OR Quickwit (lex+vec) | Vespa cluster | Federated query | SPARQL endpoints | Standards-track |
| **Pub** | Astro static | Astro + edge functions | SSR + edge | CDN-first + multi-region edge | Federated render | Federated + commercial APIs | Standards-track |
| **AI** | Ollama Cloud GLM-5 | Free + paid mix | Multi-model + fine-tunes | Ensemble + automated decorrelation | Federated inference | In-house foundation + ensemble | Continuous |
| **Federation** | none | none | none | Provincial peers | Purpose-built protocol | Standards-draft protocol | Standards-track |

**Defenses for the choices that aren't obvious:**

- **NATS or Redpanda over Kafka at Band 2.** Kafka's operational overhead is well-documented; for a 5-staff team, NATS JetStream (single-binary, simple ops) or Redpanda (Kafka-protocol-compatible, simpler ops) are 10x easier to run with similar capability at Loomwork's volume.
- **Iceberg at Band 2 (early).** Iceberg's value is open-format escape — lock-in to ClickHouse Cloud or Snowflake at Band 2 is recoverable; lock-in at Band 4 is structural. Pay the upfront complexity.
- **Vespa over distributed Milvus or Pinecone at Band 3.** Vespa supports lexical + vector + structured filtering in one engine, which matters for Loomwork's hybrid query pattern. Milvus is vector-only; Pinecone is hosted-only (vendor lock).
- **Custom federation protocol over ActivityPub at Band 4.** ActivityPub's documented scaling pathologies (DDoS-shaped fan-out, missing-replies) make it unsuitable. Building on top of ActivityPub's transport with a structured-data overlay is reasonable; using ActivityPub semantics directly is not.
- **No mention of blockchain.** Loomwork's atom integrity needs are served by cryptographic signatures (DIDs, content hashes) and audit logs. Blockchain adds operational complexity for no benefit at this design point. If a future federation member wants blockchain-anchored revocation logs, that's a per-member decision, not a substrate choice.

**Resume-Driven Development to AVOID:**
- Don't pick Kafka because "Kafka is what real engineers use" — pick the simplest queue that survives the next band.
- Don't pick ClickHouse Cloud at Band 0 because it's impressive — DuckDB is fine, and the migration to ClickHouse at Band 2 is ~1 week of work.
- Don't pick a JS framework at Band 0 — Astro static is enough; SSR enters at Band 2 when API endpoints become real.

---

## SECTION 8: Migration Hardpoints

The hardest migrations are not technical, they are organizational. Each migration is named with trigger, technical plan, governance plan, fallback.

### Migration 1: Schema migration across 10⁹ atoms

**Trigger.** Schema evolution at Band 4+. The ontology has to add a new field; existing 10⁹ atoms need to honor the new schema.

**Technical plan.** Backward-compatible by construction — schema version field, schema-aware readers, online rolling migration. Iceberg table-format supports schema evolution; pgvector supports adding columns. The work is at the application layer: every reader must handle multiple schema versions, every writer must write the new version.

**Governance plan.** Schema changes go through the federation council (Band 4+). RFC process: published rationale → community review (30-day) → vote (2/3 supermajority) → migration period (12 months minimum) → deprecation of old schema (5 years minimum at Band 5+).

**Fallback.** If migration fails partway, atoms remain in their old schema; readers tolerate. Migration retries are idempotent.

### Migration 2: Single-region → multi-region without downtime

**Trigger.** Sovereignty (legal) at Band 3. EU-jurisdiction atoms must remain in EU; some atoms cannot leave Brazil/Indonesia per local data laws.

**Technical plan.** Postgres logical replication for hot tier; Iceberg multi-region replication for warm tier; per-atom sovereignty tagging; query router that respects sovereignty. Cutover via blue-green deploy of the query router; rollback path: route to single region.

**Governance plan.** Define jurisdictional policies before cutting over. Engage legal counsel in each region. Memorialize sovereignty requirements in atom schema (each atom tagged with permitted residency).

**Fallback.** Single-region operation continues; multi-region is additive, not replacement, for the first 6 months.

### Migration 3: Evaluator-pool growth without diversity collapse

**Trigger.** Continuous, but acute at Band 3+ when evaluator pool grows past ~10 evaluators.

**Technical plan.** Decorrelation scoring matrix: pairwise agreement on a held-out set, computed weekly. Evaluators that exceed 95% agreement on the held-out set are flagged as redundant; one of the pair is rotated out. New evaluators added to maintain diversity (different model families, fine-tune lineages, training corpora).

**Governance plan.** Diversity audit annually, published. Foundation-model evaluators (Band 5) capped at 30% of pool weight by board policy. Mission-trustee veto over any change that would push diversity below threshold.

**Fallback.** If diversity drops below threshold, new revelations require human review until diversity recovers.

### Migration 4: Single-operator → board succession

**Trigger.** Founder departure (planned: 5 years before; unplanned: incapacitation, death). At Band 1+.

**Technical plan.** Documentation. Every operational decision is documented with rationale. Onboarding a successor takes 60 days at Band 1, 120 days at Band 3, 365 days at Band 5+.

**Governance plan.** Succession plan from Band 1 onward. Named successor at Band 2+. Multi-named successor pool at Band 3+. Public succession process at Band 5+.

**Fallback.** Federation absorbs orphaned instances if a single instance loses its operator at Band 4+. Mission-trustee role takes operational continuity at Band 5+.

### Migration 5: Single-jurisdiction → federation

**Trigger.** Federation invitation accepted (Band 3→4). Or: legal pressure makes single-jurisdiction unsustainable.

**Technical plan.** Federation protocol implementation; per-instance signing keys; cross-instance audit endpoints; federation council membership.

**Governance plan.** Federation constitution adoption. Instance representative seated on federation council. Cross-instance audit schedule established.

**Fallback.** Federation membership is revocable. If federation governance becomes captured or hostile, instance can leave and continue as standalone Band 3.

### Migration 6: Single-team → multi-team across timezones / cultures

**Trigger.** Staff growth past ~10 (Band 2/3 boundary).

**Technical plan.** Async-first work culture. Documentation as a load-bearing artifact. Time-zone-distributed handoffs (the editorial-review queue passes between regional teams as the day rotates).

**Governance plan.** Cultural-and-language audit of editorial decisions. Multi-language editorial committee at Band 3+. No single language dominates (English is the lingua franca but not the only one — translations are first-class, not afterthoughts).

**Fallback.** Stay smaller. Some orgs work better at small scale; growth is not mandatory.

---

## SECTION 9: 25-Year Horizon

What does Loomwork at level 100 in 2050 look like? Honest speculation.

**Atom count: 10¹¹+.** The world has continued to break in interesting ways. Loomwork at Band 6 is the substrate-of-record for "what's broken" across multiple domains. Total corpus exceeds 100 billion atoms; most are cold-tier, retained for institutional memory but rarely queried.

**AI capabilities.** This is the deepest uncertainty. Three rough scenarios:

- **Scenario A (continuity):** Foundation models continue scaling along current trajectories. Loomwork's evaluator pool includes models that are Band-5-equivalent in 2026 terms; new models are evaluated on the same diversity-and-decorrelation criteria; the substrate is stable. The discipline that maintained Krogh-Vedelsby in 2026 still maintains it.
- **Scenario B (capability transition):** AI capabilities cross a threshold (some flavor of AGI, or a paradigm shift like neuromorphic-or-bio compute). Loomwork must absorb the shift: the in-house foundation model becomes obsolete; new evaluators dominate; the federation architecture is stress-tested. Survival depends on whether the schema, governance, and audit-trail were truly portable.
- **Scenario C (capability collapse):** AI capability stalls or regresses (compute-input limits, alignment failures requiring rollback, regulatory caps). Loomwork's evaluator pool becomes constrained; human review becomes the binding constraint. Survival depends on whether human-review processes were preserved, not just decommissioned in favor of automation.

**Climate state.** 1.5°C exceeded by ~2030 (most current projections); 2.0°C by 2050 plausible. Loomwork's environmental-monitoring atom volume (deforestation alerts, methane plumes, displaced-population data) grows by orders of magnitude. The technical scale challenge is met; the political-economy challenge of *what to do with that data* is the harder problem. Loomwork at Band 6 is one node in a larger network of accountability infrastructures.

**Geopolitical.** Post-current-hegemony plausible. Multi-polar substrate becomes mandatory: Loomwork members in EU, US, India, Brazil, Indonesia, sub-Saharan Africa each operate under different legal regimes. The federation architecture is tested by jurisdictional fragmentation. Some atoms become illegal in some jurisdictions; the federation protocol must handle "this atom is sovereign-restricted to these regions."

**Loomwork's role.** Still investigative, but the *category* of "investigative" has expanded. Loomwork's atoms feed into:
- Journalist tooling (still the primary direct user)
- Government accountability dashboards (where governments still permit)
- Legal proceedings (Loomwork-cited atoms used as evidence in litigation; a chain-of-custody story built on the DID/CID provenance from Band 4 onward)
- AI training datasets (Loomwork as a public-good source of provenance-clean, telos-gated training data)
- Educational substrate (school curricula on global accountability)
- Other Loomwork instances (federation peers consume each other's outputs)

The "supramental layer" framing from Dhyana's original directive — *the eyes the mother of the universe might use* — survives if and only if the substrate stays trusted across these constituencies. Trust is the only scarce resource that doesn't compound automatically; it must be earned every year.

**What designs-for-now hold up for 25 years:**

1. **Atom schema with versioning, content-addressing, provenance, and telos-gate metadata as first-class.** Schema evolves; the schema-evolution discipline persists.
2. **Diversity-and-decorrelation discipline for evaluators.** The technology changes; the discipline survives because it's governance, not implementation.
3. **Funder diversification rules (no >15% over 5 years).** Permanent.
4. **Editorial covenant in bylaws.** The legal protection survives changes of stack and personnel.
5. **Multi-jurisdictional posture.** Once established, hard to lose.
6. **Append-only event log.** The atom event log of 2026 is still readable in 2050; that's the audit trail's gift.

**What gets replaced:**

1. **The actual storage technology.** SQLite → Postgres → Iceberg → whatever 2050's substrate is. The interfaces survive; the implementations don't.
2. **The evaluator stack.** Every model in Loomwork's evaluator pool in 2026 is gone by 2050. The pool composition discipline survives; the actual models don't.
3. **The publishing technology.** Astro is gone by 2032; the "render published atoms" interface survives.
4. **The federation protocol implementation.** Probably 2 protocol-version transitions across 25 years. The ontology vocabulary survives multiple protocol changes.
5. **The original founder.** Inevitable. Succession plan is the design that survives the founder.

---

## Appendix: Real-world Numbers Cited

- **OCCRP Aleph:** 400M+ documents from 200+ datasets, 25,000 journalist users, free for nonprofit journalism orgs (1TB/instance), pre-2025 USAID was largest funder (~50%); USAID defunded January 2025; OCCRP sued February 2025. ([OCCRP Aleph Pro FAQ](https://www.occrp.org/en/announcement/aleph-pro-frequently-asked-questions-on-the-future-of-occrps-investigative-data-platform), [OCCRP In Brief 2026](https://www.occrp.org/en/about-us/occrp-in-brief/), [Wikipedia](https://en.wikipedia.org/wiki/Organized_Crime_and_Corruption_Reporting_Project))
- **ICIJ Pandora Papers:** 11.9M records, 2.94 TB, 600 journalists from 150 orgs, year-long investigation, Neo4j + Linkurious + datashare stack. ([Linkurious blog](https://linkurious.com/blog/technology-pandora-papers-investigation/), [Neo4j case study](https://neo4j.com/blog/fraud-detection/pandora-papers-revealing-financial-secrets/), [ICIJ](https://www.icij.org/investigations/pandora-papers/about-pandora-papers-leak-dataset/))
- **Wikidata:** 1.65B item statements (early 2025), $1M from Wikimedia Endowment + $100k grant for FY24-25, $130M+ endowment overall. ([Wikimedia FY25-26 Budget](https://meta.wikimedia.org/wiki/Wikimedia_Foundation_Annual_Plan/2025-2026/Budget_Overview), [FY24-25 audit highlights](https://diff.wikimedia.org/2025/11/24/highlights-from-the-wikimedia-foundations-fiscal-year-2024-2025-audit-report/), [Endowment FY24-25](https://diff.wikimedia.org/2026/03/19/highlights-from-the-wikimedia-endowments-fiscal-year-2024-2025-audit-report/))
- **ClickHouse benchmarks:** 1B rows in ~23s for ~$0.67 (9 nodes); 10B rows in ~67s for ~$4.27 (20 nodes); ClickHouse Cloud the only system staying anchored in "Fast & Low-Cost" through 100B-row stress test. ([ClickHouse cost-performance comparison](https://clickhouse.com/blog/cloud-data-warehouses-cost-performance-comparison))
- **Mastodon scaling:** 500GB media per 1000 users; 32-64GB RAM for large communities; documented ActivityPub fan-out DDoS pathologies. ([Mastodon hardware guide](https://wehaveservers.com/blog/dev-use-cases/deploying-a-mastodon-activitypub-server-hardware-setup-guide/), [Wikipedia](https://en.wikipedia.org/wiki/ActivityPub))
- **pgvector:** operational friction above ~10–50M vectors; Vespa needed for billion-scale; Vespa latency ~15ms vs pgvector ~25–40ms. ([CallSphere benchmarks 2026](https://callsphere.ai/blog/vector-database-benchmarks-2026-pgvector-qdrant-weaviate-milvus-lancedb), [Instaclustr pgvector guide](https://www.instaclustr.com/education/vector-database/pgvector-key-features-tutorial-and-pros-and-cons-2026-guide/))
- **Foundation-funding capture risk:** ~75% of nonprofit news orgs receive foundation funding, usually majority of revenue; project-based funding creates capture risk; diversification recommended in Brazil, Romania, Senegal, AP. ([Shorenstein Center](https://shorensteincenter.org/resource/funding-the-news-foundations-and-nonprofit-media/), [GIJN diversification analysis](https://gijn.org/stories/solving-investigative-journalisms-profit-puzzle/), [Benson 2018 NYU](https://rodneybenson.org/wp-content/uploads/Benson-2018-Can-Foundations-Solve-the-Journalism-Crisis.pdf))
- **DIDs + IPFS:** content-addressing via CIDs, self-sovereign verifiable identifiers, ION/IPID combining DIDs with IPFS. ([IPFS docs on CIDs](https://docs.ipfs.tech/concepts/content-addressing/), [IPFS blog on ION](https://blog.ipfs.tech/ion-a-path-to-decentralized-identity/))

---

*End of scale architecture document. The map covers 25 years; the next 14 days build the seed. Every Band 0 decision either compounds or constrains every later band — make them with the long horizon in mind.*
