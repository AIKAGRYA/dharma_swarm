# Dharma Entelechy Architecture Contract v0

## Lattice, Proof, Ownership, and Acceptance Appendix

**Status:** Operator-review draft — not ratified canon and not an implementation specification
**Date:** 2026-07-13
**Document role:** `working_plan` — companion to the proposed architecture contract
**Subordinate to:** `2026-07-13_dharma_entelechy_architecture_contract_v0.md` and its named canonical owners
**Replaces:** nothing; continues sections 11–20 of the contract without creating a separate authority claim

---

## 11. Lattice Contract

The Lattice is a graph of typed, scoped, revocable edges.

An edge must identify:

- source;
- target;
- exchange type;
- purpose;
- consent;
- scope;
- data classification;
- authority implications, normally none;
- attribution;
- cost;
- expiry;
- revocation;
- evidence;
- outcome.

Initial exchange types may include:

- research;
- dataset;
- tool;
- skill;
- audience;
- referral;
- distribution;
- capital;
- compute;
- talent;
- campaign pattern;
- failure capsule;
- verification;
- outcome receipt.

The Lattice must remain reconstructable from authoritative identities, agreements, and receipts. A central graph projection may improve discovery but must not become a second source of truth.

---

## 12. Evidence and Effect Contract

### 12.1 Meaningful effect

A meaningful external effect requires:

- execution identity;
- authority reference;
- effect classification;
- idempotency or explicit duplicate policy;
- budget;
- before-state where applicable;
- effect receipt;
- verifier result;
- outcome readback;
- lineage to campaign, Cell, Organ, and Entelechy.

### 12.2 External outcomes

External outcomes include:

- money received;
- signed commitments;
- users who acted;
- independently reproduced scientific results;
- measured cost or time reduction;
- verified ecological change;
- adoption by an external institution;
- beneficiary-reported improvement with appropriate safeguards;
- code or policy accepted by an independent authority.

Internal scores, reports, registrations, heartbeats, ontology rows, or agent consensus do not by themselves establish external value.

### 12.3 Protected effects

Protected effects must fail closed when:

- identity is incomplete;
- authority is absent or expired;
- idempotency protection is required but unavailable;
- verifier requirements are unsatisfied;
- budget cannot be established;
- reversibility is misclassified.

Compatibility fail-open behavior may remain outside the protected proof lane but may not be represented as exactly-once or authority-complete.

---

## 13. State and Storage Contract

### 13.1 No new truth store

This architecture does not authorize a new Entelechy, Ecology, Honeycomb, or Lattice database.

The current runtime/ontology split must be reconciled first.

### 13.2 Authority and projection

For every field, the contract must state:

- authoritative owner;
- projection targets;
- synchronization direction;
- conflict behavior;
- freshness boundary;
- failure behavior;
- recovery process.

Best-effort synchronization may support observability but may not uphold identity or authority invariants.

### 13.3 Proposed canonical Cell identity

Before network implementation, the operator must approve:

- the canonical ontology path;
- the canonical runtime identity path;
- how one `cell_id` crosses both;
- whether room state is authoritative or projected;
- restart/load behavior;
- archive and lineage behavior.

---

## 14. DharmaGraph Contract

DharmaGraph owns durable campaign semantics, including:

- thread continuity;
- checkpoint and resume;
- history and replay;
- forks and counterfactual branches;
- retry;
- timeout and heartbeat;
- cancellation and atomic failure;
- context propagation;
- human interrupt and resume;
- cooperative drain;
- durable effect boundaries;
- receipt lineage.

DharmaGraph does not own:

- Jagat Kalyan;
- constitutional authority;
- Entelechy identity;
- ontology truth;
- portfolio selection;
- federation sovereignty;
- a universal Lattice registry.

The neutral graph engine must not be crowned as production topology merely because durability tests pass.

---

## 15. Economic Contract

Every Cell and Organ must identify one of:

- direct revenue;
- equity or asset creation;
- cost reduction;
- explicit subsidy;
- scientific value;
- ecological value;
- cultural or public value;
- enabling infrastructure whose beneficiaries and funding source are known.

Value exchanges across the Lattice require attribution. Internal transfers may support the organism but cannot be double-counted as external value.

### 15.1 Depth-before-proliferation marker

Approximately $1 million remains a directional milestone for meaningful economic traction, not a hard implementation or federation gate.

Scaling decisions must consider a portfolio of evidence:

- revenue and margin;
- durable demand;
- equity or asset value;
- independent scientific importance;
- verified welfare or ecological consequence;
- institutional adoption;
- strategic infrastructure;
- operator capacity and comprehension.

---

## 16. Proof Sequence

### Gate 0 — Canon and onboarding

Required:

- operator ratifies terminology;
- `make onboard` is green;
- no active-track ownership collision;
- no new truth store;
- current claim boundaries remain explicit.

### Gate 1 — One durable VentureCell

Required:

- one stable Cell identity across ontology, runtime, campaign, effects, and outcomes;
- unified lifecycle status;
- restart/resume;
- protected effects fail closed;
- external beneficiary;
- independent outcome;
- operator-readable state in sixty seconds.

### Gate 2 — Fully receipted seven-day campaign

Required:

- real economic, scientific, artistic, ecological, or public objective;
- hard cost and time budgets;
- process kills and provider substitution;
- no duplicated protected effects;
- at least three historical or counterfactual forks;
- human approval only at irreversible boundaries;
- external outcome readback;
- one improvement tested but not automatically promoted;
- independent verification.

### Gate 3 — Three-Cell mutualism

Required participants:

1. signal/research;
2. solution/embodiment;
3. distribution/customer/beneficiary.

Required measures:

- external outcome;
- cost;
- elapsed time;
- duplication avoided;
- value created by lateral exchange;
- isolated-execution comparison;
- identity preservation;
- consent;
- attribution;
- privacy;
- authority boundary;
- exit.

### Gate 4 — Ecology candidate

Only after Gate 3 may an Ecology identity or runtime projection be proposed.

### Gate 5 — Honeycomb pilot

Only after one independently operated partner Entelechy exists with:

- explicit human keyholder;
- durable identity;
- scoped federation agreement;
- revocable exchange;
- independent verification;
- tested withdrawal and exit.

### Gate 6 — Living Nobel pilot

Only after multiple externally successful campaigns demonstrate:

- credible Prize Question selection;
- portfolio comparison;
- external judging;
- value reinvestment;
- cross-campaign learning;
- governance that remains legible to participating humans.

---

## 17. Current Owner Mapping

This contract should be hardened through existing owners rather than a new active track:

- **Session entry:** `docs/governance/BUILD_SESSION_ENTRYPOINT.md` plus the
  onboarding implementation. The hardening campaign is closed; edit admission
  remains packet-bound.
- **Cell/runtime/ontology identity:** `organism-rewire-2026-07`
  (`docs/governance/ACTIVE_TRACK.yaml:764-805`).
- **Durable campaign control:** `dharmagraph-engine-2026-07`
  (`docs/governance/ACTIVE_TRACK.yaml:885-926`).
- **Effect and constitutional safety:** `sovereign-safety-tcb-2026-07`
  (`docs/governance/ACTIVE_TRACK.yaml:1301-1345`).
- **Receipted closure:** `loop-closure-2026-06`
  (`docs/governance/ACTIVE_TRACK.yaml:137-175`).
- **External proof membrane:** `darshan-publication-2026-07`
  (`docs/governance/ACTIVE_TRACK.yaml:2061-2124`).
- **Comparative measurement only:** orchestration arena, hyperbolic chamber,
  and company-builder parity
  (`docs/governance/SOVEREIGN_MANIFEST.md:31-50`).
- **Operator comprehension/support:** Helm and Merge Master Mike
  (`docs/governance/SOVEREIGN_MANIFEST.md:33-40`).

No new Lattice or Entelechy implementation track should open while the active
portfolio remains at its configured maximum
(`docs/governance/SOVEREIGN_MANIFEST.md:25-52`).

---

## 18. Explicit No-Build Decisions

Until the proof gates are satisfied, do not build:

- autonomous website or team spawning as a general capability;
- a macro-Lattice runtime;
- an Ecology registry;
- a Honeycomb authority service;
- a new Entelechy database;
- automatic capital allocation across Cells;
- cross-Entelechy ambient authority;
- automatic production evolution;
- Living Nobel productization;
- a second scheduler, bus, registry, or truth system.

Narrow experiments may use existing primitives when they directly support a named proof and remain reversible, receipted, and operator-approved.

---

## 19. Operator-Confirmed, Provisional, and Open

### Operator-confirmed in the current vision round

- `Dharma Seat` is rejected.
- `Dharma Entelechy` is the provisional name for the higher-order human–AI union.
- The Entelechy sits beneath Jagat Kalyan and the axioms.
- Ratification may recede through earned trust and reversibility.
- Verification remains permanent.
- Cell means VentureCell.
- Organs, Ecologies, Honeycomb, and Lattice are composition/federation strata, not new constitutional layers.
- Upward and lateral flows carry evidence, value, capability, and requests—not ambient authority.
- Approximately $1 million is a directional marker of deep value, not a hard gate.

### Provisional

- Exact identifier and ontology representation for Entelechy.
- Whether the Honeycomb federates Entelechy identities directly or Swarm identities acting for them.
- Exact canonical VentureCell status enum.
- Exact Organ representation.
- Which existing store owns each projected field.

### Open

- Succession when a human operator dies or becomes unavailable.
- Multiple-human Entelechies and community-held authority.
- Legal identity and ownership of Entelechy-created assets.
- Dispute resolution across federated Entelechies.
- Economic settlement and attribution protocols.
- Privacy-preserving shared learning.
- Conditions under which an Entelechy may split, merge, or remain dormant.
- How spiritual language is represented without becoming an executable authority claim.

---

## 20. Contract Acceptance Standard

This contract is ready to inform implementation only when:

1. the operator ratifies the vocabulary and open constitutional decisions;
2. each invariant has an existing owner;
3. every proposed identifier has a source-of-truth rule;
4. no section requires a new store merely to make the diagram convenient;
5. one narrow campaign can exercise the contract without macro-topology changes;
6. failure modes are observable and fail closed where consequences require it;
7. external outcome and human comprehension remain the final admission criteria.

The architecture succeeds when it enables deeper actualization and greater external service while making authority, evidence, consequence, and exit more—not less—legible.
