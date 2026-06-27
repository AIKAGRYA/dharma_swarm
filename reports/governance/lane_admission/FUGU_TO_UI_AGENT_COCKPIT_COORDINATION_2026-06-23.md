# Fugu-to-UI-Agent Coordination Memo — Operator Coherence Cockpit

Date: 2026-06-23 JST  
Audience: UI / dashboard / cockpit implementation lane  
From: Fugu backplane / admission / truth-hardening lane

## Short version

I am **not** duplicating your UI lane.

You own the cockpit user interface and dashboard experience. I am taking the non-UI control-plane/backplane lane underneath it: canonical-vs-dirty truth semantics, lane admission packets, production-readiness integration, verification gates, and the future Forge/Arena input contract.

Please keep the UI modular so it can consume these packet types instead of baking in one-off assumptions from the dirty checkout.

## Division of labor

### UI lane owns

- `/dashboard/cockpit`
- Executive Board
- Kanban
- cards / sections / filters
- operator flow
- visual hierarchy
- React / Next components
- dashboard build / lint / browser verification
- display polish and Grafana-style board experience

### Fugu backplane lane owns

- What facts are allowed to appear
- Where each fact comes from
- Whether each fact is canonical, dirty, live, stale, inferred, preserved, or uncertain
- Agent lane admission schema
- Canonical-vs-dirty separation
- Production-readiness verdict integration
- Verification gates
- Extraction / PR safety
- Forge / Orchestration Arena input contract

## Shared thesis

John routinely runs 4–10 agents across multiple providers, windows, branches, worktrees, and local/remote contexts. Therefore, “clean workspace” does **not** mean single-threaded or no dirty work. It means:

- no invisible work;
- no unclassified work;
- no unpreserved valuable work;
- no unowned work;
- no unreceipted claims;
- no candidate lane silently treated as canonical truth.

The cockpit should become the control tower that makes this visible.

## Current authority boundary

Do **not** treat `/Users/dhyana/dharma_swarm` as canonical truth.

It is a dirty candidate checkout:

```text
checkout: /Users/dhyana/dharma_swarm
branch: telos-ai-seed-v0-from-sandbox
status: CANDIDATE_HIGH_PRIORITY_NOT_CANONICAL
```

Canonical authority remains:

```text
origin/main
839fd25f43c76375f49e45012fe8f20a324aa74c
[codex] governance: refresh active track and fitness properties [impact-checked] (#647)
```

Canonical portfolio:

```text
7 active / max 10
```

Dirty candidate cockpit projection may show:

```text
11 active / max 11
```

The UI must label this distinction clearly. Do not display dirty checkout portfolio state as canonical origin/main truth.

## Requested UI contract

Please design the cockpit UI so it can ingest and display these backplane concepts as first-class fields:

### Canonicality taxonomy

Each fact/card should be labelable as one of:

- `CANONICAL_ORIGIN_MAIN`
- `CLEAN_RECONCILIATION_WORKTREE`
- `DIRTY_LOCAL_CANDIDATE`
- `OPEN_PR_REMOTE`
- `LOCAL_ONLY_BRANCH`
- `STASHED_PRESERVED`
- `OFF_REPO_ARTIFACT`
- `LIVE_RUNTIME_PROOF`
- `STALE_RECEIPT`
- `UNAVAILABLE_UNCERTAIN`
- `INFERRED`

This taxonomy is critical. Without it, agents will keep mixing dirty and canonical truth.

### Lane admission packet

Every future parallel lane should be representable by a packet with at least:

- `lane_id`
- `agent_or_provider`
- `branch`
- `worktree`
- `base_ref`
- `canonicality`
- `intended_surfaces`
- `actual_touched_surfaces`
- `dirty_untracked_count`
- `verification_commands`
- `receipt_paths`
- `preservation_status`
- `depends_on`
- `conflicts_with`
- `candidate_track`
- `promotion_recommendation`
- `operator_decision_needed`

UI implication: the cockpit should be able to render lane cards/tables from this schema, not just ad hoc worktree/branch cards.

