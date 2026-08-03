---
title: PersistentAgentDescriptor
date: 2026-08-01
status: proposal
---

# PersistentAgentDescriptor

> ## ⚠️ DRAFT — companion report failed adversarial verification (2026-08-01)
>
> This schema is derived from `docs/reports/hermes_persistent_agent_index_2026-08-01.md`,
> which carries an errata block: its surface inventory is incomplete (it misses
> `browser_agent.py`, `synthesis_agent.py`, `sleep_time_agent.py`, the 2,312-line cron
> subsystem, `garden_daemon.py`, and a sixth registry at `docs/ops/FLEET_FIELD_REGISTRY.yaml`).
>
> The FIELD SET below is not invalidated by that — it is a schema, not an inventory —
> but any "which surface supplies this today" annotation must be re-derived once the
> index is corrected. Treat the `UNSOURCED` markings as provisional.


The smallest schema that would make every persistent agent surface in
dharma_swarm discoverable and callable through one control plane.

This is a **proposal**, not a description of enforcement. Nothing in the repo
reads this schema today. Its value is the third column of the field tables: for
each field, the repo surface that already supplies the value, or `UNSOURCED`
when nothing does. **The `UNSOURCED` rows are the build backlog.** The
`CONFLICTING` rows are worse than unsourced — several surfaces supply the field
and they disagree, so a loader must pick a winner and demote the rest.

Current terminology/navigation: [`../SARATHI.md`](../SARATHI.md). Companion
inventory: [`hermes_persistent_agent_index_2026-08-01.md`](../reports/hermes_persistent_agent_index_2026-08-01.md).
Dated body reference: [`HOLON_RUNTIME_FULL_ESTATE_MAP.md`](HOLON_RUNTIME_FULL_ESTATE_MAP.md).

## Design constraints

1. **Compose, do not add.** `HOLON_RUNTIME_FULL_ESTATE_MAP.md:708-710` forbids
   creating another registry, provider router, task store, or receipt spine.
   This descriptor is a *projection contract* over existing owners, not a new
   store. A loader must derive fields from the surfaces named below.
2. **A2A 1.0 compatibility is a near-term constraint**
   (`docs/agent_tasks/hermes_full_persistent_agent_index_2026-05-28.md:196`).
   Field names that have an A2A `AgentCard` equivalent keep the A2A semantics.
3. **Declared is not proven.** Every field is either *declared* (an operator or
   a manifest asserts it) or *observed* (a runtime surface computed it).
   Mixing the two is the failure mode that produced
   `AuthorityPassport.telos_decision` defaulting to `"allow"`
   (`dharma_swarm/operator_core/living_agent_kernel.py:293`, populated verbatim
   from the untrusted wake payload at `:1473`). Every field below carries a
   `Kind` column for exactly this reason.
4. **Fail closed on absence.** A missing authority field must deny, not permit.
   `dharma_swarm/holon_budget_guard.py:30` is the counter-example to avoid:
   `cap_usd <= 0` means *unbounded*, so a default-constructed descriptor is
   unlimited rather than blocked.

## Schema (YAML form)

```yaml
# ---- identity -------------------------------------------------------------
id:                     str          # required, canonical AgentUID
name:                   str          # required, human display name
callsign:               str          # optional short alias
role:                   str          # required, from ONE role vocabulary
owner:                  str          # required, accountable human or track

# ---- execution ------------------------------------------------------------
provider_targets:       list[str]    # required, >=1
model_preferences:      list[str]    # ordered; ids must resolve in model_pool
skills:                 list[str]    # capability names
input_modes:            list[str]    # A2A defaultInputModes
output_modes:           list[str]    # A2A defaultOutputModes
working_directory:      str          # sandbox root
latency_class:          enum         # interactive | batch | background
cost_class:             enum         # free | cheap | metered | premium

# ---- addressing -----------------------------------------------------------
inbox_path:             str          # required, ONE canonical address
outbox_path:            str
a2a_card_path:          str
mcp_tools:              list[str]

# ---- state ----------------------------------------------------------------
memory_paths:           list[str]
evidence_path:          str          # required
lifecycle_state:        enum         # required, promotion ladder below
last_seen:              datetime     # observed only, never declared

# ---- authority (the half the repo is missing) -----------------------------
permissions:            object       # capability booleans
trust_level:            enum         # untrusted | evidence_only | supervised | trusted
authority_ceiling:      enum         # AutonomyLevel
reversibility_floor:    enum         # ActionClass ceiling this agent may reach
budget:                 object       # max_usd / max_model_calls / max_seconds
lease_ref:              str          # execution lease id when authority is held
routing_tags:           list[str]
```

