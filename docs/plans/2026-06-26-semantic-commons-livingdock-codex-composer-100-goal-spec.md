---
title: Semantic Commons, LivingDock, and Codex Composer 100 Goal Spec
status: working_plan
created: 2026-06-26
owner: operator + Codex
kind: goal_spec
scope: semantic_commons_livingdock_codex_composer
---

# Semantic Commons, LivingDock, and Codex Composer 100 Goal Spec

## Verdict

Take this project slice to 100 on a clean branch from current `main`, not by trying to reconcile the whole dirty recovery worktree.

The project is worth taking to 100 because it closes a central authority problem: names, private agent context, onboarding depth, and Codex Composer wake behavior all need one canonical semantic contract. The whole current recovery worktree is not worth taking to 100 as-is. It is behind `main`, dirty, and includes unrelated work. Use it as a salvage source only.

Starting estimate from audit:

| Surface | Current Score | Reason |
| --- | ---: | --- |
| Project slice | 57/100 | Good conceptual direction and partial implementation, but missing clean integration, LivingDock projection proof, D-score verifier, and PR #683 substrate in this branch. |
| Current worktree | 45/100 | Dirty recovery branch, 10 ahead / 272 behind `origin/main`, with untracked local truth and a failing orientation invariant test. |

## Objective

Land a clean, verified implementation that makes Semantic Commons the naming authority, LivingDock the canonical per-agent home, L5 Seat Load the agent-specific context loading layer, and Codex Composer a fail-closed wake/onboarding shell. The result must be honest about D4 readiness: no permanent wake loop and no D4 claim unless the required semantic, receipt, authority, A2A, and scheduler proofs are real.

## Non-Goals

- Do not make a new root map, master folder, or loose truth store.
- Do not promote `Nest`, `Holocron`, `Sanctum`, `Aerie`, `LandingDock`, or `DroidFactory` into independent authority roots.
- Do not reconcile the entire recovery worktree.
- Do not start permanent wake loops unless scheduler federation and leases are actually ratified and enforced.
- Do not claim D4 or D5 maturity from docs alone.
- Do not create live outbound side effects, external spend, protected actions, or secret-bearing artifacts.
- Do not duplicate PR #683 filesystem-native substrate. Consume it from `main`.

## Definition of 100

This slice is 100/100 only when all sections below are complete and verified.

### 1. Clean Branch and Substrate

- Start from current `origin/main` or a freshly updated local `main`.
- Confirm PR #683 filesystem-native substrate is present in the target branch.
- Salvage only focused files from the recovery worktree:
  - Semantic Commons ontology changes.
  - Session orientation L5 changes.
  - Codex Composer wake-loop script and tests.
  - Make targets for agent onboarding and Codex Composer lifecycle.
  - Focused docs or receipts directly tied to this goal.
- Leave unrelated recovery work out of the branch.

### 2. Semantic Commons Naming Authority

Semantic Commons must define the official names and aliases. LivingDock may project them, but must not become a competing naming registry.

Required official meanings:

| Name | Official Meaning | Authority |
| --- | --- | --- |
| `LivingDock` | Canonical per-agent home object. | Existing Semantic Commons object. |
| `Sanctum` | D4+ private domain environment inside LivingDock. | Alias or subspace, not new home authority. |
| `Holocron` / `HolocronNest` | Durable private context, prompt, receipt, and domain-memory layer. | Alias or subspace under LivingDock/Sanctum. |
| `Nest` | Friendly local working/private context name. | Alias only; not a truth store. |
| `Aerie` | Operator-facing fleet home/cockpit projection. | Seed object or alias over cockpit/live-ops surfaces. |
| `LandingDock` | Agent orientation/onboarding entry surface. | Alias or subspace tied to SessionOrientation. |
| `DroidFactory` | Factory Droid delegation adapter under Codex Composer. | Integration object, not command authority. |

Requirements:

- `docs/ontology/semantic_objects.yaml` contains the official objects or subspace records.
- `docs/ontology/semantic_aliases.yaml` contains aliases, including typo/drift catchers where the repository pattern supports them.
- Tests reject authority drift and ambiguous aliases.
- `make semantic-commons-check` is green.

### 3. Session Orientation Depth Model

Keep the two scales separate:

- `L0-L5` means orientation and context-loading depth.
- `D0-D5` means agent maturity and runtime authority.

