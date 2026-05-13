# Deacon (Absential Causation) → Core Four Trace

**Subagent**: pillar-05-deacon
**Pillar source**: ~/dharma_swarm/foundations/PILLAR_05_DEACON.md
**v2 anchor**: docs/CORE_FOUR_ONTOLOGY_BLUEPRINT_v2.md

---

## 1. Pillar Essence

Deacon's load-bearing claim (`PILLAR_05_DEACON.md:13–17`):

> "Deacon calls this **absential causation**: the causal efficacy of things that don't exist. This is not mysticism. It is a precise observation that the explanatory frameworks of physics — which deal only in present forces, present particles, present fields — systematically cannot account for the most obvious features of life and mind."

The engineering inversion that drives everything downstream (`PILLAR_05_DEACON.md:73–84`):

> "A constraint, by excluding certain possibilities, CREATES a new space of possibilities that could not exist without the constraint... The general principle: **constraints at one level generate capabilities at a higher level.** This is not a metaphor. It is a dynamical fact."

Three dynamical levels map onto the system (`PILLAR_05_DEACON.md:24–48`): homeodynamic (equilibrium-seeking, no telos), morphodynamic (pattern formation, transient), teleodynamic (self-maintaining, purposive). dharma_swarm's claim is that the gate + evolution loop crosses the morphodynamic → teleodynamic threshold. The current implementation has the structure but not yet the dynamics (`PILLAR_05_DEACON.md:172`): *"The 'could' is important... the gates are evaluated but do not yet reshape the fitness landscape in real time."*

The autogen analogy (`PILLAR_05_DEACON.md:120–136`) names the two halves of the reciprocal dependency: autocatalytic agents (catalysis) and telos gates (enclosure). Neither is viable alone.

---

## 2. Kernel Axioms Derived From This Pillar

Source: `dharma_kernel.py:29–75` (MetaPrinciple enum) and `dharma_kernel.py:254–263` (PrincipleSpec).

| MetaPrinciple | formal_constraint | severity | Gates which Core Four mutation? |
|---|---|---|---|
| `CONSTRAINT_AS_ENABLEMENT` | `gate.rejection includes suggested_alternative` | medium | **MemoryFact** — a `promote()` BLOCK must emit a rationale (the "suggested alternative"); gates MemoryFact promotion path directly via `gate_check_atom()`. Also gates **Task**: a blocked Task action must carry what it enables, not just what it denies. |
| `DOWNWARD_CAUSATION_ONLY` | `proposer_layer >= target_layer for constraint operations` | critical | **Task** — kernel-level axioms constrain task FSM transitions from above; lower layers (agents) may propose but not override. Also **AgentIdentity** — agent cannot self-elevate. |
| `REQUISITE_VARIETY` | `len(available_agents) >= len(distinct_task_types)` | high | **AgentIdentity** — variety constraint requires diversity of `AgentIdentity.role` values across the pool. Also **Task** — task type diversity drives agent pool requirements. |
| `ADJACENT_POSSIBLE` | `evolution_archive.generations > 0 AND proposals_per_cycle >= 1` | medium | **Task** — each evolution cycle must produce at least one `Task` representing an adjacent-possible mutation. **Artifact** — `evolution_archive` entries are `ArtifactType.METRIC` records. |

`RECURSIVE_VIABILITY` (`dharma_kernel.py:274–283`) is attributed to Beer (VSM) in the enum comment, not Deacon, though the pillar bridges them (`PILLAR_05_DEACON.md:193–196`). It is credited to Beer's pillar here; not double-counted.

Deacon is the **primary** attribution for `CONSTRAINT_AS_ENABLEMENT` only. The pillar's influence on `DOWNWARD_CAUSATION_ONLY`, `REQUISITE_VARIETY`, and `ADJACENT_POSSIBLE` is cross-pillar (Deacon shapes the framing; Beer and Kauffman hold the formal constraint).

---

## 3. Modules Embodying This Pillar

**Semantic search justification**: contextplus tools unavailable in this subagent context; proceeding to direct file reads (tier 5) after reasoning from pillar text and v2 blueprint citations.

### 3.1 `telos_gates.py` — The Gate System as Generative Constraint

