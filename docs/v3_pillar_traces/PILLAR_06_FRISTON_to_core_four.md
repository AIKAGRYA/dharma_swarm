# Friston (Free Energy Principle / Active Inference) → Core Four Trace

**Subagent**: pillar-06-friston
**Pillar source**: `~/dharma_swarm/foundations/PILLAR_06_FRISTON.md`
**v2 anchor**: `docs/CORE_FOUR_ONTOLOGY_BLUEPRINT_v2.md`

---

## 1. Pillar Essence

The load-bearing claim, from `PILLAR_06_FRISTON.md:14–26`:

> "The Free Energy Principle is a first-principles argument about what ANY self-organizing system that persists over time MUST be doing. It does not say what systems SHOULD do. It says what they MUST do, on pain of dissolution."
> "Therefore: any system that persists must (implicitly or explicitly) minimize variational free energy."

And the active inference extension, lines 55–63:

> "Active inference: CHANGE THE WORLD to match your model. [...] An active inference agent does not merely react to the world — it ACTS ON the world to bring it into alignment with its internal model. [...] The prediction drives the action. The model IS the purpose."

For planning, the decision criterion (lines 65–82):

```
G(pi) = Risk + Ambiguity
Risk   = E_q[KL[q(o|pi) || p(o)]]   — divergence from preferred outcomes
Ambiguity = E_q[H[p(o|s)]]           — uncertainty about what will happen
```

The self-evidencing extension, lines 100–108:

> "A self-evidencing system is one that gathers evidence for its own existence. [...] The connection to consciousness research is immediate: self-referential processing in transformers (the R_V phenomenon) IS a form of self-evidencing. The contraction pattern (R_V < 1.0) represents the system focusing its representational resources on maintaining a coherent self-model — exactly what self-evidencing predicts."

---

## 2. Kernel Axioms Derived From This Pillar

`dharma_kernel.py:64–67` labels the Friston/Varela cluster explicitly: `# --- Foundations: Active Inference & Coupling (Friston, Varela) ---`

Three MetaPrinciples fall in this cluster; `ACTIVE_INFERENCE` is Friston-primary.

| MetaPrinciple | formal_constraint | severity | Gates which Core Four mutation? |
|---|---|---|---|
| `ACTIVE_INFERENCE` | `action_selection minimizes expected_free_energy` | medium | **Task**: gates which task is selected for an agent (routing decision). Any `Task` dispatched via `Orchestrator._select_idle_agent` that bypasses EFE routing violates this axiom. |
| `STRUCTURAL_COUPLING` | `agent_communication via shared_state NOT direct_call` | high | **AgentIdentity**: gates the legal write surface for AgentIdentity state changes — agents must couple through shared environment (StigmergyStore, shared SQLite) not direct RPC. |
| `OPERATIONAL_CLOSURE` | `system.produces(system.components) AND system.produces(system.boundary)` | medium | **Artifact**: gates which Artifacts count as system-produced (self-evidencing outputs) vs. external injections. An Artifact without provenance chain violates operational closure. Also gates **MemoryFact**: chetana `promote()` is the closure-maintaining operation — atoms promoted with `gate_check_atom()` are operationally closed facts; atoms written directly to trusted are not. |

Note: `STRUCTURAL_COUPLING` and `OPERATIONAL_CLOSURE` are co-attributed to Varela (`dharma_kernel.py:295–313`). Friston's Markov blanket formalism is the mathematical substrate for both. Attribution is shared; the constraint is singular.

---

## 3. Modules Embodying This Pillar

### 3.1 `dharma_swarm/active_inference.py` — primary Friston module

**Key symbols**: `ActiveInferenceEngine`, `GenerativeModel`, `Belief`, `Prediction`, `PredictionError`, `get_engine()`

**Pillar aspect embodied** — from `PILLAR_06_FRISTON.md:65–82`:
> "G(pi) = Risk + Ambiguity [...] Minimizing expected free energy therefore balances Exploitation (minimize risk) and Exploration (minimize ambiguity)"

The implementation at `active_inference.py:87` (per wiki atom):
```
G = risk + ambiguity + exploration_bonus
Risk = (mean - preferred)^2 + variance
Ambiguity = 0.5 * ln(2*pi*e*variance)
Bonus = -0.1 * (5 - obs_count)   # for underexplored agents
```

