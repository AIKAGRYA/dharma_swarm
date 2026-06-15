# Build Start Announcement - Codex SemanticReceipt Runner v7

created_at: 2026-06-11T14:04:18Z
from: codex_composer
kind: build_start_announcement
worktree: /Users/dhyana/dharma_swarm_main
branch: holon/spine-v1
head: f0d03ffaf4

## Declaration

Codex Composer is preparing the next build: **SemanticReceipt v1 plus the
model critic runner that fills and validates it**.

This follows the strong model council consensus from:

- Ollama Cloud GLM
- Ollama Cloud DeepSeek v3.2
- Ollama Cloud Kimi k2.5
- Ollama Cloud Qwen3 Coder 480B
- direct DeepSeek v4 Pro
- Qwen Code running DeepSeek v4 Pro

## Current Operator Intent

The operator asked Codex to:

- run `make onboard`;
- declare the build over NATS;
- draft a self-prompt to instantiate a build that forces collaboration with
  the strongest available model lanes.

## Planned Build Contract

The next build must not be schema-only. It must include:

1. `SemanticReceipt v1` executable schema and validation.
2. `model_critic_runner` that calls non-Codex model lanes.
3. Typed success and failure artifacts.
4. Existing BoardStore/control-surface/AgentOps/A2A projection.
5. Tests proving validation, typed failure, and projection.

## Model Lanes To Use

Required fresh attempts:

- Qwen Code CLI with `deepseek-v4-pro`
- direct DeepSeek `deepseek-v4-pro`
- Ollama Cloud `glm-5:cloud`
- Ollama Cloud `deepseek-v3.2:cloud`
- Ollama Cloud `kimi-k2.5:cloud`
- Ollama Cloud `qwen3-coder:480b-cloud`
- Ollama Cloud `minimax-m2.7:cloud`
- Moonshot `kimi-k2.6` or `moonshot-v1-auto` if quota is available; otherwise
  record the quota blocker

## Authority

This announcement is a coordination mark, not approval to push, merge, spend
unbounded credits, create new state stores, or fake peer replies.

