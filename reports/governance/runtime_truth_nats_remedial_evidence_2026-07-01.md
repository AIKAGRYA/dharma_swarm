# Runtime Truth NATS Remedial Evidence - 2026-07-01

Generated: `2026-07-01T03:40:22Z`
Run id: `nats-live-20260701T033809Z-456ba995` generated `2026-07-01T03:39:21Z` status `pass`
Broker/profile: `nats://127.0.0.1:4222` / `local-live-jetstream`
Streams: `DS_TASKS` for tasks, `DS_DLQ` for DLQ
Consumer: `a2a_task_handler`
Handler model/provider under test: `ollama:glm-5.2:cloud`. Reviewer lane model is not the handler model.
Rows: `topology=pass, happy_path=pass, duplicate_path=pass, publish_failure_path=pass, handler_failure_redelivery_path=pass, stale_started_idempotency_path=pass, concurrent_duplicate_path=pass, ack_failure_path=pass, max_deliver_path=pass, dlq_failure_path=pass, restart_path=pass, compatibility_bypass_contract=pass, governance_negative_path=pass`

Output discipline for reviewers: return only the requested JSON object. The first character of your response must be `{`.

## Direct Answers To Prior Concerns

- Topology is included below as full raw JSON.
- MaxDeliver is included below as full raw JSON. DS_TASKS stream sequences and DS_DLQ stream sequences are different streams; a DS_DLQ stream sequence does not need to match the original DS_TASKS sequence.
- Failure-path handlers are deterministic failure-injection callables executed inside the same `A2AServer(require_execution_identity=True)` plus `A2ANatsTransport.consume_message` production consume path. The live model-backed semantic handler is proven on `happy_path`; failure rows prove ack/nack/redelivery/DLQ behavior under forced exceptions.
- Inline source hashes below tie the matrix to current code; this remedial packet is self-contained for the reviewed criteria.
- Compatibility publishers cannot satisfy the production gate: `compatibility_publishers_can_satisfy_production_gate=false`.

## Matrix Rows

### topology

```json
{
  "broker_url": "nats://127.0.0.1:4222",
  "consumer_ack_floor": {
    "consumer_seq": 173,
    "last_active": "2026-07-01T03:33:44.740241+00:00",
    "stream_seq": 95
  },
  "consumer_ack_policy": "explicit",
  "consumer_ack_wait_seconds": 60.0,
  "consumer_delivered": {
    "consumer_seq": 173,
    "last_active": "2026-07-01T03:33:44.657423+00:00",
    "stream_seq": 95
  },
  "consumer_filter_subject": "dharma.a2a.task.>",
  "consumer_max_deliver": 3,
  "consumer_name": "a2a_task_handler",
  "consumer_num_ack_pending": 0,
  "consumer_num_pending": 0,
  "dlq_retention": "limits",
  "dlq_stream_name": "DS_DLQ",
  "dlq_subjects": [
    "dharma.dlq.>"
  ],
  "name": "topology",
  "status": "pass",
  "stream_duplicate_window_seconds": 600.0,
  "stream_name": "DS_TASKS",
  "stream_retention": "limits",
  "stream_storage": "file",
  "stream_subjects": [
    "dharma.a2a.task.>"
  ],
  "timestamp": "2026-07-01T03:38:09Z"
}
```

### happy_path

```json
{
  "agent_id": "nats_live_20260701T033809Z_456ba995_happy_path",
  "broker_url": "nats://127.0.0.1:4222",
  "consume_ack": {
    "action": "ack",
    "duplicate": false,
    "error": "",
    "message_id": "nmsg_d1f1edaaa474f8a01f053d29e589a2ea",
    "receipt_id": "rr_020e3e786ac540da",
    "status": "ack",
    "subject": "dharma.a2a.task.nats_live_20260701t033809z_456ba995_happy_path.matrix_happy_path",
    "task_id": "nats_live_20260701T033809Z_456ba995_happy_path_474a05a9"
  },
  "consumer_name": "a2a_task_handler",
  "envelope_contract": {
    "actor": {
      "execution_agent": "nats-live-matrix-happy_path",
      "from_agent": "nats_live_matrix",
      "session_id": "nats-live-20260701T033809Z-456ba995",
      "to_agent": "nats_live_20260701T033809Z_456ba995_happy_path"
    },
    "causality": {
      "causation_id": "nats-live-20260701T033809Z-456ba995:happy_path:nats_live_20260701T033809Z_456ba995_happy_path_474a05a9",
      "correlation_id": "nats-live-20260701T033809Z-456ba995:happy_path:nats_live_20260701T033809Z_456ba995_happy_path_474a05a9",
      "message_id": "nmsg_d1f1edaaa474f8a01f053d29e589a2ea",
      "parent_span_id": "nats-live-20260701T033809Z-456ba995",
      "span_id": "nats-live-20260701T033809Z-456ba995:happy_path:nats_live_20260701T033809Z_456ba995_happy_path_474a05a9",
      "trace_id": "nats-live-20260701T033809Z-456ba995:happy_path:nats_live_20260701T033809Z_456ba995_happy_path_474a05a9"
    },
    "from_agent": "nats_live_matrix",
    "kind": "task",
    "message_id": "nmsg_d1f1edaaa474f8a01f053d29e589a2ea",
    "nats_msg_id": "nmsg_d1f1edaaa474f8a01f053d29e589a2ea",
    "payload_schema": "dharma.a2a.nats_task.v1",
    "schema": "dharma.nats.envelope.v1",
    "subject": "dharma.a2a.task.nats_live_20260701t033809z_456ba995_happy_path.matrix_happy_path",
    "to_agent": "nats_live_20260701T033809Z_456ba995_happy_path"
  },
  "headers": {
    "Dharma-Causation-Id": "nats-live-20260701T033809Z-456ba995:happy_path:nats_live_20260701T033809Z_456ba995_happy_path_474a05a9",
    "Dharma-Correlation-Id": "nats-live-20260701T033809Z-456ba995:happy_path:nats_live_20260701T033809Z_456ba995_happy_path_474a05a9",
    "Dharma-Idempotency-Key": "nats-live-20260701T033809Z-456ba995:happy_path:nats_live_20260701T033809Z_456ba995_happy_path_474a05a9:idem",
    "Dharma-Nats-Schema": "dharma.nats.envelope.v1",
    "Dharma-Run-Id": "nats-live-20260701T033809Z-456ba995:happy_path:nats_live_20260701T033809Z_456ba995_happy_path_474a05a9",
    "Dharma-Task-Id": "nats_live_20260701T033809Z_456ba995_happy_path_474a05a9",
    "Dharma-Trace-Id": "nats-live-20260701T033809Z-456ba995:happy_path:nats_live_20260701T033809Z_456ba995_happy_path_474a05a9",
    "Nats-Msg-Id": "nmsg_d1f1edaaa474f8a01f053d29e589a2ea"
  },
  "message_id": "nmsg_d1f1edaaa474f8a01f053d29e589a2ea",
  "metadata": {
    "consumer_sequence": 174,
    "num_delivered": 1,
    "stream_sequence": 96,
    "timestamp": "2026-07-01T03:38:09.745890+00:00"
  },
  "model_provider_id": "ollama:glm-5.2:cloud",
  "name": "happy_path",
  "production_path_contract": {
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
  },
  "publish_ack": {
    "action": "ack",
    "duplicate": false,
    "message_id": "nmsg_d1f1edaaa474f8a01f053d29e589a2ea",
    "receipt_id": "rr_a2555f0b8e5c495c",
    "seq": 96,
    "status": "ack",
    "stream": "DS_TASKS",
    "subject": "dharma.a2a.task.nats_live_20260701t033809z_456ba995_happy_path.matrix_happy_path",
    "task_id": "nats_live_20260701T033809Z_456ba995_happy_path_474a05a9"
  },
  "receipt_path": "/Users/dhyana/ds_runtime_truth_nats_clean_20260701/reports/a2a/nats_live_production_matrix/nats-live-20260701T033809Z-456ba995/receipts/nats_live_20260701T033809Z_456ba995_happy_path_474a05a9.semantic_receipt.json",
  "side_effect_count": 1,
  "status": "pass",
  "stream_name": "DS_TASKS",
  "task_id": "nats_live_20260701T033809Z_456ba995_happy_path_474a05a9",
  "timestamp": "2026-07-01T03:38:13Z",
  "trace_id": "nats-live-20260701T033809Z-456ba995:happy_path:nats_live_20260701T033809Z_456ba995_happy_path_474a05a9"
}
```

### duplicate_path

```json
{
  "agent_id": "nats_live_20260701T033809Z_456ba995_happy_path",
  "broker_duplicate_probe": {
    "duplicate": true,
    "seq": 96,
    "stream": "DS_TASKS"
  },
  "broker_duplicate_probe_entrypoint": "nats.aio.client.JetStreamContext.publish",
  "broker_duplicate_probe_purpose": "duplicate-window verification only; not a production task publisher",
  "broker_url": "nats://127.0.0.1:4222",
  "consumer_name": "a2a_task_handler",
  "message_id": "nmsg_d1f1edaaa474f8a01f053d29e589a2ea",
  "model_provider_id": "ollama:glm-5.2:cloud",
  "name": "duplicate_path",
  "production_path_contract": {
    "compatibility_publishers_can_satisfy_production_gate": false,
    "consume_entrypoint": null,
    "consumer_class": null,
    "consumer_require_execution_identity": null,
    "handler_contract": null,
    "publish_entrypoint": "dharma_swarm.a2a.nats_transport.A2ANatsTransport.publish_task",
    "transport_class": "dharma_swarm.a2a.nats_transport.A2ANatsTransport"
  },
  "runtime_duplicate_publish_ack": {
    "action": "ack",
    "duplicate": true,
    "message_id": "nmsg_d1f1edaaa474f8a01f053d29e589a2ea",
    "receipt_id": "rr_dabab4088b0d46e0",
    "seq": null,
    "status": "duplicate",
    "stream": "",
    "subject": "dharma.a2a.task.nats_live_20260701t033809z_456ba995_happy_path.matrix_happy_path",
    "task_id": "nats_live_20260701T033809Z_456ba995_happy_path_474a05a9"
  },
  "side_effect_count_after_replay": 1,
  "status": "pass",
  "stream_name": "DS_TASKS",
  "task_id": "nats_live_20260701T033809Z_456ba995_happy_path_474a05a9",
  "timestamp": "2026-07-01T03:38:13Z",
  "trace_id": "nats-live-20260701T033809Z-456ba995:happy_path:nats_live_20260701T033809Z_456ba995_happy_path_474a05a9"
}
```

