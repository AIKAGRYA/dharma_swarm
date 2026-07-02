# Active Track Final Boss Gate

The rigorous active-track bar proves a track is safe to leave the active WIP lane. It does not automatically prove the track should become trusted production substrate.

## Closure Kinds

- `VERIFIED_SLICE`: the track's scoped criteria passed with rigorous evidence and no open blockers. This is the default honest closeout for useful but bounded work.
- `CLOSED_NOT_PROD`: the track is intentionally closed without a production claim.
- `RETIRED`: the track is removed from the active lane because it is no longer the right work.
- `SUPERSEDED`: the track is closed because a different track absorbed the claim.
- `PRODUCTION_READY`: the track claims production readiness and must pass the Final Boss gate.
- `SUBSTRATE_TRUSTED`: the track claims future agents may treat it as durable substrate truth and must pass the Final Boss gate.

## Final Boss Review

`PRODUCTION_READY` and `SUBSTRATE_TRUSTED` require a `final_boss_review` packet with:

- a dossier path
- a council receipt path
- at least six reviewers
- `score_min: 100`
- `explicit_disagreements: 0`
- `local_verifiers_passed: true` and `returncode: 0` local verifier result
  rows for every executable check declared by the dossier
- at least two adversarial review rounds
- all required dimensions:
  - `production_engineering`
  - `sre_failure_modes`
  - `architecture_integration`
  - `anti_slop_code_quality`
  - `governance_truthfulness`
  - `security_supply_chain`
  - `future_maintainability`
- `council_coverage` proving one distinct council receipt for every
  `round x required dimension` pair

Profile-specific checks may add more requirements. For `runtime_transport`, production/substrate closure also requires runtime evidence and explicit failure-mode coverage for real broker behavior, ack/nack failure, duplicate publish idempotency, handler failure, execution identity, receipt durability, and reconnect/degradation.

## Graduation Profiles

Every `graduation_profile` has explicit dossier requirements and hard rejects.
The profile does not replace the seven Final Boss dimensions; it adds sharper
failure modes for the domain under review.

Examples:

- `runtime_transport`: real broker, ack/nack, duplicate publish, handler failure, execution identity, receipt durability, reconnect/degradation.
- `runtime_truth`: projections read from existing truth owners only; no new truth store or authority surface.
- `provider_routing`: explicit requests, deterministic fallback, credential absence, provider outage, and secret-safe routing.
- `filesystem_substrate`: folder contracts, idempotent organization, path traversal, symlink, and non-destructive mutation behavior.
- `truth_graph`: provenance, edge resolution, deterministic context artifacts, and freshness-bounded A2A presence.
- `holon_bridge`: wake receipts, read-only versus lease authority, identity lineage, and command receipt projection.
- `governance_gate`: negative tests for false-green claims, deterministic generated reports, and downgrade/bypass resistance.

## Operator Workflow

Generate the dossier and dimension-scoped prompts without calling external reviewers:

```bash
python scripts/governance/run_final_boss_review.py \
  --track-id runtime-truth-nats-2026-06 \
  --target-closure-kind SUBSTRATE_TRUSTED \
  --dry-run \
  --json
```

Run the full in-lane council:

```bash
python scripts/governance/run_final_boss_review.py \
  --track-id runtime-truth-nats-2026-06 \
  --target-closure-kind SUBSTRATE_TRUSTED \
  --runtime-evidence reports/runtime/nats_live_broker_e2e_receipt.json \
  --json
```

The runner writes:

- a dossier under `reports/governance/final_boss/`
- one prompt per required dimension and round
- council receipts under `reports/governance/final_boss/council/`
- local verifier result rows inside the synthesized review packet and run manifest
- a synthesized review packet under `reports/governance/final_boss/reviews/`
- a timestamped run manifest under `reports/governance/final_boss/runs/`
- a `latest-<track>-<target>-manifest.json` alias for the current generated run

Only a manifest with `ship_safe: true` may be copied into `ACTIVE_TRACK.yaml`.
Dry-run manifests are inspection artifacts and must never be attached as passing
evidence. If `ship_safe` is false, the manifest's `validation_blocks` are the
required changes before the track can claim `PRODUCTION_READY` or
`SUBSTRATE_TRUSTED`.

