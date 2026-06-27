# Agni -> Dharma Capital Bridge V0 Verification Receipt

Date: 2026-06-26
Checkout: `/Users/dhyana/dharma_swarm`
Branch: `recover/dharma-capital-2026-06-24`

## Verdict

PASS for V0 bridge implementation.

AMBER for portfolio judgment because sister-lab packets are not present yet and
the real Agni packet reports stale/broken evidence signals. This is not a
bridge failure; it is evidence the bridge correctly surfaces for human review.

## Scope Verified

- SHAKTI_GINKO remains the umbrella economic organ.
- DHARMA CAPITAL sits underneath SHAKTI_GINKO as portfolio/meta-capital
  intelligence.
- Agni is one child trading lab, not the fund.
- Agni emits signed evidence packets.
- Dharma Capital imports packets into receipt-backed projections and
  `capital_lab.contracts.Insight` objects.
- Import output contains human-review proposals only.
- No order, route mutation, broker write, capital approval, or authority
  escalation is produced.

## Onboarding

Command:

```bash
make onboard
```

Result: PASS.

Observed checkout:

- worktree: `/Users/dhyana/dharma_swarm`
- branch: `recover/dharma-capital-2026-06-24`
- head: `69506fc803`
- branch state: ahead 10, behind origin/main 272
- dirty files existed before this work; bridge edits were kept scoped.

## Real Snapshot Export

Command:

```bash
./.venv/bin/python -m dharma_swarm.capital_lab.agni_bridge export \
  --snapshot-root /Users/dhyana/agni_ginko_trading_history_20260625 \
  --jsonl /private/tmp/agni_bridge_verifier/agni_packets.jsonl \
  --generated-at 2026-06-26T00:00:00Z
```

Result: PASS.

Observed output:

```json
{
  "packet_id": "agni_pkt_14934da97c8c1514b37f1d5d",
  "routes_observed": 155,
  "signature": "42386001e6bf41ed423f76d16253e18b683e816a453b07132620c69b940d6273",
  "authority": {
    "read_only": true,
    "live_authority": false,
    "broker_write_authority": false,
    "capital_approval": false,
    "operator_approval_granted": false,
    "mutates_live_lab_state": false,
    "route_mutation_authority": false,
    "order_generation_authority": false
  }
}
```

The exporter wrote only to `/private/tmp/agni_bridge_verifier/agni_packets.jsonl`
during verification.

## Real Snapshot Import

Command:

```bash
./.venv/bin/python -m dharma_swarm.capital_lab.agni_bridge ingest \
  --jsonl /private/tmp/agni_bridge_verifier/agni_packets.jsonl \
  --receipt-json /private/tmp/agni_bridge_verifier/import_receipt.json
```

Result: PASS.

Observed summary:

- evidence id: `cap_evd_b67676a7738d1eeab392b5f8`
- universe: `AGNI_LAB`, `AVAX`, `BTC`, `ETH`, `SOL`
- comparison status: `sister_labs_missing`
- total PnL projected from packet: `100.9374`
- 30d PnL projected from packet: `24.3909`
- routes observed: `155`
- trades observed: `1969`
- stale feed alerts projected from packet: `277298`
- proposals generated: `3`
- every proposal: `approval_state=requires_human_review`
- every proposal: `auto_approved=false`
- every proposal: `capital_authority_change=false`
- every proposal: `route_mutation=false`
- every proposal: `order_generation=false`

## Tests

Command:

```bash
./.venv/bin/python -m pytest tests/test_capital_lab_agni_bridge.py -q
```

Result:

```text
6 passed
```

This proves:

- bridge import does not import the broker-paper membrane;
- exporter appends signed JSONL packets;
- exporter does not touch `routes.json`;
- importer maps to evidence and `Insight` objects only;
- importer compares orthogonal sister labs;
- importer flags clone-risk sister labs;
- importer rejects signature tampering;
- importer rejects authority escalation.

Command:

```bash
./.venv/bin/python -m pytest \
  tests/test_capital_lab_contracts.py \
  tests/test_capital_lab_alpha_evidence.py \
  tests/test_capital_lab_broker_paper_membrane.py \
  tests/test_capital_lab_risk_governor.py -q
```

Result:

```text
27 passed
```

This proves the lazy package export change did not break existing capital_lab
contract, alpha evidence, broker-paper, or risk-governor tests.

## Boundary Evidence

Files added or changed for this bridge:

- `dharma_swarm/capital_lab/agni_bridge.py`
- `dharma_swarm/capital_lab/__init__.py`
- `tests/test_capital_lab_agni_bridge.py`
- `docs/architecture/SHAKTI_GINKO_DHARMA_CAPITAL_AGNI_BRIDGE.md`
- `reports/capital_lab/agni_bridge/BRIDGE_V0_VERIFICATION_RECEIPT.md`

No live lab files were edited by the verifier commands. No broker SDKs, broker
paper membrane, `OrderIntent`, `PortfolioTarget`, `RiskAdjustedTarget`, or
`Order` objects are used by the bridge implementation.
