# Runtime Truth NATS Final Evidence - 2026-07-01

Review target: `runtime-truth-nats-2026-06`
Generated: `2026-07-01T00:37:10.860890Z`
Repo HEAD: `f1f3e140e3ddac4e5d246daaabb1d1d588bd04e2`

Reviewer model note: the council lane model is the critic model. The live model-backed handler under review is the system-under-test field recorded in the matrix: `ollama:glm-5.2:cloud`. Do not require the critic lane model to match the application handler model; require only that the handler model/provider recorded here is live, receipt-backed, and consistent across the matrix and semantic receipt.

Relevant git status:

```text
M dharma_swarm/a2a/a2a_bridge.py
 M dharma_swarm/a2a/a2a_server.py
 M dharma_swarm/a2a/nats_transport.py
 M dharma_swarm/operator_core/nats_live_contact.py
 M dharma_swarm/runtime_state.py
 M docs/governance/ACTIVE_TRACK.yaml
 M scripts/governance/check_nats_substrate_contract.py
 M scripts/governance/check_track_status.py
 M scripts/runtime/a2a_send.py
 M tests/test_nats_transport.py
?? reports/governance/nats_live_production_matrix/latest.json
?? reports/governance/runtime_truth_nats_compact_raw_evidence_2026-07-01.json
?? reports/governance/runtime_truth_nats_final_evidence_2026-07-01.md
?? scripts/governance/check_nats_live_production_evidence.py
?? scripts/governance/run_nats_live_production_matrix.py
?? tests/test_nats_substrate_contract.py
```

## Fresh Live Matrix

- Latest evidence: `reports/governance/nats_live_production_matrix/latest.json`
- Run evidence: `reports/governance/nats_live_production_matrix/nats-live-20260701T003355Z-3bc2492d/evidence.json`
- Run id: `nats-live-20260701T003355Z-3bc2492d`
- Generated at: `2026-07-01T00:35:04Z`
- Broker/profile: `nats://127.0.0.1:4222` / `local-live-jetstream`
- Streams: `DS_TASKS` and `DS_DLQ`
- Consumer: `a2a_task_handler`
- Handler provider/model: `ollama:glm-5.2:cloud`
- Semantic model receipt: `/Users/dhyana/dharma_swarm/reports/a2a/nats_live_production_matrix/nats-live-20260701T003355Z-3bc2492d/receipts/nats_live_20260701T003355Z_3bc2492d_happy_path_f0ef3e31.semantic_receipt.json`
- Compact raw evidence: `reports/governance/runtime_truth_nats_compact_raw_evidence_2026-07-01.json`
- Source fingerprints: `20` current files hashed into matrix

Rows:

- `topology`: status `pass`, msg `None`, task `None`, stream_seq `None`, consumer_seq `None`, ack `None/None`
- `happy_path`: status `pass`, msg `nmsg_863db763b1d8632560637390c00d14c1`, task `nats_live_20260701T003355Z_3bc2492d_happy_path_f0ef3e31`, stream_seq `78`, consumer_seq `140`, ack `ack/ack`
- `duplicate_path`: status `pass`, msg `nmsg_863db763b1d8632560637390c00d14c1`, task `nats_live_20260701T003355Z_3bc2492d_happy_path_f0ef3e31`, stream_seq `None`, consumer_seq `None`, ack `None/None`
- `publish_failure_path`: status `pass`, msg `nmsg_6c92d4073523a8f3369a2bed65e9c0ad`, task `nats_live_20260701T003355Z_3bc2492d_publish_failure_path_7ed9aacc`, stream_seq `79`, consumer_seq `141`, ack `ack/ack`
- `handler_failure_redelivery_path`: status `pass`, msg `nmsg_a6cd32becd61a86191f5e92cba29fe50`, task `nats_live_20260701T003355Z_3bc2492d_handler_failure_redelivery_path_9e20c9b7`, stream_seq `80`, consumer_seq `143`, ack `ack/ack`
- `stale_started_idempotency_path`: status `pass`, msg `nmsg_fc935526a9838ce3e15aa95cb696c56e`, task `nats_live_20260701T003355Z_3bc2492d_stale_started_idempotency_path_ca8b55fb`, stream_seq `81`, consumer_seq `144`, ack `ack/ack`
- `concurrent_duplicate_path`: status `pass`, msg `nmsg_d495a68472ad62f9c7ce52c81eda82b4`, task `nats_live_20260701T003355Z_3bc2492d_concurrent_duplicate_path_840a4501`, stream_seq `82`, consumer_seq `145`, ack `None/None`
- `ack_failure_path`: status `pass`, msg `nmsg_8caaa3cd7e0650e94ec7d9de13c53f1d`, task `nats_live_20260701T003355Z_3bc2492d_ack_failure_path_2d46bdff`, stream_seq `83`, consumer_seq `148`, ack `ack/ack`
- `max_deliver_path`: status `pass`, msg `nmsg_a019b923442e8295fd1429b1576a4abc`, task `nats_live_20260701T003355Z_3bc2492d_max_deliver_path_36eba8b7`, stream_seq `8`, consumer_seq `8`, ack `dlq/dlq`
- `dlq_failure_path`: status `pass`, msg `nmsg_cbdc16d425bf72cb7614439d076bf8b9`, task `nats_live_20260701T003355Z_3bc2492d_dlq_failure_path_949fecad`, stream_seq `None`, consumer_seq `None`, ack `nack/nack`
- `restart_path`: status `pass`, msg `nmsg_1add9fe4602fbd480ba145a8797d9209`, task `nats_live_20260701T003355Z_3bc2492d_restart_path_913a530c`, stream_seq `86`, consumer_seq `156`, ack `ack/ack`
- `compatibility_bypass_contract`: status `pass`, msg `None`, task `None`, stream_seq `None`, consumer_seq `None`, ack `None/None`
- `governance_negative_path`: status `pass`, msg `None`, task `None`, stream_seq `None`, consumer_seq `None`, ack `None/None`

## Production Path Proof

Happy-path production contract from raw JSON:

```json
{
  "compatibility_publishers_can_satisfy_production_gate": false,
  "consume_entrypoint": "dharma_swarm.a2a.nats_transport.A2ANatsTransport.consume_message",
  "consumer_class": "dharma_swarm.a2a.a2a_server.A2AServer",
  "consumer_require_execution_identity": true,
  "handler_contract": {
    "callable": "__main__.MatrixRunner.handler_model.<locals>.handler",
    "module": "__main__",
    "name": "handler",
    "qualname": "MatrixRunner.handler_model.<locals>.handler"
  },
  "publish_entrypoint": "dharma_swarm.a2a.nats_transport.A2ANatsTransport.publish_task",
  "transport_class": "dharma_swarm.a2a.nats_transport.A2ANatsTransport"
}
```

NATS headers from the delivered happy-path message, including broker duplicate key:

