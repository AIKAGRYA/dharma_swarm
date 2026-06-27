# Operator Coherence Cockpit

- Generated: `2026-06-22T20:09:48.592484+00:00`
- Schema: `operator_coherence_cockpit.v0.1`
- Repo: `/Users/dhyana/dharma_swarm`
- Prod readiness estimate: **40.8%** (computed projection; not a final truth claim)

## Executive Board

- Health: **mixed**
- Top blocker count shown: 10

### Next 3 actions
1. **local_unpreserved_work** — push, PR, receipt, or explicit operator preservation decision  
   - Card: `preservation_risk` 11 worktree(s) still at preservation risk  
   - Evidence: `git worktree/status`
2. **dirty_worktree** — inspect dirty files; declare/extract to track branch before landing  
   - Card: `worktree` dharma_swarm_main (detached)  
   - Evidence: `git worktree list --porcelain`
3. **dirty_worktree** — inspect dirty files; declare/extract to track branch before landing  
   - Card: `worktree` dharma_swarm_prod_readiness_20260623_839fd25 (detached)  
   - Evidence: `git worktree list --porcelain`

## Readiness scoring

- **source_control_coherence**: 0% × 20% — 8 dirty worktrees, 3 detached, 6 local-only/ahead worktrees, 70 stashes; 207 local branches (107 local-only, 40 unpushed-ahead, 55 orphaned)
- **governance_legibility**: 88% × 15% — 11 active tracks, max 11, 1 stale, 0 lacking evidence
- **test_ci_state**: 53% × 15% — GitHub unavailable; estimated from active-track evidence
- **runtime_telemetry_liveness**: 0% × 15% — live-ops census: 4/17 surfaces live, 2 stale, 2 blocked; 0 terminal/process owners, 0 orphan candidates
- **operator_surface_usability**: 88% × 10% — 8/8 expected operator surfaces wired, 2 stale proofs
- **preservation_safety**: 10% × 10% — 11 worktrees at local preservation risk
- **external_product_proof**: 65% × 10% — 1 revenue/external-human track(s); A2A receipt dir exists=True
- **documentation_freshness**: 67% × 5% — freshness of ACTIVE_TRACK, active_track_evidence, BROKEN_REGISTER

## Kanban counts

- Preserved Only: 70
- Needs Decision: 50
- Ready To Extract: 0
- Active Branch: 5
- Open PR: 0
- Needs Repair: 41
- Landing Queue: 0
- Verified: 13
- Archived: 6

## Reality layer (git + runtime)

- Branches: 207 local (107 local-only, 40 unpushed-ahead, 55 orphaned/upstream-gone)
- Worktrees: 8 dirty, 6 local-only/ahead; 70 stashes
- Live ops: 4 live, 2 stale, 2 blocked, 9 stopped (source: scripts/runtime/live_ops_census.py)
- Onboarding: make onboard `wired` — onboard:
	$(PYTHON) scripts/governance/agent_onboard.py
- Runtime DB / receipts: 4/4 runtime DBs readable; 19 receipt files discovered

## Definition-of-done quick answers

### What is safe?
- `track` **Runtime Truth NATS — internal live transport for A2A dispatch** — declared_intent → operator lifecycle review: shippable track can be landed/closed _(evidence: docs/governance/ACTIVE_TRACK.yaml)_
- `track` **Runtime Truth Spine — Adoption (god objects flow through invoke_agent)** — declared_intent → operator lifecycle review: shippable track can be landed/closed _(evidence: docs/governance/ACTIVE_TRACK.yaml)_
- `track` **Orientation Graph — whole-system view served on token one** — declared_intent → operator lifecycle review: shippable track can be landed/closed _(evidence: docs/governance/ACTIVE_TRACK.yaml)_
- `track` **Composer Holon Spine Longrun — fable/codex pair over verified command receipts** — declared_intent → operator lifecycle review: shippable track can be landed/closed _(evidence: docs/governance/ACTIVE_TRACK.yaml)_
- `track` **AgentAdmission + Semantic Commons — one door for agent identity and naming** — declared_intent → operator lifecycle review: shippable track can be landed/closed _(evidence: docs/governance/ACTIVE_TRACK.yaml)_
- `track` **A2A Cloud-Agent Bridge — cloud reasoners onto the NATS substrate** — declared_intent → operator lifecycle review: shippable track can be landed/closed _(evidence: docs/governance/ACTIVE_TRACK.yaml)_
- `track` **Runtime Truth Spine — one invariant, one invocation path, one receipt** — declared_intent → archived/closed; keep as historical evidence _(evidence: docs/governance/ACTIVE_TRACK.yaml)_
- `track` **Trace Identity Coverage — native propagation and soft coverage findings** — declared_intent → archived/closed; keep as historical evidence _(evidence: docs/governance/ACTIVE_TRACK.yaml)_
- `track` **Trace Attractor Causal Spine — operator-visible trace packets** — declared_intent → archived/closed; keep as historical evidence _(evidence: docs/governance/ACTIVE_TRACK.yaml)_
- `track` **BoardStore Facade — unified task/state surface for multi-agent coordination** — declared_intent → archived/closed; keep as historical evidence _(evidence: docs/governance/ACTIVE_TRACK.yaml)_

