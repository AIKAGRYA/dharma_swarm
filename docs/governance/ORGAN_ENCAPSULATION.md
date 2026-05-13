# Organ Encapsulation v0

Encapsulation in Dharma Swarm means each operational organ owns one kind of
truth, hides its internal machinery, and exposes narrow facts or commands to
other organs.

It does not mean merging AgentOps, KaizenOps, YDS, Daily Brief, burn tracking,
and TelicSeam into one subsystem. That would flatten different organs into a
new monolith.

## Rule

```text
private organ state/process
  -> canonical fact artifact
  -> explicit adapter/API
  -> operator synthesis
```

The v0 code membrane is `dharma_swarm.operator_core.operating_facts`.

## Boundaries

| Organ | Owns | Emits | Must Not Mutate |
|---|---|---|---|
| AgentOps | Bounded repo execution facts | `AgentOpsRunFact` | YDS, Daily Brief, KaizenReview |
| KaizenReview | Improvement evidence from completed AgentOps runs | `KaizenReviewFact` | AgentOps, YDS, Daily Brief |
| Human YDS | Human-authoritative quality judgment | `HumanQualityRatingFact` | AgentOps, KaizenReview, Daily Brief |
| Burn/Cost | Resource-spend and waste signals | `BurnReportFact` | AgentOps, YDS, Telic value |
| Revenue | Self-funding/product wedge signals | `RevenueSignalFact` | AgentOps, YDS, Telic value |
| Daily Operating Brief | Human-facing synthesis | `DailyOperatingBrief` | Upstream fact sources |
| Command Spine | Dry-run planning and next-packet recommendation | `WorkPacketDraft`, `AgentOpsReview` | AgentOps execution state, Telic value |
| Telic Value | Outcome/ValueEvent/Contribution truth | ontology objects | AgentOps, YDS, Daily Brief |

## Current APIs

- `load_agentops_run_facts(path)` reads AgentOps `report.json` files.
- `load_kaizen_review_facts(path)` reads KaizenReview `kaizen_review.json` files.
- `append_human_yds_rating(path, ...)` writes one human-authoritative rating.
- `load_human_yds_rating_facts(path)` reads old and new YDS records.
- `load_burn_report_facts(path)` reads JSON/JSONL burn or cost records.
- `load_revenue_signal_facts(path)` reads text revenue notes.
- `build_operating_fact_bundle(inputs)` builds the synthesis input bundle.
- `organ_state_facts(bundle)` projects declared-vs-observed organ state.
- `coherence_map_to_dict(bundle)` serializes the read-only coherence projection.
- `build_daily_operating_brief(inputs)` renders the operator-facing synthesis.

`OrganStateFact` is advisory only. It does not schedule work, mutate ontology,
assign authority, approve merges, or replace the upstream organ facts.

## Daily Brief Rule

The Daily Operating Brief consumes facts. It does not own AgentOps, Kaizen,
YDS, burn, revenue, ontology, memory, dashboard, or API state.

This keeps the brief useful without letting it become a hidden runtime
authority.

## Rust Boundary

Rust is allowed only after the Python membrane is stable.

Good future Rust candidates:

- AgentOps scope/diff validation.
- Append-only YDS ledger integrity and hash-chain verification.
- High-volume trace or report compaction.
- Workspace/process custody and lease supervision.

Keep in Python:

- intent routing,
- mission planning,
- Daily Brief synthesis,
- YDS semantics,
- Kaizen heuristics,
- telos/policy logic.

The trigger is not "Rust feels serious." The trigger is:

1. stable contract,
2. deterministic behavior,
3. green focused tests,
4. measured hot path, security pressure, or clear Python-pain.
