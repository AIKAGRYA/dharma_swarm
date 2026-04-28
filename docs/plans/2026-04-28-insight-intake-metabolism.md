# Insight Intake Metabolism Spec

Date: 2026-04-28
Status: Proposed
Scope: Canonical pipeline for random insights, external signals, inspirations, research leads, and operator intuitions.

## 1. Problem

Dharma Swarm receives useful signals from many informal sources:

- a random screenshot or social post
- an open-source project discovery
- a conversation insight
- a paper, tool, product, or architecture pattern
- an operator intuition
- a warning from another agent
- a recurring failure pattern

Today, these signals can land in arbitrary places: chat history, markdown reports, `docs/research`, ad hoc `reports/` folders, GitHub issues, local memory, or experimental branches. That preserves some information but does not reliably metabolize it into reusable system knowledge.

The missing capability is not another wiki. It is a canonical metabolism pipeline:

`capture -> research -> distill -> reflect -> decide -> apply -> retrieve`

## 2. Design Principle

Do not build a new substrate.

Use the existing canonical runtime and knowledge surfaces:

| Need | Canonical Surface |
| --- | --- |
| Raw event / operator intent | `RuntimeStateStore.session_events`, `operator_actions` |
| Full research/report artifact | `RuntimeStateStore.artifact_records` |
| Distilled durable facts | `RuntimeStateStore.memory_facts` via `SovereignMemoryPlaneAdapter` |
| Future prompt visibility | `RuntimeStateStore.context_bundles` via `ContextCompiler` |
| Human-readable durable corpus | `docs/research/`, `docs/plans/`, accepted ADRs/specs |
| Implementation decision | GitHub issue, ADR, PR, or task |

`/chetana` is not the default landing zone until it is merged, tested, and recognized as canonical on `origin/main`.

Docs/wiki are not enough by themselves because passive documents do not guarantee future agent retrieval. Runtime rows are not enough by themselves because humans need inspectable prose. The pipeline must write both.

## 3. Memory Taxonomy

Every captured insight should be classified into one or more memory types:

| Type | Meaning | Runtime Representation |
| --- | --- | --- |
| Semantic | Facts, claims, risks, stable project knowledge | `memory_facts` |
| Episodic | What happened, when, under what context, with outcome | `session_events`, `operator_actions` |
| Procedural | Reusable workflow, runbook, or skill | future skill store / docs / issue |
| Artifact | Full report, transcript, screenshot summary, source digest | `artifact_records` |
| Decision | Accepted/rejected architectural or operational choice | ADR / issue / PR note |

This mirrors common agent-memory practice in LangGraph, Letta/MemGPT, LlamaIndex, Reflexion, Generative Agents, and Voyager: raw experience is not the same as durable memory, and durable memory is not the same as an accepted procedure.

## 4. Lifecycle

### Stage 0: Capture

Goal: preserve the spark without over-processing it.

Input examples:

- freeform operator note
- URL
- screenshot
- transcript fragment
- local file path
- repo or paper reference

Output:

- `operator_actions` row when there is an explicit operator intent or decision
- `session_events` row when it is passive context
- optional raw markdown note under `reports/research/intake/`

Minimum fields:

- `capture_id`
- `captured_at`
- `source_kind`
- `source_ref`
- `operator_prompt`
- `initial_hypothesis`
- `risk_level`
- `requested_depth`

### Stage 1: Research

Goal: establish source-backed current truth.

Actions:

- browse current sources when temporal freshness matters
- inspect local repo/code when it is a Dharma integration question
- collect source list
- classify uncertainty and conflicts

Output:

- research report markdown
- source list
- `artifact_records` row pointing to the report

Suggested path:

`reports/research/intake/YYYY-MM-DD_<slug>_research.md`

### Stage 2: Distill

Goal: convert a long report into machine-usable atomic memory.

Actions:

- extract 5-20 atomic claims
- assign `truth_state`
- attach confidence and provenance
- mark risks and non-goals

Output:

- JSONL export of memory records
- `memory_facts` rows via `SovereignMemoryPlaneAdapter`

Truth states:

- `candidate`: plausible, useful, not yet accepted
- `promoted`: accepted enough to guide future work
- `stale`: previously useful but likely outdated
- `rejected`: reviewed and not to be used
- `archived`: preserved but no longer active

### Stage 3: Reflect

Goal: metabolize, not merely store.

Questions:

- What does this change about Dharma's roadmap?
- What existing substrate should absorb it?
- What duplicate/new-substrate temptation should be avoided?
- What would make this dangerous if applied too eagerly?
- What follow-up issue or test would make it real?

Output:

- synthesis section in the report
- candidate issue(s)
- optional ADR if a decision is being made

### Stage 4: Decide

Goal: separate "interesting" from "authorized work."

Decision outcomes:

- `observe`: keep as background context only
- `research_more`: source quality or risk insufficient
- `promote_memory`: make future agents see it
- `open_issue`: scope work but do not implement yet
- `write_adr`: record a decision
- `implement`: approved, scoped, testable work
- `reject`: explicitly avoid

Output:

- `operator_actions` row for human decision
- GitHub issue or ADR if actionable
- memory fact truth-state updates

### Stage 5: Apply

Goal: turn selected insight into repo change without scope leak.

Allowed application forms:

- small test
- guardrail
- template
- docs update
- runtime wiring using existing substrate
- issue/ADR only

Not allowed by default:

- new substrate
- broad refactor
- dashboard expansion
- live daemon/state mutation
- importing unrelated external architecture wholesale

### Stage 6: Retrieve

Goal: ensure future agents actually see relevant insight before acting.

Mechanism:

- `ContextCompiler` already reads promoted `memory_facts`
- future task dispatch should record `context_bundles`
- read-before-propose tests should assert relevant memory is retrieved for matching tasks

Acceptance:

- a later task about the same subject receives the promoted facts in its context bundle
- a later task can cite the source artifact
- stale/rejected facts are excluded unless explicitly requested

## 5. Proposed CLI

Implement later as:

```bash
python -m dharma_swarm.insight_intake capture \
  --title "Decepticon red-team framework" \
  --source-url "https://github.com/PurpleAILAB/Decepticon" \
  --risk high \
  --notes "Saw a viral post; evaluate whether Dharma should use it."

python -m dharma_swarm.insight_intake research <capture_id>

python -m dharma_swarm.insight_intake distill <artifact_id>

python -m dharma_swarm.insight_intake decide <capture_id> \
  --decision promote_memory \
  --reason "Architecture lessons useful; execution unsafe."

python -m dharma_swarm.insight_intake status <capture_id>
```

The CLI must be a thin orchestration layer over existing stores. It must not create a separate insight database unless that database is only a local export/cache of canonical runtime rows.

## 6. Data Contract

### InsightCapture

```json
{
  "capture_id": "insight_20260428_decepticon",
  "title": "Decepticon autonomous red-team framework",
  "captured_at": "2026-04-28T00:00:00Z",
  "source_kind": "github_repo",
  "source_ref": "https://github.com/PurpleAILAB/Decepticon",
  "operator_prompt": "Can we use this?",
  "initial_hypothesis": "Potentially useful architecture, unsafe to run directly",
  "risk_level": "high",
  "status": "researching",
  "metadata": {}
}
```

### InsightMemoryRecord

Use `dharma_swarm.contracts.common.MemoryRecord` unchanged:

```json
{
  "record_id": "insight-decepticon-001",
  "kind": "integration_guardrail",
  "text": "Do not run Decepticon on the normal desktop; use a disposable isolated VM only.",
  "truth_state": "promoted",
  "session_id": "insight_20260428_decepticon",
  "task_id": "external-security-intake",
  "agent_id": "insight-intake",
  "score": 0.95,
  "metadata": {
    "subject": "PurpleAILAB/Decepticon",
    "source_report": "reports/research/intake/2026-04-28_decepticon_research.md"
  },
  "provenance": {
    "source_url": "https://github.com/PurpleAILAB/Decepticon",
    "review_commit": "..."
  }
}
```