### publish_failure_path

```json
{
  "agent_id": "nats_live_20260701T033809Z_456ba995_publish_failure_path",
  "broker_url": "nats://127.0.0.1:4222",
  "consume_ack": {
    "action": "ack",
    "duplicate": false,
    "error": "",
    "message_id": "nmsg_4f3718b8cd467b62be54c9a8b3c55f48",
    "receipt_id": "rr_1a029da852774b47",
    "status": "ack",
    "subject": "dharma.a2a.task.nats_live_20260701t033809z_456ba995_publish_failure_path.matrix_publish_failure_path",
    "task_id": "nats_live_20260701T033809Z_456ba995_publish_failure_path_76b788c2"
  },
  "consumer_name": "a2a_task_handler",
  "failure_injection": "JetStream publish raised before broker acceptance",
  "forced_failure": "NatsTransportError: forced task publish failure for matrix row",
  "message_id": "nmsg_4f3718b8cd467b62be54c9a8b3c55f48",
  "metadata": {
    "consumer_sequence": 175,
    "num_delivered": 1,
    "stream_sequence": 97,
    "timestamp": "2026-07-01T03:38:13.662229+00:00"
  },
  "model_provider_id": "ollama:glm-5.2:cloud",
  "name": "publish_failure_path",
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
  "retry_publish_ack": {
    "action": "ack",
    "duplicate": false,
    "message_id": "nmsg_4f3718b8cd467b62be54c9a8b3c55f48",
    "receipt_id": "rr_e3700a442a1d4e20",
    "seq": 97,
    "status": "ack",
    "stream": "DS_TASKS",
    "subject": "dharma.a2a.task.nats_live_20260701t033809z_456ba995_publish_failure_path.matrix_publish_failure_path",
    "task_id": "nats_live_20260701T033809Z_456ba995_publish_failure_path_76b788c2"
  },
  "status": "pass",
  "stream_name": "DS_TASKS",
  "task_id": "nats_live_20260701T033809Z_456ba995_publish_failure_path_76b788c2",
  "timestamp": "2026-07-01T03:38:13Z",
  "trace_id": "nats-live-20260701T033809Z-456ba995:publish_failure_path:nats_live_20260701T033809Z_456ba995_publish_failure_path_76b788c2"
}
```

### handler_failure_redelivery_path

```json
{
  "agent_id": "nats_live_20260701T033809Z_456ba995_handler_failure_redelivery_path",
  "broker_url": "nats://127.0.0.1:4222",
  "consumer_name": "a2a_task_handler",
  "first_consume_ack": {
    "action": "nack",
    "dlq_failed": false,
    "duplicate": false,
    "error": "forced first handler failure",
    "message_id": "nmsg_164d0b3f40c390ff7267f94981d928e9",
    "receipt_id": "rr_a1bfd04ec4cd4e66",
    "runtime_receipts": [
      {
        "agent_id": "nats-live-matrix-handler_failure_redelivery_path",
        "causation_id": "nats-live-20260701T033809Z-456ba995:handler_failure_redelivery_path:nats_live_20260701T033809Z_456ba995_handler_failure_redelivery_path_8fcc19e6",
        "correlation_id": "nats-live-20260701T033809Z-456ba995:handler_failure_redelivery_path:nats_live_20260701T033809Z_456ba995_handler_failure_redelivery_path_8fcc19e6",
        "created_at": "2026-07-01T03:38:14.017962+00:00",
        "idempotency_key": "nats-live-20260701T033809Z-456ba995:handler_failure_redelivery_path:nats_live_20260701T033809Z_456ba995_handler_failure_redelivery_path_8fcc19e6:idem",
        "parent_run_id": "nats-live-20260701T033809Z-456ba995",
        "payload": {
          "action": "nack",
          "error": "forced first handler failure",
          "external_a2a_task_id": "nats_live_20260701T033809Z_456ba995_handler_failure_redelivery_path_8fcc19e6",
          "message_id": "nmsg_164d0b3f40c390ff7267f94981d928e9",
          "operation_hash": "1d35b6dc4b1ec53b8ca8660b5fd8bb078bd568ed5818c628290f0e5eed6ff8c5",
          "subject": "dharma.a2a.task.nats_live_20260701t033809z_456ba995_handler_failure_redelivery_path.matrix_handler_failure_redelivery_path",
          "surface": "a2a.nats_transport.consume"
        },
        "receipt_id": "rr_a1bfd04ec4cd4e66",
        "receipt_type": "nats_consume",
        "run_id": "nats-live-20260701T033809Z-456ba995:handler_failure_redelivery_path:nats_live_20260701T033809Z_456ba995_handler_failure_redelivery_path_8fcc19e6",
        "side_effect_key": "nats_consume:dharma.a2a.task.nats_live_20260701t033809z_456ba995_handler_failure_redelivery_path.matrix_handler_failure_redelivery_path:nats_live_20260701T033809Z_456ba995_handler_failure_redelivery_path_8fcc19e6",
        "status": "nack",
        "task_id": "nats_live_20260701T033809Z_456ba995_handler_failure_redelivery_path_8fcc19e6",
        "trace_id": "nats-live-20260701T033809Z-456ba995:handler_failure_redelivery_path:nats_live_20260701T033809Z_456ba995_handler_failure_redelivery_path_8fcc19e6"
      }
    ],
    "status": "nack",
    "subject": "dharma.a2a.task.nats_live_20260701t033809z_456ba995_handler_failure_redelivery_path.matrix_handler_failure_redelivery_path",
    "task_id": "nats_live_20260701T033809Z_456ba995_handler_failure_redelivery_path_8fcc19e6"
  },
  "first_delivery_metadata": {
    "consumer_sequence": 176,
    "num_delivered": 1,
    "stream_sequence": 98,
    "timestamp": "2026-07-01T03:38:13.910421+00:00"
  },
  "first_production_path_contract": {
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
  "handler_attempts": 2,
  "message_id": "nmsg_164d0b3f40c390ff7267f94981d928e9",
  "model_provider_id": "ollama:glm-5.2:cloud",
  "name": "handler_failure_redelivery_path",
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
    "consumer_sequence": 177,
    "num_delivered": 2,
    "stream_sequence": 98,
    "timestamp": "2026-07-01T03:38:13.910421+00:00"
  },
  "second_consume_ack": {
    "action": "ack",
    "duplicate": false,
    "error": "",
    "message_id": "nmsg_164d0b3f40c390ff7267f94981d928e9",
    "receipt_id": "rr_a92a5c630ffe4487",
    "status": "ack",
    "subject": "dharma.a2a.task.nats_live_20260701t033809z_456ba995_handler_failure_redelivery_path.matrix_handler_failure_redelivery_path",
    "task_id": "nats_live_20260701T033809Z_456ba995_handler_failure_redelivery_path_8fcc19e6"
  },
  "second_production_path_contract": {
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
  "status": "pass",
  "stream_name": "DS_TASKS",
  "task_id": "nats_live_20260701T033809Z_456ba995_handler_failure_redelivery_path_8fcc19e6",
  "timestamp": "2026-07-01T03:38:14Z",
  "trace_id": "nats-live-20260701T033809Z-456ba995:handler_failure_redelivery_path:nats_live_20260701T033809Z_456ba995_handler_failure_redelivery_path_8fcc19e6"
}
```

### stale_started_idempotency_path

```json
{
  "agent_id": "nats_live_20260701T033809Z_456ba995_stale_started_idempotency_path",
  "broker_url": "nats://127.0.0.1:4222",
  "consume_ack": {
    "action": "ack",
    "duplicate": false,
    "error": "",
    "message_id": "nmsg_809d7675302859e51def1e8691130302",
    "receipt_id": "rr_89a5c8b0ded9450a",
    "status": "ack",
    "subject": "dharma.a2a.task.nats_live_20260701t033809z_456ba995_stale_started_idempotency_path.matrix_stale_started_idempotency_path",
    "task_id": "nats_live_20260701T033809Z_456ba995_stale_started_idempotency_path_71caf4ef"
  },
  "consumer_name": "a2a_task_handler",
  "message_id": "nmsg_809d7675302859e51def1e8691130302",
  "metadata": {
    "consumer_sequence": 178,
    "num_delivered": 1,
    "stream_sequence": 99,
    "timestamp": "2026-07-01T03:38:14.241581+00:00"
  },
  "model_provider_id": "ollama:glm-5.2:cloud",
  "name": "stale_started_idempotency_path",
  "preexisting_idempotency_status": "started",
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
  "seeded_side_effect_key": "nats_consume:dharma.a2a.task.nats_live_20260701t033809z_456ba995_stale_started_idempotency_path.matrix_stale_started_idempotency_path:nats_live_20260701T033809Z_456ba995_stale_started_idempotency_path_71caf4ef",
  "status": "pass",
  "stream_name": "DS_TASKS",
  "task_id": "nats_live_20260701T033809Z_456ba995_stale_started_idempotency_path_71caf4ef",
  "timestamp": "2026-07-01T03:38:14Z",
  "trace_id": "nats-live-20260701T033809Z-456ba995:stale_started_idempotency_path:nats_live_20260701T033809Z_456ba995_stale_started_idempotency_path_71caf4ef"
}
```

### concurrent_duplicate_path