## Production readiness integration

Please leave space in the UI for production-readiness verdicts distinct from checker status.

The cockpit should ingest or link:

- `PROD_GRADE_REVIEW_RESULTS_2026-06-22`
- `PROD_READINESS_FINAL_CLOSEOUT_2026-06-23`
- `RENDER_CHECK_DISCREPANCY_RESOLVED_2026-06-23`

Track states to expose:

| Track | Production-readiness verdict |
|---|---|
| `runtime-truth-reconciliation-2026-06` | `CLOSE_READY_WITH_FOLLOWUP` |
| `runtime-truth-nats-2026-06` | `KEEP_ACTIVE_PROD_HARDENING` |
| `truth-graph-platform-2026-06` | `KEEP_ACTIVE_PROD_HARDENING` |
| `composer-holon-spine-longrun-2026-06` | `SPLIT_BEFORE_CLOSE` |
| `provider-routing-consolidation-2026-06` | `CLOSE_READY_WITH_FOLLOWUP` |

UI implication: do not render checker-`SHIPPABLE` as “done” or “closeable” without showing the stricter production verdict.

## Cockpit admission decision

Current lean:

```text
Successor/control-tower track, depending on runtime-truth but not hidden inside it.
```

Why:

- The cockpit spans runtime truth, git/worktrees/stashes, PR/CI, production readiness, lane admission, preservation, and future Forge/Arena input.
- Runtime truth is one input owner, not the whole scope.
- This is the operator’s swarm-control layer.

Suggested future track identity if admitted:

```text
operator-coherence-control-tower-2026-06
```

Do not edit `ACTIVE_TRACK.yaml` for this without explicit operator approval.

## Forge / Arena input contract

Please keep the UI object model clean enough that future Forge/Arena work can consume:

- `CockpitCard`
- `LaneAdmissionPacket`
- `ProductionReadinessVerdict`
- `ReceiptRef`
- `ArenaTask`
- `OrchestrationGenome`
- `VerifierJudgment`
- `PromotionDecision`

The future Forge/DGM loop should ingest clean cockpit-visible packets, not raw git chaos.

## Extraction and PR safety

The current cockpit candidate should be extracted into a dedicated reviewable branch, not raw-merged from the dirty checkout.

Suggested branch:

```text
governance/operator-coherence-cockpit-20260623
```

Known cockpit surfaces:

Modified:

- `api/main.py`
- `dashboard/src/app/dashboard/cockpit/page.tsx`

Added/untracked:

- `api/routers/operator_coherence.py`
- `dharma_swarm/operator_core/operator_coherence_cockpit.py`
- `scripts/runtime/operator_coherence_cockpit.py`
- `dashboard/src/lib/operatorCoherence.ts`
- `dashboard/src/hooks/useOperatorCoherence.ts`
- `dashboard/src/components/operator-coherence/`
- `tests/test_operator_coherence_cockpit.py`
- `reports/governance/operator_coherence_cockpit.json`
- `reports/governance/operator_coherence_cockpit.md`

## Safety constraints

Do not do any of the following without explicit operator approval:

- no `git reset`
- no `git clean`
- no stash drop
- no branch deletion
- no worktree prune
- no PR merge/close
- no raw union of dirty active tracks into `ACTIVE_TRACK.yaml`
- no destructive cleanup until off-machine preservation / GitHub auth / Agni copy is resolved

## What I need from the UI lane

1. Keep the UI data model modular.
2. Treat canonicality, evidence freshness, and uncertainty as visible fields — not hidden metadata.
3. Make room for lane admission packets and production-readiness verdicts.
4. Do not assume dirty checkout truth is canonical.
5. Keep the visual cockpit excellent, but avoid making one-off UI assumptions that the backplane cannot support.

## What I will produce

I will focus on:

- lane admission schema;
- canonicality taxonomy;
- production-readiness integration contract;
- cockpit admission review;
- extraction/PR safety plan;
- Forge/Arena input contract;
- verification gates for making candidate lanes promotable.

That should complement your UI lane without competing with it.
