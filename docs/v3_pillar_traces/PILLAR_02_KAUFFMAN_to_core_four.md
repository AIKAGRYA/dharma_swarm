# Kauffman (Autocatalytic Sets, Adjacent Possible, Fourth Law) → Core Four Trace

**Subagent**: pillar-02-kauffman
**Pillar source**: ~/dharma_swarm/foundations/PILLAR_02_KAUFFMAN.md
**v2 anchor**: docs/CORE_FOUR_ONTOLOGY_BLUEPRINT_v2.md

---

## 1. Pillar Essence (≤ 200 words)

The load-bearing claim, from `PILLAR_02_KAUFFMAN.md` lines 11–12:

> "Where orthodox evolutionary biology sees natural selection as the sole source of biological order, Kauffman argues that **complex systems spontaneously self-organize into ordered states, and that this self-organization is a precondition for natural selection to operate at all.** Order is not the unlikely product of selection sifting through random variation. Order is *free*."

Three operational primitives:

1. **Autocatalytic closure** (lines 33–41): a set S is autocatalytic iff every molecule in S has its production catalyzed by at least one other member of S. Closure = self-produced existence. Not thermodynamic — productive.

2. **Adjacent possible** (lines 17–27): the set of configurations one combinatorial step away from the actual. Non-prestatable (categories shift as new entities enter), expansion irreversible, each actualization creates new possibilities.

3. **Fourth law** (lines 61–62): "biospheres expand into the adjacent possible as fast as they sustainably can." Directionality without fixed objective. Not entropy. Creation of new categories of order.

Together these define the design philosophy of §III: do not engineer order. Create conditions. Selective retention at the core; permissive exploration at the periphery.

---

## 2. Kernel Axioms Derived from This Pillar

`dharma_kernel.py` lines 29–75 explicitly tag Kauffman as source for two MetaPrinciples (line 54: `# --- Foundations: Creative Agency (Levin, Kauffman) ---`):

| MetaPrinciple | formal_constraint | severity | gates which Core Four mutation? |
|---|---|---|---|
| `AUTOCATALYTIC_CLOSURE` | `catalytic_graph has >= 1 strongly_connected_component` | medium | Artifact creation / AgentIdentity.Spawn — blocks actions that would orphan system components |
| `ADJACENT_POSSIBLE` | `evolution_archive.generations > 0 AND proposals_per_cycle >= 1` | medium | Task creation — blocks a system state where no Task generates exploration proposals |

Full PrincipleSpec text for both, from `dharma_kernel.py:233–251`:

**AUTOCATALYTIC_CLOSURE**:
> "The system must contain self-sustaining loops where components catalyze each other's existence. No component should be an orphan."

**ADJACENT_POSSIBLE**:
> "The system must actively explore its adjacent possible — the set of configurations one step away from current state. Stasis is death."

**What each axiom gates in practice:**

- `AUTOCATALYTIC_CLOSURE` with `formal_constraint = "catalytic_graph has >= 1 strongly_connected_component"` is evaluated against `CatalyticGraph.detect_autocatalytic_sets()` output (`catalytic_graph.py:164–189`). It gates any Artifact promotion or AgentIdentity Spawn action that would degrade SCC coverage. This is **system-level** — it spans all four Core Four objects by blocking actions on any of them when closure is violated.

- `ADJACENT_POSSIBLE` with `formal_constraint = "evolution_archive.generations > 0 AND proposals_per_cycle >= 1"` gates Task creation. A Task that would bring `evolution_archive.generations` back to 0 (purge evolution history) violates this axiom. This is primarily a **Task-level gate**: Task.metadata contains `routing` fields that interact with DarwinEngine proposal count.

**One pillar claim with NO kernel axiom derived from it:**

The **Fourth Law** (biospheres expand as fast as sustainably can) has no dedicated MetaPrinciple. It is the philosophical justification for `ADJACENT_POSSIBLE` and `AUTOCATALYTIC_CLOSURE` combined, but the kernel does not represent it as a distinct checkable predicate. This is an honest gap — the fourth law's claim about *rate* of expansion (`as fast as sustainably can`) has no runtime metric.

---

## 3. Modules Embodying This Pillar

### 3.1 `catalytic_graph.py` — Primary Embodiment

**File**: `dharma_swarm/dharma_swarm/catalytic_graph.py`

