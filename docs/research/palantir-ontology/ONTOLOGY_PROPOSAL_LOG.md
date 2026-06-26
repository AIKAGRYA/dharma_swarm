# Semantic Ontology — Proposal / Observation Log

**Status:** running observation log (NOT authority) · **Opened:** 2026-06-24 · **Keeper:** rolling (any repo-aware agent appends)
**Lives in:** `docs/research/palantir-ontology/` — the ontology *proposal/grounding* zone,
beside its ancestor `PROPOSED_VOCABULARY.md`. (Proposals live here; *ratified owners* live
in `docs/ontology/`. The docops canonical guard enforces that split — this file projects,
it does not rule, so it belongs with the proposals.)

**The ontology landscape (so a newcomer can orient):**
- `dharma_swarm/ontology.py` — the **typed-object registry** (Palantir-style: `ObjectType`=schema,
  `OntologyObj`=instance, `LinkDef`/`Link`=relations, `ActionDef`/`ActionExec`=audited mutations,
  `OntologyRegistry`=catalog). ~22 domain types; api_names per ADR-008.
- `docs/ontology/SEMANTIC_COMMONS.md` + `semantic_objects.yaml` + `semantic_aliases.yaml` —
  the **naming/identity SSOT** (canonical name + owner + aliases per runtime object). The
  machine-readable index of terms.
- `docs/architecture/ADRs/ADR-008-ontology-api-name-grammar.md` — the **grammar**
  (`dharma.<domain>.<TypeName>`, PascalCase, no version suffix).
- `docs/research/palantir-ontology/vocabulary-census/PROPOSED_VOCABULARY.md` — the **ancestor**
  of this log (2026-06-02 census: "what each object IS in the life of the system"; awaits the
  operator's voice). This file is its lightweight, ongoing continuation.

**Defers to all of the above. Mints nothing.** Promotion is operator-only.

> **What this file is.** A place for agents who know the repo to *propose* terms for
> the semantic ontology — typed objects that have naturally formed in the system —
> with reasoning and intuition for each. It is a **read model**: it projects
> candidates and defers to the owner. It mints nothing. Promotion of any candidate
> into `ontology.py` is operator-only (ADR-008 `TypeStatus`: experimental → active →
> promoted) and goes through the typed-proposal envelope + schema-alignment gate.
>
> **Why it exists.** Yes — there *is* a settled-ish ontology (`ontology.py`, 22 types,
> ADR-008 grammar). But many typed objects have formed in the runtime that are *not*
> in it yet. This log is the staging area between "a class that looks like an object"
> and "a ratified `ObjectType`." It runs alongside builds so the observations are
> grounded in real code, not armchair taxonomy.

## The grammar (ADR-008, for every proposal below)

```
api_name = "dharma." <domain> "." <TypeName>
  <domain>   = lowercase snake_case      (existing: agent, economic, evolution,
                                           execution, governance, knowledge,
                                           research, revenue, task)
  <TypeName> = PascalCase, verbatim       NO ".v<N>" suffix; version lives in
                                          ObjectType.version: int
```

## The lens I classify with (so "intuition" is legible, not vibes)

- **ObjectType candidate** — stable identity, persists, is *referenced by* other
  objects, has a lifecycle/status. (Like `ResearchThread`, `AgentIdentity`.)
- **Event / receipt object** — immutable record of something that happened; identity
  is the event id; never mutated. Often better modeled as an event/time-series than a
  mutable ObjectType, though it can be a typed object with `status` frozen.
- **Link / relationship** — connects two objects (e.g. `depends_on`, a handoff edge).
  In Foundry terms a LinkType, not an ObjectType.
- **Ephemeral value object** — transient, not canonical truth (in-flight only). Should
  *not* enter the ontology; it has no durable identity.

Confidence = my read of how settled the concept is, not permission to promote.

---

## Candidates surfaced 2026-06-24 (filesystem-native-substrate, Slice A)

### Introduced by this build

| Concept | Proposed api_name | Lens | Reasoning & intuition | Conf. |
|---|---|---|---|---|
| Stage contract | `dharma.execution.StageContract` | **ObjectType candidate** | A stage has stable identity (`stage_id`), a content hash, typed inputs→outputs, and is referenced by its downstream stages. It is the unit other things point at. **Intuition:** this is the strongest new candidate — it's a *morphism made concrete* (domain=Inputs, codomain=Outputs), which is exactly the categorical-systems-theory pillar the system wants to be native to. Domain question below. | med-high |
| Stage workspace | `dharma.execution.StageWorkspace` | **ObjectType candidate** | A container object: a root + an ordered set of StageContracts. Has identity (its path), is the thing you "run." Composes-of StageContract (a link). **Intuition:** real object, but lower priority than StageContract — it's mostly an aggregate root. | med |
| Stage input row | (none — property/link) | **Link / value** | `StageInput` is a typed edge from a stage to a file/section it consumes; the sibling-output case *is* the `depends_on` link. **Intuition:** model as a LinkType (`consumes`), not an ObjectType. The `why` column is link metadata. | med |
| Stage output row | (none — property) | **value** | `StageOutput` is a declared artifact slot. **Intuition:** a property of StageContract, or a thin `ProducedArtifact` if outputs need first-class identity later. Not an object yet. | low-med |

**Domain question (for the owner).** I propose `execution` (the existing domain that
already holds dispatch/run concepts) rather than minting a new `fs_substrate` domain —
converge, don't proliferate. *But* if the filesystem-native substrate grows (OKF
bundles, semantic FS), a dedicated `substrate` domain may earn its place. Flagging, not
deciding. (Code currently carries a placeholder `dharma.fs_substrate.*` in comments;
will align to whatever the owner ratifies.)

