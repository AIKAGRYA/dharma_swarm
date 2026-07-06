# Sarathi Apex Build — Current Map (2026-07-06)

Purpose: put Codex, Fugu, Fable, Hermes, and future builders on the same page.
This file is the active front door for the Sarathi apex build. It is a map,
not a claim that Sarathi is alive.

## 0. One-line truth

Sarathi is the governed apex continuity holon: it should coordinate Hermes,
composer seats, Fugu Ultra, and workers through existing dharma_swarm
substrates, while only running code-deterministic reversible-safe actions
unattended.

Current status: generic holon/persistent-agent substrate exists; Sarathi's
identity/mind exists; Sarathi's own runtime gateway/state surfaces are still
missing; deterministic reversibility gate is drafted but uncommitted.

## 1. Primary homes

| Home | Role | Canonical? | Notes |
|---|---|---:|---|
| `/Users/dhyana/dharma_swarm` | Main source code repo | Yes | Versioned code, tests, docs, governance manifests. |
| `/Users/dhyana/.dharma` | Main live runtime/state home | Yes | Mutable identities, state, ledgers, inboxes, receipts, launch/runtime artifacts. |
| `/Users/dhyana/.hermes/hermes-agent` | Hermes product checkout | Side ecosystem | NousResearch Hermes Agent product; `hermes-m5` is John's instance, not dharma holon lineage. |
| `/Users/dhyana/dharma_swarm/docs/sovereign_holons` | Older/general sovereign-holon doctrine/build history | Historical canonical | Still important, but not the active Sarathi front door. |
| `/Users/dhyana/.dharma/agents/sarathi` | Sarathi mind/genesis | Runtime canonical | Identity/docs/genesis live here; not enough to prove Sarathi is breathing. |
| `/Users/dhyana/dharma_swarm/docs/sarathi_apex_build` | Active Sarathi map | New front door | Repo-tracked map tying code, runtime, proof gates, and roster together. |

## 2. Code stack: persistent-agent lineage to Sarathi

| Layer | Source code | Meaning | Sarathi relationship |
|---|---|---|---|
| Preset autonomous agents | `dharma_swarm/autonomous_agent.py` | ReAct-style execution engine. | Execution ancestor, not apex identity. |
| Older persistent agents | `dharma_swarm/persistent_agent.py` | Standing actor with wake loop, memory/stigmergy/messages, gate, witness log. | Ancestor pattern. Do not call Sarathi "just a PersistentAgent." |
| Registry / external registration | `dharma_swarm/agent_registry.py`, `dharma_swarm/external_agent_registration.py` | Identity and policy data. | Identity source, not sufficient runtime enforcement. |
| Living Agent Kernel | `dharma_swarm/operator_core/living_agent_kernel*.py` | Durable wake ledger, proof ledger, leases, closeback, supervisor/worker services. | Durability/proof spine Sarathi should reuse. |
| Holon bridge/runtime | `dharma_swarm/holon_bridge.py`, `dharma_swarm/holon_runtime.py`, `dharma_swarm/holon_persistence.py`, `dharma_swarm/holon_health.py` | Identity-aware governed holon wake cycle. | Sarathi gateway must wrap this; do not build a parallel loop. |
| Holon orchestration | `dharma_swarm/holon_orchestrate.py`, `dharma_swarm/orchestrator.py`, `dharma_swarm/agent_runner.py`, `dharma_swarm/intent_router.py` | Fan-out/fan-in through existing swarm substrate. | Sarathi delegates through this. |
| Operator safety | `dharma_swarm/operator_core/execution_lease.py`, `dharma_swarm/operator_core/reversibility_gate.py` | Lease authority + deterministic reversible/irreversible classification. | This is the apex safety bank. `reversibility_gate.py` is currently uncommitted. |
| Runtime responders | `scripts/runtime/*semantic_responder.py`, `scripts/runtime/*wake_loop.py`, `scripts/runtime/a2a_*.py` | Standing daemons/bridges/transport workers. | Sub-holon body templates; Fugu works as template; Fable still needs proof. |

## 3. Live identity/state homes (verified 2026-07-06)

| Runtime home | Count | Status |
|---|---:|---|
| `~/.dharma/agents` | 67 | Current holon/agent identity home. |
| `~/.dharma/ginko/agents` | 52 | Legacy/ginko registry; not the active holon home. |
| `dharma_swarm/docs/agents` | 11 | Repo docs/seats, not live runtime. |
| `~/.dharma/a2a/cards` | 49 | A2A cards. |
| `~/.dharma/external_agents` | 25 | External-agent registrations. |
| `~/.dharma/a2a_bus/inboxes` | 196 | Runtime inbox substrate; contains many stale/test/live entries. |

## 4. Current `dgc agent list` shape

`dgc agent list` currently shows:

- 5 preset wake agents: `researcher`, `coder`, `scout`, `reviewer`, `witness`.
- 17 registered sovereign holons:
  `artha_cream`, `codex_composer`, `codex_worker_spine`,
  `cybernetics_codex`, `devin-roaming-2987d222`, `fable_composer`,
  `fugu_ultra`, `hermes-m5`, `livelihood_loom_ceo`, `magpie`,
  `merge_master_mike`, `operator_guide_cursor`, `opus_composer`,
  `palantir_pilot`, `repo_cartographer`, `sakshi_auditor`, `sarathi`.

Important current warning:

- `fugu_ultra` has provider `sakana`, which is not yet a valid `ProviderType`;
  `load_holon` coerces it to `claude_code`. That is a real drift point.

## 5. Current health snapshot (2026-07-06)

| Seat | Current evidence | Honest status |
|---|---|---|
| `hermes-m5` | `~/.dharma/a2a_bus/state/hermes-m5.json` fresh, status operational, model `glm-5.1`, provider `zai`; Hermes source is `~/.hermes/hermes-agent`. | Operational field-ops/continuity organ; evidence-only authority; not dharma holon lineage. |
| `codex_composer` | Fresh service heartbeat, but `dgc agent status` says service_alive false/status error. | Has responder activity but not clean service-alive proof. |
| `fugu_ultra` | A2A state says responder active/fresh; identity still says not unattended; provider enum drift exists. | Useful template/critic; not cleanly admitted as durable holon yet. |
| `fable_composer` | A2A state stale-ish, process_running false, wake_loop_active false. | Standing semantic daemon not yet proven. |
| `sarathi` | identity/mind exists; no state/inbox/bridge heartbeat/gateway/roster/contract. | Genesis-authored, not breathing. |

## 6. Sarathi runtime surfaces: missing

These are required before Sarathi can be called alive:

```text
~/.dharma/a2a_bus/state/sarathi.json
~/.dharma/a2a_bus/inboxes/sarathi/
~/.dharma/a2a_bus/bridge_heartbeats/sarathi.json
~/.dharma/agents/sarathi/gateway/sarathi_gateway.py
~/.dharma/agents/sarathi/HOLARCHY_CONTRACT.md
~/.dharma/agents/sarathi/SUB_HOLON_ROSTER.yaml
```

Repo-side Sarathi code should be added under:

```text
dharma_swarm/sarathi/
  gateway.py
  pulse.py
  roster.py
  brief.py
  scoreboard.py
```

The runtime `~/.dharma/agents/sarathi/gateway/sarathi_gateway.py` should be a
thin wrapper importing repo code, not the source of truth itself.

## 7. Why codebase and runtime home are separate

This split is normal and mostly correct:

- repo (`dharma_swarm`) = source code, tests, docs, schemas, versioned manifests;
- runtime home (`~/.dharma`) = mutable local state, identity instances, ledgers,
  receipts, inboxes, heartbeats, secrets-adjacent runtime files, launch artifacts;
- side product (`~/.hermes`) = third-party Hermes product and its own state.

The split becomes a problem when source-like things live only in runtime state,
or when runtime identities do not point back to repo-owned code/schemas.

Current problem class:

1. too many identity homes (`~/.dharma/agents`, `~/.dharma/ginko/agents`,
   `docs/agents`, `external_agents`);
2. hyphen/underscore duplicates (`hermes_m5` vs `hermes-m5`, composer variants);
3. gateway/daemon scripts risk living only under `~/.dharma`;
4. docs/receipts/history are spread across multiple roots;
5. `dgc status` service liveness and A2A state do not always agree.

## 8. Boundary rule going forward

Do not collapse repo and runtime into one directory. Instead enforce:

1. **Source lives in git.** Runtime scripts are wrappers only.
2. **Runtime state lives in `~/.dharma`.** Do not commit mutable inboxes/heartbeats/secrets.
3. **Every runtime surface must have a repo-tracked map entry.**
4. **Every identity must declare lineage, authority, model/provider, and source-code owner.**
5. **Every "alive" claim must cite a service heartbeat or wake receipt, not a SOUL file.**

## 9. Immediate Sarathi proof gates

1. Commit `dharma_swarm/operator_core/reversibility_gate.py` and
   `tests/test_reversibility_gate.py`.
2. Patch `holon_bridge.load_holon` so `@frontier` /
   `resolve_top_available_at_wake` resolves through `model_hierarchy`.
3. Fix provider enum drift for `fugu_ultra` / Sakana or mark it as external
   provider without coercion.
4. Prove Fable as a standing semantic daemon, not a session-borne seat.
5. Create Sarathi runtime surfaces.
6. Add repo-owned `dharma_swarm/sarathi/` code and make runtime gateway a wrapper.
7. Run one multi-holon pulse producing `sarathi_pulse_receipt.json` and
   `operator_brief.md`.
8. Run overnight durability proof before setting `wake_loop_active=true`.

## 10. Most trustworthy commands

```bash
cd /Users/dhyana/dharma_swarm
make onboard
.venv/bin/python -m dharma_swarm.dgc_cli agent list
.venv/bin/python -m dharma_swarm.dgc_cli agent status --json
git status --short
```

