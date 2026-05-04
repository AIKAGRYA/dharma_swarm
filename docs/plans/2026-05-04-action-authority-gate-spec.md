# Action Authority Gate Spec

**Date:** 2026-05-04
**Status:** proposed execution spec
**Subordinate to:** `CLAUDE.md`, `docs/governance/SOVEREIGN_MANIFEST.md`, `docs/governance/BUILD_SESSION_ENTRYPOINT.md`, and `docs/governance/CANONICAL_DOC_STACK.md`
**Replaces:** no canonical document

This spec defines the smallest load-bearing runtime gate that turns high-authority agent action from an informal judgment into a typed, witnessed, ontology-native decision.

The user-facing contract remains the **Fourfold Action Warrant**. The runtime enforcement facade is `ActionAuthorityGate`. That split matters:

- `FourfoldActionWarrant` answers: "Has this action earned authority through vision, force, harmony, and precision?"
- `ActionAuthorityGate` answers: "May this concrete actor perform this concrete action on this concrete surface now?"

Do not create a new ledger, bridge, router, memory store, dashboard authority surface, or parallel governance substrate for this. Wire existing pieces.

## Evidence Pass

This spec was built from:

- Five parallel read-only agent reviews:
  - runtime execution surface map
  - governance substrate map
  - ontology and audit writeback map
  - integration and rollout map
  - failure-mode and acceptance-test map
- Local `rg` searches across the clean worktree and neighboring worktrees.
- GitNexus CLI reads against indexed repo snapshots. The fresh worktree itself was not indexed, and `gitnexus analyze` was not run because that writes state. Existing indexed snapshots showed `ActionEnvelope` and `RuntimeBridge` are mostly latent, while `TelicSeam` exposes the proposal/gate/lease/outcome method family.
- ContextPlus was attempted with semantic search for action authority and runtime enforcement. The query timed out after 120 seconds. This is itself a design signal: external semantic tools are evidence channels, not runtime dependencies.
- Memory MCP search for related prior observations returned no direct graph entities for this exact gate name.

Tool status must be recorded in future warrants as evidence, not hidden. A high-authority warrant can say `contextplus_status=timeout` or `gitnexus_status=stale_index`, but it may not pretend the semantic evidence pass happened when it did not.

## Verdict

This is the strongest missing link in the repo if the question is:

"How does an autonomous or self-authoring agent earn the right to act?"

The repo already has many parts of the answer:

- `dharma_swarm/fourfold_action_warrant.py` defines a warrant contract and trigger detection.
- `dharma_swarm/policy_compiler.py` can enforce that warrant behind `enforce_fourfold_warrant=True` and `DHARMA_FOURFOLD_ACTION_WARRANT_GATE`.
- `dharma_swarm/telos_gates.py` has Telos gatekeeping and reflective reroute.
- `dharma_swarm/semantic_governance.py` has `ActionEnvelope` and semantic governance verdicts.
- `dharma_swarm/runtime_bridge.py` normalizes actions but is mostly used by tests.
- `dharma_swarm/telic_seam.py` records `ActionProposal`, `GateDecisionRecord`, `ExecutionLease`, and `Outcome`.
- `dharma_swarm/guardrails.py` can run input, output, and tool guardrails.
- PTR v0, when present, is a shadow-only cybernetic readiness metric. It is negative evidence only.

The missing link is a single authority funnel at the moment of action. Without it, the repo can talk about governance while writes, shell commands, cron jobs, API tools, world actions, and self-modification paths bypass the governance substrate.

## Non-Goals

Do not use this spec to:

- replace `FourfoldActionWarrant`
- replace `TelosGatekeeper`
- replace `SemanticGovernanceKernel`
- replace `GuardrailRunner`
- invent a new ontology store or event ledger
- make dashboard/API views authoritative
- make `ShaktiZeitgeistExecutive` dispatch-capable
- hard-block all read-only work
- require 50-file recursive reads for trivial actions
- import dirty or off-main code blindly

Dirty worktree prototypes such as `dharma_swarm/shakti_warrant.py` can be mined for ideas. They are not canonical until merged cleanly.

## Existing Substrate Map