```json
{
  "agent_id": "nats_live_20260701T033809Z_456ba995_concurrent_duplicate_path",
  "blocked_consume_ack": {
    "action": "nack",
    "dlq_failed": false,
    "duplicate": false,
    "error": "NATS consume idempotency record is still in progress: nats_consume:dharma.a2a.task.nats_live_20260701t033809z_456ba995_concurrent_duplicate_path.matrix_concurrent_duplicate_path:nats_live_20260701T033809Z_456ba995_concurrent_duplicate_path_63a425ff status=started receipt=rr_b635362b5c7e4ec7",
    "message_id": "nmsg_1a44320b6aef5a5818a7f51d075dbf80",
    "receipt_id": "rr_b635362b5c7e4ec7",
    "runtime_receipts": [
      {
        "agent_id": "nats-live-matrix-concurrent_duplicate_path",
        "causation_id": "nats-live-20260701T033809Z-456ba995:concurrent_duplicate_path:nats_live_20260701T033809Z_456ba995_concurrent_duplicate_path_63a425ff",
        "correlation_id": "nats-live-20260701T033809Z-456ba995:concurrent_duplicate_path:nats_live_20260701T033809Z_456ba995_concurrent_duplicate_path_63a425ff",
        "created_at": "2026-07-01T03:38:14.562764+00:00",
        "idempotency_key": "nats-live-20260701T033809Z-456ba995:concurrent_duplicate_path:nats_live_20260701T033809Z_456ba995_concurrent_duplicate_path_63a425ff:idem",
        "parent_run_id": "nats-live-20260701T033809Z-456ba995",
        "payload": {
          "action": "nack",
          "existing_status": "started",
          "external_a2a_task_id": "nats_live_20260701T033809Z_456ba995_concurrent_duplicate_path_63a425ff",
          "message_id": "nmsg_1a44320b6aef5a5818a7f51d075dbf80",
          "operation_hash": "dab5169af8bbcebf841f7a56d768388b09ec4b9b8b7350fce5c1c3e89f3f2ce6",
          "subject": "dharma.a2a.task.nats_live_20260701t033809z_456ba995_concurrent_duplicate_path.matrix_concurrent_duplicate_path",
          "surface": "a2a.nats_transport.consume"
        },
        "receipt_id": "rr_b635362b5c7e4ec7",
        "receipt_type": "nats_consume",
        "run_id": "nats-live-20260701T033809Z-456ba995:concurrent_duplicate_path:nats_live_20260701T033809Z_456ba995_concurrent_duplicate_path_63a425ff",
        "side_effect_key": "nats_consume:dharma.a2a.task.nats_live_20260701t033809z_456ba995_concurrent_duplicate_path.matrix_concurrent_duplicate_path:nats_live_20260701T033809Z_456ba995_concurrent_duplicate_path_63a425ff",
        "status": "retry_blocked",
        "task_id": "nats_live_20260701T033809Z_456ba995_concurrent_duplicate_path_63a425ff",
        "trace_id": "nats-live-20260701T033809Z-456ba995:concurrent_duplicate_path:nats_live_20260701T033809Z_456ba995_concurrent_duplicate_path_63a425ff"
      }
    ],
    "status": "retry_blocked",
    "subject": "dharma.a2a.task.nats_live_20260701t033809z_456ba995_concurrent_duplicate_path.matrix_concurrent_duplicate_path",
    "task_id": "nats_live_20260701T033809Z_456ba995_concurrent_duplicate_path_63a425ff"
  },
  "blocked_production_path_contract": {
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
  "broker_url": "nats://127.0.0.1:4222",
  "cleanup_consume_ack": {
    "action": "ack",
    "duplicate": false,
    "error": "",
    "message_id": "nmsg_1a44320b6aef5a5818a7f51d075dbf80",
    "receipt_id": "rr_f608762ef83c4beb",
    "status": "ack",
    "subject": "dharma.a2a.task.nats_live_20260701t033809z_456ba995_concurrent_duplicate_path.matrix_concurrent_duplicate_path",
    "task_id": "nats_live_20260701T033809Z_456ba995_concurrent_duplicate_path_63a425ff"
  },
  "cleanup_metadata": {
    "consumer_sequence": 180,
    "num_delivered": 2,
    "stream_sequence": 100,
    "timestamp": "2026-07-01T03:38:14.462749+00:00"
  },
  "cleanup_production_path_contract": {
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
  "consumer_name": "a2a_task_handler",
  "message_id": "nmsg_1a44320b6aef5a5818a7f51d075dbf80",
  "metadata": {
    "consumer_sequence": 179,
    "num_delivered": 1,
    "stream_sequence": 100,
    "timestamp": "2026-07-01T03:38:14.462749+00:00"
  },
  "model_provider_id": "ollama:glm-5.2:cloud",
  "name": "concurrent_duplicate_path",
  "preexisting_idempotency_status": "started",
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
  "seeded_side_effect_key": "nats_consume:dharma.a2a.task.nats_live_20260701t033809z_456ba995_concurrent_duplicate_path.matrix_concurrent_duplicate_path:nats_live_20260701T033809Z_456ba995_concurrent_duplicate_path_63a425ff",
  "side_effect_count": 1,
  "status": "pass",
  "stream_name": "DS_TASKS",
  "task_id": "nats_live_20260701T033809Z_456ba995_concurrent_duplicate_path_63a425ff",
  "timestamp": "2026-07-01T03:38:14Z",
  "trace_id": "nats-live-20260701T033809Z-456ba995:concurrent_duplicate_path:nats_live_20260701T033809Z_456ba995_concurrent_duplicate_path_63a425ff"
}
```

### ack_failure_path

```json
{
  "agent_id": "nats_live_20260701T033809Z_456ba995_ack_failure_path",
  "broker_url": "nats://127.0.0.1:4222",
  "cleanup_ack": {
    "action": "ack",
    "duplicate": false,
    "error": "",
    "message_id": "nmsg_0d2f0af3e00044e4f8a011ffb9c6b39e",
    "receipt_id": "rr_cf50e00543d14324",
    "status": "ack",
    "subject": "dharma.a2a.task.nats_live_20260701t033809z_456ba995_ack_failure_path.matrix_ack_failure_path",
    "task_id": "nats_live_20260701T033809Z_456ba995_ack_failure_path_16c73fae"
  },
  "cleanup_production_path_contract": {
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
  "consumer_name": "a2a_task_handler",
  "failed_ack": {
    "action": "nack",
    "dlq_failed": false,
    "duplicate": false,
    "error": "forced broker ack failure for matrix row",
    "message_id": "nmsg_0d2f0af3e00044e4f8a011ffb9c6b39e",
    "receipt_id": "rr_72b503ac8cd54326",
    "runtime_receipts": [
      {
        "agent_id": "nats-live-matrix-ack_failure_path",
        "causation_id": "nats-live-20260701T033809Z-456ba995:ack_failure_path:nats_live_20260701T033809Z_456ba995_ack_failure_path_16c73fae",
        "correlation_id": "nats-live-20260701T033809Z-456ba995:ack_failure_path:nats_live_20260701T033809Z_456ba995_ack_failure_path_16c73fae",
        "created_at": "2026-07-01T03:38:14.883113+00:00",
        "idempotency_key": "nats-live-20260701T033809Z-456ba995:ack_failure_path:nats_live_20260701T033809Z_456ba995_ack_failure_path_16c73fae:idem",
        "parent_run_id": "nats-live-20260701T033809Z-456ba995",
        "payload": {
          "a2a_status": "completed",
          "ack_contract": "consumer_ack_intent",
          "action": "ack_intent",
          "external_a2a_task_id": "nats_live_20260701T033809Z_456ba995_ack_failure_path_16c73fae",
          "message_id": "nmsg_0d2f0af3e00044e4f8a011ffb9c6b39e",
          "operation_hash": "0532cae9a7b92148f0c3e7768d298b89e526e4a8d90dc2766aa9dde9e774cb43",
          "spine_receipt_id": "98dd81af-aefd-4a5a-9e0e-4c3c255a2d44",
          "subject": "dharma.a2a.task.nats_live_20260701t033809z_456ba995_ack_failure_path.matrix_ack_failure_path",
          "surface": "a2a.nats_transport.consume"
        },
        "receipt_id": "rr_55dbda40ce824eec",
        "receipt_type": "nats_consume",
        "run_id": "nats-live-20260701T033809Z-456ba995:ack_failure_path:nats_live_20260701T033809Z_456ba995_ack_failure_path_16c73fae",
        "side_effect_key": "nats_consume:dharma.a2a.task.nats_live_20260701t033809z_456ba995_ack_failure_path.matrix_ack_failure_path:nats_live_20260701T033809Z_456ba995_ack_failure_path_16c73fae",
        "status": "ack_intent",
        "task_id": "nats_live_20260701T033809Z_456ba995_ack_failure_path_16c73fae",
        "trace_id": "nats-live-20260701T033809Z-456ba995:ack_failure_path:nats_live_20260701T033809Z_456ba995_ack_failure_path_16c73fae"
      },
      {
        "agent_id": "nats-live-matrix-ack_failure_path",
        "causation_id": "nats-live-20260701T033809Z-456ba995:ack_failure_path:nats_live_20260701T033809Z_456ba995_ack_failure_path_16c73fae",
        "correlation_id": "nats-live-20260701T033809Z-456ba995:ack_failure_path:nats_live_20260701T033809Z_456ba995_ack_failure_path_16c73fae",
        "created_at": "2026-07-01T03:38:14.890573+00:00",
        "idempotency_key": "nats-live-20260701T033809Z-456ba995:ack_failure_path:nats_live_20260701T033809Z_456ba995_ack_failure_path_16c73fae:idem",
        "parent_run_id": "nats-live-20260701T033809Z-456ba995",
        "payload": {
          "action": "nack",
          "error": "forced broker ack failure for matrix row",
          "external_a2a_task_id": "nats_live_20260701T033809Z_456ba995_ack_failure_path_16c73fae",
          "message_id": "nmsg_0d2f0af3e00044e4f8a011ffb9c6b39e",
          "operation_hash": "0532cae9a7b92148f0c3e7768d298b89e526e4a8d90dc2766aa9dde9e774cb43",
          "subject": "dharma.a2a.task.nats_live_20260701t033809z_456ba995_ack_failure_path.matrix_ack_failure_path",
          "surface": "a2a.nats_transport.consume"
        },
        "receipt_id": "rr_72b503ac8cd54326",
        "receipt_type": "nats_consume",
        "run_id": "nats-live-20260701T033809Z-456ba995:ack_failure_path:nats_live_20260701T033809Z_456ba995_ack_failure_path_16c73fae",
        "side_effect_key": "nats_consume:dharma.a2a.task.nats_live_20260701t033809z_456ba995_ack_failure_path.matrix_ack_failure_path:nats_live_20260701T033809Z_456ba995_ack_failure_path_16c73fae",
        "status": "nack",
        "task_id": "nats_live_20260701T033809Z_456ba995_ack_failure_path_16c73fae",
        "trace_id": "nats-live-20260701T033809Z-456ba995:ack_failure_path:nats_live_20260701T033809Z_456ba995_ack_failure_path_16c73fae"
      }
    ],
    "status": "nack",
    "subject": "dharma.a2a.task.nats_live_20260701t033809z_456ba995_ack_failure_path.matrix_ack_failure_path",
    "task_id": "nats_live_20260701T033809Z_456ba995_ack_failure_path_16c73fae"
  },
  "failed_ack_production_path_contract": {
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
  "failure_injection": "message.ack raised before broker ack; original was nacked and redelivered",
  "message_id": "nmsg_0d2f0af3e00044e4f8a011ffb9c6b39e",
  "model_provider_id": "ollama:glm-5.2:cloud",
  "name": "ack_failure_path",
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
    "consumer_sequence": 182,
    "num_delivered": 2,
    "stream_sequence": 101,
    "timestamp": "2026-07-01T03:38:14.780244+00:00"
  },
  "status": "pass",
  "stream_name": "DS_TASKS",
  "task_id": "nats_live_20260701T033809Z_456ba995_ack_failure_path_16c73fae",
  "timestamp": "2026-07-01T03:38:15Z",
  "trace_id": "nats-live-20260701T033809Z-456ba995:ack_failure_path:nats_live_20260701T033809Z_456ba995_ack_failure_path_16c73fae"
}
```

