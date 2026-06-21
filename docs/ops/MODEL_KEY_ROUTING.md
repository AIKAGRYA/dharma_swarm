# Model & Key Routing — THE ONE WAY

> **Read this, ignore everything else.** There is exactly **one** place keys live, **one** tool to manage them, and **one** door to pick a model/provider. If you are an agent (any model, any session) touching keys or model selection, follow this. **Do not invent a second way.** Every "why don't we have keys / why is it on a dead provider" spiral for months came from having many ways. Now there is one. (Canonical 2026-06-06.)

## Keys — one home, one tool
- **HOME:** `~/.dharma/agent_keys.env` — the *only* place provider keys live. Sourced by every shell (`~/.zshrc`). Every line is `export`ed.
- **TOOL:** `dkeys` — the *only* way to manage keys.
  - `dkeys` → status table · `dkeys test` → live-ping all · `dkeys add VAR=value` → writes here + tests · `dkeys find <term>` → scour.
- **In code:** read a provider key *only* through `dharma_swarm/api_keys.py` constants. Never `os.environ["..._API_KEY"]` directly. Never read a project `.env`.

## Model / provider selection — one door
- **THE DOOR:** `dharma_swarm.runtime_provider.resolve_runtime_provider_config(provider, …)` → `create_runtime_provider(config)`. Every provider/model resolution goes through here.
- **ORDER:** `dharma_swarm.model_hierarchy` — power-ranked lanes (most-powerful-first; `CLAUDE_CODE`/Max ranked above the metered Anthropic API).
- **Anthropic/Claude → Max plan:** an Anthropic request auto-routes to the `claude_code` CLI (Claude Max subscription, flat-fee). Escape hatch: `DHARMA_FORCE_ANTHROPIC_API=1` forces the raw API.
- **Live-fallback:** if a provider has no live key, resolution/wake falls back to the best available provider — **never block on a dead brain.**

## Egress — the third leg (a key alone is not enough)

Keys + the resolver get you a *configured* model. To actually *reach* it the
runtime environment's **network egress allowlist** must include the provider's
API host. If it doesn't, the call dies with a 403 from the environment's egress
proxy (NOT the code, NOT the key):

```
PermissionDeniedError: Host not in allowlist: api.z.ai.
Add this host to your network egress settings to allow access.
```

**Principle: more hosts allowed = more models reachable = more freedom.** Allow
the provider hosts generously; the gate that matters is the telos gate, not the
network. The hosts are **derived from the provider registry** (never hand-kept),
so they stay correct as providers are added:

```bash
python3 scripts/ops/provider_egress_hosts.py          # one host per line
python3 scripts/ops/provider_egress_hosts.py --json    # {"hosts": [...], "special": {...}}
```

Procedure: add the listed hosts to **this environment's** egress settings (its
network policy — chosen when the environment is created; see
https://code.claude.com/docs/en/claude-code-on-the-web). It cannot be changed
from inside a session. Special cases the script also notes: `claude_code`
(Anthropic Max) runs as a CLI subprocess with no HTTP egress host (force the
metered API with `DHARMA_FORCE_ANTHROPIC_API=1` → `api.anthropic.com`); `ollama`
is a local daemon; Moonshot/DeepSeek/Perplexity ride OpenRouter today
(`openrouter.ai`). When a model "won't run" and the key is present, check egress
**before** assuming a code or key fault.

## The four rules that keep it one-way forever
1. **Never hardcode a model string** (e.g. `"claude-sonnet-4-…"`) in a module. Ask the resolver / `model_hierarchy`.
2. **Never read a provider key** except through `api_keys.py`.
3. **Never add a key** anywhere but via `dkeys add` (→ `agent_keys.env`).
4. **New provider** = add its adapter + a `DEFAULT_MODELS` entry; the resolver + router pick it up automatically. No parallel routing layer.

## Deprecated — DO NOT USE (the old scattered routes; redirected, being burned down)
- ❌ Hardcoded `claude-sonnet-4-20250514` literals in cognition modules (`planner`, `subconscious`, `witness`, `hypnagogic`, `thinkodynamic_director`, `guardian_crew`) → migrate to the resolver.
- ❌ `AgentConfig` / `AgentSpec` provider/model defaults pinned to `ANTHROPIC` → resolve at runtime.
- ❌ Reading keys from project `.env` / `.secrets` / `.hermes` / cutover/migration files → all consolidated into `agent_keys.env`.
- ❌ The metered Anthropic API as a default → use the Max plan (`claude_code`).
- ❌ OpenRouter as a primary → deprioritized (it charges a markup); direct providers first.

## Status (2026-06-06)
- ✅ Keys consolidated into the one home — **6 live clusters** (Ollama Cloud → GLM-5/DeepSeek/Kimi/MiniMax, + DeepSeek, NVIDIA NIM, OpenAI, GLM/z.ai, gemini). `dkeys test` for the live board.
- ✅ Anthropic → Max routing wired at the resolver. Brain-plug (no dead-provider wakes) + ollama default fixed.
- ⬜ **REMAINING (the routing brain):** the *power-first, never-block cascade* — order by model strength, instant fallthrough to the next live brain on any failure. Plus burning down the hardcoded-literal stragglers (rule 1) so the deprecated routes are gone, not just forbidden.