### Observed in the runtime (already typed in code, candidates for ratification)

These already exist as classes and behave like ontology objects, but are **not** in
`ontology.py`. Listed with my read of whether they *should* be:

| Concept | Where | Proposed api_name | Lens | Reasoning & intuition | Conf. |
|---|---|---|---|---|---|
| Evidence receipt | `spine/receipt.py` | `dharma.execution.EvidenceReceipt` | **Event object** | The one canonical artifact every dispatch emits; frozen, identity = `receipt_id`, already OTel-shaped. **Intuition:** strong candidate, but model as an *event/time-series* (immutable, high-volume), not a mutable ObjectType. It is arguably the most important un-ratified type in the system — the spine's whole truth claim rests on it. | high |
| Routing decision | `spine/routing.py` | `dharma.execution.RoutingDecision` | **Event object** | Frozen value object joined to the receipt by id. **Intuition:** ratify *with* EvidenceReceipt (they're a pair); on its own it's a sub-record of a dispatch. | med |
| Handoff | `handoff.py` | `dharma.execution.Handoff` | **ObjectType + Link** | Has identity, status lifecycle (pending→ack/reject), persistence, lineage chains — very object-like. **Intuition:** the Handoff is an ObjectType; the from→to relation it carries is a LinkType. Good ratification candidate. | med-high |
| Artifact | `handoff.py` | `dharma.execution.Artifact` (or `knowledge`) | **value / ObjectType** | Typed work output (`ArtifactType` enum). **Intuition:** borderline — if artifacts get durable identity + retrieval, they're objects; today they're payloads inside a Handoff. Watch this one. | med |
| Task | `models.py` | `dharma.task.Task` | **ObjectType candidate** | Identity, status, priority, `depends_on` DAG, metadata — textbook object. `task` domain already exists. **Intuition:** almost certainly already intended for the ontology; if not registered, it's an oversight worth closing. | high |
| Skill definition | `skills.py` | `dharma.agent.Skill` | **ObjectType candidate** | A markdown-frontmatter role (name, model, provider, weights). It's *already* a portable typed concept file — basically an OKF concept today. **Intuition:** ratify; it bridges `skills/*.skill.md` ↔ `AgentIdentity`. | med-high |
| Memory atom | `memory_kernel/atoms.py` | `dharma.knowledge.MemoryAtom` | **ObjectType candidate** | Has `MemoryAtomType`, authority level, truth state, read mode — a rich typed object already governing memory. **Intuition:** strong; `knowledge` domain fits. Likely a keystone type for the truth-graph track. | med-high |
| Memory surface spec | `memory_kernel/surfaces.py` | `dharma.knowledge.MemorySurface` | **ObjectType candidate** | A registered store with role/path/authority. **Intuition:** object; pairs with MemoryAtom (atoms live on surfaces — a LinkType). | med |

**Cross-cutting intuition (2026-06-24).** The runtime's *real* spine of types is
clustering in an `execution` lane (Task → RoutingDecision → EvidenceReceipt → Handoff →
StageContract) and a `knowledge` lane (MemoryAtom → MemorySurface, and OKF concept
files). The ontology in `ontology.py` is currently weighted toward `research`,
`agent`, `governance`, `economic` — i.e. the *outward/venture* objects — and is thin on
the *substrate/execution* objects that actually carry every dispatch. If I had to name
the single highest-value ratification, it's `EvidenceReceipt` (or the
Task→RoutingDecision→EvidenceReceipt triple), because the spine-adoption track's whole
"one receipt per dispatch" claim would then be ontology-native, not just code-native.

