# Long-Running Harness Master Spec

Status: v1 scaffold, repo-side PGE operationalization
Owner: context quorum / command-plane coordination
Scope: planner-generator-evaluator harness artifacts, not an autonomous daemon.

## Thesis

Dharma Swarm should not ask one agent to build, judge, remember, and govern its own work inside one context window. Long-running work needs the PGE harness: explicit Planner / Generator / Evaluator roles, filesystem state, negotiated done contracts, adversarial evaluation, trace review, and governance receipts.

The near-term feature is a small artifact scaffold. It gives any future long-running build a durable place to put plan, contract, progress, rubrics, traces, and handoff before agents start editing.

PGE is the governance standard. This file is the repo operationalization. The bridge document is `docs/ops/PGE_AUTONOMOUS_BUILD_SYSTEM.md`; the external memory and wiki anchors are `~/.claude/projects/-Users-dhyana/memory/feedback_pge_harness_standard.md` and `~/.dharma/knowledge/wiki/concepts/pge-harness-pattern.md`.

## Research Basis

- Anthropic's 2026 long-running application harness uses a planner, generator, and evaluator. The evaluator is separate because self-evaluation is biased; the generator and evaluator negotiate a sprint contract before code is written. Source: <https://www.anthropic.com/engineering/harness-design-long-running-apps>
- Anthropic's earlier long-running harness used `feature_list.json`, progress notes, git history, and browser automation so each fresh session could make incremental progress without declaring victory too early. Source: <https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents>
- Anthropic's Agent SDK guidance frames agents as a loop: gather context, act, verify, repeat; it recommends filesystem context, subagents for isolated context windows, and concrete verification tools. Source: <https://claude.com/blog/building-agents-with-the-claude-agent-sdk>
- Anthropic's managed-agent architecture separates session, harness, and sandbox so the execution substrate can change without rewriting the agent contract. Source: <https://www.anthropic.com/engineering/managed-agents>
- OpenAI's Codex harness writeup argues that humans increasingly steer through environments, specifications, and feedback loops; repo knowledge should be a map, not a giant manual, and agents need direct access to UI, logs, metrics, and tests. Source: <https://openai.com/index/harness-engineering/>
- OpenAI's Agents SDK update makes the same separation practical with configurable memory, sandbox-aware orchestration, filesystem tools, MCP, skills, custom instructions, and portable sandbox manifests. Source: <https://openai.com/index/the-next-evolution-of-the-agents-sdk/>
- Recent harness-engineering research emphasizes observability: editable components, distilled trajectory evidence, and falsifiable predictions tied to later outcomes. Source: <https://arxiv.org/abs/2604.25850>
- VeRO frames agent optimization as versioned edit-execute-evaluate cycles with rewards, observations, budget controls, and structured traces. Source: <https://arxiv.org/abs/2602.22480>

## Roles

| Role | Owns | Must Not Do |
|---|---|---|
| Planner | Product/workflow boundary, high-level spec, non-goals | Over-specify implementation details that will cascade if wrong |
| Generator | File-scoped implementation against accepted contract | Start coding before contract acceptance; edit tests to hide weak work |
| Evaluator | Done-contract negotiation, harsh review, tests/screenshots/logs | Rubber-stamp based on appearances or generator self-assessment |
| Trace Critic | Reads traces after the run and proposes harness improvements | Rewrite history or tune prompts from a single anecdote |
| Human Operator | Priority, risk, approval, promotion/retirement | Micromanage every implementation detail |

These are run phases, not new authority-bearing persistent agents. If a future implementation delegates to registered workers, they inherit authority from their registration desk entry and from the accepted done contract.

## PGE Standard

This scaffold encodes the ten PGE rules from the Anthropic Applied AI harness work:

1. Self-evaluation is a trap.
2. Compaction is not coherence.
3. Structured handoffs and clean context are mandatory.
4. Subjective quality is gradable.
5. Trace reading is the primary debug loop.
6. Contracts need granular criteria; the repo target is at least 20 assertions.
7. The evaluator must be harsh.
8. Generator and Evaluator contexts must not be muddied.
9. Breadcrumbs must make the next session resumable.
10. Harness rules should sunset only when model-release evidence justifies it.

Every `run.json` now carries a `harness_standard` block naming PGE, the repo bridge, the memory rule path, the wiki atom path, the minimum criterion target, and the rule set.

