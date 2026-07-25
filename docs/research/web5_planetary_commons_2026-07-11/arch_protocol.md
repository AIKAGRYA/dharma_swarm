# The Causal Action Receipt Protocol (CARP)
## A protocol engineer's design for the Planetary Intelligence Commons

**Lens:** Protocol engineer. **Date:** 2026-07-11.
**Charge:** minimal viable protocol — schema, signatures, non-backdateability, challenge pointers, identity rails, federation topology, adoption-by-riding, standardization boundary, three interop demos.
**Method note:** every canon claim cites `path:lines` from the five canon reports; every external claim cites a URL from the eight field reports (full reports in this directory). Claims I could not confirm are marked UNVERIFIED.

---

## 1. Elevated Thesis

The agentic internet shipped its nervous system in eighteen months and forgot to ship its conscience — not as ethics, but as *evidence*. MCP and A2A own communication (A2A v1.0, 150+ orgs — https://www.linuxfoundation.org/press/a2a-protocol-surpasses-150-organizations-lands-in-major-cloud-platforms-and-sees-enterprise-production-use-in-first-year). Web Bot Auth, ERC-8004, and OIDC-A own identity. AP2/x402/ACP own payments. C2PA and SCITT own provenance envelopes. Yet no protocol answers the five-part question every liability regime now presupposes: **under whose authority did this agent act, what material burden did it create, toward what declared purpose, what independent evidence proves the outcome, and who can challenge or reverse it?** The gap is not my inference — the standards field states it verbatim: as of early 2026 no implemented protocol combines verifiable attenuable delegation, chained policy, and provenance-aware completion records across MCP/A2A/HTTP (https://arxiv.org/pdf/2603.24775), and practitioners name attaching provenance/confidence to agent outputs as "the defining 2027 standards fight" (https://dev.to/alexmercedcoder/the-state-of-agentic-ai-standards-in-2026-mcp-a2a-webmcp-osi-and-the-protocol-stack-taking-3o2l).

The elevation move is this: **stop designing the Commons as a place and design it as a grammar.** The operator's Web5 brainstorm — "coordinating and evolving under witnessed purpose, material accountability and reciprocal obligation" — is not a platform to build; it is a *receipt semantics* to standardize. Every failed next-web (Solid, TBD/Web5, DSNP — see field_web-evolution.md) died platform-first; every surviving primitive (passkeys, VCs, C2PA, schema.org) won as a grammar carried by other people's infrastructure. So: the Planetary Intelligence Commons is **the SCITT profile + VC vocabulary + challenge state machine** that turns any agent action anywhere into a signed, non-backdateable, independently witnessed, *contestable* object — the Causal Action Receipt (CAR) — plus the thin federation that keeps custody local. The constitution is not written in a founding document; it is compiled into schema invariants that every conformant verifier enforces. Millions of CARs then form the planetary outcome graph that learns which agents, interventions, evidence sources, and financing structures produce durable welfare — but the graph is a *consequence* of the grammar, never the product sold first.

This inverts the doom of every predecessor named in the failure forensics: Cybersyn without the state, Palantir without the kill chain, Verra without the developer-pays verifier, The DAO with a reversal layer that doesn't require fracturing the chain (field_failure-forensics.md). And it is exactly what the estate's own canon already ratified: "Internal artifacts never touch archive fitness; only countersigned external acted receipts above quorum do" (ACTIVE_TRACK.yaml:682-684) — CARP is that One Wire, generalized from one organism to the web.

The 10-100x is structural, not rhetorical: dharma_swarm's spine emits receipts for one organism; the same schema signed and registered becomes compliance evidence for every GPAI deployer after 2026-08-02; the same schema with witness quorum becomes MRV for the $200B/yr biodiversity-finance mandate (https://tnfd.global/engage/tnfd-adopters/); the same schema with challenge pointers becomes the dispute layer whose absence killed ONDC (https://www.business-standard.com/companies/news/ondc-ecommerce-failure-struggles-india-125050501101_1.html). One grammar, four markets, zero platforms.

---

## 2. Architecture — Mechanisms

### 2.1 The object: Causal Action Receipt (CAR)

A CAR is a **chained set of signed segments**, each signed by its own principal, hash-linked in order, enveloped as a COSE_Sign1 (CBOR) or JOSE (JSON) structure, and **registered on a transparency service conforming to IETF SCITT (RFC 9943 — https://datatracker.ietf.org/doc/draft-ietf-scitt-architecture/)**. The receipt's identifier is the multihash of its canonical encoding. Nine segments, mirroring the operator's atomic chain (identity → intention → debit → authority → evidence → action → witnessed outcome → challenge → learning):

```
CAR v0.1 (informative field sketch; normative form = CDDL + JSON-LD context)

header:
  car_version, car_profile (0|1|2|3), car_id (multihash), created_at
  prev_car (optional — receipt chains, e.g. periodic outcome checkpoints)

S1 PRINCIPAL — who acts
  actor_did              # did:web / did:key / did:plc / did:dht — any resolvable DID
  agent_card_ref         # A2A Signed Agent Card digest, if agent
  software_attestation   # optional: model ref, code hash, C2PA-style gen-AI disclosure
  delegation_chain[]     # W3C VC 2.0 credentials, root→leaf, UCAN-style attenuation:
                         #   each link = {issuer_did, subject_did, capabilities[],
                         #   caveats{budget, domain, jurisdiction, expiry}, sig}
  human_root             # passkey/WebAuthn-anchored or eIDAS PID/QEAA for legal persons

S2 INTENTION — toward what
  intent_statement       # bounded claim, human-readable, ≤512 chars
  telos_ref              # URI into a telos registry (global minimal registry or local)
  domain, jurisdiction
  prereg_digest          # optional hash of a pre-registered plan (anti-Goodhart)

S3 BURDEN — at what material cost
  compute {energy_kwh, est_gco2e, method_ref}     # maps to EU GPAI Model Documentation
  tokens/cost_usd                                  # already in spine.EvidenceReceipt
  material[] {resource, quantity, unit, method_ref}
  obligation {amount, unit, route_ref}             # SIS reciprocity debit, if declared

S4 AUTHORITY — under whose sanction
  authority_credential   # VC from a community/bioregional/institutional registry
  consent_status         # none | documented | verified   (GAIA spine grades,
                         #   canon: 2026-06-20 spine:261-275)
  veto_window, revocation_endpoint

S5 EVIDENCE — on what basis
  evidence[] {type, digest, uri, c2pa_manifest?, oracle{did, class, independence_decl}}
  # independence_decl = signed statement of funding/relationship edges
  #   machine rule (CAR-2+): witness_payer ≠ actor_payer   (Isometric buyer-pays —
  #   https://climate-decode.com/insights/vcm-series/vcm-2026-era-of-integrity/isometric-science-first-removals-registry)

S6 ACTION — what was done
  action_type, occurred_at, location?
  ap2_mandate_refs[]     # links into AP2 Intent/Cart/Payment VC chain, if commerce
  tx_refs[]              # x402/ACP/bank/chain settlement refs
  capital {amount, currency, instrument}

S7 OUTCOME — what independently happened
  outcome_claim          # bounded, falsifiable
  witnesses[] {did, class(sensor|human|institutional|algorithmic), independence_decl, sig}
  quorum {n_channels, m_independent, diversity_note}   # ≥3 decorrelated channels for
                         # public-grade claims (anekanta gate — GAIA_ECO framework:208-210;
                         # eDNA literature demands the same triangulation —
                         # https://pmc.ncbi.nlm.nih.gov/articles/PMC12384077/)
  observed_at, durability_checkpoints[]

S8 CHALLENGE — how it can be contested
  status: unchallenged | challenged | upheld | reversed | superseded
  challenge_uri          # REQUIRED even at CAR-0: where to file
  challenge_window_ends
  bond {amount, refund_rule}      # optional anti-spam stake; bounty on success
  arbiter_set_ref                 # named institution(s), not "the community"
  reversal_of? / superseded_by?   # CAR ids — reversal is a NEW receipt; append-only
                                  # ("compost, not trash" — REMOTE_HANDOFF:50)

S9 LEARNING — what the graph gets
  outcome_grade?, graph_edges[] (typed refs to other CARs), review_at

registration:
  scitt_entries[] {log_id, inclusion_receipt}   # ≥1 required from CAR-0
  anchors[] {rfc3161_tsa | opentimestamps | eidas_qeledger_ref}
  freshness_beacon {source, value}              # e.g. peer-log tree head or drand round
```

### 2.2 Signatures and non-backdateability

Non-backdateability is the load-bearing property (7/10 upstream lenses converged on it — MEMORY: upstream-compounding-sweep-2026-07-11) and it is achieved with **zero new cryptography**, by composing four existing mechanisms:

1. **Intra-receipt hash chain.** Each segment embeds the digest of all prior segments; `car_id` = digest of the closed set. No segment can be altered or inserted after closure without changing the id.
2. **Transparency registration (the core).** Every CAR is submitted as a SCITT Signed Statement to at least one transparency service; the returned **inclusion receipt** (countersigned Merkle proof + registration time) is embedded back into the receipt's `registration` block. RFC 9943 already standardizes this — CARP defines only the *profile*: required headers, the CAR content type, and registration policy. Backdating now requires forging a log.
3. **Cross-witnessed checkpoints.** Conformant logs publish signed tree heads on a schedule and **countersign each other's checkpoints** (the Certificate Transparency gossip pattern). A log that silently rewrites history diverges from peer-countersigned checkpoints and is mechanically detectable. This is the federation's immune joint (see 2.5).
4. **Two-sided time bounding.** The optional `freshness_beacon` (a value unknowable before time T — a peer log tree head or randomness-beacon round) proves *not created before* T; the inclusion receipt proves *existed by* T'. A CAR is thus pinned inside [T, T'] by parties who don't trust each other. Optional anchors add legal weight: RFC 3161 timestamps, OpenTimestamps (Bitcoin), and — the sleeper — **eIDAS 2.0 qualified electronic ledgers**, which grant a *statutory presumption of integrity and accurate chronological ordering* across all 27 EU member states (https://digital-strategy.ec.europa.eu/en/faqs/questions-answers-trust-services-under-european-digital-identity-regulation). Nobody has composed that presumption with agent audit trails yet (field_regulatory-dpi.md, whitespace). CARP anchors into an existing QTSP's qualified ledger; it does not become one.

Signature algorithm profile: Ed25519 + ES256 mandatory-to-implement (ES256 because passkeys/WebAuthn and eIDAS certs speak it), COSE_Sign1 envelope, `cnf` binding for delegated keys. Selective disclosure via SD-JWT VC / BBS+ where segments carry personal or commercially sensitive data — a CAR can prove "authorized, within budget, witnessed by 3 independent channels" without revealing the counterparty. This is the anti-ConstitutionDAO clause: naked transparency handed Ken Griffin the bid ceiling (https://news.artnet.com/market/felix-salmon-ken-griffin-constitution-2040093); CARP defaults to *verifiable* not *public*, with publicity a per-segment policy choice.

### 2.3 Identity: ride every existing rail, mint nothing

- **Agents:** DIDs (did:web for institutions, did:key for ephemeral agents, did:plc/did:dht where portability matters — did:plc already runs 43M identities, https://atproto.com/specs/repository) + A2A Signed Agent Cards as the agent-descriptor of record + Web Bot Auth HTTP message signatures for on-the-wire attribution (IETF WEBBOTAUTH WG, milestones Apr/Aug 2026 — https://datatracker.ietf.org/group/webbotauth/about/).
- **Humans:** passkeys as the root of the delegation chain (5B passkeys in use — https://fidoalliance.org/fido-alliance-reports-accelerating-global-passkey-adoption-on-world-passkey-day-2026/). A human root signs the first delegation VC; everything below is attenuation.
- **Legal persons / EU:** eIDAS PID and qualified attestations via EUDI wallets (mandatory 2026-12-24 — same eIDAS FAQ URL above). A CAR whose S1 chain roots in a QEAA is court-grade in 27 states.
- **Delegation semantics:** W3C VC 2.0 credentials with UCAN-style capability attenuation (each link can only narrow scope/budget/expiry). This is deliberately the same shape as AP2's mandate chain — AP2 mandates *are* W3C VCs (https://eco.com/support/en/articles/14845479-ap2-agent-payments-protocol-explained) — so an AP2 Intent Mandate slots into S1/S6 unmodified.
- **Community authority (S4):** communities issue authority credentials from their own registries (a Regen-style multi-stakeholder attestation, an Indigenous council's FPIC credential, a municipal wallet). CARP standardizes the credential *envelope and revocation endpoint*, never the community's internal decision process. This is the anti-Aadhaar clause: identity failure must be **fail-open for humans** — a missing credential downgrades the CAR's profile grade; it never blocks a person from food (https://www.epw.in/engage/article/aadhaar-failures-food-services-welfare).

### 2.4 Conformance ladder (the adoption physics)

Monolithic constitutions don't get adopted; ladders do.

- **CAR-0 "Signed & Registered":** S1 (actor + at least self-delegation) + S2 (intent statement) + S6 + registration + a challenge_uri. One afternoon of integration for anyone with an MCP/A2A log stream. This alone beats every enterprise audit trail on one axis: it is *non-backdateable and third-party verifiable*.
- **CAR-1 "Burdened & Evidenced":** + S3 + S5. Maps to EU GPAI Model Documentation Form's compute/energy fields (the only material-burden field in any regulation — field_agentic-protocols.md whitespace) and AI Act Art. 12-shaped logging.
- **CAR-2 "Witnessed & Challengeable":** + S7 with quorum (≥3 decorrelated channels, witness_payer ≠ actor_payer) + full S8 state machine. This is the grade that MRV, retro-funding, and dispute resolution require.
- **CAR-3 "Constitutional":** + S4 community authority + S9 + durability checkpoints + reversal exercised at least once. The Commons grade.

Challenge state machine (normative at every grade): `REGISTERED → (window) → SETTLED`, or `REGISTERED → CHALLENGED → UPHELD | REVERSED | SUPERSEDED`, where REVERSED/SUPERSEDED mint a *new* CAR pointing back — history is never deleted, only answered. The design principle is SAB's law verbatim: "Correction must be at least as easy as publication" (SAB_DHARMIC_AGORA_REMOTE_HANDOFF_2026-06-11.md:47). No corpse in the graveyard had this organ: The DAO's only reversal was chain schism, carbon markets' only challengers were unpaid journalists, ONDC's named failure was fragmented dispute resolution (field_failure-forensics.md whitespace).

### 2.5 Federation topology: three rings, custody stays local

Empirically, the only durable decentralized pattern is *thin global standard + near-zero node cost* (fediverse survives on Raspberry-Pi economics; ATProto relays re-centralized at ~$512/mo — field_web-evolution.md). CARP's topology:

- **Ring 0 — Grammar (global, tiny, slow):** the CAR schema + CDDL/JSON-LD context, signature/registration profiles, the challenge state machine, witness-independence declaration format, a *minimal* telos registry (a handful of top-level entries; everything deeper is local), conformance test vectors, and ~7 constitutional invariants compiled into the verifier (append-only; challenge_uri required; witness independence machine-checked; fail-open for humans; no CAR grade purchasable; reversal never deletes; local authority credentials never overridden globally). Governed by the standards process itself (IETF/W3C) plus a small stewardship nonprofit. Ring 0 changes are themselves published as CARs — the protocol's own governance eats its own receipts.
- **Ring 1 — Logs (many, federated, cheap):** SCITT-profile transparency services run by anyone — bioregions, domains, registries, companies. Requirements: publish signed checkpoints, countersign ≥2 peer checkpoints per epoch, serve inclusion/consistency proofs. Target node cost: one small VPS. Logs are *dumb*: they order and prove, they never judge. Multiple registrations of one CAR across logs is encouraged (multi-homing against capture — the Auroville lesson: any single wrapper becomes the takeover instrument, https://www.livelaw.in/top-stories/auroville-residents-have-no-right-to-be-part-of-councilcommittee-formed-by-foundations-governing-body-supreme-court-286621).
- **Ring 2 — Custody (local, sovereign, thick):** community registries issuing S4 authority credentials and defining legitimate benefit; local arbiter institutions running challenge desks; local telos taxonomies. Higher rings coordinate but cannot override lower-ring legitimate autonomy — Levin/Beer multiscale competency as constitutional structure, which is also the prepared answer to the technocratic-planetary-management critique (https://onlinelibrary.wiley.com/doi/10.1002/bies.202400196; the Gaian critique named in field_planetary-computation.md).

The **outcome graph** (the "planetary intelligence that learns") is a Ring-2+ *read model* computed over CARs — explicitly a projection, never an authority, exactly per canon: "Read models project truth from owners; they do not become authority" (ACTIVE_TRACK.yaml:163-164). Anyone can compute one; nobody owns the canonical one. Friston's federated-inference math is the right formalism for it (https://pmc.ncbi.nlm.nih.gov/articles/PMC11139662/) — borrowed math, with CARP supplying the consent/authority/challenge normativity it lacks.

### 2.6 What gets standardized vs. what stays implementation

**STANDARDIZED (Ring 0):** the CAR segment schema and canonical encoding; signature + envelope profile; SCITT registration profile + inclusion-receipt embedding; the challenge state machine and its status vocabulary; witness classes + independence-declaration format; delegation-chain attenuation rules; conformance grades CAR-0..3 + test vectors; the ~7 invariants.

**IMPLEMENTATION (Rings 1-2, deliberately unstandardized):** telos taxonomies beyond the minimal registry; gate logic and fitness scoring (dharma_swarm's 25 axioms / 11 gates remain *one implementation's* conscience — the contemplative spine "is the immune system… NOT the product," OPERATIONAL_DOCTRINE.md:32); arbiter institutions and their procedures; witness selection and pricing; reputation and ranking; storage and retention; UI; the outcome-graph learners; obligation routing (SIS's reciprocity economics); community governance internals. VERSES' corpse is the tombstone for standardizing metaphysics: $154M deficit, $68K cash, going-concern doubt after leading with ontology (https://www.stocktitan.net/sec-filings/VRSSF/10-q-verses-ai-inc-quarterly-earnings-report-e7af8324e91e.html). CARP standardizes the *evidence grammar* and lets a thousand judgments bloom.

### 2.7 Riding the existing stack (adapter map)

- **AP2 (FIDO):** CAR = superset of the mandate chain. S6 references Intent/Cart/Payment VCs; CARP extends *upstream* (delegation root, telos, authority) and *downstream* (burden, witnessed outcome, challenge). Pitch inside FIDO's Agentic Authentication TWG as "Verifiable Intent, completed" — before they generalize it themselves (the #1 encroachment threat, field_agentic-protocols.md).
- **MCP/A2A (Linux Foundation):** an MCP middleware that turns tool-call logs into CAR-0 emissions; an A2A extension field on Agent Cards declaring CAR conformance grade + receipt endpoint. MCP's 2026 roadmap already wants "audit trails" (https://www.anthropic.com/news/donating-the-model-context-protocol-and-establishing-of-the-agentic-ai-foundation) — supply the cross-boundary version before per-vendor logs ossify.
- **ERC-8004:** validation-registry entries point at CAR URIs. The first empirical study found 3-15% of registrations operationally valid and 59-91% sybil feedback (https://arxiv.org/pdf/2606.26028) — CAR-backing is the fix their own data begs for.
- **C2PA:** manifests ride inside S5 as evidence payloads; CARP is to *actions* what C2PA is to *media*, and the positioning explicitly copies C2PA's path (open spec → regulation names it by example, AI Act Art. 50).
- **SCITT (IETF):** the registration substrate itself; CARP's normative deliverable #1 is literally an internet-draft: *"A SCITT Profile for Causal Action Receipts."*
- **Beckn:** CAR as the fulfillment/post-fulfillment attestation on open-network transactions; adopt the FIDE playbook — own the grammar, let integrators carry deployment (Beckn Onix via Google Cloud — https://www.googlecloudpresscorner.com/2025-11-03-Beckn-Labs-and-Google-Cloud-Partner-to-Accelerate-the-Adoption-of-Open-Networks-Worldwide-with-Beckn-Onix).
- **Regen Registry 2.0 / MRV:** ecological claims ingest as S5/S7 payloads (https://carbon-pulse.com/325435/); Isometric's buyer-pays verifier independence is adopted wholesale as the S5/S7 independence rule.
- **Spatial Web (IEEE 2874) / GeoPose:** interop target for S6 location semantics; never a rebuild.

### 2.8 The three interop demos (what makes protocol people look up)

1. **"Sign my agent's day" — the SCITT demo (IETF audience).** Instrument dharma_swarm's own MCP/A2A dispatch so every action emits a CAR-0 into a live public transparency log; ship `carp verify` (a single-binary CLI) so anyone can check any receipt; include a **red-team test vector where a backdating attempt fails verification**. The first organism that audits itself in public — no consortium can fake it, and IETF people respect running code + failing test vectors over any manifesto.
2. **"AP2 for consequences" — the FIDO demo (payments/identity audience).** A real agent purchase whose AP2 mandate chain is extended into a full CAR: delegation root above the Intent Mandate, witnessed delivery outcome below the Payment Mandate, then a **live challenge filed and a reversal CAR minted** when the outcome is wrong. Demonstrates the dispute organ nobody in the payment-protocol war (Visa TAP vs AP2 vs x402 vs ACP) owns — which is precisely why a neutral commons can own it (field_positioning-funding.md whitespace: "Switzerland" positioning).
3. **"Grounded reputation" — the ERC-8004 demo (crypto + academic audience).** Take live ERC-8004 feedback on Base (90.6% sybil per the study), publish a bridge that accepts only CAR-backed feedback, and show the validated subset with the sybil rate collapsing. Reproducible, quantified, citable — and it recruits the converging academics (Notarized Agents, DEMM — https://arxiv.org/pdf/2606.04193) as co-authors rather than competitors.

(The nature-restoration receipt — a Regen claim wrapped as CAR-2 with satellite + local human + registry witnesses and a real challenge window — is demo #4, aimed at the Living Earth Digital Twin workshop Sept 14-16, 2026 (https://livingearthtwin.org/), but it is a *domain* demo; the three above are the *protocol* demos.)

---

## 3. What Exists To Build On

**In the estate (verified on disk or in canon):**
- `dharma_swarm/spine/receipt.py:37` — `EvidenceReceipt`, frozen dataclass, one-per-dispatch, with identity (agent_id, agent_card_version), invocation (provider/model/operation), outcome (status/error taxonomy/latency), cost (tokens, cost_usd), and correlation identity — read directly this session. It is CAR segments S1+S3(partial)+S6 in production, **unsigned**. Its own track law already forbids schema churn ("Do not change EvidenceReceipt schema" — ACTIVE_TRACK.yaml:624), which is fine: CARP *wraps* it (sign + register the serialized receipt) rather than mutating it.
- The GAIA 9-step packet path — measurement → obligation → qualification → routing → evidence/audit → challengeable public claim → adaptive review (2026-06-20 spine:41-42, per canon_sis-gaia.md) — the estate's strongest CAR prototype, with consent grades, ≥3-channel rule, and 5/10/30-day challenge SLAs already specified (2026-06-20 spine:261-275). All six GAIA runtime modules exist on disk; the one failing test is on the claim-challenge path — telling, and first to fix.
- SAB/Agora's lifecycle (submitted→queued→published→challenged→canonized→composted→superseded) and its laws — the challenge state machine's seed (REMOTE_HANDOFF:47-52).
- One Wire + quorum doctrine (N≥5, M≥3) already ratified (ACTIVE_TRACK.yaml:680-684); the `web-4-0-trust-substrate` cell already declared ENVISIONED with exactly this role: "the verification protocol for the internet of agents" (VENTURE_CELL_PORTFOLIO.yaml:143-147).
- Sober counter-facts: spine adoption self-audited 54/100 with the 88/100 claim rejected; receipt DB dirty (0.0% provider proof on old rows); Loop 1 unclosed (canon_ops-reality.md). **Sign forward, never backfill** — see kill list.

**In the world (all cited above):** SCITT RFC 9943; W3C VC 2.0 / DID 1.1; AP2 v0.2 at FIDO; A2A v1.0 at LF; MCP at LF AAIF; Web Bot Auth WG; C2PA; eIDAS 2.0 qualified ledgers + EUDI wallets; passkeys at 5B; Regen Registry 2.0; Isometric's independence mechanics; Beckn Onix; ERC-8004 (as a cautionary dataset); OpenTimestamps/RFC 3161; the Levin/Beer/Friston formal lineage.

---

## 4. Sequencing From Here (solo operator, month 1 → year 10)

The constraint is absolute: one person, no entity, ~zero revenue, spine partly uncommitted. The sequence therefore front-loads *artifacts a solo can finish* and defers everything that needs institutions until institutions are pulled in by artifacts.

**Month 1 (July 2026) — Sign the spine; file the funding.**
- Wrap `EvidenceReceipt` serialization in Ed25519 signing + a local Merkle log with published checkpoints (a SCITT-profile-shaped log, even if not yet a conformant service). New receipts only, with an explicit signed genesis statement acknowledging the pre-signing corpus as historical/unwarranted. This is the 7/10-converged move.
- Publish CAR v0.1: schema draft (CDDL + JSON-LD context), `carp verify` CLI, 20 test vectors including the failing-backdate vector. GitHub + a one-page site. No manifesto.
- Longview Digital Minds RFP concept email by 07-14, submission by 07-22 (deadline 07-24 — https://forum.effectivealtruism.org/posts/ToC8jpgdwFJGtfw7C/new-round-of-digital-minds-funding-opportunities-at-longview); SFF speculation grant within 2 weeks framed as "the challenge-and-reversal layer, demonstrated before 08-02" (https://survivalandflourishing.fund/speculation-grants). Vision lives in appendices; the artifact leads.

**Months 2-3 (Aug-Sep) — Demo 1 live before/around the enforcement date; entity; standards ingress.**
- Demo 1 public: dharma_swarm's live self-audit log + verifier, timed to EU GPAI *enforcement powers* activating 2026-08-02 (cite precisely: Art. 50 transparency + Commission fines; Annex III high-risk deferred to 2027-12-02 by the Digital Omnibus — https://www.gibsondunn.com/eu-ai-act-omnibus-agreement-postponed-high-risk-deadlines-and-other-key-changes/). Never sell 08-02 as a cliff; sell non-backdateable evidence as court-and-regulator durable.
- Form the FIDE-shaped nonprofit (the recurring structural blocker: DPG Indicator 3, OpenAI fund, SFF sponsor — field_regulatory-dpi.md, field_positioning-funding.md). Two-jurisdiction custody plan from day one (Auroville clause).
- Submit *draft-carp-scitt-profile-00* to IETF SCITT; join W3C AI Agent Protocol CG (free, open to individuals); LTFF application (rolling, individuals OK — https://funds.effectivealtruism.org/funds/far-future). Living Earth Digital Twin workshop Sept 14-16 for the restoration domain door.

**Months 4-6 (Oct-Dec) — Demos 2 & 3; first money; NLnet.**
- Demo 2 (AP2 extension w/ live reversal) and Demo 3 (ERC-8004 CAR-backed feedback bridge), each with a co-author recruited from the converging academics. NLnet/NGI Open Internet Stack 2-pager for the Oct-Dec window ("trust: AI-based agents, trusted identities" is in scope — https://nlnet.nl/news/2026/20260601-call.html).
- First revenue: the $500-5,000 **agent-audit attestation** — a third party (the operator's verifier + a named human reviewer) countersigns a deployer's CAR stream for a period, producing a challengeable attestation. Rides PLD strict-liability transposition (due 2026-12-09 — https://www.twobirds.com/en/insights/2026/france/ai-liability-in-light-of-the-new-2024-pld-expanded-liability-challenging-defences-and-new-evidentiar) and EUDI wallet mandate (2026-12-24). Revenue rule fixed forever: **fees scale with receipts examined and challenges processed, never with approvals granted** (the anti-Verra invariant).

**Months 7-12 (2027 H1) — Restoration pilot; qualified-ledger anchor; conformance suite.**
- One CAR-2 restoration pilot with a verification-starved partner (BioFi/Salmon Returns-class, or a Regen project), 3 decorrelated witnesses, a real challenge window — inside the CRCF registry gap (methodologies in force 2026-05-07, EU registry only Dec 2028 — https://tracker.carbongap.org/policy/crcf/).
- Partner one QTSP to anchor CARP checkpoints in an eIDAS qualified ledger. Publish CAR-0/1 conformance suite; second independent implementation (a grantee or academic, funded by the grants above). DPG registration (type: Standard).

**Year 2 (2027) — Federation v1; the Challenge Desk; three implementations.**
- ≥3 independent transparency logs cross-countersigning checkpoints (one run by the nonprofit, two by others — a university, a registry). Stand up the first named arbiter institution: **the Challenge Desk** (SAB's process, real cases, published case law — the "seeded exemplary canon" SAB never got, REMOTE_HANDOFF:60). Three interoperating implementations = the IETF credibility bar; W3C CG report published. Revenue: attestation practice + per-log support + grants.

**Years 3-5 — Custody ring; outcome graph v1; the C2PA move.**
- Bioregional authority-credential pilots (Ring 2): 3-5 communities issuing S4 credentials under their own governance, with exercised veto/revocation — the *working local-veto demo* that answers the technocratic critique (field_planetary-computation.md threats). Beckn-network and cloud-integrator deployments carry distribution. Outcome graph v1 published as an open read model over ≥100K CARs (restoration + agent-audit domains), with durability checkpoints feeding S9. Target: a code of practice or procurement rule *names CARs by example* (as AI Act Art. 50 guidance names C2PA). Endowment + reciprocity-license revenue model to escape Matrix-style commons starvation (https://matrix.org/blog/2025/02/crossroads/).
- Operator succession plan executed and published: multi-homed custody, named successors, schism procedure — because internal schism is the documented entry wedge for capture (Auroville).

**Years 5-10 — The Commons as boring infrastructure.**
- CAR grades appear in insurance underwriting for autonomous agents, in restoration finance disbursement, in liability defense (AB 316-class regimes bar the "AI did it" defense — https://www.cliffordchance.com/insights/resources/blogs/talking-tech/en/articles/2026/02/agentic-ai-and-the-liability-gap-your-contracts-may-not-cover.html). Ring 0 governance runs on its own receipts; the founder is optional (the Loomwork B6 test: "What survives: the primitives" — MASTER_loomwork_level_100.md:133). The peoples-governance noosphere the operator seeded arrives not as a parallel state but as the *evidence layer traditional structures themselves come to depend on* — the parallel lane that interoperates so well it becomes load-bearing. If traditional structures do give way, a federated, community-custodied, challenge-native coordination grammar is already running at scale. That is the honest version of Web5.

---

## 5. The First Wedge

**Sign the receipt spine, in public, before 2026-08-02 — then sell the notarization of other people's agents.** Concretely: (1) Ed25519-sign every new dharma_swarm EvidenceReceipt into a checkpointed Merkle log with a public verifier; (2) publish CAR v0.1 + `carp verify` + the failing-backdate test vector as the spec's genesis artifacts; (3) convert to revenue as the agent-audit attestation for GPAI-touched deployers under Art. 50 + PLD evidence-disclosure pressure. The wedge is credible precisely because it is self-implicating: the first customer is the operator's own organism, whose 54/100 self-audit and rejected 88/100 claim (canon_ops-reality.md) are *published in the log* — the credibility artifact no corpse in the graveyard ever produced (field_failure-forensics.md opportunities: "gates binding the founder first"). SIS enters commercially through S3: the compute/energy fields map onto the GPAI Model Documentation Form, the only regulation-shaped material-burden hook in the entire stack. Everything else — restoration, federation, the noosphere — sequences behind a wedge one person can ship in weeks with tools already on disk.

## 6. Boldest Claim

Within five years, **no consequential autonomous action will be insurable, procurable, or legally defensible without a signed, registered, challengeable receipt** — the liability regimes arriving 2026-2028 (AI Act enforcement, PLD strict liability, AB 316) already presuppose exactly this evidence and nothing in the A2A/MCP/AP2 stack produces it. The schema that fills the gap will be a SCITT profile, not a platform; and the party best positioned to author it is not Google or FIDO but whoever *notarized themselves first* — because an evidence commons, unlike a payments network, derives authority from demonstrated self-subjection, and a solo operator with a public self-audit log possesses the one asset no consortium can purchase: a receipt trail that begins before there was anything to gain by faking it. The Causal Action Receipt is to agent actions what TLS+Certificate Transparency was to server identity — and the window before an incumbent generalizes Verifiable Intent is 12-24 months (field_agentic-protocols.md).

## 7. What Would Kill This

1. **Notarizing the dirty corpus.** Signing the existing receipt DB (0.0% provider proof) would weld the credibility asset to a falsifiable record. Kill-avoidance: sign forward only, genesis statement quarantining history. Sequencing conflict with ACTIVE_TRACK non-goals ("no new receipt systems", ACTIVE_TRACK.yaml:222-224) is real and needs an operator-opened track — canon requires it (canon_ops-reality.md open questions).
2. **Receipt-Goodhart.** If verification revenue ever scales with approvals, CARP becomes carbon credits within one market cycle (Verra: ~90% phantom — https://www.ecowatch.com/phantom-credits-verra.html). The fee rule (pay per examination/challenge, never per approval) must be a Ring 0 invariant, not a policy.
3. **Incumbent generalization.** FIDO extends Verifiable Intent from "authorized purchase" to "authorized action," or Cloudflare productizes edge-witnessed receipts, before CARP has three implementations. Mitigation is speed + positioning *inside* their venues (the AP2-superset demo), not competition.
4. **Custody inversion.** A single legal wrapper or single log becomes the takeover instrument (Auroville's 33-year fuse). Mitigation: multi-homed entity, many logs, cross-countersigned checkpoints, published succession.
5. **Manifesto-first framing.** "Web 5.0" is doubly burned (Dorsey's dead brand + fringe usage — https://www.cnbc.com/2024/11/08/jack-dorsey-dramatically-shutters-blocks-tbd-crypto-unit.html); "planetary constitutional nervous system" pattern-matches to crank filters and to VERSES' $154M ontology grave. The framing ships as an IETF draft and a CLI; the cosmology stays in the appendix.
6. **Token/tradeable-receipt trap.** Receipts as speculative units replay Toucan/KlimaDAO (KLIMA −99.94% — https://carbonplan.org/research/toucan-crypto-offsets). CARs are evidence, never instruments; obligations route through S3, value accrues to verified outcomes and reputation.
7. **Exclusion harm.** Fail-closed identity tied to entitlements reproduces Aadhaar's starvation boundary and forfeits moral legitimacy permanently. Fail-open-for-humans is a compiled invariant.
8. **Solo-operator arithmetic.** No entity (blocks DPG/most funders), one person against funded encroachers, and — canon's own circular bottleneck — the operator's outreach HOLD blocks the external witnessing the One Law requires (canon_telos.md open questions). If the trust gate doesn't open for at least the three demos and two grant applications, the protocol dies unwitnessed regardless of technical merit. UNVERIFIED whether the HOLD extends to standards-body participation; this is the first operator decision to force.
9. **Witness-mesh cost creep.** If running a log or witnessing costs more than a hobbyist can bear, the federation quietly recentralizes (ATProto relay economics). Node-cost budgets are published, tested, and versioned with the spec.
10. **Date-hype backfire.** Selling 2026-08-02 as a universal compliance cliff (it is GPAI enforcement + Art. 50; Annex III slipped to Dec 2027) would burn credibility with the exact regulatory audience the wedge courts. Cite the Omnibus precisely, always.

---

*Reference implementations seed: `dharma_swarm/spine/receipt.py` (EvidenceReceipt, verified on disk 2026-07-11), GAIA packet path, SAB lifecycle. Full evidence base: canon_*.md and field_*.md in this directory.*
