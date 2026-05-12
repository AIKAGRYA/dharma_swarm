---
title: Specs vs Spec-Forge Seam Plan
path: docs/plans/2026-04-02-specs-spec-forge-seam-plan.md
slug: specs-vs-spec-forge-seam-plan
doc_type: plan
status: active
summary: Defines the next bounded cleanup seam between normative specs, forge-stage specs, and non-spec material currently mixed into specs/.
source:
  provenance: repo_local
  kind: cleanup_plan
  origin_signals:
    - specs/README.md
    - spec-forge/README.md
    - docs/prompts/PARALLEL_BUILD_AGENT_PROMPTS_2026-03-19.md
    - docs/prompts/SOVEREIGN_BUILD_PHASE_MASTER_PROMPT_2026-03-19.md
  cited_urls: []
  generated_hint: human_or_agent_authored_repo_doc
disciplines:
  - knowledge_management
  - software_architecture
  - verification
  - operations
inspiration:
  - repo_hygiene
  - canonical_truth
connected_relevant_files:
  - specs/README.md
  - specs/research/README.md
  - spec-forge/README.md
  - docs/prompts/PARALLEL_BUILD_AGENT_PROMPTS_2026-03-19.md
  - docs/prompts/SOVEREIGN_BUILD_PHASE_MASTER_PROMPT_2026-03-19.md
  - docs/archive/VERIFICATION_COMPLETE.md
  - docs/archive/specs_research_living_layers/README.md
  - docs/REPO_ONTOLOGY_AND_HYGIENE_MASTER_SPEC_2026-04-01.md
improvement:
  room_for_improvement:
    - Keep direct references pointed at the prompt and archive destinations rather than the removed specs residues.
    - Mark superseded specs explicitly inside specs/.
    - Classify the remaining non-hot normative candidates without touching TUI-adjacent product code.
  next_review_at: '2026-05-17T12:00:00+08:00'
pkm:
  note_class: plan
  vault_path: docs/plans/2026-04-02-specs-spec-forge-seam-plan.md
  retrieval_terms:
    - specs
    - spec-forge
    - cleanup
    - canonical
    - forge
  evergreen_potential: medium
stigmergy:
  meaning: This file defines the next clean boundary between normative specifications and forge-stage or prompt-heavy material.
  state: active
  semantic_weight: 0.84
  coordination_comment: Use this file to choose one bounded specs cleanup tranche without widening into broad repo churn.
  trace_role: coordination_trace
curation:
  last_frontmatter_refresh: '2026-05-11T02:31:00+08:00'
  curated_by_model: Codex (GPT-5)
  schema_version: pkm-phd-stigmergy-v1
---
# Specs vs Spec-Forge Seam Plan

## Current Reality

The split between `specs/` and `spec-forge/` is conceptually strong and now documented in both index files:

- [`specs/README.md`](/Users/dhyana/dharma_swarm/specs/README.md) says `specs/` is the normative, formal, protocol, and verification layer.
- [`spec-forge/README.md`](/Users/dhyana/dharma_swarm/spec-forge/README.md) says `spec-forge/` is the incubation lane for emerging specifications.

The main problem is no longer directory meaning. The problem is mixed occupancy inside `specs/`.

## What Is Clearly In Bounds For `specs/`

These are good fits for `specs/`:

- formal artifacts such as `TaskBoardCoordination.tla` and `TaskBoardCoordination.cfg`
- bounded subsystem specs such as `KERNEL_CORE_SPEC.md`
- durable protocol and ontology specs such as `ONTOLOGY_PHASE2_SQLITE_UNIFICATION_SPEC_2026-03-19.md`
- stable schema and contract material such as `Dharma_Corpus_Schema.md`

## What Is Clearly Mixed Or Weakly Placed

These files did not read like enduring normative specs:

- `docs/prompts/PARALLEL_BUILD_AGENT_PROMPTS_2026-03-19.md`
- `docs/prompts/SOVEREIGN_BUILD_PHASE_MASTER_PROMPT_2026-03-19.md`
- `docs/archive/VERIFICATION_COMPLETE.md`

