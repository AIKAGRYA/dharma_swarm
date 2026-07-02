# DharmaVerifier-Ranker v0 Model Card Template

Role: template

## Identity

- Model name:
- Version:
- Base model:
- Adapter:
- Training date:
- Training owner:
- Authority: advisory only

## Intended Use

- Score and rank redacted claims, receipts, routes, evidence packets, patches, and completion claims.
- Recommend `approve`, `revise`, `block`, `escalate`, or `insufficient_context`.
- Surface missing evidence and risk.

## Non-Use

- No public claim approval.
- No autonomous dispatch.
- No source authority.
- No routing-policy mutation.
- No replacement of tests, external verifiers, or operator judgment.

## Data

- Dataset manifest:
- Redaction receipt:
- Source surfaces:
- Train/val/test split:
- Hidden holdout location:
- Leakage check receipt:
- Gold label receipt:

## Training

- Objective:
- Loss mix:
- Trainer/tool versions:
- Hardware:
- Runtime:
- Seed:
- Budget:

## Output Schema

Schema: `DHARMA_VERIFIER_RANKER_OUTPUT_V0.schema.json`

Required fields:

- `verdict`
- `quality_score`
- `evidence_sufficiency`
- `claim_integrity_risk`
- `privacy_risk`
- `route_risk`
- `gate_failures`
- `missing_evidence`
- `next_required_action`
- `confidence`
- `rationale_refs`

## Evaluation

- Eval manifest:
- Baselines:
- Main metric:
- Calibration metrics:
- Privacy recall:
- False approve rate:
- Ranking metrics:
- Downstream lift:
- Cost/latency:
- Replay command:

## Failure Analysis

- Common false approves:
- Common false blocks:
- Privacy misses:
- Bad route misses:
- Missing evidence misses:
- Calibration failures:

## Decision

Decision:

- `promote_shadow_only`
- `revise_data`
- `revise_model`
- `revise_eval`
- `kill`
- `insufficient_evidence`

Rationale:

- Evidence refs:
- Artifact hashes:
- Operator/council notes:
