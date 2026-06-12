# Parallel Lane Map

Generated: 2026-06-06T04:57:56Z

This is a non-destructive operating snapshot. It is not approval to prune, close, merge, or reset anything.

## Doctrine

- Model: one strategic active track; many coordinated work lanes
- Active track role: north-star, acceptance gates, non-goals, authority boundaries
- Lane rule: parallel work is allowed only when owned, scoped, isolated, verified, and receipted
- Cleanup rule: never delete branches/worktrees from this report without receipt review and explicit operator approval

## Summary

- Active branch: `qwen/spine-adoption` at `aa5a8e82b0`
- Worktrees: 92
- Branches sampled: 200
- Open PRs: 3
- Dirty entries in current worktree: 236
- Cleanup candidates for review: 52

## Lane Groups

| Lane | Worktrees | Branches | Open PRs | Recent commits |
|---|---:|---:|---:|---:|
| `forge-measurement` | 0 | 1 | 0 | 0 |
| `governance` | 2 | 12 | 0 | 7 |
| `live-ops-cockpit` | 3 | 8 | 0 | 4 |
| `living-agent-kernel` | 2 | 2 | 0 | 5 |
| `merge-master-mike` | 0 | 8 | 0 | 3 |
| `parked-cleanup` | 18 | 30 | 0 | 0 |
| `pr-repair-backlog` | 10 | 18 | 0 | 12 |
| `research` | 1 | 5 | 0 | 18 |
| `rss-followups` | 18 | 17 | 0 | 0 |
| `runtime-truth-spine` | 3 | 19 | 1 | 7 |
| `spine-adoption` | 5 | 7 | 2 | 13 |
| `unclassified` | 30 | 73 | 0 | 91 |

## Open PRs

| PR | Lane | State | Head | Title |
|---:|---|---|---|---|
| [#514](https://github.com/AmitabhainArunachala/dharma_swarm/pull/514) | `runtime-truth-spine` | draft | `codex/runtime-truth-nats-adapter-20260606` | [codex] add runtime-truth NATS transport |
| [#513](https://github.com/AmitabhainArunachala/dharma_swarm/pull/513) | `spine-adoption` | draft | `chore/spine-adoption-metric-20260606` | chore(governance): refresh spine adoption metric 81.2% (+6.2pp) [automated] |
| [#512](https://github.com/AmitabhainArunachala/dharma_swarm/pull/512) | `spine-adoption` | draft | `chore/spine-adoption-metric-20260605` | chore(governance): refresh spine adoption metric 81.2% (+6.2pp) [automated] |

## Current Worktree Dirty Pressure

Total dirty entries: 236

| Category | Count |
|---|---:|
| `agentops_work_packets` | 189 |
| `tests` | 12 |
| `governance_scripts` | 7 |
| `runtime_scripts` | 6 |
| `governance_docs` | 5 |
| `governance_reports` | 4 |
| `capital_lab` | 2 |
| `forge_measurement` | 2 |
| `reports` | 2 |
| `tools` | 2 |
| `repo_root` | 1 |
| `research_docs` | 1 |
| `examples` | 1 |
| `hooks` | 1 |
| `references` | 1 |

## Cleanup Candidates For Review

- `worktree` `/private/tmp/rss-wt-FU-CQ-PASSPORT-COUNT-review`: detached
- `worktree` `codex-lane/cleanup-audit`: stale_review
- `worktree` `feat/codex-lane-runner-2026-05-13`: stale_review
- `worktree` `cleanup/identity-onboarding-2026-05-12`: stale_review
- `worktree` `review/interop-fleet-2026-05-12`: stale_review
- `worktree` `review/memory-knowledge-2026-05-12`: stale_review
- `worktree` `/Users/dhyana/cleanup_worktrees/dharma_swarm_pr_queue_probe2_20260524`: detached
- `worktree` `/Users/dhyana/cleanup_worktrees/dharma_swarm_pr_queue_probe_20260524`: detached
- `worktree` `review/proof-artifacts-2026-05-12`: stale_review
- `worktree` `feat/recursive-discovery-shadow-2026-05-14`: stale_review
- `worktree` `review/root-governance-residue-2026-05-12`: stale_review
- `worktree` `cleanup/route-witness-2026-05-12`: stale_review
- `worktree` `cleanup/route-witness-main-2026-05-13`: stale_review
- `worktree` `cleanup/viz-invariant-projection-2026-05-12`: stale_review
- `worktree` `feat/world-radar-live-integration-2026-05-13`: stale_review
- `worktree` `feat/core-operating-circuit-proof`: stale_review
- `worktree` `/Users/dhyana/dharma_swarm_dgmd_smoke_20260514T045353Z`: detached
- `worktree` `runtime/main-live-20260511`: stale_review
- `worktree` `/Users/dhyana/dharma_swarm_pr326`: detached
- `worktree` `feat/world-radar-shakti-safe-convergence-2026-05-13`: stale_review
- `worktree` `feat/go-local-model-runtime-inventory`: stale_review
- `worktree` `experiments/mask-rv-whitebox-prereg`: stale_review
- `worktree` `feat/runtime-result-projector`: stale_review
- `branch` `backup/memory-kernel-prep-2026-05-14`: 23d old, no open PR head
- `branch` `cleanup/route-witness-main-2026-05-13`: 24d old, no open PR head
- `branch` `cleanup/memory-kernel-context-eval-2026-05-13`: 24d old, no open PR head
- `branch` `backup/route-witness-pr297-pre-rebase-2026-05-13`: 24d old, no open PR head
- `branch` `cleanup/main-recurring-live-salvage-2026-05-13`: 24d old, no open PR head
- `branch` `cleanup/runtime-result-projector-salvage-2026-05-13`: 24d old, no open PR head
- `branch` `cleanup/go-local-model-runtime-inventory-salvage-2026-05-13`: 24d old, no open PR head
- `branch` `cleanup/agent-truth-spine-salvage-2026-05-13`: 24d old, no open PR head
- `branch` `cleanup/kaizen-review-v0-salvage-2026-05-13`: 24d old, no open PR head
- `branch` `cleanup/module-metabolism-strategy-salvage-2026-05-13`: 24d old, no open PR head
- `branch` `cleanup/core-operating-circuit-proof-salvage-2026-05-13`: 24d old, no open PR head
- `branch` `cleanup/opportunity-dispatcher-budget-fix-salvage-2026-05-13`: 24d old, no open PR head
- `branch` `cleanup/brake-stabilization-salvage-2026-05-13`: 24d old, no open PR head
- `branch` `cleanup/action-authority-salvage-2026-05-13`: 24d old, no open PR head
- `branch` `review/memory-knowledge-2026-05-12`: 24d old, no open PR head
- `branch` `cleanup/root-memory-context-salvage-2026-05-13`: 24d old, no open PR head
- `branch` `backup/route-witness-main-pre-rebase-2026-05-13`: 24d old, no open PR head
- ... 12 more in JSON

## Recent Commits

- `84fc4afef` 2026-06-06 `spine-adoption` index on qwen/spine-adoption: aa5a8e82b feat(go-ingest): wire idea spark ingest spine (#474) (Dhyana)
- `a3ea1ee9a` 2026-06-06 `governance` doctrine(governance): implement multi-track with parallel_lane_policy (v2 schema) (Dhyana)
- `2742aaad8` 2026-06-06 `living-agent-kernel` feat(lak-e2e): metabolism-namespace-ledger — Hash-chained per-agent learning ledger store (single durable write surface; dependency root for ALL metabolism + the LEARN executor) (Dhyana)
- `c9fe74186` 2026-06-06 `living-agent-kernel` feat(lak-e2e): wire-in-real-agent-governed-run — a real PersistentAgent task is governed end-to-end by the kernel and leaves durable receipts (Dhyana)
- `e0e3ce254` 2026-06-06 `living-agent-kernel` feat(lak-e2e): wire-in-persistent-adapter — PersistentAgent -> kernel wake-payload adapter (dependency root of the WIRE-IN axis) (Dhyana)
- `3ff3d44b4` 2026-06-06 `governance` governance: support 1-10 active_tracks (schema v2, primary alias) (Dhyana)
- `95c7b5bcf` 2026-06-06 `living-agent-kernel` chore(lak-e2e): seed E2E base with committed slice-2 provider tool-call gate (Dhyana)
- `758fd5fc8` 2026-06-06 `governance` governance: preserve codex #1 parallel-lane-policy + multi-lane onboarding (Dhyana)
- `4ee828e03` 2026-06-06 `living-agent-kernel` feat(operator-core): add living agent kernel os slice (Dhyana)
- `cee160f24` 2026-06-06 `runtime-truth-spine` chore(governance): refresh spine metric after NATS ack fix (Dhyana)
- `4b86b8aef` 2026-06-06 `runtime-truth-spine` fix(a2a): persist NATS consume ack intent before broker ack (Dhyana)
- `96d942bb3` 2026-06-06 `spine-adoption` chore(governance): refresh spine adoption receipt (Dhyana)
- `25510113e` 2026-06-06 `runtime-truth-spine` feat(a2a): add runtime-truth NATS transport (Dhyana)
- `2613498b9` 2026-06-06 `spine-adoption` chore(governance): refresh spine adoption metric [automated] (AmitabhainArunachala)
- `eab8c15f6` 2026-06-05 `spine-adoption` chore(governance): refresh spine adoption metric [automated] (AmitabhainArunachala)
- `aa5a8e82b` 2026-06-06 `spine-adoption` feat(go-ingest): wire idea spark ingest spine (#474) (AmitabhainArunachala)
- `c33d8758b` 2026-06-06 `unclassified` chore(docops): refresh counts for PR474 rebase (Dhyana)
- `5e001e996` 2026-06-04 `spine-adoption` chore(go-ingest): satisfy CI governance gates (Dhyana)
- `fbdf59544` 2026-06-04 `spine-adoption` docs(go-ingest): add idea spark integration spec (Dhyana)
- `ea108c4bd` 2026-06-04 `spine-adoption` test(go-ingest): cover ingest spine receipts and transport (Dhyana)
- `2abf817c1` 2026-06-04 `spine-adoption` feat(go-ingest): wire receipt-first ingest spine (Dhyana)
- `018517f12` 2026-06-05 `merge-master-mike` Collaborating with @merge_master_mike for PR updates (#495) (Copilot)
- `489f51ad8` 2026-06-06 `merge-master-mike` chore(mike): retrigger coherence delta (Dhyana)
- `2762e4fb4` 2026-06-06 `pr-repair-backlog` docs(mike): use canonical backlog mention (Dhyana)
- `bfd261a65` 2026-06-05 `pr-repair-backlog` fix merge master mike backlog defaults (copilot-swe-agent[bot])
- `141337bbf` 2026-06-05 `merge-master-mike` plan merge master mike defaults (copilot-swe-agent[bot])
- `5be923958` 2026-06-05 `live-ops-cockpit` feat(ops): add read-only live ops cockpit (#465) (AmitabhainArunachala)
- `8ea05b1f9` 2026-06-05 `live-ops-cockpit` chore(ops): repair live cockpit rebase gates (Dhyana)
- `c8e7b5cc2` 2026-06-03 `live-ops-cockpit` chore(ops): satisfy live cockpit PR gates (Dhyana)
- `0ac4b2bca` 2026-06-02 `live-ops-cockpit` feat(ops): add read-only live ops cockpit (Dhyana)
