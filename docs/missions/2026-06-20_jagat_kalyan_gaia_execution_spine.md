# Jagat Kalyan / GAIA Execution Spine

Date: 2026-06-20
Updated: 2026-06-26
Status: hardened execution spine
Thread: architectural
Mission: Build ecological restoration coordination for AI carbon offset

## Purpose

Turn the Jagat Kalyan / GAIA thesis into one bounded execution target:

**prove one auditable pilot loop from AI activity to obligation, qualified
restoration, livelihood routing, verified evidence, challengeable public claim,
and adaptive review.**

This is the correct next move because the repository already ships a real GAIA
trust kernel plus standards-aligned intake scaffolding, but it still lacks the
external evidence discipline, challenge workflow, and operator ownership needed
for a credible live pilot.

## Current Decision

- Use the in-repo GAIA kernel as the only executable Phase 1 authority.
- Treat `~/jagat_kalyan` and other missing external stack references as
  continuity-only until restored.
- Do not build a marketplace, broad dashboard suite, or generalized coalition
  platform first.
- Keep recognition-native / fixed-point machinery optional and bounded. It may
  refine qualification or contradiction handling, but it may not replace the
  typed proof chain or become the outer platform backbone.

## Authority And Scope

Use as governing inputs:

- `docs/governance/SOVEREIGN_MANIFEST.md`
- `docs/missions/anthropic-economic-futures-submission-2026-03-21/anthropic_grant_application_submission_ready_2026-03-21.md`
- `docs/reports/JAGAT_KALYAN_RECIPROCITY_COMMONS_2026-03-11.md`
- `docs/reports/GAIA_ECO_ARCHITECTURE_2026-03-27.yaml`
- `docs/reports/GAIA_PUBLIC_CLAIM_EXPLORER_SPEC_2026-03-27.md`
- `docs/reports/PLANETARY_RECIPROCITY_COMMONS_GOVERNANCE_CHARTER_2026-03-11.md`

Use as live runtime authority:

- `dharma_swarm/ai_reciprocity_ledger.py`
- `dharma_swarm/gaia_ledger.py`
- `dharma_swarm/gaia_verification.py`
- `dharma_swarm/gaia_fitness.py`
- `dharma_swarm/gaia_platform.py`
- `dharma_swarm/evaluation_registry.py`

Use as standards-aligned adapter candidate, not primary packet authority yet:

- `dharma_swarm/gaia_initiative.py`

Use as continuity, not authority:

- `docs/dse/JAGAT_KALYAN_MASTER_VISION.md`

## Exact Runtime Packet Path

Phase 1 should run through the tested intake/report chain, not a new parallel stack:

1. `GaiaPilotIntake`
2. `GaiaPlatform.qualify_intake()`
3. `GaiaQualificationDecision`
4. `GaiaPlatform.build_intake_pilot_report()`
5. `GaiaClaimCard` + report artifacts + `AIReciprocityLedger` projection into
   `GaiaLedger`
6. monitoring, feedback, and remediation review

Optional upstream adapter, only when intentionally integrated and verified:

- `GaiaPilotMeasurementContract`
- `GaiaRestorationInitiative`
- `GaiaInitiativePilotPacket`
- `GaiaInitiativePilotPacket.to_pilot_intake()`

If work cannot be expressed through this chain, it is not Phase 1 execution. It
is either upstream research or downstream expansion.

## Hard Publication Invariant

No public ecological claim without:

- a bounded claim statement
- `methodology_ref`
- visible integrity class
- evidence path
- audit status
- challenge path
- explicit consent status when communities, land access, local knowledge, or
  livelihood claims are implicated

If any item is missing, the pilot may remain `internal_only` or `provisional`,
but it may not be published as `public_ready`.

## Success Condition

The mission is complete only when one pilot can move from compute exposure to a
challengeable report without hand-waving at any point in the chain.

That means:

