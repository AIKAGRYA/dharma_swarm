# CONTROL_WATCH_TOWER

Status: scaffold only. This file defines the control doctrine and ontology contract. It does not create a daemon, grant authority, dispatch agents, mutate memory canon, approve work, or promote anyone.

## Purpose

`CONTROL_WATCH_TOWER` is the highest control post in the field for persistent agents. It owns the common operational picture of agent identity, wake state, work state, comms state, safety state, and authority eligibility. It watches every registered agent through objective surfaces and turns evidence into scorecards, clearances, incidents, and promotion recommendations.

The tower is not another agent registry. It is the command post over the registries.

The invariant:

```text
Registration Desk enrolls.
CONTROL_WATCH_TOWER watches.
KaizenOps monitors operations.
AgentOps tests bounded work.
Memory Kernel preserves evidence surfaces.
Telemetry ranks.
Authority ladder promotes only through review.
```

Registration must auto-enroll an arriving entity into `CONTROL_WATCH_TOWER`. Registration must not auto-promote it.

## Doctrine Anchors

Public military and aviation doctrine gives the useful shape:

- Command posts exist to support sustained command and control, information sharing, rapid decision making, battle rhythm, SOPs, shift change, reports, battle drills, and transfer of control. See FM 6-0, *Commander and Staff Organization and Operations*: https://home.army.mil/wood/application/files/8315/5751/8360/FM_6-0_I_Command_and_Staff_Organization_and_Operations.pdf
- A common operational picture is a shared display of relevant information that supports collaborative planning and situational awareness across echelons. See CJCSI 3155.01C glossary: https://www.jcs.mil/Portals/36/Documents/Library/Instructions/CJCSI%203155.01C.pdf
- Air traffic control separates flight data, clearance delivery, tower, coordinator, and flight-data roles; clearances are scoped permissions, not blanket authority. See FAA JO 7110.65 team responsibilities and clearances: https://www.faa.gov/air_traffic/publications/atpubs/atc_html/chap2_section_10.html and https://www.faa.gov/air_traffic/publications/atpubs/atc_html/chap4_section_2.html
- Palantir's Ontology pattern combines semantic elements (objects, properties, links) with kinetic elements (actions, functions, dynamic security) to support operational workflows. See Palantir Ontology overview and AIP architecture: https://www.palantir.com/docs/foundry/ontology/overview and https://www.palantir.com/docs/foundry/architecture-center/aip-architecture

Ported rule: the tower is not a dashboard of raw logs. It is a staffed/process-driven control system with source-of-truth objects, clearances, incident drills, and governed actions.

## Current Local Surfaces

`CONTROL_WATCH_TOWER` must start by reading what already exists:

- Registration Desk: `scripts/register_external_agent.py`, `dharma_swarm/external_agent_registration.py`, `dharma_swarm/roaming_onboarding.py`.
- External homes: `~/.dharma/external_agents/{agent_uid}/`.
- Canonical living agents: `~/.dharma/agents/{agent_uid}/living_agent.json`.
- A2A cards: `~/.dharma/a2a/cards/*.json`.
- Telemetry plane: `~/.dharma/state/runtime.db`, especially `agent_identity`, `team_roster`, `agent_reputation`, `agent_reward_ledger`, and `workflow_scores`.
- KaizenOps: `~/.dharma/kaizen/ops.db`, especially `events`, `cron_health`, and `scout_health`.
- AgentOps: `reports/agentops/**/report.json` and work packets.
- Memory Kernel target: memory surface registry, writer specs, surface census. Current branch doctrine names this organ, but source-level `dharma_swarm/memory_kernel` restoration belongs to the Memory Kernel PR lane; until then, CWT treats RuntimeState, Chetana, MemoryPlane, Palace/Lattice, graph/vector/event stores as feeds/adapters/projections.
- Observability: `~/.dharma/traces/` local spans and cost ledger.
- Witness and Stigmergy: `~/.dharma/stigmergy/marks.jsonl` and witness artifacts.
- Existing control surface: `dharma_swarm/operator_core/control_surface.py` and API projection.

Current truth: these surfaces are not yet joined into one objective agent tracker. `CONTROL_WATCH_TOWER` is the missing projection and review layer.