Required loading scale:

| Level | Meaning |
| --- | --- |
| `L0` | Bootstrap: `AGENTS.md`, `CLAUDE.md`, `make onboard`. |
| `L1` | Routing: `ACTIVE_TRACK`, canonical doc stack, Semantic Commons. |
| `L2` | Track packet: exact owners, gates, and tests. |
| `L3` | Reference code: owning modules and verifier code. |
| `L4` | Corpus search: archaeology, reports, and wiki only after routing. |
| `L5` | Seat Load: LivingDock + Sanctum/Holocron + recent receipts for a named agent. |

Requirements:

- `docs/ontology/session_orientation.yaml` includes L5 Seat Load.
- Every orientation route starts with `L0`, `L1`, and `L2` before deeper loading.
- L5 is gated by agent identity and receipts.
- `Aerie` remains an operator fleet projection above the loading scale, not default per-agent context.

Known current defect to fix:

- `route.seat_sarathi` currently starts `L0`, `L2`, `L5`; it must include `L1` before `L2`.

### 4. Codex Composer Wake and Onboarding Shell

Codex Composer must be usable as an agent-specific loading path without pretending to be an autonomous permanent agent.

Requirements:

- `scripts/runtime/codex_composer_wake_loop.py` is present on the clean branch.
- `tests/test_codex_composer_wake_loop.py` covers safe startup, status, once-mode, receipt writing, and fail-closed behavior.
- `make onboard-agent AGENT_NAME=codex_composer` exists and loads the named agent path.
- These targets exist and are documented enough to operate:
  - `codex-composer-bootstrap`
  - `codex-composer-once`
  - `codex-composer-status`
  - `codex-composer-start`
  - `codex-composer-stop`
- `codex-composer-start` refuses to run permanently without an activation lease.
- Unleased inbox work produces a blocked receipt, not a side effect.

### 5. LivingDock Projection Proof

LivingDock must be proven as the canonical per-agent home projection.

Minimum acceptable implementation:

- A read-only verifier or dry-run materializer checks the expected Codex Composer home under:
  - `~/.dharma/agents/codex_composer/`
- The projection contract covers:
  - Semantic reference.
  - Living agent metadata.
  - Dialogue/run receipt space.
  - Sanctum/Holocron private context subspaces.
  - Sandbox/wake-cache separation from authority.
- The verifier reports missing paths as explicit blockers instead of silently creating authority.
- If a local materializer is added, it must default to dry-run and require an explicit flag for writes.

Expected authority boundary:

- Canonical home: `~/.dharma/agents/codex_composer/`
- Sandbox/wake cache: `~/.dharma/external_agents/codex_composer/nest`
- The sandbox is never the source of truth.

### 6. D-Score Verifier and Honest Maturity

Implement or wire a real verifier that scores agent maturity from evidence, not intent.

Requirements:

- The verifier produces a machine-readable report under a stable reports path.
- It records:
  - Agent identity.
  - Verified D-level.
  - Evidence paths.
  - Missing gates.
  - Whether semantic receipt, domain receipt, fail-closed authority, model responsiveness, A2A proof, scheduler proof, and decorrelated verification are green.
- Codex Composer must not be promoted to true D4 until all required gates are green.
- If A2A/NATS bridge or scheduler federation is absent, the verifier must say so plainly and cap the score.

### 7. PR #683 Filesystem-Native Integration

PR #683 is the substrate for folder-as-pipeline, OKF, semantic file retrieval, and dry-run organization.

Requirements:

- Use the merged `dharma_swarm/fs_substrate/**` implementation from `main`.
- Do not reimplement overlapping substrate under Codex Composer.
- If Holocron/Nest folder contracts need filesystem-native behavior, build on PR #683 APIs and tests.
- Run the PR #683 focused tests if present in the target branch.

### 8. A2A, Scheduler, and Wake-Loop Honesty

The 100 goal for this slice is not "make permanent autonomous Codex Composer real at any cost." It is "make the system honest, wired, and fail-closed."

Requirements:

- Permanent wake loops remain disabled unless a lease-backed manual path or ratified scheduler federation is available.
- If NATS/A2A bridge is stopped, stale, or absent, the status path reports that as a blocker.
- No command should imply live cross-agent semantic work when only local receipts exist.
- ADR-010 scheduler federation remains a prerequisite for permanent operation unless implemented and tested in this goal.

