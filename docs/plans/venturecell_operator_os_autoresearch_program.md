# VentureCell Operator OS AutoResearch Program

Date: 2026-06-02
Status: active program kernel
Contract: `docs/plans/2026-06-02-venturecell-operator-os-autoresearch-8h-goal.md`
Baseline: commit `1aca07a1 Add VentureCell Operator OS Level 70 surface`

## Purpose

This is the local `program.md` for the VentureCell Operator OS AutoResearch
run. Future agents must read it before changing the Operator OS seam.

The program optimizes company-level Operator OS score, not isolated green tests.
Every loop must make a bounded claim, patch or reject it, evaluate it, attack it,
keep/revert/queue it, write receipts, update score, and metabolize the learning.

## Editable Surfaces

- `dharma_swarm/venture_cell/operator_os/`
- `tests/test_venture_cell_operator_os_projection.py`
- focused adjacent tests named in the 8h goal contract
- `reports/venture_operator_os/<run_id>/`
- this program file and the 8h goal packet when receipts justify updates

## Forbidden Surfaces

- external outreach, spend, deploy, publish, push, merge, payment, or credential mutation
- new runners, task boards, queues, databases, routers, daemons, dashboards, or control planes
- Chetana trusted promotion without existing gates
- any code path that weakens Darshan external-reader, GO evidence receipt, governed admission, or Chetana gates
- any claim of live A2A/NATS authority without fresh ack proof tied to the action

## Score Metric

Use the contract scorecard after every loop:

| Area | Points |
|---|---:|
| Operator clarity | 15 |
| Memory usefulness | 15 |
| Task truth | 15 |
| Governance safety | 15 |
| Iteration quality | 15 |
| Product structure | 10 |
| Tests/evals | 10 |
| Metabolization | 5 |

Score from evidence only. Heartbeats, leases, and generated prose do not score
unless attached to a product artifact, deterministic eval, verifier output, or
ledger receipt.

## Loop Receipt Schema

Each 45-60 minute loop receipt must include:

- `loop_id`
- `started_at_utc`
- `ended_at_utc`
- `hypothesis`
- `patch_scope`
- `changed_files`
- `eval_commands`
- `eval_results`
- `adversarial_review`
- `decision`: `keep`, `revert`, `queue`, or `reject`
- `score_before`
- `score_after`
- `receipt_refs`
- `metabolization_note`
- `next_loop_target`

## Keep/Revert Rules

Keep a patch only when all are true:

- it improves at least one company-level score area;
- focused tests or deterministic evals cover the claim;
- gates remain default-deny for external authority;
- no unrelated dirty files are staged or rewritten;
- the receipt states what remains incomplete.

Revert or reject when any are true:

- a gate is weakened to pass a test;
- the patch creates a new substrate instead of projecting existing truth;
- MemoryKernel output cannot cite tier and source root;
- ds-goal/A2A/NATS liveness is treated as completion without task or receipt proof;
- external action would be required.

## MemoryKernel Query Evals

Minimum deterministic query prompts:

- `Polsia Cofounder VentureCell Operator OS`
- `Darshan external reader gate Go evidence receipt`
- `Go evidence receipt source_url event_uid accepted`
- `Cofounder Canvas Library Plan Execute publishing`
- `Chetana wiki memory kernel staged trusted quarantine`
- `VentureCell autonomy ladder external action approval`

A passing result must expose:

- at least one match where relevant;
- tier: `trusted`, `staged`, or `quarantine`;
- source root or local path;
- no trusted-promotion claim;
- status when only untrusted matches exist.

## Company UX Questions

Every operator-facing surface must answer:

- What is blocked?
- Who owns it?
- What evidence exists?
- What is the next governed action?
- What is the current autonomy level?
- What must happen before Growth or Comms can act externally?
- What MemoryKernel knowledge is available, truncated, missing, or untrusted?

## Current Loop Queue

1. Program kernel plus MemoryKernel query evals.
2. Operator digest tier clarity and query-result surfacing.
3. ds-goal truth reconciliation packet for raw vs reconciled task counts.
4. Darshan GO/external-reader linkage receipt packet without external action.
5. Final adversarial audit, score history, metabolization, and next goal packet.
