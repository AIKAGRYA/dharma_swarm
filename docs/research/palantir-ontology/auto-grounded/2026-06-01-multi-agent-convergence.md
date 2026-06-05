# Multi-Agent Ontology Convergence: Adversarial Research Report

**Date:** 2026-06-01  
**Scope:** CRDT applicability, KARMA (NeurIPS 2025) deep analysis, semantic 3-way merge, production systems, formal decidability, and gap analysis of dharma_swarm's schema-alignment gate (PR #408)  
**Author:** perplexity-computer  
**Posture:** Challenge, do not validate. External research first, internal assumptions last.

---

## Context

dharma_swarm runs five AI agents — claude, devin, hermes, mike, perplexity — concurrently proposing additions of `ObjectType`, `LinkDef`, and `ActionDef` nodes to a shared `OntologyRegistry` defined in `dharma_swarm/ontology.py`. The project's current governance mechanism is a static pre-merge CI gate (`scripts/governance/check_ontology_alignment.py`, PR #408) that detects syntactic collisions between open pull requests. Palantir's Foundry, the closest commercial analogue, uses a **single forward-deployed engineer plus a centralized Ontology Metadata Service** to avoid concurrent conflicts entirely — a model that explicitly does not generalize to multi-agent concurrent editing. Concurrent ontology editing at the level of semantics (not just names) is, as of 2026, an open research problem with no widely-deployed solution in industry or academia.

---

## What KARMA Actually Does