### What is dirty?
- `worktree` **dharma_swarm (telos-ai-seed-v0-from-sandbox)** — dirty_worktree → inspect dirty files; declare/extract to track branch before landing _(evidence: git worktree list --porcelain)_
- `dirty_files` **201 dirty file(s) in dharma_swarm** — local_only_work → triage dirty files into tracked branch, PR, or explicit discard plan _(evidence: git status --short)_
- `worktree` **dharma_swarm_prod_readiness_20260623_839fd25 (detached)** — dirty_worktree → inspect dirty files; declare/extract to track branch before landing _(evidence: git worktree list --porcelain)_
- `dirty_files` **6 dirty file(s) in dharma_swarm_prod_readiness_20260623_839fd25** — local_only_work → triage dirty files into tracked branch, PR, or explicit discard plan _(evidence: git status --short)_
- `worktree` **dharma_helm_build (helm/worldclass-20260612)** — dirty_worktree → inspect dirty files; declare/extract to track branch before landing _(evidence: git worktree list --porcelain)_
- `dirty_files` **9 dirty file(s) in dharma_helm_build** — local_only_work → triage dirty files into tracked branch, PR, or explicit discard plan _(evidence: git status --short)_
- `worktree` **dharma_swarm_cashclaw (cashclaw/revenue-hydra-v1)** — dirty_worktree → inspect dirty files; declare/extract to track branch before landing _(evidence: git worktree list --porcelain)_
- `dirty_files` **18 dirty file(s) in dharma_swarm_cashclaw** — local_only_work → triage dirty files into tracked branch, PR, or explicit discard plan _(evidence: git status --short)_
- `worktree` **dharma_swarm_live (organ/03-seat)** — dirty_worktree → inspect dirty files; declare/extract to track branch before landing _(evidence: git worktree list --porcelain)_
- `dirty_files` **1 dirty file(s) in dharma_swarm_live** — local_only_work → triage dirty files into tracked branch, PR, or explicit discard plan _(evidence: git status --short)_

### What is abandoned?
- `dashboard_abandoned_candidate` **dashboard/src/app/dashboard/blocks/page.tsx** — abandoned_dashboard_candidate → verify route usage or archive surface _(evidence: dashboard/src/app/dashboard/blocks/page.tsx)_
- `dashboard_abandoned_candidate` **dashboard/src/app/dashboard/qwen35/telemetry/page.tsx** — abandoned_dashboard_candidate → verify route usage or archive surface _(evidence: dashboard/src/app/dashboard/qwen35/telemetry/page.tsx)_
- `dashboard_abandoned_candidate` **dashboard/src/app/dashboard/workflows/page.tsx** — abandoned_dashboard_candidate → verify route usage or archive surface _(evidence: dashboard/src/app/dashboard/workflows/page.tsx)_
- `track` **Runtime Truth Reconciliation — operator-visible truth packets** — stale_claim → operator lifecycle review: stale verified_at exceeds ttl_days _(evidence: docs/governance/ACTIVE_TRACK.yaml)_
- `operator_surface` **Terminal / TUI** — stale_surface_proof → refresh proof or rewire surface to current projection _(evidence: terminal)_
- `operator_surface` **Provider/model routing** — stale_surface_proof → refresh proof or rewire surface to current projection _(evidence: dharma_swarm/providers.py)_

### What is live?
- No cards in this bucket.