| Substrate | Keep | Current gap | How AAG uses it |
| --- | --- | --- | --- |
| `FourfoldActionWarrant` | Warrant object and trigger logic | Not a hot-path runtime funnel | Required evidence object for high-authority actions |
| `PolicyCompiler` | Warrant enforcement semantics | Optional and not wired at execution surfaces | Component evaluator |
| `TelosGatekeeper` | Dharmic decision and reflective reroute | Mostly text/pattern based; not enough action metadata | Component evaluator |
| `SemanticGovernanceKernel` | Runtime-neutral `ActionEnvelope` verdicts | Mostly latent outside tests | Semantic evaluator for action claims and contradictions |
| `GuardrailRunner` | Phase/tool guardrail runner | Not authoritative, not always pre-tool | Component evaluator |
| `TelicSeam` | Existing ontology writeback path | Best-effort; one-to-one gate link needs aggregate record | Persistence target for proposal, decision, lease, outcome |
| `OntologyActionGateway` | Fail-closed semantics from off-main work | Not present on current main | Prior art for later ontology mutation execution |
| `ShaktiZeitgeistExecutive` | Read-only signal seam | Explicitly no dispatch authority | Evidence source only |
| PTR | Cybernetic readiness signal | Shadow-only; not a permission source | Negative evidence input only |
| GitNexus | Code graph context | Fresh worktree can be unindexed; index may be stale | Evidence source and status field |
| ContextPlus | Semantic search | Can timeout under large repo queries | Evidence source and status field |

## Naming

Use these names:

- User and docs: **Fourfold Action Warrant**
- Code facade: `ActionAuthorityGate`
- Request object: `ActionAuthorityRequest`
- Result object: `ActionAuthorityDecision`
- Evidence object: `AuthorityEvidence`

Avoid `ActionAuthorityCase` unless the ontology later creates a durable case-management object. The current ontology already has `ActionProposal`, `GateDecisionRecord`, `ExecutionLease`, and `Outcome`; adding "case" would imply a new lifecycle object that is not needed yet.

## Modes

`ActionAuthorityGate` has three modes:

| Mode | Runtime effect | Persistence |
| --- | --- | --- |
| `off` | No gate evaluation | No new gate record |
| `shadow` | Never blocks execution | Records raw decision, effective allow, would-block flag |
| `enforce` | Blocks high-authority missing/invalid/non-allowing actions | Records raw decision, effective decision, blocked flag |

Default mode is `off` until the first implementation lands. First rollout mode is `shadow`.

Fail policy:

- Read-only actions default allow unless another gate blocks them.
- High-authority side effects in `shadow` fail open with a would-block record.
- High-authority side effects in `enforce` fail closed on missing warrant, invalid warrant, stale warrant, missing capability snapshot, or missing trigger binding.
- Tool evidence providers failing does not automatically block in `shadow`; their failure is recorded.
- Tool evidence providers failing in `enforce` blocks only when the action class requires that evidence provider.
- PTR evidence may lower confidence, require review, or contribute a block reason. It must never create an allow decision, raise autonomy, bypass Telos, bypass PolicyCompiler, or imply operator consent.

## Authority Tiers

Classify every request into one tier:

| Tier | Examples | Warrant required |
| --- | --- | --- |
| `read_only` | Read file, inspect logs, collect status | No |
| `local_side_effect` | Temp file write, local cache update | Usually no; maybe shadow |
| `repo_mutation` | Write/edit files, apply diff, format tracked code | Yes for meaningful changes |
| `execution` | Shell, sandbox command, subprocess, code execution | Yes when nontrivial or external effect possible |
| `external_side_effect` | GitHub issue/PR/push, publish, network write | Yes |
| `cross_agent_dispatch` | Spawn worker, assign task, delegate authority | Yes |
| `governance_mutation` | Policy, telos, ontology, hook, CI, budget, release rules | Yes |
| `release_or_main` | Merge to main, push release, deployment | Yes and enforce |

## Authority Surfaces

The first implementation must normalize these surfaces even if only a subset is wired in PR 1:

1. `dispatch`: `Orchestrator._assign_dispatch`
2. `agent_tool`: `AgentRunner._execute_local_tool`
3. `autonomous_tool`: `AutonomousAgent._execute_tool` and world-action wrappers
4. `tool_registry`: `ToolRegistry.dispatch`
5. `api_tool`: chat/API tool execution, spawn, workflow, ontology action endpoints
6. `cron_daemon`: cron runner, launchd runner, pulse, gateway jobs
7. `sandbox_runtime`: `LocalSandboxProviderAdapter.execute`, Docker sandbox, subprocess providers
8. `ontology_action`: `OntologyRegistry.execute_action` and API execute-action path
9. `diff_self_improve`: `DiffApplier.apply`, evolution, self-improve, DGC auto paths
10. `external_bridge`: MCP, A2A, roaming daemon, external agent bridge
11. `operator_ui`: TUI and dashboard commands that trigger actions

