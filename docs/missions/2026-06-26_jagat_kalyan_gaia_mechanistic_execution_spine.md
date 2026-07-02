# Jagat Kalyan / GAIA Mechanistic Execution Spine Addendum

Date: 2026-06-26
Status: scoped addendum
Thread: mechanistic
Mission: Build ecological restoration coordination for AI carbon offset
Extends: `docs/missions/2026-06-20_jagat_kalyan_gaia_execution_spine.md`

## Purpose

Bind the mechanistic `R_V` thread to the ecological mission without letting it
expand or distort the Phase 1 packet.

Core decision:

**the ecological Phase 1 packet remains a proof-chain packet first; mechanistic
work is an internal calibration and contradiction-hunting lane unless the
director explicitly promotes it.**

## Authority Order

1. `docs/missions/anthropic-economic-futures-submission-2026-03-21/anthropic_grant_application_submission_ready_2026-03-21.md`
   - governing outward scope: exploratory empirical study, not platform launch
   - governing public-safe mechanistic summary: `~400 measurements`, `6 architectures`, activation patching `Cohen's d = -2.26`, `32/39` FDR-significant, `AUROC = 0.909`
2. `docs/missions/2026-06-20_jagat_kalyan_gaia_execution_spine.md`
   - governing ecological proof-chain order
3. `docs/reports/JAGAT_KALYAN_RECIPROCITY_COMMONS_2026-03-11.md`
   - governing public thesis and anti-greenwashing law
4. live runtime authority
   - `dharma_swarm/ai_reciprocity_ledger.py`
   - `dharma_swarm/gaia_platform.py`
   - `dharma_swarm/gaia_ledger.py`
   - `dharma_swarm/gaia_verification.py`
   - `dharma_swarm/gaia_fitness.py`
5. historical continuity only
   - `docs/dse/JAGAT_KALYAN_MASTER_VISION.md`
   - `docs/reports/session_2026-03-08/DGC_BRIEFING_FOR_AI.md`

## Scope Decisions

- Keep the ecological mission boundary unchanged: `measurement -> obligation ->
  qualification -> routing -> evidence/audit -> public claim -> adaptive review`.
- Attach mechanistic work after verification and before adaptive review as an
  internal calibration lane, not as a public-claim prerequisite.
- Treat `gaia_observer_function()` and `detect_goodhart_drift()` as the live
  ecological self-observation seam.
- Treat stronger Phase 1 continuity numbers as non-authoritative until the raw
  report path is restored locally.
- Treat SAE decomposition as optional external tooling, not a Phase 1 blocker.

## Contradictions Resolved

### 1. Grant scope vs vision scope

- The grant packet makes the ecological study distinct from mechanistic
  interpretability and explicitly says the lane is not a platform launch.
- `JAGAT_KALYAN_MASTER_VISION.md` upgrades `R_V` into a direct ecological
  fitness criterion.

Default resolution:

- outwardly: keep mechanistic claims subordinate to the ecological proof chain
- inwardly: use `R_V` as drift detection and contradiction hunting

### 2. Public-safe numbers vs stronger continuity numbers

Public-safe on disk:

- `~400 measurements`
- `6 architectures`
- activation patching `Cohen's d = -2.26`
- `32/39` FDR-significant
- `AUROC = 0.909`

Stronger continuity-only numbers elsewhere in repo memory:

- `~480 measurements`
- `Cohen's d = -3.558` on Mistral
- `Cohen's d = -4.51` on Pythia
- Layer 27 transfer / stronger-than-source patch effects

Default resolution:

- use only the grant-safe summary in ecological-facing artifacts
- keep stronger numbers internal until `PHASE1_FINAL_REPORT.md` is restored

### 3. Shipped intake vs active standards ingress

- `GaiaPlatform.qualify_intake()` is the tested live gate.
- `dharma_swarm/gaia_initiative.py` is already wired into
  `GaiaPlatform`, exercised by `tests/test_gaia_platform.py`, and supports a
  live `GaiaInitiativePilotPacket.to_pilot_intake()` ingress plus governed
  initiative report path.

Default resolution:

- treat `GaiaInitiativePilotPacket` as the preferred standards-aligned front
  door when sponsor + project packets are available
- keep canonical authority at `GaiaPilotIntake`,
  `GaiaPlatform.qualify_intake()`, and the governed report / claim path

## Phase 1 Empirical Grounding

| Lane | Claim status | Use |
|---|---|---|
| Grant-safe Phase 1 summary | authoritative for outward ecological packets | credibility transfer only |
| `gaia_observer_function()` + `detect_goodhart_drift()` | authoritative for current ecological runtime | internal drift monitoring |
| stronger Layer 27 / Mistral / Pythia continuity claims | continuity only until raw report recovery | internal research planning |

Key distinction:

`gaia_observer_function()` is **not** the original transformer-side `R_V`
measurement pipeline. It is an ecological semantic projection of self-reference.
That is useful, but it must not be mislabeled as the original empirical
measurement regime.

