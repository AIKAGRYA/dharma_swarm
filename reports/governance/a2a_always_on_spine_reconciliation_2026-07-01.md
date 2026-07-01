# A2A Always-On Spine Reconciliation

Date: 2026-07-01
Branch: `codex/a2a-always-on-spine-20260701`
Base: `origin/main` at `a4610e585`

## What This Branch Does

This branch ports the useful A2A/NATS work from the former #739 lane onto current `main`, without reopening the already closed `runtime-truth-nats-2026-06` track or importing the superseded Claude `coordination_substrate/**` package.

It adds:

- canonical NATS task transport hardening in `A2ANatsTransport`
- live NATS production matrix and freshness validator
- deterministic matrix provider mode so transport proof is not blocked by cloud-model quota
- cloud-contact denominator and ingress adapter that still publishes through `A2ANatsTransport`
- `pramana_probe.py` as an evidence-tier conductor
- the Claude reconciliation handoff and anti-sprawl architecture signpost
- `A2A_ALWAYS_ON_SPINE_MASTER_PLAN.md`, mapping the agentic design-pattern atlas into the repo's actual owners

## What It Does Not Claim

This is still not a full always-on speaking A2A system.

It does not prove:

- fleet-wide local `DHARMA_FLEET` to AGNI `DHARMA_A2A` mirroring
- production callers using `A2ANatsTransport` as the single task path
- Agent Card signature enforcement
- live `NodeGateway` initialization in the API lifespan
- voice input/output wired as a receipted adapter
- LangGraph runtime ownership

## Keep / Drop Decisions

| Source | Decision | Reason |
|---|---|---|
| #739 NATS transport hardening | Keep | Real transport, receipt, idempotency, redelivery, DLQ, and evidence improvements. |
| #739 old generated evidence | Drop | Source hashes were stale after porting onto `main`; regenerated fresh evidence in this branch. |
| Claude `docs/architecture/A2A_COORDINATION_SUBSTRATE.md` | Keep | Useful anti-sprawl doctrine and corrected equivalence map. |
| Claude `docs/ops/A2A_LOCAL_RECONCILIATION_HANDOFF.md` | Keep | Useful local reconciliation knowledge base. |
| Claude `scripts/governance/pramana_probe.py` | Keep | Non-redundant evidence-tier conductor. |
| Claude `dharma_swarm/coordination_substrate/**` | Drop | Superseded, zero production callers, redundant with existing A2A/runtime_state/pr_merge_control owners. |

## Fresh Evidence

Fresh local-live evidence was generated from this branch:

- `reports/governance/nats_live_production_matrix/nats-live-20260701T152842Z-126a62d0/evidence.json`
- `reports/governance/nats_live_production_matrix/latest.json`
- `reports/a2a/nats_live_production_matrix/nats-live-20260701T152842Z-126a62d0/receipts/nats_live_20260701T152842Z_126a62d0_happy_path_8c1a91e5.semantic_receipt.json`

Provider note: the first live matrix attempt failed because `ollama:glm-5.2:cloud` returned a weekly usage-limit error. The passing evidence uses `--provider deterministic --model local-deterministic`; NATS broker delivery remains live against `nats://127.0.0.1:4222`.

## Verification

Commands run successfully:

- `/Users/dhyana/dharma_swarm/.venv/bin/python -m pytest tests/test_a2a_cloud_contact.py tests/test_nats_transport.py tests/test_nats_substrate_contract.py tests/test_pramana_probe.py tests/test_track_portfolio.py -q`
- `/Users/dhyana/dharma_swarm/.venv/bin/python scripts/governance/check_nats_live_production_evidence.py --max-age-hours 24`
- `/Users/dhyana/dharma_swarm/.venv/bin/python scripts/governance/check_nats_substrate_contract.py`
- `make nats-substrate-contract PYTHON=/Users/dhyana/dharma_swarm/.venv/bin/python PYTEST=/Users/dhyana/dharma_swarm/.venv/bin/pytest`

## Next Implementation Order

1. Wire a production caller to `A2ANatsTransport.publish_task`, or explicitly keep `a2a_send.py` compatibility-only.
2. Add dual-broker survey: local `DHARMA_FLEET` and AGNI `DHARMA_A2A` must be reported separately.
3. Decide whether to build a scoped broker mirror; if yes, use subject allowlists and loop-prevention headers.
4. Initialize `NodeGateway` in the API lifespan and enforce Agent Card signatures or an equivalent trust gate.
5. Add the speaking adapter: speech-to-text -> OperatorIntent -> A2A task -> reply/artifact -> text-to-speech.
6. Integrate LangGraph only as a durable long-workflow layer after A2A task truth is stable.