## Field reference

`Kind` is `D` (declared by a manifest/operator) or `O` (observed from runtime).
`Req` is whether a loader must refuse a descriptor lacking the field.

### Identity

| Field | Type | Req | Kind | Supplying surface today |
| --- | --- | --- | --- | --- |
| `id` | `str` | yes | D | **CONFLICTING — 5 sources.** `examples/agents/*.registration.json:3` (`agent_uid`, 10 rows); `dharma_swarm/a2a/agent_presence.py:15-24` (`REGISTERED_AGENT_UIDS`, 8 rows); `docs/agents/*/agent.seed.yaml:2` (3 rows); `scripts/runtime/codex_composer_wake_loop.py:110-138` (`WAKE_PROFILES`, 3 rows); `inter_agent/<seat>/` (13 dirs, callsign-shaped). Verified drift: 2 roster-without-card, 4 card-without-roster (`python3 scripts/governance/a2a_agent_onboard.py --json`). |
| `name` | `str` | yes | D | `examples/agents/*.registration.json:5` (`display_name`); `dharma_swarm/a2a/agent_card.py:201` (`AgentCard.name`). |
| `callsign` | `str` | no | D | `examples/agents/*.registration.json:4`. Normalizer conflict: `dharma_swarm/holon_system/identity/canonical_names.py:6-8` maps `-`→`_` while `scripts/runtime/codex_composer_wake_loop.py:104-105` maps `_`→`-`. Applying the first to `devin-roaming-2987d222` yields `devin_roaming_2987d222`, which resolves nowhere. |
| `role` | `str` | yes | D | **CONFLICTING — 9 vocabularies.** `dharma_swarm/models.py:45-67` (`AgentRole`, 19, verified live); `dharma_swarm/skills/*.skill.md` (8, verified live); `dharma_swarm/daemon_config.py:149-179` (`ROLE_BRIEFINGS`, 5); `dharma_swarm/agent_constitution.py:120-286` (6, disjoint names); `dharma_swarm/intent_router.py:205-251` (9, adds `deployer`/`monitor` existing nowhere else); `dharma_swarm/a2a/agent_card.py:390-428` (9, private); `examples/agents/*.registration.json:9` (8 more); `dharma_swarm/ontology.py:1306-1313` (hand-copy of AgentRole); `dharma_swarm/context.py:1019-1080` (5 weight profiles). |
| `owner` | `str` | yes | D | `.github/CODEOWNERS:10` routes every path to one human. Track ownership in `docs/governance/ACTIVE_TRACK.yaml`. No per-agent owner field exists — **UNSOURCED at agent granularity.** |

### Execution

| Field | Type | Req | Kind | Supplying surface today |
| --- | --- | --- | --- | --- |
| `provider_targets` | `list[str]` | yes | D | `dharma_swarm/conductors.py:18-22` (import-time resolution); `examples/agents/*.registration.json:7` (`model_identity`); `~/.dharma/agents/<n>/identity.json` via `dharma_swarm/holon_bridge.py:152`; `dharma_swarm/model_hierarchy.py:242-262` (`DEFAULT_MODELS`). Partial and per-surface. |
| `model_preferences` | `list[str]` | no | D | `dharma_swarm/model_pool.py:240-243` (31 entries, verified live) is the declared "ONE model-grain source" (`:1`). But consolidation stopped at STEP 2 (`:22-24`); 13 of 20 `DEFAULT_MODELS` values have no pool entry, and 6 provider lanes are guard-exempt (`:319-333`). Only `dharma_swarm/tui/model_routing.py:3-9` is a true projection. |
| `skills` | `list[str]` | no | D | `dharma_swarm/skills.py:192` (`SkillRegistry.discover`, 8 verified live); `dharma_swarm/a2a/agent_card.py:159` (`AgentSkill`). **The persona body is dead**: `dharma_swarm/agent_runner.py:947-966` never imports `skills.py`; only metadata is projected. |
| `input_modes` | `list[str]` | no | D | `dharma_swarm/a2a/agent_card.py:177` — defaults `["text"]`. A2A-conformant. |
| `output_modes` | `list[str]` | no | D | `dharma_swarm/a2a/agent_card.py:178` — defaults `["text"]`. |
| `working_directory` | `str` | no | D | `examples/agents/*.registration.json` `workspace_policy.sandbox_root` (e.g. `~/.dharma/external_agents/kestrel`). Not honoured by any runner. |
| `latency_class` | enum | no | D | **UNSOURCED.** `grep -rn "latency_class" --include=*.py dharma_swarm/` returns zero. |
| `cost_class` | enum | no | D | **PARTIAL.** `dharma_swarm/model_pool.py` `ModelTier` and `below_floor` classify *models*, not agents. `grep -rn "cost_class"` returns zero. |