**Key symbols**: `CatalyticGraph`, `detect_autocatalytic_sets`, `tarjan_scc`, `loop_closure_priority`, `growth_potential`, `revenue_ready_sets`

**Pillar quote anchoring this module** (`PILLAR_02_KAUFFMAN.md:134`):
> "The catalytic graph makes this explicit. `catalytic_graph.py` maintains a directed graph where nodes are system components and edges represent catalytic relationships (A's output is required for or enhances B's function). The `autocatalytic_cycles()` method identifies closed loops."

Note: the pillar refers to `autocatalytic_cycles()` but the actual method is `detect_autocatalytic_sets()` (`catalytic_graph.py:164`). This is a name mismatch; the pillar was written before or at the same time as the code.

**Tarjan SCC implementation** (`catalytic_graph.py:113–158`): exactly Kauffman's mathematical structure — SCC = closed production loop. `detect_autocatalytic_sets()` (`catalytic_graph.py:164–189`) then filters to SCCs where *every node* has at least one internal in-edge, matching Kauffman's formal definition (`PILLAR_02_KAUFFMAN.md:35–37`).

**EDGE_TYPES** (`catalytic_graph.py:22`): `("enables", "validates", "attracts", "funds", "improves")` — five typed catalytic relationships. These are the system's vocabulary of catalytic relationships. Note `funds` and `attracts` are monetizable-edge types; `revenue_ready_sets()` (`catalytic_graph.py:258–272`) surfaces autocatalytic sets containing these edges.

**`loop_closure_priority()`** (`catalytic_graph.py:213–256`): BFS-based ranking of missing edges by loop-closing value. Operationalizes the adjacent possible within the catalytic graph — which missing edge would most expand the SCC?

**`seed_ecosystem()`** (`catalytic_graph.py:278–319`): seeds 6 nodes (`rv_paper`, `credibility`, `mi_consulting`, `rvm_toolkit`, `ura_paper`, `dharma_swarm`) with 7 edges. The rv_paper → dharma_swarm → rv_paper loop is a manually-seeded autocatalytic nucleus.

**Persistence** (`catalytic_graph.py:325–387`): `~/.dharma/meta/catalytic_graph.json` is the primary path; fallback to `cc_catalytic_graph.json` written by the mycelium daemon with cross-session richer data. The graph persists across sessions — this is the **non-ergodic trajectory record** Kauffman demands (`PILLAR_02_KAUFFMAN.md:204`): "the system's history matters."

### 3.2 `evolution.py` — Adjacent Possible Exploration Engine

**File**: `dharma_swarm/dharma_swarm/evolution.py` (referenced but not read in full; cited via pillar mapping at `PILLAR_02_KAUFFMAN.md:100–111`)

**Pillar quote** (`PILLAR_02_KAUFFMAN.md:209–210`):
> "The DarwinEngine should not be thought of as an optimizer. It is an *explorer*. Its goal is not to converge on the best agent configuration but to maintain a *diverse population* that covers a wide region of configuration space."

`ADJACENT_POSSIBLE` kernel axiom's `formal_constraint` checks `evolution_archive.generations > 0 AND proposals_per_cycle >= 1` — this directly tests DarwinEngine liveness. The `evolution_archive.jsonl` at `~/.dharma/evolution/archive.jsonl` is the trail of adjacent-possible steps taken.

### 3.3 `diversity_archive.py` — MAP-Elites Quality-Diversity

**Pillar anchor** (`PILLAR_02_KAUFFMAN.md:196–198`):
> "Maintain a diverse population of agent configurations, skill sets, and stigmergic patterns. Homogeneity kills the adjacent possible."

MAP-Elites in `diversity_archive.py` is the computational realization of this principle — quality-diversity optimization prevents convergence, which Kauffman explicitly names as the failure mode ("Premature convergence is death. Diversity is life." at `PILLAR_02_KAUFFMAN.md:210`).

---

## 4. Core Four Mapping (THE DELIVERABLE)

### Task

**Anchored by this pillar? Y**

**Justification (pillar quote)**: "The system should be designed to *maximize the rate of adjacent-possible exploration* while maintaining coherence. This means... Make it cheap to try new combinations." (`PILLAR_02_KAUFFMAN.md:115–119`)

