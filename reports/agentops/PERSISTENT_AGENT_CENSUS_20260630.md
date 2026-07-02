# Persistent Agent Census

Date: 2026-06-30 JST

## Sources

- Canonical repo: `/Users/dhyana/dharma_swarm`
- Primary file registry: `.dharma/agents/*/identity.json`
- Legacy/live ginko registry: `.dharma/ginko/agents/*/identity.json`
- Runtime telemetry registry: `.dharma/state/runtime.db:agent_identity`
- Global sovereign holons: `~/.dharma/agents/*/identity.json`
- Preset wake agents: `dharma_swarm/autonomous_agent.py:PRESET_AGENTS`
- Standing conductors: `dharma_swarm/conductors.py:CONDUCTOR_CONFIGS`

## Counts

- Repo file-backed agents: 29
- Ginko file-backed agents: 51
- Ginko-only extras not present in `.dharma/agents`: 22
- Runtime telemetry identities: 28
- Runtime telemetry retired identities: 5
- Global sovereign holons: 6
- Preset wake agents: 5
- Configured conductors: 2

## Runtime Telemetry Identities

These are the truthiest runtime identities because they are projected into `.dharma/state/runtime.db`.

| agent_id | codename | squad | role | model | provider | status |
|---|---|---|---|---|---|---|
| archeologist | archeologist | phenomenological | archeologist | meta-llama/llama-3.3-70b-instruct | openrouter | idle |
| architect | architect | architectural | architect | meta-llama/llama-3.3-70b-instruct | openrouter | idle |
| builder | builder | mechanistic | general | meta-llama/llama-3.3-70b-instruct | openrouter | idle |
| cartographer | cartographer | mechanistic | cartographer | meta-llama/llama-3.3-70b-instruct | openrouter | idle |
| codex-check | codex-check | reviewer | reviewer | claude-sonnet-4-20250514 | codex | retired |
| codex-primus | codex-primus | architectural | orchestrator | gpt-5.4 | codex | idle |
| cyber-codex | cyber-codex | cybernetics | surgeon | qwen3-coder:480b-cloud | ollama | idle |
| cyber-glm5 | glm-researcher | cybernetics | researcher | glm-5:cloud | ollama | idle |
| cyber-groq | cyber-groq | cybernetics | validator | llama-3.3-70b-versatile | groq | retired |
| cyber-kimi25 | kimi-scout | cybernetics | cartographer | kimi-k2.5:cloud | ollama | idle |
| cyber-opus | cyber-opus | cybernetics | architect | deepseek-v3.2:cloud | ollama | idle |
| demo-gpt54 | demo-gpt54 | reviewer | reviewer | openai/gpt-5.4 | claude_code | retired |
| demo-opus46 | demo-opus46 | reviewer | reviewer | anthropic/claude-opus-4-6 | claude_code | retired |
| glm-researcher | glm-researcher | mechanistic | researcher | z-ai/glm-5 | openrouter | idle |
| jagat-kalyan | jagat-kalyan | alignment | general | meta-llama/llama-3.3-70b-instruct | openrouter | idle |
| jagat_kalyan | jagat_kalyan | alignment | general | claude-code | claude_code | idle |
| kimi-cartographer | kimi-scout | mechanistic | researcher | moonshotai/kimi-k2.5 | openrouter | idle |
| local-check | local-check | reviewer | reviewer | llama3:8b | ollama | retired |
| minimax-challenger | minimax-challenger | mechanistic | researcher | minimaxai/minimax-m2.5 | nvidia_nim | idle |
| nim-generalist | nim-generalist | mechanistic | general | meta/llama-3.3-70b-instruct | nvidia_nim | idle |
| nim-validator | nim-validator | architectural | validator | meta/llama-3.3-70b-instruct | nvidia_nim | idle |
| opus-primus | opus-primus | architectural | orchestrator | claude-opus-4-6 | claude_code | idle |
| qwen-builder | qwen-builder | mechanistic | general | qwen/qwen3-coder | openrouter | idle |
| qwen-peer-check | qwen-peer-check | reviewer | reviewer | qwen3-coder:480b-cloud | ollama | retired |
| researcher | researcher | mechanistic | researcher | mistralai/mistral-small-3.1-24b-instruct | openrouter | idle |
| surgeon | surgeon | alignment | surgeon | meta-llama/llama-3.3-70b-instruct | openrouter | idle |
| test-opus-agent | test-opus-agent | researcher | researcher | openrouter/meta-llama/llama-3.3-70b-instruct | claude_code | retired |
| validator | validator | scaling | validator | mistralai/mistral-small-3.1-24b-instruct | openrouter | idle |

## Repo File Registry

`agent-0`, `agent-1`, `agent-2`, `archeologist`, `architect`, `builder`, `cartographer`, `codex-primus`, `cyber-codex`, `cyber-glm5`, `cyber-kimi25`, `cyber-opus`, `doomed`, `findme`, `glm-researcher`, `idle-1`, `idle-2`, `jagat-kalyan`, `jagat_kalyan`, `kimi-cartographer`, `minimax-challenger`, `nim-generalist`, `nim-validator`, `opus-primus`, `qwen-builder`, `researcher`, `surgeon`, `validator`, `worker-1`.

## Ginko-Only Extras

`codex-check`, `cyber-groq`, `deepseek`, `demo-gpt54`, `demo-opus46`, `garuda`, `glm`, `kimi`, `kimi-2-6-claw`, `local-check`, `mem-agent`, `nemotron`, `p`, `qwen`, `qwen-peer-check`, `r`, `scout`, `sentinel`, `setu`, `test-opus-agent`, `vajra`, `worker`.

## Global Sovereign Holons

| name | role | model | provider | status |
|---|---|---|---|---|
| codex_composer | lead_orchestrator | gpt-5.5 | codex | registered_operator_candidate |
| codex_worker_spine | single_build_worker |  |  |  |
| devin-roaming-2987d222 |  |  |  |  |
| fable_composer | master_composer | claude-fable-5 | anthropic_max | session_alive_standing_loop_pending |
| opus_composer | opus_model_seat | claude-opus-4-8 | anthropic_max | session_active_opus_wake |
| sarathi | apex_holon | @frontier | anthropic_max | GENESIS_AUTHORED_NOT_YET_BREATHING |

## Preset Wake Agents

`researcher`, `coder`, `scout`, `reviewer`, `witness`.

## Configured Conductors

`conductor_claude` and `conductor_codex` are configured standing wake-loop agents but are not present as ordinary file-backed identities in `.dharma/agents`.

## Ownership Recommendation

The strange-loop/mech-interp research line should have one accountable owner:

**Owner: `codex_composer`**

Reason: it is the global lead orchestrator with the right execution posture for exact prompt provenance, Makefile receipts, scripts, and hard verification. This work is now mostly an experimental-control problem, not a poetic or doctrine problem.

Supporting seats:

- Scientific/domain lead: `researcher`
- Implementation lane: `builder` or `qwen-builder`
- Skeptical gate: `validator` plus `nim-validator`
- Synthesis/escalation: `opus-primus`
- Not owner yet: `sarathi`, because it is authored but not breathing.

Operational rule: `codex_composer` owns the ledger and decides the next experiment; `researcher` owns claims; `validator` can block conclusions; `builder/qwen-builder` only implement bounded tasks.