### max_deliver_path

```json
{
  "agent_id": "nats_live_20260701T033809Z_456ba995_max_deliver_path",
  "broker_url": "nats://127.0.0.1:4222",
  "consumer_name": "a2a_task_handler",
  "deliveries": [
    {
      "consume_ack": {
        "action": "nack",
        "dlq_failed": false,
        "duplicate": false,
        "error": "forced handler failure for max_deliver_path",
        "message_id": "nmsg_345dc4052c0914e1de7bfc1ad7405698",
        "receipt_id": "rr_a12feb3d9bc14c7b",
        "runtime_receipts": [
          {
            "agent_id": "nats-live-matrix-max_deliver_path",
            "causation_id": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
            "correlation_id": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
            "created_at": "2026-07-01T03:38:15.176026+00:00",
            "idempotency_key": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1:idem",
            "parent_run_id": "nats-live-20260701T033809Z-456ba995",
            "payload": {
              "action": "nack",
              "error": "forced handler failure for max_deliver_path",
              "external_a2a_task_id": "nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
              "message_id": "nmsg_345dc4052c0914e1de7bfc1ad7405698",
              "operation_hash": "392fa17d2c3c18930036df6d7b0be654b4ead4e842cb2cf3ecf85c1dced9d8e0",
              "subject": "dharma.a2a.task.nats_live_20260701t033809z_456ba995_max_deliver_path.matrix_max_deliver_path",
              "surface": "a2a.nats_transport.consume"
            },
            "receipt_id": "rr_a12feb3d9bc14c7b",
            "receipt_type": "nats_consume",
            "run_id": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
            "side_effect_key": "nats_consume:dharma.a2a.task.nats_live_20260701t033809z_456ba995_max_deliver_path.matrix_max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
            "status": "nack",
            "task_id": "nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
            "trace_id": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1"
          }
        ],
        "status": "nack",
        "subject": "dharma.a2a.task.nats_live_20260701t033809z_456ba995_max_deliver_path.matrix_max_deliver_path",
        "task_id": "nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1"
      },
      "metadata": {
        "consumer_sequence": 183,
        "num_delivered": 1,
        "stream_sequence": 102,
        "timestamp": "2026-07-01T03:38:15.095295+00:00"
      }
    },
    {
      "consume_ack": {
        "action": "nack",
        "dlq_failed": false,
        "duplicate": false,
        "error": "forced handler failure for max_deliver_path",
        "message_id": "nmsg_345dc4052c0914e1de7bfc1ad7405698",
        "receipt_id": "rr_5bd333708cd24a73",
        "runtime_receipts": [
          {
            "agent_id": "nats-live-matrix-max_deliver_path",
            "causation_id": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
            "correlation_id": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
            "created_at": "2026-07-01T03:38:15.176026+00:00",
            "idempotency_key": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1:idem",
            "parent_run_id": "nats-live-20260701T033809Z-456ba995",
            "payload": {
              "action": "nack",
              "error": "forced handler failure for max_deliver_path",
              "external_a2a_task_id": "nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
              "message_id": "nmsg_345dc4052c0914e1de7bfc1ad7405698",
              "operation_hash": "392fa17d2c3c18930036df6d7b0be654b4ead4e842cb2cf3ecf85c1dced9d8e0",
              "subject": "dharma.a2a.task.nats_live_20260701t033809z_456ba995_max_deliver_path.matrix_max_deliver_path",
              "surface": "a2a.nats_transport.consume"
            },
            "receipt_id": "rr_a12feb3d9bc14c7b",
            "receipt_type": "nats_consume",
            "run_id": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
            "side_effect_key": "nats_consume:dharma.a2a.task.nats_live_20260701t033809z_456ba995_max_deliver_path.matrix_max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
            "status": "nack",
            "task_id": "nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
            "trace_id": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1"
          },
          {
            "agent_id": "nats-live-matrix-max_deliver_path",
            "causation_id": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
            "correlation_id": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
            "created_at": "2026-07-01T03:38:15.295459+00:00",
            "idempotency_key": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1:idem",
            "parent_run_id": "nats-live-20260701T033809Z-456ba995",
            "payload": {
              "action": "nack",
              "error": "forced handler failure for max_deliver_path",
              "external_a2a_task_id": "nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
              "message_id": "nmsg_345dc4052c0914e1de7bfc1ad7405698",
              "operation_hash": "392fa17d2c3c18930036df6d7b0be654b4ead4e842cb2cf3ecf85c1dced9d8e0",
              "retry_of_result_receipt_id": "rr_a12feb3d9bc14c7b",
              "retry_of_side_effect_key": "nats_consume:dharma.a2a.task.nats_live_20260701t033809z_456ba995_max_deliver_path.matrix_max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
              "retry_of_status": "failed",
              "subject": "dharma.a2a.task.nats_live_20260701t033809z_456ba995_max_deliver_path.matrix_max_deliver_path",
              "surface": "a2a.nats_transport.consume"
            },
            "receipt_id": "rr_5bd333708cd24a73",
            "receipt_type": "nats_consume",
            "run_id": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
            "side_effect_key": "nats_consume:dharma.a2a.task.nats_live_20260701t033809z_456ba995_max_deliver_path.matrix_max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1:retry:eb5f25f323e4",
            "status": "nack",
            "task_id": "nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
            "trace_id": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1"
          }
        ],
        "status": "nack",
        "subject": "dharma.a2a.task.nats_live_20260701t033809z_456ba995_max_deliver_path.matrix_max_deliver_path",
        "task_id": "nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1"
      },
      "metadata": {
        "consumer_sequence": 184,
        "num_delivered": 2,
        "stream_sequence": 102,
        "timestamp": "2026-07-01T03:38:15.095295+00:00"
      }
    },
    {
      "consume_ack": {
        "action": "dlq",
        "duplicate": false,
        "error": "forced handler failure for max_deliver_path",
        "message_id": "nmsg_345dc4052c0914e1de7bfc1ad7405698",
        "receipt_id": "rr_0c2edd08a33a4310",
        "status": "dlq",
        "subject": "dharma.a2a.task.nats_live_20260701t033809z_456ba995_max_deliver_path.matrix_max_deliver_path",
        "task_id": "nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1"
      },
      "metadata": {
        "consumer_sequence": 185,
        "num_delivered": 3,
        "stream_sequence": 102,
        "timestamp": "2026-07-01T03:38:15.095295+00:00"
      }
    }
  ],
  "dlq_envelope": {
    "actor": {
      "execution_agent": "nats-live-matrix-max_deliver_path",
      "from_agent": "nats_live_20260701T033809Z_456ba995_max_deliver_path",
      "session_id": "nats-live-20260701T033809Z-456ba995",
      "to_agent": "operator"
    },
    "causality": {
      "causation_id": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
      "correlation_id": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
      "message_id": "nmsg_ed68f3ce52293577833b5d8c256dfa72",
      "parent_span_id": "nats-live-20260701T033809Z-456ba995",
      "span_id": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
      "trace_id": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1"
    },
    "causation_id": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
    "correlation_id": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
    "created_at": "2026-07-01T03:38:15.404248+00:00",
    "from_agent": "nats_live_20260701T033809Z_456ba995_max_deliver_path",
    "kind": "event",
    "message_id": "nmsg_ed68f3ce52293577833b5d8c256dfa72",
    "parent_span_id": "nats-live-20260701T033809Z-456ba995",
    "payload": {
      "created_at": "2026-07-01T03:38:15.404248+00:00",
      "delivery_count": 3,
      "error": "forced handler failure for max_deliver_path",
      "max_deliveries": 3,
      "operator_blocker": "NATS_MAX_DELIVER_EXHAUSTED",
      "original_message_id": "nmsg_345dc4052c0914e1de7bfc1ad7405698",
      "original_payload": {
        "actor": {
          "execution_agent": "nats-live-matrix-max_deliver_path",
          "from_agent": "nats_live_matrix",
          "session_id": "nats-live-20260701T033809Z-456ba995",
          "to_agent": "nats_live_20260701T033809Z_456ba995_max_deliver_path"
        },
        "causality": {
          "causation_id": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
          "correlation_id": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
          "message_id": "nmsg_345dc4052c0914e1de7bfc1ad7405698",
          "parent_span_id": "nats-live-20260701T033809Z-456ba995",
          "span_id": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
          "trace_id": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1"
        },
        "causation_id": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
        "correlation_id": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
        "created_at": "2026-07-01T03:38:15.094896+00:00",
        "execution_identity": {
          "agent_id": "nats-live-matrix-max_deliver_path",
          "artifact_id": "",
          "causation_id": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
          "claim_id": "claim-nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
          "correlation_id": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
          "event_id": "",
          "external_a2a_task_id": "nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
          "idempotency_key": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1:idem",
          "message_id": "nmsg_345dc4052c0914e1de7bfc1ad7405698",
          "metadata": {},
          "parent_run_id": "nats-live-20260701T033809Z-456ba995",
          "proposal_id": "",
          "run_id": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
          "session_id": "nats-live-20260701T033809Z-456ba995",
          "task_id": "nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
          "trace_id": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1"
        },
        "from_agent": "nats_live_matrix",
        "kind": "task",
        "message_id": "nmsg_345dc4052c0914e1de7bfc1ad7405698",
        "parent_span_id": "nats-live-20260701T033809Z-456ba995",
        "payload": {
          "execution_identity": {
            "agent_id": "nats-live-matrix-max_deliver_path",
            "artifact_id": "",
            "causation_id": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
            "claim_id": "claim-nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
            "correlation_id": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
            "event_id": "",
            "external_a2a_task_id": "nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
            "idempotency_key": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1:idem",
            "message_id": "nmsg_345dc4052c0914e1de7bfc1ad7405698",
            "metadata": {},
            "parent_run_id": "nats-live-20260701T033809Z-456ba995",
            "proposal_id": "",
            "run_id": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
            "session_id": "nats-live-20260701T033809Z-456ba995",
            "task_id": "nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
            "trace_id": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1"
          },
          "schema": "dharma.a2a.nats_task.v1",
          "sent_at": "2026-07-01T03:38:15.094896+00:00",
          "task": {
            "artifacts": [],
            "capability": "matrix_max_deliver_path",
            "context_id": "",
            "created_at": "2026-07-01T03:38:15.061224+00:00",
            "dharma_task_id": "nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
            "error": "",
            "extensions": [],
            "from_agent": "nats_live_matrix",
            "history": [
              {
                "metadata": {},
                "parts": [
                  {
                    "_skip_validation": false,
                    "content": "{\"label\": \"max_deliver_path\", \"run_id\": \"nats-live-20260701T033809Z-456ba995\"}",
                    "filename": "",
                    "media_type": "",
                    "metadata": {},
                    "type": "text"
                  }
                ],
                "role": "user"
              }
            ],
            "id": "nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
            "messages": [
              {
                "metadata": {},
                "parts": [
                  {
                    "_skip_validation": false,
                    "content": "{\"label\": \"max_deliver_path\", \"run_id\": \"nats-live-20260701T033809Z-456ba995\"}",
                    "filename": "",
                    "media_type": "",
                    "metadata": {},
                    "type": "text"
                  }
                ],
                "role": "user"
              }
            ],
            "metadata": {
              "claim_id": "claim-nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
              "correlation_id": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
              "execution_identity": {
                "agent_id": "nats-live-matrix-max_deliver_path",
                "artifact_id": "",
                "causation_id": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
                "claim_id": "claim-nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
                "correlation_id": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
                "event_id": "",
                "external_a2a_task_id": "nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
                "idempotency_key": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1:idem",
                "message_id": "",
                "metadata": {},
                "parent_run_id": "nats-live-20260701T033809Z-456ba995",
                "proposal_id": "",
                "run_id": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
                "session_id": "nats-live-20260701T033809Z-456ba995",
                "task_id": "nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
                "trace_id": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1"
              },
              "external_a2a_task_id": "nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
              "idempotency_key": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1:idem",
              "run_id": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
              "trace_id": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1"
            },
            "result": "",
            "status": "submitted",
            "to_agent": "nats_live_20260701T033809Z_456ba995_max_deliver_path",
            "trace_id": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
            "updated_at": "2026-07-01T03:38:15.061228+00:00"
          }
        },
        "requires_ack": true,
        "schema": "dharma.nats.envelope.v1",
        "span_id": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
        "subject": "dharma.a2a.task.nats_live_20260701t033809z_456ba995_max_deliver_path.matrix_max_deliver_path",
        "task": {
          "artifacts": [],
          "capability": "matrix_max_deliver_path",
          "context_id": "",
          "created_at": "2026-07-01T03:38:15.061224+00:00",
          "dharma_task_id": "nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
          "error": "",
          "extensions": [],
          "from_agent": "nats_live_matrix",
          "history": [
            {
              "metadata": {},
              "parts": [
                {
                  "_skip_validation": false,
                  "content": "{\"label\": \"max_deliver_path\", \"run_id\": \"nats-live-20260701T033809Z-456ba995\"}",
                  "filename": "",
                  "media_type": "",
                  "metadata": {},
                  "type": "text"
                }
              ],
              "role": "user"
            }
          ],
          "id": "nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
          "messages": [
            {
              "metadata": {},
              "parts": [
                {
                  "_skip_validation": false,
                  "content": "{\"label\": \"max_deliver_path\", \"run_id\": \"nats-live-20260701T033809Z-456ba995\"}",
                  "filename": "",
                  "media_type": "",
                  "metadata": {},
                  "type": "text"
                }
              ],
              "role": "user"
            }
          ],
          "metadata": {
            "claim_id": "claim-nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
            "correlation_id": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
            "execution_identity": {
              "agent_id": "nats-live-matrix-max_deliver_path",
              "artifact_id": "",
              "causation_id": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
              "claim_id": "claim-nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
              "correlation_id": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
              "event_id": "",
              "external_a2a_task_id": "nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
              "idempotency_key": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1:idem",
              "message_id": "",
              "metadata": {},
              "parent_run_id": "nats-live-20260701T033809Z-456ba995",
              "proposal_id": "",
              "run_id": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
              "session_id": "nats-live-20260701T033809Z-456ba995",
              "task_id": "nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
              "trace_id": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1"
            },
            "external_a2a_task_id": "nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
            "idempotency_key": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1:idem",
            "run_id": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
            "trace_id": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1"
          },
          "result": "",
          "status": "submitted",
          "to_agent": "nats_live_20260701T033809Z_456ba995_max_deliver_path",
          "trace_id": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
          "updated_at": "2026-07-01T03:38:15.061228+00:00"
        },
        "to_agent": "nats_live_20260701T033809Z_456ba995_max_deliver_path",
        "trace_id": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1"
      },
      "original_subject": "dharma.a2a.task.nats_live_20260701t033809z_456ba995_max_deliver_path.matrix_max_deliver_path",
      "schema": "dharma.nats.dlq_failure.v1",
      "task_id": "nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1"
    },
    "requires_ack": false,
    "schema": "dharma.nats.envelope.v1",
    "span_id": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
    "subject": "dharma.dlq.ds_tasks.a2a_task_handler",
    "to_agent": "operator",
    "trace_id": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1"
  },
  "dlq_metadata": {
    "consumer_sequence": 10,
    "num_delivered": 1,
    "stream_sequence": 10,
    "timestamp": "2026-07-01T03:38:15.404539+00:00"
  },
  "dlq_subject": "dharma.dlq.ds_tasks.a2a_task_handler",
  "final_ack": {
    "action": "dlq",
    "duplicate": false,
    "error": "forced handler failure for max_deliver_path",
    "message_id": "nmsg_345dc4052c0914e1de7bfc1ad7405698",
    "receipt_id": "rr_0c2edd08a33a4310",
    "status": "dlq",
    "subject": "dharma.a2a.task.nats_live_20260701t033809z_456ba995_max_deliver_path.matrix_max_deliver_path",
    "task_id": "nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1"
  },
  "message_id": "nmsg_345dc4052c0914e1de7bfc1ad7405698",
  "model_provider_id": "ollama:glm-5.2:cloud",
  "name": "max_deliver_path",
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
  "status": "pass",
  "stream_name": "DS_TASKS",
  "task_id": "nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1",
  "timestamp": "2026-07-01T03:38:15Z",
  "trace_id": "nats-live-20260701T033809Z-456ba995:max_deliver_path:nats_live_20260701T033809Z_456ba995_max_deliver_path_c7af94f1"
}
```