## Score Rubric

| Area | Points |
| --- | ---: |
| Clean branch from `main` with PR #683 substrate present | 10 |
| Semantic Commons official names, aliases, and drift tests | 15 |
| SessionOrientation L5 with route invariants fixed | 12 |
| Codex Composer wake/onboarding shell and Make targets | 14 |
| LivingDock projection verifier or dry-run materializer | 15 |
| D-score verifier and honest maturity report | 15 |
| Fail-closed lease, receipt, and persistent-agent gates | 8 |
| A2A/scheduler honesty blockers and no false D4 claim | 6 |
| Closeout docs, receipts, and final scorecard | 5 |
| **Total** | **100** |

Minimum passing interpretations:

- `100/100`: All rubric areas complete and verification matrix green.
- `90-99/100`: Implementation is clean and honest, but D4 live proof remains capped by an external A2A/scheduler blocker that is explicitly reported.
- `<90/100`: Not complete enough for the stated project goal.

Hard fail conditions:

- `make semantic-commons-check` fails.
- Any orientation route reaches L4 or L5 before L0/L1/L2.
- The target branch lacks PR #683 substrate.
- Permanent Codex Composer wake loop can start without a lease.
- Codex Composer is marked D4 without real verifier evidence.
- Nest/Holocron/Sanctum become competing authority roots.

## Verification Matrix

Run the narrowest meaningful checks first, then the full focused matrix.

Required checks:

```bash
make onboard
make semantic-commons-check
pytest -q tests/test_semantic_commons.py tests/test_semantic_commons_projection.py tests/test_agent_admission.py tests/test_name_drift_preflight.py tests/test_codex_composer_wake_loop.py tests/test_persistent_agent.py
make onboard-agent AGENT_NAME=codex_composer ARGS='--skip-orientation-command'
make codex-composer-status
git diff --check
```

Run these PR #683 checks if present:

```bash
pytest -q tests/test_fs_substrate_e2e.py tests/test_okf_projection.py tests/test_organizer.py tests/test_semantic_fs.py tests/test_stage_contracts.py
```

Run any new tests added for:

- LivingDock projection.
- D-score verifier.
- SessionOrientation route invariants.
- Codex Composer lease-gated start refusal.

## Execution Plan

1. Create or switch to a clean branch from current `main`.
2. Confirm PR #683 substrate exists on the branch.
3. Inventory the recovery worktree as a read-only salvage source.
4. Port only the focused Semantic Commons, SessionOrientation, Codex Composer, Makefile, and tests work.
5. Fix route invariants, especially `route.seat_sarathi`.
6. Add or wire LivingDock projection verification.
7. Add or wire D-score verification.
8. Run the verification matrix.
9. Write a final scorecard with exact points earned, blockers, and evidence paths.
10. Stop only when the project reaches 100 or a concrete external blocker is proven and recorded.

## Suggested `/goal` Prompt

```text
/goal Take the Semantic Commons, LivingDock, SessionOrientation L5, and Codex Composer project slice to 100/100 using docs/plans/2026-06-26-semantic-commons-livingdock-codex-composer-100-goal-spec.md as the source of truth.

Start from a clean branch based on current main, not from the dirty recovery branch. Consume PR #683's merged fs_substrate from main; do not duplicate it. Use the recovery worktree only as a salvage source for focused changes: ontology objects/aliases, session_orientation L5, codex_composer wake loop/tests, Make targets, and directly related docs/receipts.

Definition of done:
- Semantic Commons is the naming authority for LivingDock, Sanctum, Holocron/HolocronNest, Nest, Aerie, LandingDock, and DroidFactory.
- LivingDock remains the canonical per-agent home projection.
- SessionOrientation has L5 Seat Load, and every route starts L0/L1/L2 before deeper loading.
- Codex Composer has fail-closed onboarding, once/status/start/stop Make targets, tests, and lease-gated permanent wake behavior.
- LivingDock projection is verified by a read-only checker or dry-run materializer.
- A real D-score verifier reports Codex Composer maturity from evidence and refuses false D4.
- A2A/NATS and scheduler blockers are reported honestly instead of papered over.
- All verification commands in the spec are run or their exact blocker is recorded.

Produce a final scorecard with points out of 100, changed files, verification evidence, and any remaining blocker. Do not reconcile the whole recovery worktree.
```