- one measured, estimated, or disclosed compute source, labeled honestly
- one reproducible obligation rule
- one standards-aligned restoration initiative packet
- one credible operator and one credible community partner
- one typed livelihood target group
- one routed funding event bounded by obligation
- one evidence bundle and one audit path
- one public or provisional claim card with visible challenge state
- one adaptive review packet with explicit owner and next action

## Workflow

| Step | Main artifact | Accept when | Depends on | Owner lane | Escalate when |
|---|---|---|---|---|---|
| 0. Scope freeze | pilot charter | sponsor class, project archetype, worker cohort, reporting period, and non-goals are fixed | governing docs | director / governance | scope expands into marketplace or universal-coverage language |
| 1. Measurement contract | `GaiaPilotMeasurementContract` | `measurement_mode`, `measurement_ref`, energy basis, carbon intensity, and `obligation_rule` are explicit | sponsor disclosure or metering source | metering / sponsor ops | compute basis cannot be measured honestly or challenged |
| 2. Initiative packet | `GaiaRestorationInitiative` | operator, area, methodology, partner diligence, consent, indicators, and verification channels are populated | project operator + community partner | initiative / partner diligence | operator, land rights, or benefit-sharing posture is unclear |
| 3. Packetization | `GaiaInitiativePilotPacket` | contract and initiative compose without blank critical fields; standards profile is explicit | steps 1-2 | integration / spec lane | required packet fields must be guessed |
| 4. Qualification gate | `GaiaPilotIntake` + `GaiaQualificationDecision` | intake clears measurement, partner, consent, and challengeability gates; visibility class is defensible | packet created | higher-trust review lane | partner credibility, consent, challenge contact, or verification mesh is weak |
| 5. Routing + ledger | `RoutingRecord` + `LivelihoodRecord` + `GaiaLedger` projection | routed value is bounded by obligation and every livelihood record points to the project | qualification approved | accounting / operator lane | obligation outruns routed value or livelihood path is nominal only |
| 6. Verification + audit | `EvidenceRecord[]` + `OutcomeRecord` + `AuditRecord` | evidence, oracle diversity, and audit exist before any verified ecological claim | routing complete | audit / evidence lane | evidence collapses to one channel or no independent audit exists |
| 7. Claim publication | `GaiaClaimCard` + intake report | claim traces the full chain and exposes integrity class, consent, challenge, and audit state | prior steps complete | publication / governance | narrative pressure outruns proof quality |
| 8. Adaptive review | monitoring snapshot + feedback + remediation decision | one post-claim review records drift, dissent, remediation, or continuation | claim issued | review / governance | negative signals exist but no owner is assigned |

## Acceptance Criteria By Lane

### Phase 0: Scope Freeze

Accept when:

- the pilot names one system boundary
- non-goals are explicit
- no public language implies a marketplace or broad coordination platform

Fail when:

- buyer class, project type, or reporting period remain open-ended

### Phase 1: Measurement Lane

Accept when:

- every packet has `measurement_mode`
- every packet has non-blank `measurement_ref`
- disclosed estimates are not mislabeled as direct metering
- the obligation rule is reproducible from the disclosed inputs

Fail when:

- energy basis is ambiguous
- internal and external obligation logic differ

### Phase 2: Initiative And Qualification Lane

Accept when:

- the initiative names operator, geography, integrity class, methodology, and
  partner
- partner diligence is explicit
- `challenge_contact` is present
- fewer than three verification channels blocks `public_ready`
- unresolved consent blocks `high_integrity`

Fail when:

- the project is ecologically plausible but socially extractive
- the project is socially strong but unverifiable

### Phase 3: Routing Lane

Accept when:

- every routed unit points to one project
- every livelihood record points to one target group
- projection into `GaiaLedger` produces no invariant violation

Fail when:

- obligation exists without actual routing
- ecological routing occurs without livelihood pathway

### Phase 4: Verification And Audit Lane

Accept when:

- every verified ecological outcome has evidence and audit
- dissenting oracles remain visible
- quantified ecological claims use the current 3-of-5 oracle threshold for
  `high_integrity`