```json
{
  "Dharma-Causation-Id": "nats-live-20260701T003355Z-3bc2492d:happy_path:nats_live_20260701T003355Z_3bc2492d_happy_path_f0ef3e31",
  "Dharma-Correlation-Id": "nats-live-20260701T003355Z-3bc2492d:happy_path:nats_live_20260701T003355Z_3bc2492d_happy_path_f0ef3e31",
  "Dharma-Idempotency-Key": "nats-live-20260701T003355Z-3bc2492d:happy_path:nats_live_20260701T003355Z_3bc2492d_happy_path_f0ef3e31:idem",
  "Dharma-Nats-Schema": "dharma.nats.envelope.v1",
  "Dharma-Run-Id": "nats-live-20260701T003355Z-3bc2492d:happy_path:nats_live_20260701T003355Z_3bc2492d_happy_path_f0ef3e31",
  "Dharma-Task-Id": "nats_live_20260701T003355Z_3bc2492d_happy_path_f0ef3e31",
  "Dharma-Trace-Id": "nats-live-20260701T003355Z-3bc2492d:happy_path:nats_live_20260701T003355Z_3bc2492d_happy_path_f0ef3e31",
  "Nats-Msg-Id": "nmsg_863db763b1d8632560637390c00d14c1"
}
```

Happy-path envelope contract:

```json
{
  "actor": {
    "execution_agent": "nats-live-matrix-happy_path",
    "from_agent": "nats_live_matrix",
    "session_id": "nats-live-20260701T003355Z-3bc2492d",
    "to_agent": "nats_live_20260701T003355Z_3bc2492d_happy_path"
  },
  "causality": {
    "causation_id": "nats-live-20260701T003355Z-3bc2492d:happy_path:nats_live_20260701T003355Z_3bc2492d_happy_path_f0ef3e31",
    "correlation_id": "nats-live-20260701T003355Z-3bc2492d:happy_path:nats_live_20260701T003355Z_3bc2492d_happy_path_f0ef3e31",
    "message_id": "nmsg_863db763b1d8632560637390c00d14c1",
    "parent_span_id": "nats-live-20260701T003355Z-3bc2492d",
    "span_id": "nats-live-20260701T003355Z-3bc2492d:happy_path:nats_live_20260701T003355Z_3bc2492d_happy_path_f0ef3e31",
    "trace_id": "nats-live-20260701T003355Z-3bc2492d:happy_path:nats_live_20260701T003355Z_3bc2492d_happy_path_f0ef3e31"
  },
  "from_agent": "nats_live_matrix",
  "kind": "task",
  "message_id": "nmsg_863db763b1d8632560637390c00d14c1",
  "nats_msg_id": "nmsg_863db763b1d8632560637390c00d14c1",
  "payload_schema": "dharma.a2a.nats_task.v1",
  "schema": "dharma.nats.envelope.v1",
  "subject": "dharma.a2a.task.nats_live_20260701t003355z_3bc2492d_happy_path.matrix_happy_path",
  "to_agent": "nats_live_20260701T003355Z_3bc2492d_happy_path"
}
```

Happy-path broker metadata and acks:

```json
{
  "consume_ack": {
    "action": "ack",
    "duplicate": false,
    "error": "",
    "message_id": "nmsg_863db763b1d8632560637390c00d14c1",
    "receipt_id": "rr_8fbc7090952b437c",
    "status": "ack",
    "subject": "dharma.a2a.task.nats_live_20260701t003355z_3bc2492d_happy_path.matrix_happy_path",
    "task_id": "nats_live_20260701T003355Z_3bc2492d_happy_path_f0ef3e31"
  },
  "metadata": {
    "consumer_sequence": 140,
    "num_delivered": 1,
    "stream_sequence": 78,
    "timestamp": "2026-07-01T00:33:55.834859+00:00"
  },
  "publish_ack": {
    "action": "ack",
    "duplicate": false,
    "message_id": "nmsg_863db763b1d8632560637390c00d14c1",
    "receipt_id": "rr_b56799f817a84195",
    "seq": 78,
    "status": "ack",
    "stream": "DS_TASKS",
    "subject": "dharma.a2a.task.nats_live_20260701t003355z_3bc2492d_happy_path.matrix_happy_path",
    "task_id": "nats_live_20260701T003355Z_3bc2492d_happy_path_f0ef3e31"
  },
  "side_effect_count": 1
}
```

Semantic receipt metadata:

```json
{
  "provider": "ollama",
  "receipt_path": null,
  "requested_model": "glm-5.2:cloud",
  "response_model": "glm-5.2",
  "schema": "dharma.nats.live_matrix.semantic_receipt.v1",
  "started_at": "2026-07-01T00:33:55Z",
  "task_id": "nats_live_20260701T003355Z_3bc2492d_happy_path_f0ef3e31",
  "timestamp": "2026-07-01T00:33:57Z",
  "trace_id": "nats-live-20260701T003355Z-3bc2492d:happy_path:nats_live_20260701T003355Z_3bc2492d_happy_path_f0ef3e31",
  "usage": {
    "completion_tokens": 109,
    "prompt_tokens": 99,
    "total_tokens": 208
  }
}
```

## Failure Matrix Proof

Handler failure and redelivery:

