# Beer (VSM) → Core Four Trace

**Subagent**: pillar-11-beer
**Pillar source**: `~/dharma_swarm/foundations/PILLAR_11_BEER.md`
**v2 anchor**: `docs/CORE_FOUR_ONTOLOGY_BLUEPRINT_v2.md`

---

## 1. Pillar Essence

From `PILLAR_11_BEER.md:13`:

> "Beer tells us **exactly how to wire the boxes and channels** so that all of this actually works."

The load-bearing claim: the VSM is not descriptive but normative — **what ANY organization MUST contain** to remain viable. Five systems (S1 Operations, S2 Coordination, S3 Control, S3* Audit, S4 Intelligence, S5 Identity), each necessary. The recursion property is structural isomorphism: every viable system contains viable systems (`PILLAR_11_BEER.md:81–83`).

Ashby's Law is the foundation: "Only variety can absorb variety." (`PILLAR_11_BEER.md:57`). The practical consequence for the swarm: "A simple controller cannot govern a complex system... it is a mathematical impossibility." (`PILLAR_11_BEER.md:65`).

Beer's two axioms that become kernel primitives:

1. **Requisite Variety**: governance must have ≥ as many distinct response modes as the environment has distinct challenge modes.
2. **Recursive Viability**: every subsystem must itself contain S1–S5; the recursion does not terminate at swarm-level.

These are the two MetaPrinciples in `dharma_kernel.py:62` under the explicit comment `# Constraint & Emergence (Deacon, Beer)`.

---

## 2. Kernel Axioms Derived from Beer

Source: `dharma_kernel.py:29–75` (MetaPrinciple enum) and `dharma_kernel.py:95–348` (PrincipleSpec definitions).

| MetaPrinciple | `formal_constraint` | severity | Gates which Core Four mutation? |
|---|---|---|---|
| `REQUISITE_VARIETY` | `len(available_agents) >= len(distinct_task_types)` | **high** | AgentIdentity (fleet must be typed-diverse, not just numerous); Task (task types must be enumerable so the constraint is checkable) |
| `RECURSIVE_VIABILITY` | `subsystem has {operations, coordination, control, adaptation, identity}` | **medium** | AgentIdentity (every agent must structurally express S1–S5 roles; this is why the constitutional topology exists as enum values, not as runtime assertions); system-level emergence (the swarm as a whole must pass the same 5-system check) |

Note: `CONSTRAINT_AS_ENABLEMENT` (`dharma_kernel.py:254–263`) has shared Deacon/Beer provenance (`PILLAR_11_BEER.md:269`: "Beer shows HOW constraints enable at organizational scale. Deacon shows WHY"). This trace attributes it primarily to Deacon; Beer's specific contribution is the two above.

No other MetaPrinciple carries Beer as sole or primary ground.

---

## 3. Modules Embodying Beer

### 3.1 `vsm_channels.py` — Beer's nervous system as code

**Path**: `dharma_swarm/dharma_swarm/vsm_channels.py`

Five distinct classes close five VSM gaps identified in `CLAUDE.md §VII`:

| Gap | Class | VSM role | Beer quote anchor |
|---|---|---|---|
| S3↔S4 feedback | `GatePatternAggregator` | Gates aggregate into zeitgeist signal | `PILLAR_11_BEER.md:47–48` (S3/S4 tension) |
| S3* sporadic audit | `SporadicAuditor` | 5% random, unpredictable audit | `PILLAR_11_BEER.md:37–41` (S3* unpredictability is its power) |
| Algedonic bypass | `AlgedonicChannel` | Pain/pleasure direct to S5 | `PILLAR_11_BEER.md:116–123` |
| Agent recursion | `AgentViabilityMonitor` + `AgentViability` | Agent-internal S1–S5 self-assessment | `PILLAR_11_BEER.md:83–85` (each agent is a viable system) |
| Variety expansion | `VarietyExpansionProtocol` | Formal gate proposal/approve cycle | `PILLAR_11_BEER.md:57–71` (requisite variety grows) |

The `AgentViability` datamodel (`vsm_channels.py:111–134`) is the most explicit Beer construct in the codebase:

```python
class AgentViability(BaseModel):
    s1_operations: float    # Can I do my job?
    s2_coordination: float  # Am I communicating?
    s3_control: float       # Am I passing gates?
    s4_intelligence: float  # Am I aware of context?
    s5_identity: float      # Am I aligned with telos?
    overall: float          # geometric mean — all systems must be healthy
```

`compute_overall()` (`vsm_channels.py:126–133`) uses a geometric mean — if any single VSM system collapses, the agent becomes non-viable. This directly operationalizes "all five necessary" (`PILLAR_11_BEER.md:19`).

### 3.2 `dharma_kernel.py` — S5 as signed axioms

`DharmaKernel` (`dharma_kernel.py:95–100`) is Beer's S5 Identity made tamper-evident. The pillar is explicit (`PILLAR_11_BEER.md:302`):

> "The DharmaKernel -- 10 SHA-256 signed axioms that cannot be modified by any operational process -- is the most literal implementation of shuddhatma in software that I can imagine. It is the unchanging witness-identity around which the entire flux of the swarm organizes itself."

S5 does not execute; it holds the field. `KernelGuard.load()` (`dharma_kernel.py:381–399` per v2 §4.6) raises if SHA-256 fails — no agent can modify S5 at runtime.

### 3.3 `telos_gates.py` — Variety Expansion Protocol

`GateRegistry` (`telos_gates.py:90–191`) implements Beer's VSM Gap 5 directly. The module docstring (`telos_gates.py:1–11`) states:

> "Variety Expansion Protocol (VSM Gap 5 / Beer): Custom pattern-based gates can be proposed, approved by S5 (Dhyana), and loaded at runtime. This ensures governance variety can grow to match threat variety without code changes."

The lifecycle: `propose()` (any agent or subsystem) → `approve()`/`reject()` (S5/Dhyana) → `load_approved()` (runtime activation). This is Ashby's Law operationalized: the governance array must be able to grow when the threat environment grows.

`GateProposal` (`telos_gates.py:40–87`) fields carry `tier: str` (A/B/C, matching `GateTier` enum in `models.py:81–84`), `trigger_patterns: list[str]`, and `justification: str` — every expansion must trace to a principle.

### 3.4 `models.py` — Constitutional AgentRole group as VSM type system

`AgentRole` enum (`models.py:43–65`) carries an explicit comment: `# Constitutional topology (6-agent stable roster)`. The six values:

```python
OPERATOR = "operator"
ARCHIVIST = "archivist"
RESEARCH_DIRECTOR = "research_director"
SYSTEMS_ARCHITECT = "systems_architect"
STRATEGIST = "strategist"
WITNESS = "witness"
```

These ARE Beer's S1–S5 mapped into a type system. The trace (see §4 below). This is the deepest point of the pillar's contribution to Core Four: the constitutional group is not just a roster — it is the VSM architecture encoded as enum constants that gate agent creation via `AgentIdentity.role`.

---

## 4. Core Four Mapping

### Task

**Anchored by Beer?** Y (system-level)

**Justification**: Beer's S1 is the operational units "that DO the work" (`PILLAR_11_BEER.md:21`). `Task` is the unit of S1 activity. Beer's requisite variety axiom constrains Task through the formal predicate: `len(available_agents) >= len(distinct_task_types)` (`dharma_kernel.py:271`). This is only checkable if task types are enumerable — which points directly to the `task_type` gap in the current Task schema.

**Current carrier**: `Task.metadata: dict[str, Any]` (`models.py:170`, v2 §2.1) is where task type currently lives. The `[wiki:models-schema]` note — "this is where type safety goes to die" — means the REQUISITE_VARIETY constraint is currently **unevaluable** at the Pydantic layer because `distinct_task_types` has no typed representation.

**Gap**: The v3 `Task` shape must add `task_type: TaskType` (a typed enum drawn from the concrete use-cases) to make the REQUISITE_VARIETY predicate evaluable. Until that column exists, the Beer axiom gates nothing.

