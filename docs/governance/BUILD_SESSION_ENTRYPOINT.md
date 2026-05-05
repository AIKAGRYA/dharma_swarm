# BUILD SESSION ENTRYPOINT

Status: current build-track pointer, no new architecture.

This file exists to keep agents from starting from stale plans or rebuilding
substrates that already exist. It is subordinate to `CLAUDE.md` for behavior
and to `docs/governance/SOVEREIGN_MANIFEST.md` for architectural truth. If this
file conflicts with either one, they win.

## 0. Current Truth

Dharma Swarm already has the main substrates needed for governed repo work:
typed ontology, telos gates, witness records, AgentOps work packets, an
ontology-native Daily Insight Brief, and structured governance reports.

The current failure mode is not lack of ideas. It is agents reading different
worktrees, stale specs, or old mismatch maps and then opening a new seam before
the previous one is load-bearing.

Current canonical seam:

- `dharma_swarm.insight_brief` is the canonical Phase 1 Daily Insight Brief writer.
- `operator_brief` from PR57 is parked and must stay disabled unless Dhyana explicitly promotes it.
- AgentOps v0 is the governed local work-packet runner.
- KaizenReview is the next learning bridge after AgentOps reports.
- Human YDS ratings are human-authoritative only; AI must not assign them.

## 1. Mandatory Read Order

Read these before changing code:

1. `CLAUDE.md` - behavior rules, build commands, repository constraints.
2. `docs/governance/SOVEREIGN_MANIFEST.md` - repo axioms and domain boundaries.
3. `docs/governance/CANONICAL_DAILY_BRIEF_WRITER_2026-05-02.md` - current brief writer decision.
4. `docs/plans/ontology-native-flow-001-insight-brief.md` - implemented Daily Insight Brief contract.
5. `docs/governance/AGENTOPS.md` - governed work-packet runner contract.
6. `docs/governance/AGENTOPS_DAILY_OPERATING_BRIEF_BRIDGE.md` - bridge toward Daily Operating Brief and YDS.
7. `INTERFACE_MISMATCH_MAP.md` and `docs/interface_mismatches.yaml` - current mismatch truth.

If older docs point to `operator_brief` as the active seam, treat them as stale
unless `CANONICAL_DAILY_BRIEF_WRITER_2026-05-02.md` has been explicitly
superseded.

## 2. Current Build Track

The active track is the repo-agent operating loop:

```text
AgentOps packet
  -> isolated worktree
  -> gates and scope checks
  -> AgentOps report
  -> KaizenReview
  -> human YDS rating
  -> Daily Operating Brief
  -> next AgentOps packet
```

Do not open a new dashboard/API/ontology/product seam to solve this. The loop is
mostly a wiring and report-consumption problem.

## 3. Next Work Order

1. Keep the mismatch registry and markdown map synchronized with pinning tests.
2. Promote KaizenReview from AgentOps reports.
3. Implement the Human YDS Ledger as an append-only local operator ledger.
4. Let the future Daily Operating Brief consume AgentOps, KaizenReview, and YDS.

Only do one of these at a time.

## 4. Do Not Do

- Do not revive `operator_brief` while `insight_brief` remains canonical.
- Do not add dashboard/API routes for this track.
- Do not add new ontology types unless an existing canonical decision requires it.
- Do not add a new ledger before checking AgentOps, KaizenReview, YDS, and ontology substrates.
- Do not add new top-level `dharma_swarm/*.py` modules.
- Do not treat AI-generated quality scores as authoritative YDS.
- Do not hide module-budget, semgrep, or mismatch failures inside unrelated phases.

## 5. Done Means

A build-session handoff is coherent only when:

- the current branch has no stale open BLOCKER mismatch entries,
- tests pin any resolved mismatch that could regress,
- the work packet says exactly which files may change,
- gates run in the correct repo Python environment,
- the report says what passed, what failed, what changed, and what needs human approval,
- any YDS rating is explicitly human-provided and append-only.
