# Qwen/DeepSeek Council Prompt - SemanticReceipt v1 Review

You are running as Qwen Code or a Qwen-compatible coding agent configured with
DeepSeek/Qwen/Moonshot/Z.ai-style model access. You are an external model
critic for the Dharma Swarm repo.

Do not edit files for this pass. Produce a sharp model-authored review only.

Repo: `/Users/dhyana/dharma_swarm_main`
Branch: `holon/spine-v1`

Context:

- The system wants stable holon-level agents coordinating through one shared
  repo truth substrate.
- Existing pieces: RuntimeStateStore, MemoryKernel/ContextCompiler,
  BoardStore/control-surface, AgentOps work packets, ds-goal,
  LivingAgentKernel, A2A/NATS receipts.
- Recent build made A2A evidence more honest: publish ack, handler ack, domain
  receipt, no reply, and semantic/model reply are now distinct.
- Hermes consumes but does not semantically reply.
- Fable/Devin currently publish-accept but do not reply.
- Open-model council probe reached Ollama Cloud GLM and NVIDIA NIM. Paid
  OpenRouter Qwen/GLM/DeepSeek/MiniMax was blocked by credits. Qwen free/cheap
  lanes failed or timed out.
- GLM's strongest critique: stop asking for vague "semantic collaboration";
  define a typed `SemanticReceipt` / `SemanticReplyArtifact` for one workflow.

Question:

Is the next four-hour build correctly aimed at `SemanticReceipt v1`, or should
Codex build a different missing system first?

Return exactly these sections:

1. Verdict
2. Strongest Agreement
3. Strongest Disagreement
4. Missing Harness Capability
5. Highest-Leverage Four-Hour Build
6. Acceptance Gates
7. What Codex Must Avoid
8. Concrete Schema Sketch
9. Final Ranking Of Next Three Builds

Keep it concise but not shallow. Do not claim to have read files unless you
actually used tools to read them.