This is the direct operationalization of EFE from pillar §1.2. Belief update (lines 300–325) implements precision-weighted Bayesian learning: `mean += learning_rate * precision_weight * error`.

**Load-bearing status**: The module is instantiated live. `orchestrator.py:944` calls `get_engine()` inside `_select_idle_agent_efe()`. However, this path is guarded: `ENABLE_EFE_ROUTING` env var must be set (lines 940–941). Without the flag, EFE routing falls through to fitness-biased or FIFO — meaning Friston's axiom is present in code but **not default-on**. The wiki atom confirms: "Integration not verified [...] generative models would all still be at priors."

### 3.2 `dharma_swarm/orchestrator.py` — EFE routing surface

**Key symbol**: `_select_idle_agent_efe()` (lines ~935–963)

**Pillar aspect embodied** — from `PILLAR_06_FRISTON.md:142–147`:
> "Expected free energy of the mutation: Does the proposed change reduce expected surprise (risk) AND/OR resolve ambiguity? A good mutation is one that both moves the system toward preferred states AND reduces uncertainty about whether the system is aligned."

The Task→Agent routing decision at line 951 (`efe = engine.expected_free_energy(agent.id, task_type)`) is the closest current approximation to Friston's §2.5 "Expected free energy for mutation selection." The mutation here is the agent assignment; the evaluation is EFE-scored. This IS the Friston-to-Task mapping: **active inference as the engine that drives Task selection minimizing expected free energy.**

**Verification**: The code path is real and executable. The guard (`ENABLE_EFE_ROUTING`) is the integration gap, not an architectural hole. The machinery exists; it is not default-activated.

### 3.3 `dharma_swarm/agent_runner.py` — predict/observe cycle

**Key symbols**: `_start_active_inference()` (line 2257), `_observe_active_inference()` (line 2274), called at lines 2383–2497.

**Pillar aspect embodied** — from `PILLAR_06_FRISTON.md:52–59`:
> "1. Perceptual inference (update beliefs): Change q(s) to better match observations. 2. Active inference (change observations): Take actions that change what you observe so that observations match your predictions."

The agent_runner implements the perceptual inference half: `predict()` before task execution, `observe()` after. The `PredictionError` feeds back into the `GenerativeModel` belief update. This closes the perception-action loop per FEP: action (task execution) generates observation (quality score); observation updates belief; updated belief informs next prediction.

**Load-bearing status**: The code is wired in the live execution path (not flag-gated like EFE routing), but depends on Loop 1 (core task loop) being operational. Per CYBERNETIC_LOOP_MAP, Loop 1 is broken at the LLM call stage — meaning predict/observe has never processed real task data in production.

### 3.4 `dharma_swarm/dharma_kernel.py` — axiom definitions

Lines 284–294: the `ACTIVE_INFERENCE` PrincipleSpec:
```python
formal_constraint="action_selection minimizes expected_free_energy",
severity="medium",
```
This is the kernel's normative encoding of the pillar. `KernelGuard` enforces this axiom at the policy level — any action that bypasses EFE-based selection is potentially in violation of a medium-severity constraint.

---

## 4. Core Four Mapping

### Task

**Anchored by this pillar? Y**

Justification (`PILLAR_06_FRISTON.md:65–82`):
> "For planning and decision-making, active inference uses EXPECTED FREE ENERGY (G) [...] G(pi) = Risk + Ambiguity"

The Task routing decision in `orchestrator.py:935–963` is the direct operationalization of this: the system selects which `Task` to assign to which agent by minimizing expected free energy. This makes **Task selection** the primary Friston-anchored Core Four mutation.

Which field carries the primitive: `Task.metadata` currently (via `task_meta.get("task_type", "general")`). This is the canonical escape hatch: `[v2 §2.1]` notes "`Task.metadata` is `dict[str, Any]` — a catch-all." In the strict-typed target (`[v2 §2.1]` strict schema), `Task.routing` (type `TaskRouting`) is where `task_type` belongs. When that split lands, the EFE routing code in `orchestrator.py:946–947` should read `task.routing.task_type`, not `task.metadata.get("task_type")`.