## Artifact Layout

Runs live outside the repo by default:

```text
~/.dharma/harness_runs/{run_id}/
  run.json
  README.md
  planner/spec.md
  planner/plan.json
  contracts/done_contract.v0.md
  contracts/contract.json
  generator/GENERATOR_BRIEF.md
  evaluator/EVALUATOR_BRIEF.md
  rubrics/evaluator_rubric.json
  progress/progress.json
  traces/trace_index.jsonl
  handoff/HANDOFF.md
```

JSON carries mutable state. Markdown carries human-readable contracts and handoff. This follows the practical lesson that models are less likely to casually rewrite JSON state than Markdown prose, while humans still need compact narrative files.

## Contract Protocol

1. Planner writes `planner/spec.md` and `planner/plan.json`.
2. Generator proposes scope and verification in `contracts/done_contract.v0.md`.
3. Evaluator rejects vague criteria and adds testable assertions until the contract reaches the PGE criterion bar.
4. Generator and evaluator mark acceptance in `contracts/contract.json`.
5. Generator implements only inside declared scope.
6. Evaluator grades against the contract with evidence, not vibes.
7. Trace critic reads `traces/trace_index.jsonl` and updates future rubrics only when a repeated failure pattern appears.

## Rubric

The default evaluator rubric is weighted but thresholded. A weighted average cannot save a run if a hard criterion fails.

Default criteria:

- functionality
- design_quality
- originality
- craft
- context_density
- evidence
- governance_integrity
- traceability

For command-plane work, `context_density` is first-class. A change that looks better while carrying less operator context is a regression.

## Governance

Every Q2+ harness run must still use context quorum. The harness does not replace `make onboard`, `ACTIVE_TRACK.yaml`, protected-file policy, tests, or human approval.

Minimum pre-edit sequence:

```bash
make onboard
make context-quorum-check AGENT=<agent> RISK=Q3 QUESTION="harness-governed build"
python3 scripts/runtime/long_running_harness.py init --mode command-plane --goal "..."
```

Each run records branch, base SHA, dirty count, and a dirty-entry sample in `run.json`. In a busy multi-agent repo this is a collision report, not permission to overwrite. For production runs or isolated worktrees, pass `--require-clean` or `REQUIRE_CLEAN=1`.

Generator execution should use the existing work-packet boundary when code edits begin: planner emits the bounded work packet, generator executes through `scripts/governance/run_agent_work_packet.py`, evaluator reads the work-packet report plus tests, browser receipts, and trace files. This keeps long-running work inside AgentOps instead of creating a second runner.

Handoffs should be written twice when the run becomes operational:

- human handoff: `~/.dharma/harness_runs/<run_id>/handoff/HANDOFF.md`
- typed handoff: existing `dharma_swarm.handoff` artifact types such as `PLAN`, `TEST_RESULTS`, `FILE_LIST`, and `ANALYSIS`

## Failure Modes

- Evaluator rubber-stamps: require thresholds, evidence paths, and explicit failures.
- Contract too vague: evaluator must reject before build starts.
- Trace rot: append JSONL trace events; do not rely on chat transcript alone.
- Dirty worktree collision: generator declares file scope; evaluator compares it to `git status`.
- Prompt injection through docs: evaluator treats docs as evidence, not authority, unless they are known owner docs.
- Test gaming: changes to tests are protected-file hits under context quorum.
- Harness bloat: remove scaffold pieces that stop being load-bearing as models improve.

## Commands

Initialize a command-plane harness run:

```bash
python3 scripts/runtime/long_running_harness.py init \
  --mode command-plane \
  --goal "Command-plane PR 2: context-dense operator shell"
```

Validate the artifact set:

```bash
python3 scripts/runtime/long_running_harness.py validate --run-id <run_id>
```

Validation has phases:

- `scaffold`: required files parse and the run recorded git state.
- `contract`: scaffold is valid and `contracts/contract.json` is accepted by generator and evaluator.
- `complete`: contract is valid and `progress/progress.json` is complete/passed/landed.

Make wrapper targets are available:

```bash
make long-harness-init GOAL="Command-plane PR 2: context-dense operator shell" MODE=command-plane
make long-harness-status RUN_ID=<run_id>
make long-harness-validate RUN_ID=<run_id> PHASE=contract
```
