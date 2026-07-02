# Qwen Code DeepSeek V4 Pro Wiring - 2026-07-01 JST

## Decision

Wire `qwen_code` to `deepseek-v4-pro` as its primary real model backend.

## Backend

| Field | Value |
| --- | --- |
| Agent | `qwen_code` |
| Harness | `qwen_code_cli` |
| Provider | `deepseek` |
| Model | `deepseek-v4-pro` |
| Endpoint | `openai-compatible://api.deepseek.com/deepseek-v4-pro` |
| Qwen auth type | `openai` |
| Required env var | `DEEPSEEK_API_KEY` |
| Qwen/OpenAI env mapping | `DEEPSEEK_API_KEY -> OPENAI_API_KEY`, `OPENAI_BASE_URL=https://api.deepseek.com`, `OPENAI_MODEL=deepseek-v4-pro` |
| Authority | `external_worker_evidence_only` |

## Updated Surfaces

- `/Users/dhyana/.qwen/settings.json`
- `/Users/dhyana/.dharma/agents/qwen_code/living_agent.json`
- `/Users/dhyana/.dharma/a2a/cards/qwen-code.json`
- `/Users/dhyana/.dharma/external_agents/qwen_code/registration.json`
- `/Users/dhyana/.dharma/external_agents/qwen_code/identity_manifest.normalized.json`
- `/Users/dhyana/.dharma/a2a_bus/state/qwen_code.json`
- `examples/agents/qwen_code.registration.json`
- `docs/agents/qwen_code/ML_SPECIALIST_CHARTER.md`
- `scripts/runtime/qwen_code_deepseek_smoke.py`

## Boundary

No API key was written to any manifest, card, source file, receipt, or report.

This does not promote `qwen_code` to a sovereign holon and does not enable autonomous dispatch. It remains manual, evidence-only, and must not write source or approve work unless explicitly assigned.

## Verification Plan

Run:

```bash
python3 scripts/runtime/qwen_code_deepseek_smoke.py
```

with `DEEPSEEK_API_KEY` present in the environment. The script writes a non-secret JSON receipt under:

```text
reports/agentops/deepseek_smokes/
```

## Live Smoke Receipt

Status: `pass`

Receipt:

```text
reports/agentops/deepseek_smokes/qwen-code-deepseek-v4-pro-smoke-20260630T153740Z.json
```

Observed:

- `qwen_version`: `0.17.1`
- `model`: `deepseek-v4-pro`
- `provider`: `deepseek`
- `returncode`: `0`
- expected marker returned: `QWEN_DEEPSEEK_V4_PRO_LIVE_OK`
- duration: `3.844s`

Post-smoke state: `live_smoke_passed_evidence_only`

Autonomous dispatch remains disabled.
