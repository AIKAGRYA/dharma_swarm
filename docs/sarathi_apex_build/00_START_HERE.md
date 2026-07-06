# Sarathi Apex Build — 00 START HERE

Status: **map + gate rescue pass, not a living Sarathi claim**.

Working checkout used for this receipt: `/Users/dhyana/dharma_swarm`, branch
`agent/magpie-seed`, HEAD `eeb217b7758e`, `39` ahead / `381` behind
`origin/main` at `0a26db0ee6f1` when verified on 2026-07-06.

## The locked sentence

Sarathi is the apex holon that USES persistent-agent lineage + living-agent kernel + holon runtime + existing orchestrator, then ADDS deterministic reversibility gating and operator-facing continuity — not a parallel rewrite.

## Read order

**`README.md` is the front door.** The canonical numbered read order is:

1. `00_START_HERE.md` — this file (orientation + locked sentence + "alive" definition).
2. `01_CURRENT_STATE.md` — live snapshot (git, dgc, runtime counts, Sarathi surfaces).
3. `02_CODEBASE_RUNTIME_BOUNDARY.md` — dharma_swarm/ vs ~/.dharma vs ~/.hermes, and the drift.
4. `03_HOLON_SYSTEM_CODE_MAP.md` — Hermes-class organs -> our code (exists/partial/scattered/missing).
5. `04_PERSISTENT_AGENT_RELATION.md` — the lineage ladder up to the apex.
6. `05_SARATHI_APEX_MAP.md` — what Sarathi is + its target source package.
7. `06_PROOF_GATES.md` — gate-ordered next work; what authorizes "alive".
8. `07_BACKLOG.md` — safe-to-change, next steps, do-not-touch.
9. `90_ANTI_SPRAWL_HARNESS.md` — the rules that stop the next map from scattering.

Supporting/historical (linked from README, non-canonical): `11_PERSISTENT_AGENT_RELATION.md`
(full file:line lineage), `12_LOAD_HOLON_COLLAPSE_PLAN.md`, `HOLON_SYSTEM_CODE_ORGANIZATION.md`,
`91_SPRAWL_HARNESS_RUNBOOK.md`, `CURRENT_MAP_2026-07-06.md`, `SCRATCHPAD_2026-07-06.md`.

## Current proof status

| Claim | Current evidence | Status |
|---|---|---|
| Keystone gate exists | `dharma_swarm/operator_core/reversibility_gate.py` is 225 lines; `tests/test_reversibility_gate.py` is 90 lines; both are untracked in this checkout. | **Verified** |
| Gate tests pass | `.venv/bin/python -m pytest tests/test_reversibility_gate.py -q` → `9 passed in 0.50s`. | **Verified under repo venv** |
| Exact `python3` command passes | `python3 -m pytest tests/test_reversibility_gate.py -q` used `/usr/bin/python3` 3.9.6 and failed during collection on repo-wide `dict[str, Any] | None` annotations. | **Red due interpreter, not gate logic** |
| Layer map is composition, not rewrite | Files and line anchors in `11_PERSISTENT_AGENT_RELATION.md`; `holon_orchestrate.py:1-7` explicitly says no second orchestrator/task store/model router/receipt spine. | **Verified** |
| Holon runtime line count | `git ls-files 'dharma_swarm/holon*' ... | xargs wc -l` for runtime code files gives 18 files / 5,668 lines. | **Verified; file-count wording corrected** |
| Sarathi executable body | `~/.dharma/agents/sarathi` has 37 files and 0 `.py/.sh/.ts/.js`; grep for `sarathi` in holon/wake code returned 0 hits. | **Mind/spec exists; body not breathing** |
| Execution leases | `find ~/.dharma/a2a_bus/leases -maxdepth 2 -type f | wc -l` → `0`. | **Verified empty** |
| Sprawl count | `/Users/dhyana` scan found 138 `holon_bridge.py` + 138 `holon_runtime.py` instances across 69 git roots; each root generally has both `dharma_swarm/` and `holon/` copies. | **Verified current scan; prior 136/68 is stale by +2/+1** |

## What is allowed next

Do **not** build a new Sarathi architecture. Do this sequence only:

1. Commit the deterministic reversibility gate and its tests on a clean branch off `origin/main` or explicitly port them there.
2. Collapse `load_holon` to one canonical module path: `dharma_swarm/holon_bridge.py`.
3. Delete or archive the `holon/` fork only after importers/tests are migrated.
4. Register `sarathi` as a `WakeProfile` only after steps 1–3 are green on the canonical tree.
5. Wrap `holon_wake_cycle()` with the reversibility gate.
6. Run exactly one unattended overnight proof and write receipts.
7. Flip `wake_loop_active=true` only after that proof.

## Definition of "alive" for this slice

A file named `SOUL.md`, `OPERATING_MAP.md`, or `identity.json` is not liveness.
Sarathi becomes alive only when all of these exist and verify:

- `load_holon("sarathi")` succeeds from the canonical code path;
- the deterministic reversibility gate blocks irreversible/unreachable actions;
- `holon_wake_cycle()` is wrapped by that gate;
- a `sarathi` wake profile exists;
- a wake receipt proves the loop ran unattended within its reversible-safe envelope;
- operator-facing continuity exists as a receipt or phone/outbox artifact;
- `wake_loop_active` is false until the above proof exists.
