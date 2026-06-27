# Standalone Holon Phase 1 Receipt

Role: witness report for the standalone `holon/` repo-within-repo package.
Generated: 2026-06-26T00:03:57Z.

This is not the final Hermes-grade verdict. It proves the first standalone
package gates and records remaining gates for the long-run objective.

## Receipt Bundle

Bundle path:

`reports/sovereign_holons/standalone_holon_phase1_20260626/`

Machine summary:

`reports/sovereign_holons/standalone_holon_phase1_20260626/installed_runtime_summary.json`

Live A2A repair receipt:

`reports/sovereign_holons/standalone_holon_phase1_20260626/A2A_LIVE_REPAIR_RECEIPT.md`

Live A2A source-audit attempt receipt:

`reports/sovereign_holons/standalone_holon_phase1_20260626/a2a_source_audit/A2A_SOURCE_AUDIT_RECEIPT.md`

Isolated install proof:

`reports/sovereign_holons/standalone_holon_phase1_20260626/isolated_install_proof_20260626T0025Z.json`

Runtime receipts:

- `reports/sovereign_holons/standalone_holon_phase1_20260626/agents/h/receipts/hrcpt_2649981fc309683844c8ad8d.json`
- `reports/sovereign_holons/standalone_holon_phase1_20260626/agents/h/receipts/hrcpt_5d8d3cd18ef53ab08fbfce0e.json`
- `reports/sovereign_holons/standalone_holon_phase1_20260626/agents/h/receipts/hrcpt_1a47f723fe9fe61d79f5c313.json`
- `reports/sovereign_holons/standalone_holon_phase1_20260626/agents/h/receipts/hrcpt_54139439fa3709ae32551d52.json`

## Commands and Results