### dlq_failure_path

```json
{
  "agent_id": "nats_live_20260701T033809Z_456ba995_dlq_failure_path",
  "broker_url": "nats://127.0.0.1:4222",
  "consumer_name": "a2a_task_handler",
  "deliveries": [
    {
      "consume_ack": {
        "action": "nack",
        "dlq_failed": false,
        "duplicate": false,
        "error": "forced handler failure for dlq_failure_path",
        "message_id": "nmsg_eb75b037188df853ebb188585ca4687d",
        "receipt_id": "rr_7adb230b2f884e54",
        "runtime_receipts": [
          {
            "agent_id": "nats-live-matrix-dlq_failure_path",
            "causation_id": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
            "correlation_id": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
            "created_at": "2026-07-01T03:38:15.566517+00:00",
            "idempotency_key": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317:idem",
            "parent_run_id": "nats-live-20260701T033809Z-456ba995",
            "payload": {
              "action": "nack",
              "error": "forced handler failure for dlq_failure_path",
              "external_a2a_task_id": "nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
              "message_id": "nmsg_eb75b037188df853ebb188585ca4687d",
              "operation_hash": "e07d82810d1d2b7a00c63522d6ec56d3627a7f7dc5a6dd99bd5fc5985fa682fa",
              "subject": "dharma.a2a.task.nats_live_20260701t033809z_456ba995_dlq_failure_path.matrix_dlq_failure_path",
              "surface": "a2a.nats_transport.consume"
            },
            "receipt_id": "rr_7adb230b2f884e54",
            "receipt_type": "nats_consume",
            "run_id": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
            "side_effect_key": "nats_consume:dharma.a2a.task.nats_live_20260701t033809z_456ba995_dlq_failure_path.matrix_dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
            "status": "nack",
            "task_id": "nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
            "trace_id": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317"
          }
        ],
        "status": "nack",
        "subject": "dharma.a2a.task.nats_live_20260701t033809z_456ba995_dlq_failure_path.matrix_dlq_failure_path",
        "task_id": "nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317"
      },
      "metadata": {
        "consumer_sequence": 186,
        "num_delivered": 1,
        "stream_sequence": 103,
        "timestamp": "2026-07-01T03:38:15.487819+00:00"
      }
    },
    {
      "consume_ack": {
        "action": "nack",
        "dlq_failed": false,
        "duplicate": false,
        "error": "forced handler failure for dlq_failure_path",
        "message_id": "nmsg_eb75b037188df853ebb188585ca4687d",
        "receipt_id": "rr_dcf5d2af7ae34e43",
        "runtime_receipts": [
          {
            "agent_id": "nats-live-matrix-dlq_failure_path",
            "causation_id": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
            "correlation_id": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
            "created_at": "2026-07-01T03:38:15.566517+00:00",
            "idempotency_key": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317:idem",
            "parent_run_id": "nats-live-20260701T033809Z-456ba995",
            "payload": {
              "action": "nack",
              "error": "forced handler failure for dlq_failure_path",
              "external_a2a_task_id": "nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
              "message_id": "nmsg_eb75b037188df853ebb188585ca4687d",
              "operation_hash": "e07d82810d1d2b7a00c63522d6ec56d3627a7f7dc5a6dd99bd5fc5985fa682fa",
              "subject": "dharma.a2a.task.nats_live_20260701t033809z_456ba995_dlq_failure_path.matrix_dlq_failure_path",
              "surface": "a2a.nats_transport.consume"
            },
            "receipt_id": "rr_7adb230b2f884e54",
            "receipt_type": "nats_consume",
            "run_id": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
            "side_effect_key": "nats_consume:dharma.a2a.task.nats_live_20260701t033809z_456ba995_dlq_failure_path.matrix_dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
            "status": "nack",
            "task_id": "nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
            "trace_id": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317"
          },
          {
            "agent_id": "nats-live-matrix-dlq_failure_path",
            "causation_id": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
            "correlation_id": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
            "created_at": "2026-07-01T03:38:15.715992+00:00",
            "idempotency_key": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317:idem",
            "parent_run_id": "nats-live-20260701T033809Z-456ba995",
            "payload": {
              "action": "nack",
              "error": "forced handler failure for dlq_failure_path",
              "external_a2a_task_id": "nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
              "message_id": "nmsg_eb75b037188df853ebb188585ca4687d",
              "operation_hash": "e07d82810d1d2b7a00c63522d6ec56d3627a7f7dc5a6dd99bd5fc5985fa682fa",
              "retry_of_result_receipt_id": "rr_7adb230b2f884e54",
              "retry_of_side_effect_key": "nats_consume:dharma.a2a.task.nats_live_20260701t033809z_456ba995_dlq_failure_path.matrix_dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
              "retry_of_status": "failed",
              "subject": "dharma.a2a.task.nats_live_20260701t033809z_456ba995_dlq_failure_path.matrix_dlq_failure_path",
              "surface": "a2a.nats_transport.consume"
            },
            "receipt_id": "rr_dcf5d2af7ae34e43",
            "receipt_type": "nats_consume",
            "run_id": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
            "side_effect_key": "nats_consume:dharma.a2a.task.nats_live_20260701t033809z_456ba995_dlq_failure_path.matrix_dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317:retry:f78053292d82",
            "status": "nack",
            "task_id": "nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
            "trace_id": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317"
          }
        ],
        "status": "nack",
        "subject": "dharma.a2a.task.nats_live_20260701t033809z_456ba995_dlq_failure_path.matrix_dlq_failure_path",
        "task_id": "nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317"
      },
      "metadata": {
        "consumer_sequence": 187,
        "num_delivered": 2,
        "stream_sequence": 103,
        "timestamp": "2026-07-01T03:38:15.487819+00:00"
      }
    },
    {
      "consume_ack": {
        "action": "nack",
        "dlq_failed": true,
        "duplicate": false,
        "error": "forced handler failure for dlq_failure_path",
        "message_id": "nmsg_eb75b037188df853ebb188585ca4687d",
        "receipt_id": "rr_b504e8002a0745d7",
        "runtime_receipts": [
          {
            "agent_id": "nats-live-matrix-dlq_failure_path",
            "causation_id": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
            "correlation_id": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
            "created_at": "2026-07-01T03:38:15.566517+00:00",
            "idempotency_key": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317:idem",
            "parent_run_id": "nats-live-20260701T033809Z-456ba995",
            "payload": {
              "action": "nack",
              "error": "forced handler failure for dlq_failure_path",
              "external_a2a_task_id": "nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
              "message_id": "nmsg_eb75b037188df853ebb188585ca4687d",
              "operation_hash": "e07d82810d1d2b7a00c63522d6ec56d3627a7f7dc5a6dd99bd5fc5985fa682fa",
              "subject": "dharma.a2a.task.nats_live_20260701t033809z_456ba995_dlq_failure_path.matrix_dlq_failure_path",
              "surface": "a2a.nats_transport.consume"
            },
            "receipt_id": "rr_7adb230b2f884e54",
            "receipt_type": "nats_consume",
            "run_id": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
            "side_effect_key": "nats_consume:dharma.a2a.task.nats_live_20260701t033809z_456ba995_dlq_failure_path.matrix_dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
            "status": "nack",
            "task_id": "nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
            "trace_id": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317"
          },
          {
            "agent_id": "nats-live-matrix-dlq_failure_path",
            "causation_id": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
            "correlation_id": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
            "created_at": "2026-07-01T03:38:15.715992+00:00",
            "idempotency_key": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317:idem",
            "parent_run_id": "nats-live-20260701T033809Z-456ba995",
            "payload": {
              "action": "nack",
              "error": "forced handler failure for dlq_failure_path",
              "external_a2a_task_id": "nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
              "message_id": "nmsg_eb75b037188df853ebb188585ca4687d",
              "operation_hash": "e07d82810d1d2b7a00c63522d6ec56d3627a7f7dc5a6dd99bd5fc5985fa682fa",
              "retry_of_result_receipt_id": "rr_7adb230b2f884e54",
              "retry_of_side_effect_key": "nats_consume:dharma.a2a.task.nats_live_20260701t033809z_456ba995_dlq_failure_path.matrix_dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
              "retry_of_status": "failed",
              "subject": "dharma.a2a.task.nats_live_20260701t033809z_456ba995_dlq_failure_path.matrix_dlq_failure_path",
              "surface": "a2a.nats_transport.consume"
            },
            "receipt_id": "rr_dcf5d2af7ae34e43",
            "receipt_type": "nats_consume",
            "run_id": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
            "side_effect_key": "nats_consume:dharma.a2a.task.nats_live_20260701t033809z_456ba995_dlq_failure_path.matrix_dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317:retry:f78053292d82",
            "status": "nack",
            "task_id": "nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
            "trace_id": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317"
          },
          {
            "agent_id": "nats-live-matrix-dlq_failure_path",
            "causation_id": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
            "correlation_id": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
            "created_at": "2026-07-01T03:38:15.843088+00:00",
            "idempotency_key": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317:idem",
            "parent_run_id": "nats-live-20260701T033809Z-456ba995",
            "payload": {
              "action": "nack",
              "dlq_error": "forced DLQ publish failure for matrix row",
              "error": "forced handler failure for dlq_failure_path",
              "external_a2a_task_id": "nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
              "message_id": "nmsg_eb75b037188df853ebb188585ca4687d",
              "operation_hash": "e07d82810d1d2b7a00c63522d6ec56d3627a7f7dc5a6dd99bd5fc5985fa682fa",
              "retry_of_result_receipt_id": "rr_7adb230b2f884e54",
              "retry_of_side_effect_key": "nats_consume:dharma.a2a.task.nats_live_20260701t033809z_456ba995_dlq_failure_path.matrix_dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
              "retry_of_status": "failed",
              "subject": "dharma.a2a.task.nats_live_20260701t033809z_456ba995_dlq_failure_path.matrix_dlq_failure_path",
              "surface": "a2a.nats_transport.consume"
            },
            "receipt_id": "rr_da11cba6fb604b3f",
            "receipt_type": "nats_consume",
            "run_id": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
            "side_effect_key": "nats_consume:dharma.a2a.task.nats_live_20260701t033809z_456ba995_dlq_failure_path.matrix_dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317:retry:3cd58f610bcb",
            "status": "dlq_failed",
            "task_id": "nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
            "trace_id": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317"
          },
          {
            "agent_id": "nats-live-matrix-dlq_failure_path",
            "causation_id": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
            "correlation_id": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
            "created_at": "2026-07-01T03:38:15.849809+00:00",
            "idempotency_key": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317:idem",
            "parent_run_id": "nats-live-20260701T033809Z-456ba995",
            "payload": {
              "action": "nack",
              "error": "forced handler failure for dlq_failure_path",
              "external_a2a_task_id": "nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
              "message_id": "nmsg_eb75b037188df853ebb188585ca4687d",
              "operation_hash": "e07d82810d1d2b7a00c63522d6ec56d3627a7f7dc5a6dd99bd5fc5985fa682fa",
              "retry_of_result_receipt_id": "rr_7adb230b2f884e54",
              "retry_of_side_effect_key": "nats_consume:dharma.a2a.task.nats_live_20260701t033809z_456ba995_dlq_failure_path.matrix_dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
              "retry_of_status": "failed",
              "subject": "dharma.a2a.task.nats_live_20260701t033809z_456ba995_dlq_failure_path.matrix_dlq_failure_path",
              "surface": "a2a.nats_transport.consume"
            },
            "receipt_id": "rr_b504e8002a0745d7",
            "receipt_type": "nats_consume",
            "run_id": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
            "side_effect_key": "nats_consume:dharma.a2a.task.nats_live_20260701t033809z_456ba995_dlq_failure_path.matrix_dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317:retry:3cd58f610bcb",
            "status": "nack",
            "task_id": "nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
            "trace_id": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317"
          }
        ],
        "status": "nack",
        "subject": "dharma.a2a.task.nats_live_20260701t033809z_456ba995_dlq_failure_path.matrix_dlq_failure_path",
        "task_id": "nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317"
      },
      "metadata": {
        "consumer_sequence": 188,
        "num_delivered": 3,
        "stream_sequence": 103,
        "timestamp": "2026-07-01T03:38:15.487819+00:00"
      }
    }
  ],
  "failure_injection": "DLQ publish raised at MaxDeliver; original was not acked and remains beyond the consumer ack floor",
  "final_ack": {
    "action": "nack",
    "dlq_failed": true,
    "duplicate": false,
    "error": "forced handler failure for dlq_failure_path",
    "message_id": "nmsg_eb75b037188df853ebb188585ca4687d",
    "receipt_id": "rr_b504e8002a0745d7",
    "runtime_receipts": [
      {
        "agent_id": "nats-live-matrix-dlq_failure_path",
        "causation_id": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
        "correlation_id": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
        "created_at": "2026-07-01T03:38:15.566517+00:00",
        "idempotency_key": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317:idem",
        "parent_run_id": "nats-live-20260701T033809Z-456ba995",
        "payload": {
          "action": "nack",
          "error": "forced handler failure for dlq_failure_path",
          "external_a2a_task_id": "nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
          "message_id": "nmsg_eb75b037188df853ebb188585ca4687d",
          "operation_hash": "e07d82810d1d2b7a00c63522d6ec56d3627a7f7dc5a6dd99bd5fc5985fa682fa",
          "subject": "dharma.a2a.task.nats_live_20260701t033809z_456ba995_dlq_failure_path.matrix_dlq_failure_path",
          "surface": "a2a.nats_transport.consume"
        },
        "receipt_id": "rr_7adb230b2f884e54",
        "receipt_type": "nats_consume",
        "run_id": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
        "side_effect_key": "nats_consume:dharma.a2a.task.nats_live_20260701t033809z_456ba995_dlq_failure_path.matrix_dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
        "status": "nack",
        "task_id": "nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
        "trace_id": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317"
      },
      {
        "agent_id": "nats-live-matrix-dlq_failure_path",
        "causation_id": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
        "correlation_id": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
        "created_at": "2026-07-01T03:38:15.715992+00:00",
        "idempotency_key": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317:idem",
        "parent_run_id": "nats-live-20260701T033809Z-456ba995",
        "payload": {
          "action": "nack",
          "error": "forced handler failure for dlq_failure_path",
          "external_a2a_task_id": "nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
          "message_id": "nmsg_eb75b037188df853ebb188585ca4687d",
          "operation_hash": "e07d82810d1d2b7a00c63522d6ec56d3627a7f7dc5a6dd99bd5fc5985fa682fa",
          "retry_of_result_receipt_id": "rr_7adb230b2f884e54",
          "retry_of_side_effect_key": "nats_consume:dharma.a2a.task.nats_live_20260701t033809z_456ba995_dlq_failure_path.matrix_dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
          "retry_of_status": "failed",
          "subject": "dharma.a2a.task.nats_live_20260701t033809z_456ba995_dlq_failure_path.matrix_dlq_failure_path",
          "surface": "a2a.nats_transport.consume"
        },
        "receipt_id": "rr_dcf5d2af7ae34e43",
        "receipt_type": "nats_consume",
        "run_id": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
        "side_effect_key": "nats_consume:dharma.a2a.task.nats_live_20260701t033809z_456ba995_dlq_failure_path.matrix_dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317:retry:f78053292d82",
        "status": "nack",
        "task_id": "nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
        "trace_id": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317"
      },
      {
        "agent_id": "nats-live-matrix-dlq_failure_path",
        "causation_id": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
        "correlation_id": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
        "created_at": "2026-07-01T03:38:15.843088+00:00",
        "idempotency_key": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317:idem",
        "parent_run_id": "nats-live-20260701T033809Z-456ba995",
        "payload": {
          "action": "nack",
          "dlq_error": "forced DLQ publish failure for matrix row",
          "error": "forced handler failure for dlq_failure_path",
          "external_a2a_task_id": "nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
          "message_id": "nmsg_eb75b037188df853ebb188585ca4687d",
          "operation_hash": "e07d82810d1d2b7a00c63522d6ec56d3627a7f7dc5a6dd99bd5fc5985fa682fa",
          "retry_of_result_receipt_id": "rr_7adb230b2f884e54",
          "retry_of_side_effect_key": "nats_consume:dharma.a2a.task.nats_live_20260701t033809z_456ba995_dlq_failure_path.matrix_dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
          "retry_of_status": "failed",
          "subject": "dharma.a2a.task.nats_live_20260701t033809z_456ba995_dlq_failure_path.matrix_dlq_failure_path",
          "surface": "a2a.nats_transport.consume"
        },
        "receipt_id": "rr_da11cba6fb604b3f",
        "receipt_type": "nats_consume",
        "run_id": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
        "side_effect_key": "nats_consume:dharma.a2a.task.nats_live_20260701t033809z_456ba995_dlq_failure_path.matrix_dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317:retry:3cd58f610bcb",
        "status": "dlq_failed",
        "task_id": "nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
        "trace_id": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317"
      },
      {
        "agent_id": "nats-live-matrix-dlq_failure_path",
        "causation_id": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
        "correlation_id": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
        "created_at": "2026-07-01T03:38:15.849809+00:00",
        "idempotency_key": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317:idem",
        "parent_run_id": "nats-live-20260701T033809Z-456ba995",
        "payload": {
          "action": "nack",
          "error": "forced handler failure for dlq_failure_path",
          "external_a2a_task_id": "nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
          "message_id": "nmsg_eb75b037188df853ebb188585ca4687d",
          "operation_hash": "e07d82810d1d2b7a00c63522d6ec56d3627a7f7dc5a6dd99bd5fc5985fa682fa",
          "retry_of_result_receipt_id": "rr_7adb230b2f884e54",
          "retry_of_side_effect_key": "nats_consume:dharma.a2a.task.nats_live_20260701t033809z_456ba995_dlq_failure_path.matrix_dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
          "retry_of_status": "failed",
          "subject": "dharma.a2a.task.nats_live_20260701t033809z_456ba995_dlq_failure_path.matrix_dlq_failure_path",
          "surface": "a2a.nats_transport.consume"
        },
        "receipt_id": "rr_b504e8002a0745d7",
        "receipt_type": "nats_consume",
        "run_id": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
        "side_effect_key": "nats_consume:dharma.a2a.task.nats_live_20260701t033809z_456ba995_dlq_failure_path.matrix_dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317:retry:3cd58f610bcb",
        "status": "nack",
        "task_id": "nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
        "trace_id": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317"
      }
    ],
    "status": "nack",
    "subject": "dharma.a2a.task.nats_live_20260701t033809z_456ba995_dlq_failure_path.matrix_dlq_failure_path",
    "task_id": "nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317"
  },
  "message_id": "nmsg_eb75b037188df853ebb188585ca4687d",
  "model_provider_id": "ollama:glm-5.2:cloud",
  "name": "dlq_failure_path",
  "operator_visible": true,
  "operator_visible_state": {
    "ack_floor": {
      "consumer_seq": 185,
      "last_active": "2026-07-01T03:38:15.414083+00:00",
      "stream_seq": 102
    },
    "delivered": {
      "consumer_seq": 188,
      "last_active": "2026-07-01T03:38:15.764469+00:00",
      "stream_seq": 103
    },
    "final_stream_sequence": 103,
    "num_ack_pending": 1,
    "num_pending": 0,
    "num_redelivered": 13
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
  "status": "pass",
  "stream_name": "DS_TASKS",
  "task_id": "nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317",
  "timestamp": "2026-07-01T03:38:15Z",
  "trace_id": "nats-live-20260701T033809Z-456ba995:dlq_failure_path:nats_live_20260701T033809Z_456ba995_dlq_failure_path_f76a0317"
}
```

