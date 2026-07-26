# Memory Common

Memory Common is the one-door retrieval surface for swarm context.

Role: operator usage guidance (reference doc). The canonical agent behavior
contract lives in `CLAUDE.md`; nothing in this document adds to or overrides
it.

## Operator Commands

- `/memory` or `dgc memory`: show common memory status.
- `/memory query <topic>` or `dgc memory query <topic>`: retrieve ranked governed memory.
- `/memory common <task>` or `dgc memory common <task>`: build a copy-pasteable agent handoff pack.
- `/memory ingest`: backfill live wiki concepts into vector/common memory.
- `/memory gate`: run the common memory regression gate.
- `/memory metabolize`: run ingest + gates and write a metabolism receipt.
- `/memory schedule` or `dgc memory schedule --schedule "every 24h"`: register recurring memory metabolism with the existing cron system.

## Suggested Agent Usage

Memory Common can seed context for non-trivial work (this is usage guidance,
not a behavioral mandate — those live in `CLAUDE.md`):

```text
/memory common <task>
```

Use the returned pack as retrieved context, not as proof by itself. Cite source ids you actually use. If hits are empty or weak, say so and proceed from live evidence.

After work, a useful receipt records:

- task and outcome
- memory sources used
- new durable observations
- contradictions or stale concepts found
- failed or surprising queries that should become eval cases

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

Metabolism receipts land under `<state_dir>/reports/memory_kernel/` (default `~/.dharma/reports/memory_kernel/`) — runtime receipts never enter git. Each metabolism run also refreshes `WIKI_VECTOR_LIVE_GATE_*_FINAL.json` and `MEMORY_RETRIEVAL_SYSTEM_GATE_*_FINAL.json` there; those `*_FINAL.json` receipts are the only place `dgc memory status` reads gate scores from, so the scores stay null until the first metabolism run (or a manual gate run with `--receipt-path`) lands under the state dir. Historical receipts left in an old checkout's in-repo `reports/memory_kernel/` are not migrated and not read — copy them into the state-dir sink if you want them visible.

## Surface State-Dir Caveat (live parity)

The Bun/Helm terminal bridge routes `/memory` with its own bridge state dir (`~/.dharma/terminal`), not the global `~/.dharma`. From that surface `status`/`query` see an empty store, and the mutating modes are reachable too: `ingest`/`metabolize` would create a second vector store and receipt sink under `~/.dharma/terminal/`. This is bug-for-bug parity with the live checkout this surface was ported from; re-rooting the bridge's memory door is a follow-up, not part of the port. Prefer `dgc memory ...` (global state dir) for real ingest/metabolism. One divergence from live parity (review-forced): `schedule` now persists the scheduling surface's `state_dir` in the cron job payload, so a scheduled metabolism runs against the same store the scheduling door observes instead of silently falling back to the global default.

## Gate Trust Caveat

The broad-sweep component of the system gate generates its eval cases from the same indexed sidecar rows it retrieves against (audit 2026-07-25 §5.7). The same applies to the metabolism path's source-coverage targets: `run_memory_metabolism` derives `*_target` values from the store's current sidecar counts, so a store that silently lost rows still earns full coverage credit. A 100/100 score is custody/regression signal, not external relevance or row-retention proof — do not re-trust it as a quality bar until the eval battery is replaced with held-out cases and the coverage targets are ratcheted against previously receipted minimums (named follow-up with the eval-battery replacement).
