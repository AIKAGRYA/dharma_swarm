# Next 10 Substrate Todos

> **DEPRECATED — retained as historical reference** (re-verified 2026-06-15 by perplexity-computer).
> Per `docs/governance/ACTIVE_TRACK.yaml`, this file is superseded by the `cockpit-control-surface-2026-05` lane and is retained for citation only. The canonical "what is being built right now" surface is `docs/governance/ACTIVE_TRACK.yaml`. Do not treat this file as the current queue.
>
> Deprecated: 2026-06-15
> Reason: Superseded by `cockpit-control-surface-2026-05` lane (SHIPPED); canonical queue is now `docs/governance/ACTIVE_TRACK.yaml`.
> Replacement: `docs/governance/ACTIVE_TRACK.yaml` (current build portfolio)
> Review / removal date: 2026-09-15

**Status:** **DEPRECATED — historical reference** (was: active build sequence)
**Owner of:** the prioritised order in which to take this repo from ~10–15% ontology-native to one fully native seam, then to a measurable value loop.
**Read first:** [`docs/governance/BUILD_SESSION_ENTRYPOINT.md`](../governance/BUILD_SESSION_ENTRYPOINT.md). That file gives you the read order and the rules. This file is the queue.

The order is load-bearing. Do not skip ahead. Each item lands as its own PR, with tests, on a feature branch.

---

## Track 1 — Root the meta layer (items 1–3)

### 1. Land the build-session entrypoint and the current track pointers
- Files involved (this PR): [`docs/governance/BUILD_SESSION_ENTRYPOINT.md`](../governance/BUILD_SESSION_ENTRYPOINT.md), [`docs/plans/ONTOLOGY_NATIVE_OPERATOR_BRIEF_MASTER_SPEC.md`](ONTOLOGY_NATIVE_OPERATOR_BRIEF_MASTER_SPEC.md), [`docs/plans/HANDOFF_ONTOLOGY_NATIVE_OPERATOR_BRIEF.md`](HANDOFF_ONTOLOGY_NATIVE_OPERATOR_BRIEF.md), this file, plus minimal pointer additions to [`README.md`](../../README.md) and [`CLAUDE.md`](../../CLAUDE.md).
- Definition of done: an agent following only README → CLAUDE.md → BUILD_SESSION_ENTRYPOINT.md ends up at the master spec for the current seam without further hunting.
- Why now: `reports/audit/end_to_end/000_MASTER_COHERENCE_SYNTHESIS.md` finds agents repeatedly miss canonical docs. Without a rooted entrypoint, every later item silently regresses.

### 2. Acknowledge substrate-nativeness state in CLAUDE.md and SOVEREIGN_MANIFEST
- One short paragraph each. State: "current runtime is ~10–15% ontology-native; current track is the operator-brief seam; do not open additional tracks until that seam ships." No grand-manifesto rewrite.
- Cross-link the audit synthesis from both files.
- Why now: agents currently treat the substrate as already true. The audit explicitly warns against that posture. Making the gap visible in the two most-read files is the cheapest way to fix it.

### 3. Add a drift line for the new pointer to `docs/governance/REPO_GOVERNANCE_AUDIT.md`
- Single bullet under "Pointer files added": this entrypoint plus the three plan files.
- Why now: per CANONICAL_DOC_STACK.md, every new doc must identify its place in the stack. Logging it in the audit closes the loop.

---

## Track 2 — First ontology-native seam (items 4–6)

### 4. Land `ONTOLOGY_NATIVE_OPERATOR_BRIEF_MASTER_SPEC.md`
- This is item 4 *as a doc*, not as code. Code lands in items 5 and 6.
- See [`ONTOLOGY_NATIVE_OPERATOR_BRIEF_MASTER_SPEC.md`](ONTOLOGY_NATIVE_OPERATOR_BRIEF_MASTER_SPEC.md) for problem, goal, non-goals, files, types, gates, witness/value events, artifact path, scheduler entry, tests, acceptance criteria, failure modes, and rollout sequence.
- Why now: writing the spec out forces the seam to be small enough to ship in one PR. If it is not, it gets split before any code is written.

