# Handoff — Ontology-Native Operator Brief, First Implementation

> **DEPRECATED — retained as historical reference** (re-verified 2026-06-15 by perplexity-computer).
> Per `docs/governance/ACTIVE_TRACK.yaml`, the underlying master spec is superseded by the `cockpit-control-surface-2026-05` lane. Implementation paths described here have either shipped (commits `695f149`, `e0cdb79`) or been re-routed through the cockpit lane. Retained for citation only. Do not pick this up as a fresh hand-off.
>
> Deprecated: 2026-06-15
> Reason: Superseded by `cockpit-control-surface-2026-05` lane (SHIPPED); implementation paths shipped or re-routed.
> Replacement: `docs/governance/ACTIVE_TRACK.yaml` (current build portfolio)
> Review / removal date: 2026-09-15

**Status:** **DEPRECATED — historical reference** (was: ready for the next code agent to pick up)
**Scope:** implements [`ONTOLOGY_NATIVE_OPERATOR_BRIEF_MASTER_SPEC.md`](ONTOLOGY_NATIVE_OPERATOR_BRIEF_MASTER_SPEC.md) item 5 and (separately) item 6 from [`NEXT_10_SUBSTRATE_TODO.md`](NEXT_10_SUBSTRATE_TODO.md).
**Read first:** [`docs/governance/BUILD_SESSION_ENTRYPOINT.md`](../governance/BUILD_SESSION_ENTRYPOINT.md). All of it. Then the master spec linked above.

This file is intentionally written so it can be pasted verbatim into the next agent's prompt window. Everything the next agent needs is here, plus the four canonical reads.

---

## 1. Read these, in this order, before writing anything

1. [`CLAUDE.md`](../../CLAUDE.md) — behavioral rules.
2. [`docs/governance/SOVEREIGN_MANIFEST.md`](../governance/SOVEREIGN_MANIFEST.md) — domain map and axioms. Pay attention to A1 (no flat-package growth), A2 (no duplicate implementations), A3 (no undocumented seams), A4 (no vibe-coding), A5 (no god objects).
3. [`docs/governance/BUILD_SESSION_ENTRYPOINT.md`](../governance/BUILD_SESSION_ENTRYPOINT.md) — read order, current track, the seven ontology-native checks.
4. [`docs/plans/ONTOLOGY_NATIVE_OPERATOR_BRIEF_MASTER_SPEC.md`](ONTOLOGY_NATIVE_OPERATOR_BRIEF_MASTER_SPEC.md) — this is your work order.

If you have not read all four, do not start. There is no catching up mid-stream on this repo.

## 2. What you are building

Exactly the seam in the master spec, no more. To be concrete:

- One new package: `dharma_swarm/operator_brief/` with `__init__.py` and `insight_brief.py`.
- One new test file: `tests/test_operator_brief_insight_brief.py` with the three tests from master spec §10.
- One new entry in `cron_jobs.json`. Match the format of existing cron-trigger entries in that file.
- (Maybe) one line in `dharma_swarm/cron_scheduler.py` if the dispatcher does not already pick up the new entry purely by data. Read the dispatcher first; if it dispatches by name without code change, leave it alone.

That is it. If your diff has anything else, you have drifted off-spec. Stop, reread the master spec §4 and §11.

## 3. What you will not touch

- Any file in `dharma_swarm/` outside the new package, except possibly `cron_scheduler.py` per above.
- Any `ObjectType` in `dharma_swarm/ontology.py`. Use the existing definitions for `KnowledgeArtifact`, `WitnessLog`, `ActionProposal`, `GateDecisionRecord`, `Outcome`, `ValueEvent`, `Contribution`, `AgentIdentity` as they stand.
- Any gate definition in `dharma_swarm/telos_gates.py`. Use `BHED_GNAN`, `STEELMAN`, `DOGMA_DRIFT`, `CONSENT` as they exist.
- Any bridge, router, adapter, orchestrator, ledger, memory store. The audit synthesis at `reports/audit/end_to_end/000_MASTER_COHERENCE_SYNTHESIS.md` §5 is explicit: do not build new, wire existing.
- The kernel. The kernel is SHA-256 signed. Do not modify.
- `CLAUDE.md`, `SOVEREIGN_MANIFEST.md`, and `CANONICAL_DOC_STACK.md` content beyond what the master spec already authorises (and that authorisation is for a different PR; not yours).
- Any feature flag flip in this PR. The flag stays default-off. Flipping it for a live tick is a separate item (NEXT_10_SUBSTRATE_TODO item 6).

## 4. Concrete entrypoint to write

In `dharma_swarm/operator_brief/insight_brief.py`, expose exactly one public function:

```python
def run_once() -> dict:
    """One tick of the operator-brief seam. Returns a dict carrying:
       - artifact_id: str | None (None if blocked or failed)
       - outcome: str ('success' | 'failed_gate:<NAME>' | 'failed_input' | 'failed_materialise')
       - witness_log_ids: list[str]
       - gate_decision_ids: list[str]
       - proposal_id: str
    Idempotent on (date, agent_id): rerunning the same day with the same input
    must not produce a duplicate KnowledgeArtifact row.
    """
```

Internal helpers (private, in the same module): `_collect_input()`, `_draft_brief()`, `_propose()`, `_apply_gates()`, `_materialise_artifact()`, `_emit_value_event()`. Keep the file under 500 lines (CLAUDE.md rule).

## 5. Tests you must write

Write `tests/test_operator_brief_insight_brief.py` with exactly the three tests from master spec §10:

1. **Object creation test** — happy path, all gates pass, asserts the full link set.
2. **Gate-block fail-closed test** — STEELMAN, DOGMA_DRIFT, CONSENT each block in turn, no artifact, no file, correct Outcome.
3. **No-raw-bypass static check** — `ast` walk asserts no direct file writes outside the artifact directory and no JSONL append outside the witness API.

Use the repo's existing test patterns for temp `~/.dharma`. Do not touch the live state directory. Look at `tests/test_runtime_state.py` for the established temp-DB pattern.

## 6. Tests to run before opening the PR

In order:

```bash
python3 -m pytest tests/test_operator_brief_insight_brief.py -v
python3 -m pytest tests/ -q --tb=short -x
python -m compileall dharma_swarm tests
make xray            # confirms no new flat top-level module
```

If the full suite has unrelated failures, capture them in the PR description. Do not "fix" anything outside your scope.

## 7. Acceptance — do not merge until all of these are true

- All three new tests pass on a clean checkout.
- `python -m compileall dharma_swarm tests` exits zero.
- `make xray` shows the new module under `dharma_swarm/operator_brief/`, not at the top level.
- The PR diff is limited to: the new package files, the new test file, the one new `cron_jobs.json` entry, and (at most) one line in `cron_scheduler.py`.
- The PR description states the substrate-nativeness estimate before and after this seam (~10–15% before; ~10–15% + this one seam after; explicit "this does not generalise to other seams").
- The PR description links back to this handoff and to the master spec.
- The feature flag `DHARMA_OPERATOR_BRIEF_ENABLED` defaults to `0`. You do not flip it in this PR.

## 8. Success condition

A reviewer can check out your branch, run `DHARMA_OPERATOR_BRIEF_ENABLED=1 python -c "from dharma_swarm.operator_brief.insight_brief import run_once; print(run_once())"` against a temp `~/.dharma`, and observe:

- One new `KnowledgeArtifact` row of subtype `operator_brief`.
- The four `GateDecisionRecord` rows linked to one `ActionProposal`.
- One `WitnessLog` row per gate plus start and materialise rows.
- One `Outcome`, one `ValueEvent`, one `Contribution`.
- One markdown file under `~/.dharma/artifacts/operator_brief/<date>/<artifact_id>.md` whose SHA-256 matches the digest on the artifact row.

If any of those is missing, you are not done.

## 9. If you get stuck

- If a substrate seems missing, search for it before adding it. The audit synthesis §6 lists every canonical substrate. The probability that the thing you need is not already in the repo is low.
- If a gate behaves unexpectedly, do not silently skip it. Read `dharma_swarm/telos_gates.py` and trace the existing call site. Gates are load-bearing in this seam.
- If the cron dispatcher does not pick up your new entry, read `dharma_swarm/cron_scheduler.py` end-to-end before patching it. The dispatcher already dispatches many entries; figure out the contract before extending it.
- If the ontology API surface is unclear, read `dharma_swarm/ontology.py` for the relevant `ObjectType` definitions and the existing `register` and `link` calls. Do not invent a new persistence path.
- If you find yourself writing a second module to "help" the first, stop. The seam is one module. Either it fits or the spec is wrong; in the latter case write the disagreement into a new plan file under `docs/plans/<date>-<slug>.md` and link it from `BUILD_SESSION_ENTRYPOINT.md`. Do not fork the seam silently.

## 10. After your PR merges, what the next next agent picks up

[`NEXT_10_SUBSTRATE_TODO.md`](NEXT_10_SUBSTRATE_TODO.md) item 6: flip the flag for one operator profile, capture the first live tick into `reports/witness/<date>-operator-brief-first-tick.md`. That is a configuration-only PR. Do not bundle it with yours.

After item 6, items 7 (RuntimeStateStore wiring), 8 (Guardian LEDGER_WATCHER), and 9 (`dgc value-events`) follow in order. Item 10 (Dharma Radar v0) does not start until item 9 has been in production use for at least one week.