### restart_path

```json
{
  "agent_id": "nats_live_20260701T033809Z_456ba995_restart_path",
  "broker_url": "nats://127.0.0.1:4222",
  "cleanup_ack": {
    "action": "ack",
    "duplicate": false,
    "error": "",
    "message_id": "nmsg_a64367c2fad026b36e9f99e157a76f1b",
    "receipt_id": "rr_1dee1f42904a4ff5",
    "status": "ack",
    "subject": "dharma.a2a.task.nats_live_20260701t033809z_456ba995_restart_path.matrix_restart_path",
    "task_id": "nats_live_20260701T033809Z_456ba995_restart_path_11416ec9"
  },
  "consumer_name": "a2a_task_handler",
  "first_delivery_metadata": {
    "consumer_sequence": 189,
    "num_delivered": 1,
    "stream_sequence": 104,
    "timestamp": "2026-07-01T03:38:15.926353+00:00"
  },
  "message_id": "nmsg_a64367c2fad026b36e9f99e157a76f1b",
  "model_provider_id": "ollama:glm-5.2:cloud",
  "name": "restart_path",
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
    "consumer_sequence": 190,
    "num_delivered": 2,
    "stream_sequence": 104,
    "timestamp": "2026-07-01T03:38:15.926353+00:00"
  },
  "restart_wait_seconds": 65,
  "status": "pass",
  "stream_name": "DS_TASKS",
  "task_id": "nats_live_20260701T033809Z_456ba995_restart_path_11416ec9",
  "timestamp": "2026-07-01T03:39:21Z",
  "trace_id": "nats-live-20260701T033809Z-456ba995:restart_path:nats_live_20260701T033809Z_456ba995_restart_path_11416ec9"
}
```

