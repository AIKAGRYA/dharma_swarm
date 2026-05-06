# Operator Brief First Tick — Witness Report

**Date:** 2026-05-05
**Environment:** local / Johns-MacBook-Pro.local
**Feature flag:** DHARMA_OPERATOR_BRIEF_ENABLED=1

## Captured IDs

| Object Type | ID | Created At |
|---|---|---|
| KnowledgeArtifact | `5ecf6797e8b74a05` | `2026-05-05T05:19:25.918967Z` |
| ActionProposal | `58104db983ad4d56` | `2026-05-05T05:19:25.895418Z` |
| GateDecisionRecord (gate 1 / CONSENT) | `2f3d1982eb4f48b5` | `2026-05-05T05:19:25.918211Z` |
| GateDecisionRecord (gate 2 / BHED_GNAN) | `82fff283226e463f` | `2026-05-05T05:19:25.918544Z` |
| GateDecisionRecord (gate 3 / STEELMAN) | `cb53a168eb424adf` | `2026-05-05T05:19:25.918694Z` |
| GateDecisionRecord (gate 4 / DOGMA_DRIFT) | `e9f41c58545e45bc` | `2026-05-05T05:19:25.918833Z` |
| Outcome | `58aafa5658074201` | `2026-05-05T05:19:25.935314Z` |
| ValueEvent | `1e61149fc266435a` | `2026-05-05T05:19:25.935576Z` |
| WitnessLog (tick start) | `76b1f2bb25a549da` | `2026-05-05T05:19:25.895620Z` |
| WitnessLog (CONSENT) | `680c9777ccfd4d23` | `2026-05-05T05:19:25.918519Z` |
| WitnessLog (BHED_GNAN) | `61cfe6563fe54aa5` | `2026-05-05T05:19:25.918675Z` |
| WitnessLog (STEELMAN) | `0f643518d58c4e62` | `2026-05-05T05:19:25.918816Z` |
| WitnessLog (DOGMA_DRIFT) | `d7c1f87cda7b4cfc` | `2026-05-05T05:19:25.918948Z` |
| WitnessLog (materialise) | `620c8c25235844c7` | `2026-05-05T05:19:25.935283Z` |

## Verification

- [x] KnowledgeArtifact has subtype `operator_brief`
- [x] All four gate decisions are linked to ActionProposal `58104db983ad4d56` by `proposal_id`; the current ontology link schema records only the first gate as typed `has_gate_decision` because that link is one-to-one
- [x] Outcome is linked to ActionProposal
- [x] ValueEvent is linked to Outcome
- [x] Artifact is persisted in RuntimeStateStore.artifact_records

## Runtime Evidence

- Cron scheduler command: `DHARMA_OPERATOR_BRIEF_ENABLED=1 ... dgc_cli cron daemon --interval-sec 0 --max-loops 1`
- Scheduler result: `jobs_executed=1`
- One-shot runtime cron job id: `646527d171be`
- Cron output: `/Users/dhyana/.dharma/cron/output/646527d171be/2026-05-05_05-19-27.md`
- Cron output summary: `operator_brief artifact=5ecf6797e8b74a05 witnesses=6`
- Ontology DB queried: `/Users/dhyana/.dharma/ontology.db`
- Runtime state DB queried: `/Users/dhyana/.dharma/state/runtime.db`

The live ontology DB in this branch uses tables `objects` and `links`; those are the schema-equivalent tables for the requested `ontology_objects` and `ontology_links` queries.

The artifact's `RuntimeStateStore.artifact_records.metadata_json` includes:

- `proposal_id`: `58104db983ad4d56`
- `gate_decision_ids`: `2f3d1982eb4f48b5`, `82fff283226e463f`, `cb53a168eb424adf`, `e9f41c58545e45bc`
- `outcome_id`: `58aafa5658074201`
- `value_event_id`: `1e61149fc266435a`
- `witness_log_ids`: `76b1f2bb25a549da`, `680c9777ccfd4d23`, `61cfe6563fe54aa5`, `0f643518d58c4e62`, `d7c1f87cda7b4cfc`, `620c8c25235844c7`
