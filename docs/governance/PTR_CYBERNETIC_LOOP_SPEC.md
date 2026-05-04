# PTR Cybernetic Loop Spec

Status: v0 build spec. First implementation is shadow-only and must not change
runtime authority, pre-commit, CI, Makefile, or autonomy behavior.

## 1. Purpose

Predictive Telic Repair (PTR) is the top-level cybernetic readiness loop for
Dharma Swarm. It measures whether the system can predict, act, verify, repair,
and preserve telos under real constraints.

PTR is not TCS. TCS is the S5 identity-coherence pillar inside PTR.

External framing:

- Karpathy verifiability: AI systems improve fastest where attempts are
  resettable, efficient, and rewardable/verifiable:
  https://karpathy.bearblog.dev/verifiability/
- Autonomic computing: self-managing systems use monitor, analyze, plan,
  execute, and knowledge loops:
  https://jmvidal.cse.sc.edu/lib/kephart03a.html
- Ashby requisite variety: regulation requires enough variety to absorb the
  disturbances being regulated:
  https://www.panarchy.org/ashby/variety.1956.html
- Goodhart/Campbell risk: a metric used as a target becomes corruptible:
  https://pmc.ncbi.nlm.nih.gov/articles/PMC7901608/

## 2. Existing Repo Anchors

- TCS is defined as `0.35*GPR + 0.35*BSI + 0.30*RM`:
  `dharma_swarm/identity.py:5`.
- `IdentityMonitor.measure()` computes TCS and drift regime:
  `dharma_swarm/identity.py:152`.
- `LiveCoherenceSensor.measure()` computes present-moment liveness:
  `dharma_swarm/identity.py:602`.
- `causal_ledger.declare_prediction()` records expected outcomes:
  `dharma_swarm/causal_ledger.py:116`.
- `causal_ledger.resolve_prediction()` records actual outcomes and deltas:
  `dharma_swarm/causal_ledger.py:200`.
- `compute_repair_score()` computes repair evidence:
  `dharma_swarm/r_repair_metric.py:166`.
- Omega divergence threshold is `0.4`: `dharma_swarm/organism.py:1035`.
- `TelosGatekeeper` owns action gate decisions:
  `dharma_swarm/telos_gates.py:221`.
- `PolicyCompiler` owns structured predicate policy evaluation:
  `dharma_swarm/policy_compiler.py:185`.
- Shakti action authority is a MetaPrinciple contract, not a core telos gate:
  `docs/governance/SHAKTI_ACTION_AUTHORITY_CONTRACT.md`.

## 3. Authority Model

PTR is negative authority only.

PTR may:

- observe
- warn
- cap autonomy downward
- require human review
- route work to witness or repair
- emit algedonic pressure
- add structured metadata for policy checks

PTR must never:

- grant ALLOW
- auto-approve tool use
- raise autonomy
- bypass TelosGatekeeper
- override immutable PolicyCompiler rules
- infer operator consent
- turn high TCS into permission
- mutate governance rules by itself

Autonomy integration, when enabled in a later PR, must be:

```text
effective_autonomy = min(base_autonomy, ptr_autonomy_cap)
```

Never `max`.

## 4. Pillars

PTR has five pillars.

1. `predictive_repair`
   - Source: `r_repair_metric.compute_repair_score()`.
   - Backing evidence: `causal_ledger` prediction and resolution marks.
   - Required for authoritative PTR.

2. `tcs_identity`
   - Source: `IdentityMonitor.measure()`.
   - Meaning: S5 identity coherence.
   - Default weight is 0.10. Absolute future max is 0.15 after calibration.
   - TCS must not dominate PTR.

3. `actuation_liveness`
   - Source: live runtime artifacts, DGC health, task movement, provider
     readiness, pulse freshness, and backlog pressure.
   - Current seed: `LiveCoherenceSensor.measure()`.

4. `repo_integrity`
   - Source: out-of-band integrity artifact.
   - Inputs: tests, syntax/import health, module budget, capsule coherence,
     semgrep/gitleaks/CodeQL summaries, and diff hygiene.
   - Expensive checks must not run in heartbeat.

5. `governance_integrity`
   - Source: out-of-band governance artifact and witness evidence.
   - Inputs: TelosGatekeeper decisions, PolicyCompiler checks, Shakti authority
     case, witness logs, operator overrides, and gate coverage.
   - Required for authoritative PTR.

## 5. Formula

PTR uses lower-confidence-bound pillar values, not optimistic point estimates.

```text
PTR_raw = exp(sum_i w_i * log(max(epsilon, LCB90(pillar_i))))

PTR = PTR_raw
    * omega_attenuator
    * calibration_confidence
    * coverage_confidence
    * independence_confidence
```

Default weights:

```text
predictive_repair       0.30
actuation_liveness      0.20
repo_integrity          0.20
governance_integrity    0.20
tcs_identity            0.10
```

Missing pillars do not become zero, but they cannot help. The conservative
prior is `0.35`; missingness reduces coverage confidence and is reported.

If `predictive_repair` or `governance_integrity` is missing, PTR is not
authoritative.

## 6. Omega Attenuation

Omega divergence is the gap between live score and TCS.

