# HOTLIST — Repo-Wide Running Task Board

**Path:** `docs/state/HOTLIST.md`
**Last updated:** 2026-05-21
**Owner:** Any agent may update this file. Use append-only discipline for status changes.

This is the repo-wide kanban that any agent (Devin, Codex, Claude Code, Cursor) can read and update. It is the single place to see what needs doing next.

For full context on each item, see `docs/state/NEXT_PHASE_MAP.md`.

---

## How To Use

1. **Before starting work:** Run `make onboard`, then read this file.
2. **Claiming a task:** Move it to IN PROGRESS, add your agent name and date.
3. **Completing a task:** Move it to DONE with evidence (PR number, commit hash, or file path).
4. **Adding a task:** Append to the appropriate priority section. Include a one-line description and evidence link.
5. **Blocked tasks:** Add `[BLOCKED: reason]` tag. Do not remove from the list.

---

## CRITICAL (do now)

| # | Task | Evidence | Status | Agent |
|---|---|---|---|---|
| H-001 | Merge PR #321 (TaskBoard adapter + BR closures) — needs CI push | PR #321, 0 CI checks triggered | TODO | — |
| H-002 | Merge PR #323 (env alias normalization + dashboard fidelity) | PR #323, 21/22 CI green | TODO | — |
| H-003 | Merge PR #325 (Codex toolbelt onboarding) — mark ready first | PR #325, 22/22 CI green, still draft | TODO | — |
| H-004 | Write ADR-0002 (trace coverage gate policy) | `docs/architecture/adr/0002-trace-coverage-gate.md` MISSING — blocks active track 6/6 | TODO | — |
| H-005 | Close active track → open next track | `ACTIVE_TRACK.yaml` — 5/6, needs ADR-0002 first | TODO | — |

## HIGH (this week)

| # | Task | Evidence | Status | Agent |
|---|---|---|---|---|
| H-006 | Triage 19 stale PRs (close superseded, rebase keepers) | PRs #99–#182 open 14+ days | TODO | — |
| H-007 | Verify Loop 1 end-to-end (providers working, need dispatch test) | `CYBERNETIC_LOOP_MAP.md` Loop 1, providers confirmed locally | TODO | — |
| H-008 | Refresh CYBERNETIC_LOOP_MAP.md (stale: claims "no LLM provider" but providers work) | Map last audit 2026-05-05 (16d) | TODO | — |
| H-009 | Refresh LIVE_OPS_DASHBOARD.md (snapshot 2026-05-11, 10d old, threshold 7d) | `docs/state/LIVE_OPS_DASHBOARD.md:4` | TODO | — |
| H-010 | Refresh INTERFACE_MISMATCH_MAP.md (last X-ray 2026-05-04, 17d) | `INTERFACE_MISMATCH_MAP.md:3` | TODO | — |

## MEDIUM (next 1-2 weeks)

| # | Task | Evidence | Status | Agent |
|---|---|---|---|---|
| H-011 | Wire BoardStore facade into orchestrator dispatch | `dharma_swarm/board/facade.py` — 0 runtime consumers | TODO | — |
| H-012 | Wire Sakshi provenance into real state transitions | `dharma_swarm/sakshi/provenance_log.py` — 0 runtime writers | TODO | — |
| H-013 | Wire Dhyana drift triage automated BR aging | `dharma_swarm/dhyana/drift_triage.py` — 0 consumers on main | TODO | — |
| H-014 | Promote Control Surface to nav position #1 | `ACTIVE_SURFACE_MANIFEST.yaml` dashboard_nav_sections — Control Surface is item #2 | TODO | — |
| H-015 | Add active track banner to command plane | Dashboard cockpit — no track info shown | TODO | — |
| H-016 | Decompose terminal_bridge.py (2,539 > 2,411 ceiling — Rule 10 violation) | `dharma_swarm/terminal_bridge.py` | TODO | — |
| H-017 | Consolidate agent contract from 8+ surfaces → 1 canonical (BR-013) | `docs/state/BROKEN_REGISTER.md` BR-013 | TODO | — |

## LOW (backlog)

| # | Task | Evidence | Status | Agent |
|---|---|---|---|---|
| H-018 | Implement Observatory endpoint | `/dashboard/observatory` — STUB | TODO | — |
| H-019 | Wire Ecosystem ReactFlow data | `/dashboard/ecosystem` — partial | TODO | — |
| H-020 | Design Synthesizer API | `/dashboard/synthesizer` — STUB | TODO | — |
| H-021 | Open evolution apply gate (BR-003) — after Sakshi provenance live | `BROKEN_REGISTER.md` BR-003 | TODO | — |
| H-022 | Wire MemoryKernel release gate (PR #312) | PR #312 | TODO | — |
| H-023 | Fix BHED_GNAN always-pass gate (BR-014) — governance-locked | `telos_gates.py:512-513` | TODO | — |
| H-024 | Resolve cron split-brain (BR-004) | `BROKEN_REGISTER.md` BR-004 | TODO | — |
| H-025 | Fix algedonic stream consumption (BR-005) | `BROKEN_REGISTER.md` BR-005 | TODO | — |
| H-026 | ADR-007 AutoProposer retirement (PR #320) | PR #320 | TODO | — |

## DONE (append completed items here)

| # | Task | Evidence | Completed | Agent |
|---|---|---|---|---|
| — | PR #313 merged (single-door onboarding) | PR #313 | 2026-05-20 | Devin |
| — | PR #315 merged (gitnexus fix) | PR #315 | 2026-05-20 | Devin |
| — | PR #318 merged (cockpit track closure) | PR #318 | 2026-05-20 | Devin |
| — | PR #319 merged (track transition + seeds) | PR #319 | 2026-05-20 | Devin |
| — | Invariant command plane findings delivered | `/home/ubuntu/invariant-command-plane-findings.md` | 2026-05-21 | Devin |
| — | Dashboard fidelity audit (25 pages) | On PR #323 branch | 2026-05-21 | Devin |
| — | Env alias normalization (GEMINI→GOOGLE_AI, etc.) | PR #323 | 2026-05-21 | Devin |
| — | Codex toolbelt onboarding CI fix | PR #325 | 2026-05-21 | Devin |
