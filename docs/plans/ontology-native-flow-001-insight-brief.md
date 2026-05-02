# Ontology-Native Flow 001 - Daily Insight Brief

## Goal

Build one private proof flow: a 04:30 WITA markdown brief for Dhyana at `~/dharma_briefs/<date>-brief.md`. It is valid only if each claim cites a real `Outcome` object, the publish action is gated, a `WitnessLog` is written, and ontology failures stop the run.

## New ObjectTypes / LinkDefs / ActionDefs

No new `ObjectType` is required for week 1.

Extend `KnowledgeArtifact` in `dharma_swarm/ontology.py:1066`:

| Property | Type | Required | Meaning |
| --- | --- | --- | --- |
| `audience` | `STRING` | no | intended reader, `dhyana` for this flow |
| `published_path` | `PATH` | no | final markdown path |
| `published_at` | `DATETIME` | no | publish timestamp |
| `published_channel` | `STRING` | no | `filesystem` |

Add `ActionDef`:

```python
ActionDef(
    name="Publish",
    object_type="KnowledgeArtifact",
    input_params={"channel": "string", "path": "path"},
    modifies=["published_path", "published_at", "published_channel"],
    telos_gates=["BHED_GNAN", "STEELMAN", "DOGMA_DRIFT", "CONSENT"],
)
```

Add `LinkDef`s:

| Link | Source -> Target | Cardinality | Use |
| --- | --- | --- | --- |
| `derived_from` | `KnowledgeArtifact -> Outcome` | `N:N` | every brief cites execution evidence |
| `cites_witness` | `KnowledgeArtifact -> WitnessLog` | `N:N` | brief cites the witnessing act |
| `published_to` | `KnowledgeArtifact -> KnowledgeArtifact` | `N:N` | draft-to-publication lineage if split later |

## New module: `dharma_swarm/insight_brief.py`

Implemented at `dharma_swarm/insight_brief.py`.

Signatures:

```python
class InsightBriefBuilder:
    def propose(self) -> list[OntologyObj]
    def compose(self, thread_objs: Iterable[OntologyObj]) -> OntologyObj
    def publish(self, brief_obj: OntologyObj) -> Path

def build_and_publish_daily_brief(...) -> Path
```

Compose loop:

1. Load score-ranked `Outcome` objects only: successful rows first, provider plumbing failures demoted, newest rows winning ties.
2. Fail if none exist.
3. Create `WitnessLog`.
4. Create draft `KnowledgeArtifact`.
5. Render claims as `ontology://KnowledgeArtifact/<id>#cites/Outcome/<id>`.
6. Update artifact content through the gateway.
7. Link `derived_from` for every `Outcome`.
8. Link `cites_witness`.
9. Publish through `Publish` action, then write markdown.

Target line count: ~280; current implementation is 280.

## New module: `dharma_swarm/ontology_action_gateway.py`

Implemented at `dharma_swarm/ontology_action_gateway.py`.

Required methods:

```python
create_object_or_fail(type_name, properties, created_by=...) -> OntologyObj
update_object_or_fail(object_id, updates, updated_by=...) -> OntologyObj
link_or_fail(link_name, source_id, target_id, ...) -> Link
execute_action_or_fail(object_type, action_name, object_id, params, ...) -> ActionExecution
```

Rules:

- Raises `OntologyGatewayError` on validation, link, action, or gate failure.
- Uses `TelosGatekeeper.check()` for actions with `telos_gates`.
- Persists shared registry writes when it owns the registry.
- Allows `REVIEW` by default, blocks `BLOCK`; `block_on_review=True` is available.

## TelicSeam Additions

Implemented `TelicSeam.record_publish(artifact_id, channel, path)` at `dharma_swarm/telic_seam.py:456`.

It remains best-effort and debug-logged. The Insight Brief does not rely on it; the brief uses `OntologyActionGateway`.

## `world_actions.py` Wrapping

Week 2 fix, because primary checkout has no `world_actions.py`.

If `.claude/worktrees/research-integration/dharma_swarm/world_actions.py` is promoted, add:

```python
def gated_world_action(name: str, payload: dict) -> WorldActionResult:
    proposal = gateway.create_object_or_fail("ActionProposal", ...)
    decision = gatekeeper.check(action=name, content=json.dumps(payload))
    gateway.create_object_or_fail("GateDecisionRecord", ...)
    if decision.decision == GateDecision.BLOCK:
        return WorldActionResult(False, name, decision.reason)
    return _execute_world_action(name, payload)
```

Wrap `github_commit_push`, `github_create_pr`, and `github_create_issue`. Block PR creation if no gate record is persisted.

## Cron Addition

Implemented in repo `cron_jobs.json` and active store `~/.dharma/cron/jobs.json`:

```json
{
  "id": "ontology_insight_brief",
  "trigger": "cron",
  "schedule": {"hour": 4, "minute": 30},
  "handler": "insight_brief",
  "ontology_path": "/Users/dhyana/.dharma/ontology.db",
  "output_dir": "/Users/dhyana/dharma_briefs"
}
```

The active store uses cron expression `30 20 * * *`, which is 04:30 WITA.

