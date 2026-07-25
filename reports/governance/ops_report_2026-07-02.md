# Dharma Swarm Governance Ops — 2026-07-02

**Report-only artifact — no source code changes. Operator holds sole merge authority.**

---

## Mission 1: Spine Adoption Tracking

| Metric | Value |
|--------|-------|
| Adoption % | **93.8%** (target: 95%) |
| Joined | 12 / 16 (75.0%) |
| Adapter-ready | 3 / 16 |
| Legacy | 1 / 16 |
| Missing | 0 / 16 |
| Quarantine | 0 / 16 |
| Total surfaces | 16 |

**Delta from committed version:** Unchanged (93.8% → 93.8%) — JSON not re-committed per policy.

### Surfaces by status

| Status | Surface ID | Label | Priority |
|--------|-----------|-------|----------|
| joined | identity_contract | Canonical ExecutionIdentity contract | 1 |
| joined | runtime_state_ledger | RuntimeStateStore durable ledger | 1 |
| joined | runtime_lifecycle_adapter | Runtime lifecycle adapter | 2 |
| joined | task_board_ingress | TaskBoard local ingress | 2 |
| joined | orchestrator_dispatch | Orchestrator dispatch path | 3 |
| joined | message_bus_transport | MessageBus internal event transport | 3 |
| joined | a2a_server_ingress | A2A task ingress | 4 |
| joined | artifact_store | Runtime artifact store | 4 |
| joined | ontology_action_tollbooth | Ontology typed action tollbooth | 5 |
| joined | workflow_checkpoint_replay | Workflow/checkpoint/replay path | 6 |
| joined | nats_jetstream_transport | NATS/JetStream event transport | 8 |
| joined | opportunity_refill_research_backend | Opportunity refill research backend | 9 |
| adapter-ready | tool_registry_dispatch | ToolRegistry side-effect dispatch | 5 |
| adapter-ready | self_modification_loop | Self-modification propose/gate/apply/verify loop | 6 |
| adapter-ready | mcp_tool_access | MCP/tool access boundary | 7 |
| legacy | legacy_no_identity_escape_hatch | Legacy no-identity escape hatch | 10 |

### Gap to 95% target

95% of 16 surfaces requires **≥15.2** joined-or-adapter-ready.  
Current: **15** (12 joined + 3 adapter-ready) — **1.2 surfaces below the 95% line.**

Graduating **one** of the two single-pattern adapter-ready surfaces closes the gap:

1. **`tool_registry_dispatch`** (`dharma_swarm/tool_registry.py`) — 1 missing pattern  
   → Add `try_begin_idempotent_side_effect` gating on tool dispatch side-effects

2. **`self_modification_loop`** (`dharma_swarm/diff_applier.py`) — 1 missing pattern  
   → Add `try_begin_idempotent_side_effect` on the apply path

3. **`mcp_tool_access`** (`dharma_swarm/mcp_server.py`, `dharma_swarm/dharma_context_mcp.py`) — 3 missing patterns (highest effort)  
   → Requires: `ExecutionIdentity` import, `RuntimeStateStore` wiring, `record_side_effect` receipts

Spine comment posted on most recent open spine PR → [#744 comment](https://github.com/AmitabhainArunachala/dharma_swarm/pull/744#issuecomment-4861004593)

---

## Mission 2: PR Lifecycle

| Category | Count |
|----------|-------|
| Total open **before** | 13 |
| Auto-closed (CONFLICTING ≥ 7 days) | **0** |
| Total open **after** | 13 |
| MERGEABLE (green-and-ready) | 8 |
| CONFLICTING | 5 |
| Duplicate auto-grounding PRs flagged | 0 |

### CONFLICTING PRs — monitoring (all < 7 days old)

| PR | Title | Age (hrs) | Auto-close eligible |
|----|-------|-----------|---------------------|
| #704 | Pudgala Autopoiesis Protostar: graded evidence gate | ~144.3h (6.01d) | **2026-07-02T23:43Z** ← today! |
| #719 | feat(sis): SEED-1 — carbon-attribution projector | ~87.8h (3.66d) | 2026-07-05T08:10Z |
| #723 | routing: canonicalize Forge benchmark lanes | ~55.4h (2.31d) | 2026-07-06T16:35Z |
| #732 | feat: persist LangGraph topology runtime state | ~31.4h (1.31d) | 2026-07-07T16:37Z |
| #734 | feat(forge): add offline production contract harness | ~25.7h (1.07d) | 2026-07-07T22:16Z |

**⚠️ Action required:** PR #704 crosses the 7-day auto-close threshold at approximately **2026-07-02T23:43Z** (tonight). If still CONFLICTING at next ops run, it will be auto-closed.

### Green-and-ready PRs (MERGEABLE)

| PR | Title | Files | +/- |
|----|-------|-------|-----|
| #747 | chore(governance): ops report 2026-07-01 | 1 | +124/−0 |
| #746 | docs: declare LangGraph runtime production candidate | 148 | +31586/−373 |
| #744 | [codex] port always-on A2A NATS spine evidence | 38 | +9354/−256 |
| #742 | spike: DharmaVerifier-Ranker v0 scaffolding | 21 | +3077/−0 |
| #740 | Harden Cybernetic Ratchet Loop evidence gates | 53 | +17094/−2 |
| #738 | Agentic Design Patterns: coverage atlas (Slot 4) | 31 | +5749/−7 |
| #737 | [codex] add metabolization sweep ledger | 7 | +2236/−16 |
| #736 | [codex] fix vector fallback scan guard | 3 | +95/−2 |

### Recommended actions

1. **PR #704** — rebase to resolve conflict or allow auto-close at next ops run (~tonight).
2. **PRs #719, #723, #732, #734** — rebase before their respective auto-close windows.
3. **Green PRs** — 8 PRs are MERGEABLE at operator discretion; #744 (spine evidence) directly advances adoption toward 95%.

---

_Generated: 2026-07-02T00:00Z_  
_Operator holds sole merge authority. No source code was modified._
