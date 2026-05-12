# Organ Wiring Matrix

Date: 2026-05-11
Status: draft wiring map

## Core Answer

This packet is not guaranteed to be the highest final product.

It is the highest current **integration object** because it can touch every major organ without requiring a rewrite. A dashboard can hide missing organs. A manifesto can bypass runtime. A product wedge can overfit to sales. A proof artifact cannot work unless the organs cooperate.

The test is simple:

```text
Can this organ sense, gate, act on, witness, remember, evaluate, or learn from
one real artifact?
```

If not, the organ is missing a wire.

## Wiring Matrix

| Organ | Current status | Missing wire | How this packet forces the wire | First mechanical edge |
|---|---|---|---|---|
| VIVEKA / gates | Present in telos gates, Semantic Anekanta, Bhed Gnan, SABP laws | One review pass that marks dossier claims pass/warn/fail | Every claim in `claims_register.md` needs tier and gate status | Add gate results to `proof_artifact_contract.json.gates` |
| SHAKTI / selection | Present as ShaktiExecutive and opportunity board | Artifact outcome must affect future selection | Packet has `opportunity_id`, outcome fields, and next-state decision | Create or map one opportunity row for this packet |
| KALYAN / value routing | Present as Outcome, ValueEvent, Contribution types | The artifact must record value, not just completion | Packet requires Outcome/ValueEvent/Contribution IDs | After review, record an Outcome for artifact production |
| MemoryKernel | M0/M1/M2A present, read-only | Claims need authority-labeled memory refs | Packet lists evidence surfaces and distinguishes authority levels | Add MemoryKernel atom refs or authority labels to claim rows |
| KnowledgeOps | Present as extraction/projection direction | Claim register should become semantic metabolism, not prose only | Packet separates claims, evidence, gaps, and promotion state | Convert selected claims into KnowledgeOps candidate cards later |
| Dharmic Agora / SABP | Public membrane live but dual-surface | Artifact needs submit/witness/challenge/canon/compost state | Contract has `sABP_submission` and `witness_link_id` | Submit dossier as spark/post after human boundary approval |
| Build Protocol | Present: plan/seal/shadow-apply | ProofArtifact contract cannot yet render into Build Protocol spec | `next_build_spec.md` defines the adapter target | Build `proof_artifact_to_spec.py` or manually create spec |
| DarwinEngine | Present: shadow sealed packet ingestion | Artifact must cause a shadow-archived improvement proposal | Packet defines next internal improvement target | Run Build Protocol shadow path for ProofArtifact adapter |
| VentureCell | Ontology type present; runtime polymorphism missing | This packet needs a parent cell that is more than a label | Contract proposes `Agentic Immune X-Ray` parent VentureCell | Register or map a VentureCell only after human approves wedge |
| FractalRoom | Mostly design vocabulary here | No typed/runtime room object yet | Packet identifies needed rooms: Evidence, Gate, Witness, Product, Build | Do not implement first; use rooms as checklist inside cell |
| SwarmLens / observability | Strong product spec, not whole organism | Needs immune claims, not just traces/costs | Packet reframes SwarmLens as one arm under immune infrastructure | Later: use packet to define SwarmLens immune dashboard requirements |
| AgentOps / interop | Emerging worktree files present | Needs to route artifacts without unsafe parallelism | Packet gives bounded artifact and roles | Later: assign reviewer/builder/challenger roles to agents |
| Human operator | Present but overloaded | Human should decide boundaries, not hold all context | `human_operator_brief.md` compresses decisions | Human answers five-line boundary block |

## Missing Or Weak Organs Exposed By This Packet

### 1. ProofArtifact Adapter

Missing:

```text
proof_artifact_contract.json -> Build Protocol spec
```

Why it matters:

Without this, the artifact stays a report and cannot enter the sealed packet / Darwin shadow spine.

Small next step:

```text
tools/build_protocol/proof_artifact_to_spec.py
```

### 2. Claim Gate Runner

Missing:

```text
claims_register.md -> Semantic Anekanta / Bhed Gnan / SATYA review output
```

Why it matters:

The dossier can sound correct without being structurally grounded.

Small next step:

```text
scripts or manual pass that writes gate statuses back into proof_artifact_contract.json
```

### 3. SABP Submission Adapter

Missing:

```text
dossier + claim register -> SABP spark/post submission payload
```

Why it matters:

The public membrane cannot witness what never enters it.

Small next step:

```text
manual semi-public submission first, adapter later
```

### 4. Outcome Feedback Recording

Missing:

```text
artifact reviewed/submitted -> Outcome / ValueEvent / Contribution
```

Why it matters:

The system must learn from artifact production, not just archive it.

Small next step:

```text
record one Outcome after human review and gate pass
```

### 5. VentureCell Runtime Binding

Missing:

```text
Agentic Immune X-Ray cell -> actual state, rooms, outputs, witness policy
```

Why it matters:

Otherwise the cell is another label.

Small next step:

```text
do not create broad runtime yet; bind this packet as the first cell artifact
```

## Why Not Start With A Website

A website can present the vision while bypassing the organs.

This packet forces the website to inherit truth:

```text
website copy
  <- dossier claims
  <- claims register
  <- evidence tiers
  <- witness/challenge state
  <- human red lines
```

That prevents the first public surface from becoming inflated.

## Why Not Start With VentureCell Schema

Schema work is necessary, but starting there risks premature collapse.

This packet tells the schema what fields are actually needed:

- claim tiers,
- evidence refs,
- gate status,
- public membrane state,
- witness link,
- outcome/value/contribution IDs,
- human boundary decisions,
- promotion and kill conditions.

The schema should follow the artifact loop, not the other way around.

## Minimum Viable Organism For This Packet

The first viable loop needs only:

1. ProofArtifact packet,
2. VIVEKA gate/check pass,
3. human boundary decision,
4. SABP witness/challenge path,
5. Outcome / ValueEvent / Contribution record,
6. Shakti feedback,
7. Build Protocol shadow improvement.

Everything else is supporting or later.

## Decision

This packet is the right next move if the goal is to wire the organism.

It is not the right next move if the goal is immediate public launch, immediate SaaS build, or broad ontology refactor.

The current task is organism closure, not market polish.

