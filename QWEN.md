# Qwen Code Context - Dharma Swarm

You are working in `/Users/dhyana/dharma_swarm_main`, not the home directory.

## Current Role

Act as an external high-power model critic and repo-aware reviewer for the
Codex Composer / A2A / holon-agent build. Do not claim to be Hermes, Fable,
Devin, Claude, or Codex. If you produce a review, identify yourself as the
actual model/lane you are running under.

## Current State

- Branch: `holon/spine-v1`
- The repo is dirty from an active Codex Composer longrun.
- Codex has already proven:
  - A2A transport can distinguish publish ack, handler ack, domain receipt,
    no reply, and semantic/model reply claims.
  - Hermes bridge can consume packets but has not produced semantic replies.
  - Fable/Devin A2A lanes currently publish-accept but do not reply.
  - A bounded `ds-goal run` now writes RuntimeStateStore owner rows.
  - AgentOps work packets can project output artifacts as board receipt refs.
- The strongest open-model critique so far came from Ollama Cloud GLM:
  build a typed `SemanticReceipt` / `SemanticReplyArtifact` contract before
  asking agents for vague "semantic collaboration".

## Key Files To Read First

- `/Users/dhyana/.dharma/agents/codex_composer/HOLON_CONTEXT.md`
- `/Users/dhyana/.dharma/a2a_bus/collab/convergence/MEGA_PROMPT_CODEX_COMPOSER_OPEN_MODEL_COUNCIL_V6_20260611T102326Z.md`
- `reports/agentops/open_model_council/council_synthesis_20260611T103030Z.md`
- `reports/agentops/workhorse_prompts/open-model-council-a2a-missing-systems-20260611T102326Z.md`
- `docs/governance/AGENTOPS.md`
- `docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md`
- `docs/ops/TMUX_AGENT_SUBSTRATE.md`

## Safety

Unless explicitly asked to implement, prefer review-only output. Do not commit,
push, merge, spend credits beyond the current call, or create new central
stores. If editing, use the existing repo surfaces and keep changes scoped.

## Desired Critique

Answer:

1. Is `SemanticReceipt v1` truly the next highest-leverage build, or is another
   seam more urgent?
2. What would Qwen/DeepSeek/Kimi/Moonshot/Z.ai style coding agents expect from
   an agentic harness here that this repo still lacks?
3. What is the narrowest four-hour build that compounds across all agents?
4. What acceptance gates would prevent fake collaboration?
5. What should Codex explicitly avoid?