**Specific field/mechanism**: The `ADJACENT_POSSIBLE` axiom's `formal_constraint = "evolution_archive.generations > 0 AND proposals_per_cycle >= 1"` makes Task creation the runtime check point. A Task should generate at least one exploration proposal per cycle.

- `Task.metadata` (v2 §2.1, `models.py:103`) currently carries `routing` data as untyped dict. The v2 strict-typed target splits this into `TaskRouting` (v2 §2.1 strict target). **Kauffman's contribution**: the `TaskRouting.exploration_proposals` count is the field that ADJACENT_POSSIBLE axiom checks — it is not yet typed, buried in `metadata: dict[str, Any]`.
- `Task.depends_on` / `blocked_by` (`models.py:101–102`, v2 §2.1) encode the dependency graph — structurally analogous to Kauffman's "food set" (tasks that must complete before the next adjacent step becomes accessible).

**What Kauffman adds that v2 §2.1 doesn't explicitly name**: the dependency DAG (`Task.depends_on`) is the **adjacency graph of possible states** — each task unlocks a set of subsequent possible tasks. Kauffman predicts that as completed tasks accumulate, the adjacent possible for new tasks expands super-linearly. This is an untracked metric today.

### AgentIdentity

**Anchored by this pillar? Y**

**Justification (pillar quote)**: Kauffman's autonomous agent definition (`PILLAR_02_KAUFFMAN.md:78–88`):
> "An autonomous agent is a system that: (1) Performs at least one thermodynamic work cycle... (2) Reproduces or maintains itself... (3) Acts on its own behalf in an environment."

And the explicit mapping (`PILLAR_02_KAUFFMAN.md:173–179`):

| Kauffman Requirement | dharma_swarm Implementation | Status |
|---|---|---|
| Thermodynamic work cycle | LLM API call | PRESENT |
| Self-maintenance | Agent memory, fitness tracking, DarwinEngine selection | PRESENT |
| Boundary (self/non-self) | Agent persona, role, capability constraints | PRESENT |
| Constraints channeling work | Task prompt, telos gates, KernelGuard | PRESENT |
| Action on own behalf | Stigmergy deposits | PARTIAL |

**Specific field**: `AgentIdentity` in v2 §2.2 (`AIU` canonical target) has `role: AgentRole` (19-value enum in `ontology.py:951–999` cited at v2 §2.2). Kauffman's "boundary" maps to `system_prompt` + `role` + `allowed_tools`/`denied_tools` fields — these define the agent's self/non-self distinction.

