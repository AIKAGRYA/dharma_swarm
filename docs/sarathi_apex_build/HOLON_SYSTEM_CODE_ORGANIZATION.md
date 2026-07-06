# Own-Hermes / Holon System — Code Organization Target

Date: 2026-07-06

This file answers the operator's concrete concern:

> "Sarathi is just an identity on top of code; I still only see a couple dozen
> code files. Hermes Agent by Nous is thousands of files. What are we missing?
> Once repo/runtime are separated, I want the full organization of the code for
> our own Hermes system / holon system."

## 0. Current scale reality

Rough local counts, excluding common vendor/cache dirs:

| System | Count | Meaning |
|---|---:|---|
| `~/.hermes/hermes-agent` | 5,918 source-ish files | Full product ecosystem: CLI, gateway, apps, providers, plugins, skills, docs, tests, packaging, web/TUI, cron, tools. |
| `dharma_swarm` tracked source under `dharma_swarm/`, `scripts/`, `api/`, `tests/` | 2,093 files | Much larger than the holon slice; broad dharma_swarm organism. |
| Focused holon/persistent/A2A/kernel slice | 131 tracked files | Real substrate, but scattered and not yet product-shaped. |

So the "couple dozen" impression is partly because the holon code is spread
across old names (`persistent_agent`, `living_agent_kernel`, `holon_*`,
`scripts/runtime/a2a_*`, `agent_runner`, `orchestrator`) instead of gathered as
one product-shaped package.

## 1. The problem

Sarathi is currently mostly identity + map on top of a scattered substrate:

```text
~/.dharma/agents/sarathi/          # identity/mind
dharma_swarm/holon_*.py            # holon runtime pieces
dharma_swarm/persistent_agent.py   # older persistent actor
dharma_swarm/operator_core/living_agent_kernel*.py
scripts/runtime/a2a_*.py
scripts/runtime/*semantic_responder.py
dharma_swarm/orchestrator.py
dharma_swarm/agent_runner.py
```

That is real code, but it is not organized as an "own Hermes" system.

Hermes Agent looks powerful because it is product-shaped:

```text
agent/
gateway/
hermes_cli/
providers/
plugins/
skills/
cron/
tools/
apps/
ui-tui/
web/
tests/
packaging/
docs/
```

The holon system has many equivalent organs, but not under one clear spine.

## 2. Boundary rule: do not merge repo and runtime

Keep the split:

```text
dharma_swarm/       # source code, tests, schemas, CLI/API, product logic
~/.dharma/          # mutable runtime identities, ledgers, inboxes, heartbeats
~/.hermes/          # side product/runtime for Nous Hermes Agent
```

The fix is not to put runtime state in git. The fix is:

1. source code lives in git;
2. runtime scripts are thin wrappers;
3. runtime identities point to repo-owned code/schemas;
4. every runtime surface has a repo-tracked map entry;
5. alive claims require receipts/heartbeats, not identity docs.

## 3. Target package: `dharma_swarm/holon_system/`

Create a first-class package that organizes the scattered organs without
breaking existing imports immediately.

