# Open PR Backlog Review — AmitabhainArunachala/dharma_swarm (2026-08-09)

Source: GitHub API via `list_pull_requests` (state=open, sort=updated desc), 2026-08-09.
**33 open PRs.** Oldest untouched: #1115 (2026-07-25, zero activity since creation day).

## Recommended actions

### Close (stale drafts stranded >2 weeks, superseded by the moving trunk)
The seven `ci-stranded-rebase-skipped`-labeled drafts from 2026-07-12..21 form a cohort the
automation itself has given up rebasing. Either re-adopt into an active track's next-items or
close with salvage notes:

- **#904** feat(holon): authority-scoped remote fast path — draft since 2026-07-12, stranded label. Close/salvage.
- **#1060** diff-applier idempotency fence (spine A1) — draft 2026-07-19, stranded. Close or re-adopt into titanium track (owns `dharma_swarm/diff_applier.py`).
- **#1061** MCP spine A2 — draft 2026-07-19, stranded. Same decision as #1060; they travel together.
- **#1063** store-sync spine B2 — draft 2026-07-19, stranded. Close/salvage.
- **#1070** xray discover_files cap — draft 2026-07-20, last touched 2026-07-24. Close; small enough to redo fresh if wanted.
- **#1080** REMOTE_HOLON_MESH v1.1 spec (sole-copy salvage) — docs-only; body says sole copy — extract the doc to an issue/track note, then close.
- **#1086** AGNI hub readiness probe — draft 2026-07-21, stranded. Close.
- **#1115** a2a responder restart boundary — draft, zero activity since 2026-07-25. Close.

### Operator decision required (explicitly blocked on you)
- **#1081** TELOS canon reconciliation — title carries `[BLOCKED-ON-OPERATOR-DECISION]` since 2026-07-21. Decide or close; 3 weeks blocked is a queue poison.
- **#1067** pre-constitutional founder direction docs — `mike-watch` label, open since 2026-07-19. Docs-only; decide and land or close.
- **#1213 / #1214** governance track closures (helm terminal, arena) — both say CLOSED_NOT_PROD; if you agree the tracks are done, these should merge promptly since they gate portfolio WIP accounting. Note tension: CLAUDE.md still lists both tracks as ACTIVE.

### Merge-priority lane (recent, active, unblock other work)
- **#1185** Mike gate risk recompute — `mike-watch`, actively updated (2026-08-09). Merge Master's own gate correctness; review first.
- **#1312** restore frozen LangGraph oracle tuple — small fix on dharmagraph track, fresh (2026-08-08).
- **#1313** docops counts reconcile — mechanical follow-up to #1179; merge when green.
- **#1200** loop-closure: 10 post-merge findings incl. two verified denylist bypasses — security-adjacent; prioritize review.
- **#1219** sarathi composition root — active organism-rewire track work, updated 2026-08-08.

### Dependency bumps (batch-decide)
- **#1222** setuptools, **#1284** h2, **#1224** time (tauri) — merge if CI green; they're cheap and rot fast.

### Judgment calls
- **#1149** Devin: Darwin apply gate sandbox mode (BR-003, bot-pr, open since 2026-07-27) — this widens the self-modification surface; needs a human decision, not a queue slot. Decide within the sovereign-safety track or close.
- **#1129** memory-plane clique fix (`mike-watch`, 2026-07-25) — real fix by title; re-review, rebase, land or close.
- **#1145** swarm image provenance seal — untouched since 2026-07-31; same treatment.
- **#1310** Dharma World Deck spec (draft) / **#1204** hygiene cluster N (draft) / **#1206** onboard kill-switch visibility (draft) / **#1201** persistent-agent map / **#1182** docops reconcile heads / **#1184** WP-0S observation / **#1212** WP-0G ratification / **#1307** ops snapshot shape — active-ish; triage inside their owning tracks.

## Structural observation
21 of 33 PRs are >1 week old; 12 are drafts. The `ci-stranded-rebase-skipped` label is doing
silent graveyard duty — nothing routes those PRs to a close/salvage decision. A weekly
"strand court" (auto-close with salvage-note after N days stranded) would keep the queue honest.