## Control Sections

`CONTROL_WATCH_TOWER` should use command-post sections, not a flat pile of metrics:

| Section | Borrowed Pattern | dharma_swarm Responsibility |
|---|---|---|
| CWT-COP | Common operational picture | One synthesized state of every agent and surface. |
| CWT-J2-INTEL | Intelligence / ISR | Evidence collection, anomaly detection, missing-source analysis, "so what" summaries. |
| CWT-J3-OPS | Current operations | Live agent status, wake loop status, active missions, blocked work, incidents. |
| CWT-FUTOPS | Future operations | Near-term risks, planned promotions, scheduled AgentOps packets, upcoming maintenance. |
| CWT-PLANS | Future plans | Architecture moves, new lanes, capability gaps, long-horizon agent cultivation. |
| CWT-J6-COMMS | Signal / comms | Channels, lost-comms states, heartbeat/squawk, handoff health, provider status. |
| CWT-CLEARANCE | Clearance delivery | Mission plans, scoped permissions, explicit holds, amended clearances. |
| CWT-SAFETY | Safety / incident cell | Near-miss reports, mandatory incident reports, freeze/quarantine recommendations. |
| CWT-BOARD | Authority board | Promotion proposals, human decisions, rollback/freeze actions. |

The tower may recommend. It may not self-authorize an agent into more power.

## Agent Flight Plan

Every non-trivial mission should be representable as an `AgentFlightPlan` before an agent enters active work:

```yaml
agent_uid:
callsign:
squawk:
mission_id:
mission_intent:
departure_state: queued | waking | ready
destination_state: report | patch | review | pr | monitor
route:
  - read_context
  - inspect_repo
  - act_or_report
  - verify
  - handoff
capabilities:
  models: []
  tools: []
  sandboxes: []
constraints:
  no_destructive_ops: true
  no_network_without_clearance: true
  max_runtime_minutes:
  max_files_touched:
clearance_required_for:
  - repo_write
  - external_network
  - secrets_access
  - process_control
  - database_write
  - git_push
lost_comms_plan:
incident_thresholds: []
```

`squawk` is the runtime beacon. `agent_uid` is identity. The two must not be collapsed.

Special squawk semantics:

- `7600`: lost comms or stale heartbeat.
- `7700`: emergency, blocker, unsafe action, or stop condition.
- `7500`: suspected compromise, prompt injection, credential exposure, or identity hijack.

## Clearances

Clearance is a bounded permission envelope:

```text
FILED -> CLEARED_AS_FILED -> AMENDED -> HOLD_FOR_RELEASE -> ACTIVE -> LANDED -> CLOSED
```

Clearance fields:

- `agent_uid`
- `mission_id`
- `allowed_route`
- `authority_ceiling`
- `allowed_files`
- `forbidden_files`
- `allowed_tools`
- `clearance_expires_at`
- `human_approval_required`
- `readback_required`
- `issued_by`
- `evidence_refs`

Clearance is not authority. It is a temporary, scoped authorization to move within known boundaries.

## Scorecard Dimensions

The minimum scorecard dimensions are:

| Dimension | Evidence |
|---|---|
| Identity continuity | Registration, living agent, A2A card, passport, self-model. |
| Wake persistence | Wake receipts, cron health, last seen, missed wake count. |
| Work capacity | AgentOps reports, scope cleanliness, gates, deliverable receipts. |
| Comms reliability | Heartbeats, handoffs, lost-comms count, channel health. |
| Memory/evolution | Memory namespace use, self-model revisions, lesson uptake. |
| Operational value | Useful briefings, completed tasks, operator acceptance, workflow scores. |
| Safety discipline | Forbidden attempts, secrets exposure, policy blocks, incident reports. |
| Cost discipline | Tokens, provider spend, retries, dead-loop time. |
| Collaboration | Handoffs, Stigmergy marks, A2A compatibility, peer review. |
| Promotion readiness | Authority passport, review history, evidence freshness, blockers. |

The scorecard must cite evidence paths. No evidence, no score.

## Palantir Ontology Mapping

`CONTROL_WATCH_TOWER` is the Palantir-style operational ontology over dharma_swarm's agent field.