### compatibility_bypass_contract

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
  "timestamp": "2026-07-01T03:39:21Z",
  "trace_id": "nats-live-20260701T033809Z-456ba995"
}
```

### governance_negative_path

```json
{
  "agent_id": "governance",
  "broker_url": "nats://127.0.0.1:4222",
  "consumer_name": "a2a_task_handler",
  "expected_failure_contains": "missing required rows",
  "message_id": null,
  "model_provider_id": "ollama:glm-5.2:cloud",
  "name": "governance_negative_path",
  "negative_command": [
    "/Users/dhyana/dharma_swarm/.venv/bin/python",
    "/Users/dhyana/ds_runtime_truth_nats_clean_20260701/scripts/governance/check_nats_live_production_evidence.py",
    "--evidence",
    "/var/folders/2n/h27kz83n6dn90pzkb_8v3pm80000gn/T/nats-matrix-negative-b0xx3me9/tampered.json",
    "--max-age-hours",
    "999999"
  ],
  "negative_return_code": 1,
  "negative_stderr": "NATS_LIVE_PRODUCTION_EVIDENCE_FAILED EvidenceError: missing required rows: ['happy_path', 'governance_negative_path']\n",
  "negative_stdout": "",
  "status": "pass",
  "stream_name": "DS_TASKS",
  "tamper_description": "removed the required happy_path row from otherwise fresh live evidence",
  "tampered_row_removed": "happy_path",
  "task_id": null,
  "timestamp": "2026-07-01T03:39:21Z",
  "trace_id": "nats-live-20260701T033809Z-456ba995"
}
```

## Semantic Receipt

```json
{
  "content": "{\"run_id\":\"nats-live-20260701T033809Z-456ba995\",\"task_id\":\"nats_live_20260701T033809Z_456ba995_happy_path_474a05a9\",\"label\":\"happy_path\",\"status\":\"confirmed\",\"mode\":\"live_semantic_execution\"}",
  "provider": "ollama",
  "requested_model": "glm-5.2:cloud",
  "response_model": "glm-5.2",
  "schema": "dharma.nats.live_matrix.semantic_receipt.v1",
  "started_at": "2026-07-01T03:38:09Z",
  "task_id": "nats_live_20260701T033809Z_456ba995_happy_path_474a05a9",
  "timestamp": "2026-07-01T03:38:13Z",
  "trace_id": "nats-live-20260701T033809Z-456ba995:happy_path:nats_live_20260701T033809Z_456ba995_happy_path_474a05a9",
  "usage": {
    "completion_tokens": 99,
    "prompt_tokens": 98,
    "total_tokens": 197
  }
}
```

## Negative Command Evidence

```json
[
  {
    "command": [
      "/Users/dhyana/dharma_swarm/.venv/bin/python",
      "/Users/dhyana/ds_runtime_truth_nats_clean_20260701/scripts/governance/check_nats_live_production_evidence.py",
      "--evidence",
      "/var/folders/2n/h27kz83n6dn90pzkb_8v3pm80000gn/T/nats-matrix-negative-b0xx3me9/tampered.json",
      "--max-age-hours",
      "999999"
    ],
    "return_code": 1,
    "stderr": "NATS_LIVE_PRODUCTION_EVIDENCE_FAILED EvidenceError: missing required rows: ['happy_path', 'governance_negative_path']\n",
    "stdout": "",
    "timestamp": "2026-07-01T03:39:21Z"
  }
]
```

## Source Freshness Fingerprints

```json
{
  "dharma_swarm/a2a/a2a_bridge.py": {
    "exists": true,
    "mtime": "2026-07-01T03:27:12.713233Z",
    "sha256": "b4a138c3c9647258b8cd30fecd6df4ffedfce8ca3a4e05f3d7baec21b4e9602b",
    "size": 17457
  },
  "dharma_swarm/a2a/a2a_cloud_contact.py": {
    "exists": true,
    "mtime": "2026-07-01T03:26:56.875967Z",
    "sha256": "8e67b78b4c5e815308b4f64632de641aece34b2f27d53cbcc5ff3a4caebc050e",
    "size": 6668
  },
  "dharma_swarm/a2a/a2a_server.py": {
    "exists": true,
    "mtime": "2026-07-01T03:27:12.713408Z",
    "sha256": "4b7cb34a2a96dc5ea53d5ada1df0110dd483ad4cf5602c757b5b2fc84f75d2cf",
    "size": 26197
  },
  "dharma_swarm/a2a/nats_transport.py": {
    "exists": true,
    "mtime": "2026-07-01T03:27:12.713597Z",
    "sha256": "e90b1eb0b1bcfecf38f263ee8d97a37ae08bbda93d39e1f9d5bb40d14506baae",
    "size": 39502
  },
  "dharma_swarm/operator_core/nats_live_contact.py": {
    "exists": true,
    "mtime": "2026-07-01T03:27:12.713736Z",
    "sha256": "c728f8064477894295407ea7b32727ae4f5a0c57e932836965afceecf2bac202",
    "size": 8126
  },
  "dharma_swarm/operator_core/nats_substrate_status.py": {
    "exists": true,
    "mtime": "2026-07-01T03:26:56.982886Z",
    "sha256": "dde9020f72ca67a1ac99296e366192ced80297f03c617a71c28c61323d302446",
    "size": 5687
  },
  "dharma_swarm/runtime_state.py": {
    "exists": true,
    "mtime": "2026-07-01T03:27:12.713818Z",
    "sha256": "25e40a99d46280bb064d56c06ddfbeb7421326e4bff6eab5aaee06da9d7c042f",
    "size": 163007
  },
  "docs/governance/ACTIVE_TRACK.yaml": {
    "exists": true,
    "mtime": "2026-07-01T03:30:10.027164Z",
    "sha256": "24fd0dcd8fa6fe1e5cf064ae951a638b646cb2ae5e8baa1afc8b6963a26aa641",
    "size": 142264
  },
  "docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md": {
    "exists": true,
    "mtime": "2026-07-01T03:26:57.070566Z",
    "sha256": "1fd6fa6704dd557172ad0851e781bf179248d7053c7417aee704110af5b8ff9c",
    "size": 14581
  },
  "scripts/governance/check_nats_live_production_evidence.py": {
    "exists": true,
    "mtime": "2026-07-01T00:31:11.571210Z",
    "sha256": "fc274e657daf025d203b5fc9607cea769c213c78ef777e82e7c81cda68d2b9c2",
    "size": 20243
  },
  "scripts/governance/check_nats_substrate_contract.py": {
    "exists": true,
    "mtime": "2026-07-01T03:27:12.714287Z",
    "sha256": "a6a2207b21b907a742bcd11cfa0ea0410c4748a3f5bd79029d1ffa1ad89e7bb8",
    "size": 17241
  },
  "scripts/governance/check_track_status.py": {
    "exists": true,
    "mtime": "2026-07-01T03:37:41.026458Z",
    "sha256": "1b64d99b47a4f35e33acf5983481c21d84b5b80301c910e528a270a453aec7d0",
    "size": 41488
  },
  "scripts/governance/run_nats_live_production_matrix.py": {
    "exists": true,
    "mtime": "2026-07-01T00:33:50.481642Z",
    "sha256": "f17ce917c7f724cb3bd2487002308c899f61302a30430e1517ca59e18fe97317",
    "size": 56868
  },
  "scripts/runtime/a2a_domain_reply_worker.py": {
    "exists": true,
    "mtime": "2026-07-01T03:26:57.476393Z",
    "sha256": "b299a848ee65c5c7ba6625673993b3e0b1a0820b573f85c9bef1d8b329af8ead",
    "size": 23376
  },
  "scripts/runtime/a2a_inbox_bridge.py": {
    "exists": true,
    "mtime": "2026-07-01T03:26:57.476692Z",
    "sha256": "b3670b0f8aace08d78bea741eaefbd1d43f0c2ea3b2b9ab52195ee2ca521883c",
    "size": 17623
  },
  "scripts/runtime/a2a_reply_capture.py": {
    "exists": true,
    "mtime": "2026-07-01T03:26:57.476982Z",
    "sha256": "78f83ccc95070a817aaf3dc838b133accf07fbf64728542674f895e9bf294963",
    "size": 16757
  },
  "scripts/runtime/a2a_send.py": {
    "exists": true,
    "mtime": "2026-07-01T03:27:12.714589Z",
    "sha256": "4d9fc3ee3deabd751f5eb07556529a743687c34b48dc6fc4c9469c43694a6154",
    "size": 32813
  },
  "tests/test_a2a_cloud_contact.py": {
    "exists": true,
    "mtime": "2026-07-01T03:26:57.528456Z",
    "sha256": "e618718df674c91c8ecb8b445a62f1be22cde72b68dff8b39cdb851d602188ca",
    "size": 6368
  },
  "tests/test_nats_substrate_contract.py": {
    "exists": true,
    "mtime": "2026-07-01T00:31:40.711724Z",
    "sha256": "ff08ffb46abbf0abd822fd3c3e1909e31595dfa3a32eb551b6f89afda5b5d7fd",
    "size": 8072
  },
  "tests/test_nats_transport.py": {
    "exists": true,
    "mtime": "2026-07-01T03:27:12.714756Z",
    "sha256": "a815b9144cf4282bd2592f4c62fa08fdec106680b4ddd6e0751a8de83a0d4831",
    "size": 24635
  }
}
```
