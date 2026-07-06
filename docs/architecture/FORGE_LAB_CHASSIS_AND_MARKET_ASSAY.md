# Forge Lab Chassis and Market Assay Vision

Status: implementation note for the Forge v3 chassis lane.

## Principle

Dharma Swarm needs two kinds of fitness signal, but they must not be mixed.

1. **Dense internal fitness** evolves the system.
2. **Sparse external market fitness** validates the champion.

The inner lab may be wild. The external membrane may not be.

## Three rings

### Ring 1 — Category A: agent evolution

The unit of evolution is a coding scaffold genome: model roster, prompt
strategy, verifier pattern, patch strategy, context window, and related agent
behavior.

This ring runs inside Forge Lab:

- parent sampled from the full archive;
- 3–5 children generated per generation;
- every child archived, including blocked and duplicate children;
- candidates graded on internal taskbed / benchmark slices;
- no promotion claims in EXPLORE.

### Ring 2 — Category B: swarm configuration evolution

The unit of evolution is collaboration topology: roles, edges, handoffs,
budget allocation, verifier placement, and debate/review shape.

This ring should use the same chassis shape as Category A, but with topology
genomes and swarm-arena grading.

### Ring 3 — outer market assay

Paid PR/bounty repair is not the training furnace. It is the champion-only
market assay.

The population does not enter the market. One selected champion may enter the
market through a bounded external-contact lease, against one target, with one
receipt chain.

The market assay measures:

- merged or rejected;
- paid or unpaid;
- profit or loss;
- reputation preserved or damaged;
- whether the evolved champion beats the plain-frontier baseline.

## Boundary law

EXPLORE freely. CONFIRM honestly. PROMOTE rarely. CONTACT externally only
through a lease.

Forge Lab governs the membrane, not the imagination:

- marked scratch worktree;
- no live daemon mutation;
- no secrets, wallets, or production access;
- no grader/safety/archive tampering;
- budget cap recorded;
- lineage recorded;
- positive lift claims forbidden in EXPLORE.

## Current chassis slice

The first chassis implementation is deliberately modest:

- safe scratch worktree lifecycle;
- append-only candidate store;
- novelty-weighted parent sampling;
- pluggable mutation operators;
- EXPLORE experiment loop;
- taskbed fast-lane seam;
- honest closeout as `inconclusive_low_power`.

It creates traffic through the evolutionary archive without pretending the
system has proven lift.

The next scientific milestone is not a paid bounty. It is an internal
same-budget comparison:

> evolved champion vs. plain frontier baseline on the internal fresh gradient.

Only after that should a bounded live market assay be granted.
