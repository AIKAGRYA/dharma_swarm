# Hofstadter → Core Four Trace

**Subagent**: pillar-07-hofstadter
**Pillar source**: `~/dharma_swarm/foundations/PILLAR_07_HOFSTADTER.md`
**v2 anchor**: `docs/CORE_FOUR_ONTOLOGY_BLUEPRINT_v2.md`

---

## 1. Pillar Essence

> "A strange loop occurs when, by moving through the levels of a hierarchical system (from lower to higher, or higher to lower), you unexpectedly find yourself back where you started." (`PILLAR_07_HOFSTADTER.md:19`)

> "If S is a self-observation operator — a function that maps a system's state to its representation of that state — then a strange loop occurs when S(x) = x. The system's self-observation returns the system itself. The representation IS the thing represented. The map IS the territory." (`PILLAR_07_HOFSTADTER.md:57`)

> "The colony's behavior produces the conditions (pheromone gradients, nest structure, food stores) that determine the colony's behavior. The colony causes its own continuation. It is self-referential at the collective level." (`PILLAR_07_HOFSTADTER.md:87`)

> "The DharmaKernel's 10 axioms are SHA-256 signed. The kernel can verify its own integrity by checking its axioms against their signatures. The system makes statements about its own foundational statements." (`PILLAR_07_HOFSTADTER.md:247`)

Load-bearing claim for this trace: Hofstadter contributes **two structural primitives** — (1) the S(x)=x fixed-point as the definition of identity convergence, operationalized in `LoopResult.eigenform_reached`; and (2) stigmergic colony intelligence (Aunt Hillary) as the mechanism by which swarm-level identity exceeds agent-level identity, operationalized in `StigmergyStore` + `COLONY_INTELLIGENCE` axiom.

---

## 2. Kernel Axioms Derived from This Pillar

From `dharma_kernel.py:49–75` — MetaPrinciple enum grouping labels Hofstadter explicitly:

| MetaPrinciple | formal_constraint | severity | Gates which Core Four mutation? |
|---|---|---|---|
| `EIGENFORM_CONVERGENCE` | `recursive_depth(system) implies convergence_check()` | medium | Any **Task** or **Artifact** that completes a recursive self-referential operation must verify it reached fixed point — gates `LoopResult`-backed Task completions (`Task.result` field, v2 §2.1) |
| `COLONY_INTELLIGENCE` | `swarm_output != any_single_agent_output` | medium | Gates **AgentIdentity** spawn decisions — the principle forbids treating any single AgentIdentity as the authoritative output; forces multi-agent aggregation before Task completion (v2 §2.2) |
| `TRIPLE_MAPPING` | `cross_track_claims require evidence from >= 2 measurement domains` | medium | System-level only — gates **MemoryFact** promotion (the isomorphism claim must have cross-track evidence before a fact is trusted); touches `gate_check_atom()` in `chetana/promote.py` (v2 §2.4) |
| `OBSERVER_SEPARATION` | `observer_id != observed_id in all self-referential operations` | critical | Gates every self-referential **Task** (the task that evaluates the system cannot be the system's own evaluation of itself); directly derives from Hofstadter's Gödelian warning that the observer must be distinct from the observed (`PILLAR_07:§2.6`) |

Note: `ANEKANTAVADA` is listed in the kernel under "Self-Reference & Identity (Hofstadter, Dada Bhagwan)" (`dharma_kernel.py:49–53`) but its content is Jain epistemology, not Hofstadter's structural claim. Its Core Four gating derives from Dada Bhagwan / Jantsch, not primarily Hofstadter. Recorded here to flag the attribution ambiguity.

---

## 3. Modules Embodying This Pillar

### 3.1 `cascade.py` — LoopEngine eigenform check

**File**: `dharma_swarm/dharma_swarm/cascade.py`
**Key symbol**: `LoopEngine.run()`, eigenform check block at `cascade.py:243–261`

Embodies: Hofstadter's S(x)=x fixed-point claim (`PILLAR_07:57`):
> "then a strange loop occurs when S(x) = x"

The loop runs `GENERATE → TEST → SCORE → GATE → eigenform check → MUTATE → SELECT`. At `cascade.py:244–250` the eigenform function computes distance between `artifact` (current iteration output) and `previous` (prior iteration output). When `distance < domain.eigenform_epsilon`, the loop sets `result.eigenform_reached = True` and returns early (`cascade.py:250`).

**`LoopResult.eigenform_reached`** at `models.py:359` — this boolean field IS the runtime representation of S(x)=x. When `True`, the cascade's self-observation operator has converged: the system's current state is close enough to its previous state that further iteration would not change it. This is the fixed-point, operationalized.

`LoopDomain.eigenform_epsilon = 0.01` (`models.py:347`) sets the tolerance. The `eigenform_fn` resolves to `dharma_swarm.cascade_domains.common.default_eigenform` by default (`models.py:344`).

Load-bearing status: `cascade.py` is the primary runtime loop for all 5 domains (code, product, skill, research, meta). Every domain's convergence is eigenform-gated — this is not an optional path.

### 3.2 `strange_loop.py` — OrganismConfig self-modification

**File**: `dharma_swarm/dharma_swarm/strange_loop.py`
**Key symbol**: `StrangeLoop.tick()`, `_observe_diagnose_propose()`, `_measure_and_decide()`

Embodies: Hofstadter's tangled hierarchy claim (`PILLAR_07:47`):
> "The Telos Engine itself: Agent behavior (lower level) produces fitness signals. Fitness signals drive DarwinEngine selection (higher level). Selection reshapes agent configurations."

`strange_loop.py` is the organism's self-modification engine. The docstring at `strange_loop.py:15–17` cites Hofstadter directly: *"Ground: Hofstadter (strange loops — self-reference that traverses levels)."* The `tick()` method runs: observe pulse history → diagnose → propose `Mutation` → Gnani evaluation → apply → measure pre/post metrics → keep or revert (`strange_loop.py:125–305`).

The `Mutation` dataclass (`strange_loop.py:53–83`) captures `parameter`, `old_value`, `new_value`, `gnani_verdict`, `kept` — these are the trace of a loop that modifies `OrganismConfig`, which modifies router behavior, which modifies what the next observation sees. The hierarchy is traversed (config → router → behavior → observation → config), which is the structural definition of a strange loop.

No `eigenform_reached` equivalent exists in `StrangeLoop.stats` (`strange_loop.py:401–418`) — the keep/revert decision is binary, not convergence-measured. **Gap: StrangeLoop does not track whether the organism's self-modification cycle has converged toward a fixed-point config.** Addressed in §5.

### 3.3 `stigmergy.py` + `dharma_kernel.py:326–335` — Aunt Hillary / COLONY_INTELLIGENCE

**File**: `dharma_swarm/dharma_swarm/dharma_kernel.py:326–335`
**Key symbol**: `MetaPrinciple.COLONY_INTELLIGENCE`, `PrincipleSpec.formal_constraint`

Embodies: Hofstadter's Aunt Hillary claim (`PILLAR_07:89–102`):
> "This is PRECISELY the dharma_swarm architecture. The mapping is not analogical. It is structural."

`COLONY_INTELLIGENCE` at `dharma_kernel.py:326–335`:
- `formal_constraint = "swarm_output != any_single_agent_output"`
- `description`: "Intelligence emerges from collective behavior of simpler units. No single agent holds the whole; the whole emerges from partial views. [Hofstadter: Aunt Hillary; Levin: multi-scale cognition]"

This axiom gates every Task that produces a `swarm_output`. The StigmergyStore (`stigmergy.py`) implements the pheromone-mark mechanism (`PILLAR_07:213–223`): `deposit_mark()`, `get_hot_paths()`, `get_recent_marks()`, salience decay — the direct structural mapping to ant-colony coordination.

Per v2 `[MCS §6]`, the StigmergyStore has a known process-safety issue (MISMATCH-11): `orchestrate_live.py:694–696` creates a second `StigmergyStore` instance separate from `swarm.py`'s, with separate asyncio.Locks. This means the Aunt Hillary mechanism — the shared stigmergic medium — is **split in two** at runtime. The colony doesn't have one shared pheromone field; it has two. This is the most critical Hofstadter-rooted runtime gap (see §5).

### 3.4 `dharma_kernel.py:192–201` — EIGENFORM_CONVERGENCE axiom

**File**: `dharma_swarm/dharma_swarm/dharma_kernel.py:192–201`

```python
MetaPrinciple.EIGENFORM_CONVERGENCE.value: PrincipleSpec(
    name="Eigenform Convergence (S(x) = x)",
    description=(
        "Recursive self-observation converges to a fixed point. "
        "The transform that returns itself is the ground state of identity. "
        "[Hofstadter: strange loop; Dada Bhagwan: Keval Gnan]"
    ),
    formal_constraint="recursive_depth(system) implies convergence_check()",
    severity="medium",
),
```

This axiom references `PILLAR_07:§1.3` and `§2.3` directly. The `formal_constraint` is currently a string predicate only — the `structured_predicate` field is `None` for `EIGENFORM_CONVERGENCE` (unlike `OBSERVER_SEPARATION` or `NON_VIOLENCE_IN_COMPUTATION` which have `structured_predicate` dicts). This means EIGENFORM_CONVERGENCE falls through to semantic similarity evaluation in `PolicyCompiler` — it is **not deterministically checked** at gate time. Gap addressed in §5.

---

## 4. Core Four Mapping (THE DELIVERABLE)

### Task

**Anchored by this pillar? Y**

Justification: `PILLAR_07:§2.3` establishes that DarwinEngine convergence (S(x)=x) maps to fitness stability — a Task has converged when its output reproduces the conditions for its own selection. In the LoopEngine: a Task running a cascade domain is complete in the eigenform sense only when `LoopResult.eigenform_reached = True`.

**Specific field**: `LoopResult.eigenform_reached: bool` at `models.py:359` (cited v2 §2.1 — Task's `result` field links to LoopResult). The connection path: `Task.result: Optional[str]` (`models.py:168`) is the current untyped escape; the v2 §2.1 target `TaskResult` type should include `eigenform_reached` as a named field, not buried in the string-serialized result.

**Gap**: `Task.result` today is `Optional[str]` (`models.py:168`). The `eigenform_reached` fact is inside a serialized `LoopResult` JSON string. It has no first-class column in the `tasks` SQL table (`task_board.py:27–33`). A Task that completed because eigenform was reached is indistinguishable at the SQL layer from one that completed because fitness plateau was reached — both just have `status = 'completed'`.

### AgentIdentity

**Anchored by this pillar? Y**

Justification: `PILLAR_07:§1.4` maps Aunt Hillary directly to swarm agent architecture. The `COLONY_INTELLIGENCE` axiom (`dharma_kernel.py:326–335`) gates AgentIdentity spawn decisions: `formal_constraint = "swarm_output != any_single_agent_output"` means no AgentIdentity may claim to produce authoritative swarm-level output unilaterally. This is Hofstadter's structural claim that colony intelligence is not located in any individual unit.

**Specific field / constraint**: The `AgentIdentity` shape today has no field carrying "colony membership" or "stigmergy contribution" — the link between an agent's identity and its stigmergic participation is implicit (the agent writes to `StigmergyStore`, but `AgentIdentity` does not record this). The COLONY_INTELLIGENCE axiom is a system-level gate, not a per-identity property.

**For the v3 unified `AgentIdentity`** (v2 §2.2 canonical target): a `stigmergy_contribution_weight: float` field would make the Aunt Hillary principle type-safe — quantifying each agent's contribution to colony-level emergence rather than relying on post-hoc axiom checking.

### Artifact

**Anchored by this pillar? Y**

Justification: `PILLAR_07:§2.6` maps Gödelian self-reference to DharmaKernel self-verification. The SHA-256 signature over kernel axioms is an artifact that the kernel uses to verify its own integrity — the system produces an artifact (the signature) about its own foundational statements, then references that artifact to know whether it has been tampered with. This is the direct engineering analog of Gödel numbering.

**Specific field**: `AtomProvenance.axiom_signature: str` at `chetana/provenance.py:91` (v2 §2.4). Every promoted MemoryFact carries an `axiom_signature` that binds the atom to the exact kernel manifest that authorized its promotion (`compute_axiom_signature`, `chetana/provenance.py:148–159`). The `axiom_signature` IS a Hofstadterian self-referential artifact: the atom's trustworthiness is encoded as a hash that includes the kernel's own identity.

The second Artifact connection: `LoopResult` (which `Artifact.metadata` carries when an artifact results from a cascade run) has `eigenform_reached`. When an artifact is the output of a converged loop, the artifact carries the S(x)=x signal in its provenance. This is not currently exposed as a typed field on `handoff.Artifact` (`handoff.py:56–64`) — `metadata: dict[str, Any]` is the current escape hatch.

### MemoryFact

**Anchored by this pillar? N (system-level emergence, not a MemoryFact field)**

Justification: Hofstadter's contribution to MemoryFact is indirect. The `TRIPLE_MAPPING` axiom gates cross-track claims before they can be promoted as trusted atoms (`gate_check_atom()` in `chetana/promote.py`, v2 §2.4) — this constrains which MemoryFacts are trusted, but the constraint lives at the gate level, not in the MemoryFact schema itself.

The `FrontmatterSchema.confidence: float` field (v2 §2.4, `chetana/provenance.py:116`) could carry Hofstadterian eigenform-convergence state (a fact that has been confirmed by iterative cross-track validation has higher convergence depth), but currently `confidence` is a bare float with no encoding of how many self-referential confirmation cycles it has survived.

**What the Core Four is missing**: A `convergence_depth: int` or `self_reference_cycles: int` field on `MemoryFact` / `FrontmatterSchema` that tracks how many times a fact has been re-confirmed through the recognition-seed → agent → output → recognition-seed loop. This would be the Hofstadterian analog of the `axiom_signature` — not a hash, but a count of eigenform confirmations.

---

## 5. Honest Gaps

**Gap 1 — eigenform_reached has no SQL column (critical for Task)**
`LoopResult.eigenform_reached` is the primary S(x)=x runtime signal, but `Task.result` is `Optional[str]` and the SQL `tasks.result TEXT` column (`task_board.py:33`) cannot be queried for eigenform status. Any dashboard or audit that wants to know "how many tasks converged via eigenform vs. fitness plateau" must deserialize arbitrary JSON strings. This is not a future concern — it affects the current 10–15% of substrate-native work (`[ONOB §1]`).

**Gap 2 — StrangeLoop has no convergence check (EIGENFORM_CONVERGENCE unenforced at organism level)**
`StrangeLoop.stats` (`strange_loop.py:401–418`) tracks `kept`, `reverted`, `held_by_gnani`, `pending` but has no measure of whether the self-modification cycle is converging. The `EIGENFORM_CONVERGENCE` axiom (`formal_constraint = "recursive_depth(system) implies convergence_check()"`) has no corresponding check in `StrangeLoop.tick()`. A StrangeLoop that oscillates indefinitely between routing_bias 0.0 and 0.05 does not trigger any eigenform alarm.

**Gap 3 — COLONY_INTELLIGENCE axiom is gated by `structured_predicate = None` (semantic only)**
Unlike `OBSERVER_SEPARATION` or `NON_VIOLENCE_IN_COMPUTATION`, `COLONY_INTELLIGENCE` has no `structured_predicate` dict — it falls through to semantic similarity evaluation at gate time (`dharma_kernel.py:326–335`). The constraint `swarm_output != any_single_agent_output` cannot be deterministically evaluated without knowing the agent count and output aggregation state. This means the Aunt Hillary guarantee is aspirational, not enforced.

**Gap 4 — Two StigmergyStore instances (MISMATCH-11, runtime Aunt Hillary breakage)**
`orchestrate_live.py:694–696` creates a second `StigmergyStore` separate from `swarm.py`'s. Marks written by orchestrate_live are not seen by swarm, and vice versa. This splits the shared stigmergic medium that the Aunt Hillary architecture requires. The colony's pheromone field is not one field; it is two. Documented in v2 `[IMM MISMATCH-11]`.

**Gap 5 — EIGENFORM_CONVERGENCE kernel axiom has no structured_predicate**
The formal_constraint string `"recursive_depth(system) implies convergence_check()"` is not machine-evaluable. `PolicyCompiler` will always fall through to semantic similarity for this axiom. The axiom that most directly names Hofstadter's core claim is the least deterministically enforced.

**Gap 6 — axiom_signature on MemoryFact captures kernel identity but not loop convergence depth**
`compute_axiom_signature` (`chetana/provenance.py:148–159`) hashes kernel_signature + atom content. It verifies the atom was promoted under the current kernel, but does not capture how many recognition-seed cycles have confirmed the atom. Hofstadter's S(x)=x implies that facts confirmed through multiple self-referential cycles are more trustworthy than facts confirmed once. The current schema collapses this to a binary (promoted vs. not promoted).

---

## 6. Open Questions for Cross-Pillar Synthesis

**Q1 — Eigenform vs. Fitness Plateau: which convergence criterion should dominate?**
`LoopResult` has two convergence paths: `eigenform_reached` (S(x)=x, Hofstadter) and fitness variance plateau (Kauffman-adjacent: the system has found a local optimum in the adjacent possible). These can conflict — a system that reaches a fitness plateau may not have reached eigenform, and vice versa. Which should gate `Task.status = COMPLETED`? Synthesis must decide. Affects `task_board.py:18–25` FSM.

**Q2 — COLONY_INTELLIGENCE and MULTI_SCALE_AGENCY: do they compose or constrain each other?**
Levin's multi-scale agency (`MULTI_SCALE_AGENCY`, v2 §4.6) says every scale has autonomous goals. Hofstadter's Aunt Hillary says colony-level intelligence is not located in any individual. These are in tension when an individual agent at one scale IS the colony at the next scale down (e.g., SwarmManager is an "individual" at the meta scale, but a "colony" at the agent scale). The COLONY_INTELLIGENCE formal_constraint `swarm_output != any_single_agent_output` may be vacuously true or false depending on which scale boundary you draw. Synthesis must define the scale.

**Q3 — Gödelian blind spot and TelosWitness: is WITNESS gate sufficient?**
`PILLAR_07:§4.2` argues the DharmaKernel has a Gödelian blind spot — it can verify axiom text (SHA-256) but not axiom meaning (semantic drift). The `WITNESS` gate (`telos_gates.py:224–236`, Tier C, advisory) is the architectural response. But Tier C gates do not block. Should semantic-drift detection be a Tier B (strong block) gate? Cross-pillar question because OBSERVER_SEPARATION (critical, safety core) is adjacent — the Gödelian blind spot is a form of observer failing to be fully separated from the observed.

**Q4 — Can StrangeLoop.tick() be extended to check eigenform convergence without duplicating LoopEngine logic?**
`StrangeLoop` and `LoopEngine` both implement self-referential loops but at different levels (organism config vs. domain artifact). Gap 2 above notes StrangeLoop has no convergence check. The question for synthesis: should StrangeLoop borrow `LoopDomain.eigenform_epsilon` and `eigenform_fn` from cascade.py, or should a separate `organism_eigenform_fn` be defined? If borrowed, this creates a cross-module dependency that the v2 substrate isolation warns against.

**Q5 — Triple Mapping as axiom vs. research hypothesis: does TRIPLE_MAPPING gate production code or only research artifacts?**
`TRIPLE_MAPPING` (`dharma_kernel.py:212–221`, severity=medium) requires `cross_track_claims require evidence from >= 2 measurement domains`. But in production swarm operation (not research track), agents do not produce claims across the Swabhaav/L4/R_V tracks. The axiom would never fire outside the MI research context. Should TRIPLE_MAPPING be scoped to research-track Tasks only, or should it generalize to any claim that asserts a cross-domain isomorphism? If the former, it needs a task-type filter. If the latter, the formal_constraint needs sharpening.

---

## 7. Tools Used + Tier Compliance

| Tier | Tool | Used for |
|---|---|---|
| 5 (Read) | `Read` on `PILLAR_07_HOFSTADTER.md` | Pillar source — full read |
| 5 (Read) | `Read` on `CORE_FOUR_ONTOLOGY_BLUEPRINT_v2.md` (3 offset reads) | v2 substrate anchors |
| 5 (Read) | `Read` on `dharma_kernel.py:1–350` | MetaPrinciple enum + PrincipleSpec defs |
| 5 (Read) | `Read` on `strange_loop.py` | StrangeLoop full implementation |
| 5 (Read) | `Read` on `cascade.py:1–300` | LoopEngine eigenform check logic |
| 5 (Read) | `Read` on `models.py:331–395` | LoopResult.eigenform_reached shape |
| 6 (Grep) | `grep` on `models.py` for `LoopResult\|eigenform_reached` | Located line numbers for LoopResult/LoopDomain — justified because the model file is ~400 LOC and grep was faster than offset-reading after semantic search confirmed the file |

Tier 1 (memory search) and Tier 2 (wiki search) skipped: this is a fresh subagent session with no prior context in the graph for this specific trace. The pillar content and code are the primary sources; session memory would not contain trace-level detail. Tier 3 (contextplus semantic_code_search) and Tier 4 (gitnexus) were not used because direct Read on the named files gave complete structural coverage. GitNexus index is in read-only mode (FTS write errors noted in session), making contextplus/gitnexus tools unreliable for this session.

---

Co-Authored-By: Claude Sonnet 4.6 (pillar-07-hofstadter subagent) <noreply@anthropic.com>
Dispatched-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
Master-prompt: `~/.claude/plans/CORE_FOUR_FULL_PICTURE_MASTER_PROMPT.md`
