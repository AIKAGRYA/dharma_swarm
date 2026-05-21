# PGE Autonomous Build System

Status: repo bridge for the PGE governance standard
Owner: context quorum / long-running harness / AgentOps
Scope: autonomous-build doctrine and repo wiring, not a new daemon.

## Plain English

PGE means Planner / Generator / Evaluator. It is the standing rule for any serious autonomous build: one role sets the product boundary, one role builds inside a contract, and one separate adversarial role tries to prove the work is not done.

The Memory Palace and Claude memory surfaces define PGE as governance. The repo operationalizes it through `docs/ops/LONG_RUNNING_HARNESS.md`, `scripts/runtime/long_running_harness.py`, context quorum, AgentOps work packets, and future command-plane projection.

## Authority Chain

Use this order when documents disagree:

1. `docs/governance/ACTIVE_TRACK.yaml`
2. `docs/ops/context_quorum_policy.json`
3. `docs/ops/PGE_AUTONOMOUS_BUILD_SYSTEM.md`
4. `docs/ops/LONG_RUNNING_HARNESS.md`
5. `~/.claude/projects/-Users-dhyana/memory/feedback_pge_harness_standard.md`
6. `~/.dharma/knowledge/wiki/concepts/pge-harness-pattern.md`

The external memory/wiki files explain the standard. The repo files define how agents must apply it inside `dharma_swarm`.

## Trigger

Use PGE when any one condition is true:

- build is expected to last at least 30 minutes
- build has at least 3 sprints or iterations
- build creates or changes at least 1 user-facing verifiable artifact
- build touches command plane, Goodworks DGM, governance, tests, measurement, CI, or persistent-agent substrate

## Repo Wiring

| Layer | Repo surface | Responsibility |
|---|---|---|
| Entry | `make onboard` | Shows current active track, dirty state, and long-run harness pointer |
| Context gate | `make context-quorum-check` | Records risk, receipts, protected-file hits, and handoff state |
| Harness scaffold | `make long-harness-init` | Creates filesystem run state under `~/.dharma/harness_runs/<run_id>/` |
| PGE metadata | `run.json` `harness_standard` | Records PGE rule set, threshold, memory path, and wiki path |
| Contract gate | `make long-harness-validate PHASE=contract` | Fails until Generator and Evaluator both accept the contract |
| Execution boundary | `scripts/governance/run_agent_work_packet.py` | Preferred code-edit boundary once a generator starts work |
| Completion gate | `make long-harness-validate PHASE=complete` | Fails unless contract is accepted and progress is complete/passed/landed |
| Projection | command-plane future work | Later UI should display run status, contract state, findings, and evidence paths |

## PGE Roles

| Role | Repo expression | Rule |
|---|---|---|
| Planner | `planner/spec.md`, `planner/plan.json` | Stays high-level; sets product boundary and non-goals |
| Generator | `generator/GENERATOR_BRIEF.md` plus work-packet execution | Builds only after accepted contract; declares file scope |
| Evaluator | `evaluator/EVALUATOR_BRIEF.md`, `rubrics/evaluator_rubric.json` | Harsh, separate, evidence-based, output-only judge |
| Trace Critic | `traces/trace_index.jsonl`, `handoff/HANDOFF.md` | Reads traces and updates future rubrics only after repeated patterns |

These are phases of one harness run. They are not automatically new L4 agents and do not grant authority outside the contract.

## Ten Standing Rules

1. Self-evaluation is a trap; use a separate adversarial evaluator.
2. Compaction is not coherence; filesystem state is authoritative.
3. Structured handoffs and clean context beat chat-only continuity.
4. Subjective quality is gradable through explicit weighted rubrics.
5. Trace reading is the primary debugging loop.
6. Contracts should carry at least 20 testable assertions for long builds.
7. Evaluator prompts must be harsh enough to counter sycophancy.
8. Do not muddy Generator and Evaluator contexts.
9. Leave timestamped JSON breadcrumbs and a compact handoff.
10. Co-evolve the harness with model releases and record sunset criteria.

## Command Plane Application

For command-plane work, PGE is mandatory for context shell, cockpit, 3D benchmark, and route-consolidation PRs. The evaluator must fail a change that makes the interface prettier while reducing operator context density.

The first planned command-plane PGE run is:

```bash
make long-harness-init \
  RUN_ID=command-plane-context-shell-2026-05 \
  MODE=command-plane \
  GOAL="Command-plane PR 2: context-dense operator shell"
```

That scaffold is not build permission. Build permission starts only after:

```bash
make long-harness-validate RUN_ID=command-plane-context-shell-2026-05 PHASE=contract
```

## Anti-Slop Boundaries

- Do not create a second autonomous runner when AgentOps work packets can own execution.
- Do not let one agent plan, build, judge, and remember its own work.
- Do not call an initialized scaffold complete.
- Do not use UI screenshots as evidence unless the real route or a clearly declared fixture was opened.
- Do not rewrite tests, governance, CI, or scorer files without context quorum and explicit contract scope.
- Do not import external memory rules as unbounded authority; repo governance and active track still win.

## Future Projection

The command plane should eventually show:

- harness run id
- active track id
- PGE phase: scaffold / contract / building / evaluating / complete / blocked
- contract criterion count
- generator/evaluator acceptance
- context quorum receipt
- dirty-worktree snapshot
- protected-file hits
- evaluator findings
- evidence links
- next operator action

That dashboard should be a read-only projection over harness state first. It should not become a new coordination substrate.
