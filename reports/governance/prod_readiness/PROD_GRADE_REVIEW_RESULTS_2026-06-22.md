# Production-Grade Review Results - 2026-06-22

Generated: 2026-06-23T00:25:00+09:00

Authority baseline:

- Canonical ref: `origin/main`
- Canonical commit: `839fd25f43c76375f49e45012fe8f20a324aa74c`
- Commit subject: `[codex] governance: refresh active track and fitness properties [impact-checked] (#647)`
- Review worktree: `/private/tmp/dharma_swarm_prod_readiness_20260623_839fd25`
- Dirty candidate checkout excluded from authority: `/Users/dhyana/dharma_swarm`

This review does not close any track. It reviews the five checker-SHIPPABLE
tracks against a stricter production-readiness bar: operator-visible integration,
runtime/live evidence, declared owned-surface integrity, test coverage depth, and
whether closure would hide remaining production risk.

## Required Command Results

| Command | Result | Notes |
|---|---:|---|
| `make onboard` | PASS | Reports 7 active tracks, max 10, five checker-SHIPPABLE targets. Runtime truth and manifest-health sections degrade under default `python3` because clean worktree has no local dependency environment. |
| `python3 scripts/governance/check_track_status.py` | PASS | Reports five SHIPPABLE targets, two in-progress tracks, and warn-only WIP/spine-coverage findings. |
| `python3 scripts/governance/render_active_track_includes.py --check` | FAIL | Managed blocks are out of date in `CLAUDE.md`, `docs/governance/SOVEREIGN_MANIFEST.md`, and `docs/governance/BUILD_SESSION_ENTRYPOINT.md`. Diff is whitespace-only inside rendered active-track text, but the gate still fails. |

Additional verification:

- Focused runtime/truth/composer/provider batch: `71 passed in 5.73s`.
- NATS transport/contact batch: `55 passed in 1.25s`.
- Composer frozen verifier set: `104 passed in 2.23s`.
- Runtime-truth broader canonical batch: `29 passed in 2.42s`.
- Provider-routing broader batch: `135 passed in 1.23s`.
- `nc -vz 127.0.0.1 4222`: FAIL, connection refused.
- `/Users/dhyana/dharma_swarm/.venv/bin/python scripts/governance/truth_graph_nats_e2e_demo.py`: FAIL, `NATS_E2E_FAIL: [Errno 61] Connection refused`.
- `make orient` with default clean-tree `python3`: FAIL, missing `pydantic`.
- `make PYTHON=/Users/dhyana/dharma_swarm/.venv/bin/python orient`: PASS and writes `reports/orientation/repo_context.json` and `.md`.

## Strategic Confirmation

- Canonical active count on `origin/main`: 7.
- `track_policy.max_active`: 10.
- A new orchestration-substrate track would take the canonical portfolio to 8/10 and would not exceed the hard WIP cap.
- Dirty local-only tracks should not be raw-promoted now. Keep them as candidate lanes in reconciliation/portfolio-truth records until they have explicit owner approval, non-overlap review, and production-grade evidence.
- Stale local reactivation of `orientation-graph-2026-06` should not be promoted; it is closed on `origin/main` and superseded by `truth-graph-platform-2026-06`.
- `cybernetics-codex-stewardship-2026-06` should be folded under `loop-closure-2026-06` unless the operator deliberately opens a separate successor track; its core surfaces are already represented on `origin/main`.

## Verdict Summary

| Track | Checker status | Production verdict | DGM/orchestration-arena impact |
|---|---|---|---|
| `runtime-truth-reconciliation-2026-06` | SHIPPABLE | CLOSE_READY_WITH_FOLLOWUP | Does not block admission; should remain a closure follow-up risk if default operator renders degrade. |
| `runtime-truth-nats-2026-06` | SHIPPABLE | KEEP_ACTIVE_PROD_HARDENING | Blocks production-grade live-transport claims; does not block opening the orchestration track by cap. |
| `truth-graph-platform-2026-06` | SHIPPABLE | KEEP_ACTIVE_PROD_HARDENING | Partially blocks DGM readiness because live NATS proof and fresh agent presence are not currently proven. |
| `composer-holon-spine-longrun-2026-06` | SHIPPABLE | SPLIT_BEFORE_CLOSE | Does not block DGM admission; longrun/standing-wake production work should split from Build A readiness closure. |
| `provider-routing-consolidation-2026-06` | SHIPPABLE | CLOSE_READY_WITH_FOLLOWUP | Enables DGM/orchestration model-roster work; live-provider canary remains follow-up. |

