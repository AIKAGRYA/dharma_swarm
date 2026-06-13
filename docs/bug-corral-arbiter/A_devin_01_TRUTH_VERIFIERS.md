# Truth Verifiers

**Consolidated from 9 source files. Provenance: `09_PROVENANCE.md`.**
**Last source touched:** 2026-06-05

Declared-vs-actual findings: where the code logs or claims one thing and
does another, where identity and envelope schemas fragment, and where the
dashboard reports fidelity it does not have. These are the audits that
check the system against its own ground truth.

## Headline state

The load-bearing finding is `execute_action`: the ontology action path
records `"success"` and appends to the audit log without applying the
field mutations the schema declares. Around it sit a cluster of
declared-vs-actual gaps — an auto-approving interrupt gate, identity and
envelope sprawl with no join keys — plus two runtime-truth audits
(seam, dashboard) that drove the current Runtime Truth Spine work.

The andon audit also produced a verifier-quality lesson: the upstream
Codex audit was directionally right about fragmentation but evidentially
sloppy (hallucinated names, miscounts, audited untracked working-tree
files). Treat single-agent audits as smoke signals, not specifications.

## Findings (sorted by severity, then date desc)

### CRITICAL · TV-01 · execute_action logs success without mutating

- Sources: `docs/research/palantir-ontology/vocabulary-census/andon/reconciliation.md`, `.../verdicts/perplexity-C.md`
- First reported: 2026-06-01
- Last confirmed: 2026-06-05
- Detail: `execute_action` at `dharma_swarm/ontology.py:594-639` sets
  `execution.result = "success"` (line 637) and appends to `_action_log`
  (line 638), then returns. It never reads `ActionDef.modifies`
  (`dharma_swarm/ontology.py:140`) and never calls `update_object`, so the
  declared mutation never fires. `ActionDef.modifies` is a dead schema
  field: 90+ `modifies=[...]` declarations exist (e.g.
  `dharma_swarm/ontology.py:878,910,914,1599`) but none is consumed at
  execute time. No test asserts post-action object state
  (`tests/test_ontology_registry.py:345-404` checks only
  `result.result == "success"`). The `ActionDef` docstring
  (`dharma_swarm/ontology.py:130-135`) promises atomic, auditable,
  reversible mutation; the execution path provides none. Not a regression
  — never wired.
- Status: OPEN

### MAJOR · TV-02 · InterruptGate auto-approves in production

- Sources: `docs/research/palantir-ontology/vocabulary-census/andon/reconciliation.md`, `.../verdicts/perplexity-C.md`
- First reported: 2026-06-01
- Last confirmed: 2026-06-05
- Detail: `InterruptGate.__init__`
  (`dharma_swarm/checkpoint.py:97-106`) defaults `auto_approve=True`;
  `interrupt()` (`dharma_swarm/checkpoint.py:108-152`) returns `APPROVE`
  immediately when `callback is None`. The production singleton
  `_interrupt_gate = InterruptGate()` at `dharma_swarm/cascade.py:36` is
  wired with no callback, so every gate-phase interrupt auto-approves. A
  full callback + timeout + filesystem path exists
  (`dharma_swarm/checkpoint.py:121-150`) but is not used in production.
  Separately, `resolve()` (`dharma_swarm/checkpoint.py:154-163`) verifies
  no caller identity — any process that knows a `request_id` can forge an
  approval.
- Status: OPEN

### MAJOR · TV-03 · execute_action skips write-role check

- Sources: `docs/research/palantir-ontology/vocabulary-census/andon/verdicts/perplexity-C.md`
- First reported: 2026-06-01
- Last confirmed: 2026-06-01
- Detail: `execute_action` (`dharma_swarm/ontology.py:594-639`) checks
  `telos_required` but never checks `write_roles`. By contrast
  `create_object` and `update_object` are guarded
  (`dharma_swarm/ontology.py:280-292`). A caller with no write permission
  can execute any action on any object so long as telos gates pass or the
  type is not `telos_required`.
- Status: OPEN

### MAJOR · TV-04 · Identity sprawl with no join keys

