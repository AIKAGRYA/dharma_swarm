# External Audit: Action Authority Gate Spec

**Date:** 2026-05-04  
**Worktree:** `/Users/dhyana/dharma_swarm_action_authority_spec`  
**Branch:** `chore/action-authority-gate-spec`  
**Audited commit:** `2049e51 docs(governance): specify action authority gate rollout`  
**Primary artifact:** `docs/plans/2026-05-04-action-authority-gate-spec.md`

## Verdict

**PASS WITH CHANGES.**

`ActionAuthorityGate` is genuinely missing as a unified side-effect authority funnel. The current repo has strong component substrates, but no equivalent hot-path gate tying concrete actor, surface, action, warrant, telos, policy, guardrail, semantic verdict, and ontology persistence together.

The spec should **not** become the implementation contract as-is. It can become the implementation contract only after the changes below, and only after the current Operator Brief seam is acceptance-tested or the canonical active-track docs explicitly supersede that order.

## Tool Status

- `rg` and direct source inspection were authoritative.
- GitNexus MCP was unavailable in this session.
- `npx gitnexus status` reported: `Repository not indexed. Run: gitnexus analyze`.
- `gitnexus analyze` was not run because it writes state and the audit was read-only.
- ContextPlus was available, but its root/index state was not cleanly bound to this worktree. It was useful as auxiliary semantic context, not as authoritative evidence.

The spec's evidence-pass language should be updated to match current tool reality instead of saying only that ContextPlus timed out.

## Highest-Risk Findings

1. **Active-track conflict.** `CLAUDE.md`, `BUILD_SESSION_ENTRYPOINT.md`, and `NEXT_10_SUBSTRATE_TODO.md` all say the active engineering track is the ontology-native Operator Brief seam. Broad AAG implementation before that seam is accepted would violate the current track order unless the canonical docs are explicitly updated.

2. **Persistence contract is not strong enough for enforce mode.** The proposed `ActionProposal -> GateDecisionRecord -> ExecutionLease -> Outcome` path is the right existing ontology path, but `TelicSeam` is best-effort and currently swallows failures. Enforce mode needs explicit failure behavior, durable decision identity, and `WitnessLog` linkage.

3. **TelicSeam constructor mismatch is real.** `orchestrator.py` calls `TelicSeam(..., registry_path=ontology_db)`, while `TelicSeam.__init__` accepts `path`, not `registry_path`. The exception is swallowed, so ontology writeback can silently fail.

4. **Runtime bypasses are real.** Verified bypass surfaces include AgentRunner local write/edit/shell tools, autonomous agent world actions, `world_actions.py`, ontology API mutation endpoints, agentic chat tools, cron handlers, sandbox/runtime adapters, diff application, A2A dispatch, roaming dispatch, and TUI subprocess adapters.

5. **The 50-file rule needs an implementation-level override.** The spec scopes deep read to high-authority governance/release/diff surfaces, which is directionally correct. The current `build_fourfold_action_warrant` default applies `MIN_EVIDENCE_FILES = 50` to any required trigger. AAG must pass per-tier thresholds or refactor Fourfold evidence policy, otherwise it will overblock or become a runtime sink.

## Governance Compliance

The spec's location under `docs/plans/` is compliant for a proposed execution plan. It subordinates itself to the canonical docs and avoids a new top-level package file by pointing to `dharma_swarm/action_authority/`.

The non-compliance risk is activation order, not file placement. If AAG becomes the next active implementation track, `BUILD_SESSION_ENTRYPOINT.md` and `NEXT_10_SUBSTRATE_TODO.md` must be updated first.

## Multiple Seams Answer

Yes, multiple seams can be worked in parallel in a narrow sense, but not as multiple unbounded implementation tracks.

Safe parallelism:

- Independent read-only audits.
- Spec refinement and surface mapping.
- Small prerequisite fixes that directly support the active seam, such as the `TelicSeam` constructor/writeback proof.
- Shadow-only instrumentation that does not alter runtime behavior and does not claim acceptance of a second seam.
- Test design for future surfaces.

Unsafe parallelism:

- Opening another user-visible seam before Operator Brief is accepted.
- Adding new bridges, routers, ledgers, memory stores, or authority tables.
- Enforcing AAG across broad runtime surfaces before shadow evidence and current-track acceptance.
- Splitting work across tracks in a way that prevents substrate-nativeness from being measured end-to-end.

The practical rule is: one seam is the active falsifiability target; other seams may be audited, specified, or prepared only if they do not compete for canonical track status or introduce new runtime substrates.

## Required Spec Edits Before Implementation

- State that AAG is queued after Operator Brief acceptance, or explicitly supersede the canonical active track.
- Correct the GitNexus and ContextPlus evidence-pass status.
- Require aggregate `GateDecisionRecord` semantics because the current ontology has one-to-one `ActionProposal.has_gate_decision`.
- Add `WitnessLog` linkage and visible failure behavior.
- Define enforce-mode behavior when persistence fails.
- Define per-tier evidence thresholds and the exact call contract with `build_fourfold_action_warrant`.
- Expand the runtime surface list with exact files for chat, TUI, A2A, roaming, sandbox, and diff/self-improvement.
- Split the broad PR5 surface into smaller PRs.

## Recommended PR Order

1. Spec correction only: tool status, active-track language, exact surfaces, thresholds.
2. `TelicSeam` constructor/writeback proof.
3. AAG model/classifier under `dharma_swarm/action_authority/`, default off.
4. Orchestrator dispatch shadow mode with aggregate gate decision.
5. AgentRunner local tool shadow mode.
6. API/chat and ToolRegistry integration.
7. Autonomous/world action integration.
8. Cron integration.
9. Sandbox/runtime adapter integration.
10. Diff/self-improvement integration.
11. A2A, roaming, TUI, and external bridge integration.
12. Narrow enforce-mode rollout after shadow logs show acceptable false positives.

## Missing Test Matrix

- Mode semantics: off, shadow, enforce.
- Stale, missing, or mismatched warrant binding.
- Per-tier 50-file threshold behavior.
- `TelicSeam` constructor and durable writeback.
- `WitnessLog` linkage for allow, review, and block.
- Enforce-mode persistence failure.
- Direct side-effect blocking for AgentRunner, autonomous tools, world actions, API, chat, cron, sandbox, diff, A2A, roaming, and TUI adapters.
- Operator Brief non-regression.
- Static guard against new flat modules, ledgers, bridges, routers, or authority tables.

## Final Contract Decision

**No:** this spec should not become the implementation contract as-is.

**Yes after changes:** it can become the implementation contract after the required edits and after Operator Brief acceptance, or after an explicit canonical decision to change the active track.
