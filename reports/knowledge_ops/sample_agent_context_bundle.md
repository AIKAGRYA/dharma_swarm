# Agent Context Bundle: knowledgeops.v0.sample

Role: knowledge-ops-reviewer
Generated: 2026-05-12T15:10:39.303211+00:00
Expires: 2026-05-13T03:10:39.303211+00:00
Token budget: 12000

Objective:
Inventory KnowledgeOps substrate.

Authority:
- This bundle is a projection. Source refs outrank summaries.
- Canonical docs and human/operator approvals outrank generated cards.

Relevant nodes:
- `broken_register_item:00053364822a7d8ba9757231` [broken_register_item/trusted] BR-011 — `INTERFACE_MISMATCH_MAP.md` self-declared stale
- `broken_register_item:0101d01cc960b216d8bf4efa` [broken_register_item/trusted] > **Convergence pass executed 2026-05-07 18:00–18:10:** Plan at `~/.claude/plans/yes-write-a-plan-wobbly-cerf.md`. Closed items moved to CLOSED section: BR-001 (cron daemon plist fixed), BR-016 (SOVEREIGN_MANIFEST counts refreshed 514→567), BR-017 (BUILD_SESSION_ENTRYPOINT.md cherry-picked), BR-018 (MEGAFILE_INDEX referenced from CLAUDE.md + README). BR-015 was already CLOSED. Total CLOSED = 5; OPEN = 14.
- `broken_register_item:04d23d7f3800c2c82fd0a12a` [broken_register_item/trusted] > **Convergence pass executed 2026-05-07 18:00–18:10:** Plan at `~/.claude/plans/yes-write-a-plan-wobbly-cerf.md`. Closed items moved to CLOSED section: BR-001 (cron daemon plist fixed), BR-016 (SOVEREIGN_MANIFEST counts refreshed 514→567), BR-017 (BUILD_SESSION_ENTRYPOINT.md cherry-picked), BR-018 (MEGAFILE_INDEX referenced from CLAUDE.md + README). BR-015 was already CLOSED. Total CLOSED = 5; OPEN = 14.
- `broken_register_item:209ef7bdab8e9c458ad6658f` [broken_register_item/trusted] BR-004 — Cron split-brain (repo vs live)
- `broken_register_item:30244ef303ff377f10d33994` [broken_register_item/trusted] BR-014 — `BHED_GNAN` always passes
- `broken_register_item:375bae2a572742580a6bfe61` [broken_register_item/trusted] > **Convergence pass executed 2026-05-07 18:00–18:10:** Plan at `~/.claude/plans/yes-write-a-plan-wobbly-cerf.md`. Closed items moved to CLOSED section: BR-001 (cron daemon plist fixed), BR-016 (SOVEREIGN_MANIFEST counts refreshed 514→567), BR-017 (BUILD_SESSION_ENTRYPOINT.md cherry-picked), BR-018 (MEGAFILE_INDEX referenced from CLAUDE.md + README). BR-015 was already CLOSED. Total CLOSED = 5; OPEN = 14.
- `broken_register_item:4844fc8bc57aaee6d7bc7a97` [broken_register_item/trusted] BR-009 — Roadmap is contested (3 docs claim primacy)
- `broken_register_item:5039e142ceff2fccfddca47e` [broken_register_item/trusted] BR-010 — `NAVIGATION.md` exists at non-canonical path; file itself stale
- `broken_register_item:5b6fd97b25d9f0706f30f092` [broken_register_item/trusted] Next id: `BR-020`. Append below. Do NOT renumber existing items.
- `broken_register_item:617dc77425baeb067a7e34cf` [broken_register_item/trusted] > **Convergence pass executed 2026-05-07 18:00–18:10:** Plan at `~/.claude/plans/yes-write-a-plan-wobbly-cerf.md`. Closed items moved to CLOSED section: BR-001 (cron daemon plist fixed), BR-016 (SOVEREIGN_MANIFEST counts refreshed 514→567), BR-017 (BUILD_SESSION_ENTRYPOINT.md cherry-picked), BR-018 (MEGAFILE_INDEX referenced from CLAUDE.md + README). BR-015 was already CLOSED. Total CLOSED = 5; OPEN = 14.
- `broken_register_item:7c6b025ef8369c0c2ced1d52` [broken_register_item/trusted] BR-003 — Apply gate present but closed (self-evolution loop)
- `broken_register_item:8721a1f063d366f40a4a87c7` [broken_register_item/trusted] BR-007 — Two stores for one self (runtime.db ↔ ontology.db never synced)
- `broken_register_item:9683268e78345e1af3e25334` [broken_register_item/trusted] 2. **Write side (this commit):** `dharma_swarm/shakti_executive/feedback_writer.py` exposes `update_opportunity_outcome(opp_id, outcome)` that appends realized outcomes to `opportunity_board.json` and updates `learned_score_delta`. Atomic write, idempotent on duplicate `outcome_id`, capped per-outcome score delta. 8/8 tests pass under `tests/test_feedback_writer.py`. **Caller wiring (proposal_id → campaign manifest → opportunity_id resolution) is NOT yet in place** — the writer is a public-API library; the resolver is a follow-up. Full VentureCell polymorphism (BR-008) and full loop closure remain open.
- `broken_register_item:9975630145269cf011064188` [broken_register_item/trusted] > **Convergence pass executed 2026-05-07 18:00–18:10:** Plan at `~/.claude/plans/yes-write-a-plan-wobbly-cerf.md`. Closed items moved to CLOSED section: BR-001 (cron daemon plist fixed), BR-016 (SOVEREIGN_MANIFEST counts refreshed 514→567), BR-017 (BUILD_SESSION_ENTRYPOINT.md cherry-picked), BR-018 (MEGAFILE_INDEX referenced from CLAUDE.md + README). BR-015 was already CLOSED. Total CLOSED = 5; OPEN = 14.
- `broken_register_item:a1a212886c733332e940cce8` [broken_register_item/trusted] BR-006 — Recognition seed stale
- `broken_register_item:c0a2ecebd4c86b4ee4c01951` [broken_register_item/trusted] BR-019 — Coherence Delta gate enforced honor-system only
- `broken_register_item:d09e0e96c41e8c012a3860a1` [broken_register_item/trusted] BR-013 — Agent contract fragmented across 8+ surfaces
- `broken_register_item:d4089788554b3780b02c22ef` [broken_register_item/trusted] BR-005 — Algedonic stream in degenerate steady-state
- `broken_register_item:d9f1669cf2f90da1a2192ee6` [broken_register_item/trusted] BR-002 — Central VentureCell loop is open
- `broken_register_item:e48c889c589b3a7ba12ed158` [broken_register_item/trusted] BR-012 — `CYBERNETIC_LOOP_MAP.md` stale (6 days)

Edge summary:
- derived_from: 5
- extracts_concept: 249
- observes: 15
- references: 159
- tracks_brokenness_of: 20

Stale or time-bound sources:
- none in selected nodes

Evidence to return:
- Source paths inspected.
- Any contradictions or stale claims found.
- Tests or commands run, if implementation follows.

Anti-drift:
- Do not create new authority docs from this bundle.
- Do not promote dream/synthesis candidates without evidence and review.