- Sources: `docs/research/palantir-ontology/vocabulary-census/andon/reconciliation.md`, `.../verdicts/perplexity-A.md`
- First reported: 2026-06-01
- Last confirmed: 2026-06-05
- Detail: at least 13 identifier surfaces, with three acute collisions.
  `claim_id` fragments four ways with four generators and zero FKs:
  `TaskClaim.claim_id` (`dharma_swarm/runtime_state.py:352`, prefix
  `clm_`), `DharmaCorpus.Claim.id` (`dharma_swarm/dharma_corpus.py:93`,
  format `DC-YYYY-NNNN`), `auto_research.ClaimRecord.claim_id`
  (`dharma_swarm/auto_research/models.py:80`), `DecisionClaim.claim_id`
  (`dharma_swarm/decision_ontology.py:106`). `receipt_id` exists on five
  surfaces with mismatched types (`dharma_swarm/spine/receipt.py:41` is
  `UUID`; `dharma_swarm/board/models.py:111`,
  `dharma_swarm/knowledge_ops/memory_promotion_executor.py:94`,
  `dharma_swarm/memory_kernel/burn_in.py:25`,
  `dharma_swarm/operator_core/closure_v0.py:64` are `str`). `agent_id` is
  type-inconsistent: a UUID hex from `AgentConfig.id`
  (`dharma_swarm/models.py:156`) at some call sites, a role-name string
  (`"claude"`) at others (`dharma_swarm/telic_seam.py:109`,
  `dharma_swarm/agent_runner.py:1654`). `correlation_id` is aliased to
  `trace_id` by the spine (`dharma_swarm/spine/__init__.py:15-24`,
  `dharma_swarm/spine/receipt.py:94-96`), but `A2ATask.trace_id` defaults
  to `""` (`dharma_swarm/a2a/a2a_server.py:222`), so the correlation chain
  can break silently. The intended unifier `CorrelationContext`
  (`dharma_swarm/correlation_context.py:113-155`) is voluntary and read by
  no ID-bearing struct on construction. `correlation_key`, named by the
  upstream audit, does not exist anywhere in source.
- Status: OPEN

### MAJOR · TV-05 · Envelope schemas fragmented and unbridged

- Sources: `docs/research/palantir-ontology/vocabulary-census/andon/reconciliation.md`, `.../verdicts/perplexity-B.md`
- First reported: 2026-06-01
- Last confirmed: 2026-06-05
- Detail: six real coordination envelopes with no shared required field
  set — `RuntimeEnvelope` (`dharma_swarm/runtime_contract.py:41-50`),
  `MessageBus` messages and a disjoint events sub-schema
  (`dharma_swarm/message_bus.py:27-35` and `:57-67`), `A2ATask`
  (`dharma_swarm/a2a/a2a_server.py`), `SignalBus`, and `OnboardingReceipt`
  — plus an eighth, `CanonicalEvent`
  (`dharma_swarm/engine/events.py:58`), uncatalogued and unbridged. Only
  about 3 of 15 pairwise translators exist
  (`dharma_swarm/a2a/a2a_bridge.py:74,187,263-283`;
  `dharma_swarm/session_event_bridge.py:51`). `trace_id` overlaps
  `RuntimeEnvelope` (auto-generated, `dharma_swarm/runtime_contract.py:68`)
  and `A2ATask` (optional carry-through,
  `dharma_swarm/a2a/a2a_server.py:213`) with no mechanism forcing one
  value across a causal chain. NATS is at least three ad-hoc wire formats,
  not one schema, and lives outside `dharma_swarm/`.
- Status: OPEN

### MAJOR · TV-06 · Runtime truth-surface explosion

- Sources: `docs/reports/CONVERGED_SEAM_AUDIT_RUNTIME_TRUTH_SPINE.md`
- First reported: 2026-05-28
- Last confirmed: 2026-05-28
- Detail: the converged Perplexity-plus-Codex seam audit found no single
  canonical record of what happened. Overlapping truth or persistence
  surfaces include `session_ledger.py`, `runtime_lifecycle.py`,
  `telemetry_plane.py`, `agent_registry.py`, `witness.py`,
  `engine/event_memory.py`, `operator_brief/persistence.py`,
  `board/event_log.py`, `sakshi/provenance_log.py`, `message_bus.py`,
  `lineage.py`, `telic_seam.py`. `AgentRunner.run_task` carries ~16
  responsibilities; `SwarmManager` is a wiring god object. Prescription:
  build the Runtime Truth Spine (one `EvidenceReceipt`, one
  `invoke_agent(...)`, one `RoutingDecision`) before expanding fabric, and
  add an anti-accretion rule requiring any new `dharma_swarm/` file that
  imports `sqlite3`/`aiosqlite` to declare its relation to
  `EvidenceReceipt`.
- Status: IN PROGRESS — driving track `runtime-truth-spine-adoption-2026-06`

### MAJOR · TV-07 · Dashboard fidelity gaps

- Sources: `docs/state/DASHBOARD_FIDELITY_AUDIT.md`
- First reported: 2026-05-20
- Last confirmed: 2026-06-05
- Detail: of the dashboard pages, 9 are LIVE, 13 are PROVIDER-GATED
  (endpoint exists, sparse until agents dispatch), and 5 are STUB —
  Observatory (`/api/agents/observatory` does not exist), Synthesizer (no
  endpoint), Workflows and Blocks (placeholders), Ecosystem (viz exists
  but ReactFlow not wired). Env alias mismatches (`GEMINI_API_KEY`,
  `NVIDIA_API_KEY`, `PERPLEXITY_API_KEY`) were fixed via
  `normalize_env_aliases()`. Provider status at audit time: Anthropic low
  credits, Groq access denied, SiliconFlow and Moonshot auth failures.
- Status: OPEN — STUB pages and provider-auth lanes outstanding

### MINOR · TV-08 · No workflowRun boundary

- Sources: `docs/research/palantir-ontology/vocabulary-census/andon/verdicts/devin-D.md`
- First reported: 2026-06-01
- Last confirmed: 2026-06-02
- Detail: 13 layered state owners exist but none traces a full workflow
  lifecycle. The contract `CWS` at
  `dharma_swarm/operator_core/contracts.py:217` declares `workflow_id`,
  `status`, `active_lane_ids`, `blocked_by` but has no runtime producer.
  `DelegationRun` (`dharma_swarm/runtime_state.py:368`) is the closest
  durable record but is scoped to one delegation, not a workflow. The
  owners are layered (no two write the same table), not competing; the gap
  is the missing unifying type.
- Status: OPEN — structural gap, not a conflict

### INFO · TV-09 · A2ATask dual-use is bounded

- Sources: `docs/research/palantir-ontology/vocabulary-census/andon/verdicts/devin-E.md`
- First reported: 2026-06-01
- Last confirmed: 2026-06-02
- Detail: `A2ATask` is used for both external (remote node) and internal
  (intra-swarm) work, but the upstream "dangerous conflation" framing is
  wrong. Auth is enforced at the gateway
  (`dharma_swarm/a2a/node_gateway.py:161-163`); origin is tagged
  (`metadata["source"]` at `dharma_swarm/a2a/a2a_bridge.py:127`,
  `from_agent="remote"` at `dharma_swarm/a2a/node_gateway.py:211`); the A2A
  task store is separate from the swarm board; cycle detection caps
  delegation depth at 10. The only real gap is that `A2ATask.from_agent`
  is an untyped string. Recorded so the question is not re-litigated.
- Status: RESOLVED — verdict: not a defect

### INFO · TV-10 · Audit-quality lesson from the andon

- Sources: `docs/research/palantir-ontology/vocabulary-census/andon/reconciliation.md`
- First reported: 2026-06-01
- Last confirmed: 2026-06-05
- Detail: the upstream Codex audit was directionally correct on
  fragmentation but evidentially unreliable. It hallucinated names
  (`correlation_key`, a "spec envelope", `nats_a2a_bridge.py`), miscounted
  (the 8th envelope, the four-way `claim_id` collision listed as one), and
  audited its own untracked working-tree files as if they were repo state.
  Keep single-agent audits as smoke signals; confirm each claim against
  source before acting.
- Status: INFO — verifier hygiene

## Live tooling pointers

These owners are authoritative and live. The corral does not copy them.

- [`docs/state/BROKEN_REGISTER.md`](../state/BROKEN_REGISTER.md) — append-only ledger of what is broken today (BR-NNN).
- [`INTERFACE_MISMATCH_MAP.md`](../../INTERFACE_MISMATCH_MAP.md) — declared-vs-actual interface gap log.
- [`docs/governance/REPO_GOVERNANCE_AUDIT.md`](../governance/REPO_GOVERNANCE_AUDIT.md) — canonical contradictions and staleness audit.
- [`docs/architecture/VERIFICATION_LANE.md`](../architecture/VERIFICATION_LANE.md) — the live verification lane (`scripts/verification_lane.py`).

## Superseded / archived sources

- `reports/dashboard/DASHBOARD_WIRING_AUDIT_2026-03-19.md` (2026-03-19):
  earlier dashboard wiring baseline. Endpoints mostly returned `200`; the
  Claude lane reported "logged in but capped" as healthy until
  availability metadata (`available`, `availability_kind`, `status_note`)
  was added. GraphQL `connection_graph` and semantic `search` were stubbed
  (`api/routers/graphql_router.py`); `fetchTask()` filtered task lists
  client-side for lack of a `GET /api/commands/tasks/{id}` endpoint;
  `ErrorBanner.tsx` checked only `/api/health`. Mostly superseded by
  TV-07; retained for the historical baseline and the still-open
  task-by-id and provider-degradation recommendations.
