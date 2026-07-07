# /goal SARATHI_HOLON_SYSTEM_ORGANIZATION_V1_1

Supersedes SARATHI_HOLON_SYSTEM_ORGANIZATION_V1 (2026-07-06). Same thesis, same
constraints, three material amendments. Written 2026-07-07 after a 4-agent,
hash-verified census of the entire estate (134 file copies checked, 67 git
roots, all state homes). The facts below are verified — do NOT re-derive them,
and do NOT trust v1 where it contradicts this file.

## Why v1.1 exists — three defects in v1

**A1 — v1's facts are stale.** The reversibility gate is NOT uncommitted. Commit
`f18fe8476` ("sarathi: add reversibility-gated wake brick", 2026-07-06, on
`agent/magpie-seed`, NOT pushed) already landed:

- `dharma_swarm/operator_core/reversibility_gate.py` (225 lines) + 90-line tests
- `dharma_swarm/holon_runtime.py` gated via caller-supplied `planned_action`
- Sarathi registered as a WakeProfile in `scripts/runtime/codex_composer_wake_loop.py`
- `scripts/governance/sprawl_guard.py` (exit-code anti-sprawl harness)
- `docs/sarathi_apex_build/` — 9 files including `12_LOAD_HOLON_COLLAPSE_PLAN.md`
  and `91_SPRAWL_HARNESS_RUNBOOK.md` (v1's file list is incomplete)

61 scoped tests green (`tests/test_reversibility_gate.py`, `test_holon_runtime*`,
`test_codex_composer_wake_loop.py`, `test_holon_bridge.py`). Do not re-do this.

**A2 — v1's target package name is already occupied by a corpse.**
`dharma_swarm/holon_system/` EXISTS on `agent/magpie-seed`: 20 files, 323 lines,
kernel/authority/gateway/identity scaffold, ZERO external importers, abandoned
mid-construction, and it imports legacy `agent_registry`
(`holon_system/identity/__init__.py:11`). v1 would graft facades onto it blind.
**Decision (operator-ratified via this goal): delete the dead scaffold first,
then build the facade package fresh at that same path.** Record the deletion in
its own commit with the census evidence cited.

**A3 — v1 builds on the wrong branch.** `/Users/dhyana/dharma_swarm` is on
`agent/magpie-seed`, 381 commits behind `origin/main`, which is the
operator-ratified canon. The collapse plan's own Phase 0
(`docs/sarathi_apex_build/12_LOAD_HOLON_COLLAPSE_PLAN.md`) forbids building
Sarathi from the dirty fork. **Decision: all v1.1 work happens on a clean
branch off `origin/main` (suggested name: `feat/holon-system-collapse-base`),
in its own worktree.** The magpie-seed brick gets PORTED onto it (see Phase B);
magpie-seed itself is left untouched — no reverts, no deletions there.

## Core thesis (unchanged from v1)

Sarathi is not the whole build. Sarathi is the apex occupant of the holon
system. The real build is our own Hermes-class holon system:

```text
holon_system =
  identity + provider routing + persistent wake kernel +
  governed runtime + orchestration + A2A transport +
  semantic responders + gateway + observability +
  packaging/CLI + proof gates
```

Do not drift into "Sarathi identity docs only."

## Verified current state (2026-07-07 — trust these, cite them, don't re-derive)

Four bodies of the persistent-agent/holon concept coexist in the one repo tree:

| Body | Size | Verified status |
|---|---|---|
| `dharma_swarm/holon_*.py` + `scripts/holon_*.py` | 26 files / 6,798 lines | CANONICAL runtime. Four layers: identity / liveness / work-authority / completion-proof (see `docs/architecture/AGENT_HOLON_CODE_MAP.md`) |
| `holon/` fork package | 24 files / 3,318 lines | Redefines both singleton primitives (`load_holon`, `holon_wake_cycle`), own organs/providers/memory_kernel. Only 2 importers: `scripts/verify_holon_harness_prod.py:1461` + `tests/test_holon_truth_projection.py`. KILL in Phase B |
| `dharma_swarm/holon_system/` | 20 files / 323 lines | DEAD scaffold, zero external importers. KILL in Phase B, rebuild fresh at path in Phase C |
| Legacy stack: `persistent_agent.py` (633) / `autonomous_agent.py` (1,465) / `agent_registry.py` (980) / `agent_runner.py` (3,553) / `swarm.py` (3,306) | 9,937 lines | ALL LIVE and load-bearing — `holon_l4_orchestration_runtime.py:61` imports SwarmManager; swarm.py has 15 non-test importers. DO NOT retire, DO NOT refactor. It is substrate, not duplicate |

Estate: zero unique holon runtime exists outside the repo's git history. 134
copies across 67 roots are ~90% byte-identical origin/main mirrors; all drift
sits in 7 magpie-lineage trees. The mirrors age out on their own — not this
goal's job.

Bridge lineages (git blobs): origin/main `dharma_swarm/holon_bridge.py` =
`2d601da3` (204 lines, canonical base). magpie-seed dev version = `470a7bb5`
(397 lines; adds HolonDialogueContext, agentic-provider refusal, LivingDock
context — additive, port intentionally, never wholesale).

Runtime state (context only; fixing it belongs to the
agent-admission-semantic-commons track, NOT this goal): five competing identity
homes; `~/.dharma/agents` has 63 dirs, only 17 with identity.json; hermes
exists in 4 spellings; `ginko/agents/jagat-kalyan` vs `jagat_kalyan` declare
different models. Cite in the boundary doc; do not remediate here.

Uncommitted maps that must be metabolized, not multiplied:
`docs/architecture/AGENT_HOLON_CODE_MAP.md` (19KB, untracked, high quality —
commit it) and `docs/architecture/HOLON_RUNTIME_FULL_ESTATE_MAP.md` (untracked,
from a parallel session — fold what's unique into the front door or commit with
a front-door link). Three sessions produced overlapping maps on 2026-07-06;
this goal ENDS map proliferation.

## Non-negotiable constraints (v1 list, plus four)

1–12. All twelve v1 constraints stand verbatim (no alive claims, no
wake_loop_active=true, no Hermes-beating claims without receipts, no runtime
state into git, no source into `~/.dharma`, no bulk moves, no reverts of
unrelated work, no receipt noise, no parallel orchestrator/router/task
store/bus/spine, existing substrate first, code integrity in git,
`.venv/bin/python`).

13. **One lane.** No second organizer runs concurrently on
`docs/sarathi_apex_build/`, `holon/`, `holon_system/`, or the holon primitives
while this goal is in flight.
14. **Branch discipline.** All commits go to the clean branch off
`origin/main`. Nothing new lands on `agent/magpie-seed`.
15. **Machine-checkable done.** The collapse spine is complete only when
`python3 scripts/governance/sprawl_guard.py` exits 0 on the clean branch. Not
prose — exit code.
16. **Pre-commit hooks are known-broken** (stale docops manifest, venv gaps).
Scoped tests green first, then `git commit --no-verify` is authorized. Push the
clean branch after the first commit (loss-risk rule: the estate lost work to a
wipe on 2026-06-20).

## Phases

### Phase A — front door + maps (START NOW; parallel-safe, additive docs only)

Covers v1 deliverables 1, 2, 3, 6, 7, 8, 9.

1. Set up the base: `git worktree add ~/ds_holon_collapse_20260707 -b feat/holon-system-collapse-base origin/main`
   (respect the worktree budget: tag it to this goal). Work there.
2. Port the docs + gate from magpie-seed brick `f18fe8476`: cherry-pick where
   clean; the `holon_runtime.py` gating seam needs a small manual port (magpie's
   runtime file is a singleton blob; origin/main's differs). Gate + tests must
   pass on the clean base: `.venv/bin/python -m pytest tests/test_reversibility_gate.py tests/test_holon_runtime.py -q`.
3. Normalize `docs/sarathi_apex_build/` to the v1 read order (README, 00, 01
   CURRENT_STATE, 02 CODEBASE_RUNTIME_BOUNDARY, 03 HOLON_SYSTEM_CODE_MAP, 04
   PERSISTENT_AGENT_RELATION, 05 SARATHI_APEX_MAP, 06 PROOF_GATES, 07 BACKLOG,
   90/91 harness). Existing files mostly cover these — rename/index, do not
   duplicate. Commit `docs/architecture/AGENT_HOLON_CODE_MAP.md`; metabolize
   HOLON_RUNTIME_FULL_ESTATE_MAP.md.
4. Boundary doc (v1 deliverable 2): repo = source; `~/.dharma` = mutable
   runtime; `~/.hermes` = third-party side ecosystem (hermes-m5 is a
   NousResearch product instance, NOT dharma holon lineage). Name the five
   identity homes and the drift honestly; point to the agent-admission track as
   owner of the fix.
5. Hermes-organ comparison map (v1 deliverable 3): mark each organ exists /
   partial / missing / scattered, against the verified census above.
6. Live-state capture (v1 deliverable 7): run the read-only commands, record
   in 01_CURRENT_STATE.md.
7. Proof gates + anti-sprawl harness (v1 deliverables 8, 9): update
   06_PROOF_GATES.md with the ten v1 gates, marking gate 1 (reversibility gate
   committed + tests) DONE-on-fork / PORTED-in-Phase-A; keep the harness rules
   and add: every new map must be linked from README or it is sprawl.

### Phase B — collapse spine (after A lands; sequenced, destructive, cite evidence)

1. Delete `dharma_swarm/holon_system/` (dead scaffold; zero importers —
   verified 2026-07-06). Own commit.
2. Delete the `holon/` fork package. First migrate its only two importers:
   `scripts/verify_holon_harness_prod.py:1461` (fallback import — point at
   `dharma_swarm.holon_runtime`) and `tests/test_holon_truth_projection.py:23-24`
   (`holon.contracts`/`holon.receipts` — port or inline the needed types).
   Preserve anything genuinely unique from the fork's tests as canonical tests.
   Own commit.
3. Prove: `python3 scripts/governance/sprawl_guard.py` exits 0. Record output
   in 06_PROOF_GATES.md. Full scoped holon test set green.
4. Note for the operator (do not execute): the 7 drifted magpie-lineage
   worktrees and 3 /private/tmp worktrees are cleanup candidates under the
   worktree-budget rule, operator-gated.

### Phase C — facade package + Sarathi source (gated on B complete)

1. Build `dharma_swarm/holon_system/` fresh at the now-empty path: thin
   compatibility facades ONLY (`identity/ runtime/ kernel/ authority/
   orchestration/ transport/ responders/ gateway/ observability/ cli/ api/
   sarathi/`), each module a re-export over the existing canonical organ, e.g.
   `holon_system/runtime/bridge.py: from dharma_swarm.holon_bridge import load_holon, get_holon_provider, RunningHolon`.
   Add `tests/test_holon_system_imports.py` proving every facade path imports.
2. `holon_system/sarathi/` — gateway.py, pulse.py, roster.py, brief.py,
   scoreboard.py per v1 deliverable 5. Runtime file
   `~/.dharma/agents/sarathi/gateway/sarathi_gateway.py` = thin wrapper only.
3. Port the magpie dev-397 bridge additions (dialogue safety, LivingDock
   context) as an intentional patch with the v1 Phase-3 test set (unsafe
   provider refusal, safe override resolution, bounded context reads).
4. Sarathi runtime surfaces (state/inbox/heartbeat files) — created empty and
   honest, no alive claims.

## Commit strategy

Separate commits, in order: (1) ported gate + runtime seam, (2) front-door
docs normalization + committed maps, (3) scaffold deletion, (4) fork deletion +
importer migration, (5) facade package + import tests, (6) Sarathi package +
runtime wrapper. Push after each. Nothing else from the dirty tree.

## Success criteria (v1 set, plus)

- All v1 success criteria stand.
- `sprawl_guard.py` exits 0 on `feat/holon-system-collapse-base`.
- `agent/magpie-seed` untouched; origin/main untouched until PR review.
- Zero new maps outside the front door; the two orphan maps metabolized.
- A future agent answers v1's ten orientation questions in under 60 seconds
  from `docs/sarathi_apex_build/README.md` alone.

## Final response format (unchanged from v1)

1. Changed files. 2. What is now organized. 3. What is still messy.
4. Codebase/runtime boundary verdict. 5. Holon-system vs Sarathi distinction.
6. Verification run (exact commands + output). 7. Next exact step.

Do not overclaim. Sarathi is still identity + gate + one proof cycle, not a
breathing holon. Say so plainly if still true.
