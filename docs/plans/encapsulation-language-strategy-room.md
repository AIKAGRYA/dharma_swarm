# Encapsulation + Second-Language Strategy Room

Status: research / architecture discussion room  
Branch: `research/encapsulation-language-strategy-room`  
Owner: Dhyana / Dharma Swarm agents  
Purpose: develop, challenge, and harden the Go/Rust/Python architecture before implementation.

---

## 0. Why this file exists

Dharma Swarm is approaching a structural threshold: the system is becoming runtime-real, but the next layer must not simply add more Python modules or more agents. The next layer must clarify what gets encapsulated, which invariants must become hard boundaries, and which language should own which part of the organism.

This room exists so multiple agents can research and debate the architecture for several days before any build begins.

Core question:

> How do we turn Dharma Swarm from a Python-centered agent organism into a modular, high-throughput, economically useful autonomous company substrate without losing the dharmic telos?

Working thesis:

```text
Python = mind / semantic orchestration / LLM cognition
Go     = sensorium / high-throughput ingestion / concurrent services
Rust   = bone-law / invariant kernel / ledgers / state machines / verification
```

This is a hypothesis, not a decision.

---

## 1. Mandatory context before contributing

Every agent entering this room must read these first:

1. `AGENTS.md` — canonical cross-agent rules if present on this branch/main.
2. `CLAUDE.md` — current behavioral rules, project architecture, key abstractions, and Transcendence Principle.
3. `README.md` — repo map, entry points, and distinction between shipped behavior and exploratory material.
4. `NAVIGATION.md` — module map and “when to touch” guidance.
5. `INTERFACE_MISMATCH_MAP.md` — current interface-contract fragility and live mismatches.
6. `MODEL_ROUTING_MAP.md` — provider/model routing architecture and inconsistencies.
7. `CYBERNETIC_LOOP_MAP.md` — feedback-loop closure status and acid tests.
8. `docs/plans/agent-work-os-v0.md` if present — cross-agent work OS direction.
9. Recent PRs #47–#55 — runtime lifecycle, context-bearing dispatch, Guardian hardening, external agent registration, operator ground truth, and agent work OS.

Do not propose a rewrite before reading these.

---

## 2. Repo surfaces most relevant to this discussion

### Runtime state and canonical truth

- `dharma_swarm/runtime_state.py`
- `dharma_swarm/runtime_lifecycle.py`
- `dharma_swarm/orchestrator.py`
- `dharma_swarm/agent_runner.py`
- `dharma_swarm/swarm.py`

Key issue: state exists, but state transitions and invariants need stronger encapsulation.

### Governance / membrane / hard boundaries

- `dharma_swarm/dharma_kernel.py`
- `dharma_swarm/telos_gates.py`
- `dharma_swarm/guardian_crew.py`
- `dharma_swarm/injection_scanner.py`
- `dharma_swarm/external_agent_registration.py`
- `dharma_swarm/dgm_loop.py`

Key issue: agent outputs must pass through a membrane before becoming real actions, artifacts, money claims, or source mutations.

### Model/provider routing

- `MODEL_ROUTING_MAP.md`
- `dharma_swarm/providers.py`
- `dharma_swarm/router_v1.py`
- `dharma_swarm/agent_runner.py`

Key issue: agents should request capabilities, not directly choose models/providers.

### Dashboard/API/control plane

- `api/main.py`
- `api/routers/`
- `dashboard/`
- `run_operator.sh`

Key issue: dashboard should evolve from “what is the swarm doing?” to “what customer/work order/value/deliverable is moving?”

### Commercial spine to design

Likely new domain objects, not yet implementation commitments:

- `Customer`
- `Opportunity`
- `WorkOrder`
- `Deliverable`
- `ValueEvent`
- `InvoiceRecord`
- `CaseStudy`

Key issue: money requires typed commercial metabolism: intake → work order → verified artifact → value event → invoice → renewal.

---

## 3. Encapsulation thesis