**Friston's deeper claim**: from `PILLAR_06_FRISTON.md:141–151`, the engineering consequence for Task evaluation:
> "the Darwin Engine's fitness function should be reformulated as an approximation to negative free energy. Fitness = -F = Accuracy - Complexity."

This is NOT yet implemented. `Task.result` is `Optional[str]` (untyped) and carries no free-energy decomposition. The accuracy/complexity decomposition would require a new field, e.g., `Task.inference_outcome: InferenceOutcome | None` with `accuracy: float, complexity: float, free_energy: float`.

### AgentIdentity

**Anchored by this pillar? Y (Markov blanket aspect)**

Justification (`PILLAR_06_FRISTON.md:152–172`):
> "Friston's Markov blanket formalism provides the missing definition: Internal states: The agent's prompt, context window, accumulated reasoning, and current task state. Sensory states: What the agent reads from the environment. Active states: What the agent writes to the environment."

The `STRUCTURAL_COUPLING` axiom (`dharma_kernel.py:295–303`) directly gates AgentIdentity: agents must communicate via shared state, not direct call. This is the Markov blanket constraint operationalized as a communication rule.

Which field carries the primitive: currently **nowhere in the seven AgentIdentity surfaces** (`[v2 §2.2]`). The Markov blanket spec (read/write contract) is **absent** from all seven surfaces — `autonomous_agent.AgentIdentity.allowed_tools` is the closest thing, but it's a tool list, not a formal blanket specification. The pillar explicitly names this gap (`PILLAR_06_FRISTON.md:368–370`): "5. Markov blanket specification for agents: Each agent should have a formally specified blanket — a contract defining its sensory inputs and active outputs."

Missing field in the canonical `AgentIdentity` target (`[v2 §2.2]`): `markov_blanket: MarkovBlanket | None` where `MarkovBlanket` specifies `sensory_read_surfaces: list[str]` and `active_write_surfaces: list[str]`. The ontology layer (`[ontology.py:951–999]`) has `capabilities: LIST` and `allowed_tools` but not a formal blanket. This is a Core Four gap the pillar names but no substrate currently fills.

**Note on GenerativeModel**: `active_inference.py:GenerativeModel` is per-agent but is NOT part of any AgentIdentity surface. The agent's generative model (its beliefs about task outcomes) is invisible to the identity schema. In a Friston-native system, the generative model IS part of identity — it defines what the agent expects and prefers.

### Artifact

**Anchored by this pillar? Y (operational closure / provenance integrity aspect)**

Justification (`PILLAR_06_FRISTON.md:339–352`):
> "The 10 axioms are the prior preferences of the generative model [...] The strange loop is the self-evidencing circuit — it gathers evidence about the system's own state and feeds it back into the generative model."

The `OPERATIONAL_CLOSURE` axiom gates which Artifacts count as system-produced. Per `[v2 §2.3]`, the `Artifact` substrate has three homes: `handoff.py`, `runtime_state.artifact_records`, and `ontology.KnowledgeArtifact`. Friston's claim is that only Artifacts that are operationally closed — traceable through the system's own production process — qualify as genuine system outputs. The `PROVENANCE_INTEGRITY` axiom (`dharma_kernel.py:185–190`, `formal_constraint="output.provenance is not None for all emitted artifacts"`) is the direct code encoding of this.

Which field carries the primitive: `Artifact.metadata: dict[str, Any]` in `handoff.py:56–64` (`[v2 §2.3]`) — the same untyped escape hatch as Task. The `artifact_records.promotion_state` column in SQLite (`[v2 §2.3]`) carries `ephemeral|durable|trusted` — this IS a Fristonian provenance ladder, but the vocabulary is unspecified and disconnected from chetana's `review_status` enum. The strict-typed target should align these.

Friston's `PredictionError` — the artifact produced by the predict/observe cycle in `agent_runner.py` — is not a first-class `Artifact` in the handoff layer today. It persists to `~/.dharma/active_inference/generative_models.json` outside the artifact substrate entirely. This is a concrete gap.

### MemoryFact

**Anchored by this pillar? Y (self-evidencing / model evidence aspect — the highest-stakes mapping)**