### What is blocked?
- `track` **Runtime Truth Reconciliation — operator-visible truth packets** — stale_claim → operator lifecycle review: stale verified_at exceeds ttl_days _(evidence: docs/governance/ACTIVE_TRACK.yaml)_
- `broken_register` **BR-003 — Apply gate present but closed (self-evolution loop)** — known_breakage → repair or explicitly retire this broken-register item _(evidence: docs/state/BROKEN_REGISTER.md)_
- `broken_register` **BR-004 — Cron split-brain (repo vs live)** — known_breakage → repair or explicitly retire this broken-register item _(evidence: docs/state/BROKEN_REGISTER.md)_
- `broken_register` **BR-005 — Algedonic stream in degenerate steady-state** — known_breakage → repair or explicitly retire this broken-register item _(evidence: docs/state/BROKEN_REGISTER.md)_
- `broken_register` **BR-013 — Agent contract fragmented across 8+ surfaces** — known_breakage → repair or explicitly retire this broken-register item _(evidence: docs/state/BROKEN_REGISTER.md)_
- `broken_register` **BR-014 — `BHED_GNAN` always passes** — known_breakage → repair or explicitly retire this broken-register item _(evidence: docs/state/BROKEN_REGISTER.md)_
- `broken_register` **BR-006 (CLOSED 2026-05-11) — Recognition seed stale** — known_breakage → repair or explicitly retire this broken-register item _(evidence: docs/state/BROKEN_REGISTER.md)_
- `broken_register` **BR-002 (CLOSED 2026-05-10 via PR #187) — central VentureCell loop feedback** — known_breakage → repair or explicitly retire this broken-register item _(evidence: docs/state/BROKEN_REGISTER.md)_
- `broken_register` **BR-007 (CLOSED 2026-05-10 via PR #187) — runtime.db and ontology.db sync** — known_breakage → repair or explicitly retire this broken-register item _(evidence: docs/state/BROKEN_REGISTER.md)_
- `broken_register` **BR-008 (CLOSED 2026-05-10 via PR #187) — VentureCell ontology/organ polymorphism** — known_breakage → repair or explicitly retire this broken-register item _(evidence: docs/state/BROKEN_REGISTER.md)_

### What might be rogue?
- `stash` **stash@{2026-06-19 00:14:42 +0900}: On (no branch): deploy-unblock: stray governance reports 20260618T151442Z** — hidden_local_work → operator decision: inspect and either declare, apply to a branch, or archive _(evidence: git stash list)_
- `stash` **stash@{2026-06-18 20:07:05 +0900}: On feat/trust-gate-scoreboard: compost/worktree-cull/2026-06-18 /Users/dhyana/ds_trus** — hidden_local_work → operator decision: inspect and either declare, apply to a branch, or archive _(evidence: git stash list)_
- `stash` **stash@{2026-06-18 20:07:05 +0900}: On codex/pr578-main-sync: compost/worktree-cull/2026-06-18 /Users/dhyana/ds_pr578_fix** — hidden_local_work → operator decision: inspect and either declare, apply to a branch, or archive _(evidence: git stash list)_
- `stash` **stash@{2026-06-18 20:07:05 +0900}: On codex/main-review-blockers: compost/worktree-cull/2026-06-18 /Users/dhyana/ds_main** — hidden_local_work → operator decision: inspect and either declare, apply to a branch, or archive _(evidence: git stash list)_
- `stash` **stash@{2026-06-18 20:07:05 +0900}: On (no branch): compost/worktree-cull/2026-06-18 /Users/dhyana/ds_loopclose_night** — hidden_local_work → operator decision: inspect and either declare, apply to a branch, or archive _(evidence: git stash list)_
- `stash` **stash@{2026-06-18 20:07:04 +0900}: On fable/loop1-trunk-delegated: compost/worktree-cull/2026-06-18 /Users/dhyana/ds_loo** — hidden_local_work → operator decision: inspect and either declare, apply to a branch, or archive _(evidence: git stash list)_
- `stash` **stash@{2026-06-18 20:07:04 +0900}: On codex/truth-graph-v1: compost/worktree-cull/2026-06-18 /Users/dhyana/ds_codex_trut** — hidden_local_work → operator decision: inspect and either declare, apply to a branch, or archive _(evidence: git stash list)_
- `stash` **stash@{2026-06-18 20:07:04 +0900}: On tam/build-2026-06: compost/worktree-cull/2026-06-18 /Users/dhyana/dharma_swarm_tam** — hidden_local_work → operator decision: inspect and either declare, apply to a branch, or archive _(evidence: git stash list)_
- `stash` **stash@{2026-06-17 08:28:49 +0900}: On telos-ai-seed-v0-from-sandbox: codex-telos-ontology-wip** — hidden_local_work → operator decision: inspect and either declare, apply to a branch, or archive _(evidence: git stash list)_
- `stash` **stash@{2026-06-16 00:56:54 +0900}: On telos-ai-seed-v0-from-sandbox: what-not-to-do mandala cockpit attempt 2026-06-16** — hidden_local_work → operator decision: inspect and either declare, apply to a branch, or archive _(evidence: git stash list)_

## Source errors / uncertainty

- `tmux.ls`: error connecting to /private/tmp/tmux-501/default (No such file or directory)

- `launchctl.list`: launchctl list failed
- `ps`: [Errno 1] Operation not permitted: 'ps'
- `github.auth`: gh auth unavailable; PR/CI triage omitted

## Evidence discipline

This receipt is generated from probe JSON. Do not hand-edit it as truth; regenerate from `scripts/runtime/operator_coherence_cockpit.py`.
