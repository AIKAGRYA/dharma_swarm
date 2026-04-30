# Ontology-Native Flow 001 — Daily Command Brief

Status: implementation seed  
Branch: `feature/ontology-native-command-brief-v0`  
Scope: one private, fail-closed, ontology-native artifact for Dhyana  
Non-goal: public product, brand, dashboard, Go/Rust, or external audit

---

## Master Builder Prompt

You are building **Ontology-Native Flow 001** for Dharma Swarm.

Do not reframe. Do not rename. Do not broaden. Do not build a public product.

The task is to create the first private artifact that is structurally impossible to produce without the ontology substrate.

### Mission

Build a daily command brief generator that writes one signed markdown file:

```text
~/dharma_briefs/YYYY-MM-DD.md
```

The brief is not a summary. It is a decision artifact.

It must answer:

```text
1. What is currently true?
2. What changed?
3. What matters today?
4. What is blocked?
5. What should be done first?
6. What should be ignored?
7. What evidence supports the claims?
8. What value was created or not created?
```

### Hard rule

For this flow only:

```text
If durable state cannot be recorded as typed ontology objects/actions, the flow stops.
```

This is the first exception to the old TelicSeam migration mode where ontology write-through is additive and best-effort.

### Why this exists

The current repo has real ontology infrastructure:

- `dharma_swarm/ontology.py` — ObjectType, OntologyObj, LinkDef, ActionDef, ActionExecution, SecurityPolicy.
- `dharma_swarm/ontology_hub.py` — SQLite persistence for objects, links, action log.
- `dharma_swarm/ontology_runtime.py` — shared runtime registry.
- `dharma_swarm/telic_seam.py` — additive write-through metabolic seam.
- `tests/test_telic_seam.py` — tested dispatch → gate → outcome → value → contribution chain.

But the ontology is not yet sovereign. Many paths can still write, call models, mutate runtime state, or create external artifacts without typed actions.

This flow is the first narrow sovereignty proof.

---

## Flow

```text
BriefSource
  ↓
BriefClaim
  ↓
BriefDecision
  ↓
KnowledgeArtifact / CommandBrief artifact
  ↓
ValueEvent
  ↓
WitnessLog
```

Every step must create:

```text
OntologyObj
ActionExecution
WitnessLog
```

The final markdown must cite ontology references in this form:

```text
ontology://<TypeName>/<object_id>#action/<action_id>
```

If a claim has no ontology reference, it must not appear as a claim.

---

## Minimal Object Types

This implementation may define lightweight flow-local types dynamically at runtime. Long-term, the stable types can migrate into `OntologyRegistry.create_dharma_registry()`.

Required types for v0:

```text
BriefSource
BriefClaim
BriefDecision
CommandBrief
```

Existing types used:

```text
KnowledgeArtifact
ValueEvent
WitnessLog
```

---

## Required Actions

```text
IngestSource
CreateClaim
CreateDecision
MaterializeBrief
RecordBriefValue
RecordWitness
```

Each action must gate via `TelosGatekeeper.check()` before object creation.

For this flow, gate failure or ontology persistence failure is fatal.

---

## Falsification Criteria

Set before running:

```text
1. If ontology.db is empty or deleted and the brief still generates normal claims, the flow failed.
2. If any claim in the markdown lacks an ontology:// reference, the flow failed.
3. If `WitnessLog` count remains 0 after 7 days, the substrate failed to breathe.
4. If Dhyana stops reading the brief by day 14, the artifact failed to earn its place.
5. If a brief claim’s ontology reference does not resolve to a real object/action, the gateway failed.
6. If the brief can be summarized as “Claude wrote a memo,” the typed-citation discipline collapsed.
```

---

## Output Format

```markdown
# Dhyana Daily Command Brief — YYYY-MM-DD

## 1. Current Ground Truth
- Claim with ontology citation.

## 2. Active Decisions
- Decision with ontology citation.

## 3. Highest-Leverage Work Order
- One recommendation only.

## 4. Substrate Health
- Ontology object/action/witness/value counts.

## 5. Signals Worth Attention
- Evidence-backed signal claims only.

## 6. Ignore List
- Explicit not-now items.

## 7. Value Ledger
- What value was produced or not produced.

## 8. Final Command
- One sentence.
```

If a section lacks verified data, write:

```text
NO VERIFIED DATA
```

Do not hallucinate coherence.

---

## Week-1 Build Plan

1. Add `dharma_swarm/ontology_action_gateway.py`.
2. Add `dharma_swarm/command_brief.py`.
3. Add `tests/test_ontology_action_gateway.py`.
4. Add `tests/test_command_brief.py`.
5. Keep all logic local and narrow.
6. No dashboard.
7. No scheduler until manual generation works.
8. No world-facing action.

---

## Definition of Done for v0

```text
- Brief generation creates ontology objects.
- Brief generation creates action executions.
- Brief generation creates witness logs.
- Brief markdown includes ontology citations for all claims.
- Generation fails closed on gate violation.
- Tests cover success and blocked-path behavior.
```

---

## Parking Lot

Do not build these in v0:

```text
Dharma Radar public product
Dharma OS branding
Go sensorium
Rust invariant kernel
dashboard projection
scheduler / cron
GitHub PR creation
external audit surface
multi-source live ingestion
```