---

## Candidates surfaced 2026-06-24 (filesystem-native-substrate, Slice B — OKF)

| Concept | Proposed api_name | Lens | Reasoning & intuition | Conf. |
|---|---|---|---|---|
| OKF concept | `dharma.knowledge.OKFConcept` | **ObjectType candidate** | One markdown file in a portable bundle; its path IS its identity; carries a required `type`. **Intuition:** this is the *interchange shadow* of an ontology object — the same noun, serialized for export/import. Worth ratifying because it's the boundary type between our ontology and the outside world (Google-OKF compat). It is to `MemoryAtom` what a shipping container is to a warehouse shelf. | med |

**Observation from building the projector.** `project_semantic_objects()` reads
`docs/ontology/semantic_objects.yaml` and emits one OKF concept per object, using each
object's **`kind`** (`runtime_object`, `identifier`, `route_binding`,
`governance_contract`, `key_store`, ...) as the OKF `type`. That means the manifest's
`kind` field is *already* functioning as a lightweight ObjectType discriminator — the
system has two parallel type-vocabularies (the `kind:` tags in semantic_objects.yaml and
the `ObjectType`s in ontology.py) that have not been reconciled. **Intuition / flag for
the owner:** these should eventually share one type lattice; today a `runtime_object`
(Semantic Commons) and an `ObjectType` (ontology.py) are cousins that don't know they're
related. Reconciling them is probably the single highest-leverage ontology cleanup.

## Candidates surfaced 2026-06-24 (filesystem-native-substrate, Slices C + D)

| Concept | Proposed api_name | Lens | Reasoning & intuition | Conf. |
|---|---|---|---|---|
| Retrieval hit | `dharma.knowledge.RetrievalHit` | **value (projection)** | `ScoredAtom` — a ranked projection of a MemoryAtom (surface, score, snippet). **Intuition:** ephemeral query result, *not* durable truth — should stay a value object, not an ObjectType. Listed so the line between "atom" (object) and "hit" (transient view of it) stays crisp. | med |
| LSFS syscalls | (Actions, not objects) | **ActionDef-like** | `keywords_retrieve / semantic_retrieve / group_semantic / integrated_retrieve` are *operations over* the knowledge graph, not nouns. **Intuition:** in the Palantir model these are Action/Function definitions, not ObjectTypes — a reminder that not everything typed is an object; some typed things are verbs. | med |
| Reorg proposal | `dharma.execution.ReorgProposal` | **ObjectType candidate** | A dry-run plan with identity, a lifecycle (proposed → applied), and review surface. **Intuition (the sharp one):** this *re-instances the existing metabolic loop* — `ReorgProposal` is a `proposal`, the `confirm=True` gate is a `gateDecision`, and `ApplyResult` is an `outcome`. Slice D is the metabolic loop (`proposal → gateDecision → outcome`, per PROPOSED_VOCABULARY.md) specialized for filesystem reorg. That is strong evidence the metabolic-loop triple is the system's *most reusable* shape — worth ratifying as the canonical generic before specializing it. | med-high |
| Reorg move | (property/link of ReorgProposal) | **value** | One src→dst edge with a reason. **Intuition:** a link/value inside the proposal, not its own object. | low-med |
| Apply result | `dharma.execution.OutcomeRecord`? | **event object** | Record of what was applied/skipped — an `outcome`/`ActionExec`. **Intuition:** ratify *with* the generic metabolic `outcome`, not as a one-off. | med |

**Cross-cutting (2026-06-24, end of Slices A–D).** Across four slices the same
triad keeps reappearing: a *declaration* (StageContract, ReorgProposal), a *gated
dispatch* (invoke_agent / confirm), and an *immutable record* (EvidenceReceipt,
ApplyResult). This is the `proposal → gateDecision → outcome` metabolic loop the
2026-06-02 census already named as bedrock. **My strongest single recommendation
for the owner:** ratify that triple as the canonical generic in `ontology.py`
first; nearly every substrate object I proposed is a specialization of it. The
filesystem-native work didn't invent new shapes — it kept rediscovering the
metabolic loop on disk.

## How to append (for the next agent)

1. Add a row under a dated heading: concept · proposed api_name (ADR-008 grammar) ·
   lens · reasoning/intuition · confidence.
2. Never edit `ontology.py` from here. This log proposes; the owner ratifies.
3. If a candidate gets ratified, mark the row `→ RATIFIED (commit)` and leave it as
   history.