- `make onboard`: exit 0; confirmed dirty branch and active `composer-holon-spine-longrun-2026-06` track.
- `bash scripts/runtime/codex_toolbelt_status.sh`: exit 0; local code tools available, provider env keys absent.
- `.venv/bin/python -m pytest -q holon/tests tests/test_holon_runtime.py`: exit 0, `20 passed`.
- `.venv/bin/python -m holon verify --json`: exit 0, standalone verifier status `pass`.
- `rg -n "from dharma_swarm|import dharma_swarm|dashboard|APEX|control_surface" holon --glob '*.py' --glob '!tests/**' --glob '!__pycache__/**'`: exit 1 with no matches.
- `.venv/bin/python -m pip wheel --no-deps --no-build-isolation /Users/dhyana/dharma_swarm/holon -w /private/tmp/holon-dist`: exit 0; built `holon_runtime-0.1.0-py3-none-any.whl`.
- `/private/tmp/holon-standalone-venv/bin/python -m pip install --force-reinstall /private/tmp/holon-dist/holon_runtime-0.1.0-py3-none-any.whl`: exit 0.
- Isolated import probe from `/private/tmp`: exit 0; `holon` imported from site-packages and `dharma_swarm_spec=None`.
- `/private/tmp/holon-standalone-venv/bin/python -m holon verify --json`: exit 0, installed verifier status `pass`.
- Installed runtime wake probe: exit 0; status `ran`, provider `echo`, one receipt written.
- Installed `holon a2a-ping h --agents-root ... --min-agents 3`: exit 0; three local identity probes passed and wrote receipts.
- `.venv/bin/python -m pytest -q tests/test_model_critic_runner.py tests/test_codex_composer_semantic_inbox_drain.py tests/test_a2a_domain_reply_worker.py tests/test_a2a_domain_reply_artifact.py`: exit 0, `16 passed`.
- `.venv/bin/python -m pytest -q holon/tests tests/test_holon_runtime.py tests/test_model_critic_runner.py tests/test_codex_composer_semantic_inbox_drain.py tests/test_a2a_domain_reply_worker.py tests/test_a2a_domain_reply_artifact.py`: exit 0, `46 passed`.
- `python3 -m compileall -q holon scripts/runtime/model_critic_runner.py scripts/runtime/codex_composer_semantic_inbox_drain.py scripts/runtime/a2a_domain_reply_artifact.py scripts/runtime/a2a_domain_reply_worker.py`: exit 0.
- `.venv/bin/python -m pip wheel --no-deps /Users/dhyana/dharma_swarm/holon -w /private/tmp/holon-dist-isolated`: exit 0; normal isolated PEP 517 build produced wheel sha256 `4ef3846f70d29499fdbd2f653f1ffd41fb9ca259421ed92447324ffd44ed5263`.
- `/private/tmp/holon-standalone-venv2/bin/python -m pip install --force-reinstall /private/tmp/holon-dist-isolated/holon_runtime-0.1.0-py3-none-any.whl`: exit 0; installed metadata has `Metadata-Version: 2.4`, `Provides-Extra: dev`, `RECORD`, console script `holon`, and `dharma_swarm_spec=None`.
- `.venv/bin/python -m pytest -q tests/test_holon_truth_projection.py`: exit 0, `3 passed`.
- `.venv/bin/python -m pytest -q holon/tests tests/test_holon_runtime.py tests/test_holon_truth_projection.py tests/test_runtime_truth_projection_fields.py tests/test_living_dock_verifier.py tests/test_holon_service_liveness.py`: exit 0, `47 passed`.
- `python3 -m compileall -q dharma_swarm/holon_truth_projection.py tests/test_holon_truth_projection.py`: exit 0.
- `.venv/bin/python -m holon verify --json`: exit 0, standalone verifier status `pass` after adding the parent projection adapter.
- `.venv/bin/python -m pytest -q holon/tests`: exit 0, `17 passed` after adding standalone supervisor lock and heartbeat coverage.
- `.venv/bin/python -m pytest -q holon/tests tests/test_holon_runtime.py tests/test_holon_truth_projection.py tests/test_runtime_truth_projection_fields.py tests/test_living_dock_verifier.py tests/test_holon_service_liveness.py tests/test_model_critic_runner.py tests/test_codex_composer_semantic_inbox_drain.py tests/test_a2a_domain_reply_worker.py tests/test_a2a_domain_reply_artifact.py`: exit 0, `68 passed`.
- `python3 -m compileall -q holon dharma_swarm/holon_truth_projection.py tests/test_holon_truth_projection.py scripts/runtime/model_critic_runner.py scripts/runtime/codex_composer_semantic_inbox_drain.py scripts/runtime/a2a_domain_reply_artifact.py scripts/runtime/a2a_domain_reply_worker.py`: exit 0.
- `.venv/bin/python -m holon verify --json`: exit 0, standalone verifier status `pass` after adding `holon/organs/service.py`.
- `.venv/bin/python -m pytest -q holon/tests`: exit 0, `21 passed` after adding provider tool-call execution and provider-reported cost propagation.
- `.venv/bin/python -m pytest -q holon/tests tests/test_holon_runtime.py tests/test_holon_truth_projection.py tests/test_runtime_truth_projection_fields.py tests/test_living_dock_verifier.py tests/test_holon_service_liveness.py tests/test_model_critic_runner.py tests/test_codex_composer_semantic_inbox_drain.py tests/test_a2a_domain_reply_worker.py tests/test_a2a_domain_reply_artifact.py`: exit 0, `72 passed`.
- `python3 -m compileall -q holon dharma_swarm/holon_truth_projection.py tests/test_holon_truth_projection.py scripts/runtime/model_critic_runner.py scripts/runtime/codex_composer_semantic_inbox_drain.py scripts/runtime/a2a_domain_reply_artifact.py scripts/runtime/a2a_domain_reply_worker.py`: exit 0 after provider/runtime updates.
- `.venv/bin/python -m holon verify --json`: exit 0, standalone verifier status `pass` after provider/runtime updates.
- `.venv/bin/python -m pip wheel --no-deps /Users/dhyana/dharma_swarm/holon -w /private/tmp/holon-dist-isolated-rerun`: exit 0; rebuilt wheel sha256 `cee304e0c9d496abe34d18337528edf59356dde8b4c7cf25f7eda6da4f3644d6`.
- `/private/tmp/holon-standalone-venv3/bin/python -m pip install --force-reinstall ...`: exit 1 because that venv was Python 3.9.6 and the package correctly requires Python `>=3.11`.
- `.venv/bin/python -m venv /private/tmp/holon-standalone-venv4`: exit 0; created Python 3.13 venv.
- `/private/tmp/holon-standalone-venv4/bin/python -m pip install --force-reinstall /private/tmp/holon-dist-isolated-rerun/holon_runtime-0.1.0-py3-none-any.whl`: exit 0.
- `/private/tmp/holon-standalone-venv4/bin/python -m holon verify --json` from `/private/tmp`: exit 0, installed verifier status `pass`.
- Installed import probe from `/private/tmp`: exit 0; `holon_file=/private/tmp/holon-standalone-venv4/lib/python3.13/site-packages/holon/__init__.py`, distribution version `0.1.0`, and `dharma_swarm_spec=None`.
- `.venv/bin/python -m pytest -q holon/tests`: exit 0, `23 passed` after adding `holon burn-in` and source-proof coverage.
- `.venv/bin/python -m holon burn-in h --agents-root reports/sovereign_holons/standalone_holon_phase1_20260626/agents --prompt "observe continuity" --duration-seconds 0 --interval-seconds 0 --min-cycles 2 --multi-hour-threshold-seconds 7200`: exit 0; wrote burn-in receipt `reports/sovereign_holons/standalone_holon_phase1_20260626/agents/h/receipts/hrcpt_34cb3a0b22e8b8f7eee63ec5.json`, `sample_count=2`, `passed=true`, `multi_hour_proven=false`, source digest `sha256:a5d1cf467830ae6efe4ab989bd41a17e09bb35e90f497790d1d0e8af9956bffe`.
- `.venv/bin/python -m pytest -q holon/tests tests/test_holon_runtime.py tests/test_holon_truth_projection.py tests/test_runtime_truth_projection_fields.py tests/test_living_dock_verifier.py tests/test_holon_service_liveness.py tests/test_model_critic_runner.py tests/test_codex_composer_semantic_inbox_drain.py tests/test_a2a_domain_reply_worker.py tests/test_a2a_domain_reply_artifact.py`: exit 0, `74 passed`.
- `python3 -m compileall -q holon dharma_swarm/holon_truth_projection.py tests/test_holon_truth_projection.py scripts/runtime/model_critic_runner.py scripts/runtime/codex_composer_semantic_inbox_drain.py scripts/runtime/a2a_domain_reply_artifact.py scripts/runtime/a2a_domain_reply_worker.py`: exit 0 after burn-in/source-proof updates.
- `.venv/bin/python -m holon verify --json`: exit 0, standalone verifier status `pass` with `burn_in.py` and `source_proof.py`.
- `.venv/bin/python -m pip wheel --no-deps /Users/dhyana/dharma_swarm/holon -w /private/tmp/holon-dist-isolated-burnin`: exit 0; rebuilt wheel sha256 `215f688d4128e9d377092896015f24675cd7975dc3a02fd65cb88d4e2847000b`.
- `/private/tmp/holon-standalone-venv5/bin/python -m pip install --force-reinstall /private/tmp/holon-dist-isolated-burnin/holon_runtime-0.1.0-py3-none-any.whl`: exit 0.
- `/private/tmp/holon-standalone-venv5/bin/python -m holon verify --json` from `/private/tmp`: exit 0, installed verifier status `pass`.
- Installed import probe from `/private/tmp`: exit 0; `holon_file=/private/tmp/holon-standalone-venv5/lib/python3.13/site-packages/holon/__init__.py`, distribution version `0.1.0`, and `dharma_swarm_spec=None`.
- `/private/tmp/holon-standalone-venv5/bin/python -m holon burn-in h --agents-root /private/tmp/holon-installed-agents --prompt "observe installed continuity" --duration-seconds 0 --interval-seconds 0 --min-cycles 1 --multi-hour-threshold-seconds 7200`: exit 0; installed-package burn-in receipt `/private/tmp/holon-installed-agents/h/receipts/hrcpt_78c772aa02f49210457b6740.json`, `passed=true`, `multi_hour_proven=false`, source digest `sha256:6bca60ff32ce1226995c213c991c2fbd4682ae9c12f20dc62fcda169de657175`, and `dharma_swarm_spec=None`.
- Live A2A sends to `codex_composer`, `hermes-m5`, and `fable_composer`: exit 0; all three returned `HANDLER_ACKED` send receipts.
- Local semantic drains for those original packets: final accepted drains used local Ollama and wrote packet-level SemanticReceipts with `source_audit_claim=false`; these are documented in `A2A_LIVE_REPAIR_RECEIPT.md`.
- `NATS_URL=nats://127.0.0.1:4222 .venv/bin/python scripts/runtime/a2a_domain_reply_worker.py ...`: exit 0 for all three original packets; final domain receipts are:
  `reports/a2a/domain_reply_receipts/20260626T002940Z-codex_composer-2bbba006f775.json`,
  `reports/a2a/domain_reply_receipts/20260626T002942Z-hermes-m5-cf4716e01dc7.json`,
  `reports/a2a/domain_reply_receipts/20260626T002943Z-fable_composer-5aa607b21b57.json`.
