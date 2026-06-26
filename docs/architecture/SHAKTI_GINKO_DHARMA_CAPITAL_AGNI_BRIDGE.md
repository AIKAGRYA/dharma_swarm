# SHAKTI_GINKO -> DHARMA CAPITAL -> Agni Bridge V0

Status: implemented V0, read-only evidence bridge.

## Tree

```text
SHAKTI_GINKO
  -> DHARMA CAPITAL
      -> trading labs
          -> Agni
              -> routes
```

SHAKTI_GINKO is the economic mother-wing. It owns the broad revenue and
economic-organ frame for the repo.

DHARMA CAPITAL sits underneath SHAKTI_GINKO. It is the portfolio intelligence
and meta-capital allocator layer. It thinks across labs and produces
human-review proposals. It does not inherit permission to trade.

Agni is one child lab under DHARMA CAPITAL. Agni emits evidence about what it is
doing, what is working, what is stale or broken, and which route-level receipts
support the claim.

Routes are lab-local implementation details. They are evidence sources, not
capital allocation authorities.

## Implemented Surface

The V0 implementation is
`dharma_swarm/capital_lab/agni_bridge.py`.

It has two halves:

- Exporter: reads stable local Agni snapshot files and appends signed JSONL
  packets.
- Importer: validates signed packets and maps them into capital_lab evidence,
  `Universe`, `Insight`, lab comparison, and human-review proposal objects.

The exporter reads only these stable files:

- `agni_daily_reports.json`
- `agni_trading_timeline.json`
- `agni_alpha_full_summary.json`

The current local snapshot root used for verification was:

```text
/Users/dhyana/agni_ginko_trading_history_20260625
```

## Authority Boundary

Every packet carries this authority boundary:

```json
{
  "read_only": true,
  "live_authority": false,
  "broker_write_authority": false,
  "capital_approval": false,
  "operator_approval_granted": false,
  "mutates_live_lab_state": false,
  "route_mutation_authority": false,
  "order_generation_authority": false
}
```

The importer rejects packets whose authority block differs, even if the packet
is re-signed.

## Capital Mapping

Agni packets map to `capital_lab.contracts.Insight` objects only.

They do not map to:

- `PortfolioTarget`
- `RiskAdjustedTarget`
- `Order`
- broker-paper `OrderIntent`
- route mutation patches
- approved capital allocations

This preserves the capital_lab contract:

```text
Universe -> Insight -> PortfolioTarget -> RiskAdjustedTarget -> Order
```

Agni contributes evidence at the `Insight` layer. DHARMA CAPITAL compares labs
and proposes review. Humans approve capital authority.

## Sister Labs

The importer accepts multiple signed lab packets. Comparison is portfolio-level:

- one packet: `sister_labs_missing`
- multiple packets with distinct `strategy_scope`: `compared`
- multiple packets sharing a `strategy_scope`: `compared_with_clone_risk`

This keeps sister VPS labs complementary and orthogonal rather than Agni clones.

## BoardStore Fit

V0 does not write BoardStore cards. The output proposals are plain
human-review projection objects designed to become BoardStore cards later.

This follows the BoardStore rule that projection surfaces do not own authority.
Future BoardStore posting should be an adapter that consumes these proposal
objects, not a mutation hidden in the importer.

## Commands

Run exporter against a local Agni snapshot:

```bash
./.venv/bin/python -m dharma_swarm.capital_lab.agni_bridge export \
  --snapshot-root /Users/dhyana/agni_ginko_trading_history_20260625 \
  --jsonl /private/tmp/agni_bridge_verifier/agni_packets.jsonl \
  --generated-at 2026-06-26T00:00:00Z
```

Run importer:

```bash
./.venv/bin/python -m dharma_swarm.capital_lab.agni_bridge ingest \
  --jsonl /private/tmp/agni_bridge_verifier/agni_packets.jsonl \
  --receipt-json /private/tmp/agni_bridge_verifier/import_receipt.json
```

Run tests:

```bash
./.venv/bin/python -m pytest tests/test_capital_lab_agni_bridge.py -q
./.venv/bin/python -m pytest \
  tests/test_capital_lab_contracts.py \
  tests/test_capital_lab_alpha_evidence.py \
  tests/test_capital_lab_broker_paper_membrane.py \
  tests/test_capital_lab_risk_governor.py -q
```