**Beer-specific field the v3 target needs**:
```python
task_type: TaskType          # extracted from metadata; makes REQUISITE_VARIETY checkable
vsm_system: Literal["S1"] = "S1"  # explicit layer tag for routing
```

### AgentIdentity

**Anchored by Beer?** Y — this is the central Beer contribution to Core Four.

**Justification**: The constitutional 6-agent topology (`models.py:57–63`) is Beer's VSM roles encoded as a type system. Each maps to a VSM system:

| `AgentRole` value | VSM system | Beer function |
|---|---|---|
| `OPERATOR` | S3 (Control) | Resource allocation, performance targets, "rules of the game" |
| `ARCHIVIST` | S3* (Audit) | Independent sporadic audit, not on the S2/S3 reporting chain |
| `RESEARCH_DIRECTOR` | S4 (Intelligence) | External scanning, future modeling, adaptation proposals |
| `SYSTEMS_ARCHITECT` | S2 (Coordination) | Anti-oscillation, inter-unit damping, shared protocols |
| `STRATEGIST` | S5 (Policy/Identity) | Constitutional function, identity maintenance, S3/S4 tension balancer |
| `WITNESS` | S5 + Algedonic | Identity witness; direct pain/pleasure bypass (algedonic channel) |

The `WITNESS` role maps to two Beer concepts simultaneously: S5 as the unchanging witness-ground (`PILLAR_11_BEER.md:302`) and the algedonic channel as the direct-to-identity signal path (`PILLAR_11_BEER.md:116–123`). This is the single most load-bearing Beer→AgentIdentity trace.

**Current substrate**: `AgentIdentity.role: AgentRole` at the Pydantic layer (v2 §2.2, canonical target from `[AIU §2]`). The constitutional group exists as enum values. What does NOT exist yet: a `viability: AgentViability | None` field on `AgentIdentity` that would carry the agent-internal S1–S5 self-assessment. `AgentViability` is defined in `vsm_channels.py:111–134` but is not wired into the canonical `AgentIdentity` schema.

**RECURSIVE_VIABILITY gates AgentIdentity** (`dharma_kernel.py:274–283`): `formal_constraint = "subsystem has {operations, coordination, control, adaptation, identity}"`. Each constitutional-role agent must be able to self-report its own S1–S5 health. Without `AgentViability` embedded in or linked from `AgentIdentity`, RECURSIVE_VIABILITY is a named principle with no runtime carrier.

**v2 anchor**: v2 §2.2 Surface 4 (`_AGENT_IDENTITY` ontology object, `[ontology.py:951–999]`) carries `swabhaav_capacity: FLOAT` — this is the closest current proxy for S5 identity health. The RECURSIVE_VIABILITY principle demands four more floats (S1–S4). They do not exist.

### Artifact

**Anchored by Beer?** Y (system-level — variety attenuation and variety amplification)

**Justification**: Beer's variety engineering (`PILLAR_11_BEER.md:91–101`) defines three mechanisms. Artifacts are the carriers of variety attenuation (upward information compression) and variety amplification (downward policy expansion). The pillar is explicit about dharma_swarm: "context.py is a variety attenuator — the 30K character budget compresses... DharmaKernel is a variety amplifier — 10 axioms generate an infinite space of possible compliant actions."

`Artifact.artifact_type` (8-value enum, `handoff.py:27–37` per v2 §2.3) does not currently distinguish attenuating artifacts (ANALYSIS, METRIC, CONTEXT — information compressed upward) from amplifying artifacts (PLAN, CODE_DIFF — policy expanded downward). Beer demands this distinction to route variety correctly through the VSM channels.

**Beer-specific field the v3 target should add**:
```python
variety_direction: Literal["attenuation", "amplification", "lateral"] = "lateral"
vsm_source: str = ""  # which VSM system produced this artifact
vsm_target: str = ""  # which VSM system consumes this artifact
```

These are not cosmetic. Without `variety_direction`, the `GatePatternAggregator` (`vsm_channels.py:142–251`) cannot distinguish whether a gate block represents S1→S3 signal (pain, attenuation) or S5→S1 constraint (amplification) — the entire S3↔S4 feedback loop loses its directional semantics.

### MemoryFact

