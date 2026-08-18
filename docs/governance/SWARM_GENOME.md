# SWARM GENOME

Purpose: first-token map for a new human or agent entering Dharma Swarm.
This file is a projection-only front door. It does not own live state,
runtime receipts, active track truth, agent identity, or doctrine.

## 10-Second Identity

**Jagat Kalyan** (universal welfare) is the ceiling. **Dharma Swarm** is the
operational organism/body that enacts it — not itself the telos. It is
binocular: Sakshi (Witness, inward lucidity) and Drishti (Seer, outward
vision), and every loop closes through reality. Human authority, consent,
uncertainty, plurality, and exit remain intact.

The organism is plural. Ten irreducible dimensions are all real roots, each
carried at its honest maturity (never over-claimed):

1. human actualization — durable continuity/agency for a human's latent dharma *(proposed)*
2. self-recognition — does knowing what it is change behavior? *(research)*
3. organismic viability — persist across models, restarts, forks, operator absence *(ratified)*
4. creative intelligence — exceed the best member without collapsing diversity *(ratified)*
5. metabolism — acquire/reinvest energy without betraying telos *(ratified)*
6. world service — inward intelligence becomes consequential action *(ratified)*
7. public meaning — propagate wisdom without propaganda or sludge *(ratified)*
8. reproduction/federation — Cells, Organs, Ecologies, sovereign federations *(envisioned)*
9. civilizational evolution — institutions/breakthroughs worthy of humanity *(envisioned)*
10. telos/conscience — power grows while telos and human authority stay upstream *(ratified)*

The governance spine below (authority, identity, receipts) is the organism's
immune/nervous system — necessary, but not the whole being. Its core discipline
stays: every claim knows its owner, every side effect has identity, every
completion claim points to a receipt, and attractive prose never outruns them.

> The typed, content-addressed form of this identity is the invariant Organism
> Boot Packet (`dharma_swarm/orientation_packet.py`), injected before an
> agent's first token on every provider. Both this document and that packet are
> **projections**, not authority. The authority sources — the ratified kernel
> axioms, doctrine, and the human operator — always win. If a projection drifts
> from the authority sources (or the two projections drift from each other),
> the projection is wrong and must be repaired; neither projection may
> overrule an authority source.

## What This Map Is

- A compact orientation map.
- A list of what to read next.
- A claim-language firewall.
- A reminder that the Runtime Truth Spine already exists.

## What This Map Is Not

- Not a source of live truth.
- Not a replacement for `ACTIVE_TRACK.yaml`.
- Not a command ledger.
- Not a dashboard.
- Not an agent identity or SOUL file.
- Not permission to run autonomous loops.

## Whole Organism Map

The organism has several organs. Treat each as owning a narrow truth.

1. Intent: `docs/governance/ACTIVE_TRACK.yaml`
   - Owns active tracks, acceptance criteria, surfaces, and non-goals.
   - `make onboard` projects it, but does not own it.

2. Runtime truth: `dharma_swarm/runtime_state.py` plus spine modules
   - Owns persisted runtime receipts, execution identity, idempotency, and
     runtime state rows.
   - `spine.EvidenceReceipt` is dispatch proof.
   - `RuntimeReceipt` is persisted runtime proof.
   - `IdempotencyRecord` is the exactly-once substrate.

3. Dispatch spine: `dharma_swarm/spine/`
   - Owns canonical identity, receipts, invocation, and tollbooth gates.
   - Do not create parallel command-spine abstractions.

4. Projection surfaces: onboarding, dashboards, reports, cards
   - Show current interpretation of owner facts.
   - They are allowed to be useful.
   - They are not authority.

5. Governance and doctrine: `docs/governance/`, `docs/doctrine/`
   - Owns stable rules, not live status.
   - Doctrine should point to owners when state can change.

6. Board and control surface: `dharma_swarm/board/`, `api/routers/control_surface.py`
   - Projects work, receipts, and attention states.
   - Must distinguish sent, delivered, domain receipt, semantic reply, and
     completed.

7. Value and revenue: Telic value, RevenueSpine, venture docs
   - May project signals.
   - Must not claim self-funding or market proof without external receipts.

## Active Objective Coverage

As of the latest onboard evidence available to this branch:

- Runtime truth reconciliation is active.
- NATS/runtime truth work is active.
- Revenue/external-human proof is not covered by an active track here.
- Research-depth proof is not covered by an active track here.

Always rerun `make onboard` before citing this.

## Custody Labels

Use these labels when describing any claim:

- OWNER: the file, DB table, script, or external system that owns the fact.
- PROJECTION: a derived view over owner facts.
- RECEIPT: durable proof created by the owner path.
- AMBER: plausible but missing a required proof edge.
- RED: false, unsafe, forged, or contradicted by owner evidence.
- EXTERNAL-GATED: needs human approval or outside-system proof.
- HISTORICAL: useful background, not current authority.

## Forbidden Overclaims

Do not say:

- "the system is self-funding" without payment or revenue ledger receipts;
- "external humans are served" without outreach, approval, reply, or artifact proof;
- "runtime truth is fully saturated" while default paths still bypass identity or receipts;
- "A2A collaboration happened" from broker publish alone;
- "handler ack means semantic reply";
- "green AgentOps means runtime-bound" without runtime truth refs;
- "deployed equals main" without deploy provenance;
- "Forge/Hydra is runnable" without a fresh run receipt;
- "Chetana is main-owned canon metabolism" without main-owned owner proof;
- "live trading authority exists" without explicit human/legal exchange authority.

## Allowed Claim Language

Say:

- "projected by onboarding";
- "observed in this checkout";
- "runtime receipt present";
- "idempotency claimed before side effect";
- "handler ack only";
- "domain receipt present";
- "semantic reply claimed by typed payload";
- "AMBER until receipt X exists";
- "RED until owner Y contradicts this."

## Strongest Weak Spots

1. Claim inflation
   - Vision language can outrun receipts.
   - Use `REALITY_DEBT_LEDGER.md`.

2. Command cutover gaps
   - Some command surfaces are default-path joined, some are adapter-ready,
     and some remain legacy or external.
   - Use `RUNTIME_TRUTH_COMMAND_CUTOVER.md`.

3. A2A evidence ambiguity
   - Publish, delivery, domain receipt, semantic reply, and work completion are
     separate states.

4. Dirty worktree and many parallel branches
   - Do not assume one checkout tells the whole story.
   - Preserve unrelated changes.

5. External proof gap
   - Self-funding, external humans served, and market proof need external
     receipts, not more internal prose.

## Next 3 Reads

1. `make onboard`
2. `docs/governance/REALITY_DEBT_LEDGER.md`
3. `docs/governance/RUNTIME_TRUTH_COMMAND_CUTOVER.md`

After that, read the source owner:

- active work: `docs/governance/ACTIVE_TRACK.yaml`
- doctrine: `docs/governance/SOVEREIGN_MANIFEST.md`
- anti-slop: `docs/governance/ANTI_SLOP_RULES.md`

## Source Hierarchy

1. Human/operator instruction and safety constraints.
2. Runtime owners: `ExecutionIdentity`, `EvidenceReceipt`, `RuntimeStateStore`,
   `RuntimeReceipt`, `IdempotencyRecord`.
3. Active owner files: `ACTIVE_TRACK.yaml`, `ACTIVE_SURFACE_MANIFEST.yaml`,
   state registers, and external receipts.
4. Projection surfaces: onboarding, dashboards, generated reports, cards.
5. Doctrine and historical docs.

If two sources disagree, prefer the live owner or mark the claim AMBER until
the owner conflict is reconciled.
