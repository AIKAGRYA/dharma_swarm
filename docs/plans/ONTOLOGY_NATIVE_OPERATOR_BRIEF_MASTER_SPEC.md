# Master Build Spec — Ontology-Native Operator Brief (Daily Insight Brief)

> **DEPRECATED — retained as historical reference** (re-verified 2026-06-15 by perplexity-computer).
> Per `docs/governance/ACTIVE_TRACK.yaml`, this master spec is superseded by the `cockpit-control-surface-2026-05` lane. First ontology-native seam shipped at commit `695f149`; runtime artifact seam wiring shipped at `e0cdb79`. Retained for citation by `scripts/governance/agent_onboard.py` and the active-track notes. Do not pick this up as a fresh build target.
>
> Deprecated: 2026-06-15
> Reason: Superseded by `cockpit-control-surface-2026-05` lane (SHIPPED); first seam shipped at `695f149`, runtime artifact seam wiring at `e0cdb79`.
> Replacement: `docs/governance/ACTIVE_TRACK.yaml` (current build portfolio)
> Review / removal date: 2026-09-15

**Status:** **DEPRECATED — historical reference** (was: spec, not implemented; portions shipped via cockpit lane)
**Owner of:** the contract for the first ontology-native seam in dharma_swarm.
**Read first:** [`docs/governance/BUILD_SESSION_ENTRYPOINT.md`](../governance/BUILD_SESSION_ENTRYPOINT.md), [`docs/governance/SOVEREIGN_MANIFEST.md`](../governance/SOVEREIGN_MANIFEST.md), [`reports/audit/end_to_end/000_MASTER_COHERENCE_SYNTHESIS.md`](../../reports/audit/end_to_end/000_MASTER_COHERENCE_SYNTHESIS.md).
**Companion:** [`HANDOFF_ONTOLOGY_NATIVE_OPERATOR_BRIEF.md`](HANDOFF_ONTOLOGY_NATIVE_OPERATOR_BRIEF.md) (copy-paste handoff for the next code agent).

---

## 1. Problem

The dharma_swarm runtime claims a typed ontology, gated proposal flow, an immutable kernel, append-only witness log, and an artifact/value loop. The audit at `reports/audit/end_to_end/000_MASTER_COHERENCE_SYNTHESIS.md` confirms the substrates exist but estimates that ~85–90% of live runtime work bypasses them — writing JSON to arbitrary paths, calling LLMs directly, and emitting "operator briefs" or "daily summaries" through code paths that never touch the ontology, never invoke gates, and never produce a `WitnessLog` row.

This means the substrate is not load-bearing. It can be deleted without breaking observable runtime behaviour. That is the worst possible state for a system whose value proposition is graph-grounded, telos-gated, witness-bearing value production.

The fix is not another spec, another bridge, or another router. The fix is to make **one** user-visible flow ontology-native end-to-end, prove it with tests, and let the substrate carry weight.

## 2. Goal

Pick the smallest user-visible operator-facing artifact and make it ontology-native: the **daily Operator Brief**, also called Daily Insight Brief.

A single tick of the brief generator must:

1. Construct a `KnowledgeArtifact` of subtype `operator_brief`.
2. Link it to: at least one `WitnessLog`, one `ActionProposal`, four `GateDecisionRecord` rows (one per applied gate), one `Outcome`, and one `ValueEvent`.
3. Apply gates `BHED_GNAN`, `STEELMAN`, `DOGMA_DRIFT`, and `CONSENT`. A BLOCK on any gate must prevent artifact materialisation. The block itself is a witnessed `GateDecisionRecord`.
4. Materialise the artifact body to a signed path under `~/.dharma/artifacts/operator_brief/<date>/<artifact_id>.md`. The path is recorded on the `KnowledgeArtifact`.
5. Run from a single new module (`dharma_swarm/operator_brief/insight_brief.py`) and a single new entry in `cron_jobs.json`. No new bridges, routers, adapters, or memory stores.