### 5. Implement the operator-brief module behind a feature flag
- One new module: `dharma_swarm/operator_brief/insight_brief.py` (subdirectory, not flat top level — axiom A1 in `SOVEREIGN_MANIFEST.md`).
- Surgical edits to: the orchestrator dispatch tail, the gate evaluation call site, the artifact persistence path, the cron registration. Spec lists exact files.
- Feature flag: `DHARMA_OPERATOR_BRIEF_ENABLED=1` in env. Default off.
- Tests: see master spec §10. Required: object creation test, gate-block test (fail-closed), no-raw-bypass test.
- Why now: the spec is only proven when one tick of the live cron writes one `KnowledgeArtifact` of subtype `operator_brief` linked correctly. Anything less is documentation theatre.

### 6. Flip the feature flag on for one operator profile and witness one tick
- **Status: done** — witness commit `f57ccad`.
- No new code. Configuration change only.
- Capture the resulting `KnowledgeArtifact` id, the linked `WitnessLog` ids, the four `GateDecisionRecord` ids (one per applied gate), the `ActionProposal` id, the `Outcome` id, and the `ValueEvent` id.
- Land them in a one-page report under `reports/witness/<date>-operator-brief-first-tick.md`. This is the falsifiability checkpoint the audit asks for.
- Why now: a green test suite is not the same as a live tick. The audit explicitly notes the repo "delays falsifiability". This item closes that.

---

## Track 3 — Make the seam load-bearing for downstream substrates (items 7–8)

### 7. Wire the brief artifact into `RuntimeStateStore.artifact_records`
- Per audit §5 Slice 2, do not build a new artifact registry. Use `dharma_swarm/runtime_state.py` `record_artifact()`.
- Add the read-before-propose guard: the operator-brief generator must cite at least one `session_events` or `memory_facts` row. Test asserts this fails closed if no source is cited.
- Why now: this is the wiring step that prevents the seam from drifting back into a parallel data path. Without it, the brief is ontology-native in name only.

### 8. Add `LEDGER_WATCHER` to Guardian for empty operator-brief output
- Per audit §5 Slice 3 and §8 commit 3. Read-only against a temp `runtime.db`.
- DEGRADED when the brief cron has fired ≥10 times with zero new `KnowledgeArtifact` rows of subtype `operator_brief`. BLOCKER at ≥100 ticks.
- Why now: the seam needs a watchdog so silent failure is impossible. Without it, the next agent will not know if the substrate path has rotted out under them.

---

## Track 4 — Generalise to a value loop (items 9–10)

### 9. Add a `ValueEvent` aggregation read in the dashboard or CLI
- **Status: done** — PR #85 (pending merge)
- One new read-only surface: `dgc value-events --since <date>` lists `ValueEvent` rows linked from `operator_brief` artifacts, grouped by `Contribution.attributed_to`.
- No new substrate. Reads from existing ontology tables only.
- Why now: this is the smallest possible value-loop closure. Once value events from one seam are visible to operators, the case for opening a second seam (Dharma Radar v0) becomes empirical instead of aspirational.

### 10. Open the second seam (Dharma Radar v0) only after item 9 ships
- Do not start design work on Dharma Radar before item 9 is merged and one operator has used `dgc value-events` against real data for at least a week.
- The Dharma Radar plan inherits the same seven ontology-native checks from `BUILD_SESSION_ENTRYPOINT.md` §3. Do not relax them.
- Why now: opening a second seam earlier is the failure mode the audit warned about. The first seam has to carry weight before the second is reasonable.

---

## How this list stays current

- Each item is a PR. The PR closes by editing this file: status flips from `pending` to `done` with the merged commit hash.
- Items are not reordered. If priorities change, write a new file under `docs/plans/<date>-<slug>.md` that supersedes this one and link to it from `BUILD_SESSION_ENTRYPOINT.md`.
- If the audit synthesis is regenerated and changes the canonical substrate table, this file is rewritten before the next item is started, not after.
