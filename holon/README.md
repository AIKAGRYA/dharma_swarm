# Holon Runtime

`holon-runtime` is a standalone Holon agent runtime package. It can be
installed from this directory without importing the parent `dharma_swarm`
package.

Core guarantees:

- local package metadata and `holon` CLI entrypoint
- no parent package imports in core runtime modules
- governed cycle loop with kill, budget, retry/fallback provider routing,
  memory context projection, artifact gate, receipts, and restartable ledger
- bounded supervisor with atomic lock files and hash-chained service heartbeats
- burn-in runner with per-sample supervisor receipts and source-tree digest
- read-only local A2A identity probe receipts
- strict isolation verifier

Quick checks:

```bash
python -m holon verify --json
python -m holon status <agent-name>
python -m holon wake <agent-name> "Run one bounded cycle."
python -m holon supervise <agent-name> --cycles 2
python -m holon burn-in <agent-name> --duration-seconds 300 --min-cycles 2
```

The runtime writes under the supplied `--agents-root` or
`~/.dharma/agents/<agent-name>/` by default. It stores cycle records in
`wake_ledger.jsonl`, service liveness in `service_heartbeats.jsonl`, and
idempotent receipts under `receipts/`.

Provider responses may report dollar cost directly. When they only report token
usage, configure local rates with `HOLON_<PROVIDER>_INPUT_USD_PER_1M_TOKENS`,
`HOLON_<PROVIDER>_OUTPUT_USD_PER_1M_TOKENS`, or
`HOLON_<PROVIDER>_TOTAL_USD_PER_1M_TOKENS` where `<PROVIDER>` is `OPENAI` or
`OPENROUTER`. Generic `HOLON_INPUT_USD_PER_1M_TOKENS`,
`HOLON_OUTPUT_USD_PER_1M_TOKENS`, and `HOLON_TOTAL_USD_PER_1M_TOKENS` are used
as fallbacks. The package does not hard-code vendor prices.

Burn-in receipts include `multi_hour_proven`. A short or smoke burn-in may pass
its configured sample gate while still reporting `multi_hour_proven=false`; that
is not a substitute for the multi-hour production gate.
