# Megafile Index

**Status:** canonical onboarding slot index
**Scope:** where the highest-system maps live and how cold agents should read them
**Owner surface:** DocOps authority registry plus Coherence Delta merge discipline

This file is the stable index for the ten high-level onboarding megafiles. It
does not replace the slot files. It tells agents which slot owns which kind of
truth, which file currently fills the slot, and which slots are still only
seeded or missing.

## Read Order

1. Vision Synthesis
2. Operational Doctrine
3. Live Roadmap
4. Limbs Atlas
5. Wiring And Loops
6. Live Ops Dashboard
7. Broken Register
8. Operator Runbook
9. Agent Contract
10. Contemplative Spine

## Slot Table

| Slot | Role | Current file | Status |
|---:|---|---|---|
| 1 | Highest vision and attractor closure | `docs/vision_maps/MASTER_2026-05-07_attractor_closure_synthesis.md` | SEEDED |
| 2 | Mission, refusal posture, kill conditions | `docs/doctrine/OPERATIONAL_DOCTRINE.md` | MISSING |
| 3 | What is shipping now and what is deferred | `docs/roadmap/LIVE_ROADMAP.md` | MISSING |
| 4 | Organ/module atlas and ownership map | `docs/architecture/NAVIGATION.md` plus `make xray` | PARTIAL / STALE |
| 5 | Interfaces, routing, and closed/open loops | `CYBERNETIC_LOOP_MAP.md`, `INTERFACE_MISMATCH_MAP.md`, `MODEL_ROUTING_MAP.md` | FRAGMENTED |
| 6 | Today's live system state | `docs/state/LIVE_OPS_DASHBOARD.md` | SEEDED |
| 7 | Known broken, stale, or contradictory claims | `docs/state/BROKEN_REGISTER.md` | SEEDED |
| 8 | Change -> test -> ship -> observe | `docs/operations/OPERATOR_RUNBOOK.md` | MISSING |
| 9 | Human/AI agent contract and identity | `AGENT_IDENTITY_UNIFICATION.md`, `/Users/dhyana/CLAUDE.md` | FRAGMENTED |
| 10 | Foundations, Sanskrit/technical glossary, contemplative spine | `foundations/INDEX.md` | PARTIAL |

## Promotion Rule

A slot file becomes authoritative only when all of the following are true:

1. It exists in the repo.
2. It is registered in `docs/governance/CANONICAL_DOC_STACK.md`.
3. If it uses authority-scope language, it is also registered in
   `docs/docops/assertions.yaml`.
4. Its count-sensitive claims pass `make docops-integrity`.
5. PRs changing it answer the Coherence Delta fields.

## Current Gaps

- Slot 2 is still fragmented across cabinet strategy and telos files.
- Slot 3 has no single current roadmap that reconciles Loomwork, active PRs,
  and local runtime state.
- Slot 4 still depends on a stale static navigation file and generated xray
  output rather than one fresh limbs atlas.
- Slot 8 is missing; this is the most important operator-facing gap after the
  map surfaces are present.
- Slot 9 is split between repo-local agent identity docs and the global operator
  contract.

## Source Evidence

This index is seeded from `/Users/dhyana/.dharma/audit/ten_megafiles_survey_2026-05-07.md`
and the six source surveys at `/Users/dhyana/.dharma/audit/ten_megafiles_q*.md`.
Those audit files are evidence, not repo authority. This index is the repo-local
home for the slot shape.