### Addressing

| Field | Type | Req | Kind | Supplying surface today |
| --- | --- | --- | --- | --- |
| `inbox_path` | `str` | yes | D | **CONFLICTING — 6 live address spaces.** (1) `roaming_mailbox/tasks/` (`dharma_swarm/roaming_mailbox.py:50`); (2) `~/.dharma/sarathi/mailbox/tasks/` (`scripts/runtime/sarathi_wake_daemon.py:237`); (3) `~/.dharma/a2a_bus/tasks/queue.jsonl` (`dharma_swarm/operator_core/a2a_task_lifecycle.py:67`); (4) `~/.dharma/a2a_bus/inboxes/<uid>/` (`scripts/runtime/a2a_inbox_bridge.py:101`); (5) NATS `dharma.a2a.<name>` compat; (6) NATS `dharma.agent.<uid>.inbox` canonical (`dharma_swarm/a2a/agent_card.py:85-86`). Registration cards pick among four schemes at `examples/agents/*.registration.json:14` and **no resolver dispatches on that field**. |
| `outbox_path` | `str` | no | D | `~/.dharma/a2a_bus/outboxes/<uid>/` (`scripts/runtime/a2a_domain_reply_worker.py:37`); `roaming_mailbox/responses/`. |
| `a2a_card_path` | `str` | no | D | `~/.dharma/a2a/cards/<callsign>.json` (`dharma_swarm/a2a/agent_card.py:489-493`). Absent on this host. Spelling drift: `docs/agents/cybernetics_codex/agent.seed.yaml:21` points at a hyphenated filename the uid would not produce. |
| `mcp_tools` | `list[str]` | no | D | **UNSOURCED for agents.** The only `mcp_tools` field in the repo is `dharma_swarm/fourfold_action_warrant.py:70` on `CapabilityInventory`, which is a warrant input, not an agent descriptor. |

### State

| Field | Type | Req | Kind | Supplying surface today |
| --- | --- | --- | --- | --- |
| `memory_paths` | `list[str]` | no | D | `dharma_swarm/holon_bridge.py:32` (`~/.dharma/agents`) **vs** `dharma_swarm/agent_registry.py:27,221` (`~/.dharma/ginko/agents`) — same on-disk schema, two roots, unreconciled; `holon_bridge.py:6-8` declares the second non-canonical. `dharma_swarm/autonomous_agent.py:422` (`AgentMemoryBank`). |
| `evidence_path` | `str` | yes | O | `dharma_swarm/holon_persistence.py:29` (`holon_events.jsonl`); `dharma_swarm/spine/receipt.py:155`; `dharma_swarm/operator_core/a2a_task_lifecycle.py` receipts; `reports/a2a/*_receipts/` — **gitignored** (`.gitignore:122`), so invisible from a fresh checkout. |
| `lifecycle_state` | enum | yes | O | **CONFLICTING.** `dharma_swarm/holon_runtime.py` statuses (`ran`, `halted:kill`, `halted:budget`, `halted:reversibility_gate`, `halted:error`, `halted:unverified`); `ACTIVE_SURFACE_MANIFEST.yaml:405-440` status strings; `docs/agents/*/agent.seed.yaml` (`shadow_registered`, `declared_not_started`); `examples/agents/*.registration.json` `status: registered`. Recommend the estate map's promotion ladder (`HOLON_RUNTIME_FULL_ESTATE_MAP.md:101-108`) instead: `IdentityPresent → DialogueProven → ProposalCycleProven → GovernedEffectProven → ReceiptBound → DurableServiceProven`. |
| `last_seen` | datetime | no | O | `~/.dharma/a2a_bus/bridge_heartbeats/<uid>.json` (`scripts/runtime/a2a_inbox_bridge.py`); `dharma_swarm/a2a/node_registry.py:340` (`_mark_stale`); `dharma_swarm/agent_runner.py:3323` (heartbeat freshness). **Must never be declared** — every current liveness signal is self-reported, and `scripts/runtime/merge_master_mike_daemon.py:279` names "treating tmux session existence as completion proof" as a forbidden inference. |