### InsightDecision

Store as `operator_actions`:

```json
{
  "action_name": "insight_decision",
  "actor": "operator",
  "reason": "Architecture lessons useful, execution unsafe",
  "payload": {
    "capture_id": "insight_20260428_decepticon",
    "decision": "promote_memory",
    "next_action": "open_issue",
    "blocked_actions": ["install_on_host", "wire_c2_stack"]
  }
}
```

## 7. Repository Layout

Proposed stable paths:

```text
reports/research/intake/      raw/source-backed intake reports
reports/research/synthesis/   cross-intake synthesis and trend reports
docs/research/accepted/       durable accepted research notes
docs/adr/                     accepted architectural decisions
docs/plans/                   proposed implementation specs and plans
```

Do not use `reports/intel/` as the long-term canonical name. It is acceptable as a temporary prototype artifact, but the stable name should be `research/intake` because the pipeline includes more than threat intelligence.

## 8. Integration With Existing Dharma Substrates

### RuntimeStateStore

Use:

- `record_artifact`
- `record_memory_fact`
- `record_operator_action`
- `record_session_event`
- later: `record_context_bundle`

Do not add new tables for phase 1.

### Sovereign Intelligence Layer

Use:

- `build_sovereign_intelligence_layer`
- `SovereignMemoryPlaneAdapter.write_memory`

This keeps facts behind the existing `MemoryPlane` contract.

### AutoResearch

Use as a source-backed research helper when the question fits its scope. It is not yet the full metabolism loop.

### KnowledgeStore

Use for retrieval/corpus search where helpful, but do not make it the source of truth for promoted runtime facts. It is a retrieval layer, not the decision ledger.

### Scout/Synthesis

Existing scout reports under `~/.dharma/scouts` are useful prior art but are not ideal as the canonical intake path because they write live home-state paths and were designed for domain scouts, not operator insight metabolism.

### Chetana

Defer until merged and tested. Later, Chetana may become the reflective stage. For now, treating it as canonical would create an unreviewed parallel substrate.

## 9. Tests Required Before Implementation Is Accepted

Minimum tests:

1. Capture writes an `operator_actions` row for explicit operator input using a temp runtime DB.
2. Research artifact records a markdown report in `artifact_records`.
3. Distill writes `memory_facts` through `SovereignMemoryPlaneAdapter`, not direct ad hoc SQL.
4. Truth-state update promotes/rejects a candidate memory fact.
5. Context compiler retrieves promoted facts for a related task.
6. Rejected/stale facts are not included by default.
7. All tests use temp runtime DBs, not `~/.dharma`.
8. No dashboard/API or Chetana dependency in phase 1.

## 10. First Implementation Slice

Slice A: File + Memory Intake Only

Files likely touched:

- `dharma_swarm/insight_intake.py`
- `tests/test_insight_intake.py`
- `docs/plans/2026-04-28-insight-intake-metabolism.md`

Behavior:

- create a capture record
- write a report artifact path
- ingest JSONL `MemoryRecord`s through `SovereignMemoryPlaneAdapter`
- record an operator decision
- prove row counts in temp DB

Explicit non-goals:

- no web UI
- no dashboard
- no Chetana
- no live `~/.dharma`
- no new DB schema
- no automatic implementation PRs
- no autonomous browsing without operator request

## 11. Definition Of Done

The pipeline is usable when a random insight can be processed end to end:

1. The operator captures an idea.
2. The system creates an intake artifact.
3. Research output is source-backed.
4. Atomic memory facts are written with provenance.
5. The operator decision is recorded.
6. A future related task sees the promoted memory in its context bundle.
7. The full chain can be audited from future task back to source.

## 12. Immediate Recommendation

Do not move fast into Chetana or wiki-first work.

Create Slice A as a small canonical intake tool that writes:

- one markdown artifact
- one artifact record
- several memory facts
- one operator action

Then use the Decepticon review as the first fixture.
