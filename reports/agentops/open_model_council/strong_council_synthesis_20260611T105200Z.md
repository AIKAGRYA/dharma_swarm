# Strong Model Council Synthesis - 2026-06-11T10:52:00Z

## What Changed

The stronger model council overturned the weaker wording of v6.

The next build should not be "define SemanticReceipt v1" by itself. The
consensus across GLM, DeepSeek, Kimi, Qwen Coder, and direct DeepSeek v4 Pro is:

**Build SemanticReceipt v1 and the model critic runner together.**

A schema without a runner is another empty contract. The runner is what makes
the schema binding: it calls a non-Codex model, validates structured output,
writes a typed semantic artifact, records failures, and projects the result
through the existing board/runtime surfaces.

## Models Tried

Successful useful responses:

- Ollama Cloud `glm-5:cloud`
- Ollama Cloud `deepseek-v3.2:cloud`
- Ollama Cloud `kimi-k2.5:cloud`
- Ollama Cloud `qwen3-coder:480b-cloud`
- direct DeepSeek `deepseek-v4-pro`
- Qwen Code CLI configured with `deepseek-v4-pro`

Low-quality response:

- Ollama Cloud `minimax-m2.7:cloud` returned only "I'll inspect the repo first
  before rendering judgment" because this direct provider path did not expose
  repo tools.

Failed:

- Moonshot `kimi-k2.6` and `moonshot-v1-auto`: provider quota/balance blocked.
- direct DeepSeek `deepseek-v4-flash`: empty/model-error response.

Earlier failed or unavailable:

- OpenRouter paid Qwen/GLM/DeepSeek/MiniMax: insufficient credits.
- OpenRouter-free Qwen: timeout.
- Groq Qwen: access denied/network settings.
- Cerebras Qwen: model unavailable to this account.
- SiliconFlow Qwen: invalid API key.

## Consensus

- `SemanticReceipt v1` is the right seam.
- It must include provenance from day one: writer identity, provider/model,
  confidence, capability match, evidence refs, and explicit non-claims.
- The system needs a model-provider-agnostic critic runner, not only a schema.
- The runner must treat provider fragility as normal: auth failure, quota
  failure, timeout, empty response, schema failure, and capability mismatch all
  need typed failure artifacts.
- The first workflow should be narrow: architecture critique / missing-gates
  review, not a generic inference engine.
- Do not expose the receipt as an agent-facing optimization target too early.
  First make it an internal spine audit artifact visible to BoardStore/control
  surface.

## Disagreements

- Some models suggested a NATS subscription and a semantic receipt subject.
  Codex should be careful here: the repo already has A2A/NATS lanes, domain
  reply artifacts, AgentOps work packets, RuntimeStateStore, and BoardStore.
  New subjects are acceptable only if they are declared as part of the existing
  substrate, not a new bus.
- Direct DeepSeek emphasized the runner as a cost-aware, degraded-mode boundary:
  not just a validator, but a semantic feedback amplifier designed for model
  fragility.
- Kimi argued v1 should be internal spine audit first, not shared agent-facing
  contract, to avoid agents gaming the schema before the judge is proven.

## Updated Highest-Leverage Four-Hour Build

Build:

1. `dharma_swarm/operator_core/semantic_receipt.py`
   - typed schema / Pydantic model or dataclass;
   - JSON Schema export;
   - validation function;
   - typed failure taxonomy.

2. `scripts/runtime/model_critic_runner.py`
   - reads a prompt/work packet/A2A delivery;
   - calls a configured non-Codex model, starting with Ollama Cloud GLM;
   - asks for structured JSON matching the schema;
   - retries once with validation errors if the model returns invalid shape;
   - writes a success or typed failure artifact under `reports/agentops/semantic_receipts/`;
   - sets semantic claims only after validation passes.

3. Board/control-surface projection
   - existing AgentOps/A2A/BoardStore surfaces should show:
     provider/model, verdict, confidence, capability match, missing context,
     acceptance gates, explicit disagreement, and failure type.

4. Tests
   - valid receipt passes;
   - invalid receipt fails with specific errors;
   - runner writes typed failure for unavailable provider;
   - runner writes validated artifact for a fixture/model stub;
   - board adapter projects fields.

## Final Ranking

1. SemanticReceipt v1 plus model critic runner.
2. Provider fallback/failure router for model critic lanes.
3. Hermes/Fable wake loop that consumes requests and emits SemanticReceipts.

