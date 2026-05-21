# Command Plane Long-Running Harness Application

Status: future command-plane PGE operating rule
Parent spec: `docs/ops/LONG_RUNNING_HARNESS.md`
PGE bridge: `docs/ops/PGE_AUTONOMOUS_BUILD_SYSTEM.md`

## Why This Exists

The command-plane redesign is too broad for loose multi-agent work. Palette revaluation, context-density layout, cockpit refactors, 3D benchmark work, and route consolidation each need independent contracts and adversarial evaluation.

The harness layer turns each future command-plane PR into a file-backed PGE run: Planner sets boundary, Generator builds inside the accepted contract, Evaluator harshly grades evidence.

This is an evidence layer first. It should not add dashboard chrome before the backend run records, contract status, and evaluator findings are stable.

## Do Not Interrupt Current Palette Lane

The Nihonga palette PR is already in motion. This harness applies to future command-plane work and to any follow-up review of that PR. Do not touch `dashboard/src/lib/theme.ts`, `dashboard/src/app/globals.css`, or `dashboard/src/lib/motion.ts` from this harness lane while another agent owns them.

## First Future Run

Recommended run:

```bash
make long-harness-init \
  MODE=command-plane \
  GOAL="Command-plane PR 2: context-dense operator shell"
```

The output run directory becomes the shared filesystem state for planner, generator, evaluator, and trace critic.

If code editing starts, the generator should route through the existing AgentOps work-packet boundary rather than a bespoke runner. The command plane should later project the resulting run status, contract state, and evaluator findings as operational truth.

Do not treat scaffold validation as completion. A future command-plane run is only build-ready after `PHASE=contract` passes, and only landable after `PHASE=complete` passes with evaluator evidence. PGE requires at least 20 testable assertions for a serious build; the initial seed below is only a starting point.

## PR 2 Done Contract Seed

The generator and evaluator should negotiate from this seed:

1. The shell increases context carrying capacity on `/dashboard/control-surface`.
2. The operator can see active track, dirty-worktree pressure, recent evidence, runtime health, and next action without page-hopping.
3. The layout remains legible at desktop and narrow viewport.
4. No new route, API, store, daemon, or surface is added unless manifest-registered.
5. Screenshots or browser receipts exist for `/dashboard`, `/dashboard/control-surface`, and one dense route.
6. The evaluator may fail the PR if visual design improves but context density worsens.
7. The handoff names any surface deferred to later PRs.
8. Any change to tests, CI, governance, or active-surface registration is called out as a protected-file hit.
9. The final contract reaches the PGE criterion bar before implementation starts.
10. The evaluator judges output/evidence only and does not inherit generator hidden reasoning.

## Phase Mapping

| Command-plane phase | Harness mode | Evaluator emphasis |
|---|---|---|
| Phase 1 palette | Review-only after current lane lands | Taste invariants, contrast, no surface change |
| Phase 2 context shell | Full planner/generator/evaluator | Context density, evidence legibility, operator flow |
| Phase 3 cockpit v2 | Full planner/generator/evaluator | Component craft, state clarity, no route sprawl |
| Phase 4 3D benchmark | Full harness plus benchmark witness | 60fps, fallback, nonblank canvas, reduced-motion |
| Phase 5 route consolidation | Full harness plus active-surface manifest check | No duplicate routes, migration clarity |

## Evaluator Rubric Override

For command-plane runs, the evaluator should weight:

- context_density: must pass
- functionality: must pass
- design_quality: must pass
- originality: should pass
- craft: should pass
- governance_integrity: must pass
- evidence: must pass
- traceability: must pass

## Trace Review

After each command-plane PR, the trace critic reads:

- harness `traces/trace_index.jsonl`
- browser/screenshot receipts
- `git diff --stat`
- failed commands
- evaluator findings

The critic updates future command-plane prompts only when a repeated failure appears. One-off taste complaints do not become new rules.
