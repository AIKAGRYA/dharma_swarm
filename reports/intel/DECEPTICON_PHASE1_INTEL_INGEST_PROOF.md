# Decepticon Phase 1 Intel Ingest Proof

Date: 2026-04-28
Worktree: `/Users/dhyana/promotion_worktrees/decepticon_phase1_intel`
Branch: `intel/decepticon-phase1`

## Canonical Path Used

The Decepticon phase-1 insights were fed through Dharma's existing sovereign intelligence adapter:

`build_sovereign_intelligence_layer(db_path=...)`
`-> SovereignMemoryPlaneAdapter`
`-> RuntimeStateStore.record_memory_fact(...)`
`-> memory_facts`

The report artifact was recorded through:

`RuntimeStateStore.record_artifact(...)`
`-> artifact_records`

No new substrate was created.

## Safety Boundary

The ingest targeted a repo-local runtime DB:

`reports/intel/decepticon_phase1_intel.runtime.db`

This file is ignored by git via `*.db`. The live `~/.dharma/state/runtime.db` was not touched.

## Ingest Result

```json
{
  "memory_facts": 10,
  "artifact_records": 1,
  "fact_ids": [
    "decepticon-phase1-001",
    "decepticon-phase1-002",
    "decepticon-phase1-003",
    "decepticon-phase1-004",
    "decepticon-phase1-005",
    "decepticon-phase1-006",
    "decepticon-phase1-007",
    "decepticon-phase1-008",
    "decepticon-phase1-009",
    "decepticon-phase1-010"
  ],
  "artifact_ids": [
    "decepticon-phase1-report"
  ]
}
```

## Versioned Export

The versioned memory payloads live at:

`reports/intel/decepticon_phase1_memory_records.jsonl`

The human-readable research report lives at:

`reports/intel/DECEPTICON_PHASE1_RESEARCH.md`