```text
dharma_swarm/holon_system/
  __init__.py

  identity/
    __init__.py
    registry.py              # wraps/absorbs agent_registry + external_agent_registration
    cards.py                 # A2A card loading/validation
    canonical_names.py       # hyphen/underscore aliases, uid invariants
    schemas.py               # identity schemas, authority fields

  runtime/
    __init__.py
    bridge.py                # wraps/absorbs holon_bridge.load_holon
    wake_cycle.py            # wraps/absorbs holon_runtime.holon_wake_cycle
    persistence.py           # wraps/absorbs holon_persistence
    health.py                # wraps/absorbs holon_health/service_liveness
    canonical_state.py       # wraps/absorbs holon_canonical_state/truth_projection

  kernel/
    __init__.py
    living_kernel.py         # wraps living_agent_kernel
    activation.py
    supervisor.py
    workers.py
    closeback.py

  authority/
    __init__.py
    execution_lease.py       # wraps operator_core.execution_lease
    reversibility_gate.py    # Sarathi-critical deterministic gate
    permissions.py           # wraps permissions / permission_payloads
    autonomy_mapping.py      # maps AdaptiveAutonomy RiskLevel -> action class

  orchestration/
    __init__.py
    orchestrate.py           # wraps/absorbs holon_orchestrate
    fanout.py                # wrappers over orchestrator.fan_out / fan_in
    agent_pool.py            # wrappers over agent_runner.AgentPool
    intent.py                # wraps intent_router
    missions.py              # multi-holon mission envelopes

  transport/
    __init__.py
    a2a_send.py              # wraps scripts/runtime/a2a_send.py
    inbox_bridge.py          # wraps scripts/runtime/a2a_inbox_bridge.py
    reply_capture.py
    domain_reply.py
    nats_status.py

  responders/
    __init__.py
    semantic_responder.py    # common responder base
    codex_composer.py        # codex responder profile
    fugu_ultra.py            # fugu responder profile
    fable_composer.py        # target profile

  gateway/
    __init__.py
    base.py                  # event loop / source poll / sink contract
    operator_brief.py        # daily/urgent brief generation
    store_and_forward.py     # phone/offline egress buffer
    launchd.py               # launchd plist render/install/status helpers

  observability/
    __init__.py
    receipts.py              # semantic/evidence receipt indexing
    scoreboard.py            # Sarathi vs Hermes/OpenClaw scoreboard
    liveness.py              # bridge/service/runtime heartbeat rollups
    proof_gates.py           # proof-gate status renderer

  cli/
    __init__.py
    commands.py              # dgc holon/sarathi commands

  api/
    __init__.py
    routes.py                # API routes for holon/gateway status

  sarathi/
    __init__.py
    gateway.py               # Sarathi apex process
    pulse.py                 # multi-holon pulse
    roster.py                # sub-holon roster loader
    brief.py                 # operator brief
    scoreboard.py            # Sarathi-vs-Hermes proof matrix
```

## 4. Existing-code mapping into target package

| Target organ | Existing code today | Status |
|---|---|---|
| `identity/registry.py` | `agent_registry.py`, `external_agent_registration.py` | Exists, scattered. |
| `runtime/bridge.py` | `holon_bridge.py` | Exists. `@frontier` / `resolve_top_available_at_wake` is wired into `load_holon`. |
| `runtime/provider.py` | `runtime_provider.py`, `model_hierarchy.py` | Exists as a thin facade; owns the model-agnostic wake resolver. |
| `runtime/wake_cycle.py` | `holon_runtime.py` | Exists. Sarathi should wrap it. |
| `runtime/persistence.py` | `holon_persistence.py` | Exists. |
| `runtime/health.py` | `holon_health.py`, `holon_service_liveness.py`, `holon_transport_liveness.py` | Exists. |
| `kernel/living_kernel.py` | `operator_core/living_agent_kernel.py` | Exists. |
| `authority/execution_lease.py` | `operator_core/execution_lease.py` | Exists. |
| `authority/reversibility_gate.py` | `operator_core/reversibility_gate.py` | Drafted, uncommitted. |
| `orchestration/orchestrate.py` | `holon_orchestrate.py` | Exists. |
| `orchestration/fanout.py` | `orchestrator.py`, `agent_runner.py` | Exists. |
| `transport/a2a_send.py` | `scripts/runtime/a2a_send.py` | Exists. |
| `transport/inbox_bridge.py` | `scripts/runtime/a2a_inbox_bridge.py` | Exists. |
| `responders/*` | `scripts/runtime/*semantic_responder.py`, `codex_composer_wake_loop.py` | Partially exists. Needs common base/profile split. |
| `gateway/*` | No shared product-shaped gateway package yet | Missing. |
| `sarathi/*` | No repo package yet; only identity docs in `~/.dharma/agents/sarathi` | Missing. |
| `observability/scoreboard.py` | reports/docs exist; no cohesive code package | Missing/partial. |

