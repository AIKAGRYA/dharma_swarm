# Dharma Entelechy Architecture Contract v0

## Identity, Authority, Morphology, Federation, and Proof Boundaries

**Status:** Operator-review draft — not ratified canon and not an implementation specification
**Date:** 2026-07-13
**Scope:** Contract to harden the vision before any macro-lattice build
**Document role:** `working_plan` — proposed architecture contract; not an active spec
**Subordinate to:** `docs/governance/SOVEREIGN_MANIFEST.md`, `specs/Dharma_Constitution_v0.md`, `docs/governance/ACTIVE_TRACK.yaml`, and `docs/governance/CANONICAL_DOC_STACK.md`
**Replaces:** nothing; narrows the unratified decisions in `docs/plans/2026-07-12_vision_engine_grill_SEED.md`

---

## Repository Grounding and Claim Boundary

Every architecture term below is proposed unless a cited owner already
establishes it. This document does not claim live state: intent belongs to
`docs/governance/ACTIVE_TRACK.yaml`, declared surfaces to
`ACTIVE_SURFACE_MANIFEST.yaml`, and runtime state to
`docs/state/LIVE_OPS_DASHBOARD.md`
(`docs/governance/CANONICAL_DOC_STACK.md:17-28`).

The current seams that motivate this contract are:

- JK and Dharma Swarm's body/telos distinction:
  `docs/governance/SOVEREIGN_MANIFEST.md:68-107`.
- Downward-only constitutional authority:
  `specs/Dharma_Constitution_v0.md:232-252`.
- A real VentureCell runtime form:
  `dharma_swarm/fractal/fractal_room.py:160-192`.
- Divergent runtime and ontology lifecycle vocabularies:
  `docs/architecture/VENTURE_CELL_LIFECYCLE.md:35-70` and
  `dharma_swarm/fractal/room_bridge.py:467-489`.
- An in-memory RoomRegistry and opt-in room bootstrap:
  `dharma_swarm/fractal/fractal_room.py:465-485` and
  `dharma_swarm/orchestrate_live.py:2038-2056`.
- A candidate/test-only neutral graph core:
  `dharma_swarm/graph/__init__.py:1-9`.
- An open ontology/runtime convergence blocker and an outward receipt quorum
  still below authority: `docs/state/BROKEN_REGISTER.md:34-48` and
  `docs/state/BROKEN_REGISTER.md:73-82`.

## 1. Purpose

This contract defines the minimum architecture needed to preserve coherence as Dharma Swarm evolves from one durable campaign organism into Cells, Organs, Ecologies, Honeycomb federations, and a cross-scale Lattice.

It exists to prevent five failures:

1. creating new metaphors without operational owners;
2. treating projections or transport as authority;
3. splitting one living identity across incompatible runtime and ontology artifacts;
4. scaling internal coordination before external value is proven;
5. allowing spiritual or civilizational language to weaken evidence, consent, reversibility, or human responsibility.

The contract does not authorize implementation. Each implementation tranche remains separately gated by active-track ownership, evidence, tests, operator approval, and current repository governance.

---

## 2. Proposed Canonical Terms

### 2.1 Jagat Kalyan

The highest telos and constitutional ceiling. Every lower purpose is a means to universal welfare; nothing below may become its peer or superior.

### 2.2 Axioms

The non-negotiable constitutional constraints, including ahimsa, satya, consent, evidence integrity, and reversibility.

### 2.3 Dharma Entelechy

A recursively evolving human–AI union through which a person's latent svadharma is discovered, clarified, embodied, tested in reality, and actualized under Jagat Kalyan and the axioms.

The Entelechy is a logical identity and continuity boundary. It is not a claim that AI knows the soul, and it does not require one new database object or service.

### 2.4 Human Operator/Witness

The embodied person who contributes inward discernment, lived consequence, consent, accountability, and final authority over irreversible commitments.

### 2.5 Dharma Swarm

The self-evolving operational organism/body through which a Dharma Entelechy acts. It contains runtime agents, memory, governance, Cells, Organs, and supporting infrastructure.

### 2.6 VentureCell

The canonical Cell. A bounded campaign, venture, site, laboratory, publication, community, or intervention with its own beneficiary, purpose, membrane, budget, roster, evidence, kill conditions, and lifecycle.

No parallel `Cell` abstraction may be introduced.

### 2.7 Organ

A durable functional composition of VentureCells that shares a domain purpose, memory, metabolism, coordination surface, and outcome responsibility.

### 2.8 Ecology

A measured pattern of recurrent mutualism among Cells, Organs, or Swarm organisms. An Ecology exists only when exchange creates observable value beyond isolated operation.