A module is not modular because it lives in a separate file. A module is modular when:

```text
1. It owns its internal state.
2. It exposes a small public API.
3. Other modules cannot mutate its internals directly.
4. Its invariants are enforced at the boundary.
5. It can be replaced without collapsing the organism.
```

Design principle:

> No module owns reality unless it owns the invariants.

Implication for Dharma Swarm:

- Python agents may propose.
- Runtime/governance cores must validate.
- Event logs and ledgers must record.
- Human/operator/customer surfaces must approve where required.

---

## 4. What may need encapsulation

Research and refine this list.

### 4.1 Runtime state transitions

Candidate invariant examples:

```text
TaskClaim cannot complete without DelegationRun evidence.
DelegationRun cannot mark delivered without ArtifactRecord.
WorkspaceLease cannot be reused after release/expiry.
ContextBundle cannot be injected unless scanned and fenced.
OperatorAction must carry actor, reason, payload, and timestamp.
```

Question: should this remain Python, move to Rust, or be shared through a small service boundary?

### 4.2 Event journal

Candidate responsibilities:

```text
append_event
validate_event_schema
compute_event_hash
verify_hash_chain
replay_events
derive_current_state
detect_missing_or_corrupt_events
```

Question: should Dharma Swarm adopt event sourcing as the primary substrate, with SQLite tables as projections?

### 4.3 Commercial value ledger

Candidate responsibilities:

```text
record_estimated_value
record_verified_value
link_value_to_evidence
link_value_to_customer_confirmation
prevent_invoice_without_deliverable_or_override
feed verified value back into routing/evolution
```

Question: what is the minimum commercial object model that creates real economic metabolism without overbuilding?

### 4.4 Provider routing and capability requests

Candidate design shift:

```text
Agent asks for capability: long_context + code_review + low_cost + tool_use
Router selects provider/model based on cost, capability, latency, failure history, and task type.
```

Question: what belongs in provider capabilities vs. routing memory vs. agent identity?

### 4.5 Tool authority and external agents

Candidate authority ladder:

```text
read_only
write_sandbox
write_branch
open_pr
merge_pr
deploy
bill_customer
contact_customer
```

Question: how do we prevent authority from being inherited through memory, prompt context, or previous identity claims?

### 4.6 High-throughput ingestion

Candidate Go plane:

```text
source connectors
polling / streaming
rate limits
retry logic
deduplication
backpressure
source health
normalized event envelope
metrics
```

Question: is Go the best first second-language move because Dharma Swarm needs a sensorium before it needs a Rust invariant kernel?

---

## 5. Language strategy hypotheses

### Hypothesis A — Rust first

Use Rust for:

```text
event journal
work-order state machine
artifact verification
value ledger
permission kernel
routing score kernel
```

Pros:

- strongest invariants
- memory safety
- excellent for impossible-state modeling
- good Python interop through PyO3/maturin

Cons:

- slower development
- higher cognitive load
- less ideal for fast connector proliferation

### Hypothesis B — Go first

Use Go for:

```text
100-source ingestion
websocket/API polling
source health probes
queue workers
metrics endpoints
high-concurrency services
single-binary daemons
```

Pros:

- excellent concurrency
- fast to build and deploy
- simple services
- strong fit for source ingestion and live telemetry

Cons:

- weaker type-level invariants than Rust
- less expressive for state-machine safety
- can still become mutable-service soup without discipline

### Hypothesis C — Python only for now

Use Python but enforce better boundaries:

```text
Pydantic schemas
private modules
public service methods only
state transition APIs
runtime contract tests
Guardian checks
```

Pros:

- fastest iteration
- no polyglot complexity
- current repo already Python-centered

Cons:

- may preserve the same failure mode
- weaker hard boundaries
- high-throughput ingestion may remain clumsy

### Hypothesis D — Go + Rust, but sequenced

Likely preferred sequence:

```text
1. Go sensorium for high-throughput source ingestion.
2. Python consumes normalized events and performs semantic orchestration.
3. Rust core later hardens event journal, work-order state machine, value ledger, and artifact verification.
```

Question: does this introduce too much architecture too early, or is it the right long-term spine?

---

## 6. Proposed AI Builder Discussion Room protocol

Use this file as the shared room. Agents should append or propose patches under the sections below. Do not scatter the discussion across random markdown files.

### Roles

Use at least these perspectives:

1. **Systems Architect** — modularity, bounded contexts, service boundaries.
2. **Go Specialist** — ingestion, concurrency, service deployment, observability.
3. **Rust Specialist** — state machines, ledgers, invariants, FFI/service boundaries.
4. **Python Runtime Maintainer** — how to integrate without breaking current runtime.
5. **DevOps/SRE** — deployment, logs, metrics, queueing, backpressure, failure modes.
6. **Commercial Architect** — customer intake, work orders, deliverables, value ledger, billing.
7. **Dharma Guardian** — telos preservation, authority boundaries, anti-drift, anti-mystification.
8. **Skeptic/Red Team** — complexity, premature optimization, polyglot risk, security risk.

### Required output from each agent

Each agent should produce:

```text
1. Strongest recommendation
2. What must be encapsulated
3. What language/runtime should own it
4. What not to build yet
5. Biggest hidden risk
6. First three implementation slices
7. How to verify the design is working
```

### Decision rule

No implementation until this room converges on:

```text
1. First money-facing pipeline
2. First encapsulated boundary
3. First non-Python component, if any
4. Integration path back into existing runtime_state / orchestrator / dashboard
5. Test and observability plan
6. Kill criteria if the experiment adds complexity without value
```

---

## 7. Candidate target architecture

Draft only.

```text
External world
  ↓
Go Sensorium
  - source adapters
  - polling/streaming
  - retries/rate limits
  - dedupe/backpressure
  - normalized events
  ↓
Event Queue / Runtime DB
  ↓
Python Dharma Swarm
  - semantic interpretation
  - task decomposition
  - LLM calls
  - agent orchestration
  - artifact creation
  ↓
Rust Dharma Core
  - event validation
  - state-machine transitions
  - artifact verification
  - value ledger
  - permission kernel
  ↓
Dashboard / Operator / Customer Surface
  - approvals
  - work orders
  - deliverables
  - verified value
  - invoices / renewals
```

Open question: Should Rust be a library called by Python, a local service, or both?

---

## 8. First money-facing pipeline to evaluate

Candidate: **AI Systems X-Ray**

```text
Customer connects repo / uploads workflow notes
  ↓
Dharma Swarm scans architecture, runtime, provider use, evals, agent flows
  ↓
Agents produce findings
  ↓
Verification membrane checks claims against evidence
  ↓
Customer-facing report is generated
  ↓
Optional implementation PRs
  ↓
Value ledger records estimated and verified savings
  ↓
Recurring monitoring retainer
```

Research questions:

```text
What exact customer pain is strongest?
What input data is required?
What can be automated today?
What needs human review?
What is a credible price?
What does the deliverable look like?
What evidence makes the report trustworthy?
How does this become recurring revenue?
```

---

## 9. Research prompts for external agents

### Prompt A — Systems architect

```text
You are entering the Dharma Swarm Encapsulation + Second-Language Strategy Room.
Read CLAUDE.md, README.md, INTERFACE_MISMATCH_MAP.md, CYBERNETIC_LOOP_MAP.md, MODEL_ROUTING_MAP.md, runtime_state.py, runtime_lifecycle.py, api/main.py, and this file.

Your task: identify the minimum encapsulation boundaries required to turn Dharma Swarm into a reliable autonomous company substrate. Focus on bounded contexts, ports/adapters, event sourcing, state machines, and anti-coupling. Do not propose implementation before mapping boundaries.

Return:
1. top 7 encapsulation boundaries
2. current repo risks
3. recommended ownership by Python/Go/Rust
4. first 3 implementation slices
5. kill criteria
```