The gate should not live separately in all of these files. It should be a small shared facade that each surface calls.

## Request Contract

`ActionAuthorityRequest` should be a Pydantic model or frozen dataclass with this shape:

```python
class ActionAuthorityRequest:
    action_id: str
    actor_id: str
    actor_type: str
    runtime_type: str
    task_id: str | None
    surface: AuthoritySurface
    tier: AuthorityTier
    action_type: str
    title: str
    intent: str
    content: str
    target_paths: tuple[str, ...]
    requested_tools: tuple[str, ...]
    command: str | None
    network_targets: tuple[str, ...]
    autonomy_level: str | None
    trust_mode: str | None
    think_phase: str | None
    spec_ref: str | None
    requirement_refs: tuple[str, ...]
    metadata: Mapping[str, object]
    evidence: tuple[AuthorityEvidence, ...]
    capability_snapshot: CapabilitySnapshot
    fourfold_warrant: FourfoldActionWarrant | None
    provenance: Mapping[str, object]
    created_at: datetime
```

Minimum metadata keys:

- `authority_surface`
- `authority_tier`
- `authority_mode`
- `authority_trigger_reasons`
- `authority_gate_version`
- `fourfold_warrant_id`
- `gitnexus_status`
- `contextplus_status`
- `skills_status`
- `mcp_status`
- `hooks_status`
- `worktree_status`

## Evidence Contract

`AuthorityEvidence` should support file, test, graph, semantic, runtime, tool, hook, and human evidence:

```python
class AuthorityEvidence:
    source: str
    kind: str
    summary: str
    paths: tuple[str, ...]
    category: str
    theme: str
    why_it_matters: str
    confidence: float
    metadata: Mapping[str, object]
```

For governance mutations, release/main actions, and self-modification, the warrant must include a `capability_snapshot`:

- available skills
- available MCP connectors
- available plugins
- active hooks
- current branch
- dirty worktree summary
- current index/source status for GitNexus
- current query status for ContextPlus
- relevant tests or verification commands
- PTR score status when available: verdict, authoritative flag, confidence, caps, and evidence freshness. Missing PTR remains review pressure only; it is not a hard dependency in PR 1.

PTR is not part of the positive authority path. A healthy PTR score can strengthen the evidence story but cannot grant authority. A stale, low-coverage, missing, or negative PTR score can only lower confidence or push the decision toward `review` or `block`.

## The 50-File Rule

The user's "50 files before action" instinct is directionally right for high-authority changes, but it must not be a universal tax on every decision.

Use this rule:

- `governance_mutation`, `release_or_main`, and `diff_self_improve` actions require a deep-read warrant.
- A deep-read warrant must cite at least 50 meaningful file observations across categories, unless the action proves a narrower bounded scope.
- File count alone is not sufficient. The warrant must group the observations into themes and explain the architecture in three dense paragraphs:
  1. vision: what larger pattern this action serves
  2. connection: which substrates and bypasses it touches
  3. execution: why this action is the right next move now
- The warrant must include root/governance docs, code surfaces, tests, tool/plugin/hook state, and GitNexus/ContextPlus status.
- Runtime hot paths may use cached or precomputed evidence packets. They should not block normal operation on a live 50-file read.

This keeps Mahasaraswati real without turning every HOLD into a token sink.

## Decision Contract

`ActionAuthorityDecision`:

```python
class ActionAuthorityDecision:
    decision_id: str
    action_id: str
    proposal_id: str | None
    mode: ActionAuthorityMode
    raw_decision: Literal["allow", "review", "block"]
    effective_decision: Literal["allow", "review", "block"]
    would_block: bool
    blocked: bool
    reason: str
    component_results: Mapping[str, object]
    gate_results: Mapping[str, object]
    guardrail_results: Mapping[str, object]
    trigger_reasons: tuple[str, ...]
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    warrant_id: str | None
    semantic_verdict: Mapping[str, object] | None
    policy_decision: Mapping[str, object] | None
    witness_reroutes: tuple[Mapping[str, object], ...]
    duration_ms: int
    provenance: Mapping[str, object]
    created_at: datetime
```

Decision vocabulary is only `allow`, `review`, `block`. Map legacy `warn` and `hold` into `review`.

