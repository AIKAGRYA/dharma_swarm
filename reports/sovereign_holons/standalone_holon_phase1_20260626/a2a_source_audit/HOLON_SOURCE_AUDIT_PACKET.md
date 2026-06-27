# Standalone Holon Source Audit Request

Date: 2026-06-26
Sender: codex
Target agents: codex_composer, hermes-m5, fable_composer
Scope: `/Users/dhyana/dharma_swarm/holon` plus parent projection

## Request

Review whether the current standalone `holon/` runtime is isolated, packageable,
receipt-backed, and materially closer to a Hermes-grade standalone holon runtime.
Do not claim a full pass unless the evidence supports it.

Required audit boundaries:

- This is a source-level audit of the current source tree and recorded commands.
- This is not a multi-hour burn-in proof. The bounded burn-ins passed but have
  `multi_hour_proven=false`.
- This is not a clean immutable release proof. The repository is dirty.
- This is not a claim that cloud providers reviewed source. Source review must
  stay local.

## Source Proof

- `holon/` source tree digest:
  `sha256:a5d1cf467830ae6efe4ab989bd41a17e09bb35e90f497790d1d0e8af9956bffe`
- Git HEAD:
  `01d22b94fc05bf4bb248c2f51b09102377129d25`
- Git dirty: `true`
- Git status digest for `holon/`:
  `sha256:49c4410178a0bcc22caac00e9f7e974493b9a368ae11048631cebd27850b6fca`
- Installed wheel digest from isolated build:
  `sha256:215f688d4128e9d377092896015f24675cd7975dc3a02fd65cb88d4e2847000b`

## Key Source Files

- `holon/holon_runtime.py`
  `sha256:bfe13b56848d2ccf9de51a92b377240c674f9c3274200f79332f06ad51ca836b`
- `holon/providers.py`
  `sha256:e964acd2238579606c9ee94ceef55db83bfc04a11eb5e97dc752f4a1702ccb2e`
- `holon/supervisor.py`
  `sha256:10e4391c3ec7679f3650fb3facb23acb89729be94dbb6969991d415c284b4339`
- `holon/organs/service.py`
  `sha256:fd0201ff419e8a400a0d75ef695b05181b542dfe0e5deebcb1837bd4285ebc3d`
- `holon/burn_in.py`
  `sha256:8618bf579aef487179e8772d68cfe53b60dc329073c540f4798de43176392349`
- `holon/source_proof.py`
  `sha256:18c30f4574b3707d602eebb711068d98168cf54e2d2073710e4716a34a220d26`
- `dharma_swarm/holon_truth_projection.py`
  parent projection for standalone receipts

## Verification Already Run

- `.venv/bin/python -m pytest -q holon/tests`
  result: `23 passed in 0.28s`
- `.venv/bin/python -m pytest -q holon/tests tests/test_holon_runtime.py tests/test_holon_truth_projection.py tests/test_runtime_truth_projection_fields.py tests/test_living_dock_verifier.py tests/test_holon_service_liveness.py tests/test_model_critic_runner.py tests/test_codex_composer_semantic_inbox_drain.py tests/test_a2a_domain_reply_worker.py tests/test_a2a_domain_reply_artifact.py`
  result: `74 passed in 2.51s`
- `python3 -m compileall -q holon dharma_swarm/holon_truth_projection.py tests/test_holon_truth_projection.py scripts/runtime/model_critic_runner.py scripts/runtime/codex_composer_semantic_inbox_drain.py scripts/runtime/a2a_domain_reply_artifact.py scripts/runtime/a2a_domain_reply_worker.py`
  result: pass
- `.venv/bin/python -m holon verify --json`
  result: `status=pass`
- Source-tree bounded burn-in:
  receipt `reports/sovereign_holons/standalone_holon_phase1_20260626/agents/h/receipts/hrcpt_34cb3a0b22e8b8f7eee63ec5.json`
  result: `passed=true`, `sample_count=2`, `multi_hour_proven=false`
- Installed wheel verification:
  `/private/tmp/holon-standalone-venv5/bin/python -m holon verify --json`
  result: `status=pass`, `dharma_swarm_spec=None`
- Installed package burn-in smoke:
  receipt `/private/tmp/holon-installed-agents/h/receipts/hrcpt_78c772aa02f49210457b6740.json`
  result: `passed=true`, `multi_hour_proven=false`

## Audit Questions

1. Does the source show standalone operation without requiring parent
   `dharma_swarm` imports inside the installed `holon` package?
2. Do provider routing, tool-call execution, budget enforcement, and artifact
   gates fail closed enough to prevent unreceipted outcome claims?
3. Does `holon/organs/service.py` provide enough service lock, heartbeat, stale
   recovery, and liveness evidence for an L4-style single-runner guard?
4. Does the parent projection in `dharma_swarm/holon_truth_projection.py`
   honestly bind standalone receipts back to runtime truth without making the
   standalone package depend on the parent?
5. What remaining gaps block a Hermes-grade-or-better claim?

Return a typed SemanticReceipt. If you inspected source excerpts, include an
acceptance gate named `source_audit_inspected_current_holon_source` with
`met=true`; otherwise leave `source_audit_claim=false`.