## Track Reviews

### `runtime-truth-reconciliation-2026-06`

Verdict: `CLOSE_READY_WITH_FOLLOWUP`

Evidence checked:

- Declared owned surfaces: `dharma_swarm/operator_core/**`, `scripts/governance/agent_onboard.py`, `dharma_swarm/runtime_state.py`.
- Completion criteria all pass in `reports/governance/active_track_evidence.json`.
- `RuntimeTruthPacket` and `RuntimeTruthState` exist in `dharma_swarm/operator_core/contracts.py`.
- `render_runtime_truth` is wired into `scripts/governance/agent_onboard.py`.
- Runtime truth projection code is present in `dharma_swarm/operator_core/runtime_truth.py`.
- Focused and broadened tests pass:
  - `tests/test_agent_onboard.py::test_runtime_truth_render_is_read_only`
  - `tests/test_operator_core_contracts.py`
  - `tests/test_runtime_truth_projection_fields.py`
  - `tests/test_runtime_truth_command_cutover.py`
  - `tests/test_runtime_state_invariants.py`
  - runtime truth spine v1/v2 evidence/adapters/tollbooth tests
  - `tests/test_spine_persistence_invariant.py::test_submit_via_spine_retry_does_not_create_second_runtime_receipt`

Missing production-grade evidence:

- In the clean disposable worktree, default `make onboard` prints runtime-truth unavailable because default `python3` lacks dependency installation. The venv-backed path works, but the default operator path still degrades in a clean checkout.
- The rendered-include gate fails before any closure workflow, so dependent docs are not currently lifecycle-clean.
- The review did not prove a fresh live runtime database with current production jobs; it proved the read-only projection contract and tests.

Concrete next actions:

1. Make the default operator path dependency-honest: either ensure onboarding/orientation use the repo venv consistently or degrade with an explicit remediation line that does not hide runtime truth.
2. Refresh rendered active-track include blocks after any approved closure, not before reconciliation approval.
3. Add one current runtime DB receipt snapshot proving the projection renders real live jobs, not only fixtures.

Recommended owner lane: `runtime-truth-reconciliation-2026-06` closeout follow-up owned by `@AmitabhainArunachala`.

DGM/orchestration-arena path: does not block opening the orchestration-substrate track. It should be carried as closure follow-up risk because DGM review surfaces depend on trustworthy operator truth packets.

Closure risk: low to medium. The architecture is read-only and well-tested, but default clean-checkout operator rendering is not production-smooth.

### `runtime-truth-nats-2026-06`

Verdict: `KEEP_ACTIVE_PROD_HARDENING`

Evidence checked:

- Declared owned surfaces: `docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md`, `dharma_swarm/a2a/a2a_nats_contact.py`, `dharma_swarm/a2a/a2a_core_contact.py`.
- Completion criteria pass, but only prove that the NATS master spec exists and contains the string `NATS`.
- NATS implementation surfaces found under current main:
  - `dharma_swarm/a2a/nats_transport.py`
  - `dharma_swarm/operator_core/nats_live_contact.py`
  - `dharma_swarm/operator_core/nats_substrate_status.py`
  - `scripts/runtime/a2a_send.py`
  - `scripts/runtime/a2a_inbox_bridge.py`
  - `scripts/runtime/a2a_domain_reply_worker.py`
  - `scripts/runtime/a2a_reply_capture.py`
- NATS-focused tests pass: `55 passed in 1.25s`.
- NATS spec explicitly says declared surfaces are not liveness proof and live state requires JetStream health plus ack-bearing hot-contact receipt.

Missing production-grade evidence:

- Two declared owned-surface files are missing on `origin/main`: `dharma_swarm/a2a/a2a_nats_contact.py` and `dharma_swarm/a2a/a2a_core_contact.py`.
- Local broker check fails: `127.0.0.1:4222` refused connection.
- Truth-graph NATS e2e demo fails with connection refused.
- The available tests prove honest offline behavior and fake JetStream behavior; they do not prove a current live JetStream ack path.
- `make orient` with venv reads a stale live-ops receipt claiming `transport.nats` live, but current socket evidence contradicts it.

