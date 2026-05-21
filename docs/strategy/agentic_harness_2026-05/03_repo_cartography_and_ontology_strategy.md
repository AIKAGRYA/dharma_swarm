# 03 Repo Cartography And Ontology Strategy

Expert lens: repo cartographer and ontology architect.
Local grounding: written after reading the 33-file local evidence base in `00_local_evidence_base.md`.
External grounding: Codified Context, ContextCov, Sourcegraph Cody context, Qodo Context Engine, Augment Context Engine.

## Core Claim

Dharma Swarm's bottleneck is not that no one has made enough maps. The bottleneck is that too many maps compete for authority. Cartography must become layered: entrypoint, current active truth, runtime spine, historical research, and optional deep maps.

The ontology promotion work is the decisive clue. Promote the operational runtime spine before adding philosophical or aspirational abstractions.

## The Five-Layer Map

Layer 1: Entry.

- `make onboard`
- `docs/ops/AGENT_ONBOARDING.md`
- active track output

Layer 2: Current truth.

- `docs/governance/ACTIVE_TRACK.yaml`
- generated active track evidence
- broken register
- protected-file policy

Layer 3: Runtime spine.

- `RuntimeSession`
- `SessionEvent`
- `TaskClaim` / `ExecutionLease`
- `DelegationRun`
- `ContextBundle`
- `RoutingDecision`
- `RuntimeArtifact`
- `ExternalOutcome`
- `OperatorInterrupt`

Layer 4: Deep architecture.

- `CLAUDE.md`
- `MEGAFILE_INDEX.md`
- canonical doc stack
- command-plane design lock
- persistent-agent cultivation docs

Layer 5: Research archive.

- persistent-agent census and deep dive
- ontology promotion packet
- older speculative plans

## Why This Matters

New agents fail when every document looks equally authoritative. The cartography system must rank documents by operational authority and freshness. A March moonshot doc may be useful context, but it must not override a May active track or a live failing test.

The repo should treat maps as projections over source-of-truth objects. A repo map is not truth. It is a view over files, symbols, runtime records, tests, and governance documents. When the view is stale, it should degrade visibly.

## Ontology Boundary

Promote objects only when they have:

- Durable state.
- Stable fields.
- Workflow role.
- Relationships.
- Governance/operator/autonomy value.
- Semantic clarity.

This keeps Dharma Swarm from turning every useful phrase into a canonical noun. `ContextBundle` and `RoutingDecision` deserve promotion faster than another abstract telos term because they are where agents actually fail.

## Anti-Sprawl Rule

Every new map must answer:

- What source of truth does this project?
- What stale condition invalidates it?
- Which agent role owns refresh?
- Which active workflow reads it?
- What existing map does it replace or summarize?

If those answers are missing, the file is probably sprawl.

## Cartographer Agent Contract

The Repo Cartographer should own:

- Fresh subsystem map.
- Runtime-spine object map.
- Protected-file map.
- Index freshness receipts.
- Known-stale map register.

It must never own:

- Measurement scripts.
- CI configs.
- Agent identity promotion decisions.
- Provider key material.

## Immediate Move

Make `docs/strategy/agentic_harness_2026-05/` a strategic map, not another canonical authority. Its authority is advisory. `make onboard`, active track, tests, and source files remain higher authority for execution.