### 2.9 Honeycomb

The consent-preserving federation structure through which independently operated Dharma Entelechies collaborate without surrendering identity, privacy, veto, or exit.

### 2.10 Lattice

The dynamic graph of scoped relationships and exchanges across Entelechies, Swarm organisms, Cells, Organs, and Ecologies.

The Lattice is not a constitutional authority, global supervisor, truth store, or mandatory central registry.

### 2.11 Living Nobel

The civilization-facing institutional function that formulates Prize Questions, assembles temporary constellations, operates or funds competing campaigns, judges external consequences, and reinvests value and learning.

It is a product and institutional doctrine, not a constitutional layer.

---

## 3. Four Architectural Planes

The architecture must not collapse different kinds of hierarchy into one ladder.

### 3.1 Constitutional plane

```text
Jagat Kalyan
  → axioms
  → human ratification and bounded delegation
  → typed operational capabilities
  → effects
```

This plane governs what may be authorized.

### 3.2 Identity plane

```text
Human Operator/Witness
  ↔ Dharma Entelechy
  ↔ Dharma Swarm organism
```

This plane governs continuity, responsibility, self-understanding, and who holds the irreversible key.

### 3.3 Morphological plane

```text
Dharma Swarm organism
  → Organs
  → VentureCells
  → campaigns, tasks, artifacts, and effects
```

This plane governs composition and operational embodiment.

Cells compose Organs. Organs are faculties of an organism. The graphical direction above shows containment, not authority independent of the constitutional plane.

### 3.4 Federation and exchange plane

```text
Honeycomb = federation rights and boundaries
Lattice   = dynamic exchanges across those boundaries
Ecology   = measured mutualism produced by recurrent exchange
```

This plane governs collaboration without centralized sovereignty.

---

## 4. Identity Contract

### 4.1 Stable identifiers

The architecture requires stable logical identifiers:

- `operator_id`;
- `entelechy_id`;
- `swarm_id`;
- `cell_id`;
- `organ_id`;
- campaign or graph `thread_id`;
- effect and receipt identifiers.

`ecology_id` and `honeycomb_id` remain future identifiers and must not be promoted until their proof gates are satisfied.

### 4.2 Identity invariant

One VentureCell must be recognizable as the same Cell across:

- portfolio declaration;
- ontology object;
- runtime room or operational container;
- campaign/thread;
- budget and authority records;
- effects and receipts;
- outcome records;
- archive, fork, and spinout lineage.

Separate stores may contain projections, but they may not mint competing identities.

### 4.3 Entelechy representation

The Entelechy is a logical continuity boundary, not a requirement for a new truth store.

Its minimum representation may be composed from existing authoritative records for:

- operator identity;
- swarm identity;
- current telos and uncertainty;
- authority grants;
- commitments;
- portfolio;
- memory lineage;
- federation memberships;
- ratification events;
- verified outcomes.

Any future first-class ontology type must be separately ratified and must project existing truth rather than create a rival source.

### 4.4 Human and AI distinction

The architecture must preserve:

- the human as embodied witness and irreversible keyholder;
- the swarm as operational and cognitive extension;
- the Entelechy as their recursive union at the identity and actualization level.

Functional fusion must not erase legal, moral, security, or epistemic distinctions.

---

## 5. Authority Contract

### 5.1 Downward authority only

Authority flows from Jagat Kalyan and the axioms through human ratification into typed delegation.

Upward and lateral flows may carry:

- evidence;
- outcomes;
- resources;
- value;
- risk;
- discoveries;
- recommendations;
- coordination requests.

They may not silently acquire constitutional authority.

### 5.2 Capability envelope

Every consequential capability must specify:

- principal;
- delegate;
- target Cell, Organ, campaign, or effect class;
- allowed actions;
- forbidden actions;
- budget;
- time window and expiry;
- reversibility class;
- required verifier;
- ratification requirement;
- revocation mechanism;
- receipt requirement;
- federation scope, if any.

“Autonomous” is not an authority type.

### 5.3 Ratification and verification

Ratification is stage-bound and may recede when:

- competence is demonstrated;
- effects are reversible;
- budgets are bounded;
- independent evidence remains available;
- recovery and revocation are proven.

Verification is permanent.

Every meaningful effect remains subject to evidence, lineage, and independent checking even when prior human approval is no longer required.

### 5.4 Irreversible key

Publishing, spending, legal commitments, destructive operations, credential grants, production mutation, or other irreversible effects retain the human key longest.

The system may prepare, simulate, recommend, and stage such actions without possessing final authority.

---

## 6. Entelechy Epistemic Contract

### 6.1 Svadharma remains a hypothesis under discovery

