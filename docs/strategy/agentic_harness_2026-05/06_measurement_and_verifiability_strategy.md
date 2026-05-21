# 06 Measurement And Verifiability Strategy

Expert lens: measurement scientist and CI guardian.
Local grounding: written after reading the 33-file local evidence base in `00_local_evidence_base.md`.
External grounding: STATE-Bench, Anthropic multi-agent research, GitHub Copilot usage metrics, Greptile review loop, ContextCov.

## Core Claim

Measurement integrity matters more than agent confidence. Dharma Swarm should copy the domains where models are strongest: deterministic, verifiable loops with fast feedback and durable traces.

The transcript is right that code works well for agents because it is testable. Dharma Swarm's moat should be turning agent coordination into a testable domain.

## What To Measure

Agent task outcomes:

- completed tasks.
- failed tasks.
- stale handoffs.
- tests run.
- protected-file touches.
- review findings.
- rework required.

Context quality:

- tools checked.
- source diversity.
- stale index detections.
- manifest completeness.
- disagreement handling.
- time to first useful edit.

Memory quality:

- recall hit relevance.
- stale memory incidents.
- duplicate memory rate.
- memory writes with source refs.
- task improvement after recall.

Repo health:

- CI pass rate.
- build pass rate.
- frontend build state.
- import smoke state.
- broken-register age.
- active-track progress.

Agent cultivation:

- role continuity.
- autonomous successful wake actions.
- peer review acceptance.
- skill acquisition evidence.
- measured improvement over baseline.

## CI Beats Judgment

If an agent says a build is safe and CI says no, CI wins. If an agent says a measurement harness should be edited, the harness becomes protected evidence and needs independent review. If an agent modifies tests to make itself look good, the task should be marked contaminated until a reviewer validates the test change against behavior.

## Omega And HP

Omega and HP measurements should become sacred instrumentation surfaces:

- Agents may read them freely.
- Agents may propose changes with rationale.
- Agents may not quietly alter scoring definitions.
- Scorer changes require before/after run evidence.
- Any benchmark improvement must cite the exact diff, test command, and artifact.

## Arena Design

Start with small arenas:

- onboarding compression: can an agent reach useful context in under 5 minutes?
- handoff fidelity: can another agent continue without asking the human?
- protected-file compliance: does the agent avoid Q4 surfaces?
- repo-map freshness: does the map identify stale assumptions?
- PR review quality: does the reviewer find real defects without noise?

Each arena needs baseline, task set, scorer, artifact, and regression threshold.

## Learning From STATE-Bench

STATE-Bench asks whether memory improves reliability, task completion, efficiency, and user experience. Dharma Swarm should use that exact stance for Memory Palace. Do not celebrate memory because it exists. Celebrate it only when it reduces repeated failure and improves measured task outcomes.

## Immediate Move

Create a lightweight `measurement_receipt.json` convention for Q3/Q4 work:

```json
{
  "commands_run": [],
  "ci_checked": false,
  "tests_changed": false,
  "protected_measurement_paths_touched": [],
  "before_metric": null,
  "after_metric": null,
  "review_required": true
}
```

Do this before adding more dashboards.