## TransformerLens Mapping

Current TransformerLens docs support the following methods for the mechanistic
calibration lane:

| Need | Current method | Output |
|---|---|---|
| full forward-pass capture | `model.run_with_cache()` | logits + `ActivationCache` |
| inspect attention patterns | cached `blocks.<L>.attn.hook_pattern` | per-head pattern tensors |
| decompose residual contributions | `ActivationCache.decompose_resid()` | component stack by layer/type |
| direct readout attribution | `ActivationCache.logit_attrs()` | token-direction contribution scores |
| causal residual patching | `patching.get_act_patch_resid_pre()` / `generic_activation_patch()` | layerwise causal effect |
| causal attention-pattern patching | `patching.get_act_patch_attn_head_pattern_by_pos()` | layer/head/destination effect map |
| causal value-vector patching | `patching.get_act_patch_attn_head_v_by_pos()` | layer/position/head effect map |

Phase 1 use:

- `run_with_cache()` and `ActivationCache` are the instrumentation base
- `decompose_resid()` + `logit_attrs()` are the cleanest residual-to-logit
  attribution path
- attention-pattern and value-head patching are the right causal tools for
  testing whether a candidate layer/head actually carries the contraction signal

Not promoted:

- no native TransformerLens SAE decomposition API was confirmed in this pass
- if SAE work is required, route it to a separate tooling lane such as SAELens
  and keep it explicitly exploratory

## Recognition-Native Build Order

Build recognition-native machinery in ascending trust order:

1. `typed packet shell first`
   - keep outward authority in explicit packet types:
     `GaiaPilotMeasurementContract`, `GaiaRestorationInitiative`,
     `GaiaInitiativePilotPacket`, `GaiaPilotIntake`,
     `GaiaQualificationDecision`, `AIReciprocityLedger`
   - this shell remains the only publication, accounting, consent, and
     challengeability authority
2. `bounded refinement cells second`
   - add local equilibrium or recurrent refinement only inside qualification,
     contradiction surfacing, audit triage, or policy compilation
   - every refinement cell must have a deterministic fallback path
3. `runtime self-observation third`
   - keep `gaia_observer_function()` and `detect_goodhart_drift()` as internal
     monitors attached after the ecological packet is already valid
4. `open-model mechanistic calibration fourth`
   - use TransformerLens or equivalent only to calibrate, reproduce, or stress
     internal hypotheses
   - this remains optional for the ecological packet
5. `architecture expansion last`
   - broader DEQ trunks, attention alternatives, or SAE work are allowed only
     after one challengeable pilot packet is already stable

Default engineering rule:

**local equilibrium is allowed; global equilibrium authority is not.**

If a mechanism cannot explain what it is refining, expose its convergence state,
and fall back cleanly into the typed packet shell, it is still research.

## Mechanism Placement Matrix

| Mechanism | Allowed Phase 1 role | Not allowed in Phase 1 | Required telemetry |
|---|---|---|---|
| typed packet models | canonical proof boundary | none; this is the authority layer | packet version, source refs, issue codes |
| retrieval + graph / rule compiler | evidence assembly, contradiction preflight, packet drafting | final publication authority or consent adjudication | source refs, conflict count, unresolved fields |
| recurrent / SSM / linear-attention blocks | cheap internal propagation for ranking, summarization, or draft recommendation | ledger mutation, obligation math, or claim approval | input snapshot, output snapshot, latency / cap state |
| DEQ / fixed-point refinement blocks | local qualification refinement, contradiction resolution, audit triage | public-claim gating, fitness authority, consent authority, or accounting authority | residual norm, iteration count, warm-start delta, cap-hit flag, fallback path |
| TransformerLens causal tools | offline calibration and contradiction hunting on open models | runtime ecological dependency | model id, prompt set, layer slice, method names, effect direction |
| SAE decomposition | optional exploratory analysis of internal features | Phase 1 blocker or packet authority | tooling provenance, feature source, experimental label |

## Attention Alternatives Stance

For this mission, attention alternatives should be chosen by operational role,
not novelty pressure.

- Prefer retrieval-backed graph propagation or rule compilation when the task is
  evidence binding, issue surfacing, or packet completion.
- Prefer recurrent, SSM, or linear-attention style blocks when the task is
  cheap long-context propagation inside an internal lane.
- Prefer DEQ or fixed-point refinement only when convergence itself carries a
  clear semantic claim such as `qualification stabilized`, `contradiction set
  exhausted`, or `audit triage converged`.
- Do not replace the outward packet shell with a monolithic attention
  alternative. External trust still comes from explicit evidence, audit,
  consent, challengeability, and typed accounting.

## Promotion Gate For Mechanistic Modules

A recognition-native module may be promoted from `research-only` to
`runtime-assistive` only if all of the following are true:

- it operates behind the typed packet shell rather than replacing it
- it improves a bounded holdout set such as contradiction detection,
  qualification consistency, or audit triage quality