### Authority

This block is the reason the descriptor is worth building. The primitives all
exist and **have never been composed**.

| Field | Type | Req | Kind | Supplying surface today |
| --- | --- | --- | --- | --- |
| `permissions` | object | yes | D | `examples/agents/*.registration.json` `autonomy_policy` — 8 booleans (`can_write_source`, `can_approve_prs`, `can_mutate_telos`, …), verified on `kestrel.registration.json`. Nothing enforces them. Adjacent: `dharma_swarm/operator_core/permissions.py:24` `GovernancePolicy` (per-tool gating) — **not importable**: `python3 -c "from dharma_swarm.operator_core.permissions import GovernanceFilter"` → `ModuleNotFoundError: No module named 'textual'` via `permissions.py:13` → `dharma_swarm/tui/engine/__init__.py:25`. |
| `trust_level` | enum | yes | D | **PARTIAL / GitHub-only.** `scripts/runtime/pr_merge_control.py:1017-1021` `TRUSTED_REVIEW_LOGINS` maps two bot identities exactly. `dharma_swarm/operator_core/execution_lease.py:116` has `custody_grade` (default `Q1`). `grep -rn "trust_level" --include=*.py dharma_swarm/` returns zero. |
| `authority_ceiling` | enum | yes | D | `dharma_swarm/operator_core/autonomy_dial.py:36` `AutonomyLevel` (shadow/propose/dispatch/full), default `PROPOSE`, invalid→`SHADOW` (`:55`). **Process-global** via `DGC_SARATHI_AUTONOMY` (`:33`); the one per-call override seam is `delegate_all(level=...)` (`dharma_swarm/holon_system/sarathi/delegate.py:198`). |
| `reversibility_floor` | enum | yes | **D** | Declared per agent — the most dangerous `ActionClass` this agent may ever reach. It is **not** observed, and `load_descriptors()` must never call the classifier to populate it: `classify_action()` (`dharma_swarm/operator_core/reversibility_gate.py:237`) classifies *one concrete action string*, and at descriptor-load time no action exists. Sourcing it from the classifier would either fail every descriptor or freeze a stale class that later authorizes a different action. The classifier supplies the **action's** class at call time; the gate compares that against this declared floor. Vocabulary and enforcement come from `reversibility_gate.py:47` `ActionClass` (4 values) + `:63` `NEVER_AUTO_PATTERNS` (28 entries, both verified live) + `:118` `GateDecision`. Stdlib-only, deterministic, total. **The single best discriminant available.** Live probe of the call-time half: `classify_action("git push origin main")` → `operator_only`, `never_auto_hit='git push'`, `may_execute_unattended=False`. |
| `budget` | object | yes | D | `dharma_swarm/operator_core/execution_lease.py:161` (`max_seconds`/`max_model_calls`/`max_usd`); `dharma_swarm/holon_budget_guard.py:25` (`check_cost_cap`, the only halting USD primitive, **one importer repo-wide**). Fail-open hazard at `:30`. |
| `lease_ref` | `str` | no | O | **CONFLICTING — 4 lease vocabularies, zero conversions.** (a) file-backed dict, `dharma_swarm/operator_core/execution_lease.py:116` (`schema_version: dharma.execution_lease.v1`; there is **no `class ExecutionLease`** anywhere); (b) `WorkspaceLease` SQLite dataclass, `dharma_swarm/runtime_state.py:610`; (c) ontology `ExecutionLease` ObjectType, `dharma_swarm/ontology.py:1673`, written for provenance only by `dharma_swarm/telic_seam.py:199`; (d) live-mutation lease read by `dharma_swarm/evolution_safety_runtime.py:280`. |
| `routing_tags` | `list[str]` | no | D | `dharma_swarm/skills/*.skill.md` `tags:`/`keywords:` frontmatter; `dharma_swarm/intent_router.py:254-291` keyword table — duplicates the frontmatter with no shared source and already differs in membership. |