- Attempted external `glm-5:cloud` semantic drain was rejected before execution because it would send private repo context to an external model route; the accepted path used local Ollama only.
- Source-audit A2A packet send to `codex_composer`, `hermes-m5`, `fable_composer`, and a follow-up send to `opus_composer`: exit 0; all four returned `HANDLER_ACKED` send receipts:
  `reports/a2a/send_receipts/20260626T010618Z-codex_composer-holon-source-audit-codex-20260626.json`,
  `reports/a2a/send_receipts/20260626T010621Z-hermes-m5-holon-source-audit-hermes-20260626.json`,
  `reports/a2a/send_receipts/20260626T010621Z-fable_composer-holon-source-audit-fable-20260626.json`,
  and `reports/a2a/send_receipts/20260626T014034Z-opus_composer-holon-source-audit-opus-20260626.json`.
- Source-audit semantic drain attempt: `codex_composer`, `fable_composer`, and `opus_composer` produced final valid SemanticReceipts with `source_audit_claim=true`; `hermes-m5` remained a typed failure. The source-gated A2A identity threshold is satisfied at 3/4, but authenticated target-runtime execution is not claimed.
- Source-audit domain replies and reply capture: all four final domain replies were published as `DOMAIN_RECEIPTED`, with source-gated payloads for `codex_composer`, `fable_composer`, and `opus_composer`:
  `reports/a2a/domain_reply_receipts/20260626T013809Z-codex_composer-holon-source-audit-codex-20260626.json`,
  `reports/a2a/domain_reply_receipts/20260626T014921Z-hermes-m5-holon-source-audit-hermes-20260626.json`,
  `reports/a2a/domain_reply_receipts/20260626T013811Z-fable_composer-holon-source-audit-fable-20260626.json`,
  and `reports/a2a/domain_reply_receipts/20260626T014238Z-opus_composer-holon-source-audit-opus-20260626.json`.
  Reply-capture receipts prove the reply subjects were capturable as `DOMAIN_RECEIPTED`; `hermes-m5` has latest corrected typed-failure capture and `opus_composer` has final source-gated reply capture, while codex/fable have earlier domain captures:
  `reports/a2a/reply_receipts/20260626T012510Z-codex_composer-holon-source-audit-codex-20260626.json`,
  `reports/a2a/reply_receipts/20260626T015127Z-hermes-m5-holon-source-audit-hermes-20260626.json`,
  `reports/a2a/reply_receipts/20260626T012509Z-fable_composer-holon-source-audit-fable-20260626.json`,
  and `reports/a2a/reply_receipts/20260626T014251Z-opus_composer-holon-source-audit-opus-20260626.json`.