**Anchored by Beer?** Y (system-level — specifically algedonic channel and S3* audit trail)

**Justification**: Beer identifies two memory types: the normal variety-attenuated reports (compressed, delayed, filterable) and the algedonic channel (two bits, unfiltered, immediate). These map to two distinct `MemoryFact` populations:

1. **Normal S2/S3 memory** — `memory_facts` table (`runtime_state.py:115–132` per v2 §2.4): `fact_kind`, `truth_state`, `confidence`, `valid_from/valid_to`. This is variety-attenuated runtime memory.
2. **Algedonic memory** — `~/.dharma/meta/algedonic.jsonl` (written by `AlgedonicChannel._persist()`, `vsm_channels.py:536–539`): a separate JSONL stream that bypasses the `RuntimeStateStore` entirely.

The split is intentional and correct per Beer: algedonic signals must NOT go through the normal S2/S3 attenuation chain. But it creates a memory authority violation: the `[CDS]` Memory Authorities table (v2 §2.4) does not name `AlgedonicChannel` as an authority. The algedonic JSONL is written outside the `RuntimeStateStore.record_memory_fact()` API, which means it is invisible to `MemoryLattice.recall()`.

**Gap**: Either (a) algedonic signals need a `fact_kind = "algedonic"` write path through `RuntimeStateStore` with `truth_state = "urgent"` and `valid_from = now`, or (b) `MemoryLattice` needs an explicit algedonic subscriber. Currently the algedonic channel writes to `~/.dharma/meta/algedonic.jsonl` and `~/.dharma/meta/ALGEDONIC_ACTIVE.md` (human-readable), neither of which is in the `[CDS]` authority table.

**S3* audit trail**: `SporadicAuditor` (`vsm_channels.py:259–365`) persists `AuditResult` to `~/.dharma/meta/sporadic_audits.jsonl`. Same problem: outside the `RuntimeStateStore`, invisible to `MemoryLattice`.

---

## 5. Honest Gaps

### Gap 1: REQUISITE_VARIETY is unevaluable today

`formal_constraint: "len(available_agents) >= len(distinct_task_types)"` (`dharma_kernel.py:271`). `distinct_task_types` is not a typed field anywhere — it lives in `Task.metadata`. Until `TaskType` is a first-class enum column, this axiom is a named principle without a checkable predicate. The KernelGuard SHA-256 signs the axiom text; it does not verify the constraint holds at runtime.

### Gap 2: RECURSIVE_VIABILITY has no runtime carrier

`formal_constraint: "subsystem has {operations, coordination, control, adaptation, identity}"` (`dharma_kernel.py:282`). `AgentViability` (`vsm_channels.py:111–134`) implements the data shape for this assessment but is not linked from `AgentIdentity`. The constitutional topology enum values exist; agent-level S1–S5 health scores do not exist as a linked field. The viability check is unregistered.

### Gap 3: Algedonic and S3* memory outside all authority surfaces

`AlgedonicChannel` writes to `~/.dharma/meta/algedonic.jsonl` and `~/.dharma/meta/ALGEDONIC_ACTIVE.md`. `SporadicAuditor` writes to `~/.dharma/meta/sporadic_audits.jsonl`. Neither path appears in the `[CDS]` Memory Authorities table (v2 §2.4). Per Beer, this is architecturally correct (algedonic MUST bypass S2/S3 channels) — but it means the memory authority table is incomplete. These are write surfaces that exist in production code, undocumented as authorities.

### Gap 4: Constitutional role → VSM function mapping is informal

`models.py:57–63` carries the comment `# Constitutional topology (6-agent stable roster)`. The mapping from role to VSM function is documented in `PILLAR_11_BEER.md` and this trace file, but is NOT encoded as a typed constant in the codebase. Any future code consuming `AgentRole.OPERATOR` must re-derive that OPERATOR = S3 by convention. A `VSM_ROLE_MAP: dict[AgentRole, str]` constant would make the mapping load-bearing rather than documentary.

### Gap 5: System 2 (Coordination) is the VSM's acknowledged weakness