Concrete next actions:

1. Reconcile owned surfaces: either restore the declared `a2a_nats_contact.py` / `a2a_core_contact.py` files or update `ACTIVE_TRACK.yaml` only through an approved lifecycle change to point at the actual owner modules.
2. Produce a fresh `nats_live_contact.py --write-receipt` result with `ack_verified=true`.
3. Run a live JetStream publish/consumer round trip and attach the receipt path.
4. Make `make onboard` / `make orient` prefer fresh NATS receipts over stale live-ops snapshots when reporting transport liveness.

Recommended owner lane: keep in `runtime-truth-nats-2026-06` under `@codex`.

DGM/orchestration-arena path: blocks production-grade live-transport claims for DGM/orchestration. It does not block admitting the orchestration track by cap, but the orchestration track should not assume live NATS until this is resolved.

Closure risk: high. Closing this now would hide missing declared surfaces and lack of current broker ack proof.

### `truth-graph-platform-2026-06`

Verdict: `KEEP_ACTIVE_PROD_HARDENING`

Evidence checked:

- Declared owned surfaces are present: orientation graph scripts, truth-graph NATS demo scripts, A2A receipt gate, agent presence projection, tests, and `reports/orientation/**`.
- Completion criteria all pass in checker evidence.
- Focused tests pass:
  - `tests/test_orientation_graph.py`
  - `tests/test_truth_graph_repo_context.py`
  - `tests/test_a2a_gate.py`
  - `tests/test_agent_registry_presence.py`
- `make PYTHON=/Users/dhyana/dharma_swarm/.venv/bin/python orient` writes `reports/orientation/repo_context.json` and `.md`.
- Generated repo context reports 7 active tracks and `loop1_live: False`.

Missing production-grade evidence:

- Default `make orient` fails in the clean worktree because default `python3` lacks `pydantic`.
- Current NATS e2e proof fails with connection refused, while repo context still points at `reports/orientation/nats_e2e_receipt.json`.
- Agent presence projection shows all listed agents with RED heartbeats in the generated repo context; this is useful truth, but not a production-ready active-presence substrate.
- The track depends on `orientation-graph-2026-06`, which is closed on `origin/main`; that is valid historically, but closure should ensure no stale local reactivation is unioned back into active tracks.

Concrete next actions:

1. Require fresh NATS e2e receipt generation or explicitly mark NATS proof absent in `repo_context`.
2. Make `make orient` dependency-honest in clean worktrees.
3. Add a freshness policy for `reports/orientation/nats_e2e_receipt.json` so stale proof cannot satisfy production review.
4. Keep local `orientation-graph-2026-06` reactivation out of the reconciliation union.

Recommended owner lane: keep in `truth-graph-platform-2026-06` under `@codex`.

DGM/orchestration-arena path: partially blocks production-grade DGM readiness because the arena needs truthful repo context and live-presence proof. It does not block opening the orchestration-substrate track.

Closure risk: medium to high. Static and test evidence is solid, but live NATS/presence proof is not current.

### `composer-holon-spine-longrun-2026-06`

Verdict: `SPLIT_BEFORE_CLOSE`

Evidence checked:

- Declared owned surfaces exist across `docs/sovereign_holons/**`, `reports/sovereign_holons/**`, `dharma_swarm/holon_*.py`, `scripts/holon_*.py`, and `tests/test_holon_*.py`.
- Completion criteria all pass in checker evidence.
- `reports/sovereign_holons/BUILD_A_90_READINESS_PACKET.md` explicitly says it is a confidence-lift packet, not a launch receipt.
- `reports/sovereign_holons/COMPOSER_WAKE_WITNESSED.md` proves one-shot unattended wake proof for both composer seats.
- Frozen verifier set passes now: `104 passed in 2.23s`.
- Initial focused holon bridge/runtime tests also passed in the 71-test batch.

Missing production-grade evidence:

- The readiness packet itself says unattended standing composer operation is not proven without runtime wake/cost facts.
- `COMPOSER_WAKE_WITNESSED.md` explicitly does not install or ratify a permanent standing wake loop.
- The track depends on `runtime-truth-spine-adoption-2026-06`, which remains active at 7/8 and still has intentional bypass sites.
- No fresh current-date recurring wake proof was generated in this review.

Concrete next actions:

1. Split the track into a closable Build A readiness closure and a successor permanent-standing-wake / composer-production-hardening track.
2. Keep longrun claims out of the closed-track reason unless fresh recurring wake, cost/routing ledger, and state freshness proof exist.
3. Keep dependency on `runtime-truth-spine-adoption-2026-06` explicit until bypass allowlist is drained.

Recommended owner lane: close only a Build A readiness sub-scope after operator approval; open/keep successor lane for standing composer operation under `@AmitabhainArunachala`.

DGM/orchestration-arena path: does not block DGM/orchestration track admission. It is adjacent holon readiness work and should not consume the orchestration substrate slot unless deliberately scoped as a dependency.

Closure risk: medium. Build A readiness is strong; longrun production semantics are not yet proven.

### `provider-routing-consolidation-2026-06`

Verdict: `CLOSE_READY_WITH_FOLLOWUP`

Evidence checked:

- Declared owned surfaces exist: provider policy, model hierarchy/pool/defaults, runtime provider, routers, providers implementation, and architecture doc.
- Completion criteria all pass in checker evidence.
- Architecture doc declares one precedence: `explicit > capability/power > malleable overlays > learned > availability prune > fallback walk`.
- Code evidence:
  - `provider_policy.py` reads `context["preferred_provider"]`.
  - Explicit provider pin returns before cost/telemetry reranking.
  - `power_first` ordering is default.
  - `ProviderType.ZHIPU`, `DEFAULT_ZHIPU_MODEL`, and `ZhipuProvider` exist.
  - Zhipu runtime-provider creation path exists.
- Provider-focused verifier batch passes: `135 passed in 1.23s`.

Missing production-grade evidence:

- No live z.ai/Zhipu API call was run; the track properly avoids committing credentials, but production closure should record that first-party path remains key/egress dependent.
- No current live provider-canary receipt was produced for the consolidated routing path.
- Stage 5 leaves deliberate exceptions, especially `AgentConfig.model` and model literals outside routing. Those are documented, but should remain follow-up, not disappear.

Concrete next actions:

1. Close the consolidation track only with a follow-up item for live provider canary and egress allowlist proof.
2. Add a post-closure smoke receipt proving explicit provider/model selection reaches an actual configured provider when keys are available.
3. Keep documented Stage 5 exceptions visible in a successor drift-cleanup owner, not as hidden debt.

Recommended owner lane: close under `provider-routing-consolidation-2026-06` with a successor provider-live-canary/drift-cleanup follow-up owned by `@AmitabhainArunachala`.

DGM/orchestration-arena path: does not block; it enables the orchestration substrate by giving it a coherent model roster and explicit-routing policy. The arena should still require live-provider canary proof before making production quality claims.

Closure risk: low to medium. Static, behavior, and routing tests are strong; live-provider proof remains environment-gated.

## Dirty Local-Only Track Recommendation

Current dirty checkout active-only additions relative to `origin/main`:

- `a2a-cloud-agent-bridge-2026-06`
- `agent-admission-semantic-commons-2026-06`
- `cybernetics-codex-stewardship-2026-06`
- `helm-worldclass-terminal-2026-06`
- `orientation-graph-2026-06`
- `telos-ai-morning-refinery-2026-06`

Recommendation: do not promote these into canonical `ACTIVE_TRACK.yaml` during
this closure review. Preserve them as candidate lanes in reconciliation records.
`orientation-graph-2026-06` is stale because it is already closed on
`origin/main`. `cybernetics-codex-stewardship-2026-06` should fold under
`loop-closure-2026-06` unless the operator explicitly opens a successor.

## Closure Guidance

The portfolio has room for the orchestration substrate by cap, but production
readiness is not the same as WIP capacity. The cleanest path is:

1. Admit the orchestration-substrate track only after reconciliation records the
   phantom/local-only lanes honestly.
2. Close `provider-routing-consolidation-2026-06` with follow-up after operator
   approval.
3. Close `runtime-truth-reconciliation-2026-06` with follow-up after dependency
   and rendered-include hygiene is handled.
4. Keep `runtime-truth-nats-2026-06` and `truth-graph-platform-2026-06` active
   for live-proof hardening.
5. Split `composer-holon-spine-longrun-2026-06` before closure so Build A
   readiness does not masquerade as permanent standing composer production.