- Provider cost fallback: `estimate_usage_cost_usd` now prefers provider-reported dollar cost and otherwise estimates from usage tokens when operator-supplied `HOLON_<PROVIDER>_*_USD_PER_1M_TOKENS` rates are configured; `.venv/bin/python -m pytest -q holon/tests` passed with `27 passed`.
- `python3 -m compileall -q holon`: exit 0 after provider pricing updates.
- `.venv/bin/python -m holon verify --json`: exit 0 after provider pricing updates.
- Fresh isolated package proof after provider pricing: `.venv/bin/python -m pip wheel --no-deps /Users/dhyana/dharma_swarm/holon -w /private/tmp/holon-dist-isolated-provider-pricing`: exit 0; rebuilt current wheel sha256 `6fe306162a7ead6af9269b8d906c3f5b712bbcf77e063a07b2f55c380e412390`.
- `/private/tmp/holon-standalone-venv-provider-pricing/bin/python -m pip install --force-reinstall /private/tmp/holon-dist-isolated-provider-pricing/holon_runtime-0.1.0-py3-none-any.whl`: exit 0.
- `/private/tmp/holon-standalone-venv-provider-pricing/bin/python -m holon verify --json` from `/private/tmp`: exit 0, installed verifier status `pass`.
- Installed import probe from `/private/tmp`: exit 0; `holon_file=/private/tmp/holon-standalone-venv-provider-pricing/lib/python3.13/site-packages/holon/__init__.py`, distribution version `0.1.0`, console script `holon`, and `dharma_swarm_spec=false`.
- Current source proof check: checkout `holon/` source digest `sha256:bbf1012f01acd995b3cf62d8fa98f28426acf96ce01d21b6fb47a081875631d4`; fresh installed package source digest `sha256:2c5598d66d241ff3cacbcea9072ba707e41d0f1d81f0f3d8ce3cf6458cf69d1e`.
- Fresh installed burn-in smoke first attempt from `/private/tmp` failed with `FileNotFoundError` because `/private/tmp/holon-installed-agents-provider-pricing/h/identity.json` did not exist. This was a setup failure, not a package import failure.
- After creating minimal temp identity `{"model":"holon-echo-v1","provider":"echo","system_prompt":"I am h."}`, `/private/tmp/holon-standalone-venv-provider-pricing/bin/python -m holon burn-in h --agents-root /private/tmp/holon-installed-agents-provider-pricing --prompt "observe installed provider-pricing continuity" --duration-seconds 0 --interval-seconds 0 --min-cycles 1 --multi-hour-threshold-seconds 7200`: exit 0; receipt `/private/tmp/holon-installed-agents-provider-pricing/h/receipts/hrcpt_86e2699992dc0e295e12feb8.json`, `passed=true`, `sample_count=1`, `multi_hour_proven=false`, installed source digest `sha256:2c5598d66d241ff3cacbcea9072ba707e41d0f1d81f0f3d8ce3cf6458cf69d1e`.
- A2A receipt truthfulness hardening: semantic failures now publish `semantic_audit_depth=typed_failure` instead of carrying stale `source_audit`; `a2a_reply_capture.py --deliver-policy latest` can capture the latest reply-subject payload when JetStream replay would otherwise return older messages.
- `.venv/bin/python -m pytest -q tests/test_a2a_reply_capture.py tests/test_codex_composer_semantic_inbox_drain.py tests/test_a2a_domain_reply_worker.py tests/test_a2a_domain_reply_artifact.py holon/tests`: exit 0, `49 passed`.
- `.venv/bin/python -m pytest -q holon/tests tests/test_holon_runtime.py tests/test_holon_truth_projection.py tests/test_runtime_truth_projection_fields.py tests/test_living_dock_verifier.py tests/test_holon_service_liveness.py tests/test_model_critic_runner.py tests/test_codex_composer_semantic_inbox_drain.py tests/test_a2a_domain_reply_worker.py tests/test_a2a_domain_reply_artifact.py tests/test_a2a_reply_capture.py`: exit 0, `87 passed`.
- `python3 -m compileall -q scripts/runtime/a2a_reply_capture.py scripts/runtime/codex_composer_semantic_inbox_drain.py scripts/runtime/a2a_domain_reply_worker.py holon`: exit 0.
- `.venv/bin/python -m holon verify --json`: exit 0 after A2A receipt truthfulness updates.
- Provider credential operator-contact path: direct human ask was avoided. A narrow secret-reference request was routed through `operator_guide_cursor` over A2A:
  `reports/sovereign_holons/standalone_holon_phase1_20260626/operator_proxy/HOLON_PROVIDER_SECRET_PROXY_REQUEST.md`.
  The first send without `NATS_URL` wrote `NATS_SECRETS_MISSING`:
  `reports/a2a/send_receipts/20260626T015411Z-operator_guide_cursor-holon-provider-secret-proxy-20260626.json`.
  The retry with `NATS_URL=nats://127.0.0.1:4222` returned `OPERATOR_GUIDE_CURSOR_CONSUMED` / `HANDLER_ACKED`:
  `reports/a2a/send_receipts/20260626T015442Z-operator_guide_cursor-holon-provider-secret-proxy-20260626.json`.
  Delivery receipt:
  `reports/a2a/inbox_bridge_receipts/20260626T015435Z-operator_guide_cursor-holon-provider-secret-proxy-20260626.json`.
  Latest reply capture:
  `reports/a2a/reply_receipts/20260626T020007Z-operator_guide_cursor-holon-provider-secret-proxy-20260626.json`, status `NO_REPLY`; no secret-reference handle is available yet.