```text
omega = abs(live_score - tcs)

omega <= 0.15: no penalty
omega > 0.15: attenuate PTR
omega >= 0.40: max verdict CAUTION
omega >= 0.40 for 3 cycles: HOLD
```

PTR v0 uses:

```text
attenuator = 1.0                                   if omega <= 0.15
attenuator = max(0.25, exp(-2*((omega-0.15)/0.25)^2)) otherwise
```

## 7. Verdict Bands

Authoritative score bands:

```text
PTR >= 0.70: PROCEED
0.55-0.70:  CAUTION
0.40-0.55:  REPAIR_MODE
< 0.40:     HOLD
```

Caps:

- `repo_integrity < 0.50`: HOLD
- `governance_integrity < 0.50`: HOLD
- `TCS < 0.40`: max verdict CAUTION
- `TCS < 0.25 for 3 cycles`: HOLD
- `omega >= 0.40`: max verdict CAUTION
- `omega >= 0.40 for 3 cycles`: HOLD
- `provisional` or `low_coverage`: INSUFFICIENT_EVIDENCE
- `near_eigenform`: max verdict CAUTION
- missing predictive repair or governance integrity: INSUFFICIENT_EVIDENCE

## 8. Evidence Schema

Canonical score artifact:

```json
{
  "ptr_version": "ptr.v0",
  "computed_at": "iso8601",
  "source": "organism.heartbeat|script|manual",
  "ptr": 0.0,
  "ptr_raw": 0.0,
  "verdict": "INSUFFICIENT_EVIDENCE|HOLD|REPAIR_MODE|CAUTION|PROCEED",
  "authoritative": false,
  "confidence": 0.0,
  "omega_delta": 0.0,
  "omega_attenuator": 0.0,
  "ptr_autonomy_cap": 1,
  "authority_model": "negative_only",
  "components": {
    "predictive_repair": 0.0,
    "tcs_identity": 0.0,
    "actuation_liveness": 0.0,
    "repo_integrity": 0.0,
    "governance_integrity": 0.0
  },
  "component_lcb90": {},
  "weights": {},
  "caps": [],
  "inputs_stale": [],
  "missingness": [],
  "evidence_refs": [],
  "notes": []
}
```

Persistence paths:

```text
~/.dharma/meta/ptr_score.json
~/.dharma/meta/ptr_history.jsonl
~/.dharma/meta/repo_integrity.json
~/.dharma/meta/governance_integrity.json
```

## 9. Control Loop

PTR maps to MAPE-K:

1. Monitor
   - Read TCS, live score, repair score, repo artifact, governance artifact.

2. Analyze
   - Compute lower-bound pillar vector, confidence, missingness, omega, and caps.

3. Plan
   - Pick repair pressure: identity, liveness, repo, governance, prediction
     coverage, or operator review.

4. Execute
   - Later PR only. Route repair tasks or cap autonomy downward.

5. Verify
   - Resolve causal predictions after the declared window.

6. Knowledge
   - Append `ptr_history.jsonl`, calibration stats, and evidence refs.

## 10. Rollout

Phase 0: spec and schema only.

Phase 1: shadow scorer.
- Add pure scorer, JSON artifacts, and focused tests.
- No runtime authority change.

Phase 2: advisory.
- Operator brief and Guardian warnings may display PTR.
- PolicyCompiler metadata is log/warn only.

Phase 3: downward-only enforcement.
- PTR may cap autonomy or require human approval after sustained evidence.
- PTR still cannot grant authority.

Phase 4: required evidence.
- High-authority actions require PTR evidence or explicit operator override.
- Missing evidence routes to review, not global dispatch failure.

Phase 5: PTR-owned claims.
- Autonomous claims of repair require prediction and resolution coverage.

## 11. First Build Scope

Add:

- `docs/governance/PTR_CYBERNETIC_LOOP_SPEC.md`
- `dharma_swarm/ptr_metric.py`
- `dharma_swarm/ptr_integrity.py`
- `scripts/ptr_integrity_probe.py`
- `tests/test_ptr_metric.py`
- `tests/test_ptr_integration.py`

Do not:

- wire into pre-commit
- wire into Makefile
- change TelosGatekeeper behavior
- change PolicyCompiler behavior
- change autonomy behavior
- run repo checks in heartbeat

## 12. Anti-Goodhart Tests

Required behavioral tests:

- High TCS cannot produce PROCEED when live score is dead.
- Missing predictive repair withholds authoritative PTR.
- Missing governance integrity withholds authoritative PTR.
- Missing non-core evidence cannot improve PTR.
- Skipped integrity probes emit `low_coverage` and withhold authoritative PTR.
- Provisional or low-coverage repair evidence withholds authoritative PTR.
- Malformed integrity artifacts withhold authoritative PTR through the full score.
- Repo or governance hard failure caps verdict to HOLD.
- Omega divergence attenuates PTR and caps verdict.
- Sustained Omega divergence holds instead of merely warning.
- Near-eigenform repair evidence is an underchallenge alarm, not victory.
- A zero pillar collapses the geometric score.
- Stale artifacts reduce confidence.
- PTR output declares `authority_model="negative_only"`.
- `ptr_autonomy_cap` never exceeds HUMAN_ON_LOOP (`2`) in v0.