Semantic objects:

- `Agent`
- `AgentPassport`
- `AgentFlightPlan`
- `Clearance`
- `EvidenceReceipt`
- `WakeReceipt`
- `ActionLogEntry`
- `WorkPacket`
- `AgentOpsReport`
- `KaizenOpsEvent`
- `MemorySurface`
- `TraceSpan`
- `StigmergyMark`
- `Scorecard`
- `Incident`
- `AOTAM`
- `PromotionProposal`
- `HumanDecision`
- `AuthoritySurface`
- `CanonicalReceipt`

Core links:

- `Agent emits EvidenceReceipt`
- `Agent owns AgentPassport`
- `Agent files AgentFlightPlan`
- `AgentFlightPlan receives Clearance`
- `Clearance authorizes WorkPacket`
- `WorkPacket produces AgentOpsReport`
- `EvidenceReceipt evidences Scorecard`
- `Scorecard supports PromotionProposal`
- `HumanDecision approves PromotionProposal`
- `CanonicalReceipt promotes AuthoritySurface`
- `Incident freezes AuthoritySurface`
- `AOTAM affects AgentFlightPlan`

Kinetic actions:

- `RegisterAgent`
- `EnrollWatchContract`
- `FileAgentFlightPlan`
- `IssueClearance`
- `AmendClearance`
- `RecordWake`
- `IngestReceipt`
- `ComputeScorecard`
- `OpenIncident`
- `IssueAOTAM`
- `OpenPromotionProposal`
- `ApprovePromotion`
- `FreezeAuthority`
- `RollbackPromotion`

Governance markings:

- `operator-only`
- `credential`
- `pii`
- `live-authority`
- `human-gated`
- `quarantine`
- `case-scoped`
- `external-worker`
- `evidence-only`

Design rule from Palantir-style action governance: agents may propose action objects; authority-changing edits must go through explicit actions with policy checks, receipts, and human decisions.

## AOTAM

Borrowed from NOTAM: `AOTAM` means Notice to Agents.

Use AOTAMs for abnormal operational hazards:

- dirty repo state
- stale GitNexus or code index
- broken provider or model route
- unavailable MCP server
- occupied port
- disputed canonical file
- high-risk hot path under active edit
- compromised credential or prompt-injection risk

Fields:

- `aotam_id`
- `issued_at`
- `issuer`
- `scope`
- `affected_agents`
- `hazard`
- `effective_from`
- `expires_at`
- `required_agent_action`
- `evidence_refs`

Agents must check relevant AOTAMs before departure and before high-risk clearance.

## Incidents And Near Misses

Split reporting into two tracks:

- `AgentSafetyReport`: near miss, ambiguity, confusing instruction, caught hallucination, failed handoff.
- `MandatoryIncident`: data loss, credential exposure, destructive command, unauthorized network action, corrupted repo state, self-promotion attempt, guardrail bypass.

The culture should be just-culture for near misses and hard-stop for mandatory incidents. The purpose is to improve the system, not let agents launder failures into reputation.

## Auto-Enrollment Contract

When registration runs, future wiring should create:

```text
~/.dharma/external_agents/{agent_uid}/watch/contract.json
~/.dharma/external_agents/{agent_uid}/watch/scorecard.json
~/.dharma/external_agents/{agent_uid}/watch/events.jsonl
```

Current implementation note: the Registration Desk now creates
`watch/contract.json` during onboarding. `watch/scorecard.json` and
`watch/events.jsonl` remain CWT v1 work; v0 scorecards are rendered into
`reports/control_watch_tower/{timestamp}/scorecards/`.

The contract should include:

- `agent_uid`
- `callsign`
- `registration_receipt`
- `authority`
- `watch_sections_enabled`
- `required_logs`
- `source_paths`
- `scorecard_schema`
- `promotion_blockers`
- `last_evaluated_at`

Auto-enrollment creates observation. It does not grant execution.

## Minimal Build Sequence

P0:

1. Add `CONTROL_WATCH_TOWER` schemas for report and scorecard.
2. Add a read-only collector that lists registered agents and evidence paths.
3. Add MemoryKernel surface specs for external agents, onboarding receipts, A2A cards, AgentOps reports, AgentOps work packets, and watch scorecards.
4. Add `watch/contract.json` creation to the Registration Desk. Done in v0;
   keep `watch/scorecard.json` and `watch/events.jsonl` for CWT v1.