- Multi-hour burn-in launched in tmux session `holon_multi_hour_burnin_20260626` with log `reports/sovereign_holons/standalone_holon_phase1_20260626/holon_multi_hour_burnin.log`; as of 2026-06-26T02:31:55Z it is still running and has written hash-chained service heartbeats through cycle 67. This is not a completed multi-hour proof until the final receipt reports `multi_hour_proven=true`.

## Hermes Parity Matrix

| Capability | Phase 1 evidence | Status |
|---|---|---|
| Independent packaging | `holon/pyproject.toml`, local PEP 517 backend, fresh isolated wheel install with current wheel sha256 `6fe306162a7ead6af9269b8d906c3f5b712bbcf77e063a07b2f55c380e412390` | Pass |
| CLI entrypoint | `holon` console script and `python -m holon` verifier | Pass |
| Agent loop | `HolonRuntime.run_provider_cycle`, `holon_wake_cycle`, `run_holon_loop` | Partial |
| Provider routing/fallback | Identity-aware `ProviderRouter` with OpenAI/OpenRouter optional routes, echo fallback, provider-reported cost propagation, operator-configured token-price fallback, and route-level max-cost fail-closed behavior | Partial; live key-backed provider run pending |
| Tool registry | `ToolRegistry` plus artifact writer returning `ArtifactRef`; runtime executes provider tool-call envelopes and OpenAI-compatible tool calls normalize into that envelope | Pass for local execution |
| Memory/session lifecycle | Standalone read-only `MemoryKernel`, wake ledger, restart tests | Pass for local loop |
| Receipts | Side-effect-key-idempotent `EvidenceReceipt` JSON and JSONL index | Pass |
| Restart safety | `resume_point`, loop restart test, and supervisor next-cycle test | Pass |
| Kill/budget drills | Unit tests cover kill, budget, mid-loop halt | Pass |
| Long-running supervision | `SupervisorConfig`, bounded supervisor entrypoint, non-blocking service lock, stale-lock recovery, hash-chained `service_heartbeats.jsonl`, and `holon burn-in` receipts with source proof | Partial; multi-hour burn-in pending |
| Live external providers | Not proven; local provider keys absent in toolbelt status; a safe secret-reference request was routed through `operator_guide_cursor` A2A and handler-acked | Pending on proxy response |
| Independent multi-agent audit | Live A2A handler ACKs, domain receipts, and reply-capture receipts for four agent identities; source-audit prompts produced valid source-gated receipts for `codex_composer`, `fable_composer`, and `opus_composer`, while `hermes-m5` remains a typed failure | Partial; source-gated identity threshold 3/4, authenticated target-runtime audit still not claimed |