Implemented handler dispatch in `dharma_swarm/cron_runner.py` via handler
`insight_brief`. The handler passes `ontology_path` explicitly; otherwise
running from the repo root can resolve to repo-local `.dharma/ontology.db`.

## Acceptance Tests

Implemented in `tests/test_insight_brief.py`:

- `test_brief_creates_typed_objects`
- `test_brief_fails_without_outcomes`
- `test_propose_demotes_provider_plumbing_failures`
- `test_failures_render_under_breakages`
- `test_brief_citations_resolve`
- `test_publish_action_passes_gates`
- `test_brief_bypass_attempt_fails`

Current result:

```text
pytest -q tests/test_insight_brief.py tests/test_ontology_registry.py tests/test_telic_seam.py tests/test_ontology_hub.py
175 passed, 1 warning in 0.65s
```

## Canonical Writer Lock - 2026-05-02

`dharma_swarm.insight_brief` is the canonical Phase 1 Daily Insight Brief writer.

PR57 `operator_brief` is parked. Its cron entry remains disabled and env-gated
by `DHARMA_OPERATOR_BRIEF_ENABLED`. Existing `operator_brief` rows stay in
`ontology.db` as historical test/probe rows, but Phase 1 must not produce new
`operator_brief` rows unless the canonical decision changes.

Day 1 for the 56-day Phase 1 count is **2026-05-02 at 04:30 WITA**. The May 1
brief was a manual/live test run, not the scheduled production start.

Decision note: `docs/governance/CANONICAL_DAILY_BRIEF_WRITER_2026-05-02.md`.

## Week 1 Calendar - IN PRODUCTION

**2026-05-01 DONE:** schema, gateway, builder, cron handler, tests landed.
Manual/live test brief generated (`2026-05-01-brief.md`).

**2026-05-02 DONE:** active daemon fired `ontology_insight_brief` at 04:30 WITA
and generated `/Users/dhyana/dharma_briefs/2026-05-02-brief.md`. Scheduled
production rows:

- `WitnessLog/27c3d9cf60ef4939`, `created_by=insight_brief`, `created_at=2026-05-01T20:30:35.326389Z`.
- `KnowledgeArtifact/bc05093b1e8d4b77`, `created_by=insight_brief`, `created_at=2026-05-01T20:30:37.717086Z`.

**Remaining this week:**
- **2026-05-03-07:** fix content quality only. Provider plumbing failures are demoted in ranking; the remaining work is improving the quality and diversity of successful Outcome rows.
- **2026-05-08:** remove legacy Entity/ONTOLOGY dict from `ontology.py` (tagged for this date). Remove Entity/ONTOLOGY from `__all__`.

## Week 2 Calendar

- Wrap promoted `world_actions` or explicitly delete/quarantine the research worktree path. Add test proving `github_create_pr` cannot run without a gate decision record.
- Wire `record_dispatch` and `record_gate_decision` into `agent_runner.py` alongside existing `record_outcome` calls. This closes the metabolic loop gap (decision chain currently missing).

## Week 3-4 Calendar

Week 3: director-to-ontology contract. `thinkodynamic_director.py` and `overnight_director.py` must emit `ActionProposal`, `GateDecisionRecord`, and `Outcome` for selected flows.

Week 4: Ginko first foot in. Keep existing files, dual-write one `VentureCell`, daily Brier dashboard as `KnowledgeArtifact`, and backtest run as `Outcome`.

## Standing Rules

Pre-commit warning hook:

```text
For any new file under dharma_swarm/ with .write_text or open(..., "w"):
  require import dharma_swarm.telic_seam
  OR require comment: # substrate-bypass: <reason>
Warn only. Do not block in week 1.
```

Purpose: stop the bleed without freezing development.

## Falsification Criteria

1. **2026-05-08:** `WitnessLog` count still 5 (manual/cron-runner baseline) -> substrate failed to sustain daily production.
2. **2026-05-15:** Dhyana stopped reading -> artifact failed.
3. **Always:** citation does not resolve to real `Outcome` -> block-on-fail broken.
4. **2026-05-15:** content reads as "Claude wrote a summary" -> withdraw substrate claim.

## What's Deferred

- Mirror surface.
- TELOS AI surface.
- Audit-others phase.
- New branding.
- New architecture documents.
- Any surface beyond the brief.

Parking lot: `~/dharma_swarm/docs/parking_lot/REFRAMES_DEFERRED.md`.

## What Codex Will Do vs What Dhyana Must Do

Codex has produced: schema diff, gateway, builder, cron handler, cron entry, tests, synthesis, plan. First brief generated.

**Dhyana must:**
1. Confirm on 2026-05-02 that launchd PID `com.dharma.cron-daemon` produced the 04:30 WITA brief. The active scheduler is `~/.dharma/cron/jobs.json`, not repo-only `cron_jobs.json`.
2. Keep the runtime producing high-signal Outcome rows; the brief is only as good as the execution data it cites.
3. Choose the one external witness.
4. On 2026-05-08: remove the deprecated Entity/ONTOLOGY dict (lines 1564-1722, plus `__all__` entries).
5. Read the brief tomorrow morning. That's the test.