When this is true and tested, one user-visible seam is at 100% ontology-native. Other seams remain at ~10–15% until they receive the same treatment.

## 3. Non-goals

The following are explicitly out of scope for this seam:

- Dharma Radar v0 in any form. Do not borrow code from radar plans into this seam.
- Full agent identity unification (audit Slice 4). The brief generator may use whichever existing identity model the orchestrator passes it; it does not need to canonicalise identity.
- Dashboard rendering of the brief. The brief is materialised to disk and recorded in the ontology. A dashboard surface comes later.
- Cross-agent voting, ensemble brief generation, or transcendence-mode aggregation. One brief per tick from one configured agent profile.
- Schema changes to existing `ObjectType` definitions in `dharma_swarm/ontology.py`. The seam uses `KnowledgeArtifact` as defined today, with subtype encoded in an existing property field.
- Any change to the kernel, the gate registry, or the four chosen gate definitions.
- Any new substrate listed in audit §5 "do not build new, wire existing".

## 4. Files and modules touched

This seam is intentionally narrow. Listed in expected order of edit:

| File | Action | Why |
|---|---|---|
| `dharma_swarm/operator_brief/__init__.py` | new | package marker for new subdirectory (axiom A1: no flat top-level growth) |
| `dharma_swarm/operator_brief/insight_brief.py` | new | sole new logic module: `generate_operator_brief()`, `_apply_gates()`, `_materialise_artifact()` |
| `cron_jobs.json` | edit | one new cron entry pointing at `insight_brief.run_once` |
| `dharma_swarm/cron_scheduler.py` | edit | dispatch the new entry. Confirm the existing dispatch already handles named callable; if it does, no edit needed here. |
| `tests/test_operator_brief_insight_brief.py` | new | the three required tests in §10 |

Do not touch any other file. If you find you need to, pause and re-read [`SOVEREIGN_MANIFEST.md`](../governance/SOVEREIGN_MANIFEST.md) §SHARED INVARIANTS and the audit synthesis §5.

## 5. Typed objects used

All from existing definitions in `dharma_swarm/ontology.py`. Do not redefine.

| Object | Purpose in this seam |
|---|---|
| `KnowledgeArtifact` | the brief itself; subtype `operator_brief` carried in an existing property |
| `WitnessLog` | one entry per gate evaluation and one entry for materialisation |
| `ActionProposal` | the proposal to publish the brief (Propose → gate → Approve/Reject) |
| `GateDecisionRecord` | one row per applied gate, linked to the `ActionProposal` |
| `Outcome` | success/fail outcome of the tick, linked to the artifact |
| `ValueEvent` | one event indicating the brief was produced, linked to the artifact |
| `Contribution` | one row attributing the brief to the producing `AgentIdentity` |
| `AgentIdentity` | existing; identifies the agent that drafted the brief (whichever current identity model the orchestrator uses; no migration) |

## 6. Required gates

Applied in this exact order against the `ActionProposal` for publishing the brief:

1. `CONSENT` — Tier B. Confirms permission system did not flag the brief content as exfiltration of restricted material. Existing implementation in `dharma_swarm/telos_gates.py`.
2. `BHED_GNAN` — Tier C. Doer-witness distinction. Always passes today; we keep it in the order so the witness row exists. If the implementation is later strengthened, this seam picks up the change automatically.
3. `STEELMAN` — Tier C. Counterargument requirement. The brief content must include at least one steelman of an opposing read of the input data. The gate enforces this.
4. `DOGMA_DRIFT` — Tier C. Confidence without evidence check. The brief must cite at least one runtime fact (`session_events` or `memory_facts` row id). The gate enforces this.

A `BLOCK` from any gate aborts materialisation. The block decision is itself a `GateDecisionRecord` linked to the `ActionProposal`. No artifact file is written. An error `Outcome` is recorded.

A `REVIEW` decision is treated as block for v0. We can soften to "queue for human" later.

## 7. Witness, value, and contribution events

Every tick emits, in order:

1. `WitnessLog` row "operator_brief.tick.start" with the input snapshot hash.
2. One `WitnessLog` row per gate evaluation referencing the `GateDecisionRecord` id.
3. On all-gates-pass: `WitnessLog` row "operator_brief.materialise" with the artifact path and content hash.
4. `ValueEvent` row of subtype `operator_brief_published` linked to the `KnowledgeArtifact`.
5. `Contribution` row attributing the brief to the producing `AgentIdentity`.
6. `Outcome` row (`success` or `failed_gate:<gate_name>` or `failed_input`).

On any gate block: rows 3, 4, and 5 are skipped. Row 6 carries the failure reason. Row 1 and the per-gate rows still land. Silence is not allowed.

## 8. Artifact path and signing

- Directory: `~/.dharma/artifacts/operator_brief/<YYYY-MM-DD>/`.
- Filename: `<artifact_id>.md` where `artifact_id` is the `KnowledgeArtifact` primary id.
- Body: markdown, with a YAML frontmatter block carrying `artifact_id`, `agent_id`, `gate_decisions` (list of `gate_name:decision`), `witness_log_ids`, `proposal_id`, `content_sha256`.
- Signing: write the file, compute SHA-256, store the digest on the `KnowledgeArtifact` row. The kernel signing path is out of scope for v0; we record the digest, not a kernel signature.
- Filesystem rule from `SOVEREIGN_MANIFEST.md`: nothing outside `~/.dharma/`. This path complies.

## 9. Scheduler / cron integration

- Add one entry to `cron_jobs.json`, modelled on the existing entries (the file already has multiple cron-trigger jobs with `schedule` blocks).
- Cadence: once per day, configurable via env `DHARMA_OPERATOR_BRIEF_CRON` (default `0 9 * * *` local time).
- Feature flag: the dispatcher checks `DHARMA_OPERATOR_BRIEF_ENABLED`. Default `0`. The flag flips on per [`NEXT_10_SUBSTRATE_TODO.md`](NEXT_10_SUBSTRATE_TODO.md) item 6.
- The cron handler imports `insight_brief.run_once` and calls it with no arguments. `run_once` is the single public entrypoint of the new module.

## 10. Tests

All three live in `tests/test_operator_brief_insight_brief.py`. They run against a temp `~/.dharma` (use existing test patterns; do not touch the live state directory).

### 10.1 Object creation test
- Run `insight_brief.run_once()` with all gates configured to pass.
- Assert exactly one new `KnowledgeArtifact` row of subtype `operator_brief`.
- Assert it has links to ≥1 `WitnessLog`, ≥4 `GateDecisionRecord` (one per gate), 1 `ActionProposal`, 1 `Outcome`, 1 `ValueEvent`, 1 `Contribution`.
- Assert the materialised file exists at the expected path and its SHA-256 matches the digest on the artifact row.

### 10.2 Gate-block fail-closed test
- Configure `STEELMAN` to BLOCK for the test input (omit the steelman section).
- Run `insight_brief.run_once()`.
- Assert: zero `KnowledgeArtifact` rows of subtype `operator_brief`. Zero files in the artifact directory. One `Outcome` row with reason `failed_gate:STEELMAN`. One `GateDecisionRecord` of decision `BLOCK` for STEELMAN. The `WitnessLog` row for the block exists.
- Repeat for `DOGMA_DRIFT`, `CONSENT`, and `BHED_GNAN` (the last is a smoke test; if the gate implementation always passes today, the test asserts that and is updated when the gate strengthens).

### 10.3 No-raw-bypass test
- Static check: import `dharma_swarm.operator_brief.insight_brief` and assert that the module does not call `open(..., 'w')` directly on any path outside the artifact directory; that all DB writes go through `OntologyRegistry`; that no JSONL append happens outside the witness log API.
- This test is short and uses `ast` to walk the module. Its purpose is to make a future regression visible at PR time.

## 11. Acceptance criteria

The seam is accepted when, simultaneously:

- The three tests in §10 pass on a clean checkout.
- One live tick on a developer machine, with the feature flag on, produces the expected rows and file. Captured in `reports/witness/<date>-operator-brief-first-tick.md` per [`NEXT_10_SUBSTRATE_TODO.md`](NEXT_10_SUBSTRATE_TODO.md) item 6.
- `make test-smoke` and `make test-all` (or their pytest equivalents) pass overall.
- `python -m compileall dharma_swarm tests` passes.
- `make xray` does not show a new top-level flat module (axiom A1 holds).
- No other module's behaviour changes. `git diff main...HEAD` for non-operator_brief paths is limited to the cron entry and (if needed) one line in `cron_scheduler.py`.

## 12. Failure modes and how they surface

| Failure | What the seam does | What the operator sees |
|---|---|---|
| Gate BLOCK | no artifact, witness row exists, Outcome=failed_gate:X | next tick of `dgc status` shows last brief outcome=failed; cron log clean; ledger watcher (item 8) flips DEGRADED after threshold |
| Missing input (no `session_events` cited) | DOGMA_DRIFT BLOCK as above | as above |
| Ontology DB unreachable | exception, no rows, Outcome row not even attempted | cron daemon log shows the exception; this is acceptable for v0; item 8 watchdog catches sustained failure |
| Filesystem write fails after gates pass | rows 1–2 exist, row 3 (materialise witness) does not, Outcome=failed_materialise | tick is visible as failed; rerunning is safe (idempotent on artifact_id) |
| Cron dispatcher not configured | seam never runs; ledger watcher (item 8) blocks at the threshold | empty `KnowledgeArtifact` set for `operator_brief` is detected, not silent |

The "best effort, never blocks" pattern called out by the audit is explicitly rejected. Every failure produces a row.

## 13. Rollout sequence

1. Land this spec, the entrypoint, and the next-10 todo (this PR).
2. Implement module + tests behind feature flag (`NEXT_10_SUBSTRATE_TODO` item 5). Do not flip the flag in this PR.
3. Code review against §11 acceptance criteria. No merge until tests pass.
4. Flip flag for one operator profile, capture first-tick report (`NEXT_10_SUBSTRATE_TODO` item 6).
5. Wire artifact rows into `RuntimeStateStore.artifact_records` (`NEXT_10_SUBSTRATE_TODO` item 7).
6. Add Guardian `LEDGER_WATCHER` thresholds (`NEXT_10_SUBSTRATE_TODO` item 8).
7. Add `dgc value-events` read surface (`NEXT_10_SUBSTRATE_TODO` item 9).
8. Only after item 9: open Dharma Radar v0 design (`NEXT_10_SUBSTRATE_TODO` item 10).

## 14. Open questions deferred out of v0

Recorded so the next agent does not silently re-decide them:

- Whether the brief should also emit a `Stigmergy` mark. v0: no. Reconsider after item 7.
- Whether `BHED_GNAN` should ever block in this seam. v0: no, mirrors current implementation. Reconsider when the gate is strengthened repo-wide.
- Whether the brief should be cryptographically signed by the kernel. v0: SHA-256 only. Kernel signing is a separate spec.
- Whether multiple operator profiles should each get their own brief. v0: one profile, configured by env. Multi-profile is item 11+ of a later todo file.

## 15. What this seam does NOT prove

This is the honest scope. The seam, when shipped, proves:

- One user-visible flow can be ontology-native end-to-end on this codebase.
- The four gates can be load-bearing, not advisory.
- A `KnowledgeArtifact` can carry the right links and survive a gate block fail-closed test.

It does not prove:

- That the rest of the runtime is ontology-native. It is not. Substrate-nativeness moves from ~10–15% to slightly above that, not to 100%.
- That the value loop produces useful operator outcomes. That is item 9 of the next-10 todo.
- That the substrate scales to the Dharma Radar surface. That is item 10.

State this explicitly in any PR description that claims success on this seam. Do not generalise the win.