`[telos_gates.py:211–236]` — `TelosGatekeeper.CORE_GATES` dict: 11 immutable gates.

Deacon: *"by constraining the action space, they GENERATE the space of aligned behavior"* (`PILLAR_05_DEACON.md:109`). The gates are not merely a post-hoc filter; per the pillar they define the topology of the aligned action space.

Current implementation gap (pillar's own critique, `PILLAR_05_DEACON.md:111–116`): each gate returns a score + PASS/WARN/BLOCK but does **not** emit a `suggested_alternative` — the `formal_constraint` for `CONSTRAINT_AS_ENABLEMENT` (`dharma_kernel.py:261`). The gate checks at `[telos_gates.py:421–594]` produce `(GateResult, reason_string)` tuples; reason strings describe *what is blocked*, not *what is enabled*.

The `BHED_GNAN` gate (`[telos_gates.py:512–513]`) always passes today ("Doer-witness distinction noted") — no operational content. The pillar's witness-constraint claim (`PILLAR_05_DEACON.md:210–218`) is the most sophisticated Deacon bridge and it is inert.

Ontology layer: `AgentIdentity.Spawn` action carries `telos_gates=["AHIMSA"]` (`[ontology.py:986–993]` per v2 §4.4). This is the most concrete instance of constraint-as-enablement made operational: AHIMSA gates the creation of new agents, defining what kinds of agents can exist.

**Load-bearing status**: HIGH. `TelosGatekeeper.check()` is called from `chetana/promote.py` (`gate_check_atom()`) and from `ontology.py` execute_action flow (v2 §4.3). Any removal would disable atom promotion and action execution.

### 3.2 `chetana/promote.py` — The 11-Step Promotion Bottleneck

`[chetana/promote.py:1–17]` docstring: step 3 is `gate_check_atom()` — telos gates applied to atom body content before trusted promotion.

Deacon connection: the promote() pipeline is the autogen enclosure made operational. The atom cannot leave staging (the "container") until the gates confirm it serves the telos. The gate is the constraint that generates the trusted knowledge space by excluding what doesn't belong there.

`PromoteResult.decision: GateResult` at `[chetana/promote.py:59]` — the BLOCK/WARN/ALLOW decision IS the constraint output. The rationale field (`[chetana/promote.py:61]`) is where the Deaconian "suggested alternative" should live — and it is currently `Optional[str] = None` by default (often not populated).

**Load-bearing status**: HIGH. 22 files, 127 tests on the membrane branch (per chetana hook log). The promote pipeline is the single write bottleneck for `MemoryFact` trusted atoms per v2 §2.4 authority #4.

### 3.3 `dharma_kernel.py` — CONSTRAINT_AS_ENABLEMENT Axiom Spec

`[dharma_kernel.py:254–263]`: the `CONSTRAINT_AS_ENABLEMENT` PrincipleSpec.
- `formal_constraint = "gate.rejection includes suggested_alternative"`
- `severity = "medium"`
- No `structured_predicate` — falls through to semantic similarity evaluation in PolicyCompiler, not deterministic check.

This is the axiom's own gap: it cannot be mechanically verified today (no `structured_predicate`), so `KernelGuard` cannot enforce it deterministically. The constraint exists as a principle but not as a runtime check.

### 3.4 `evolution.py` / `DarwinEngine` (indirect)

The pillar (`PILLAR_05_DEACON.md:204`): *"the Darwin Engine explores the adjacent possible. But WHAT adjacent possible? Deacon says: the one shaped by the telos gates."* The Darwin Engine is named in `CLAUDE.md` as `dharma_swarm/evolution.py`. Per the pillar's §2.1 engineering consequence: before generating mutation candidates, the Darwin Engine should consult gate specifications to define the exploration region. Currently it does not (per pillar §5 "Implications Not Yet Implemented" item 1).

---

## 4. Core Four Mapping (THE DELIVERABLE)

### Task

**Anchored by this pillar? Y**

Justification (pillar quote, `PILLAR_05_DEACON.md:108–110`): *"The 11 telos gates... are currently implemented as alignment filters... Deacon's framework reveals what the gates ACTUALLY do: by constraining the action space, they GENERATE the space of aligned behavior."*

Every Task that passes gate check is a task in the enabled space. Every blocked Task carries information about what IS enabled. The `CONSTRAINT_AS_ENABLEMENT` axiom's `formal_constraint` — *"gate.rejection includes suggested_alternative"* — maps to a missing field on `Task`: when a task is blocked or failed, there is no `suggested_alternative: str | None` field.

Current substrate: `Task.result: Optional[str]` at `[models.py:167]` (v2 §2.1). A blocked task writes its reason into `result`; there is no typed "what is enabled" field. The dict escape hatch `Task.metadata` (`[models.py:170]`) currently absorbs routing hints, stigmergy data, tool flags — but not gate-rejection alternatives.

Deacon-shaped strict-typed target: a `TaskConstraintRecord` nested model inside `Task`:
```python
class TaskConstraintRecord(BaseModel):
    blocking_gate: str | None          # gate name that blocked
    rationale: str                     # why blocked
    suggested_alternative: str | None  # CONSTRAINT_AS_ENABLEMENT field
```
This would give Deacon's principle runtime weight rather than principle-only status. Currently 0% substrate-native.

Cross-pillar note: `DOWNWARD_CAUSATION_ONLY` (Aurobindo-flavored, but Deacon provides the mechanism) gates `Task` FSM transitions — `PENDING → ASSIGNED` cannot be overridden from below.

### AgentIdentity

**Anchored by this pillar? Y (partial / system-level)**

Justification (`PILLAR_05_DEACON.md:150`): *"a teleodynamic agent is not one that has been CONSTRAINED to be aligned. It is one whose own dynamics CONSTITUTE alignment. The constraint is intrinsic, not extrinsic."*

The pillar makes a strong claim about what `AgentIdentity` should be: an agent whose role carries intrinsic alignment, not just external gate-passing. The `AgentIdentity.Spawn` action gated by `AHIMSA` (`[ontology.py:986–993]`, v2 §4.4) is the operational instance. It says: the space of valid agents is defined by the AHIMSA constraint. Creating an agent IS a constraint-enabled act.

However: the SEVEN competing AgentIdentity surfaces (v2 §2.2) mean that in practice, agents are created through paths that bypass the ontology `execute_action` flow entirely. `startup_crew.py` uses dict literals; `autonomous_agent.py` uses a dataclass. Neither passes through `AHIMSA` gate. The Deaconian claim that constraint-generation defines the agent space is violated in 6 of 7 creation paths.

The Deacon contribution to AgentIdentity is primarily system-level emergence: the agent pool's behavioral diversity is constrained-enabled by the gate system (agents that pass all gates are, by definition, in the aligned subspace). But this constraint is not yet intrinsic to `AgentIdentity` as a typed object.

Missing field: `AgentIdentity` has no `teleodynamic_level: Literal["homeodynamic", "morphodynamic", "teleodynamic"]` — the three-level vocabulary from `PILLAR_05_DEACON.md:24–48` has no substrate carrier at all.

### Artifact

**Anchored by this pillar? Y (indirect, via autogen loop)**

Justification (`PILLAR_05_DEACON.md:120–134`): *"the 'catalytic' process (agents doing work) and the 'enclosing' process (the telos/fitness framework) are reciprocally dependent... The autogenesis loop is sketched but not yet closed."*

Artifacts are the **outputs of catalysis** — they are what the agents produce. The autogen's container (telos gates) constrains what artifacts can become trusted. The `Artifact.artifact_type` 8-enum (`[handoff.py:27–37]`, v2 §2.3) includes `METRIC` — evolution fitness metrics. These are the Deaconian fitness measurements that should feed back into the fitness landscape.

The `Experiment.Archive` action `creates=["KnowledgeArtifact"]` (`[ontology.py:914–916]`, v2 §4.4) is the closest operational instance: archiving an experiment produces an artifact that must pass telos gates (`MAHASARASWATI`, `AHIMSA+SATYA`). Constraint enables the creation of a trusted knowledge artifact.

Gap: `Artifact.metadata: dict[str, Any]` (`[handoff.py:63]`, v2 §6.1) carries no typed field for `gate_check_result` — the constraint record that made this artifact trusted. The Deaconian "constraint specification" (what the constraint enabled) is swallowed by the untyped metadata escape.

### MemoryFact

**Anchored by this pillar? Y — this is the PRIMARY and MOST CONCRETE mapping**

The Deacon → telos_gates → MemoryFact promotion path is the **key claim to verify**. Verdict: **REAL and partially operational, with a significant gap**.

The path:
1. Staged atom (in `~/.dharma/knowledge/staging/`) — the morphodynamic state, transient
2. `promote()` calls `gate_check_atom()` (`[chetana/promote.py:33]`) — the constraint runs
3. On ALLOW: atom is written to `~/.dharma/knowledge/wiki/concepts/<slug>.md` with `AtomProvenance.axiom_signature` binding it to the kernel (`[chetana/provenance.py:148–159]`, v2 §2.4)
4. The trusted atom IS a MemoryFact — authority #4 in the CDS Memory Authorities table (v2 §2.4)

This path is **operational on the membrane branch** (`chetana/promote.py:1–17`, 127 tests passing per hook log). The `CONSTRAINT_AS_ENABLEMENT` axiom is operationalized here in the clearest form anywhere in the codebase: the 11 gates constrain what can be a trusted atom, thereby GENERATING the trusted knowledge space.

The gap: `AtomProvenance.rationale` is not a field (`[chetana/provenance.py:84–95]`, v2 §2.4). The `PromoteResult.rationale: str | None = None` (`[chetana/promote.py:61]`) records the decision reason but does not record what the atom **enables** — the Deaconian positive specification. A BLOCK result writes a rejected-atom audit row but there is no `suggested_alternative` in the schema.

The `MemoryFact.truth_state` field (`[runtime_state.py:116–132]`, v2 §2.4) captures validity but not constraint-origin. The `provenance_json TEXT` column is the escape hatch that currently swallows what should be a typed `ConstraintRecord`.

**The `CONSTRAINT_AS_ENABLEMENT` formal constraint — `"gate.rejection includes suggested_alternative"` — is violated across all four Core Four objects.** It is a principle without runtime teeth.

---

## 5. Honest Gaps

**Gap 1: `CONSTRAINT_AS_ENABLEMENT` has no runtime verification.**

The `PrincipleSpec.formal_constraint = "gate.rejection includes suggested_alternative"` has no `structured_predicate` (`dharma_kernel.py:263`). `KernelGuard` cannot deterministically check it. The pillar's central engineering claim — that constraint-as-limitation should be upgraded to constraint-as-generation — is not enforced anywhere. The `PromoteResult.rationale` field exists but is optional and rarely populated. No gate in `telos_gates.py` returns a `suggested_alternative`.

**Gap 2: The autogenesis loop is not closed (pillar's own admission).**

`PILLAR_05_DEACON.md:172`: *"The 'could' is important. The current implementation has the structure but not yet the dynamics. The gates are evaluated but do not yet reshape the fitness landscape in real time."* The Darwin Engine (`evolution.py`) does not consult gate specifications before generating mutation candidates. The constraint → fitness feedback (`PILLAR_05_DEACON.md:133–136`) is wired to `strange_loop.py` observations but not to DarwinEngine's fitness landscape as an intrinsic coupling.

**Gap 3: `BHED_GNAN` gate is inert.**

`[telos_gates.py:512–513]`: always passes with "Doer-witness distinction noted." The pillar's most sophisticated contribution (`PILLAR_05_DEACON.md:210–218`) — the witness as absential constraint that acts by not acting — has no operational content in the gate it maps to. The WITNESS gate (`[telos_gates.py:515–557]`) handles think-phases, but BHED_GNAN specifically (doer-witness distinction) does nothing.

**Gap 4: The three-level vocabulary (homeodynamic / morphodynamic / teleodynamic) has no substrate carrier.**

None of the Core Four objects carries a typed `dynamical_level` field. This means the system cannot self-diagnose whether it has crossed the morphodynamic → teleodynamic threshold — one of the five "Implications Not Yet Implemented" listed in `PILLAR_05_DEACON.md:246`.

**Gap 5: Gate rejections don't propagate Deacon's "positive specification" to MemoryFact.**

When `gate_check_atom()` blocks a promotion, the rejected-atom audit row captures why it was blocked — but not what the constraint ENABLES. Per `[chetana/promote.py:1–17]` step 4: writes rejected-atom audit row but there is no `enabled_space_description` field. The autogen principle says the container's damage-repair tells you what the container is FOR; currently the gate system only tells you what it blocks.

---

## 6. Open Questions for Cross-Pillar Synthesis

1. **Deacon's autogenesis loop vs. Varela's autopoiesis**: Both anchor system-level self-maintenance. Pillar §3.2 says autogen EXTENDS autopoiesis by adding directionality (`PILLAR_05_DEACON.md:192–196`). Does the synthesis assign `OPERATIONAL_CLOSURE` (Varela) and `CONSTRAINT_AS_ENABLEMENT` (Deacon) to separate substrate fields, or does one subsume the other? The `AgentIdentity.Spawn` action's `AHIMSA` gate is both operational-closure (the agent-space boundary is self-produced by what passes the gate) and constraint-as-enablement. Synthesis must decide if these are the same field or two.

2. **Deacon's teleodynamic threshold vs. Friston's free energy minimum**: The pillar says teleodynamic systems work *against* the thermodynamic gradient (contragrade). Friston says systems minimize expected free energy (which IS minimizing surprise, which approaches homeodynamics). Are these in tension for `Task` — should a task surprise-minimize or remain permanently "approaching" an asymptotic telos? The fitness function design depends on resolving this.

3. **`CONSTRAINT_AS_ENABLEMENT` structured_predicate is missing — who adds it?** This is the one Deacon-primary axiom with no deterministic check. Adding `structured_predicate = {"field": "gate_rejection_has_alternative", "op": "eq", "value": False}` would make it mechanically enforceable. But that requires a `PromoteResult.suggested_alternative` field and gate implementations that return one. Is this a v3 deliverable or post-v3?

4. **The `REQUISITE_VARIETY` constraint (`len(available_agents) >= len(distinct_task_types)`) is attributed to Beer/Ashby** with Deacon providing the framing mechanism. Is this actually a Beer pillar axiom that Deacon explains, or a Deacon axiom that Beer quantifies? The assignment matters for which pillar trace owns the AgentIdentity pool-diversity claim.

5. **The telos as permanent absential (`PILLAR_05_DEACON.md:154–161`) implies fitness should be asymptotic, never 1.0.** The Darwin Engine's current fitness function (referenced in `CLAUDE.md` as `ginko_brier.py` for Brier scoring) likely uses a 0–1 bounded score. Does v3 need to introduce an asymptotic fitness function, and if so, which Core Four object carries the `asymptotic_target: float` field? `AgentIdentity.telos_alignment: float` in the GraphQL wire surface (`[graphql_schema:68]`, v2 §2.2) is a 0–1 float today. Deacon says it should never reach 1.0.

---

## 7. Tools Used + Tier Compliance

- **Tier 5 (Read)**: Template (`v3_pillar_subagent_template.md`), v2 blueprint (multiple offset reads), pillar source (`PILLAR_05_DEACON.md`), `dharma_kernel.py:25–155`, `dharma_kernel.py:155–280`, `telos_gates.py:1–100`, `telos_gates.py:200–350`, `telos_gates.py:350–500`, `telos_gates.py:450–600`, `chetana/promote.py:1–80`.
- **Tier 3/4 (contextplus / semantic search)**: Not available in this subagent execution context. Justification for skip: pillar-to-code mapping was sufficiently grounded in v2 blueprint citations (which already cite specific file:line locations for all Core Four substrates). Additional semantic search would add coverage breadth but not change the structural conclusions.
- **Tier 6 (Bash/grep)**: Used only to check `v3_pillar_traces/` directory existence and `_INDEX.md` status. Not used for code search.

---

Co-Authored-By: Claude Sonnet 4.6 (pillar-05-deacon subagent) <noreply@anthropic.com>
Dispatched-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
Master-prompt: ~/.claude/plans/CORE_FOUR_FULL_PICTURE_MASTER_PROMPT.md