## Name collisions a loader must resolve first

Verified by import, not inferred:

| Name | Definition A | Definition B | Same object? |
| --- | --- | --- | --- |
| `GateDecision` | `dharma_swarm/models.py:95` — `str` Enum `allow`/`block`/`review` | `dharma_swarm/operator_core/reversibility_gate.py:118` — frozen dataclass carrying `ActionClass` | **No** |
| `EvidenceReceipt` | `dharma_swarm/spine/receipt.py:41` — OTel-aligned dispatch receipt | `dharma_swarm/operator_core/closure_v0.py:90` — deprecated alias for `ClosureEvidenceReceipt` | **No** |
| `RuntimeTruthState` / `RuntimeTruthPacket` | `dharma_swarm/operator_core/runtime_truth.py:25,130` | `dharma_swarm/operator_core/contracts.py:24,125` | No — aliased at `runtime_truth.py:22` |
| `GovernancePolicy` / `GovernanceFilter` | `dharma_swarm/operator_core/permissions.py:24,40` | `dharma_swarm/tui/engine/governance.py:25,47` | No — near-identical duplicates |

`tools/manifest_check.py:75-85` already enforces exactly-one canonical
`EvidenceReceipt` definition site and has been taught about the alias — extend
that mechanism to the other three rather than adding a new guard.

## Correlation identity

Three closure layers use two field names for one concept:

- `dharma_swarm/spine/receipt.py:46` — `trace_id`, exported as
  `dharma.correlation_id` in the OTel span (`:100`);
- `dharma_swarm/operator_core/a2a_task_lifecycle.py:102` — `correlation_id`;
- `dharma_swarm/operator_core/closure_v0.py:71` — `correlation_id`.

They are reconciled only by a comment at `spine/receipt.py:94-100`. A descriptor
must pick one name; `dharma_swarm/spine/identity.py:28` `ExecutionIdentity`
(`trace_id`/`correlation_id`/`task_id`/`run_id`) is the existing carrier and is
the right owner.

## The authority join that does not exist

`GateDecision.requires_execution_lease` is set and serialized at
`dharma_swarm/operator_core/reversibility_gate.py:129`, and **nothing ever looks
a lease up in response**. Verified: no file imports both
`dharma_swarm.operator_core.reversibility_gate` and
`dharma_swarm.operator_core.execution_lease`; and no file imports both
`dharma_swarm.telos_gates` and `reversibility_gate`
(`grep -rl "dharma_swarm.telos_gates" --include=*.py . | xargs grep -l "reversibility_gate"` → empty).

Closing that join is `Packet 1` of the estate map
(`HOLON_RUNTIME_FULL_ESTATE_MAP.md:646-658`) and is what the `authority` block
above exists to carry.

## Reference implementation targets

Two existing call sites are the templates to copy, not replace:

1. **Fail-closed execute step** —
   `api/chat_tool_execution.py:208` `_require_shell_gate_allow`: quarantines and
   raises on timeout, on any exception, on a malformed result, and on anything
   that is not explicitly `ALLOW` (`:242`). The strictest gate→effect binding in
   the repo.
2. **Floor-and-ceiling composition** —
   `dharma_swarm/holon_system/sarathi/delegate.py:218-253`: reversibility gate as
   floor (a `never_auto_hit` or gated `ActionClass` refuses at *every* dial
   level, `:225-234`), autonomy dial as ceiling (`:237,:249`). The doctrine is
   stated at `dharma_swarm/operator_core/autonomy_dial.py:6`.