## Gate Algorithm

For every wired surface:

1. Normalize the action into `ActionAuthorityRequest`.
2. Classify `surface` and `tier`.
3. Compute `trigger_reasons` with the existing Fourfold trigger logic.
4. Attach tool, MCP, skill, hook, git, and worktree status.
5. If high-authority, require a `FourfoldActionWarrant`.
6. Evaluate Fourfold warrant through `PolicyCompiler` semantics.
7. Evaluate Telos through `TelosGatekeeper` or `check_with_reflective_reroute`.
8. Evaluate Semantic Governance through an `ActionEnvelope`.
9. Evaluate applicable `GuardrailRunner` tool/input checks.
10. Read PTR only as optional negative evidence when an artifact is available.
11. Aggregate component results into raw decision.
12. Convert raw decision to effective decision according to mode.
13. Persist authority result through `TelicSeam.record_gate_decision` when a proposal exists.
14. Create or permit an `ExecutionLease` only for effective allow.
15. Execute action.
16. Record outcome through existing outcome paths.

The aggregate result should appear in `gate_results` as:

```python
"ACTION_AUTHORITY": {
    "result": "PASS" | "WARN" | "FAIL",
    "reason": "...",
    "mode": "shadow" | "enforce",
    "raw_decision": "allow" | "review" | "block",
    "effective_decision": "allow" | "review" | "block",
}
```

## Telic Persistence

Do not create `ActionAuthorityCase` as a new ontology object in PR 1.

Use existing lifecycle objects:

- `ActionProposal`
- `GateDecisionRecord`
- `ExecutionLease`
- `Outcome`

Add these properties to the authority gate section of `GateDecisionRecord.properties`:

- `authority_gate_name`
- `authority_gate_mode`
- `authority_gate_raw_decision`
- `authority_gate_effective_decision`
- `authority_gate_would_block`
- `authority_gate_blocked`
- `authority_gate_reason`
- `authority_gate_policy_version`
- `authority_gate_warrant_id`
- `authority_gate_evidence_refs`
- `authority_gate_evaluated_at`
- `authority_gate_trace_id`

Important preflight bug: current `orchestrator.py` calls `TelicSeam(registry=registry, registry_path=ontology_db)`, while `TelicSeam.__init__` accepts `path`, not `registry_path`. Because that exception is swallowed, live orchestrator ontology writeback may be disabled. Fixing that is a prerequisite before claiming AAG persistence is live in orchestrator dispatch.

## Rollout Order

### PR 1: Pure Model And Classifier

Files:

- `dharma_swarm/action_authority/` or another existing subpackage, not a new flat top-level module if avoidable.
- focused tests under `tests/`.

Deliver:

- request/decision/evidence models
- tier/surface classifier
- trigger binding to `trigger_reasons_for_action`
- mode handling
- no runtime behavior change

Tests:

- default off
- read-only classification
- repo mutation classification
- governance mutation classification
- missing high-authority warrant would block in shadow
- complete high-authority warrant allows
- invalid/stale/non-allowing warrant blocks in enforce

### PR 2: Telic Dispatch Shadow

Files:

- `dharma_swarm/orchestrator.py`
- `dharma_swarm/telic_seam.py` only if needed for metadata shape
- tests for orchestrator ontology writeback

Deliver:

- fix the `registry_path`/`path` constructor mismatch
- call AAG from `_assign_dispatch`
- record `ACTION_AUTHORITY` inside `GateDecisionRecord`
- do not block dispatch yet

Tests:

- dispatch writes `ActionProposal`
- dispatch writes gate decision with authority payload
- shadow mode raw block still effective allow
- no duplicate proposal/gate objects

### PR 3: Agent Tool Shadow

Files:

- `dharma_swarm/agent_runner.py`
- tests around local tool execution

Deliver:

- call AAG before `write_file`, `edit_file`, `shell_exec`/`bash`, network fetch/search, and other side-effect tools
- attach resolved path, command, workdir, requested tool, autonomy level
- record shadow decisions without blocking normal tests

Tests:

- read file does not require warrant
- write/edit classified as repo mutation
- shell classified as execution
- destructive shell would block in shadow
- metadata includes target paths and command summary

### PR 4: Tool Registry, API, And Autonomous World Actions

Files:

- `dharma_swarm/tool_registry.py`
- `dharma_swarm/autonomous_agent.py`
- `dharma_swarm/world_actions.py`
- API/chat tool execution surfaces