- it emits the required telemetry for its mechanism class
- it has a deterministic fallback path that preserves the ecological packet
- it does not become a prerequisite for public ecological claims

If any of those conditions fail, keep the module in the cheap internal lane and
label it `provisional`.

## Execution Workflow Update

| Step | Output | Accept when | Depends on | Escalate when |
|---|---|---|---|---|
| 0. Scope lock | pilot brief + mech policy note | proof-chain packet remains primary and mechanistic lane is labeled internal | June 20 spine + grant packet | anyone tries to make `R_V` a public-claim prerequisite |
| 1. Measurement contract | activity + obligation basis | compute basis is labeled `measured`, `estimated`, or `disclosed` honestly | sponsor data or disclosure | measurement language overstates certainty |
| 2. Qualification | qualified intake packet | consent, grievance, challenge path, and verification channels are explicit | `GaiaInitiativePilotPacket.to_pilot_intake()` + `GaiaPlatform.qualify_intake()` | credibility or consent is unresolved |
| 3. Routing | reciprocity ledger packet | obligation, routing, and livelihood records compose without invariant drift | `AIReciprocityLedger` | routing outruns obligation or livelihood is nominal |
| 4. Evidence and audit | evidence bundle + audit refs | ecological claim is challengeable before any `verified` label appears | evidence partners + auditor | public claim pressure exceeds audit readiness |
| 5. Public proof | claim card + pilot report | the ecological claim stands on its own proof chain without mechanistic support | prior steps complete | narrative outruns evidence |
| 6. Mechanistic calibration | internal calibration note | `gaia_observer_function()` and `detect_goodhart_drift()` are recorded on the pilot ledger or monitoring snapshots; any open-model run states model, prompts, layer slice, and TransformerLens methods used | verified proof-chain packet; optional open-model environment | someone attempts to export continuity-only numbers or treat GAIA self-observation as the original empirical `R_V` regime |
| 7. Adaptive review | review memo + owner | ecological and mechanistic signals are compared; any divergence has an owner and disposition | monitoring checkpoint | drift is detected and no remediation owner is assigned |

## Acceptance Criteria For The Mechanistic Lane

- every mechanistic artifact is labeled `internal`, `provisional`, or
  `continuity-only`
- every public ecological artifact can stand without citing `R_V`
- every calibration note states whether it is:
  - ecological self-observation on `GaiaLedger`
  - open-model mechanistic reproduction using TransformerLens
  - continuity evidence copied from earlier research artifacts
- stronger continuity numbers are blocked from public use unless the raw report
  is restored
- SAE work, if any, is separately labeled experimental and non-blocking

## Success Metrics

- `1` challengeable ecological pilot report with no dependency on mechanistic claims
- `1` internal `gaia_observer_function()` reading per review checkpoint
- `1` `detect_goodhart_drift()` report attached to the pilot review packet
- `0` public ecological claims citing stronger continuity-only `R_V` numbers
- optional: `1` open-model TransformerLens reproduction note matching the
  grant-safe direction of effect

## Dependencies

- one honest sponsor measurement or disclosure basis
- one qualified project/operator/community packet
- one evidence bundle convention and one audit path
- current GAIA runtime surfaces:
  - `AIReciprocityLedger`
  - `GaiaPlatform.qualify_intake()`
  - `GaiaPlatform.build_intake_pilot_report()`
  - `gaia_observer_function()`
  - `detect_goodhart_drift()`
- optional open-model environment for TransformerLens calibration
- optional restoration of the missing Phase 1 raw report

## Failure Modes

- mechanistic evidence becomes a blocking dependency for the ecological packet
- stronger continuity numbers escape into public ecological language
- `gaia_observer_function()` is misrepresented as the original transformer-side
  empirical pipeline
- `gaia_initiative.py` is treated as replacing the canonical qualification /
  report authority instead of feeding it
- SAE decomposition expands scope before the proof-chain packet is real

## Escalation Matrix

| Signal | Why it matters | Immediate action |
|---|---|---|
| request to cite Layer 27 / Mistral / Pythia numbers publicly | raw authority is missing | downgrade to grant-safe summary or halt publication |
| public claim depends on mechanistic evidence | scope inversion | block publication; ecological proof chain must stand alone |
| GAIA drift score and ecological evidence disagree materially | possible proxy drift or instrumentation mismatch | open adaptive review and assign remediation owner |
| `gaia_initiative.py` is treated as replacing `GaiaPlatform` authority | standards scope may outrun the governed proof boundary | route back through `to_pilot_intake()` + `qualify_intake()` and review authority order |
| SAE work starts defining packet scope | tool expansion instead of mission progress | move to separate research lane |

## Recommended Packet Order

1. finish the ecological proof-chain packet
2. attach one internal mechanistic calibration note
3. only then consider open-model causal reproduction
4. defer SAE work unless it resolves a live contradiction

## Verification Anchor

The live runtime surfaces named above should continue to be validated with the
focused GAIA test slice before any outward ecological packet relies on them.