```json
{
  "first_consume_ack": {
    "action": "nack",
    "dlq_failed": false,
    "duplicate": false,
    "error": "forced first handler failure",
    "message_id": "nmsg_a6cd32becd61a86191f5e92cba29fe50",
    "receipt_id": "rr_14354ff2779c4fa2",
    "runtime_receipts": [
      {
        "agent_id": "nats-live-matrix-handler_failure_redelivery_path",
        "causation_id": "nats-live-20260701T003355Z-3bc2492d:handler_failure_redelivery_path:nats_live_20260701T003355Z_3bc2492d_handler_failure_redelivery_path_9e20c9b7",
        "correlation_id": "nats-live-20260701T003355Z-3bc2492d:handler_failure_redelivery_path:nats_live_20260701T003355Z_3bc2492d_handler_failure_redelivery_path_9e20c9b7",
        "created_at": "2026-07-01T00:33:57.725763+00:00",
        "idempotency_key": "nats-live-20260701T003355Z-3bc2492d:handler_failure_redelivery_path:nats_live_20260701T003355Z_3bc2492d_handler_failure_redelivery_path_9e20c9b7:idem",
        "parent_run_id": "nats-live-20260701T003355Z-3bc2492d",
        "payload": {
          "action": "nack",
          "error": "forced first handler failure",
          "external_a2a_task_id": "nats_live_20260701T003355Z_3bc2492d_handler_failure_redelivery_path_9e20c9b7",
          "message_id": "nmsg_a6cd32becd61a86191f5e92cba29fe50",
          "operation_hash": "ce85632d1b7dae33f2cc379eeb5631f2d0ec8986d0c9131bcec77f0d79d06565",
          "subject": "dharma.a2a.task.nats_live_20260701t003355z_3bc2492d_handler_failure_redelivery_path.matrix_handler_failure_redelivery_path",
          "surface": "a2a.nats_transport.consume"
        },
        "receipt_id": "rr_14354ff2779c4fa2",
        "receipt_type": "nats_consume",
        "run_id": "nats-live-20260701T003355Z-3bc2492d:handler_failure_redelivery_path:nats_live_20260701T003355Z_3bc2492d_handler_failure_redelivery_path_9e20c9b7",
        "side_effect_key": "nats_consume:dharma.a2a.task.nats_live_20260701t003355z_3bc2492d_handler_failure_redelivery_path.matrix_handler_failure_redelivery_path:nats_live_20260701T003355Z_3bc2492d_handler_failure_redelivery_path_9e20c9b7",
        "status": "nack",
        "task_id": "nats_live_20260701T003355Z_3bc2492d_handler_failure_redelivery_path_9e20c9b7",
        "trace_id": "nats-live-20260701T003355Z-3bc2492d:handler_failure_redelivery_path:nats_live_20260701T003355Z_3bc2492d_handler_failure_redelivery_path_9e20c9b7"
      }
    ],
    "status": "nack",
    "subject": "dharma.a2a.task.nats_live_20260701t003355z_3bc2492d_handler_failure_redelivery_path.matrix_handler_failure_redelivery_path",
    "task_id": "nats_live_20260701T003355Z_3bc2492d_handler_failure_redelivery_path_9e20c9b7"
  },
  "first_delivery_metadata": {
    "consumer_sequence": 142,
    "num_delivered": 1,
    "stream_sequence": 80,
    "timestamp": "2026-07-01T00:33:57.668279+00:00"
  },
  "handler_attempts": 2,
  "production_path_contract": {
    "compatibility_publishers_can_satisfy_production_gate": false,
    "consume_entrypoint": "dharma_swarm.a2a.nats_transport.A2ANatsTransport.consume_message",
    "consumer_class": "dharma_swarm.a2a.a2a_server.A2AServer",
    "consumer_require_execution_identity": true,
    "handler_contract": {
      "callable": "__main__.MatrixRunner.handler_fail_then_success.<locals>.handler",
      "module": "__main__",
      "name": "handler",
      "qualname": "MatrixRunner.handler_fail_then_success.<locals>.handler"
    },
    "publish_entrypoint": "dharma_swarm.a2a.nats_transport.A2ANatsTransport.publish_task",
    "transport_class": "dharma_swarm.a2a.nats_transport.A2ANatsTransport"
  },
  "redelivery_metadata": {
    "consumer_sequence": 143,
    "num_delivered": 2,
    "stream_sequence": 80,
    "timestamp": "2026-07-01T00:33:57.668279+00:00"
  },
  "second_consume_ack": {
    "action": "ack",
    "duplicate": false,
    "error": "",
    "message_id": "nmsg_a6cd32becd61a86191f5e92cba29fe50",
    "receipt_id": "rr_0e1fc29dcd3f4d6f",
    "status": "ack",
    "subject": "dharma.a2a.task.nats_live_20260701t003355z_3bc2492d_handler_failure_redelivery_path.matrix_handler_failure_redelivery_path",
    "task_id": "nats_live_20260701T003355Z_3bc2492d_handler_failure_redelivery_path_9e20c9b7"
  },
  "status": "pass"
}
```

Ack failure surfacing:

```json
{
  "cleanup_ack": {
    "action": "ack",
    "duplicate": false,
    "error": "",
    "message_id": "nmsg_8caaa3cd7e0650e94ec7d9de13c53f1d",
    "receipt_id": "rr_49e0af1cfeda4a44",
    "status": "ack",
    "subject": "dharma.a2a.task.nats_live_20260701t003355z_3bc2492d_ack_failure_path.matrix_ack_failure_path",
    "task_id": "nats_live_20260701T003355Z_3bc2492d_ack_failure_path_2d46bdff"
  },
  "failed_ack": {
    "action": "nack",
    "dlq_failed": false,
    "duplicate": false,
    "error": "forced broker ack failure for matrix row",
    "message_id": "nmsg_8caaa3cd7e0650e94ec7d9de13c53f1d",
    "receipt_id": "rr_a26dcd93b12e4671",
    "runtime_receipts": [
      {
        "agent_id": "nats-live-matrix-ack_failure_path",
        "causation_id": "nats-live-20260701T003355Z-3bc2492d:ack_failure_path:nats_live_20260701T003355Z_3bc2492d_ack_failure_path_2d46bdff",
        "correlation_id": "nats-live-20260701T003355Z-3bc2492d:ack_failure_path:nats_live_20260701T003355Z_3bc2492d_ack_failure_path_2d46bdff",
        "created_at": "2026-07-01T00:33:58.252050+00:00",
        "idempotency_key": "nats-live-20260701T003355Z-3bc2492d:ack_failure_path:nats_live_20260701T003355Z_3bc2492d_ack_failure_path_2d46bdff:idem",
        "parent_run_id": "nats-live-20260701T003355Z-3bc2492d",
        "payload": {
          "a2a_status": "completed",
          "ack_contract": "consumer_ack_intent",
          "action": "ack_intent",
          "external_a2a_task_id": "nats_live_20260701T003355Z_3bc2492d_ack_failure_path_2d46bdff",
          "message_id": "nmsg_8caaa3cd7e0650e94ec7d9de13c53f1d",
          "operation_hash": "9d30524d7ede923d7c7a8022b5fde4f086e7aa2fab413a80a19073210e2a17e9",
          "spine_receipt_id": "a4b94b02-9f4c-46a5-81f1-06eb0cf284e1",
          "subject": "dharma.a2a.task.nats_live_20260701t003355z_3bc2492d_ack_failure_path.matrix_ack_failure_path",
          "surface": "a2a.nats_transport.consume"
        },
        "receipt_id": "rr_9f57cb6757714960",
        "receipt_type": "nats_consume",
        "run_id": "nats-live-20260701T003355Z-3bc2492d:ack_failure_path:nats_live_20260701T003355Z_3bc2492d_ack_failure_path_2d46bdff",
        "side_effect_key": "nats_consume:dharma.a2a.task.nats_live_20260701t003355z_3bc2492d_ack_failure_path.matrix_ack_failure_path:nats_live_20260701T003355Z_3bc2492d_ack_failure_path_2d46bdff",
        "status": "ack_intent",
        "task_id": "nats_live_20260701T003355Z_3bc2492d_ack_failure_path_2d46bdff",
        "trace_id": "nats-live-20260701T003355Z-3bc2492d:ack_failure_path:nats_live_20260701T003355Z_3bc2492d_ack_failure_path_2d46bdff"
      },
      {
        "agent_id": "nats-live-matrix-ack_failure_path",
        "causation_id": "nats-live-20260701T003355Z-3bc2492d:ack_failure_path:nats_live_20260701T003355Z_3bc2492d_ack_failure_path_2d46bdff",
        "correlation_id": "nats-live-20260701T003355Z-3bc2492d:ack_failure_path:nats_live_20260701T003355Z_3bc2492d_ack_failure_path_2d46bdff",
        "created_at": "2026-07-01T00:33:58.256257+00:00",
        "idempotency_key": "nats-live-20260701T003355Z-3bc2492d:ack_failure_path:nats_live_20260701T003355Z_3bc2492d_ack_failure_path_2d46bdff:idem",
        "parent_run_id": "nats-live-20260701T003355Z-3bc2492d",
        "payload": {
          "action": "nack",
          "error": "forced broker ack failure for matrix row",
          "external_a2a_task_id": "nats_live_20260701T003355Z_3bc2492d_ack_failure_path_2d46bdff",
          "message_id": "nmsg_8caaa3cd7e0650e94ec7d9de13c53f1d",
          "operation_hash": "9d30524d7ede923d7c7a8022b5fde4f086e7aa2fab413a80a19073210e2a17e9",
          "subject": "dharma.a2a.task.nats_live_20260701t003355z_3bc2492d_ack_failure_path.matrix_ack_failure_path",
          "surface": "a2a.nats_transport.consume"
        },
        "receipt_id": "rr_a26dcd93b12e4671",
        "receipt_type": "nats_consume",
        "run_id": "nats-live-20260701T003355Z-3bc2492d:ack_failure_path:nats_live_20260701T003355Z_3bc2492d_ack_failure_path_2d46bdff",
        "side_effect_key": "nats_consume:dharma.a2a.task.nats_live_20260701t003355z_3bc2492d_ack_failure_path.matrix_ack_failure_path:nats_live_20260701T003355Z_3bc2492d_ack_failure_path_2d46bdff",
        "status": "nack",
        "task_id": "nats_live_20260701T003355Z_3bc2492d_ack_failure_path_2d46bdff",
        "trace_id": "nats-live-20260701T003355Z-3bc2492d:ack_failure_path:nats_live_20260701T003355Z_3bc2492d_ack_failure_path_2d46bdff"
      }
    ],
    "status": "nack",
    "subject": "dharma.a2a.task.nats_live_20260701t003355z_3bc2492d_ack_failure_path.matrix_ack_failure_path",
    "task_id": "nats_live_20260701T003355Z_3bc2492d_ack_failure_path_2d46bdff"
  },
  "failure_injection": "message.ack raised before broker ack; original was nacked and redelivered",
  "production_path_contract": {
    "compatibility_publishers_can_satisfy_production_gate": false,
    "consume_entrypoint": "dharma_swarm.a2a.nats_transport.A2ANatsTransport.consume_message",
    "consumer_class": "dharma_swarm.a2a.a2a_server.A2AServer",
    "consumer_require_execution_identity": true,
    "handler_contract": {
      "callable": "__main__.MatrixRunner.handler_success.<locals>.handler",
      "module": "__main__",
      "name": "handler",
      "qualname": "MatrixRunner.handler_success.<locals>.handler"
    },
    "publish_entrypoint": "dharma_swarm.a2a.nats_transport.A2ANatsTransport.publish_task",
    "transport_class": "dharma_swarm.a2a.nats_transport.A2ANatsTransport"
  },
  "redelivery_metadata": {
    "consumer_sequence": 148,
    "num_delivered": 2,
    "stream_sequence": 83,
    "timestamp": "2026-07-01T00:33:58.195355+00:00"
  },
  "status": "pass"
}
```

MaxDeliver to typed DLQ:

```json
{
  "deliveries": [
    {
      "consume_ack": {
        "action": "nack",
        "dlq_failed": false,
        "duplicate": false,
        "error": "forced handler failure for max_deliver_path",
        "message_id": "nmsg_a019b923442e8295fd1429b1576a4abc",
        "receipt_id": "rr_e8d3c125778b4666",
        "runtime_receipts": [
          {
            "agent_id": "nats-live-matrix-max_deliver_path",
            "causation_id": "nats-live-20260701T003355Z-3bc2492d:max_deliver_path:nats_live_20260701T003355Z_3bc2492d_max_deliver_path_36eba8b7",
            "correlation_id": "nats-live-20260701T003355Z-3bc2492d:max_deliver_path:nats_live_20260701T003355Z_3bc2492d_max_deliver_path_36eba8b7",
            "created_at": "2026-07-01T00:33:58.426493+00:00",
            "idempotency_key": "nats-live-20260701T003355Z-3bc2492d:max_deliver_path:nats_live_20260701T003355Z_3bc2492d_max_deliver_path_36eba8b7:idem",
            "parent_run_id": "nats-live-20260701T003355Z-3bc2492d",
            "payload": {
              "action": "nack",
              "error": "forced handler failure for max_deliver_path",
              "external_a2a_task_id": "nats_live_20260701T003355Z_3bc2492d_max_deliver_path_36eba8b7",
              "message_id": "nmsg_a019b923442e8295fd1429b1576a4abc",
              "operation_hash": "1873d88581b9380dedb8e32f8a8c4bde234e25fe9a01727c0a9675713521ef82",
              "subject": "dharma.a2a.task.nats_live_20260701t003355z_3bc2492d_max_deliver_path.matrix_max_deliver_path",
              "surface": "a2a.nats_transport.consume"
            },
            "receipt_id": "rr_e8d3c125778b4666",
            "receipt_type": "nats_consume",
            "run_id": "nats-live-20260701T003355Z-3bc2492d:max_deliver_path:nats_live_20260701T003355Z_3bc2492d_max_deliver_path_36eba8b7",
            "side_effect_key": "nats_consume:dharma.a2a.task.nats_live_20260701t003355z_3bc2492d_max_deliver_path.matrix_max_deliver_path:nats_live_20260701T003355Z_3bc2492d_max_deliver_path_36eba8b7",
            "status": "nack",
            "task_id": "nats_live_20260701T003355Z_3bc2492d_max_deliver_path_36eba8b7",
            "trace_id": "nats-live-20260701T003355Z-3bc2492d:max_deliver_path:nats_live_20260701T003355Z_3bc2492d_max_deliver_path_36eba8b7"
          }
        ],
        "status": "nack",
        "subject": "dharma.a2a.task.nats_live_20260701t003355z_3bc2492d_max_deliver_path.matrix_max_deliver_path",
        "task_id": "nats_live_20260701T003355Z_3bc2492d_max_deliver_path_36eba8b7"
      },
      "metadata": {
        "consumer_sequence": 149,
        "num_delivered": 1,
        "stream_sequence": 84,
        "timestamp": "2026-07-01T00:33:58.372061+00:00"
      }
    },
    {
      "consume_ack": {
        "action": "nack",
        "dlq_failed": false,
        "duplicate": false,
        "error": "forced handler failure for max_deliver_path",
        "message_id": "nmsg_a019b923442e8295fd1429b1576a4abc",
        "receipt_id": "rr_11b5fc9f8098455a",
        "runtime_receipts": [
          {
            "agent_id": "nats-live-matrix-max_deliver_path",
            "causation_id": "nats-live-20260701T003355Z-3bc2492d:max_deliver_path:nats_live_20260701T003355Z_3bc2492d_max_deliver_path_36eba8b7",
            "correlation_id": "nats-live-20260701T003355Z-3bc2492d:max_deliver_path:nats_live_20260701T003355Z_3bc2492d_max_deliver_path_36eba8b7",
            "created_at": "2026-07-01T00:33:58.426493+00:00",
            "idempotency_key": "nats-live-20260701T003355Z-3bc2492d:max_deliver_path:nats_live_20260701T003355Z_3bc2492d_max_deliver_path_36eba8b7:idem",
            "parent_run_id": "nats-live-20260701T003355Z-3bc2492d",
            "payload": {
              "action": "nack",
              "error": "forced handler failure for max_deliver_path",
              "external_a2a_task_id": "nats_live_20260701T003355Z_3bc2492d_max_deliver_path_36eba8b7",
              "message_id": "nmsg_a019b923442e8295fd1429b1576a4abc",
              "operation_hash": "1873d88581b9380dedb8e32f8a8c4bde234e25fe9a01727c0a9675713521ef82",
              "subject": "dharma.a2a.task.nats_live_20260701t003355z_3bc2492d_max_deliver_path.matrix_max_deliver_path",
              "surface": "a2a.nats_transport.consume"
            },
            "receipt_id": "rr_e8d3c125778b4666",
            "receipt_type": "nats_consume",
            "run_id": "nats-live-20260701T003355Z-3bc2492d:max_deliver_path:nats_live_20260701T003355Z_3bc2492d_max_deliver_path_36eba8b7",
            "side_effect_key": "nats_consume:dharma.a2a.task.nats_live_20260701t003355z_3bc2492d_max_deliver_path.matrix_max_deliver_path:nats_live_20260701T003355Z_3bc2492d_max_deliver_path_36eba8b7",
            "status": "nack",
            "task_id": "nats_live_20260701T003355Z_3bc2492d_max_deliver_path_36eba8b7",
            "trace_id": "nats-live-20260701T003355Z-3bc2492d:max_deliver_path:nats_live_20260701T003355Z_3bc2492d_max_deliver_path_36eba8b7"
          },
          {
            "agent_id": "nats-live-matrix-max_deliver_path",
            "causation_id": "nats-live-20260701T003355Z-3bc2492d:max_deliver_path:nats_live_20260701T003355Z_3bc2492d_max_deliver_path_36eba8b7",
            "correlation_id": "nats-live-20260701T003355Z-3bc2492d:max_deliver_path:nats_live_20260701T003355Z_3bc2492d_max_deliver_path_36eba8b7",
            "created_at": "2026-07-01T00:33:58.510305+00:00",
            "idempotency_key": "nats-live-20260701T003355Z-3bc2492d:max_deliver_path:nats_live_20260701T003355Z_3bc2492d_max_deliver_path_36eba8b7:idem",
            "parent_run_id": "nats-live-20260701T003355Z-3bc2492d",
            "payload": {
              "action": "nack",
              "error": "forced handler failure for max_deliver_path",
              "external_a2a_task_id": "nats_live_20260701T003355Z_3bc2492d_max_deliver_path_36eba8b7",
              "message_id": "nmsg_a019b923442e8295fd1429b1576a4abc",
              "operation_hash": "1873d88581b9380dedb8e32f8a8c4bde234e25fe9a01727c
```

DLQ publish failure remains operator-visible:

```json
{
  "failure_injection": "DLQ publish raised at MaxDeliver; original was not acked and remains beyond the consumer ack floor",
  "final_ack": {
    "action": "nack",
    "dlq_failed": true,
    "duplicate": false,
    "error": "forced handler failure for dlq_failure_path",
    "message_id": "nmsg_cbdc16d425bf72cb7614439d076bf8b9",
    "receipt_id": "rr_22fb99cedf9d4b70",
    "runtime_receipts": [
      {
        "agent_id": "nats-live-matrix-dlq_failure_path",
        "causation_id": "nats-live-20260701T003355Z-3bc2492d:dlq_failure_path:nats_live_20260701T003355Z_3bc2492d_dlq_failure_path_949fecad",
        "correlation_id": "nats-live-20260701T003355Z-3bc2492d:dlq_failure_path:nats_live_20260701T003355Z_3bc2492d_dlq_failure_path_949fecad",
        "created_at": "2026-07-01T00:33:58.703982+00:00",
        "idempotency_key": "nats-live-20260701T003355Z-3bc2492d:dlq_failure_path:nats_live_20260701T003355Z_3bc2492d_dlq_failure_path_949fecad:idem",
        "parent_run_id": "nats-live-20260701T003355Z-3bc2492d",
        "payload": {
          "action": "nack",
          "error": "forced handler failure for dlq_failure_path",
          "external_a2a_task_id": "nats_live_20260701T003355Z_3bc2492d_dlq_failure_path_949fecad",
          "message_id": "nmsg_cbdc16d425bf72cb7614439d076bf8b9",
          "operation_hash": "50e8cd3efcba434a57c7f33255b06b48d949552bdb1b00a15a9de59e52e24574",
          "subject": "dharma.a2a.task.nats_live_20260701t003355z_3bc2492d_dlq_failure_path.matrix_dlq_failure_path",
          "surface": "a2a.nats_transport.consume"
        },
        "receipt_id": "rr_8b875fdce26742bc",
        "receipt_type": "nats_consume",
        "run_id": "nats-live-20260701T003355Z-3bc2492d:dlq_failure_path:nats_live_20260701T003355Z_3bc2492d_dlq_failure_path_949fecad",
        "side_effect_key": "nats_consume:dharma.a2a.task.nats_live_20260701t003355z_3bc2492d_dlq_failure_path.matrix_dlq_failure_path:nats_live_20260701T003355Z_3bc2492d_dlq_failure_path_949fecad",
        "status": "nack",
        "task_id": "nats_live_20260701T003355Z_3bc2492d_dlq_failure_path_949fecad",
        "trace_id": "nats-live-20260701T003355Z-3bc2492d:dlq_failure_path:nats_live_20260701T003355Z_3bc2492d_dlq_failure_path_949fecad"
      },
      {
        "agent_id": "nats-live-matrix-dlq_failure_path",
        "causation_id": "nats-live-20260701T003355Z-3bc2492d:dlq_failure_path:nats_live_20260701T003355Z_3bc2492d_dlq_failure_path_949fecad",
        "correlation_id": "nats-live-20260701T003355Z-3bc2492d:dlq_failure_path:nats_live_20260701T003355Z_3bc2492d_dlq_failure_path_949fecad",
        "created_at": "2026-07-01T00:33:58.787568+00:00",
        "idempotency_key": "nats-live-20260701T003355Z-3bc2492d:dlq_failure_path:nats_live_20260701T003355Z_3bc2492d_dlq_failure_path_949fecad:idem",
        "parent_run_id": "nats-live-20260701T003355Z-3bc2492d",
        "payload": {
          "action": "nack",
          "error": "forced handler failure for dlq_failure_path",
          "external_a2a_task_id": "nats_live_20260701T003355Z_3bc2492d_dlq_failure_path_949fecad",
          "message_id": "nmsg_cbdc16d425bf72cb7614439d076bf8b9",
          "operation_hash": "50e8cd3efcba434a57c7f33255b06b48d949552bdb1b00a15a9de59e52e24574",
          "retry_of_result_receipt_id": "rr_8b875fdce26742bc",
          "retry_of_side_effect_key": "nats_consume:dharma.a2a.task.nats_live_20260701t003355z_3bc2492d_dlq_failure_path.matrix_dlq_failure_path:nats_live_20260701T003355Z_3bc2492d_dlq_failure_path_949fecad",
          "retry_of_status": "failed",
          "subject": "dharma.a2a.task.nats_live_20260701t003355z_3bc2492d_dlq_failure_path.matrix_dlq_failure_path",
          "surface": "a2a.nats_transport.consume"
        },
        "receipt_id": "rr_6c7db65b1eab4be6",
        "receipt_type": "nats_consume",
        "run_id": "nats-live-20260701T003355Z-3bc2492d:dlq_failure_path:nats_live_20260701T003355Z_3bc2492d_dlq_failure_path_949fecad",
        "side_effect_key": "nats_consume:dharma.a2a.task.nats_live_20260701t003355z_3bc2492d_dlq_failure_path.matrix_dlq_failure_path:nats_live_20260701T003355Z_3bc2492d_dlq_failure_path_949fecad:retry:d31adb3d93c8",
        "status": "nack",
        "task_id": "nats_live_20260701T003355Z_3bc2492d_dlq_failure_path_949fecad",
        "trace_id": "nats-live-20260701T003355Z-3bc2492d:dlq_failure_path:nats_live_20260701T003355Z_3bc2492d_dlq_failure_path_949fecad"
      },
      {
        "agent_id": "nats-live-matrix-dlq_failure_path",
        "causation_id": "nats-live-20260701T003355Z-3bc2492d:dlq_failure_path:nats_live_20260701T003355Z_3bc2492d_dlq_failure_path_949fecad",
        "correlation_id": "nats-live-20260701T003355Z-3bc2492d:dlq_failure_path:nats_live_20260701T003355Z_3bc2492d_dlq_failure_path_949fecad",
        "created_at": "2026-07-01T00:33:58.862065+00:00",
        "idempotency_key": "nats-live-20260701T003355Z-3bc2492d:dlq_failure_path:nats_live_20260701T003355Z_3bc2492d_dlq_failure_path_949fecad:idem",
        "parent_run_id": "nats-live-20260701T003355Z-3bc2492d",
        "payload": {
          "action": "nack",
          "dlq_error": "forced DLQ publish failure for matrix row",
          "error": "forced handler failure for dlq_failure_path",
          "external_a2a_task_id": "nats_live_20260701T003355Z_3bc2492d_dlq_failure_path_949fecad",
          "message_id": "nmsg_cbdc16d425bf72cb7614439d076bf8b9",
          "operation_hash": "50e8cd3efcba434a57c7f33255b06b48d949552bdb1b00a15a9de59e52e24574",
          "retry_of_result_receipt_id": "rr_8b875fdce26742bc",
          "retry_of_side_effect_key": "nats_consume:dharma.a2a.task.nats_live_20260701t003355z_3bc2492d_dlq_failure_path.matrix_dlq_failure_path:nats_live_20260701T003355Z_3bc2492d_dlq_failure_path_949fecad",
          "retry_of_status": "failed",
          "subject": "dharma.a2a.task.nats_live_20260701t003355z_3bc2492d_dlq_failure_path.matrix_dlq_failure_path",
          "surface": "a2a.nats_transport.consume"
        },
        "receipt_id": "rr_b7678f6fb6244605",
        "receipt_type": "nats_consume",
        "run_id": "nats-live-20260701T003355Z-3bc2492d:dlq_failure_path:nats_live_20260701T003355Z_3bc2492d_dlq_failure_path_949fecad",
        "side_effect_key": "nats_consume:dharma.a2a.task.nats_live_20260701t003355z_3bc2492d_dlq_failure_path.matrix_dlq_failure_path:nats_live_20260701T003355Z_3bc2492d_dlq_failure_path_949fecad:retry:bdb99ba8b6d2",
        "status": "dlq_failed",
        "task_id": "nats_live_20260701T003355Z_3bc2492d_dlq_failure_path_949fecad",
        "trace_id": "nats-live-20260701T003355Z-3bc2492d:dlq_failure_path:nats_live_20260701T003355Z_3bc2492d_dlq_failure_path_949fecad"
      },
      {
        "agent_id": "nats-live-matrix-dlq_failure_path",
        "causation_id": "nats-live-20260701T003355Z-3bc2492d:dlq_failure_path:nats_live_20260701T003355Z_3bc2492d_dlq_failure_path_949fecad",
        "correlation_id": "nats-live-20260701T003355Z-3bc2492d:dlq_failure_path:nats_live_20260701T003355Z_3bc2492d_dlq_failure_path_949fecad",
        "created_at": "2026-07-01T00:33:58.866016+00:00",
        "idempotency_key": "nats-live-20260701T003355Z-3bc2492d:dlq_failure_path:nats_live_20260701T003355Z_3bc2492d_dlq_failure_path_949fecad:idem",
        "parent_run_id": "nats-live-20260701T003355Z-3bc2492d",
        "payload": {
          "action": "nack",
          "error": "forced handler failure for dlq_failure_path",
          "external_a2a_task_id": "nats_live_20260701T003355Z_3bc2492d_dlq_failure_path_949fecad",
          "message_id": "nmsg_cbdc16d425bf72cb7614439d076bf8b9",
          "operation_hash": "50e8cd3efcba434a57c7f33255b06b48d949552bdb1b00a15a9de59e52e24574",
          "retry_of_result_receipt_id": "rr_8b875fdce26742bc",
          "retry_of_side_effect_key": "nats_consume:dharma.a2a.task.nats_live_20260701t003355z_3bc2492d_dlq_failure_path.matrix_dlq_failure_path:nats_live_20260701T003355Z_3bc2492d_dlq_failure_path_949fecad",
          "retry_of_status": "failed",
          "subject": "dharma.a2a.task.nats_live_20260701t003355z_3bc2492d_dlq_failure_path.matrix_dlq_failure_path",
          "surface": "a2a.nats_transport.consume"
        },
        "receipt_id": "rr_22fb99cedf9d4b70",
        "receipt_type": "nats_consume",
        "run_id": "nats-live-20260701T003355Z-3bc2492d:dlq_failure_path:nats_live_20260701T003355Z_3bc2492d_dlq_failure_path_949fecad",
        "side_effect_key": "nats_consume:dharma.a2a.task.nats_live_20260701t003355z_3bc2492d_dlq_failure_path.matrix_dlq_failure_path:nats_live_20260701T003355Z_3bc2492d_dlq_failure_path_949fecad:retry:bdb99ba8b6d2",
        "status": "nack",
        "task_id": "nats_live_20260701T003355Z_3bc2492d_dlq_failure_path_949fecad",
        "trace_id": "nats-live-20260701T003355Z-3bc2492d:dlq_failure_path:nats_live_20260701T003355Z_3bc2492d_dlq_failure_path_949fecad"
      }
    ],
    "status": "nack",
    "subject": "dharma.a2a.task.nats_live_20260701t003355z_3bc2492d_dlq_failure_path.matrix_dlq_failure_path",
    "task_id": "nats_live_20260701T003355Z_3bc2492d_dlq_failure_path_949fecad"
  },
  "operator_visible": true,
  "operator_visible_state": {
    "ack_floor": {
      "consumer_seq": 151,
      "last_active": "2026-07-01T00:33:58.599882+00:00",
      "stream_seq": 84
    },
    "delivered": {
      "consumer_seq": 154,
      "last_active": "2026-07-01T00:33:58.811414+00:00",
      "stream_seq": 85
    },
    "final_stream_sequence": 85,
    "num_ack_pending": 1,
    "num_pending": 0,
    "num_redelivered": 11
  },
  "production_path_contract": {
    "compatibility_publishers_can_satisfy_production_gate": false,
    "consume_entrypoint": "dharma_swarm.a2a.nats_transport.A2ANatsTransport.consume_message",
    "consumer_class": "dharma_swarm.a2a.a2a_server.A2AServer",
    "consumer_require_execution_identity": true,
    "handler_contract": {
      "callable": "__main__.MatrixRunner.handler_always_fail.<locals>.handler",
      "module": "__main__",
      "name": "handler",
      "qualname": "MatrixRunner.handler_always_fail.<locals>.handler"
    },
    "publish_entrypoint": "dharma_swarm.a2a.nats_transport.A2ANatsTransport.publish_task",
    "transport_class": "dharma_swarm.a2a.nats_transport.A2ANatsTransport"
  },
  "status": "pass"
}
```