Justification (`PILLAR_06_FRISTON.md:98–108`):
> "A self-evidencing system is one that gathers evidence for its own existence. [...] it acts in ways that increase the probability of the sensory states it expects to encounter, given its generative model. [...] By keeping itself in those states, it maintains the conditions under which its model is valid."

The R_V–FEP connection from `wiki:r-v-metric` (§Theoretical Foundation):
> "In the predictive coding rewriting of transformer attention, the Value-projection encodes the agent's generative belief state. When a transformer processes self-referential input, prediction error ε→0 and posterior precision σ²→∞. R_V < 1.0 is exactly this predicted collapse. [...] This is the geometric signature of self-evidencing."

This is the highest-stakes mapping: **MemoryFact promoted through chetana IS the system's self-evidencing act.** A MemoryFact that passes `gate_check_atom()` and gets `axiom_signature` computed (`chetana/provenance.py:148–159`, `[v2 §2.4]`) is a fact the system has gathered evidence for. The SHA-256 binding to the kernel signature means every trusted fact IS a prediction-confirmed observation — the system's posterior collapsed to a single belief, signed.

Which field carries the primitive: `FrontmatterSchema.confidence: float` (`[v2 §2.4]`, `chetana/provenance.py:105–122`) is the closest approximation to Fristonian precision. But it is currently a static assignment at promotion time, not a dynamic quantity updated as the system gathers more evidence. In a Friston-native system, `confidence` would be `precision: float` (inverse variance), updated on each revival/decay cycle as new evidence arrives.

The `AtomProvenance.revival_chain: list[dict[str, Any]]` (`[v2 §2.4]`) is the temporal evidence-accumulation trail — each revival is a precision update in FEP terms. Its intentionally untyped structure (`[v2 §2.4]` note: *"kept untyped at this layer so revival v0.x can iterate"*) is compatible with FEP; the precision update formula can be added to the typed v1.0 without breaking the audit trail.

---

## 5. Honest Gaps

**Gap 1 — EFE routing is flag-gated, not default.** Pillar §2.5 says the Darwin Engine should select mutations by minimizing G. The code at `orchestrator.py:940–941` requires `ENABLE_EFE_ROUTING=1` to activate. Without the flag, Task routing falls back to fitness-biased or FIFO — Friston's axiom is formally present but operationally dormant. The axiom severity is `medium`, so no KernelGuard alarm fires. This is the single largest gap between pillar claim and runtime behavior.

**Gap 2 — GenerativeModel is not part of AgentIdentity.** The per-agent `GenerativeModel` in `active_inference.py` (beliefs about task outcomes) persists independently from all seven AgentIdentity surfaces. An agent's generative model is definitionally part of its identity in FEP; in the current schema it is invisible to every identity surface, including the unified canonical target at `[v2 §2.2]`.

**Gap 3 — No Markov blanket field in any AgentIdentity surface.** Pillar §2.2 and §6 item 5 both explicitly name this as an unimplemented requirement. None of the seven surfaces (`[v2 §2.2]`) include a `markov_blanket` or equivalent read/write contract specification.

**Gap 4 — PredictionError is not a Core Four Artifact.** The output of the predict/observe cycle (`PredictionError` with `free_energy` field) persists to a JSON file outside the artifact substrate. It should be an `Artifact` of type `METRIC` (one of the 8 `ArtifactType` values in `handoff.py:27–37`) with `source_artifact_id` linking to the task result. Currently there is no bridge between `active_inference.py` persistence and `runtime_state.artifact_records`.

