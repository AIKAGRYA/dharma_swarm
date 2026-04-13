# SHAKTI ZEITGEIST EXECUTIVE SPEC

Status: proposed runtime spec
Scope: live `_lf5` daemon integration
Date: 2026-04-13

## Purpose

`ShaktiZeitgeistExecutive` is the swarm's strategic executive layer.

It exists to convert:

- external zeitgeist
- internal capability awareness
- mission continuity
- GNANI constitutional guidance
- OMEGA pain and divergence signals

into:

- ranked opportunities
- bounded campaigns
- domain allocation weights
- dispatch and evolution pressure toward real-world leverage

This layer is not a worker. It is not another broad philosophy module. It is a runtime allocator that keeps the swarm from collapsing into internal-maintenance eddies.

## Hierarchy

The intended control hierarchy is:

1. `GNANI`
Truth, witness, identity, non-delusion, constitutional ceiling.

2. `ShaktiZeitgeistExecutive`
Strategic sensing, leverage hunting, campaign creation, budget allocation, world-pulse orientation.

3. `OMEGA`
Pain, coherence, homeostasis, drift and divergence correction, operational brake and rebalance input.

4. `OperationalSwarm`
Agents, research, DGM, archaeology, builds, publishing, sub-swarms.

Implementation note:
`OMEGA` remains a hard constraint and corrective input. `ShaktiZeitgeistExecutive` should consume Omega signals and remain bounded by GNANI.

## Why This Exists

The live swarm currently exhibits an internal-attractor pattern:

- dense internal traces are easier to detect than world opportunities
- archive and stigmergy reinforce recent local seams
- local code and maintenance pressure is concrete and machine-readable
- high-level telos exists, but is not compiled strongly enough into allocation

The result is a stable but inward-drifting organism.

`ShaktiZeitgeistExecutive` exists to restore:

- strategic hunger
- opportunity sensitivity
- domain balance
- real-world leverage
- artifact-producing orientation

## Non-Goals

This layer must not become:

- a replacement for GNANI
- a replacement for OMEGA
- a new all-powerful daemon
- a freeform chatbot persona
- a second orchestrator
- a speculative rewrite of the full repo

It should be a compact strategic layer with clear runtime authority.

## Existing Runtime Threads To Collapse

This spec intentionally reuses and unifies existing work.

### Primary donor

`/Users/dhyana/dharma_swarm_lf5/dharma_swarm/thinkodynamic_director.py`

This is the strongest existing ancestor. It already contains:

- altitude model: `SUMMIT`, `STRATOSPHERE`, `GROUND`
- cycle: `VISION -> SENSE -> PROPOSE -> COMPILE -> DELEGATE -> MONITOR -> ASCEND`
- leverage-oriented project archetypes
- real mission and campaign continuity hooks

### Environmental sensing

`/Users/dhyana/dharma_swarm_lf5/dharma_swarm/zeitgeist.py`

This is already the S4 environmental intelligence seam. It should become the sensing subsystem, not remain a side utility.

### Mission and campaign continuity

`/Users/dhyana/dharma_swarm_lf5/dharma_swarm/mission_contract.py`
`/Users/dhyana/dharma_swarm_lf5/dharma_swarm/mission_garden.py`

These already define mission state, campaign artifacts, execution briefs, and cultivation jobs. They should become the state backbone for executive continuity.

### Constraint and constitutional inputs

`/Users/dhyana/dharma_swarm_lf5/dharma_swarm/organism.py`
`/Users/dhyana/dharma_swarm_lf5/dharma_swarm/algedonic_activation.py`

These provide the homeostatic and pain signals that the executive must consume.

### Policy and exploration guide

`/Users/dhyana/dharma_swarm_lf5/specs/research_living_layers/research_shakti_creative_autonomy.md`

This contains the correct exploration philosophy:

- proactive opportunity generation
- novelty vs interestingness
- bounded autonomy
- opportunity archives
- creative and strategic diversity

The executive should instantiate this pragmatically rather than re-describe it.

## New Module Boundary

Add:

`/Users/dhyana/dharma_swarm_lf5/dharma_swarm/shakti_zeitgeist_executive.py`

This module should orchestrate existing subsystems and own executive state.

Suggested top-level types:

- `ShaktiZeitgeistExecutive`
- `ExecutiveSignalBundle`
- `OpportunityCandidate`
- `StrategicCampaign`
- `AllocationWeights`
- `ExecutiveSnapshot`

Suggested helper components:

- `ExecutiveSignalIngestor`
- `OpportunityRanker`
- `CampaignCompiler`
- `AllocationPolicy`
- `ExecutiveStateStore`

## Runtime Responsibilities

`ShaktiZeitgeistExecutive` should do six things:

1. Continuously sense external and internal opportunity.
2. Rank opportunities by leverage and world-value.
3. Detect domain starvation and internal over-concentration.
4. Mint bounded campaigns from the highest-value opportunities.
5. Emit allocation weights that influence dispatch and DGM.
6. Persist concise executive briefs and state artifacts.

## Inputs

The executive should ingest the following signal classes.

### A. External / zeitgeist signals

- `ZeitgeistScanner.scan()` results
- research artifacts and synthesis briefs
- repo and ecosystem scans
- competition and tool-release observations
- opportunity, threat, methodology, and trend signals

### B. Internal swarm signals

- loop health
- idle persistent agent counts
- artifact creation rates
- archive concentration
- recent gauntlet pressure
- provider availability and cost mix
- runtime failures and anomaly summaries

### C. Mission and campaign signals

- active mission state
- active campaign state
- mission garden outputs
- operator-directed priorities
- lodestone and telos briefings

### D. Constitutional and pain signals

- GNANI seed state and lodestone outputs
- Omega divergence
- failure rate
- telos drift
- self-model gap
- ontological drift

### E. Capability signals

- available strong model lanes
- repo surfaces available for action
- research and build throughput
- persistent named agent roster

## Output Artifacts

The executive must emit stable runtime artifacts under `~/.dharma/meta/`.

Add:

- `~/.dharma/meta/shakti_executive_state.json`
- `~/.dharma/meta/opportunity_board.json`
- `~/.dharma/meta/allocation_weights.json`
- `~/.dharma/meta/active_campaigns.json`
- `~/.dharma/meta/executive_briefs/YYYY-MM-DDTHHMMSS.md`

### `shakti_executive_state.json`

Contains:

- last cycle timestamp
- signal summary
- domain balance summary
- top opportunity ids
- top campaigns
- current allocation weights
- last advisory or hold flags

### `opportunity_board.json`

Contains ranked `OpportunityCandidate` records:

- `id`
- `title`
- `domain`
- `source_signals`
- `why_now`
- `telos_alignment`
- `world_value`
- `leverage`
- `novelty`
- `urgency`
- `capability_fit`
- `artifact_potential`
- `cost_efficiency`
- `internal_churn_penalty`
- `repetition_penalty`
- `final_score`

### `allocation_weights.json`

Contains soft-control weights for the live runtime:

- per-domain weights
- per-source weights
- per-loop pressure multipliers
- per-campaign boosts
- over-concentration penalties

### `active_campaigns.json`

Contains bounded `StrategicCampaign` records:

- `id`
- `title`
- `goal`
- `domain`
- `why_now`
- `entry_conditions`
- `success_conditions`
- `artifact_contract`
- `preferred_agents`
- `preferred_models`
- `budget_hint`
- `status`
- `review_cadence`

### Executive brief

A concise markdown artifact for operator visibility:

- strongest opportunity
- strongest risk
- domains being starved
- what is being deprioritized
- campaigns activated
- why the current allocation changed

## Opportunity Scoring Model

Each opportunity should be ranked with an explicit multi-factor score.

Required dimensions:

- `telos_alignment`
- `world_value`
- `leverage`
- `novelty`
- `urgency`
- `capability_fit`
- `artifact_potential`
- `strategic_compounding`
- `cost_efficiency`
- `domain_balance_bonus`
- `internal_churn_penalty`
- `repetition_penalty`

Interpretation:

- high telos, leverage, artifact potential, and capability fit should dominate
- novelty matters, but only if it is interestingly new
- repeated touching of already-dominant seams should be penalized
- internal work should be demoted when external-value domains are starved

## Domain Balance

The executive must explicitly track recent effort distribution across domains.

Initial domain set:

- `internal_maintenance`
- `reliability`
- `research`
- `artifact_publication`
- `productization`
- `ecosystem_scan`
- `revenue_exploration`
- `strategic_infrastructure`

Each cycle should compute:

- share of recent work by domain
- share of recent artifacts by domain
- share of recent spend by domain
- starvation score by domain

The executive should then:

- increase pressure on starved but high-value domains
- decrease pressure on overserved internal-maintenance domains

## Campaign Model

The executive should mint campaigns instead of only scoring isolated tasks.

`StrategicCampaign` should include:

- `id`
- `title`
- `goal`
- `domain`
- `why_now`
- `thesis`
- `entry_conditions`
- `success_conditions`
- `artifact_contract`
- `preferred_models`
- `preferred_agents`
- `budget_hint`
- `review_cadence`
- `expires_at`

Campaigns should be small enough to execute and review, but large enough to alter swarm behavior for multiple cycles.

## Integration With Existing Runtime

### In `swarm.py`