Restart recovery:

```json
{
  "cleanup_ack": {
    "action": "ack",
    "duplicate": false,
    "error": "",
    "message_id": "nmsg_1add9fe4602fbd480ba145a8797d9209",
    "receipt_id": "rr_a7840b39b80445b1",
    "status": "ack",
    "subject": "dharma.a2a.task.nats_live_20260701t003355z_3bc2492d_restart_path.matrix_restart_path",
    "task_id": "nats_live_20260701T003355Z_3bc2492d_restart_path_913a530c"
  },
  "first_delivery_metadata": {
    "consumer_sequence": 155,
    "num_delivered": 1,
    "stream_sequence": 86,
    "timestamp": "2026-07-01T00:33:58.919767+00:00"
  },
  "production_path_contract": {
    "compatibility_publishers_can_satisfy_production_gate": false,
    "consume_entrypoint": "dharma_swarm.a2a.nats_transport.A2ANatsTransport.consume_message",
    "consumer_class": "dharma_swarm.a2a.a2a_server.A2AServer",
    "consumer_require_execution_identity": true,
    "handler_contract": {
      "callable": "__main__.MatrixRunner.handler_success.<locals>.handler",
      "module": "__main__",
      "name": "handler",
      "qualname": "MatrixRunner.handler_success.<locals>.handler"
    },
    "publish_entrypoint": "dharma_swarm.a2a.nats_transport.A2ANatsTransport.publish_task",
    "transport_class": "dharma_swarm.a2a.nats_transport.A2ANatsTransport"
  },
  "redelivery_metadata": {
    "consumer_sequence": 156,
    "num_delivered": 2,
    "stream_sequence": 86,
    "timestamp": "2026-07-01T00:33:58.919767+00:00"
  },
  "restart_wait_seconds": 65,
  "status": "pass"
}
```

## Bypass And Governance Proof

Compatibility publishers cannot satisfy the production gate:

```json
{
  "agent_id": "governance",
  "broker_url": "nats://127.0.0.1:4222",
  "canonical_runtime_truth_nats_task_path": "dharma_swarm.a2a.nats_transport.A2ANatsTransport.publish_task",
  "checks": {
    "a2a_send_declares_gate_ineligible": true,
    "a2a_send_marks_noncanonical": true,
    "a2a_send_names_canonical_transport": true,
    "domain_reply_worker_does_not_mint_nats_envelope_v1": true,
    "domain_reply_worker_uses_domain_receipt_schema": true
  },
  "compatibility_publishers_can_satisfy_production_gate": false,
  "compatibility_surfaces": [
    {
      "classification": "operator_contact_compatibility_only",
      "may_satisfy_production_gate": false,
      "path": "scripts/runtime/a2a_send.py"
    },
    {
      "classification": "domain_reply_publisher_not_task_transport",
      "may_mint_nats_envelope_v1": false,
      "may_satisfy_production_gate": false,
      "path": "scripts/runtime/a2a_domain_reply_worker.py"
    }
  ],
  "consumer_name": "a2a_task_handler",
  "gate_enforced_by": [
    "scripts/governance/check_nats_substrate_contract.py",
    "scripts/governance/check_nats_live_production_evidence.py",
    "docs/governance/ACTIVE_TRACK.yaml:nats_live_production_evidence_fresh"
  ],
  "message_id": null,
  "model_provider_id": "ollama:glm-5.2:cloud",
  "name": "compatibility_bypass_contract",
  "status": "pass",
  "stream_name": "DS_TASKS",
  "task_id": null,
  "timestamp": "2026-07-01T00:35:04Z",
  "trace_id": "nats-live-20260701T003355Z-3bc2492d"
}
```

Governance negative tamper path:

```json
{
  "expected_failure_contains": "missing required rows",
  "negative_return_code": 1,
  "negative_stderr": "NATS_LIVE_PRODUCTION_EVIDENCE_FAILED EvidenceError: missing required rows: ['happy_path', 'governance_negative_path']\n",
  "negative_stdout": "",
  "status": "pass",
  "tamper_description": "removed the required happy_path row from otherwise fresh live evidence",
  "tampered_row_removed": "happy_path"
}
```