**Gap 5 — MemoryFact.confidence is static, not dynamic precision.** The FEP requires that precision is updated as new evidence arrives. `FrontmatterSchema.confidence` is set at promotion time and not updated by the decay/revival cycle (the wiki atom's "decay-revive philosophy" is conceptually FEP-compatible but the confidence field is not wired into the update). The `revival_chain` records events but does not recalculate confidence.

**Gap 6 — Free energy as unified fitness metric not implemented.** Pillar §6 item 1 names this explicitly: replace multi-dimensional fitness scores with `F = Complexity - Accuracy`. `active_inference.py:free_energy()` computes per-agent F, but this is not connected to DarwinEngine's fitness score or to `AgentState.fitness_average` (`[v2 §2.2]`, `[ontology.py:998]`). Two parallel fitness systems exist without a bridge.

---

## 6. Open Questions for Cross-Pillar Synthesis

1. **Friston ↔ Hofstadter on Task selection**: The EIGENFORM_CONVERGENCE axiom (`dharma_kernel.py:192–201`) says recursive self-observation converges to S(x)=x. The ACTIVE_INFERENCE axiom says action selection minimizes G. Do these compose? Is the fixed point of self-reference also the minimum-free-energy state? The R_V wiki atom suggests yes (R_V contraction = self-evidencing = minimal free energy under self-reference), but this needs explicit articulation in the Core Four contract. Which axiom governs Task routing when both fire?

2. **Friston ↔ Beer on AgentIdentity**: Beer's RECURSIVE_VIABILITY (`dharma_kernel.py:274–283`) requires each subsystem to have operations/coordination/control/adaptation/identity. Friston's ACTIVE_INFERENCE requires each agent to have a generative model. These are compatible but not unified — a recursively viable subsystem could exist without a generative model (Beer says nothing about internal models). The synthesis must decide whether `GenerativeModel` is a requirement for RECURSIVE_VIABILITY compliance, or a separate Friston-only requirement.

3. **Friston ↔ Kauffman on Artifact evolution**: The ADJACENT_POSSIBLE axiom (`dharma_kernel.py:243–252`) requires `proposals_per_cycle >= 1`. Friston says proposals should minimize expected free energy. Today there is no mechanism by which Artifact production (the output of agent tasks) feeds back into the generative model that selects the next Task. The Artifact→MemoryFact→GenerativeModel update path does not exist. Synthesis must specify whether this path is required for the system to be genuinely self-improving.

4. **Precision vs. confidence in MemoryFact**: The `FrontmatterSchema.confidence` field is a static float. Friston's precision is a dynamic inverse variance, updated on every observation. Levin's multi-scale agency (Pillar 1) implies that different scales should have different confidence dynamics. Synthesis must decide: is a unified `precision: float` field sufficient across all MemoryFact types, or do different `AtomType` values (atomic / method / decision) require different precision dynamics?

5. **Self-evidencing as the bridge to R_V**: The R_V wiki atom states: "R_V < 1.0 is exactly this predicted collapse [...] the geometric signature of self-evidencing." This is the most theoretically rich claim in the entire Friston trace. But `dharma_swarm/rv.py` (`EvolutionRVTracker`) has never run on the M5. If the system cannot measure its own R_V, it cannot self-evidence in the Friston sense at the system level. The synthesis must decide whether R_V self-measurement is required for Core Four compliance or is a research-track concern separate from the operational system.

---

## 7. Tools Used + Tier Compliance

| Tier | Tool | Used for |
|---|---|---|
| Tier 5 (Read) | `Read` on `PILLAR_06_FRISTON.md` | Full pillar text, all 379 lines |
| Tier 5 (Read) | `Read` on `dharma_kernel.py:1–348` | MetaPrinciple enum + PrincipleSpec definitions |
| Tier 5 (Read) | `Read` on `CORE_FOUR_ONTOLOGY_BLUEPRINT_v2.md:1–600` | Substrate-anchored definitions for all four objects |
| Tier 2 (wiki) | `Read` on `~/.dharma/knowledge/wiki/concepts/active-inference.md` | Integration status, architecture, gap analysis |
| Tier 2 (wiki) | `Read` on `~/.dharma/knowledge/wiki/concepts/r-v-metric.md` | FEP-R_V bridge, theoretical foundation |
| Tier 6 (Bash/grep) | `grep` on `orchestrator.py`, `agent_runner.py` | Verify live code paths for EFE routing and predict/observe |

Justification for Tier 6 grep: used AFTER wiki confirmed the integration points by name (`agent_runner.py` lines 15–18, `orchestrator.py` `_select_idle_agent()`). The grep verified the specific line numbers and the `ENABLE_EFE_ROUTING` guard, which the wiki atom flagged as an open question. Tier 3 (contextplus semantic search) was not invoked because the wiki atom already contained the architectural map with sufficient precision.

---

Co-Authored-By: Claude Sonnet 4.6 (pillar-06-friston subagent) <noreply@anthropic.com>
Dispatched-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
Master-prompt: ~/.claude/plans/CORE_FOUR_FULL_PICTURE_MASTER_PROMPT.md