- initialize `ShaktiZeitgeistExecutive`
- run an executive cycle on a fixed cadence, recommended every 30 to 60 minutes
- expose executive summary through health/read-model surfaces
- allow the executive to publish a single current snapshot into runtime state

### In `orchestrator.py`

Consume `allocation_weights.json` or the in-memory equivalent to:

- boost campaign-linked tasks
- penalize internal-only churn when maintenance is overserved
- boost tasks with strong artifact contracts
- prefer tasks in starved but high-value domains

### In `dgm_loop.py`

Use executive weights to:

- demote mutation monoculture
- privilege strategically relevant files and domains
- reward changes that unlock artifacts, campaigns, or world-facing progress

### In provider and routing logic

Use executive priorities to reserve stronger cheap/free models for:

- high-leverage campaigns
- world-facing research
- synthesis and opportunity evaluation

## Relationship To GNANI And OMEGA

### GNANI

GNANI remains the constitutional witness.

The executive must not override:

- truthfulness
- non-delusion
- telos integrity
- explicit holds

GNANI should remain the final ceiling.

### OMEGA

Omega remains the pain and divergence substrate.

The executive must consume Omega signals as hard inputs:

- when divergence spikes, reduce exploration pressure
- when coherence weakens, favor rebalancing and repair
- when telos drift appears, route energy into reorientation

Omega should constrain and redirect executive hunger, not replace it.

## Cadence

Recommended initial cadence:

- executive cycle every 45 minutes
- opportunity refresh every cycle
- campaign review every 3 cycles
- domain-balance recomputation every cycle
- operator-facing executive brief every cycle

This cadence is fast enough to matter and slow enough to avoid thrash.

## Phase Plan

### Phase 1: Read-only executive

Build:

- signal ingestion
- opportunity ranking
- domain-balance accounting
- executive artifacts and briefs

Do not yet control dispatch.

Success criteria:

- stable artifact emission
- meaningful opportunity ranking
- visible domain-balance diagnostics

### Phase 2: Soft runtime influence

Add:

- task scoring boosts and penalties
- DGM weighting input
- domain starvation correction

Success criteria:

- reduced internal-churn share
- broader campaign distribution
- more artifact-producing work selected

### Phase 3: Campaign authority

Add:

- bounded campaign minting
- per-campaign resource hints
- preferred agent/model routing

Success criteria:

- multiple cycles of campaign-driven behavior
- clearer operator-facing strategic direction

### Phase 4: Fractal expansion

Later, allow:

- company-local executives
- sub-swarm executives
- portfolio-level central executive

This phase is explicitly out of scope for the first implementation.

## Tests To Reuse

These existing tests already cover adjacent behavior and should guide implementation:

- `/Users/dhyana/dharma_swarm_lf5/tests/test_thinkodynamic_director.py`
- `/Users/dhyana/dharma_swarm_lf5/tests/test_zeitgeist.py`
- `/Users/dhyana/dharma_swarm_lf5/tests/test_mission_garden.py`
- `/Users/dhyana/dharma_swarm_lf5/tests/test_mission_contract.py`
- `/Users/dhyana/dharma_swarm_lf5/tests/test_shakti.py`
- `/Users/dhyana/dharma_swarm_lf5/tests/test_shakti_darwin_integration.py`
- `/Users/dhyana/dharma_swarm_lf5/tests/test_operator_views.py`

Add new tests:

- `tests/test_shakti_zeitgeist_executive.py`
- `tests/test_shakti_zeitgeist_executive_integration.py`

Required new test cases:

- opportunity ranking favors world-value over internal churn
- domain starvation raises weights for neglected domains
- repetitive local seam pressure is penalized
- campaigns compile from top-ranked opportunities
- executive outputs serialize cleanly
- executive weights influence orchestrator selection

## First Implementation Slice

The smallest high-value slice is:

1. add `shakti_zeitgeist_executive.py`
2. ingest `thinkodynamic_director`, `zeitgeist`, mission state, omega signals
3. emit `opportunity_board.json`, `allocation_weights.json`, and one executive brief
4. wire orchestrator to read the resulting soft weights

That is enough to begin changing behavior without destabilizing the daemon.

## Do Not Build Yet

Do not build yet:

- a separate executive daemon
- a full RTN rewrite
- a multi-company portfolio controller
- a new ontology system
- a large dashboard redesign
- a broad repo merge

The first implementation should be minimal, hot-path relevant, and measurable.

## Implementation Decision

The correct build approach is:

- runtime truth: `_lf5`
- donor seam: `thinkodynamic_director`
- sensing seam: `zeitgeist.py`
- continuity seam: `mission_contract.py` and `mission_garden.py`
- constraint seam: `organism.py` and `algedonic_activation.py`
- policy guide: `research_shakti_creative_autonomy.md`

This layer should be implemented as an authoritative strategic allocator, not as a new theory document.