### Prompt B — Go specialist

```text
You are the Go specialist for Dharma Swarm.
Question: should Go become the high-throughput ingestion/sensorium layer?

Research the architecture for pulling from 100+ sources continuously: GitHub, RSS, APIs, filesystem, webhooks, Discord/Slack later, provider telemetry, logs.

Design a minimal Go service that emits normalized events into Dharma Swarm without taking over semantic cognition.

Return:
1. minimal Go service design
2. event envelope
3. queue/storage recommendation
4. observability plan
5. concurrency/backpressure design
6. integration with Python runtime_state.py
7. what not to build yet
```

### Prompt C — Rust specialist

```text
You are the Rust specialist for Dharma Swarm.
Question: should Rust become the invariant kernel?

Design a minimal Rust crate/service for event validation, work-order state transitions, artifact verification, value ledger, and permission checks. Compare PyO3 library vs local service boundary.

Return:
1. exact invariants Rust should own
2. proposed crate/module layout
3. Python integration strategy
4. data model sketches
5. test strategy
6. migration path from Python
7. what not to move into Rust
```

### Prompt D — Commercial architect

```text
You are the commercial architect for Dharma Swarm.
Question: what is the first money-facing pipeline?

Evaluate AI Systems X-Ray, LLM/GPU Cost Audit, Agent Work OS Setup, and AI Governance/Verification Audit.

Return:
1. ranked wedge products
2. customer profile
3. pricing hypothesis
4. deliverable template
5. required repo capabilities
6. missing commercial objects
7. first 14-day build plan
```

### Prompt E — Skeptic / red team

```text
You are the red-team skeptic for Dharma Swarm.
Attack the plan. Assume Go/Rust/Python polyglot architecture may be premature, overcomplicated, or ego-driven.

Return:
1. strongest argument against adding Go
2. strongest argument against adding Rust
3. strongest argument against commercial objects now
4. what should be proven in Python first
5. complexity budget
6. simplest viable alternative
7. exact evidence that would change your mind
```

---

## 10. Open decision log

Append decisions here only after debate.

### Decision 001 — pending

Question: first non-Python component?

Options:

```text
A. Go sensorium first
B. Rust invariant kernel first
C. Python-only hardening first
D. No decision until AI Systems X-Ray pipeline spec is complete
```

Current status: undecided.

### Decision 002 — pending

Question: first money-facing pipeline?

Options:

```text
A. AI Systems X-Ray
B. LLM/GPU Cost Audit
C. Agent Work OS Setup
D. Governance / Verification Audit
```

Current status: undecided.

### Decision 003 — pending

Question: first encapsulated boundary?

Options:

```text
A. Event journal
B. Work-order state machine
C. Provider capability router
D. Artifact verification membrane
E. Go event ingestion envelope
```

Current status: undecided.

---

## 11. Non-goals for now

Do not build these yet:

```text
Full rewrite of Dharma Swarm
Distributed Kubernetes swarm
General-purpose custom programming language
Autonomous customer outreach without human approval
Autonomous billing without human approval
Rust rewrite of existing Python runtime
Go rewrite of dashboard/API
Complex message bus before event envelope is stable
```

---

## 12. Definition of ready to build

This strategy is ready to build only when the discussion room produces:

```text
1. One selected wedge product.
2. One selected first encapsulation boundary.
3. One selected first non-Python component, or explicit Python-only decision.
4. Concrete data model.
5. Integration points with existing repo files.
6. Test plan.
7. Observability plan.
8. Rollback plan.
9. 7-day implementation plan.
10. Human approval from Dhyana.
```

Until then, this remains research and architecture only.

---

## 13. Working mantra

> Encapsulation is how Dharma becomes executable.
>
> Go moves the world’s signals.
> Rust protects the laws.
> Python thinks, synthesizes, and speaks.
> The dashboard commands.
> The ledger remembers.
> The customer value proves the company is real.
