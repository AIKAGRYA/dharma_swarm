# Memory Common

Memory Common is the one-door retrieval surface for swarm context.

## Operator Commands

- `/memory` or `dgc memory`: show common memory status.
- `/memory query <topic>` or `dgc memory query <topic>`: retrieve ranked governed memory.
- `/memory common <task>` or `dgc memory common <task>`: build a copy-pasteable agent handoff pack.
- `dgc wiki search <term>`: search the governed wiki projection through Memory Common.
- `dgc wiki show <topic>`: show an exact trusted concept file, falling back to governed retrieval.
- `/memory ingest`: backfill live wiki concepts into vector/common memory.
- `/memory gate`: run the common memory regression gate.
- `/memory metabolize`: run ingest + gates and write a metabolism receipt.
- `/memory schedule` or `dgc memory schedule --schedule "every 24h"`: register recurring memory metabolism with the existing cron system.

## Agent Contract

Before non-trivial work, call Memory Common with the task:

```text
/memory common <task>
```

Use the returned pack as retrieved context, not as proof by itself. Cite source ids you actually use. If hits are empty or weak, say so and proceed from live evidence.

After work, write a receipt with:

- task and outcome
- memory sources used
- accepted context
- rejected context
- new durable observations
- contradictions or stale concepts found
- failed or surprising queries that should become eval cases
- Chetana staged atom path, or a `not durable` reason

## Karpathy Wiki Contract

The Karpathy LLM Wiki method is enforced locally through this loop:

```text
raw/source receipt -> staged atom -> governed promotion -> trusted wiki concept
  -> vector/search projection -> Memory Common pack -> agent receipt
```

Agents must treat retrieval as context, not authority. When a task names a
canonical owner file or schema, read that owner file directly. When a task
produces durable knowledge, stage it through Chetana or record why it is not
durable. Do not write directly into trusted wiki concepts except through a
governed promotion path.

For non-trivial work, the closeout must include:

- `memory_sources_used`
- `accepted_context`
- `rejected_context`
- `durable_observations`
- `contradictions`
- `dead_ends`
- `candidate_atom_path`

## Metabolism Loop

The compounding loop is:

```text
agent work -> receipt -> curated wiki/atoms -> ingest -> governed retrieval -> gate -> next agent context
```

Nothing writes directly to vector memory as truth. Truth flows through receipts and promoted wiki/atom surfaces; the vector DB is the query projection.

For regular compounding, schedule:

```bash
dgc memory schedule --schedule "every 24h"
dgc cron daemon
```

Run `dgc memory metabolize` manually after wiki/atom promotion when you want an immediate receipt. The scheduled job uses the typed `memory_common_metabolism` cron handler, so it runs local ingest/gates directly and fails the cron job if the gates fail.
