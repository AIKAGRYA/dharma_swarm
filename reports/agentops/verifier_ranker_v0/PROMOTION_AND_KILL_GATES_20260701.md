# Promotion and Kill Gates

Role: active report / governance boundary

## Authority Boundary

`DharmaVerifier-Ranker v0` is advisory. It may improve triage, ranking, and
evidence-gap detection. It may not become an authority surface.

Forbidden:

- autonomous dispatch;
- source mutation;
- routing policy mutation;
- public claim approval;
- replacing deterministic tests;
- replacing external verifiers;
- replacing operator judgment;
- updating Forge/DGM/archive fitness.

## Promotion Gates

Gate 0, package readiness:

- schema exists;
- redaction rules exist;
- inventory receipt exists;
- label plan exists;
- baseline/eval plan exists;
- model card template exists;
- package manifest passes.

Gate 1, data readiness:

- graph exporter implemented;
- all rows validate against schema;
- redaction receipt passes;
- no raw private bodies or provider payloads;
- train/val/test split manifest exists;
- hidden holdout is outside agent-readable paths.

Gate 2, baseline readiness:

- deterministic baseline run;
- repo rule scorer baseline run;
- cheap local model baseline run;
- DeepSeek/frontier/open judge baselines attempted or blocker receipts written;
- no silent fallback.

Gate 3, first model readiness:

- first small trained or simulated ranker run;
- eval receipt with raw artifacts preserved;
- calibration report;
- failure analysis;
- model card.

Gate 4, shadow integration:

- shadow-only path;
- no policy mutation;
- disagreement logging;
- operator-visible refusal when insufficient context.

Gate 5, promotion consideration:

- at least 100 paired heldout tasks;
- lower confidence bound above zero on main metric;
- privacy recall not worse than deterministic scanner;
- false approve rate below preregistered threshold;
- replay succeeds from raw artifacts and hashes.

## Kill Gates

Kill or revise the model if:

- it trains on raw private logs, secrets, credentials, raw message bodies, or provider payloads;
- gold labels leak into train;
- hidden holdouts are agent-readable;
- model output fails strict JSON schema above a preregistered threshold;
- privacy recall regresses;
- false approves increase on unsupported claims;
- calibration is unsafe;
- model self-reports success without external proof;
- provider/model differs from preregistration;
- eval scorer, task set, or rubric changes post hoc;
- downstream shadow mode does not improve pass rate or cost at fixed safety.

## Promotion Decision Values

Allowed decision values:

- `promote_shadow_only`
- `revise_data`
- `revise_model`
- `revise_eval`
- `kill`
- `insufficient_evidence`

No decision value grants runtime authority.