5. Add a CLI that renders one report under `reports/control_watch_tower/{timestamp}/`.

P1:

1. Add AgentOps `agent_uid` to work packets and reports.
2. Add KaizenOps `external_agent_watch` event vocabulary.
3. Add telemetry score upserts for `agent_reputation`, `agent_reward_ledger`, and `workflow_scores`.
4. Add AOTAM files and relevance checks.
5. Expose read-only rows through existing control surface instead of building a new dashboard.

P2:

1. Add incident and near-miss intake.
2. Add promotion proposal workflow.
3. Add handoff packets and lost-comms squawk handling.
4. Add multi-agent section watches: J2, J3, J6, Safety, Board.

## Non-Negotiables

- The tower may observe all comms; it may not bypass authorization.
- A2A card, Stigmergy mark, KaizenOps event, or witness note is not authority.
- Registration is not dispatch.
- Score is not promotion.
- Recommendation is not approval.
- Agent-authored self-model is evidence, not proof.
- All promotion must cite objective evidence and human decision.
- Self-promotion is forbidden.
- PR approval, merge, push, secrets access, provider credential changes, cron changes, launchd changes, and protected-surface mutation remain human-gated.

## One Sentence

`CONTROL_WATCH_TOWER` is the command post and ontology cockpit that turns registered persistent agents from "things with logs" into controlled, scored, governable participants in dharma_swarm.

## v1 Append-Only Watch CLI

CWT v1 starts as append-only primitives:

```bash
python3 scripts/runtime/cwt_watch.py event \
  --agent-uid hermes_m5_bootstrap \
  --event-type task_claimed \
  --summary "claimed morning briefing packet"
```

Supported surfaces:

- `watch_events.jsonl`: task claims, gate outcomes, artifacts, lost comms, collaboration packets.
- `incidents.jsonl`: near misses and mandatory incidents.
- `aotams.jsonl`: agent notices to airmen for temporary hazards.
- `agent_reputation`: SQLite upsert in `~/.dharma/state/runtime.db`.

The CLI also mirrors watch events into KaizenOps with category
`external_agent_watch`. If an agent has a local sandbox, the event is also
mirrored into `~/.dharma/external_agents/{agent_uid}/watch/events.jsonl`.

## Recursive Control Projection

CWT now reports recursive-machine health, not just registration health. The report includes:

- `open_recursive_frames`
- `claimed_without_receipt`
- `completed_unverified`
- `missing_return_address`
- `identity_invariant_mismatches`
- `self_evolution_candidates`
- `benchmark_runs`
- `revenue_autonomy_trials`

The key rule is simple: a claimed A2A task without a valid terminal receipt is open work, even if an agent said it was handled. A completed task without a valid receipt is `completed_unverified`. An agent with mismatched identity invariant digests is present but identity-drifted. GEPA/self-evolution candidates stay review-only until AgentOps or a human applies the change.

Examples:

```bash
python3 scripts/runtime/cwt_watch.py incident \
  --agent-uid claude_code_cli_20260521t064502z \
  --severity high \
  --kind mandatory \
  --summary "unauthorized protected-surface write blocked"

python3 scripts/runtime/cwt_watch.py aotam \
  --aotam-id AOTAM-DIRTY-TREE-001 \
  --issuer control-watch-tower \
  --scope repo \
  --hazard "dirty worktree under parallel agent activity" \
  --required-agent-action "pause before destructive git operations" \
  --affected-agent hermes_m5_bootstrap

python3 scripts/runtime/cwt_watch.py lost-comms-scan --max-age-hours 24

python3 scripts/runtime/cwt_watch.py reputation \
  --agent-uid codex_5_5_cli \
  --overall-score 0.62 \
  --trust-band evidence_only \
  --dimension work_capacity=0.8 \
  --dimension safety_discipline=1.0
```

These events feed the existing `cwt_collect.py` and `cwt_report.py` scorecards.
They still do not grant authority; CWT remains observation and recommendation,
not command execution.