## Dharma Swarm Integration Matrix

| Dharma strength | Phase 1 binding | Status |
|---|---|---|
| LivingDock | Uses `~/.dharma/agents/<agent>` shape and local identity files | Partial |
| Runtime truth / receipts | Local receipt adapter plus parent-side `dharma_swarm.holon_truth_projection.project_holon_receipt`, projecting standalone receipts into `ExecutionIdentity`, `TaskClaim`, `DelegationRun`, `ArtifactRecord`, and `side_effect_complete` rows | Pass for projection adapter |
| Semantic inbox / A2A | Local identity probes plus live `HANDLER_ACKED`, domain publish, and reply-captured `DOMAIN_RECEIPTED` receipts for four agent identities; valid source-gated semantic proof exists for `codex_composer`, `fable_composer`, and `opus_composer`, while `hermes-m5` source-audit drain is a typed failure | Partial |
| Verifier discipline | `holon.verifier` plus isolated install proof | Pass |
| L4 lock/heartbeat patterns | Standalone supervisor now uses atomic lock files and hash-chained service heartbeats without parent imports | Pass for local supervisor |
| Parent adapters only | Core has no parent imports; parent projection lives in `dharma_swarm/holon_truth_projection.py` only | Pass |

## Contamination Report

Standalone core scan found no `dharma_swarm` imports and no dashboard/APEX/control-surface tokens in non-test `holon/*.py` sources. The installed package also verifies cleanly with the parent package absent from the isolated environment.

## Audit Hardening Report

Three read-only explorer audits were run after the first Phase 1 receipt. The follow-up patch addressed:

- packaging metadata version and dev extras in the custom PEP 517 backend
- normal isolated build proof with wheel hash and installed metadata
- verifier dynamic-import and case-insensitive token bypasses
- identity-aware provider routing
- artifact-backed outcome pass path and artifact writer `ArtifactRef`
- side-effect-key receipt idempotency
- supervisor next-cycle resume
- kill/budget early halt side-effect suppression
- A2A safe packet filenames and `0600` writes
- A2A source-audit and authenticated-runtime claim boundaries

Parent truth projection hardening added after the audit: `project_holon_receipt` is deterministic by source receipt id, verifies the standalone receipt digest, records lifecycle rows with provider/model accounting context, links artifact records, carries LivingDock verifier findings, and blocks the parent projection when LivingDock is required and failing.

Standalone supervisor hardening added after the audit: `run_supervisor` now acquires a non-blocking atomic lock before runtime construction, recovers expired locks, releases owned locks in `finally`, writes hash-chained running/idle/paused service heartbeats, and returns lock/liveness details in the supervisor receipt.

Provider/tool hardening added after the audit: OpenAI-compatible routes now send tool schemas, normalize returned function calls into a runtime tool envelope, execute tools through `ToolRegistry`, attach `ArtifactRef` results before the artifact gate, halt failed tool calls with receipts, propagate provider-reported dollar cost, and fail closed when a router cost cap is exceeded.

Burn-in/source-proof hardening added after the audit: `holon burn-in` runs real supervisor samples, records per-sample supervisor receipts and liveness, includes portable source-tree digests plus git context when available, and explicitly reports `multi_hour_proven=false` for short smoke runs.

Provider price hardening added after the audit: OpenAI-compatible providers now keep cost accounting fail-closed under route caps by using provider-reported dollar cost when present and estimating token cost from operator-supplied per-million-token rates when only usage tokens are returned. Vendor prices are not hard-coded into the package.

A2A receipt truthfulness hardening added after the audit: semantic drain and domain publish code now distinguishes `source_audit`, `packet_only`, and `typed_failure`, and reply capture has an opt-in latest-message policy for JetStream subjects with older queued replies.

Remaining hardening gaps: live key-backed provider burn-in with configured price rates and approved secret-reference handle, immutable commit hash for source-to-proof binding, authenticated target-runtime A2A audits, and completed multi-hour supervisor burn-in.

## A2A Repair Report

Live A2A repair was performed after the initial package gates. Three tmux inbox bridge sessions were started for `codex_composer`, `hermes-m5`, and `fable_composer`; all three accepted the audit packet with `HANDLER_ACKED`. The delivered packets were then drained through local Ollama-backed SemanticReceipt generation and published back to their recorded reply subjects as typed domain receipts.

Detailed evidence is recorded in:

`reports/sovereign_holons/standalone_holon_phase1_20260626/A2A_LIVE_REPAIR_RECEIPT.md`

Boundary: this proves live A2A transport plus typed packet-level semantic/domain receipt repair. It does not prove a long-running autonomous peer daemon independently inspected the full source tree; the final objective still requires deeper independent audits, live provider burn-in, and multi-hour supervisor gates.

## A2A Source-Audit Attempt

A source-audit packet was then sent to the same three target identities, then
rerouted once to `opus_composer` to satisfy the three-source-gated-identity
threshold after `hermes-m5` failed semantic validation. All four reached A2A
handler acknowledgment and all four final domain replies were published as
typed `DOMAIN_RECEIPTED` payloads:

`reports/sovereign_holons/standalone_holon_phase1_20260626/a2a_source_audit/A2A_SOURCE_AUDIT_RECEIPT.md`

The source-audit claim is source-gated but bounded. `codex_composer`,
`fable_composer`, and `opus_composer` produced valid local SemanticReceipts
with `source_audit_claim=true`; `hermes-m5` remains a typed semantic failure.
This satisfies the three-identity source-gated A2A audit threshold, but it does
not prove authenticated target-runtime execution or final Hermes-grade
agreement.

## Verdict

Phase 1 improves the requested end state: `holon/` is now a standalone installable package with local runtime closure, receipts, verifier, CLI, tests, isolated install proof, parent runtime-truth projection, provider tool execution, operator-configured token-cost fallback, service lock/heartbeat supervision, burn-in smoke receipts, source-tree proof, and live A2A semantic/domain receipt repair. It is not yet proven Hermes-grade or better because completed multi-hour supervisor burn-in, live key-backed provider burn-in, clean immutable commit binding, and independent source audits remain open.