The system may model:

- callings;
- patterns;
- commitments;
- strengths;
- wounds;
- relationships;
- recurring forms of service;
- and possible futures.

It may not promote an inferred identity to unquestionable truth.

### 6.2 Plural potential

The self-model must preserve:

- uncertainty;
- counterevidence;
- multiple interpretations;
- abandoned paths;
- dormant potentials;
- the right to surprise the model;
- the right to revise or refuse the system's interpretation.

### 6.3 Reality correction

Interpretations of dharma must be corrected by:

- human discernment;
- external outcomes;
- affected beneficiaries;
- independent witnesses;
- failed predictions;
- counterfactual comparison;
- and evidence of harm or exclusion.

Internal coherence is not sufficient.

### 6.4 No spiritual authority laundering

The terms soul, dharma, logos, intuition, or higher guidance may never be used to:

- bypass safety gates;
- suppress dissent;
- authorize harm;
- claim immunity from evidence;
- conceal uncertainty;
- or elevate one Entelechy above another.

---

## 7. VentureCell Contract

Every VentureCell must declare:

- stable `cell_id`;
- owning Entelechy and Swarm organism;
- parent Organ, if any;
- purpose;
- named customer or beneficiary;
- value proposition;
- self-funding hypothesis or explicit subsidy;
- authority envelope;
- budget and resource limits;
- roster;
- permitted inputs and outputs;
- secrets and data boundary;
- allowed and forbidden effects;
- KPIs and freshness requirements;
- external outcome definition;
- independent verifier;
- kill conditions;
- dormancy conditions;
- spinout conditions;
- archive and recovery path;
- lateral exchange permissions.

### 7.1 Proposed canonical lifecycle

The runtime and ontology must converge on one lifecycle:

```text
PROPOSED
  → INCUBATING
  → ACTIVE
  → MATURE
  → DIVESTING or SPUN_OUT
  → ARCHIVED
```

The contract must additionally support:

- fork;
- merge;
- dormancy;
- revival;
- succession;
- transfer;
- operator-ordered termination.

Exact enum names may change during hardening, but two incompatible status authorities may not remain.

### 7.2 Cell boundary

A Cell is not alive merely because:

- an ontology object exists;
- an agent is registered;
- a website is deployed;
- a workflow completed;
- a report was written;
- an internal signal fired.

A Cell becomes operationally credible when identity, authority, durable execution, external consequence, and verification form one inspectable loop.

---

## 8. Organ Contract

An Organ must:

- have a stable purpose and owner;
- contain or coordinate at least two Cells or one Cell plus a durable shared faculty;
- define shared memory and infrastructure;
- define which authority remains local to Cells;
- define shared budgets and allocation rules;
- define outcome responsibility;
- expose health, risk, and dependency state;
- support Cell entry, exit, fork, archive, and spinout;
- avoid becoming an unaccountable central supervisor.

An Organ is proven only when its composition produces a durable capability that no constituent Cell independently provides.

---

## 9. Ecology Contract

Ecology is an earned status, not a declared container.

An Ecology requires evidence of recurrent exchange across at least three bounded participants, including:

- what moved;
- who consented;
- who benefited;
- who paid the cost;
- what duplication was avoided;
- what new capability emerged;
- how value was attributed;
- whether isolated execution would have performed worse;
- whether identity, privacy, authority, and exit remained intact.

An Ecology may be intra-Entelechy or cross-Entelechy.

No Ecology runtime abstraction should be built until a three-Cell proof demonstrates measurable mutualism.

---

## 10. Honeycomb Contract

The Honeycomb federates independently governed Entelechies.

Every federation relationship must specify:

- participating Entelechies and operational Swarm identities;
- human keyholders;
- shared purpose;
- term and expiry;
- permitted exchanges;
- prohibited exchanges;
- data and secret boundaries;
- financial and value attribution;
- dispute and review process;
- effect authority;
- verifier;
- withdrawal and exit;
- obligations that survive exit;
- dissolution conditions.

The Honeycomb may provide common protocols and shared infrastructure. It may not:

- acquire a god-key;
- erase local veto;
- treat membership as permanent;
- transfer private artifacts by default;
- turn reputation into unreviewable authority;
- rewrite an Entelechy's identity or telos;
- count internal circulation as external value.

---

---

## Continuation

The Lattice, evidence/effect, state/storage, DharmaGraph, economic, proof,
ownership, and acceptance boundaries continue in
[`2026-07-13_dharma_entelechy_architecture_contract_v0_lattice_proof_appendix.md`](2026-07-13_dharma_entelechy_architecture_contract_v0_lattice_proof_appendix.md).