The checker requires the full coverage matrix and a minimum of two rounds. That
means at least fourteen distinct passing council receipts: two rounds times the
seven required Final Boss dimensions. A single all-purpose receipt cannot
satisfy a production/substrate claim.

Example attach shape:

```yaml
target_closure_kind: SUBSTRATE_TRUSTED
graduation_profile: runtime_transport
final_boss_review:
  dossier: "reports/governance/final_boss/runtime-truth-nats-2026-06-substrate_trusted.json"
  council_receipts:
    - "reports/governance/final_boss/council/<receipt>.json"
  council_coverage:
    - round: 1
      dimension: production_engineering
      council_receipt: "reports/governance/final_boss/council/<production_engineering-receipt>.json"
    - round: 1
      dimension: sre_failure_modes
      council_receipt: "reports/governance/final_boss/council/<sre_failure_modes-receipt>.json"
    - round: 2
      dimension: production_engineering
      council_receipt: "reports/governance/final_boss/council/<round2-production_engineering-receipt>.json"
  reviewer_count: 6
  score_min: 100
  explicit_disagreements: 0
  local_verifiers_passed: true
  local_verifier_results:
    - id: track_status
      command: "/Users/dhyana/dharma_swarm/.venv/bin/python scripts/governance/check_track_status.py"
      passed: true
      returncode: 0
  rounds: 2
  dimensions:
    - production_engineering
    - sre_failure_modes
    - architecture_integration
    - anti_slop_code_quality
    - governance_truthfulness
    - security_supply_chain
    - future_maintainability
  runtime_evidence:
    - "reports/runtime/nats_live_broker_e2e_receipt.json"
  failure_modes_tested:
    - real_broker_e2e
    - ack_nack_failure
    - idempotency_duplicate_publish
    - handler_failure
    - execution_identity
    - receipt_durability
    - reconnect_or_degradation
  mock_only: false
```

## Master Operating Prompt

Use this as the long-running goal prompt for any agent instantiated to maintain
this lane:

```text
Build and hardwire the Active Track Final Boss graduation system.

Mission: no active track may become PRODUCTION_READY or SUBSTRATE_TRUSTED unless
it passes a profile-aware, evidence-backed, multi-round adversarial gate with
decorrelated model reviewers, a fresh persistent A2A witness, executable local
verification, and zero unresolved blockers.

Do not optimize for confidence, green-looking YAML, or model agreement. Optimize
for substrate truth. A useful bounded slice may close as VERIFIED_SLICE. A
production/substrate claim must prove production engineering, SRE failure modes,
architecture integration, anti-slop code quality, governance truthfulness,
security/supply-chain posture, and future maintainability at 100/100.

Hard rules:
- Passing tests are necessary but never sufficient when the claim boundary is
  wider than the tests.
- Model agreement is never a substitute for executable local verifier results
  in the attached review packet.
- Mock-only or fake-only runtime evidence cannot satisfy runtime substrate
  claims.
- Every production/substrate claim needs a generated dossier, council receipts,
  >=6 required reviewers, score_min 100, zero explicit disagreements, all Final
  Boss dimensions, at least two rounds, one distinct council receipt per
  round/dimension pair, and profile-specific failure-mode evidence.
- The runner may produce prompts and manifests, but only the checker decides
  whether a review packet is attachable.
- Failed lanes, stale persistent witnesses, provider errors, malformed JSON, low
  scores, or any explicit disagreement are blockers.
- Preserve limitations and non-claims. Do not convert VERIFIED_SLICE into
  SUBSTRATE_TRUSTED without new evidence.

Work loop:
1. Generate the dossier and dry-run prompts.
2. Run local verifiers.
3. Run every dimension through the decorrelated council.
4. Fix concrete blockers in code, tests, receipts, docs, or architecture.
5. Repeat until the checker reports no Final Boss blockers.
6. Attach the review packet only when ship_safe is true.
```

## NATS Precedent

`runtime-truth-nats-2026-06` is intentionally closed as `VERIFIED_SLICE`, not `PRODUCTION_READY` or `SUBSTRATE_TRUSTED`. Its test evidence is useful and rigorous enough to leave the active WIP lane, but it is not a full production-live NATS substrate claim.

This is the core distinction the gate protects: close useful slices without inflating them into substrate truth.
