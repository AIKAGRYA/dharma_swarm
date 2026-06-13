# Qwen Code / DeepSeek v4 Pro Review - SemanticReceipt v1

created_at: 2026-06-11T10:40:00Z
agent_uid: qwen_code_deepseek_v4_pro
provider_surface: qwen_code_cli
model: deepseek-v4-pro
prompt: reports/agentops/workhorse_prompts/qwen-deepseek-semantic-receipt-council-20260611T104000Z.md
status: ok
semantic_reply_claim: true
peer_model_processed_claim: true
tool_policy: read_file_only

## Review

### 1. Verdict

SemanticReceipt v1 is correctly aimed, but the four-hour build should be schema
plus runner together, not schema alone. The existing domain reply artifact
schema already has `verdict`, `summary`, and boolean
`semantic_reply_claim`/`peer_model_processed_claim` flags. Those are a halfway
house. Defining a new schema without a runner that populates it adds another
well-typed empty shape to a system already full of them.

The bottleneck is not the contract definition. It is that no runtime exists
that can call an external model, validate structured output against the
contract, and publish a populated SemanticReceipt.

### 2. Strongest Agreement

GLM's core insight is right: "semantic reply" must become a typed,
machine-readable artifact, not a human-interpreted string.

The current domain reply artifact path produces free-text `verdict` and
`summary`. Downstream code cannot reliably ask whether the peer understood the
request, what context is missing, or what gates the peer requires. Structured
fields such as `intent_ack`, `capability_match`, `missing_context`, and
structured `recommendations` make the artifact queryable and gatable.

Also agree that the council step is circular. Using unproven peers to design
the mechanism for proving peers is self-referential. The fact that GLM produced
a useful critique through Ollama already proves the pattern works; the council
did not need to be a separate phase, it needed to be the first artifact
produced through the new contract.

### 3. Strongest Disagreement

The council synthesis treats building the schema as the next move. That is not
sufficient. A schema alone is roughly 30 minutes of work. The system already
knows the fields it wants. The gap is not "what shape should the artifact
have?" It is "how does a non-Codex model populate that shape through a governed
runtime?"

Secondary disagreement: the honest expectation from Qwen/DeepSeek/Kimi/
Moonshot/Z.ai style coding agents is a model-agnostic runner that lets any
provider lane participate through the same contract. The system currently has
per-provider ad hoc scripts. A fallback-capable model-router abstraction would
compound across every future build.

### 4. Missing Harness Capability

A model-provider-agnostic critic runner.

It should:

- accept an AgentOps work packet or A2A inbox delivery with an
  `expected_output_schema` reference;
- call a configured model provider with fallback priority;
- validate the model response against the SemanticReceipt schema;
- reject unstructured prose and require populated structured fields;
- write the validated artifact through the existing domain reply path;
- set `semantic_reply_claim=true` and `peer_model_processed_claim=true` only
  when actual model output passed validation;
- project artifact fields onto the control-surface board.

Without this runner, the schema is a document, every model lane requires
bespoke scripting, and `semantic_reply_claim=true` remains a trust-me boolean.

### 5. Highest-Leverage Four-Hour Build

SemanticReceipt v1 schema plus one Ollama-backed GLM critic runner, wired
through the existing domain reply path and projected onto the board.

Suggested split:

- Hour 1: define SemanticReceipt as typed code with JSON Schema export and
  validation.
- Hours 2-3: build `scripts/runtime/model_critic_runner.py`.
- Hour 4: project structured SemanticReceipt fields onto the existing
  control-surface board and run it against the council prompt.

This compounds because it closes:

external model -> structured validated artifact -> board projection.

It also makes adding Qwen/DeepSeek lanes configuration, not new architecture.

### 6. Acceptance Gates

- Schema is code, not docs.
- At least one non-Codex model artifact passes validation.
- Structured fields are board-visible.
- Failure is typed, not silent.
- No new stores, buses, or authorities.
- Existing tests remain green.
- Add tests for valid schema, invalid schema, runner success, and typed
  provider failure.

### 7. What Codex Must Avoid

- Building the schema without the runner.
- Using Codex/Claude output to claim external peer collaboration.
- Creating a generic "inference engine" or "semantic understanding layer."
- Adding retry/fanout/backpressure/cancellation before one lane works
  end-to-end.
- Claiming the schema solves the Hermes/Fable/Devin wake-loop gap.
- Making `semantic_reply_claim=true` a default or manual flag.

### 8. Concrete Schema Sketch

Core fields:

- `schema_version = "dharma.semantic_receipt.v1"`
- `agent_uid`
- `model_identity`
- `authored_by_model`
- `review_target`
- `intent_ack`
- `capability_match`
- `understood_request`
- `missing_context`
- `verdict`
- `summary`
- `recommendations`
- `acceptance_gates`
- `explicit_disagreement`
- `evidence_refs`
- `confidence`
- `not_claimed_agents`
- `correlation_id`
- `reply_to`
- `created_at`
- `model_call_latency_ms`

Key validation rules:

- schema version must match;
- `authored_by_model` must be true for semantic receipts;
- `model_identity` must contain provider and model;
- `capability_match` and `confidence` must be floats between 0 and 1;
- `explicit_disagreement` is required when verdict is not pass;
- `not_claimed_agents` must be a list.

### 9. Final Ranking Of Next Three Builds

1. SemanticReceipt v1 schema plus Ollama GLM critic runner.

   This closes the loop from external model to structured validated artifact to
   board projection. The validation function becomes the universal acceptance
   gate.

2. Model-provider router with fallback priority.

   The council probe proved provider fragility: OpenRouter paid blocked,
   Groq denied, Cerebras unavailable, SiliconFlow auth failed, OpenRouter free
   timed out, and Ollama worked reliably. A router with typed failure recording
   makes the critic runner resilient.

3. Hermes/Fable wake-loop with SemanticReceipt consumption.

   Hermes already has an inbox bridge with handler ack. It needs a wake loop
   that pulls from inbox, calls a model, populates a SemanticReceipt, and
   publishes through the domain reply path.

## Bottom Line

The council synthesis is directionally correct but stops one step short.
Define the schema, yes, but the four-hour build must include the runner that
makes the schema binding. A contract with no runtime to enforce it is just
another well-typed empty shape.

