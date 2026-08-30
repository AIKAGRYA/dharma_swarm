# Model & Key Routing - The One Way

Current as of 2026-07-05.

Read this before any agent touches provider keys, model IDs, routing, or Forge
benchmarks. This is the operational source of truth. Older architecture notes
are background only.

## The Contract

- New key writes have one canonical destination: `~/.dharma/agent_keys.env`.
- Keys are managed by one tool: `dkeys`.
- The versioned tool source is `scripts/dkeys.py`; install it with
  `install -m 700 scripts/dkeys.py ~/.dharma/bin/dkeys`.
- Code reads keys through one module: `dharma_swarm/api_keys.py`.
- Shell and launchd entrypoints source one loader:
  `scripts/load_runtime_env.sh`.
- Model/provider resolution enters through one door:
  `dharma_swarm.runtime_provider.resolve_runtime_provider_config()` followed by
  `create_runtime_provider()`.
- Provider order and lane roles come from `dharma_swarm/model_hierarchy.py`.
- Model-grain routes and the Kimi K2.6-class floor live in
  `dharma_swarm/model_pool.py` and `dharma_swarm/evolution_roster.py`.

Do not add project `.env` files, ad hoc key readers, provider-specific routers,
or hardcoded model strings in unrelated modules.

## Key Rules

Use:

```bash
dkeys
dkeys test
dkeys add VAR              # hidden prompt; value never enters argv/history
printf '%s' "$VALUE" | dkeys add VAR --stdin
dkeys find KIMI_API_KEY    # variable-name fragments only; values stay redacted
dkeys safe-json            # automation-safe status; no values, masks, or lengths
dkeys exec XAI_API_KEY -- your-command --flag
```

`dkeys env` is deliberately disabled. Never print, copy, or synchronize the
whole key store. A remote holon gets a named/scoped secret grant for its child
process; SSH reachability is not authorization to replicate credentials.
`dkeys exec` strips every other stored provider variable from the child
environment and injects only the named references; it invokes the command
directly, without a shell.

Legacy stores may still be read by the transitional runtime loader. That is a
migration fact, not permission to add another store. New writes go only to the
canonical destination above.

For the scheduled/operator refresh path, use:

```bash
make provider-check
```

That runs `scripts/refresh_provider_status.sh`, which sources
`scripts/load_runtime_env.sh`, runs `dkeys test` when available, and refreshes
`~/.dharma/logs/provider_credits_latest.json`.

Then route through code like:

```python
from dharma_swarm.models import ProviderType
from dharma_swarm.runtime_provider import (
    create_runtime_provider,
    resolve_runtime_provider_config,
)

config = resolve_runtime_provider_config(ProviderType.KIMI_CODE)
provider = create_runtime_provider(config)
```

Never read `os.environ["..._API_KEY"]` outside `api_keys.py`, and never pass a
secret value in a command-line argument.

## Current First-Party Lanes

Kimi Code:

- Provider enum: `ProviderType.KIMI_CODE`
- Key: `KIMI_API_KEY`
- Alias accepted: `MOONSHOT_KIMI_API_KEY`
- Base URL: `https://api.kimi.com/coding/v1`
- Model ID: `k3`
- Provider class: `KimiCodeProvider`
- Note: Kimi Code forces `temperature=1`; the provider normalizes this.

Z.ai Coding:

- Provider enum: `ProviderType.ZHIPU`
- Key: `ZHIPU_API_KEY`
- Aliases accepted: `GLM_API_KEY`, `ZAI_API_KEY`, `ZHIPUAI_API_KEY`,
  `BIGMODEL_API_KEY`
- Base URL: `https://api.z.ai/api/coding/paas/v4`
- Model ID: `glm-5.2`
- Provider class: `ZhipuProvider`
- Note: the coding-plan endpoint is intentional. The generic Z.ai endpoint can
  reject coding-plan keys even when coding quota is live.

Claude/OpenAI subscription lanes:

- `ProviderType.CLAUDE_CODE` routes through the Claude CLI / Max plan.
- `ProviderType.CODEX` routes through the Codex CLI / OpenAI subscription.
- The metered Anthropic/OpenAI APIs are not the default escape hatch unless the
  caller explicitly forces that route.

## Routing Files