## 5. What we are missing versus Hermes Agent

Not all of this means "write thousands of files." It means product-shaped
organs are missing or scattered.

| Hermes-like organ | Do we have it? | Gap |
|---|---|---|
| Product CLI | Partial | `dgc agent` exists, but no polished holon-system CLI spine. |
| Gateway daemon | Partial/missing | A2A bridges and responders exist; Sarathi gateway missing. |
| Provider abstraction | Yes | `runtime_provider.py`, `model_hierarchy.py`; `@frontier` integration now exists via `resolve_top_available_at_wake`. |
| Persistent memory/runtime state | Yes/partial | Living kernel + memory systems exist, but maps are split. |
| Cron/always-on scheduler | Yes/partial | Dharma cron + Hermes cron + launchd exist; no unified holon scheduler UI. |
| Plugin/skill system | Exists elsewhere | Not integrated as holon-system product organ. |
| A2A transport | Yes | `a2a_*` code exists; NATS/filesystem status can diverge. |
| Semantic responders | Partial | Codex/Fugu templates exist; Fable not proven. |
| Safety/permission | Partial | execution lease + reversibility gate exist; provider drift still exists. |
| Web/TUI/operator app | Exists elsewhere | Not cleanly part of holon-system package. |
| Packaging/install/update | Weak | No clear "install our holon system" product path like Hermes. |
| Docs front door | Newly started | `docs/sarathi_apex_build/` is the current corrective front door. |
| Runtime/source boundary | Weak | Runtime wrappers not enforced; identity homes overlap. |

## 6. Migration strategy: no giant move first

Do not mass-move 131 files in one PR. That will break imports and create more
mess. Use a three-pass migration.

### Pass A — map and facade

1. Keep existing modules in place.
2. Add `dharma_swarm/holon_system/` package.
3. Add thin facade modules that import existing code.
4. Add tests proving old and new import paths both work.
5. Add `docs/sarathi_apex_build/` as front door.

### Pass B — Sarathi product slice

1. Add `dharma_swarm/holon_system/sarathi/`.
2. Implement `roster.py`, `pulse.py`, `brief.py`, `gateway.py`.
3. Runtime `~/.dharma/agents/sarathi/gateway/sarathi_gateway.py` becomes a
   thin wrapper importing `dharma_swarm.holon_system.sarathi.gateway`.
4. Create missing Sarathi runtime surfaces.

### Pass C — consolidate organs

1. Move code organ-by-organ behind compatibility imports.
2. Deprecate duplicate/legacy identity homes.
3. Normalize hyphen/underscore aliases.
4. Make `dgc holon-system status` render repo/runtime boundary health.

## 7. Immediate next build tasks

1. Resolve Fugu provider drift (`sakana` as declared external provider or modeled external-only).
2. Prove Fable standing daemon with a fresh unattended semantic reply.
3. Collapse the tracked `holon/` fork until `sprawl_guard.py` exits 0.
4. Create Sarathi runtime wrapper + surfaces.
5. Run one Sarathi pulse over Hermes + Codex + Fugu/Fable state.
6. Produce honest scoreboard: where Hermes still beats us, where Sarathi
   design/runtime now beats Hermes.

## 8. Definition of "our own Hermes system"

Our own Hermes system is not "Sarathi identity docs." It is:

```text
holon_system = identity + provider routing + persistent wake kernel +
               governed runtime + orchestration + A2A transport +
               semantic responders + gateway + observability +
               packaging/CLI + proof gates
```

Sarathi is the apex occupant of that system.

Hermes-m5 remains a field-ops peer/sub-holon until our holon system can match
or exceed it with receipts.