Per the pillar's own VSD (`PILLAR_11_BEER.md:181–193`): "System 2 (Coordination): ADEQUATE BUT THIN... there is no explicit anti-oscillation mechanism." The `SYSTEMS_ARCHITECT` AgentRole maps to S2, but there is no `S2CoordinationLayer` class or module. The role exists in the enum; the function it names does not exist as a load-bearing module. This is the largest structural gap the Beer pillar reveals.

---

## 6. Open Questions for Cross-Pillar Synthesis

1. **Beer + Levin on AgentIdentity recursion**: Levin's cognitive light cones and Beer's VSM recursion both claim that agent-level structure must mirror swarm-level structure. Does the constitutional 6-role topology apply at agent-internal level (each agent contains mini-OPERATOR, mini-WITNESS, etc.) or only at swarm level? If agent-level, `AgentViability`'s 5 floats map directly to S1–S5 sub-agents inside each agent — a micro-swarm. The synthesis must decide the recursion boundary.

2. **Beer + Friston on S3/S4 tension**: The `ACTIVE_INFERENCE` axiom (Friston) and the S3/S4 tension (Beer) describe the same optimize-vs-explore dynamic from different angles. Does the v3 Core Four need a single `explorationPressure` field on `AgentIdentity` or `Task` that both axioms gate? Or do they remain independent checks? Composition or competition?

3. **Algedonic memory authority**: The `[CDS]` table has 7 memory write surfaces. Should the AlgedonicChannel be an 8th — Write class, owner `vsm_channels.AlgedonicChannel`, write API `fire()`, forbidden bypass: write to algedonic.jsonl directly? Or should algedonic signals be routed through `RuntimeStateStore.record_memory_fact()` with `fact_kind="algedonic"` and `truth_state="urgent"`? This requires a cross-pillar decision because it touches both Beer (channel integrity) and Varela (operational closure of the memory boundary).

4. **Beer + Kauffman on S1 operations**: Kauffman's autocatalytic sets provide the mathematical basis for S1 (the pillar says so explicitly at `PILLAR_11_BEER.md:249–253`). The `CatalyticGraph` (`catalytic_graph.py`) implements this. Does `Task.vsm_system = "S1"` need a `catalytic_node_id: str | None` field that links each task into the autocatalytic graph? Or does that over-tighten a connection that should remain emergent?

5. **VarietyExpansionProtocol duplication**: `vsm_channels.VarietyExpansionProtocol` and `telos_gates.GateRegistry` are two independently-implemented gate expansion systems with nearly identical semantics. Both propose gates, both require S5 approval, both persist to `~/.dharma/meta/`. They differ in data shape (`GateExpansionProposal` vs `GateProposal`) and write path. The synthesis must decide: consolidate into one, or clarify distinct scopes (vsm_channels for reactive variety expansion from zeitgeist; telos_gates for deliberate governance expansion)?

---

## 7. Tools Used + Tier Compliance

| Tier | Tool | Used for |
|---|---|---|
| 5 (Read) | Direct file reads | Template, v2 blueprint (sections), PILLAR_11_BEER.md, dharma_kernel.py:1–350, vsm_channels.py (full), telos_gates.py:1–130, models.py:40–170 |
| 6 (Bash/grep) | `grep -n` on models.py and telos_gates.py | Located AgentRole enum line numbers and GateProposal/GateRegistry class locations |

Tier 1 (memory MCP) and Tier 2 (wiki CLI) skipped with justification: the task is a first-instance extraction from primary source files, not a retrieval of prior session knowledge. The constitutional role → VSM mapping is not in the memory graph (it needs to be written there as a conclusion of this session, not retrieved). Tier 3–4 (contextplus, gitnexus) skipped because the working directory is `dharma_swarm_integrate_chetana`, not `dharma_swarm`, and the gitnexus index is read-only in this context (FTS errors observed in PreToolUse hook output). Direct reads from the cited primary files are more reliable here.

---

Co-Authored-By: Claude Sonnet 4.6 (pillar-11-beer subagent) <noreply@anthropic.com>
Dispatched-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
Master-prompt: ~/.claude/plans/CORE_FOUR_FULL_PICTURE_MASTER_PROMPT.md