Fail when:

- outcome is presented as verified on evidence alone
- audit exists but the evidence path is broken

### Phase 5: Claim Publication Lane

Accept when:

- every claim states methodology
- every claim exposes integrity class, audit status, challenge status, and
  consent state
- proxy-only claims remain `experimental` or `emerging`
- any material challenge, grievance, or consent dispute blocks promotional
  wording

Fail when:

- a public card implies certainty beyond evidence quality
- reversal or disagreement is hidden behind refreshed summaries

### Phase 6: Adaptive Review Lane

Accept when:

- at least one post-routing monitoring checkpoint exists
- operator, community, and audit feedback can remain separate
- remediation or continuation is explicitly assigned

Fail when:

- the report is produced once and never reviewed
- negative feedback is summarized away

## Success Metrics

The first packet is good enough when all of the following are true:

- `measurement_mode` is honest on every packet
- `challenge_contact` is non-blank on every publishable packet
- `len(verification_channels) >= 3` for any `public_ready` claim
- `partner_credibility == credible` for any `public_ready` claim
- consent is at least `documented` for qualification and `verified` for any
  `high_integrity` public claim
- `total_routed_usd <= total_obligation_usd`
- every public or provisional claim has at least one evidence ref and one audit
  ref
- one monitoring checkpoint and one feedback packet exist within the first
  review window
- if the public challenge path is live, it meets the default 5/10/30-day
  acknowledge / triage / initial-finding service levels

## Core Dependencies

| Dependency | Why it matters | Minimum acceptable state |
|---|---|---|
| sponsor activity source | grounds the obligation | metered, disclosed, or estimated with explicit labeling |
| obligation rule | prevents narrative drift | formula or policy text reproducible from the packet |
| restoration operator | carries delivery risk | named operator with diligence reference |
| community partner | prevents extractive routing | named partner with benefit-sharing and grievance references |
| verification mesh | makes claims challengeable | at least three distinct channels for public-ready claims |
| evidence storage | preserves auditability | stable references or hashes for source bundles |
| audit lane | prevents verification theater | named review path outside the operator’s self-assertion |
| governance owner | prevents fake completion | named owner for publication, challenge triage, and remediation |

## Escalation Matrix

| Signal | Why it matters | Immediate action |
|---|---|---|
| compute basis is estimated but presented as measured | trust breaks at step one | relabel as `estimated` or `disclosed`, or halt intake |
| fewer than three verification channels | public claim is not challengeable enough | hold at qualification; downgrade visibility |
| partner credibility is `unknown` or `provisional` without rationale | capital may route into a weak operator | freeze approval and escalate to governance |
| consent is `pending`, `unknown`, `disputed`, or `withdrawn` | social harm risk outruns pilot value | block `public_ready`; open remediation or halt |
| `challenge_contact` is missing | the claim cannot be challenged | block qualification output |
| routed value exceeds obligation | breaks accounting integrity | reject routing packet and repair before projection |
| evidence exists without independent audit | creates verification theater | keep claim provisional and block `verified` language |
| material grievance or challenge appears after publication | public credibility is at risk | freeze promotional wording; move to remediation state |
| review owner is absent after adverse signals | the adaptive loop is fake | stop scale decision until ownership is assigned |
| recognition-native refinement hits cap, diverges from fallback, or changes a gate outcome without stable explanation | hidden solver behavior can silently become authority | downgrade to advisory-only, force deterministic fallback, and open architecture review |

## Recognition-Native Architecture Stance

Recognition-native systems for this mission should be built as governed hybrids,
not `DEQ-first everywhere`.

Use:

- explicit typed state transitions for public accountability
- explicit retrieval and evidence binding for contradiction handling
- recurrent / SSM / attention hybrids for efficient internal propagation
- fixed-point or equilibrium refinement only where convergence has semantic
  meaning: claim qualification, contradiction resolution, audit triage, or
  policy compilation

Do not use:

- equilibrium machinery as the outer GAIA proof-chain backbone
- learned fixed-point scores as direct authority for publication, fitness, or
  promotion
- opaque attention-alternative trunks as a substitute for challengeable
  evidence paths

If a refinement block is introduced, it must emit:

- residual norm
- iteration count
- warm-start delta
- cap-hit or timeout state
- fallback path

### Architecture Routing Matrix

| Need | Preferred mechanism | Why | Required guardrails | Keep out of |
|---|---|---|---|---|
| public proof-chain state, consent, audit, claim visibility | typed packet + explicit rules | this is the challengeable authority boundary | deterministic transitions, provenance, human-reviewable diffs | DEQ scores, latent heuristics, opaque rankers |
| evidence assembly, contradiction preflight, policy lookup | retrieval + graph/rule compilation | traceability matters more than learned compression here | source refs, hashable artifacts, contradiction surfacing | end-to-end latent routing without source visibility |
| cheap internal propagation across long histories | recurrent / selective SSM / hybrid linear-attention blocks | cheaper than full attention for long-horizon internal state movement | bounded context windows, latency telemetry, fallback summaries | publication decisions and final claim authority |
| global synthesis across small or medium evidence sets | explicit attention or retrieval-augmented attention | cross-document binding still benefits from content-addressable mixing | fixed input set, visible citations, bounded output schema | replacing ledger/accounting invariants |
| qualification stabilization, contradiction resolution, audit triage | bounded fixed-point / DEQ refinement block | equilibrium semantics are useful when the task is "settle under constraints" | residual norm, iteration count, warm-start delta, cap-hit state, deterministic fallback | direct publication, consent adjudication, ecological fitness authority |
| offline model understanding and calibration | mechanistic tools such as TransformerLens and causal patching | useful for internal calibration and drift hunting | holdout tasks, offline-only use, no production write authority | Phase 1 shipping dependency |

### Promotion Gate For Recognition-Native Modules

Any recognition-native module stays `provisional` unless all of the following
are true:

- it improves one bounded holdout task tied to a named spine step
- its convergence or rollout telemetry is recorded per run
- a deterministic fallback path exists and can be forced by policy
- fallback disagreement is inspectable after the fact
- it cannot directly set `public_ready`, `high_integrity`, consent status, or
  audit status
- disabling it does not break the outer proof chain

Promote such a module only as an inner optimization lane. Do not promote it to
mission authority.

Phase 1 ecological authority remains external evidence, audit, consent,
challengeability, and typed accounting. Recognition-native machinery can assist
those lanes, but it does not replace them.

## Cheap Lanes Vs High-Trust Lanes

Route outward to cheaper lanes:

- standards comparison
- candidate project research
- evidence packet assembly
- report drafting
- test fixture construction

Keep in higher-trust lanes:

- obligation rule approval
- partner qualification signoff
- consent and grievance adjudication
- integrity-class publication decisions
- audit acceptance
- remediation closure

## Non-Goals

- no carbon marketplace
- no generalized credit issuance engine
- no autonomous land management
- no public impact narrative without challengeability
- no platform rewrite
- no requirement that recognition-native substrate R&D ship before one honest
  pilot packet

## Immediate Packet Order

Build in this order:

1. `pilot charter + non-goals`
2. `GaiaPilotMeasurementContract`
3. `GaiaRestorationInitiative`
4. `GaiaInitiativePilotPacket`
5. `GaiaPilotIntake` + `GaiaQualificationDecision`
6. routed ledger + evidence + audit packet
7. claim card + pilot report
8. adaptive review + remediation note

## Acceptance Bar For Mission Completion

This mission is complete when the repo can show one real or credibly staged
pilot packet with:

- the full path from activity to obligation to qualification to routing to
  evidence to audit to claim
- explicit livelihood participation
- visible integrity class, challenge state, and consent state
- no broken accounting invariants
- at least one adaptive review loop

Anything less is still architecture or research, not ecological restoration
coordination.