They are prompt-heavy, wave-specific, or completion-report style material.

## Ambiguous But Not First-Move Targets

These should not be moved in the first tranche without deeper coupling review:

- `specs/DGC_TERMINAL_ARCHITECTURE.md`
- `specs/DGC_TERMINAL_ARCHITECTURE_v1.1.md`
- `specs/SOVEREIGN_BUILD_PHASE_MASTER_SPEC_2026-03-19.md`
- `specs/STIGMERGY_11_LAYER_SPEC_2026-03-23.md`
- `specs/research/`

Reasons:

- some still function as active architectural reference
- some may belong in `docs/architecture/` rather than `spec-forge/`
- some are research substrate, which is a separate classification question
- the DGC terminal pair is TUI-adjacent and should not be edited by the overnight cleanup lane unless a separate owner explicitly authorizes that seam

## Executed Tranches

### Prompt And Completion Residue

The first bounded move was a prompt-and-completion tranche out of `specs/`, and that move is now completed.

### Authoritative Destinations

- `docs/prompts/PARALLEL_BUILD_AGENT_PROMPTS_2026-03-19.md`
- `docs/prompts/SOVEREIGN_BUILD_PHASE_MASTER_PROMPT_2026-03-19.md`
- `docs/archive/VERIFICATION_COMPLETE.md`

### Removed Specs Residue

- `specs/PARALLEL_BUILD_AGENT_PROMPTS_2026-03-19.md`
- `specs/SOVEREIGN_BUILD_PHASE_MASTER_PROMPT_2026-03-19.md`
- `specs/VERIFICATION_COMPLETE.md`

### Destination Rule

- prompt-heavy files moved to `docs/prompts/` because they remain useful as reusable prompt artifacts
- completion or wave-closeout material moved to `docs/archive/` because it reads as historical verification residue rather than current normative spec truth

### Living-Layers Research Duplicate

The second bounded move removed the stale tracked duplicate subtree:

- `specs/research_living_layers/README.md`
- `specs/research_living_layers/research_subconscious_ai.md`
- `specs/research_living_layers/research_stigmergy_agents.md`
- `specs/research_living_layers/research_shakti_creative_autonomy.md`

Authority now splits cleanly:

- current research companion truth stays under `specs/research/`
- historical duplicate living-layers inputs stay under `docs/archive/specs_research_living_layers/`

### Non-Hot Occupant Classification

The third bounded tranche classified the remaining tracked `specs/` occupants in
[`specs/README.md`](/Users/dhyana/dharma_swarm/specs/README.md) without moving
files or touching TUI-adjacent terminal spec bodies.

The classification preserves:

- formal verification truth under the task-board TLA+ pair
- foundational kernel, constitution, and corpus schema material under `specs/`
- active ontology and stigmergy runtime contract material under `specs/`
- the ontology TODO as a subordinate companion checklist
- `GODEL_CLAW_V1_SPEC.md` as architecture specification plus roadmap evidence, not current task authority
- `SOVEREIGN_BUILD_PHASE_MASTER_SPEC_2026-03-19.md` as deferred build-doctrine material because prompt and governance references still couple to it
- the DGC terminal pair as excluded from overnight non-TUI cleanup beyond index-level precedence notes
- `specs/research/` as active companion evidence, not duplicate residue

## Working Rule

Do not move architectural specs and prompt packets in the same tranche.

Do not edit TUI-adjacent DGC terminal architecture specs in the overnight cleanup lane without an explicit hot-lane owner.

## Validation Standard

Any implementation pass on this seam should:

1. update `specs/README.md`
2. update any direct live references to the moved files
3. preserve frontmatter integrity
4. keep the tranche Git-real and merge-safe
5. avoid touching `spec-forge/` family structure unless a move explicitly targets it

## Why This Is The Right Next Step

This move improves the repo in three ways at once:

- it makes `specs/` more truthful
- it reduces top-level ambiguity between specs and prompts
- it avoids the harder coupling questions around architecture and research material until the easy win is complete
