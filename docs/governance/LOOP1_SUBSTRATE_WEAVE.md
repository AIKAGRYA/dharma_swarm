# Loop 1 Substrate Weave

This note ties the current Loop 1 truth-registry work to the four seams that
must be made load-bearing before broader autonomous/runtime claims are credible.

## 1. Daily Brief / Operator Brief

Current canonical writer on this branch is `dharma_swarm.insight_brief`.
`docs/governance/CANONICAL_DAILY_BRIEF_WRITER_2026-05-02.md` explicitly parks
the PR57 `operator_brief` package and says it must stay disabled unless Dhyana
promotes it.

Branch truth:

- `InsightBriefBuilder.publish()` executes `KnowledgeArtifact.Publish` through
  `OntologyActionGateway.execute_action_or_fail()`.
- `tests/test_insight_brief.py::test_publish_action_passes_gates` verifies the
  resulting action history and required gates.
- no `dharma_swarm/operator_brief` package is present in this branch.

Therefore the next safe action is not to force `operator_brief` ActionExec
wiring into this branch. The safe path is:

1. keep `insight_brief` canonical until the promotion decision changes;
2. if `operator_brief` is promoted, require ActionProposal, GateDecision,
   ActionExecution, Outcome, ValueEvent, Contribution, and WitnessLog coverage
   in one focused PR;
3. prevent two parallel daily-brief surfaces from writing competing ontology
   contracts without an explicit governance decision.

## 2. Agent Identity

`dharma_swarm.models.AgentConfig` is the canonical runtime identity constructor
on this branch. The repo still contains several identity-shaped schemas for
disk persistence, API projection, telemetry, and domain-local trials.

The immediate weave is to pin that inventory in a test. New identity-shaped
classes should fail the guard until they are either mapped to `AgentConfig` or
accepted as explicitly non-runtime projection schemas.

## 3. Shared Routing

`dharma_swarm.providers.ModelRouter` and `RoutingMemoryStore` are the shared
routing substrate. Some surfaces still call runtime providers directly,
including autonomous agents and dashboard chat subprocess completion.

Current inventory:

- `dharma_swarm.swarm.SwarmManager` constructs the shared router with
  `create_default_router()`.
- `dharma_swarm.agent_runner.AgentRunner` uses `complete_for_task()` when its
  provider is routed.
- `dharma_swarm.autonomous_agent.AutonomousAgent` still creates runtime
  providers directly in two provider loops.
- `api.routers.chat` still creates a runtime provider directly for dashboard
  chat subprocess completion.

Those are hot paths. The safe weave is a separate routing PR with focused tests
for provider selection, fallback behavior, routing-memory writes, and dashboard
chat compatibility. It should not be bundled with identity or daily-brief work.

## 4. Truth Docs

`docs/interface_mismatches.yaml` is the machine-readable truth registry for
open/resolved interface mismatches. Narrative maps such as
`INTERFACE_MISMATCH_MAP.md`, `CYBERNETIC_LOOP_MAP.md`, and
`MODEL_ROUTING_MAP.md` must be treated as explanatory surfaces that follow code
and tests, not as authority by themselves.

The recurring rule is simple: close the smallest real loop, write the guard,
then update the narrative.
