# Open-Model Council Probe Summary - 20260611T102512Z

prompt: `/Users/dhyana/dharma_swarm_main/reports/agentops/workhorse_prompts/open-model-council-a2a-missing-systems-20260611T102326Z.md`
prompt_sha256: `a47987ffedbd20934aacfd05d50421ae1d3f48ba860f860c5d73b06b74eca415`
responded: 1/5

## qwen_openrouter - error

provider: `openrouter`
model: `qwen/qwen3.7-plus`
latency_ms: `834.3`
artifact: `/Users/dhyana/dharma_swarm_main/reports/agentops/open_model_council/20260611T102512Z-qwen_openrouter.json`

```text
APIStatusError: Error code: 402 - {'error': {'message': 'Insufficient credits. Add more using https://openrouter.ai/settings/credits', 'code': 402}}
```

## glm_openrouter - error

provider: `openrouter`
model: `z-ai/glm-5.1`
latency_ms: `533.9`
artifact: `/Users/dhyana/dharma_swarm_main/reports/agentops/open_model_council/20260611T102512Z-glm_openrouter.json`

```text
APIStatusError: Error code: 402 - {'error': {'message': 'Insufficient credits. Add more using https://openrouter.ai/settings/credits', 'code': 402}}
```

## deepseek_openrouter - error

provider: `openrouter`
model: `deepseek/deepseek-v4-pro`
latency_ms: `1221.2`
artifact: `/Users/dhyana/dharma_swarm_main/reports/agentops/open_model_council/20260611T102512Z-deepseek_openrouter.json`

```text
APIStatusError: Error code: 402 - {'error': {'message': 'Insufficient credits. Add more using https://openrouter.ai/settings/credits', 'code': 402}}
```

## minimax_openrouter - error

provider: `openrouter`
model: `minimax/minimax-m3`
latency_ms: `523.4`
artifact: `/Users/dhyana/dharma_swarm_main/reports/agentops/open_model_council/20260611T102512Z-minimax_openrouter.json`

```text
APIStatusError: Error code: 402 - {'error': {'message': 'Insufficient credits. Add more using https://openrouter.ai/settings/credits', 'code': 402}}
```

## glm_ollama_cloud - ok

provider: `ollama`
model: `glm-5`
latency_ms: `29936.2`
artifact: `/Users/dhyana/dharma_swarm_main/reports/agentops/open_model_council/20260611T102512Z-glm_ollama_cloud.json`

```text
## External Model Critic Review

### Verdict
**Partially on-seam.** Steps 1-3 are research theater, not building. The actual work (step 4) is underspecified—"smallest missing piece" is a goal, not a design. The constraint (step 5) is defensive but doesn't guide toward what *to* build.

### Biggest Missing Architecture Piece
**Semantic contract negotiation.** External peers cannot produce "semantic replies" because there is no shared schema for what constitutes one. You have transport-level acks (good), but no protocol for:
- Capability declaration ("I can respond to class-X requests")
- Response schema contracts ("A semantic reply to goal-decomposition has fields: subgoals, dependencies, confidence")
- Failure modes that aren't just "no reply"

Without this, "semantic reply" is a string that humans interpret, not a machine-readable artifact.

### Highest-Leverage Four-Hour Build
**Implement `SemanticReceipt` as a typed schema in existing A2A receipt flow:**
```
SemanticReceipt {
  intent_ack: string,      // What the peer understood
  capability_match: float, // Confidence they can handle this
  response_schema: JSON,   // Structured output
  missing_context: []      // What they need to proceed
}
```
Wire this into `RuntimeStateStore` as a queryable artifact. No new store. This makes "semantic collaboration visible" by forcing structure.

### What Current Systems Do Better
- **LangGraph**: Explicit state machines with termination conditions—you have receipts but no state transition rules
- **AutoGen**: Conversation patterns with expected-reply schemas—you have transport but no reply contracts
- **CrewAI**: Task delegation with `expected_output` definitions—you have work packets but no output specifications
- **OpenDevin/Devin**: Action-observation loops with structured
```