Deliver:

- universal fallback at `ToolRegistry.dispatch`
- autonomous side-effect tools use AAG, not ad hoc fail-open side-effect checks
- GitHub/world/subswarm actions are high-authority by default
- API surfaces call the same gate and remain projection/command surfaces, not authority stores

Tests:

- autonomous gate exception does not silently allow high-authority action in enforce mode
- GitHub PR/push/world actions require warrant
- API ontology action cannot bypass AAG when enforce mode is active
- dashboard/API does not persist authority decisions outside ontology path

### PR 5: Cron, Sandbox, Diff, And External Bridges

Files:

- cron runner/daemon paths
- sandbox/runtime contract adapters
- diff/self-improve/evolution paths
- MCP/A2A/roaming bridge paths

Deliver:

- pre-execution AAG for scheduled jobs and subprocess execution
- runtime events carry `decision_id` and `warrant_id`
- diff apply and self-improvement require warrant in enforce mode
- external bridge dispatches cannot inherit authority automatically

Tests:

- cron job execution records authority decision
- sandbox execution classified with command/workdir metadata
- diff apply missing warrant blocks in enforce
- external agent remains evidence-only unless explicitly authorized

### PR 6: Enforce Narrowly

Do not turn on global enforcement. Start with:

- release/main actions
- governance mutations
- self-modifying diff apply
- external side effects
- cross-agent dispatch from untrusted or external actors

Success means low false positives and visible would-block data, not maximum blocking.

## Acceptance Matrix

The full spec is accepted only when tests prove:

- AAG is disabled by default.
- Shadow mode never blocks but records raw/effective decision.
- Enforce mode blocks missing/invalid/stale/non-allowing warrants for high-authority actions.
- Read-only actions do not require warrants.
- `trigger_reasons` are bound to the attached warrant.
- GitNexus and ContextPlus status fields are present on high-authority warrants.
- Capability snapshot includes skills, MCP connectors, plugins, hooks, branch, and dirty status.
- PTR is represented only as negative evidence: it cannot produce allow, cannot raise autonomy, cannot bypass Telos or PolicyCompiler, and cannot infer operator consent.
- `ShaktiZeitgeistExecutive` remains read-only and `dispatch_authority` remains false.
- Dispatch writes one `ActionProposal` and one aggregate `GateDecisionRecord`.
- `ExecutionLease` is created only after effective allow.
- `AgentRunner._execute_local_tool` cannot write/edit/shell in enforce mode without authority.
- API/chat/world action paths cannot bypass the same gate.
- Cron and sandbox execution carry decision metadata.
- Diff/self-improvement paths fail closed in enforce mode.
- No new ledger, router, bridge, memory store, or dashboard authority table is introduced.
- `git diff --check`, focused tests, policy compiler tests, Fourfold tests, TelicSeam tests, AgentRunner tests, and runtime contract tests are green.

## Conflict Risks

Likely conflict zones:

- off-main `OntologyActionGateway` work
- dirty/untracked `shakti_warrant` prototype
- memory-tail/governance-truth branches touching ontology/action paths
- API/dashboard WIP that may try to become authority-bearing
- TelicSeam constructor mismatch fix if another branch already repaired it

Integration order:

1. Land this spec only.
2. Land model/classifier with no hot-path behavior change.
3. Fix TelicSeam constructor/writeback proof.
4. Wire dispatch in shadow.
5. Wire AgentRunner local tools in shadow.
6. Wire autonomous/API/tool-registry/world actions in shadow.
7. Wire cron/sandbox/diff/external bridges in shadow.
8. Enable narrow enforcement only after would-block data is reviewed.

## Three-Paragraph Warrant Standard

Every high-authority warrant must end with three paragraphs, not bullet mush:

1. **Vision:** state the larger living pattern the action serves and why this action belongs to the current build track.
2. **Connection:** name the exact substrates, bypasses, tests, hooks, tools, and worktree state that make the action safe or unsafe.
3. **Execution:** explain why the proposed move is the right next move now, including the smallest rollback or stop condition.

Those paragraphs are not decoration. They are the compression step that proves the agent has integrated the evidence instead of merely collecting it.

## Implementation Principle

The repo does not need another impressive governance phrase. It needs a tiny gate at the side-effect point that records why an agent had authority to act, blocks only where the risk justifies it, and writes the answer into the existing ontology lifecycle.
