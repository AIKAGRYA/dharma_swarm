# Canonical Daily Brief Writer - 2026-05-02

## Decision

`dharma_swarm.insight_brief` is the canonical Phase 1 Daily Insight Brief writer.

`operator_brief` from PR57 is parked. It must remain disabled unless Dhyana explicitly promotes it to replace `insight_brief` or accepts two parallel brief surfaces with separate ontology contracts.

## Evidence

- Active scheduler job: `~/.dharma/cron/jobs.json`, job id `ontology_insight_brief`.
- Active handler: `insight_brief`.
- Active output path: `/Users/dhyana/dharma_briefs`.
- First scheduled production tick: 2026-05-02 04:30 WITA.
- Scheduled production artifact: `/Users/dhyana/dharma_briefs/2026-05-02-brief.md`.
- Scheduled production rows:
  - `WitnessLog/27c3d9cf60ef4939`, `created_by=insight_brief`, `created_at=2026-05-01T20:30:35.326389Z`.
  - `KnowledgeArtifact/bc05093b1e8d4b77`, `created_by=insight_brief`, `created_at=2026-05-01T20:30:37.717086Z`.

## Day Count

Day 1 for the Phase 1 no-reframe window is 2026-05-02 at 04:30 WITA.

The May 1 brief file was a manual/live test run. It remains valid evidence that the flow can run, but it does not start the scheduled production count.

## Parking PR57

PR57 worktree:

```text
/Users/dhyana/promotion_worktrees/dharma_swarm_operator_brief_pr57
e0cdb79 feat(operator_brief): wire runtime artifact seam 2026-05-01 22:55:03 +0800
```

PR57's cron entry is disabled and env-gated by `DHARMA_OPERATOR_BRIEF_ENABLED`.

Existing `operator_brief` ontology rows are retained as historical test/probe rows. Do not delete them. Do not create new `operator_brief` rows during Phase 1 unless the canonical decision changes.