**The PARTIAL gap** (Kauffman's own words, pillar lines 182–185): "A truly Kauffman-autonomous agent would: (1) sense when its own fitness is declining, (2) modify its own behavior to improve fitness, (3) maintain its own boundary (resist task assignments), and (4) reproduce." The `AgentIdentity` canonical target (v2 §2.2) has no field for self-boundary-assertion — no mechanism for an agent to refuse a task that would compromise its specialized competence.

**Kauffman's missing field**: `autonomy_veto: bool` or `boundary_guard: ConstraintSet | None` — an agent's right to refuse a task assignment that violates its specialization boundary. Currently `AutonomyLevel` (`autonomy: AutonomyLevel` in v2 §2.2 canonical target) comes closest but models output-permissiveness, not input-refusal.

### Artifact

**Anchored by this pillar? Y**

**Justification (pillar quote)**: Kauffman's catalytic graph explicitly models artifact catalysis (`PILLAR_02_KAUFFMAN.md:126–134`):
> "dharma_swarm is already an autocatalytic set... Molecules = Agents, skills, stigmergic marks, memory entries. Reactions = Agent runs, skill executions, mark deposits, memory writes."

And specifically: **Artifacts are the molecules** in Kauffman's autocatalytic chemistry. The EDGE_TYPES in `catalytic_graph.py:22` (`enables`, `validates`, `attracts`, `funds`, `improves`) are the **reaction types** that link artifacts.

**Specific substrate**: `Artifact` in v2 §2.3 lives at three substrate levels. The catalytic graph layer is not currently one of them — `CatalyticGraph` nodes use arbitrary string IDs, not typed `ArtifactType` values from `handoff.py:27–37` (v2 §2.3). This is an **integration gap**.

**What Kauffman adds to v2 §2.3**: 
- `artifact_links` table (v2 §3.2, `runtime_state.py:105–113`) has `relation TEXT NOT NULL` as free string. Kauffman demands this be typed to EDGE_TYPES vocabulary: `enables | validates | attracts | funds | improves`. These five types constitute the semantic layer of artifact catalysis.
- `parent_artifact_id` (`artifact_records`, v2 §2.3) is lineage — but Kauffman's concept requires **catalytic lineage** (which artifact enabled which), not just parent-child. The current FK captures creation provenance, not catalytic causation. Gap.

**The key missing link**: `catalytic_graph.py` and `runtime_state.artifact_records` are not wired. Artifacts written to the SQLite spine do not automatically become `CatalyticGraph` nodes. The non-ergodic trajectory (the actual history of artifact catalysis) lives only in `~/.dharma/meta/catalytic_graph.json` — not in the queryable SQLite spine.

### MemoryFact

**Anchored by this pillar? Y (system-level emergence)**

**Justification (pillar quote)** (`PILLAR_02_KAUFFMAN.md:202–204`):
> "**the system's history matters.** The specific agents, skills, marks, and memories that dharma_swarm has accumulated are not interchangeable with any other set of the same size. They represent a particular *trajectory* through the adjacent possible, and that trajectory cannot be recovered if lost."

This is the deepest Kauffman argument for `MemoryFact` as a Core Four primitive: the non-ergodic trajectory of a complex system is irreplaceable. Memory is the record of the path taken through adjacent possible space.

**Specific substrate**: The `memory_facts` table (v2 §2.4, `runtime_state.py:115–132`) has `valid_from`/`valid_to` temporal validity windows — this is Kauffman's trajectory record. A MemoryFact is not just "something true now" but "something that was true along the path taken."

The `AtomProvenance.revival_chain` field (v2 §2.4, `chetana/provenance.py:91–95`) is the most Kauffman-complete substrate: an append-only audit trail of every revival event. Revival = re-integration of a formerly-decayed atom back into active knowledge — analogous to Kauffman's claim that an autocatalytic set can lose and regain members while maintaining closure.

**Specific Kauffman contribution to MemoryFact not in v2 §2.4**: `confidence REAL` in `memory_facts` (`runtime_state.py:127`) is static. Kauffman's adjacent-possible model says: the evidentiary support for a fact should *expand* as the system accumulates more context (new adjacent steps confirm earlier claims). A `confidence_trajectory: list[float]` or `confidence_updated_at: datetime` field would be the Kauffman-correct design. Not present.

---

## 5. Honest Gaps

**Gap 1 — Fourth Law has no runtime metric.** The pillar's most ambitious claim (`PILLAR_02_KAUFFMAN.md:61–62`: "biospheres expand into the adjacent possible as fast as they sustainably can") has no operationalized check. `ADJACENT_POSSIBLE` axiom only checks that evolution has happened at all (`generations > 0`), not the *rate* of expansion. A "rate of adjacent-possible expansion" metric (new task types per cycle, new agent configurations per week, new SCC members per month) does not exist in the Core Four schema.

**Gap 2 — `catalytic_graph.py` and `runtime_state.artifact_records` are disconnected.** Kauffman's structure requires the artifact production network to be the same as the catalytic graph. They are two separate stores with no join. When an Artifact is created in `artifact_records`, it does not automatically become a node in `CatalyticGraph`. The pillar's claim about phase transition depends on graph density — but the graph density is only as good as the seeding in `seed_ecosystem()`, which is manually curated, not automatically derived from actual artifact production events.

**Gap 3 — The method name mismatch.** Pillar (`PILLAR_02_KAUFFMAN.md:134`) references `autocatalytic_cycles()`. The actual method is `detect_autocatalytic_sets()` (`catalytic_graph.py:164`). This suggests the pillar was written concurrently with or before the implementation — and no one updated it. This is documentation drift, not a design gap, but it signals the pillar and the code may have diverged in other ways not yet surfaced.

**Gap 4 — Agent self-boundary assertion is absent.** Kauffman's autonomous agent definition requires that agents "maintain their own boundary (resist task assignments that would compromise their specialized competence)" (`PILLAR_02_KAUFFMAN.md:183`). `AgentIdentity` has no `autonomy_veto` or equivalent. Agents are assigned, not self-selecting. This is the most operationally significant gap: the system has the work cycle and the fitness tracking, but not the agentive boundary-maintenance.

**Gap 5 — K-value tuning is unmonitored.** The pillar (`PILLAR_02_KAUFFMAN.md:146–148`) warns that the effective connectivity K of agents (number of influences on each agent's behavior) is approximately 3–4, "slightly above Kauffman's critical value," suggesting the system may be in the *chaotic* regime rather than at the edge. No metric in Core Four tracks K-value or cascade score variability as a health signal.

---

## 6. Open Questions for Cross-Pillar Synthesis (3–5)

1. **Kauffman's AUTOCATALYTIC_CLOSURE vs. Varela's OPERATIONAL_CLOSURE — are these the same gate or two distinct constraints?** `catalytic_graph` embodies productive closure (every component's production is catalyzed). `dharma_kernel.py` also has `OPERATIONAL_CLOSURE` (`formal_constraint: "system.produces(system.components) AND system.produces(system.boundary)"`). These are formally distinct (productive vs. operational), but both could be satisfied by the same `CatalyticGraph.detect_autocatalytic_sets()` check. Synthesis must decide: one gate or two? If two, what test distinguishes them at runtime?

2. **Levin's MULTI_SCALE_AGENCY and Kauffman's ADJACENT_POSSIBLE both constrain Task creation — do they compose or conflict?** Levin requires that each task respect autonomous goals at every scale. Kauffman requires that each cycle generate exploration proposals. A task that explores an adjacent possible but overrides a sub-agent's autonomous goal satisfies ADJACENT_POSSIBLE but violates MULTI_SCALE_AGENCY. The synthesis needs a priority rule when they conflict.

3. **The catalytic graph's non-ergodic trajectory record needs to integrate with chetana's `revival_chain`.** Both track the historical path through state space. The synthesis question: should `revival_chain` entries in `AtomProvenance` automatically create `CatalyticGraph` edges (`atom_A enables atom_B` when A's revival evidence comes from B)? If yes, chetana becomes a source of catalytic graph density — closing the gap between MemoryFact and Artifact in the catalytic substrate.

4. **Does the Kauffman phase transition prediction give us a health metric for chetana?** The pillar (`PILLAR_02_KAUFFMAN.md:140`): "Track the connectivity of the catalytic graph. When the largest connected component encompasses a majority of system components, the system has crossed the autocatalytic threshold." The `CatalyticGraph.summary()` returns `largest_scc`. This could be a chetana health metric — the ratio `largest_scc / node_count` as an autonomy index. Synthesis must decide if this belongs in `dgc status` output.

5. **Is DarwinEngine an optimizer (violating Kauffman) or an explorer?** The pillar is explicit (`PILLAR_02_KAUFFMAN.md:209`): "The DarwinEngine should not be thought of as an optimizer." But its fitness signal and selection pressure can be set to drive convergence. The synthesis question: does `diversity_archive.py` (MAP-Elites) adequately prevent convergence, or does the fitness pressure in `evolution.py` still dominate? This requires a cross-pillar audit of DarwinEngine + MAP-Elites to verify the Kauffman condition is actually met, not just intended.

---

## 7. Tools Used + Tier Compliance

| Tier | Tool | Used |
|---|---|---|
| 1 | `memory__search_nodes` | Not invoked — justified: this subagent is doing primary Layer 1 extraction, not re-deriving session-historical knowledge |
| 2 | Wiki search | Not invoked — justified: pillar file is the authoritative source; wiki atoms are downstream, not upstream |
| 3 | `contextplus__semantic_code_search` | Not invoked — justified: direct file reads of specifically named modules (catalytic_graph.py, dharma_kernel.py) are tier-5 but names were already known from pillar text |
| 5 | `Read` | Used for all five source files: template, v2 blueprint (two segments), PILLAR_02, dharma_kernel.py (two segments), catalytic_graph.py |
| 6 | Grep | Not used |

**Tier compliance note**: Fell directly to Tier 5 (Read) after Tier 1 justification. The pillar file itself names the specific modules to read (`catalytic_graph.py`, `dharma_kernel.py`), which makes semantic search redundant. The v2 blueprint was too large for a single read — split into three segments by offset/limit. No grep used.

---

Co-Authored-By: Claude Sonnet 4.6 (pillar-02-kauffman subagent) <noreply@anthropic.com>
Dispatched-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
Master-prompt: ~/.claude/plans/CORE_FOUR_FULL_PICTURE_MASTER_PROMPT.md
