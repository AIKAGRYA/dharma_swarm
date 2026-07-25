# DharmaVerifier-Ranker v0 Data Inventory

Role: report  
Generated receipt: `DATA_INVENTORY_RECEIPT_20260701.json`  
Inventory mode: metadata-only, no raw private message body readout

## Summary

The repository and local Dharma state contain enough receipt, route, provider,
eval, and artifact metadata to build `Dharma Semantic Receipt Graph v0`. The
existing generic training JSONL files are not safe training data for this model
as-is; they remain quarantined until redacted and relabelled.

## Inventoried Surfaces

| Surface | Count / Size | Candidate Records | Training Value | Leakage Risk | v0 Decision |
|---|---:|---|---|---|---|
| `reports/a2a` | 21,214 files / 18,945,378 bytes | `a2a_delivery`, `artifact_ref`, `claim_evidence` | high | medium | metadata and redacted content only |
| `reports/agentops/semantic_receipts` | 40 files / 97,359 bytes | `semantic_receipt`, `verifier_outcome`, `claim_evidence` | high | medium | metadata and redacted content only |
| `reports/agentops/deepseek_ml_lead_council` | 5 files / 24,857 bytes | `human_or_council_label`, `claim_evidence` | medium | low | include after hash lock |
| `reports/sab_first_six_agent_flywheel` | 139 files / 535,929 bytes | `agent_event`, `semantic_receipt`, `a2a_delivery` | medium | medium | metadata and redacted content only |
| `~/.dharma/state/runtime.db` | 1 file / 380,551,168 bytes | `provider_attempt`, `routing_decision`, `agent_event`, `verifier_outcome` | high | medium | schema/counts and selected redacted rows only |
| `~/.dharma/db/messages.db` | 1 file / 1,059,975,168 bytes | `a2a_delivery`, `artifact_ref` | high | high | exclude raw message bodies |
| `~/.dharma/datasets` | 66 JSONL files / 96,411,124 bytes / 220,002 rows | `agent_event` | medium | high | quarantine until redacted and relabelled |
| `~/.dharma/forge_v1` | 3,599 files / 40,850,206 bytes | `eval_result`, `claim_evidence`, `verifier_outcome` | high | medium | metadata and redacted content only |
| `~/sis/docs` | 61 files / 333,191 bytes | `claim_evidence`, `artifact_ref` | medium | medium | hash-locked references only |
| `dharma_swarm/` code surface | 2,750 files / 44,346,823 bytes | `eval_result`, `verifier_outcome` | medium | low | baseline reference, not training text |
| `reports/generated/verification` | 9 files / 195,680 bytes | `eval_result`, `claim_evidence` | medium | medium | metadata and redacted content only |
| `reports/governance` | 691 files / 697,555,104 bytes | `human_or_council_label`, `eval_result`, `claim_evidence` | medium | medium | metadata and redacted content only |
| `~/.dharma/agent_memory` | 146 files / 4,995,207 bytes | `agent_event`, `claim_evidence` | low | high | content excluded, hash metadata only |
| `~/.dharma/traces` | 130,556 files / 88,582,888 bytes | `agent_event`, `artifact_ref` | medium | high | quarantine until schema and redaction review |

## Runtime DB Metadata

`~/.dharma/state/runtime.db`

- Hash: `sha256:c56f8eb869096e79dd60f7ae050b026bb1c7a319771510465c050be13d8fa51e`
- `provider_attempts`: 4,328
- `routing_decisions`: 8,534
- `runtime_receipts`: 87,159
- `delegation_runs`: 8,073
- `artifact_records`: 3,977
- `external_outcomes`: 16,894
- `task_claims`: 8,380
- `model_routing_outcomes`: 0

High-value fields:

- provider/model/success/outcome/error class/duration/cost from `provider_attempts`
- route path, selected provider/model hint, confidence, candidate chain, trace id from `routing_decisions`
- receipt type, task id, trace id, status, side-effect key from `runtime_receipts`
- assigned-to/status/failure code/receipt hashable projection from `delegation_runs`

Excluded or restricted fields:

- `error_detail` requires redaction or hashing.
- JSON payload columns require field-aware redaction before training.

## Messages DB Metadata

`~/.dharma/db/messages.db`

- Hash: `sha256:864cfefa1c6d2cc1b34a35041b091b20764c0775edb6ec2f6a62e5bff6454282`
- `messages`: 992,069
- `events`: 13,231
- `artifacts`: 0
- `subscriptions`: 75

Hard exclusions:

- `messages.body`
- `events.payload`
- `artifacts.content`

Allowed v0 projections:

- message id hash
- sender/recipient agent ids, after agent-id allowlist check
- subject hash and optional redacted subject class
- timestamps
- status
- reply graph ids
- metadata after redaction

## Agent Memory Metadata

`~/.dharma/agent_memory/memories.db`

- Hash: `sha256:5e855b0f853d402fedf7cf07eddaba3e82a102b00ecb29eef2d5ea638cd8a611`
- `memories`: 347
- `shared_memories`: 0

Hard exclusions:

- `memories.content`
- `shared_memories.content`

Allowed v0 projections:

- agent id hash or allowlisted agent id;
- memory key hash;
- scope;
- timestamps;
- access count;
- embedding hash;
- lane.

## Source Schemas and Labels

Existing weak labels:

- semantic receipt `verdict`, `confidence`, `failure_type`
- provider attempt `success`, `outcome`, `error_class`
- route decision confidence and final outcome
- runtime receipt status
- Forge closeout, contrast, contamination, split, and budget fields
- human/council labels from council synthesis and future gold set

Label quality:

- semantic receipt labels are useful but self-referential telemetry, not proof;
- provider/routing outcomes are strong operational labels when correlated with actual artifact/test outcomes;
- human/council labels need adjudication and leakage controls;
- existing generic JSONL has unknown privacy/label quality and is quarantined.

## v0 Export Format

Export as JSONL where each row validates against `DHARMA_SEMANTIC_RECEIPT_GRAPH_V0.schema.json`.

Required graph record types:

- `agent_event`
- `provider_attempt`
- `routing_decision`
- `semantic_receipt`
- `verifier_outcome`
- `artifact_ref`
- `claim_evidence`
- `a2a_delivery`
- `eval_result`
- `human_or_council_label`

Each row must include:

- stable `record_id`
- `source_ref`
- `source_hash`
- `content_hash`
- timestamp
- provenance
- privacy tags
- evidence refs
- label fields
- redacted payload or hash-only payload

## Training Value Ranking

First export slice:

1. `reports/agentops/semantic_receipts`
2. `reports/a2a` metadata and redacted receipts
3. `~/.dharma/state/runtime.db` provider/routing/runtime tables
4. `~/.dharma/forge_v1` eval and measurement artifacts
5. gold labels from human/council adjudication

Defer:

- `~/.dharma/db/messages.db` raw bodies
- `~/.dharma/agent_memory` content
- `~/.dharma/traces` content until a trace schema/redaction review exists
- `~/.dharma/datasets` until redacted and relabelled
- provider payloads and raw error strings

## Required Next Data Command

```bash
./.venv/bin/python scripts/agentops/verifier_ranker_v0_inventory.py
```
