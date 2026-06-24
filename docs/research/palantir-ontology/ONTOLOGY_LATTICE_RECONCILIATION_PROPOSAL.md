# Ontology Lattice Reconciliation — Design Proposal

**Status:** PROPOSAL (propose step; no `ontology.py` / `semantic_objects.yaml` edits in this doc) · **Date:** 2026-06-24
**Lane:** ontology-lattice-reconciliation · **Branch:** `claude/ontology-lattice-reconciliation`
**Defers to:** `dharma_swarm/ontology.py` (ObjectType registry), ADR-008 grammar, Semantic Commons.
Promotion of any ObjectType is operator-only (ADR-008 `TypeStatus`). This doc proposes; the operator ratifies.

> Co-developed with the **organism-convergence (policy + observability)** lane. Single-writer
> ordering agreed: **this reconciliation lands first; that lane's vocab-governance PR rebases
> on the unified lattice.** That lane does not touch `ontology.py`; it governs metaphor terms
> (e.g. reserve bare "spine") as objects/aliases in `semantic_objects.yaml` *after* this lands.

---

## 1. The problem (finding #3 from the build)

The repo has **two type-vocabularies that do not reference each other**:

- **`dharma_swarm/ontology.py`** — 21 ratified `ObjectType`s under the ADR-008 grammar
  `dharma.<domain>.<TypeName>`. Domains: agent, economic, evolution, execution, governance,
  knowledge, research, revenue, task.
- **`docs/ontology/semantic_objects.yaml`** — 13 runtime objects tagged with a `kind:`
  (evidence_receipt, governance_contract, identifier, key_store, provider_factory,
  route_binding, routing_order, routing_policy, routing_telemetry, runtime_object,
  runtime_router, transport_substrate, verifier_boundary), each with a canonical name + owner.

A reader cannot tell, from either file, that (say) the `evidence_receipt` *kind* and a
metabolic *record* ObjectType are the same noun. That is the unreconciled lattice.

## 2. The key insight — they are two TIERS, not duplicates

Reconciliation does **not** mean merging the two into one flat list. Inspected closely, they
sit at **different altitudes**:

| | `ontology.py` ObjectTypes | `semantic_objects.yaml` kinds |
|---|---|---|
| **What** | Domain + **metabolic** objects the system *reasons about* | **Substrate/runtime** components the system *runs on* |
| **Examples** | ResearchThread, ValueEvent, ActionProposal, Outcome | NATSSubstrate (transport), ModelRouter (router), DKeysKeyStore (key store) |
| **Role** | The typed graph (objects/links/actions) | The naming SSOT (canonical name + owner per component) |

Most `kind:` values (transport_substrate, runtime_router, key_store, provider_factory,
route_binding, routing_order, routing_policy, runtime_router) are **infrastructure
components, NOT domain ObjectTypes** — they belong in the naming SSOT and should *stay* there.
So the goal is **cross-reference, not collapse**: make the two tiers point at each other where
they overlap, and leave the rest cleanly tiered.

## 3. The seam — where the two tiers genuinely overlap (~3 objects)

These `kind:` entries name the *same noun* as a (present or missing) ObjectType:

| `semantic_objects.yaml` kind | The noun | ObjectType status | Action |
|---|---|---|---|
| `evidence_receipt` | the spine's `EvidenceReceipt` (immutable dispatch record) | **NOT an ObjectType** — only a code class + this kind tag | **Promote** to `dharma.execution.EvidenceReceipt` |
| `runtime_object` (A2ACard) | the agent discovery card | not an ObjectType | Candidate `dharma.agent.AgentCard` |
| `routing_telemetry` (RoutingMemory) | provider-learning evidence store | not an ObjectType | Candidate `dharma.execution.RoutingMemory` (lower priority) |

## 4. The metabolic triad — the spine of the lattice (finding #4)

Across all four filesystem-substrate slices the same triad recurred:
**declaration → gated dispatch → immutable record.** Its status in `ontology.py` today:

| Step | Canonical ObjectType | Status |
|---|---|---|
| declaration | `dharma.governance.ActionProposal` | ✅ ratified |
| gated dispatch / decision | `dharma.governance.GateDecisionRecord` | ✅ ratified |
| immutable record | `dharma.execution.Outcome` **and/or** `EvidenceReceipt` | ⚠️ split / gap |

**The gap:** the "record" step is split. `Outcome` (business result) is ratified; the
`EvidenceReceipt` (the dispatch-proof the spine actually emits, one per `invoke_agent`) is
**not** an ObjectType — yet it is arguably the single most-produced record in the runtime.

**Proposal:** canonicalize the triad as the named generic
`ActionProposal → GateDecisionRecord → {Outcome | EvidenceReceipt}`, and ratify
`dharma.execution.EvidenceReceipt` so the dispatch record is a first-class node. Every
substrate object specializes this triad: my `StageContract`→dispatch→`EvidenceReceipt`,
my `ReorgProposal`→confirm-gate→`ApplyResult`, and the organism-convergence lane's
observability discipline (proposal→gate→receipt) are all the same shape.

## 5. The reconciliation mechanism (minimal, converge-don't-collapse)

Add one optional cross-reference field to `semantic_objects.yaml` entries that **are** ratified
ObjectTypes — leaving pure-infrastructure entries without one:

```yaml
EvidenceReceipt:
  kind: evidence_receipt
  object_type: dharma.execution.EvidenceReceipt   # <-- NEW cross-ref; absent for pure infra
  owner: dharma_swarm/spine/receipt.py
```

This unifies the two registries **without flattening the tiers**: the naming SSOT keeps every
runtime component; the ones that are also domain/metabolic objects now point at their ObjectType.
A reader (or the OKF projector) can then render one coherent graph.

## 6. Proposed landing order (operator-gated)

1. **(this doc)** Proposal reviewed by operator + organism-convergence lane.
2. **Ratify** `dharma.execution.EvidenceReceipt` (+ optionally `dharma.agent.AgentCard`) in
   `ontology.py` — operator-only promotion, its own small PR.
3. **Canonicalize the triad** as the named generic (doc/registry note).
4. **Add `object_type:` cross-refs** to the ~3 overlapping `semantic_objects.yaml` entries
   (single-writer; this is the shared-surface edit the other lane rebases on).
5. The organism-convergence lane's vocab-governance PR rebases on (4).

## 7. Non-goals

- Do not collapse the two tiers into one flat list (they are genuinely different altitudes).
- Do not turn infrastructure components (transport/router/key-store) into domain ObjectTypes.
- Do not edit `ontology.py` without operator ratification (ADR-008).
- Do not touch `dharma_swarm/fs_substrate/**` (owned by the filesystem-native-substrate lane / PR #683).
- Do not reconcile the repo-wide manifest counts (owned by governance ops / PR #660).
