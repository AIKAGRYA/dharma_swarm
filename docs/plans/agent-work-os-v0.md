# Agent Work OS v0

## Purpose

Agent Work OS v0 gives Dharma Swarm a canonical cross-agent interface for repo-local work. It lets Codex, Claude, Warp, Copilot, OpenCode, Junie, and future agents read the same operating rules without replacing Dharma Swarm's runtime substrate.

## Decision

`AGENTS.md` is canonical.

`WARP.md` is a compatibility pointer only. Warp supports `AGENTS.md` as project rules, and the broader agent ecosystem also recognizes it, so Dharma Swarm should not maintain separate rule sources.

`.agents/skills/` is a portable workflow layer. It is not a new canonical skill system. The canonical DS mode vocabulary remains `mode_pack/contracts/mode_pack.v1.json`, and runtime truth remains in the runtime spine.

`specs/<work-id>/PRODUCT.md` and `specs/<work-id>/TECH.md` become the expected shape for serious work. Product specs define behavior and invariants. Tech specs define implementation, files, tests, risks, and rollback.

## Why This Exists

Dharma Swarm already has strong runtime organs:

- `RuntimeStateStore` for structured runtime state
- `RuntimeLifecycle` for lifecycle producer wiring
- `SessionLedger` for session event traces
- `ContextCompiler` for persisted context bundles
- `GuardianCrew` for runtime invariants
- `TelosGatekeeper` for dharmic safety gates
- `mode_pack` for canonical operating modes

The gap is not another ledger or another agent registry. The gap is a clean repo-facing interface that makes outside agents behave as disciplined DS contributors.

## What This Adopts From Warp

- Repo-readable project rules
- Portable skills with `SKILL.md`
- Spec-first implementation for substantial work
- Clear separation between human intent, agent execution, review, and proof

## What This Does Not Adopt

- No vendored Warp source
- No copied Warp runtime code
- No Oz dependency
- No Warp terminal or UI integration
- No new DS runtime substrate
- No replacement for `mode_pack`

## Operating Model

1. Agents read `AGENTS.md`.
2. Agents invoke a focused `.agents/skills/<skill>/SKILL.md` workflow when the task matches.
3. Serious work receives `PRODUCT.md` and `TECH.md` under `specs/<work-id>/`.
4. Implementation remains bounded to the approved branch and files.
5. Proof lands in a report packet.
6. Guardian, CI, tests, and human review decide whether it can merge.

## First Skill Set

- `global-repo-reckoning`
- `promotion-packet-splitter`
- `control-loop-pr-review`
- `baseline-red-stabilizer`
- `operator-ground-truth-review`
- `guardian-invariant-review`
- `issue-to-product-tech-spec`

## Intentional Boundaries

This plan does not touch runtime behavior, memory promotion, dashboard, Darwin/Shakti, provider routing, operator actions, runtime tables, live state, or active PR branches.

## Next Step

Review the interface files for scope, clarity, and compatibility with existing DS governance. If accepted, add an export/install slice that lets `agent_export.py` and `agent_install.py` emit `.agents/skills/<slug>/SKILL.md` from canonical DS agent or mode specs.
