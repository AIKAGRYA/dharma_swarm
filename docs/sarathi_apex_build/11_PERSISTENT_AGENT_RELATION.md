# 11 — Persistent-Agent Relation: Agents → Persistent Agents → Holons → Sarathi Apex

This document exists to stop the word-collapsing that created the sprawl. The
stack is a composition of already-existing strata, not a rewrite and not a new
parallel orchestrator.

## The locked sentence

Sarathi is the apex holon that USES persistent-agent lineage + living-agent kernel + holon runtime + existing orchestrator, then ADDS deterministic reversibility gating and operator-facing continuity — not a parallel rewrite.

## Layer stack

```text
Registry / identity records
  → PersistentAgent / AutonomousAgent lineage
  → LivingAgentKernel durable wake ledger + leases + closeback
  → Holon runtime + bridge + persistence + kill/budget/health organs
  → Existing Orchestrator fan-out/fan-in
  → Sarathi apex wrapper: reversibility gate + roster + brief/phone continuity
```

## Verified file table

| Layer | File anchors | Verified facts | What it means | What it is not |
|---|---|---|---|---|
| Registry / identity | `dharma_swarm/agent_registry.py:181` (`AgentRegistry`), `dharma_swarm/agent_registry.py:318` (frontier proposals without second task store), `dharma_swarm/external_agent_registration.py:434-438` (onboarding receipt) | `agent_registry.py` is 980 lines; `external_agent_registration.py` is 527 lines. | Identity, policy, registration, and onboarding receipts. | Not a running mind and not proof of wake/metabolism. |
| Older persistent actor | `dharma_swarm/persistent_agent.py:117` (`PersistentAgent`), `dharma_swarm/persistent_agent.py:371` (`wake()`), `dharma_swarm/persistent_agent.py:622` (task injection from orchestrator) | `persistent_agent.py` is 633 lines. | The older standing-agent pattern: memory/messages/stigmergy/wake. | Not by itself a holon or apex; it lacks the full holon contract and apex gate. |
| Older autonomous actor | `dharma_swarm/autonomous_agent.py:384` (`AutonomousAgent`), `dharma_swarm/autonomous_agent.py:428` (`wake()`), `dharma_swarm/autonomous_agent.py:1277` (orchestrator decides who wakes) | `autonomous_agent.py` is 1,465 lines. | Execution ancestor / ReAct-style worker lineage. | Not an apex chief-of-staff body. |
| Living durable spine | `dharma_swarm/operator_core/living_agent_kernel.py:1199` (`LivingAgentKernel`), `:1030` (`lease_next_wake`), `:1113` (`record_wake_closeback`), `:1539` facade `lease_next_wake`, `:1958` `closeback_source_wake` | `living_agent_kernel.py` is 2,921 lines. | Durable wake ledger, leases, proof ledger, closeback, daemon control, source-closeback. | Not a duplicate holon runtime; it is the durability/proof spine the holon should reuse. |
| Holon bridge | `dharma_swarm/holon_bridge.py:106` (`load_holon`), `:152` (`get_holon_provider`), `:198` (`get_holon_dialogue_provider` on the dev branch), `:336` (`build_request`), `:357` (`holon_reply`), `:382` (`guard_outcome_claim`) | Current branch file is 397 lines; `origin/main` and deploy body are 204 lines. | Loads `~/.dharma/agents/<name>/identity.json` and prompt into a `RunningHolon`; routes through the holon's own provider/prompt. | Not the wake loop and not the source of operator authority. |
| Holon wake runtime | `dharma_swarm/holon_runtime.py:52` (`holon_wake_cycle`), `:75-86` kill/budget before work, `:123-132` runner faults become governed halt, `:141-187` result/persist path, `:190` (`run_holon_loop`) | Runtime file is 247 lines. Runtime code glob `dharma_swarm/holon*` is 18 files / 5,668 lines. | Governed metabolism: kill → budget → injected work → compass → persistence. | Not Sarathi-specific yet; currently no `sarathi` grep hit in holon/wake code. |
| Existing swarm orchestration | `dharma_swarm/holon_orchestrate.py:1-7`, `:315` (`orchestrate_holon`), `:394-395` existing `orchestrator.fan_out/fan_in` | `holon_orchestrate.py` is 460 lines. Its module docstring says it does not create a second orchestrator, task store, model router, or receipt spine. | Thin holon planning/wiring over the existing `Orchestrator`. | Not a new task store/router/receipt spine. |
| Wake profile shell | `scripts/runtime/codex_composer_wake_loop.py:54` (`WakeProfile`), `:96-112` codex+fable profiles, `:660` lease classifier, `:1196-1202` repeated start refused without activation lease | Seat-parameterized shell exists for `codex_composer` and `fable_composer`; no `sarathi` profile yet. | Safe reusable wake wrapper template. | Not a model-cognition loop by itself; `model_identity` is metadata, not a model call. |
| Reversibility gate | `dharma_swarm/operator_core/reversibility_gate.py:1-20` doctrine, `:34-45` `ActionClass`, `:50-76` `NEVER_AUTO_PATTERNS`, `:78-84` `RiskLevel → ActionClass`, `:130-184` deterministic classifier | 225-line untracked file; tests are 90 lines and pass under the repo venv. | Sarathi-specific apex safety brick: code-deterministic reversible-safe envelope. | Not a model opinion and not an authority expansion. |

## Relationship in one paragraph

`AgentRegistry` and external registration define and admit identities. `PersistentAgent`
and `AutonomousAgent` are older standing/executing actor lineages. The
`LivingAgentKernel` supplies the durable wake ledger, leases, proof ledger, and
source closeback. The holon bridge/runtime load identity and run governed wake
cycles while reusing kill/budget/persistence/health organs. `holon_orchestrate.py`
then composes this with the existing `Orchestrator`, explicitly avoiding a second
orchestrator/task store/router/receipt spine. Sarathi should sit on top of this
stack as an apex wrapper: deterministic reversibility gate first, then roster,
brief, phone/operator egress, and proof-backed wake status.

## Current liveness truth

- `load_holon("sarathi")` succeeds in this branch against `~/.dharma/agents/sarathi` and returns model `gemini-2.5-flash`, provider `google_ai`, prompt length `1882`.
- That is identity loading only. It is not a breathing Sarathi.
- `~/.dharma/agents/sarathi` currently has 37 files and 0 executable `.py/.sh/.ts/.js` files.
- `~/.dharma/a2a_bus/leases` currently has 0 lease files.
- `rg sarathi dharma_swarm/holon* scripts/runtime/codex_composer_wake_loop.py` returns no hits.
