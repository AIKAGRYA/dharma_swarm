# VentureCell Operator OS Score-50 Planner Contract

Generated: 2026-06-02
Mission: `20260602-venturecell-operator-os-8h`
Baseline commit: `648b958d Add Darshan Go receipt external reader gate`

## Mission Diagnosis

The original mission is alive by heartbeat, but not productive by artifact
progress. The runner is cycling and ready checks pass, but the builder task has
not created the expected mission artifact under `reports/venture_operator_os/`
and has not recorded a task completion, block, or failure receipt.

The right repair is not another unmanaged swarm. The repair is to convert the
run into a receipt-backed score-50 packet with explicit artifacts, tests, and
blocked conditions.

## Score-50 Definition

This mission reaches score 50 only when it has all of the following:

1. A planner contract with concrete scope, stop rules, file paths, verifiers,
   and score allocation.
2. A builder receipt or blocked builder receipt with exact evidence.
3. An adversarial audit that blocks false autonomy, fake live transport, raw
   private evidence, external action leakage, and dashboard theater.
4. A verifier matrix with command outputs and pass/fail results.
5. An operator handoff with current state, next action, and remaining product
   gap.
6. Corresponding `ds-goal record` receipts for all closed lanes.

## Score Allocation

| Area | Points | Evidence |
|---|---:|---|
| Darshan Go external-reader gate operational proof | 20 | Commit `648b958d`, tests, control-surface row |
| ds-goal and long-harness receipt discipline | 12 | Existing mission plus `venturecell-operator-os-8h-score50` harness |
| TaskBoard/A2A DONE-gate projection or bounded spec | 8 | Internal surface map plus blocker if unsafe |
| VentureCell Operator OS read-only projection | 10 | Profile/departments/canvas/attention/daily-cycle plan mapped to files |
| Chetana/wiki memory-kernel path | 6 | Read-only MemoryKernel projection plan and retrieval evals |
| Daily operating digest with receipts/blockers | 6 | Handoff contract and next artifact path |
| Adversarial audit and verifier matrix | 8 | This packet plus test results |

Target realistic result: 56-66/100 for mission-control readiness without
external action. Anything above 70/100 needs real external reader/client/revenue
feedback and should be treated as overclaiming.

## Polsia Structure To Surpass

Public evidence indicates Polsia's real structure is a company-instance
operating system:

- company instance ledger;
- CEO, Engineering, Growth, Research, Browser, Onboarding, Support/Chat roles;
- recurring autonomous operations;
- broad integration surface;
- live operational telemetry;
- task/execution/event streams;
- dry-run vs real external action boundary;
- public activity narrative.

Dharma Swarm should copy the company-instance ledger, role/task/event stream,
daily operating cycle, and live telemetry pattern. DS should surpass Polsia
with signed receipts, budget gates, verifiers, Chetana memory, TaskBoard/A2A
state, and governance-backed external action approval.

## Cofounder Structure To Borrow

Cofounder contributes the cleaner company-OS shell:

- company workspace;
- departments;
- agents with instructions, skills, tools, and model;
- Canvas;
- Library;
- Plan/Execute;
- attention queue;
- task states;
- integrations;
- publishing gates.

Dharma Swarm should implement this as read-only projections over existing
surfaces first, not as a new dashboard substrate.

## Existing DS Surfaces To Use

| Operator OS concept | DS surface |
|---|---|
| Company profile | `docs/governance/VENTURE_CELL_PORTFOLIO.yaml`, `VentureCellV1` |
| Departments | employees runtime, external agent registration, A2A identities |
| Canvas | TaskBoard + A2A + Darshan bundle + control surface projection |
| Attention queue | failed/blocked/review tasks, gate decisions, external action queue |
| Library | Chetana/wiki plus Darshan artifacts/source packs/receipts |
| Plan/Execute | `governed_work_admission.py` and `ds-goal` leases |
| Daily operating cycle | `daily_operating_brief.py`, operating facts, Darshan conductor |
| Live transport | NATS only when ack proof exists |

## Stop Conditions

Record `blocked`, not `completed`, if any of these occur:

- real external contact, credentials, payment, publishing, deploy, push, or
  merge is required;
- A2A/NATS live authority is needed without ack proof;
- dirty worktree conflicts make scoped edits unsafe;
- focused Darshan gate tests fail and cannot be repaired quickly;
- Chetana retrieval cannot be verified;
- no new completion receipt appears after 90 minutes of claimed work;
- the only path forward is to create a new dashboard/substrate instead of
  wiring existing surfaces.

## Exact Next Productive Artifact

The next productive builder artifact is:

`reports/venture_operator_os/20260602-8h/build_receipt.md`

It must contain changed files or no-change statement, tests, current blockers,
and a `ds-goal record` closure for the builder lane.