**Paper:** Yuxing Lu, Wei Wu, Xukai Zhao, Rui Peng, Jinzhuo Wang. "KARMA: Leveraging Multi-Agent LLMs for Automated Knowledge Graph Enrichment." NeurIPS 2025 Spotlight. arXiv:2502.06472. [https://arxiv.org/abs/2502.06472](https://arxiv.org/abs/2502.06472)

### Architecture

KARMA is a **hierarchical multi-agent LLM pipeline** for enriching an *existing* knowledge graph (KG) from unstructured biomedical text. It deploys nine specialized agents under a Central Controller Agent (CCA): Reader, Summarizer, Entity Extraction, Entity Disambiguation, Relationship Extraction, Schema Alignment (SAA), Conflict Resolution (CRA), and two Evaluator Agents.

### Exact Mechanism of Schema Alignment (SAA)

The Schema Alignment Agent performs an **LLM-based probabilistic classification** of newly extracted entities and relations against a fixed, pre-defined set of valid types \(\mathcal{T}\) (Disease, Drug, Gene, etc.):

\[
\tau^{*} = \arg\max_{\tau \in \mathcal{T}} \, \mathrm{LLM}_{\mathrm{SAA}}(v, \tau, P_{\mathrm{align}})
\]

If no suitable type match exists, the SAA **flags the candidate for human review** — it does not create a new type autonomously. This is a **pre-merge alignment gate**, not a runtime reconciler.

### Exact Mechanism of Conflict Resolution (CRA)

The CRA checks newly extracted triplets against existing KG relationships. When a new triplet \(t\) is logically incompatible with an existing triplet \(t'\):

\[
\mathrm{LLM}_{\mathrm{CRA}}(t, t') \to \{\texttt{Agree}, \texttt{Contradict}\}
\]

If `Contradict`, the triplet is **discarded or queued for expert review**. This is also a **pre-merge gate with LLM-based debate**, not a learned policy that directly modifies the graph.

### Measured Claims vs. Speculation

**Measured (reported in the paper):**
- Up to 38,230 new entities extracted from 1,200 PubMed articles across 3 biomedical domains
- 83.1% LLM-verified correctness (DeepSeek-v3 backbone, genomics domain)
- 18.6% reduction in conflict edges vs. baseline (conflict ratio \(R_{CR} = 0.186\) for DeepSeek-v3/genomics)
- Ablation: removing the CRA reduces LLM correctness from 0.831 → 0.790 in genomics (−4.9%)
- Metabolomics shows 12.4–11.9% lower QA coherence than other domains

**What the paper does NOT prove:**
- It does not evaluate concurrent multi-agent schema proposal scenarios where two agents simultaneously propose *different schemas for the same type name* — KARMA's SAA only classifies against a fixed schema; it does not merge competing schema definitions
- The "conflict resolution" is triplet-level, not schema-level — it detects contradictory facts, not contradictory type definitions
- Evaluation uses LLM-based metrics, not independent human expert validation at scale; the authors explicitly acknowledge this limitation
- The system does not handle namespace conflicts, cardinality disagreements between agents, or ontology evolution over time
- It is a pipeline architecture, not a consensus protocol — agents do not negotiate; the CCA serially assigns tasks

### What KARMA Solves vs. dharma_swarm's Problem

| Dimension | KARMA | dharma_swarm |
|---|---|---|
| Domain | Fixed biomedical KG schema | Open, evolving property-graph schema |
| Conflict type | Factual triplet contradictions | Schema-level type/link/action definition collisions |
| Resolution mechanism | Discard or human review | Deterministic merge or human arbitration |
| Concurrency model | Sequential pipeline under CCA | Truly concurrent PRs from 5 agents |
| Schema mutability | Fixed schema, agents enrich ABox | Schema is itself the thing being modified (TBox evolution) |

**Conclusion:** KARMA solves a different problem. The check_ontology_alignment.py gate citing KARMA as its model is **a conceptual mismatch**. KARMA's SAA classifies against a fixed schema; dharma_swarm's problem is that the schema itself is the contested object. No published multi-agent system has solved TBox-level concurrent ontology evolution with automatic convergence guarantees.

---

## CRDT Applicability to Ontology

### The CRDT Foundation

The foundational result is Shapiro, Preguiça, Baquero, and Zawirski (2011), "Conflict-free Replicated Data Types," *Symposium on Self-Stabilizing Systems*, Springer LNCS 6976, pp. 386–400 ([https://pages.lip6.fr/Marc.Shapiro/papers/CRDTs_SSS-2011.pdf](https://pages.lip6.fr/Marc.Shapiro/papers/CRDTs_SSS-2011.pdf)). The core guarantee is **Strong Eventual Consistency (SEC)**: replicas that have delivered the same updates converge to the same state deterministically, without coordination. This is achieved by ensuring operations are **commutative** (op-based CRDTs) or that state merge is a **join-semilattice** (state-based CRDTs). A survey of the landscape is provided by Preguiça, Baquero, and Shapiro (2018), arXiv:1805.06358 ([https://arxiv.org/abs/1805.06358](https://arxiv.org/abs/1805.06358)).

### CRDTs for JSON: The Closest Analogue

Kleppmann and Beresford (2017), "A Conflict-Free Replicated JSON Datatype," *IEEE Transactions on Parallel and Distributed Systems* 28(10):2733–2746, arXiv:1608.03960 ([https://arxiv.org/abs/1608.03960](https://arxiv.org/abs/1608.03960)), extended CRDTs to arbitrarily nested JSON maps and lists. Their key contribution: concurrent modifications to different branches of a JSON tree can always be merged. **However**, their system uses a **multi-value register** for leaf-node conflicts — when two agents write different values to the same leaf, *both* values are retained until the application resolves the ambiguity. This is explicitly not conflict-free at the application layer; the JSON structure converges, but the application may receive an invalid state (a field that is simultaneously a string and a list, for example). The authors acknowledge this and note that garbage collection (tombstone removal) is required for production use.

### Why CRDTs Are Hard for Typed Schemas

Schemas are not general-purpose JSON. A dharma_swarm `ObjectType` carries **semantic constraints**: property types, link cardinalities, security policies, status lifecycles, and a `telos_alignment` float. These constraints interact non-monotonically:

1. **Type constraints are not monotone.** Adding a property to type A and simultaneously removing it from type A in two concurrent branches cannot be merged by a grow-only set (G-Set) — one operation must win. Standard add-wins or remove-wins semantics (discussed in Zhang, Wei, and Huang 2022, "Remove-Win: a Design Framework for CRDTs," arXiv:1905.01403, [https://arxiv.org/abs/1905.01403](https://arxiv.org/abs/1905.01403)) can be applied locally, but choosing add-wins vs. remove-wins for schema properties has downstream semantic consequences that cannot be resolved by the data structure alone.

2. **Cardinality constraints are not composable.** If agent A proposes `ONE_TO_MANY` for a `LinkDef` and agent B proposes `MANY_TO_ONE` for the same `(source_type, name)` pair, there is no mathematically sound lattice join. The cardinality values are incomparable; one must be discarded. No CRDT design resolves this without application-level knowledge.

3. **Semantic constraints create non-commutativity.** Masson, Syriani, and Dávid (2022), "Extensible Conflict-Free Replicated Datatypes for Real-time Collaborative Software Engineering," *FedCSIS*, DOI:10.15439/2022F99 ([https://annals-csis.org/proceedings/2022/drp/pdf/99.pdf](https://annals-csis.org/proceedings/2022/drp/pdf/99.pdf)), explicitly identified that graph-type CRDTs in model-driven engineering fail when **constraints on types** are involved: the constraint space is not a lattice, and constraint operations do not commute in general.

4. **Namespace conflicts are structurally unresolvable by CRDTs.** Two agents adding `ObjectType(name="Transaction")` with different property sets creates a name collision. CRDTs can store both entries (via a 2P-Set or add-wins set), but this results in two incompatible type definitions under the same name — a semantic inconsistency that no CRDT can resolve because it requires domain knowledge about which definition is "correct."

5. **The CALM theorem limits CRDT applicability.** Laddad et al. (2022), "Keep CALM and CRDT On," arXiv:2210.12605 ([https://arxiv.org/abs/2210.12605](https://arxiv.org/abs/2210.12605)), prove that coordination-free distributed computation is exactly the class of monotone programs (CALM theorem). Schema evolution is inherently non-monotone — deleting a type, restricting a cardinality, or changing a status from `active` back to `experimental` are all non-monotone operations. Any system that permits non-monotone schema evolution *cannot* achieve CRDT-style convergence without coordination.

### What CRDTs Can and Cannot Do for dharma_swarm

**CRDTs CAN handle:**
- Accumulating sets of proposed new type names (grow-only set)
- Tracking which agents have endorsed a proposal (multi-value register)
- Append-only audit logs of proposals

**CRDTs CANNOT handle:**
- Semantic merging of two conflicting cardinality constraints
- Resolving namespace collisions between same-named types with different schemas
- Enforcing type-system invariants across replicas without coordination
- Non-monotone schema operations (deletions, demotions, cardinality restrictions)

The Automerge library (Kleppmann et al., https://automerge.org) and Yjs (https://github.com/yjs/yjs) implement JSON CRDTs in production but both explicitly document that application-level conflicts (semantically invalid states) remain the application's responsibility to detect and resolve. Neither is designed for typed schema registries.

---

## Semantic 3-Way Merge: State of the Art

Git's 3-way merge is textual: it finds a common ancestor and merges line-by-line. For schemas defined in Python files (as in dharma_swarm), Git's merge will produce syntactically valid but semantically invalid Python in the presence of concurrent modifications to the same `ObjectType` constructor call. The state of the art for *semantic* 3-way merge of schemas is as follows:

### OWL Ontology Editors: ContentCVS and WebProtégé

The most rigorous academic work on concurrent OWL ontology development is the ContentCVS system (Jiménez-Ruiz et al., "Supporting Concurrent Ontology Development," *Data & Knowledge Engineering*, 2011, [https://www.cs.ox.ac.uk/isg/tools/ContentCVS/paperDKE-DATAK-1291.pdf](https://www.cs.ox.ac.uk/isg/tools/ContentCVS/paperDKE-DATAK-1291.pdf)). ContentCVS adapts CVS semantics to OWL ontologies with three levels of conflict detection:

1. **Syntactic equivalence** — trivial, ignores ordering differences
2. **Structural equivalence** — OWL-aware, ignores irrelevant structural variations
3. **Semantic equivalence** — uses a DL reasoner to compare logical entailments

ContentCVS found that: (a) detecting deductive differences in SROIQ (OWL 2 Full) is **undecidable**; (b) semantic conflict resolution requires invoking a reasoner, which is computationally expensive; (c) automatic resolution of **lexical conflicts** (two developers independently adding the same concept with different names) is impossible without ontology matching techniques. These findings apply directly to dharma_swarm: detecting whether two independently-proposed `ObjectType` definitions are semantically equivalent requires reasoning about the property-graph semantics of the types, which the current git-diff + AST-parse approach cannot do.

A practical concurrent ontology editor, WebProtégé ([https://pmc.ncbi.nlm.nih.gov/articles/PMC3691821/](https://pmc.ncbi.nlm.nih.gov/articles/PMC3691821/)), uses a client-server architecture with real-time broadcast of changes. Its concurrency model is **last-write-wins on individual axioms** with a change-tracking overlay — not a semantic merge. Users reported duplicate class insertion when two editors added the same class concurrently with no notification after the fact.

A 2024 addition to this toolset is KGCL (Knowledge Graph Change Language), Mungall et al., *Database* (2024), DOI:10.1093/database/baae133 ([https://pmc.ncbi.nlm.nih.gov/articles/PMC11753292/](https://pmc.ncbi.nlm.nih.gov/articles/PMC11753292/)). KGCL provides a standardized data model for *describing* changes to ontologies at a high level — add class, remove property, rename edge — but it does not provide merge semantics. It is a change-description language, not a reconciliation protocol.

### GraphQL Schema Federation

Apollo Federation ([https://www.apollographql.com/docs/graphos/schema-design/federated-schemas/composition](https://www.apollographql.com/docs/graphos/schema-design/federated-schemas/composition)) uses **static composition at build time**: if two subgraphs define the same field with incompatible types, composition fails hard and no supergraph schema is generated. Object types are merged via **union** (all fields from all subgraphs), input types and arguments via **intersection** (only shared fields). Shared fields must have compatible return types across all subgraphs — type mismatches break composition. This is a **fail-fast conflict gate**, not a semantic merge. It catches syntactic incompatibilities but does not reason about semantic intent. This is structurally similar to dharma_swarm's ALIGN-004 check, but more systematic about union/intersection semantics.

**Known limit:** Apollo Federation's composition does not handle cases where two subgraphs define the same type name with semantically equivalent but syntactically different structures. It also does not handle concurrent proposals from autonomous agents — it assumes human-authored subgraph schemas submitted to a central schema registry.

### dbt Merge Conflicts

dbt's conflict resolution is entirely textual (standard Git merge), with no schema-level semantics. Its documentation ([https://docs.getdbt.com/docs/platform/git/merge-conflicts](https://docs.getdbt.com/docs/platform/git/merge-conflicts)) describes line-level conflict markers that must be resolved manually. Schema evolution in dbt relies on **backward-compatibility conventions** (adding columns is safe, dropping is not) enforced by convention and CI checks, not automated semantic merge.

### Ontology Merging Research: Algebraic Approaches

Guo et al. (2022), "Merging Ontologies Algebraically," arXiv:2208.08715 ([https://arxiv.org/abs/2208.08715](https://arxiv.org/abs/2208.08715)), defines ontology merging systems with properties of **idempotence (I), commutativity (C), associativity (A), and representativity (R)**. A merge operator satisfying ICAR is a good candidate for automated merging. However, the paper shows that satisfying all four simultaneously is non-trivial and depends on the expressivity of the ontology language. For property graphs with typed links and cardinality constraints (as in dharma_swarm), no off-the-shelf ICAR merge operator exists.

Babalou and König-Ries (2020), "Towards Building Knowledge by Merging Multiple Ontologies with CoMerger," arXiv:2005.02659 ([https://arxiv.org/abs/2005.02659](https://arxiv.org/abs/2005.02659)), presents a partitioning-based approach for merging multiple OWL ontologies. It handles binary merges and extends to n-ary by iterating. Key limitation: it assumes ontologies have been **aligned** (matched) before merging, which requires solving the ontology alignment problem — itself an unsolved general problem.

Keet and Grütter (2021), "Toward a systematic conflict resolution framework for ontologies," *Journal of Biomedical Semantics* ([https://pmc.ncbi.nlm.nih.gov/articles/PMC8352153/](https://pmc.ncbi.nlm.nih.gov/articles/PMC8352153/)), catalog common modeling conflicts in OWL ontologies and propose a library of resolution strategies. They identify that some conflicts require **meaning negotiation** — human consensus on domain semantics — before automated resolution is possible. This is directly applicable to dharma_swarm: when two agents propose incompatible `telos_alignment` scores for the same type, no algorithm can resolve this without domain-level judgment.

---

## Production Multi-Agent Ontology Systems

| System | Mechanism | Strength | Known Limit | Source |
|---|---|---|---|---|
| **Palantir Foundry Ontology Manager** | Single forward-deployed engineer + centralized OMS; PR-based changes with human review; recently added PR support for schema evolution | Single point of authority eliminates concurrent conflicts; deeply integrated with object storage and action execution | Explicitly does NOT scale to multi-agent concurrent editing; historically required manual edit with page reload after each change; "ClickOps" model; no automatic semantic merge | [Palantir Community AMA (2025)](https://community.palantir.com/t/ama-learn-from-the-ontology-manager-team/5100) |
| **LinkedIn DataHub** | Stream-based metadata platform using Kafka for change events (MetadataChangeProposal/MetadataChangeLog); Aspect versioning with monotonically increasing version numbers; schema stored in PDL (Pegasus Data Language) with Avro | Decoupled producers/consumers; streaming metadata changes with eventual consistency; supports schema evolution via aspect versioning | Last-write-wins on aspect updates; no semantic merge; concurrent writes to the same aspect produce a race condition resolved by wall-clock time; no multi-agent proposal negotiation | [DataHub Engineering Blog (2020)](https://www.linkedin.com/blog/engineering/data-management/datahub-popular-metadata-architectures-explained) |
| **Apollo Federation** | Static composition at build time; union/intersection merge rules for type fields; composition fails hard on type mismatches | Catches breaking changes early; clear merge semantics for fields (union for objects, intersection for inputs) | Pre-merge gate only; no runtime reconciliation; does not handle semantic equivalence; human-authored schemas assumed | [Apollo Federation Docs](https://www.apollographql.com/docs/graphos/schema-design/federated-schemas/composition) |
| **Confluent Schema Registry** | Compatibility mode enforcement (FULL, BACKWARD, FORWARD) on Avro/JSON/Protobuf schemas; version history; automated compatibility checks | Prevents breaking changes; clear compatibility semantics | No concurrent conflict resolution — schema must be submitted serially; incompatible concurrent submissions produce a rejection | [Confluent Schema Evolution Docs](https://docs.confluent.io/cloud/current/flink/concepts/schema-statement-evolution.html) |
| **WebProtégé** | Client-server OWL editor with real-time change broadcast; last-write-wins on individual axioms; change tracking overlay | Real-time visibility of concurrent edits; change history | Duplicate class insertion when two users add the same class concurrently; no semantic merge; conflict notification happens after-the-fact | [Horridge et al. 2013, PMC3691821](https://pmc.ncbi.nlm.nih.gov/articles/PMC3691821/) |
| **ContentCVS** | OWL-aware CVS adaptation; structural equivalence for conflict detection; reasoner-based semantic diff | Most theoretically rigorous concurrent OWL editing system; distinguishes structural vs. semantic conflicts | Semantic conflict detection is undecidable for SROIQ (OWL 2); requires external reasoner (expensive); no automatic resolution of lexical conflicts; academic prototype, not production | [Jiménez-Ruiz et al. 2011, Oxford](https://www.cs.ox.ac.uk/isg/tools/ContentCVS/paperDKE-DATAK-1291.pdf) |
| **KGCL (OBO Foundry)** | Standardized change description language for ontology modifications; machine-readable change events | Enables systematic tracking and communication of ontology changes | Change description only; no merge semantics; does not resolve concurrent conflicting changes | [Mungall et al. 2024, Database](https://pmc.ncbi.nlm.nih.gov/articles/PMC11753292/) |

**Summary finding:** No production system in 2026 provides automatic semantic merge of concurrent schema proposals from multiple autonomous agents. All production systems either (a) enforce serialization (single authority), (b) use fail-fast gates (Apollo), or (c) defer to human resolution (Palantir, WebProtégé, DataHub). The multi-agent autonomous concurrent editing problem is solved in practice by avoiding it, not by solving it.

---

## Theoretical Decidability

### The AGM Framework

The foundational work on rational belief revision is Alchourrón, Gärdenfors, and Makinson (AGM), "On the Logic of Theory Change: Partial Meet Contraction and Revision Functions," *Journal of Symbolic Logic* 50(2):510–530, 1985. The AGM postulates define what a *rational* revision of a belief set K by a new belief \(\alpha\) must satisfy: closure, success, inclusion, vacuity, consistency, extensionality, superexpansion, and subexpansion. The revision operation is defined via the Levi Identity:

\[K * \alpha = (K - \neg\alpha) + \alpha\]

where \(-\) is contraction and \(+\) is expansion. A recent semantic generalization appears in arXiv:2112.13557 ([https://arxiv.org/abs/2112.13557](https://arxiv.org/abs/2112.13557)): Kabir et al. (2021–2023) establish a generic model-theoretic characterization of AGM revision over arbitrary Tarskian logics, showing that preference relations need not be transitive in the general case.

### Belief Revision in Description Logics

AGM revision has been adapted to description logics (DLs), the formal foundation of OWL ontologies. Key results:

- **EL ontologies** (the lightweight tractable DL used in OBO ontologies): Revision of EL ontologies under the AGM paradigm is studied in Zhuang et al. (2023), "Revision of prioritized EL ontologies," *Applied Intelligence*, DOI:10.1007/s10489-023-05074-6 ([https://dl.acm.org/doi/10.1007/s10489-023-05074-6](https://dl.acm.org/doi/10.1007/s10489-023-05074-6)). The paper finds that priority-based revision for EL is decidable in polynomial time under certain assumptions. However, this is for **single-agent revision** — one agent receiving one new belief and revising its ontology accordingly.

- **ALC ontologies**: Aiguier et al. (2015), "Relaxation-based revision operators in description logics," demonstrate that AGM-compliant revision operators can be defined for ALC and its fragments (EL, ELU) ([https://www.semanticscholar.org/paper/dc82ee7e0b0ec5b42e706890ca5191b2c0c67864](https://www.semanticscholar.org/paper/dc82ee7e0b0ec5b42e706890ca5191b2c0c67864)). The revision is computed by "relaxing" the model space. Decidable, but computationally expensive (EXPTIME for ALC reasoning).

- **SROIQ (OWL 2 Full)**: The logical difference between two SROIQ ontologies — detecting what new entailments arise when they are merged — is **undecidable** (Jiménez-Ruiz et al. 2011, cited above). This is the critical result for dharma_swarm: if the system ever evolves to OWL-level expressivity, automated semantic conflict detection becomes formally intractable.

- **Ontology Evolution Under Semantic Constraints**: Grau, Jiménez-Ruiz, Kharlamov, and Zheleznyakov (2012), "Ontology Evolution Under Semantic Constraints," studied the problem of safely evolving an ontology while preserving a set of semantic constraints ([https://www.semanticscholar.org/paper/fa61e369a1f7d000cd0c00b43c33ec4ca8550a83](https://www.semanticscholar.org/paper/fa61e369a1f7d000cd0c00b43c33ec4ca8550a83)). They show that constraint-preserving evolution is decidable for EL but becomes undecidable for more expressive DLs, and that even in EL, computing the "safest possible update" is NP-hard in the general case.

### Multiple Revision and Multi-Agent Convergence

The multiple revision problem — revising an ontology with multiple simultaneously-arriving beliefs — was studied in the CEUR-WS workshop paper "Multiple Revision in Description Logics" ([https://ceur-ws.org/Vol-2438/paper3.pdf](https://ceur-ws.org/Vol-2438/paper3.pdf)). Key result: multiple revisions do not, in general, commute. If agent A proposes belief \(\alpha\) and agent B proposes belief \(\beta\), then \((K * \alpha) * \beta \neq (K * \beta) * \alpha\) in general. This is the formal statement of why **concurrent multi-agent ontology editing does not have a canonical solution**: the order in which proposals are applied affects the result, and different orderings can produce different ontologies.

**Convergence decidability:** For the property-graph formalism used in dharma_swarm (typed objects, links, cardinalities, lifecycle statuses), the problem is below OWL-level expressivity. If we restrict to the ALIGN rules in check_ontology_alignment.py (name uniqueness, api_name uniqueness, status monotonicity, link compatibility, action signature compatibility), all checks are decidable in polynomial time via simple set operations. However, **semantic convergence** — ensuring that after merging concurrent proposals, the resulting ontology has no unintended logical consequences — requires reasoning that the current gate does not perform at all.

---

## Gaps in dharma_swarm's Current Align-Gate

The following gaps are concrete, specific, and backed by external literature. They are listed in order of severity.

### Gap 1: No Semantic Equivalence Detection

The gate compares `ObjectType` definitions by field equality (`api_name`, `telos_alignment`, `description`, `version`). Two agents may independently propose semantically equivalent types with different descriptions or different `telos_alignment` scores. The gate will flag these as ALIGN-001 conflicts, forcing operator resolution of what may actually be non-conflicting proposals. Conversely, two types with the same name but genuinely incompatible semantics (e.g., one defines `Transaction` as a financial event, the other as a database operation) will only be flagged if scalar fields differ — **there is no check on the semantic meaning of property definitions**. ContentCVS (Jiménez-Ruiz et al.) identifies this as the core limitation of structural-only comparison: structural equivalence neither implies semantic compatibility nor detects semantic incompatibility.

### Gap 2: No 3-Way Merge — Conflicts Block, They Don't Resolve

The gate is explicitly "intentionally additive — it never modifies ontology.py, never auto-resolves, never merges." This is a correct design choice *given the current tooling*, but it means that every detected conflict becomes a manual operator interruption. With 5 concurrent agents and a growing ontology, the frequency of ALIGN-001 through ALIGN-005 conflicts will scale as O(n²) with the number of concurrent PRs. There is no mechanism to automatically resolve non-conflicting concurrent additions (two agents adding different, unrelated types) — these still require operator review because the gate does not distinguish "truly conflicting" from "merely concurrent but compatible." Keet and Grütter (2021) catalog exactly this failure mode: resolution frameworks must distinguish conflicts requiring negotiation from concurrent compatible changes that can be safely merged.

### Gap 3: No Runtime Locking or Optimistic Concurrency Control

The gate runs at PR creation time. Between PR creation and merge, another PR may modify the same type definitions without triggering a re-check of the original PR. The gate's snapshot comparison uses `git fetch` of open PR heads — if a PR is updated after the gate runs, the gate result is stale. There is no version-vector or logical timestamp attached to proposals; there is no mechanism to detect that two proposals were based on different versions of `origin/main`. This is the classic **lost update problem** in distributed systems. LinkedIn DataHub addresses this with monotonically increasing aspect version numbers and optimistic locking — any attempt to update an aspect must include the current version number, and concurrent updates to the same version number are rejected.

### Gap 4: Property-Level Conflicts Are Invisible

The `TypeSpec` dataclass in the gate stores `properties: dict[str, dict]` but the AST extractor in `_extract_ontology_snapshot` does not populate this field — it is left as `{}` (empty dict, with the comment "filled below via LinkDef/PropertyDef extraction" that is never implemented). **ALIGN-001 therefore does not actually compare property definitions** — it only compares `api_name`, `telos_alignment`, `shakti_energy`, `version`, and `description`. Two agents proposing `ObjectType("Transaction")` with completely different property schemas (different property names, different `PropertyType` values, different nullability) will **not** be flagged as conflicting if the scalar metadata fields happen to agree. This is a direct implementation gap, not a design gap.

### Gap 5: No Semantic Closure Check on Merged State

Even when no pairwise conflict exists between two PRs, their union may introduce unintended semantic consequences. For example: PR A adds `ObjectType("Asset")` with a link to `ObjectType("Transaction")`; PR B adds `ObjectType("Transaction")` with a link back to `ObjectType("Asset")` creating a bidirectional cycle. Neither PR alone is problematic, but their merge creates a circular dependency that may or may not be intended. The gate checks pairwise conflicts but does not check the semantic closure of the union of all proposed changes. ContentCVS identified this as a core challenge: the merged ontology \(O_1 \cup O_2\) can have entailments not present in either \(O_1\) or \(O_2\) individually.

### Gap 6: Status Monotonicity Is Declared but Not Enforced Against Runtime State

ALIGN-003 checks that two PRs don't assign conflicting statuses to the same type. But the gate does not check whether a proposed status change is backward-compatible with the *production runtime state* of objects instantiated from that type. If `ObjectType("Transaction")` has been promoted to `PROMOTED` in production and has live instances, a PR proposing structural changes to its property schema is not flagged — only status field changes are checked. Palantir's OMS explicitly separates schema-level promotion from instance-level compatibility: a type can be structurally modified in a non-breaking way even after promotion, but the current gate has no concept of breaking vs. non-breaking structural changes.

### Gap 7: No Handling of Tombstones or Deletions

ALIGN-006 checks for undeprecated removal of a `PROMOTED` `ObjectType`. But the gate has no concept of **tombstones** — a mechanism to track that a type has been deleted so that future proposals using the same name can be detected as reuse of a deleted name. If agent A deletes `ObjectType("Transaction")` (with a deprecation marker) and agent B simultaneously proposes a new `ObjectType("Transaction")` with a different schema, the gate may not flag this as a conflict if the deprecation marker is present in A's PR. CRDTs for sets (2P-Set, OR-Set) have well-understood tombstone semantics — once removed, an element cannot be re-added without explicit re-add operations — but the current gate has no equivalent.

### Gap 8: No Consensus Protocol for Multi-Agent Proposal Negotiation

The gate is binary: conflict or no conflict. There is no mechanism for agents to negotiate — to say "I proposed X but I see agent B proposed Y; let me defer to B's proposal" or "both proposals are acceptable; here is a merged proposal." The operator must manually resolve all flagged conflicts. As the paper on multiple revision in description logics shows, the order of conflict resolution affects the final ontology. Without a formal consensus protocol, the operator's manual decisions are the only source of convergence, and these decisions are not auditable as formal justifications. This is the most fundamental architectural gap: the system outsources convergence to human judgment without providing the human with formal support for making that judgment correctly.

---

## Adversarial Questions the Project Has Not Answered

**1. What is the convergence guarantee?** If 5 agents each submit 3 ontology PRs simultaneously, what is the formal guarantee that the system eventually reaches a consistent ontology? Is convergence guaranteed, or merely possible? Under what conditions does the operator's manual resolution produce an inconsistent ontology without the system detecting it?

**2. Why is Python source the schema representation?** `ontology.py` is both executable code and schema definition. The AST-based extractor in the gate cannot evaluate computed expressions — any `ObjectType` whose arguments involve variables, function calls, or conditional logic will be silently misextracted. This means the gate's correctness depends on an informal convention that all `ObjectType` definitions use literal arguments, which is not enforced anywhere. A schema registry (Protobuf, Avro, JSON Schema, LinkML) would provide a machine-readable, formally structured representation that eliminates this class of extraction errors.

**3. What happens when two agents add semantically equivalent but syntactically distinct types?** The gate detects name collisions but not semantic equivalence. If agent A adds `ObjectType("TxnRecord")` and agent B adds `ObjectType("TransactionRecord")` with the same property structure, both will be merged — creating a duplicate type. No current check catches this. This is the "lexical conflict" problem identified by ContentCVS as requiring ontology matching techniques to resolve automatically.

**4. How does the system handle the N+1 agent problem?** The gate is designed for 5 agents. What happens at 10 agents, or at a swarm of 50 ephemeral AI agents each making micro-proposals? The O(n²) pairwise comparison in `_detect_conflicts` scales poorly. At what agent count does manual operator resolution become the bottleneck, and what is the plan for that regime?

**5. Is `telos_alignment` a semantic primitive or a metadata tag?** The gate treats `telos_alignment` as a scalar field that must match exactly across concurrent proposals. But if two agents independently assign `telos_alignment=0.85` and `telos_alignment=0.82` to the same type, are these in conflict? If so, who arbitrates? If not, what merge rule applies (min, max, average)? The absence of a formal semantics for `telos_alignment` means the gate's ALIGN-001 check for this field cannot be justified on principled grounds.

**6. What is the recovery procedure when a bad merge reaches production?** The gate prevents merges with detected conflicts. But if a conflict-free (per the gate) set of changes is merged and later found to produce an invalid ontology state at runtime, what is the rollback procedure? How are live object instances migrated if a type definition is reverted? There is no answer in the current codebase.

**7. Has the system been tested against adversarial agent behavior?** KARMA's experimental design included an "Agent Provocateur" that deliberately added conflicting and incorrect content to an ontology to assess the system's detection capability. dharma_swarm has no equivalent adversarial test. What happens if one agent systematically proposes type definitions that are syntactically valid but semantically designed to degrade the ontology's utility?

**8. What is the semantic contract of `api_name`?** ALIGN-007 enforces the pattern `dharma.<domain>.<TypeName>.v<N>` but does not enforce semantic stability — an `api_name` can be reused across incompatible versions by simply bumping the `vN` suffix. If downstream systems depend on `dharma.finance.Transaction.v1`, and agent A proposes `dharma.finance.Transaction.v2` with a completely different property schema, no consumer is notified. The version bump is syntactically valid but semantically breaking for consumers expecting additive-only changes.

---

## Recommended Next Moves (Ranked by Feasibility)

### 1. Migrate Schema Definition to a Machine-Readable Format (Highest Feasibility)

Replace Python-source-as-schema with a structured schema language (LinkML YAML, JSON Schema, Avro, or Protobuf). This eliminates the AST-extraction gap (Gap 4), makes schema definitions machine-verifiable, and enables integration with existing schema governance tools. LinkML ([https://linkml.io/linkml/howtos/collaborative-development.html](https://linkml.io/linkml/howtos/collaborative-development.html)) supports Python dataclass generation from YAML schemas, is OWL-compatible, and provides built-in schema merge utilities. Cost: medium migration effort. Benefit: eliminates an entire class of gate failure modes and enables tool ecosystem reuse.

### 2. Implement Property-Level Conflict Detection and Monotone Add-Only Sets (High Feasibility)

Fix the immediate implementation gap: populate the `properties` dict in `_extract_ontology_snapshot` and add ALIGN-008 (property schema mismatch) and ALIGN-009 (property deletion without deprecation) checks. Adopt an add-only policy for properties within a promoted type (new properties can be added, existing properties cannot be removed or type-changed without a version bump). This is a CRDT-compatible constraint: property sets become grow-only sets (G-Sets), which have well-defined merge semantics. The gate can then merge non-conflicting concurrent additions automatically rather than requiring operator review.

### 3. Introduce Proposal Versioning with Optimistic Locking (Medium Feasibility)

Attach a `base_version` field to every ontology proposal — the SHA of `origin/main` at the time the proposal was drafted. The gate should reject any proposal whose `base_version` does not match the current `origin/main` SHA, requiring the proposing agent to rebase. This prevents the lost-update problem (Gap 3). Adopt LinkedIn DataHub's pattern: every aspect write must include the current version number, and concurrent writes to the same version number are rejected with a conflict signal. This transforms the problem from "detect conflicts at PR time" to "prevent concurrent edits to diverged state from being silently merged."

### 4. Implement a Semantic Closure Check on Proposed Merges (Medium Feasibility, High Value)

After pairwise conflict detection passes, run a semantic closure check: given the union of all currently-open proposals plus `origin/main`, does the resulting type graph have any circular dependencies, unresolvable link targets, or violated invariants? This requires building a graph of proposed types and their links and running reachability analysis — O(V+E) with V types and E links. For the current ontology size, this is trivially fast. This addresses Gap 5 and prevents a large class of "no pairwise conflict but still semantically broken" scenarios.

### 5. Adopt a Formal Proposal-Review-Merge Protocol with Explicit Consensus Tracking (Lower Feasibility, Highest Long-Term Value)

Move from a binary "conflict or no conflict" gate to a formal consensus protocol: each proposal enters a `PROPOSED` state, requires endorsement from N of M agents before entering `APPROVED`, and is only merged when no other `APPROVED` proposal touches the same type. This is a distributed coordination protocol — not a CRDT (which avoids coordination) but a structured coordination mechanism. The academic literature on belief merging (Bouraoui et al. 2022, "Region-Based Merging of Open-Domain Terminological Knowledge," arXiv:2205.02660, [https://arxiv.org/abs/2205.02660](https://arxiv.org/abs/2205.02660)) provides a formal foundation: translate type proposals into "regions" in a conceptual space, merge by majority or weighted combination, then translate back to schema definitions. This approach requires significant engineering investment but is the only path to automated convergence that does not require complete serialization of schema edits.

---

## Sources

1. **KARMA (NeurIPS 2025 Spotlight)** — Yuxing Lu, Wei Wu, Xukai Zhao, Rui Peng, Jinzhuo Wang. "KARMA: Leveraging Multi-Agent LLMs for Automated Knowledge Graph Enrichment." arXiv:2502.06472 (2025). https://arxiv.org/abs/2502.06472

2. **Shapiro et al. CRDT 2011** — Marc Shapiro, Nuno Preguiça, Carlos Baquero, Marek Zawirski. "Conflict-free Replicated Data Types." *Symposium on Self-Stabilizing Systems*, Springer LNCS 6976, pp. 386–400 (2011). https://pages.lip6.fr/Marc.Shapiro/papers/CRDTs_SSS-2011.pdf

3. **Kleppmann & Beresford 2017 JSON CRDT** — Martin Kleppmann, Alastair R. Beresford. "A Conflict-Free Replicated JSON Datatype." *IEEE Transactions on Parallel and Distributed Systems* 28(10):2733–2746 (2017). arXiv:1608.03960. https://arxiv.org/abs/1608.03960

4. **Preguiça, Baquero, Shapiro 2018 CRDT Overview** — Nuno Preguiça, Carlos Baquero, Marc Shapiro. "Conflict-free Replicated Data Types (CRDTs)." *Encyclopedia of Big Data Technologies*, Springer (2018). arXiv:1805.06358. https://arxiv.org/abs/1805.06358

5. **Laddad et al. 2022 CALM** — Shadaj Laddad, Conor Power, Mae Milano, Alvin Cheung, Natacha Crooks, Joseph M. Hellerstein. "Keep CALM and CRDT On." arXiv:2210.12605 (2022). https://arxiv.org/abs/2210.12605

6. **Masson, Syriani, Dávid 2022 Extensible CRDTs** — Constantin Masson, Eugene Syriani, István Dávid. "Extensible Conflict-Free Replicated Datatypes for Real-time Collaborative Software Engineering." *FedCSIS* (2022). DOI:10.15439/2022F99. https://annals-csis.org/proceedings/2022/drp/pdf/99.pdf

7. **Jiménez-Ruiz et al. 2011 ContentCVS** — Ernesto Jiménez-Ruiz et al. "Supporting Concurrent Ontology Development." *Data & Knowledge Engineering* (2011). https://www.cs.ox.ac.uk/isg/tools/ContentCVS/paperDKE-DATAK-1291.pdf

8. **Mungall et al. 2024 KGCL** — Chris Mungall, Christian Kindermann et al. "A change language for ontologies and knowledge graphs." *Database* (2024). DOI:10.1093/database/baae133. https://pmc.ncbi.nlm.nih.gov/articles/PMC11753292/

9. **Keet & Grütter 2021** — C. Maria Keet, Rolf Grütter. "Toward a systematic conflict resolution framework for ontologies." *Journal of Biomedical Semantics* (2021). https://pmc.ncbi.nlm.nih.gov/articles/PMC8352153/

10. **Guo et al. 2022 Algebraic Merging** — Xiuzhan Guo, Arthur Berrill, Ajinkya Kulkarni, Kostya Belezko, Min Luo. "Merging Ontologies Algebraically." arXiv:2208.08715 (2022). https://arxiv.org/abs/2208.08715

11. **Babalou & König-Ries 2020 CoMerger** — Samira Babalou, Birgitta König-Ries. "Towards Building Knowledge by Merging Multiple Ontologies with CoMerger." arXiv:2005.02659 (2020). https://arxiv.org/abs/2005.02659

12. **AGM 1985** — Carlos Alchourrón, Peter Gärdenfors, David Makinson. "On the Logic of Theory Change: Partial Meet Contraction and Revision Functions." *Journal of Symbolic Logic* 50(2):510–530 (1985). [Foundational; no arXiv] https://doi.org/10.2307/2274239

13. **AGM Semantics 2021** — arXiv:2112.13557. "AGM Belief Revision, Semantically." https://arxiv.org/abs/2112.13557

14. **Multiple Revision in Description Logics** — CEUR-WS Vol-2438, Paper 3. "Multiple Revision in Description Logics." https://ceur-ws.org/Vol-2438/paper3.pdf

15. **Zhuang et al. 2023 EL Revision** — "Revision of prioritized EL ontologies." *Applied Intelligence* (2023). DOI:10.1007/s10489-023-05074-6. https://dl.acm.org/doi/10.1007/s10489-023-05074-6

16. **Grau et al. 2012 Ontology Evolution Under Constraints** — Bernardo Cuenca Grau, Ernesto Jiménez-Ruiz, Evgeny Kharlamov, Dmitriy Zheleznyakov. "Ontology Evolution Under Semantic Constraints." (2012). https://www.semanticscholar.org/paper/fa61e369a1f7d000cd0c00b43c33ec4ca8550a83

17. **Aiguier et al. 2015 ALC Revision** — Marc Aiguier, Jamal Atif, Isabelle Bloch, Céline Hudelot. "Relaxation-based revision operators in description logics." (2015). https://www.semanticscholar.org/paper/dc82ee7e0b0ec5b42e706890ca5191b2c0c67864

18. **Bouraoui et al. 2022 Region-Based Merging** — Zied Bouraoui, Sébastien Konieczny et al. "Region-Based Merging of Open-Domain Terminological Knowledge." arXiv:2205.02660 (2022). https://arxiv.org/abs/2205.02660

19. **Apollo Federation Composition Rules** — Apollo GraphQL Docs. https://www.apollographql.com/docs/graphos/schema-design/federated-schemas/composition

20. **Palantir Ontology Manager AMA** — Palantir Developer Community (2025). https://community.palantir.com/t/ama-learn-from-the-ontology-manager-team-about-the-applications-history-and-help-us-shape-its-future/5100

21. **LinkedIn DataHub Architecture** — LinkedIn Engineering Blog (2020). https://www.linkedin.com/blog/engineering/data-management/datahub-popular-metadata-architectures-explained

22. **Zhang, Wei, Huang 2022 Remove-Win CRDT** — Yuqi Zhang, Hengfeng Wei, Yu Huang. "Remove-Win: a Design Framework for Conflict-free Replicated Data Types." arXiv:1905.01403 (2022). https://arxiv.org/abs/1905.01403

23. **WebProtégé** — Matthew Horridge et al. "WebProtégé: A Collaborative Ontology Editor." *Semantic Web* (2013). PMC3691821. https://pmc.ncbi.nlm.nih.gov/articles/PMC3691821/