## Verification Commands

- `./.venv/bin/python -m dharma_swarm.operator_core.nats_live_contact --endpoint nats://127.0.0.1:4222 --timeout 2` -> rc `0`; `NATS_LIVE`, `ack_tier=DELIVERED_TO_CONSUMER`.
- `/Users/dhyana/dharma_swarm/.venv/bin/python /Users/dhyana/dharma_swarm/scripts/governance/run_nats_live_production_matrix.py --endpoint nats://127.0.0.1:4222` -> rc `0`; evidence `/Users/dhyana/dharma_swarm/reports/governance/nats_live_production_matrix/nats-live-20260701T003355Z-3bc2492d/evidence.json`; status `pass`.
- `./.venv/bin/python scripts/governance/check_nats_live_production_evidence.py --max-age-hours 24` -> rc `0`; `NATS_LIVE_PRODUCTION_EVIDENCE_OK`.
- `pytest -q tests/test_nats_transport.py tests/test_nats_substrate_contract.py tests/test_a2a_cloud_contact.py tests/test_a2a_send.py` -> rc `0`; `47 passed in 3.76s`.
- `make nats-substrate-contract` -> rc `0`; `NATS_CONTRACT_OK`; live evidence OK; `73 passed in 4.24s`.
- `./.venv/bin/python scripts/governance/check_track_status.py` -> rc `0`; `runtime-truth-nats-2026-06 all 3 completion criteria pass - SHIPPABLE`.

## Source Hashes

- `dharma_swarm/a2a/a2a_bridge.py` sha256 `b4a138c3c9647258b8cd30fecd6df4ffedfce8ca3a4e05f3d7baec21b4e9602b` mtime `2026-07-01T00:14:16.254573Z` size `17457`
- `dharma_swarm/a2a/a2a_cloud_contact.py` sha256 `8e67b78b4c5e815308b4f64632de641aece34b2f27d53cbcc5ff3a4caebc050e` mtime `2026-06-18T06:18:41.695697Z` size `6668`
- `dharma_swarm/a2a/a2a_server.py` sha256 `4b7cb34a2a96dc5ea53d5ada1df0110dd483ad4cf5602c757b5b2fc84f75d2cf` mtime `2026-07-01T00:14:07.316150Z` size `26197`
- `dharma_swarm/a2a/nats_transport.py` sha256 `e90b1eb0b1bcfecf38f263ee8d97a37ae08bbda93d39e1f9d5bb40d14506baae` mtime `2026-07-01T00:09:51.253671Z` size `39502`
- `dharma_swarm/operator_core/nats_live_contact.py` sha256 `c728f8064477894295407ea7b32727ae4f5a0c57e932836965afceecf2bac202` mtime `2026-06-30T23:17:52.740819Z` size `8126`
- `dharma_swarm/operator_core/nats_substrate_status.py` sha256 `dde9020f72ca67a1ac99296e366192ced80297f03c617a71c28c61323d302446` mtime `2026-06-13T03:03:39.462080Z` size `5687`
- `dharma_swarm/runtime_state.py` sha256 `25e40a99d46280bb064d56c06ddfbeb7421326e4bff6eab5aaee06da9d7c042f` mtime `2026-07-01T00:10:12.455725Z` size `163007`
- `docs/governance/ACTIVE_TRACK.yaml` sha256 `55284295b504d05186f2e433d6d443d512467f24ab40d09fccab05abb517fc81` mtime `2026-07-01T00:21:26.115999Z` size `143176`
- `docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md` sha256 `1fd6fa6704dd557172ad0851e781bf179248d7053c7417aee704110af5b8ff9c` mtime `2026-06-13T03:03:39.496441Z` size `14581`
- `scripts/governance/check_nats_live_production_evidence.py` sha256 `fc274e657daf025d203b5fc9607cea769c213c78ef777e82e7c81cda68d2b9c2` mtime `2026-07-01T00:31:11.571210Z` size `20243`
- `scripts/governance/check_nats_substrate_contract.py` sha256 `a6a2207b21b907a742bcd11cfa0ea0410c4748a3f5bd79029d1ffa1ad89e7bb8` mtime `2026-07-01T00:31:20.220053Z` size `17241`
- `scripts/governance/check_track_status.py` sha256 `040927305ba68bd320fdfa5a11bab6297809e69eed68bc9a253c76d4dc6d67c8` mtime `2026-06-30T22:43:46.606978Z` size `45240`
- `scripts/governance/run_nats_live_production_matrix.py` sha256 `f17ce917c7f724cb3bd2487002308c899f61302a30430e1517ca59e18fe97317` mtime `2026-07-01T00:33:50.481642Z` size `56868`
- `scripts/runtime/a2a_domain_reply_worker.py` sha256 `b299a848ee65c5c7ba6625673993b3e0b1a0820b573f85c9bef1d8b329af8ead` mtime `2026-06-26T02:56:08.699198Z` size `23376`
- `scripts/runtime/a2a_inbox_bridge.py` sha256 `b3670b0f8aace08d78bea741eaefbd1d43f0c2ea3b2b9ab52195ee2ca521883c` mtime `2026-06-26T02:56:08.699261Z` size `17623`
- `scripts/runtime/a2a_reply_capture.py` sha256 `78f83ccc95070a817aaf3dc838b133accf07fbf64728542674f895e9bf294963` mtime `2026-06-26T02:56:08.699327Z` size `16757`
- `scripts/runtime/a2a_send.py` sha256 `4d9fc3ee3deabd751f5eb07556529a743687c34b48dc6fc4c9469c43694a6154` mtime `2026-06-30T23:45:15.723367Z` size `32813`
- `tests/test_a2a_cloud_contact.py` sha256 `e618718df674c91c8ecb8b445a62f1be22cde72b68dff8b39cdb851d602188ca` mtime `2026-06-25T02:41:20.120948Z` size `6368`
- `tests/test_nats_substrate_contract.py` sha256 `ff08ffb46abbf0abd822fd3c3e1909e31595dfa3a32eb551b6f89afda5b5d7fd` mtime `2026-07-01T00:31:40.711724Z` size `8072`
- `tests/test_nats_transport.py` sha256 `a815b9144cf4282bd2592f4c62fa08fdec106680b4ddd6e0751a8de83a0d4831` mtime `2026-07-01T00:10:26.796742Z` size `24635`

## Boundary

This is live JetStream evidence against `nats://127.0.0.1:4222` using profile `local-live-jetstream`. It is not filesystem-only, fake-JetStream-only, or stale-summary evidence. The raw matrix carries source hashes; `check_nats_live_production_evidence.py` rejects evidence if any source fingerprint is stale, if production path metadata is missing, if `Nats-Msg-Id` is absent, if compatibility publishers can satisfy the gate, or if the governance-negative tamper path does not fail.
