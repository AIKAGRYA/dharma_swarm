# Fractal Room Membrane v0

Fractal Room v0 is a typed causal membrane around existing Dharma Swarm organs.
It is not a new executor, dashboard, ontology writer, swarm daemon, or autonomy
loop.

## Causal Stack

| Layer | Intention | Existing organs | Room contract |
|---|---|---|---|
| Telos | Preserve identity and dharmic constraints | `dharma_kernel.py`, `telos_gates.py`, `vsm_channels.py` | room purpose and law must remain compatible with kernel/gates |
| Ontology | Keep value and contribution truth | `ontology.py`, `telic_seam.py` | room identity maps to `VentureCell` / `cell_id`; value facts stay in ontology |
| Operation | Execute bounded work | `task_board.py`, `agent_runner.py`, AgentOps runner | room projects scoped work packets; executors remain separate |
| Coordination | Share local signals | `signal_bus.py`, `stigmergy.py` | room memory namespace and channels scope coordination facts |
| Economy | Account for cost, budget, and revenue | `economic_engine.py`, `economic_spine.py`, `cost_tracker.py` | room declares budget and kill/spinout evidence; accounting organs own numbers |
| Learning | Convert runs into improvement | KaizenReview, `insight_brief.py`, Daily Operating Brief | room pulse consumes reports and emits one conservative next move |
| Human quality | Preserve human taste | Command spine, operating facts | AI may request YDS, but cannot assign authoritative ratings |

## What A Room Does

A room answers:

- why this work exists,
- what it may and may not do,
- which files/tools/work surfaces are in scope,
- what gates and human approvals bind it,
- what value or revenue hypothesis it is testing,
- where its reports, witness logs, and learning artifacts live,
- what the next packet should be,
- and when it should be killed, archived, or spun out.

## What A Room Does Not Do

A room does not:

- run AgentRunner,
- mutate ontology,
- write dashboard/API state,
- run git,
- run tests,
- merge/push,
- assign YDS,
- or launch live autonomy.

Those remain owned by their existing organs. The room only supplies a stable
`room_id` / `cell_id` context and a validation membrane.

## First-Class Fractals

| Room | Purpose | Primary organs |
|---|---|---|
| `dharma-swarm-core` | Preserve the organism's identity, reliability, and learning capacity | kernel, gates, governance, briefs |
| `agentops` | Make repo-agent work scoped, gated, reportable, and repeatable | AgentOps runner, KaizenReview, governance tests |
| `governance` | Keep law, brakes, budgets, and interface truth real | telos gates, module budget, semgrep, mismatch registry |
| `revenue-wedge` | Prove one self-funding external value path under budget and kill conditions | economic organs, Daily Brief, AgentOps packets |
| `research` | Convert exploration into durable cited knowledge artifacts | insight brief, ontology artifacts, witness logs |
| `daily-operating` | Tell the human what happened, what mattered, what cost money, what to stop, and what to do next | operating facts, Daily Brief, YDS ledger |

## Build Rule

`dharma_swarm/fractal/fractal_room.py` is allowed to define schema,
validation, serialization, module-binding constants, and AgentOps scope
projection.

It must not import or call runtime organs. Runtime wiring should happen later
through explicit adapters that pass `room_id` / `cell_id` into existing facts.
