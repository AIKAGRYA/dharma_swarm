# Open-Model Council Synthesis - 2026-06-11T10:30:30Z

## What Was Tried

Codex attempted an open/frontier model council against:

- OpenRouter paid: Qwen `qwen/qwen3.7-plus`, GLM `z-ai/glm-5.1`, DeepSeek
  `deepseek/deepseek-v4-pro`, MiniMax `minimax/minimax-m3`
- Ollama Cloud: GLM `glm-5:cloud`
- OpenRouter free: Qwen `qwen/qwen3-coder:free`
- Groq: Qwen `qwen/qwen3-32b`
- Cerebras: Qwen `qwen-3-235b-a22b-instruct-2507`
- SiliconFlow: Qwen Coder `Qwen/Qwen3-Coder-480B-A35B-Instruct`
- NVIDIA NIM: `meta/llama-3.3-70b-instruct`
- Google AI: `gemini-2.5-flash`

Prompt:

`reports/agentops/workhorse_prompts/open-model-council-a2a-missing-systems-20260611T102326Z.md`

## Response Quality

High-quality response:

- `glm_ollama_cloud` responded with a concrete architectural critique.

Useful but less specific response:

- `nvidia_nim_llama` responded with a reasonable but more generic critique.

Low-quality/truncated response:

- `gemini_google_ai` responded, but the response was only 200 characters and is
  not enough to treat as serious council input.

Failed or unavailable:

- OpenRouter paid Qwen/GLM/DeepSeek/MiniMax all failed with `402` insufficient
  credits.
- OpenRouter-free Qwen timed out after 120s.
- Groq Qwen failed with `403` access denied/network settings.
- Cerebras Qwen failed with `404` model not available to this account.
- SiliconFlow Qwen failed with `401` invalid API key.

## Strongest Critique

GLM's strongest point:

The system should not keep asking for "semantic collaboration" as a vague
human-readable outcome. It needs a typed semantic response contract. The next
build should define one narrow `SemanticReceipt` schema for one workflow, then
route that through the existing A2A/AgentOps/RuntimeState/BoardStore surfaces.

This critique is better than the current v6 prompt's first instinct. The model
council is useful as a probe, but if peer replies are not reliable, a larger
council can become circular: using unproven peers to design the mechanism for
proving peers.

## Model Consensus

- The goal is broadly aimed at the right seam: semantic peer/workhorse
  collaboration, not more raw transport proof.
- Existing surfaces should be reused: A2A, AgentOps, RuntimeStateStore,
  BoardStore/control surface, and MemoryKernel/ContextCompiler.
- Codex should avoid creating a new bus, new memory authority, or standalone
  kanban.
- The next build needs clear acceptance gates and machine-readable output, not
  another prose-only review loop.

## Disagreement

- GLM argues the next build should be a typed `SemanticReceipt` contract.
- NVIDIA NIM frames the missing piece as a broader "Semantic Reply Generator" or
  inference engine.

Codex interpretation:

The safer and higher-leverage synthesis is to build the narrow contract first,
not the broad inference engine. A broad inference engine risks becoming another
god component. A narrow `SemanticReceipt` contract creates a measurable seam
that any model or peer runner can satisfy.

## A2A Peer Request Pass

The same council prompt was sent through A2A:

- Hermes: packet `bb9b7e2470f8`, `HANDLER_ACKED`, consumed, no reply.
- Fable Cursor: packet `eb84b96dd201`, `PUBLISH_ACCEPTED`, no consume/reply.
- Fable Composer: packet `a73376e259af`, `PUBLISH_ACCEPTED`, no consume/reply.
- Devin: packet `cf8618dc738c`, `PUBLISH_ACCEPTED`, no consume/reply.

Reply capture receipts all record `NO_REPLY` and
`semantic_reply_claim=false`.

## Updated Highest-Leverage Build

Build a narrow semantic response contract:

1. Add a typed `SemanticReceipt` or `SemanticReplyArtifact` schema for one
   workflow, probably "goal critique / missing-gates review".
2. Include fields such as:
   - `intent_ack`
   - `capability_match`
   - `understood_request`
   - `missing_context`
   - `recommendations`
   - `acceptance_gates`
   - `explicit_disagreement`
   - `evidence_refs`
   - `confidence`
   - `not_claimed_agents`
3. Make the existing model/provider runner write that artifact after a model
   call.
4. Project it into AgentOps and the control-surface board with proof tier and
   model/provider identity.
5. Preserve A2A transport status separately from semantic artifact status.

## What This Changes In v6

The v6 longrun should still start with a model council, but only as a fast
probe. The main build should now be:

"Typed SemanticReceipt v1 for open-model/workhorse critique, routed through
existing AgentOps/A2A/RuntimeState/BoardStore surfaces."

That is more concrete than "get semantic peer replies" and gives Hermes, Fable,
Devin, Qwen, GLM, DeepSeek, MiniMax, Codex, or any future lane the same contract
to satisfy.