- `dharma_swarm/api_keys.py`: canonical env var names, aliases, runtime env load.
- `dharma_swarm/models.py`: `ProviderType` enum.
- `dharma_swarm/model_defaults.py`: one per-provider default model map.
- `dharma_swarm/model_hierarchy.py`: provider tiers, roles, intelligence seed.
- `dharma_swarm/model_pool.py`: logical model pool, provider routes, power floor.
- `dharma_swarm/key_oracle.py`: reads `dkeys test` status without key material.
- `dharma_swarm/runtime_provider.py`: resolver and provider factory.
- `dharma_swarm/providers.py`: concrete provider implementations.
- `scripts/refresh_provider_status.sh`: one scheduled/manual refresh for
  `keys_status.json` plus credit-health heuristics.

## Forge Benchmark Entry Points

Use these only after `dkeys test` shows the needed provider lanes are live.

Roster/canonical measurement:

```bash
PYTHONPATH=$PWD python -m dharma_swarm.forge_v1.canonical census --strategy explore -n 12
PYTHONPATH=$PWD DOCKER_CONTEXT=colima-forge-swebench python -m dharma_swarm.forge_v1.canonical run \
  --instances django__django-12209 --budget 60000 --label smoke
```

Autoloop matrix:

```bash
PYTHONPATH=$PWD DOCKER_CONTEXT=colima-forge-swebench python -m dharma_swarm.forge_v1.autoloop matrix \
  --instances django__django-12209,sympy__sympy-22914 \
  --models k3,moonshotai/kimi-k3,glm-5.2,gemini-2.5-flash \
  --label smoke
```

Verifier-role first slice:

```bash
PYTHONPATH=$PWD DOCKER_CONTEXT=colima-forge-swebench python -m dharma_swarm.forge_v1.forge_v2.runner \
  --instances django__django-12209,sympy__sympy-22914 \
  --generator glm-5.2 --verifier k3 \
  --replicates 1 --budget 60000 --label smoke
```

## Host Boot & Liveness (audit-adjudicated 2026-07-05)

One loader, one precedence. `dharma_swarm.api_keys.bootstrap_runtime_env()` is
the only loader (never-overwrite, first writer wins); `scripts/load_runtime_env.sh`
is its thin shell projection. Anything that boots a daemon must go through one
of those two — never an inline `set -a; source ...` block in a launchd plist or
wrapper script. Inline sourcing is how the same host ended up with daemons
holding three different key environments at once.

- Vault envelope rule: `~/.dharma/agent_keys.env` must never export
  `ANTHROPIC_BASE_URL`, `ANTHROPIC_MODEL`, `ANTHROPIC_DEFAULT_*_MODEL`, or
  `CLAUDE_CODE_SUBAGENT_MODEL`. Gateway lanes get their own namespaced vars
  (`KIMI_*`, `AGNI_GLM_*`) plus an explicit opt-in wrapper (`claude-kimi`).
  A global Anthropic-envelope override silently rewires every Anthropic-SDK
  client on the host — including Claude Code's safety classifier.
- Daemon restart rule: a vault edit changes nothing for already-running
  daemons; their env snapshot is frozen at spawn. After `dkeys add`/`dkeys rm`,
  kickstart the launchd jobs (or accept documented staleness).
- Liveness is only real when probed through the same client the runtime uses
  (`dharma_swarm` provider classes / `provider_smoke`). Raw curl probes get
  bot-blocked (Groq 403s a bare urllib call that `GroqProvider` completes
  in <1s) and light pings miss completion-path failures (NIM pinged "live"
  while real completions timed out).
- A provider chain must never lead with a lane in a known-exhausted state.
  `key_oracle` reads `dkeys test` status; consult it (or recent 429 receipts)
  before seeding the chain head. Ollama Cloud's weekly cap manifests as
  `429 "weekly usage limit"` — quota language, not credit language, so
  credit-error regexes must match rate/quota wordings too.

## Deprecated

- `MODEL_ROUTING_MAP.md` is archived.
- `docs/architecture/MODEL_ROUTING_CANON.md` is architectural background.
- OpenRouter-first routing is deprecated unless no first-party route is live.
- Project `.env` key storage is deprecated.
- Any hidden model literal outside routing/model-pool files is suspect.
- Inline `set -a; source agent_keys.env` blocks in launchd plists / wrapper
  scripts are deprecated boot paths — route through `load_runtime_env.sh`.
