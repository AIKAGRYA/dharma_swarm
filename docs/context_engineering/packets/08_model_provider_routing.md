# Packet 08: Model, Provider, Key, And Routing Layer

Packet ID: `ctx.model-provider-routing`

Use when touching provider adapters, model routing, keys, `dkeys`, model pool,
OpenAI/Ollama/DeepSeek/Qwen routes, verifier-ranker model use, or live provider
telemetry.

Do not use for prompt content or agent identity unless model selection is the
actual issue.

## Authority Model

- Key owner: `~/.dharma/agent_keys.env` managed only by `dkeys`
- Key access owner: `dharma_swarm/api_keys.py`
- Routing owner: `dharma_swarm.runtime_provider.resolve_runtime_provider_config`
- Provider owners: `dharma_swarm/providers.py`, provider adapters,
  `dharma_swarm/model_hierarchy.py`, `dharma_swarm/model_pool_registry.py`
- Telemetry owner: provider attempts in runtime DB and `make onboard`
- Proof owner: provider smoke tests, routing guard tests, live attempt telemetry

Core invariant: one key home, one key tool, one resolver door.

## Mission

Prevent dead-provider spirals, secret leakage, and hardcoded model drift. The
model layer should choose the strongest live available route, fail over
honestly, and never bypass the resolver or key rules.

## First Reads

L0 Safety:

- `make onboard`
- `docs/ops/MODEL_KEY_ROUTING.md`

L1 Route:

- provider/model section in `make onboard`
- relevant active track if provider work is part of a larger loop

L2 Owners:

- `dharma_swarm/runtime_provider.py`
- `dharma_swarm/providers.py`
- `dharma_swarm/api_keys.py`
- `dharma_swarm/model_hierarchy.py`
- `dharma_swarm/model_pool_registry.py`

L3 Evidence:

- `reports/agentops/QWEN_CODE_DEEPSEEK_V4_PRO_WIRING_20260701.md`
- `reports/agentops/deepseek_smokes/**`
- provider attempt telemetry from runtime DB/onboard

L4 Search:

- `rg -n "resolve_runtime_provider_config|create_runtime_provider|DEFAULT_MODELS|API_KEY|model_hierarchy|provider_attempts" dharma_swarm scripts tests docs`

L5 Seat:

- `qwen_code` when ML/NVIDIA skill stewardship is relevant, but do not let seat
  context override provider routing rules.

## Live Probes

```bash
make onboard
dkeys test
```

For code changes:

```bash
pytest tests/test_runtime_provider.py tests/test_provider_smoke.py tests/test_model_key_routing_guard.py tests/test_model_pool_registry.py
```

Do not print secrets. Redact environment output.

## Retrieval Contract

- Query: "one key home one resolver door model routing"
  Source family: `docs/ops/MODEL_KEY_ROUTING.md`.
- Query: "provider attempts live green blocked degraded"
  Source family: `make onboard`, runtime DB telemetry.
- Query: "qwen code deepseek v4 pro wiring"
  Source family: agentops reports and tests.

## Operating Loop

1. Confirm whether this is key management, route selection, adapter behavior,
   fallback, telemetry, or tests.
2. Read `MODEL_KEY_ROUTING.md`.
3. Use `dkeys` for key status; never inspect or copy secret values.
4. Route all code through the resolver.
5. Add provider defaults in the existing adapter/defaults pattern.
6. Verify with routing guard tests and smoke tests.
7. Handoff with provider status and no secrets.

## Guardrails

- Never hardcode model strings in runtime modules.
- Never read provider keys directly from `os.environ` outside `api_keys.py`.
- Never add keys outside `dkeys`.
- Never commit keys, tokens, headers, or raw provider responses with secrets.
- Never block on a dead provider if fallback is available.
- Never route Anthropic to metered API by default when Max/Claude Code route is
  intended.

## Context Budget

- Tiny: `make onboard`, model key routing doc, this packet.
- Standard: tiny plus runtime provider, provider adapter, tests.
- Deep: standard plus telemetry, model pool reports, smoke receipts.

## Done Criteria

Complete means:

- no secrets are exposed;
- routing goes through the resolver;
- tests or live telemetry prove the behavior;
- fallback/degraded state is honest;
- handoff includes no key material.

## Agent Prompt Block

```text
You are working in Dharma Swarm using context packet ctx.model-provider-routing.
Read MODEL_KEY_ROUTING.md first. There is one key home, one key tool, and one
resolver door. Do not hardcode model strings or read keys directly. Use dkeys only
for key status and redact all sensitive output. Verify with runtime provider,
provider smoke, model key guard, or model pool tests.
```

## Handoff Receipt Shape

```json
{
  "packet_id": "ctx.model-provider-routing",
  "work_type": "key_management|route_selection|adapter|fallback|telemetry|test",
  "providers_touched": [],
  "resolver_paths": [],
  "commands_run": [],
  "tests": [],
  "live_status": "",
  "secrets_exposed": false,
  "fallback_behavior": ""
}
```
