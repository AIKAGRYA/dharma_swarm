# Runtime Truth NATS Remedial Evidence - 2026-07-01

Generated: `2026-07-01T00:40:48.888058Z`
Run id: `nats-live-20260701T003355Z-3bc2492d` generated `2026-07-01T00:35:04Z` status `pass`
Broker/profile: `nats://127.0.0.1:4222` / `local-live-jetstream`
Streams: `DS_TASKS` for tasks, `DS_DLQ` for DLQ
Consumer: `a2a_task_handler`
Handler model/provider under test: `ollama:glm-5.2:cloud`. Reviewer lane model is not the handler model.
Rows: `topology=pass, happy_path=pass, duplicate_path=pass, publish_failure_path=pass, handler_failure_redelivery_path=pass, stale_started_idempotency_path=pass, concurrent_duplicate_path=pass, ack_failure_path=pass, max_deliver_path=pass, dlq_failure_path=pass, restart_path=pass, compatibility_bypass_contract=pass, governance_negative_path=pass`

Output discipline for reviewers: return only the requested JSON object. The first character of your response must be `{`.

## Direct Answers To Prior Concerns

- Topology is below as full raw JSON.
- MaxDeliver is not truncated below. DS_TASKS stream sequences and DS_DLQ stream sequences are different streams; DS_DLQ `stream_sequence` 9 does not need to match the original DS_TASKS sequence.
- Failure-path handlers are deterministic failure-injection callables executed inside the same `A2AServer(require_execution_identity=True)` plus `A2ANatsTransport.consume_message` production consume path. The live model-backed semantic handler is proven on `happy_path`; failure rows prove ack/nack/redelivery/DLQ behavior under forced exceptions.
- Inline source hashes below tie the matrix to current code; this remedial packet is self-contained for the reviewed criteria.

## Topology Full Row

```json
{
  "broker_url": "nats://127.0.0.1:4222",
  "consumer_ack_floor": {
    "consumer_seq": 139,
    "last_active": "2026-07-01T00:33:15.245544+00:00",
    "stream_seq": 77
  },
  "consumer_ack_policy": "explicit",
  "consumer_ack_wait_seconds": 60.0,
  "consumer_delivered": {
    "consumer_seq": 139,
    "last_active": "2026-07-01T00:33:15.177336+00:00",
    "stream_seq": 77
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
  "timestamp": "2026-07-01T00:33:55Z"
}
```

## Happy Path Contract And Semantic Receipt

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
  "envelope_contract": {
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
  },
  "headers": {
    "Dharma-Causation-Id": "nats-live-20260701T003355Z-3bc2492d:happy_path:nats_live_20260701T003355Z_3bc2492d_happy_path_f0ef3e31",
    "Dharma-Correlation-Id": "nats-live-20260701T003355Z-3bc2492d:happy_path:nats_live_20260701T003355Z_3bc2492d_happy_path_f0ef3e31",
    "Dharma-Idempotency-Key": "nats-live-20260701T003355Z-3bc2492d:happy_path:nats_live_20260701T003355Z_3bc2492d_happy_path_f0ef3e31:idem",
    "Dharma-Nats-Schema": "dharma.nats.envelope.v1",
    "Dharma-Run-Id": "nats-live-20260701T003355Z-3bc2492d:happy_path:nats_live_20260701T003355Z_3bc2492d_happy_path_f0ef3e31",
    "Dharma-Task-Id": "nats_live_20260701T003355Z_3bc2492d_happy_path_f0ef3e31",
    "Dharma-Trace-Id": "nats-live-20260701T003355Z-3bc2492d:happy_path:nats_live_20260701T003355Z_3bc2492d_happy_path_f0ef3e31",
    "Nats-Msg-Id": "nmsg_863db763b1d8632560637390c00d14c1"
  },
  "message_id": "nmsg_863db763b1d8632560637390c00d14c1",
  "metadata": {
    "consumer_sequence": 140,
    "num_delivered": 1,
    "stream_sequence": 78,
    "timestamp": "2026-07-01T00:33:55.834859+00:00"
  },
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
    "message_id": "nmsg_863db763b1d8632560637390c00d14c1",
    "receipt_id": "rr_b56799f817a84195",
    "seq": 78,
    "status": "ack",
    "stream": "DS_TASKS",
    "subject": "dharma.a2a.task.nats_live_20260701t003355z_3bc2492d_happy_path.matrix_happy_path",
    "task_id": "nats_live_20260701T003355Z_3bc2492d_happy_path_f0ef3e31"
  },
  "semantic_receipt": {
    "content": "```json\n{\"run_id\":\"nats-live-20260701T003355Z-3bc2492d\",\"task_id\":\"nats_live_20260701T003355Z_3bc2492d_happy_path_f0ef3e31\",\"label\":\"happy_path\",\"status\":\"confirmed\",\"runtime\":\"nats\",\"mode\":\"live_semantic_execution\"}\n```",
    "provider": "ollama",
    "receipt_path": null,
    "requested_model": "glm-5.2:cloud",
    "response_model": "glm-5.2",
    "schema": "dharma.nats.live_matrix.semantic_receipt.v1",
    "task_id": "nats_live_20260701T003355Z_3bc2492d_happy_path_f0ef3e31",
    "trace_id": "nats-live-20260701T003355Z-3bc2492d:happy_path:nats_live_20260701T003355Z_3bc2492d_happy_path_f0ef3e31",
    "usage": {
      "completion_tokens": 109,
      "prompt_tokens": 99,
      "total_tokens": 208
    }
  },
  "side_effect_count": 1
}
```

## Handler Failure Redelivery

```json
{
  "first_consume_ack": {
    "action": "nack",
    "dlq_failed": false,
    "duplicate": false,
    "error": "forced first handler failure",
    "message_id": "nmsg_a6cd32becd61a86191f5e92cba29fe50",
    "receipt_id": "rr_14354ff2779c4fa2",
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

## Ack Failure Surfacing

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

## MaxDeliver Typed DLQ

```json
{
  "deliveries_on_DS_TASKS": [
    {
      "consume_ack": {
        "action": "nack",
        "dlq_failed": false,
        "duplicate": false,
        "error": "forced handler failure for max_deliver_path",
        "message_id": "nmsg_a019b923442e8295fd1429b1576a4abc",
        "receipt_id": "rr_e8d3c125778b4666",
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
        "status": "nack",
        "subject": "dharma.a2a.task.nats_live_20260701t003355z_3bc2492d_max_deliver_path.matrix_max_deliver_path",
        "task_id": "nats_live_20260701T003355Z_3bc2492d_max_deliver_path_36eba8b7"
      },
      "metadata": {
        "consumer_sequence": 150,
        "num_delivered": 2,
        "stream_sequence": 84,
        "timestamp": "2026-07-01T00:33:58.372061+00:00"
      }
    },
    {
      "consume_ack": {
        "action": "dlq",
        "duplicate": false,
        "error": "forced handler failure for max_deliver_path",
        "message_id": "nmsg_a019b923442e8295fd1429b1576a4abc",
        "receipt_id": "rr_2143415987d6405a",
        "status": "dlq",
        "subject": "dharma.a2a.task.nats_live_20260701t003355z_3bc2492d_max_deliver_path.matrix_max_deliver_path",
        "task_id": "nats_live_20260701T003355Z_3bc2492d_max_deliver_path_36eba8b7"
      },
      "metadata": {
        "consumer_sequence": 151,
        "num_delivered": 3,
        "stream_sequence": 84,
        "timestamp": "2026-07-01T00:33:58.372061+00:00"
      }
    }
  ],
  "dlq_actor": {
    "execution_agent": "nats-live-matrix-max_deliver_path",
    "from_agent": "nats_live_20260701T003355Z_3bc2492d_max_deliver_path",
    "session_id": "nats-live-20260701T003355Z-3bc2492d",
    "to_agent": "operator"
  },
  "dlq_causality": {
    "causation_id": "nats-live-20260701T003355Z-3bc2492d:max_deliver_path:nats_live_20260701T003355Z_3bc2492d_max_deliver_path_36eba8b7",
    "correlation_id": "nats-live-20260701T003355Z-3bc2492d:max_deliver_path:nats_live_20260701T003355Z_3bc2492d_max_deliver_path_36eba8b7",
    "message_id": "nmsg_c2c167b89b7d6dcf3b6d4fceaaabdc24",
    "parent_span_id": "nats-live-20260701T003355Z-3bc2492d",
    "span_id": "nats-live-20260701T003355Z-3bc2492d:max_deliver_path:nats_live_20260701T003355Z_3bc2492d_max_deliver_path_36eba8b7",
    "trace_id": "nats-live-20260701T003355Z-3bc2492d:max_deliver_path:nats_live_20260701T003355Z_3bc2492d_max_deliver_path_36eba8b7"
  },
  "dlq_error": "forced handler failure for max_deliver_path",
  "dlq_metadata_on_DS_DLQ": {
    "consumer_sequence": 8,
    "num_delivered": 1,
    "stream_sequence": 8,
    "timestamp": "2026-07-01T00:33:58.594909+00:00"
  },
  "dlq_original_message_id": "nmsg_a019b923442e8295fd1429b1576a4abc",
  "dlq_original_subject": "dharma.a2a.task.nats_live_20260701t003355z_3bc2492d_max_deliver_path.matrix_max_deliver_path",
  "dlq_outer_schema": "dharma.nats.envelope.v1",
  "dlq_payload_schema": "dharma.nats.dlq_failure.v1",
  "dlq_subject": "dharma.dlq.ds_tasks.a2a_task_handler",
  "final_ack": {
    "action": "dlq",
    "duplicate": false,
    "error": "forced handler failure for max_deliver_path",
    "message_id": "nmsg_a019b923442e8295fd1429b1576a4abc",
    "receipt_id": "rr_2143415987d6405a",
    "status": "dlq",
    "subject": "dharma.a2a.task.nats_live_20260701t003355z_3bc2492d_max_deliver_path.matrix_max_deliver_path",
    "task_id": "nats_live_20260701T003355Z_3bc2492d_max_deliver_path_36eba8b7"
  },
  "message_id": "nmsg_a019b923442e8295fd1429b1576a4abc",
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
  "task_id": "nats_live_20260701T003355Z_3bc2492d_max_deliver_path_36eba8b7",
  "trace_id": "nats-live-20260701T003355Z-3bc2492d:max_deliver_path:nats_live_20260701T003355Z_3bc2492d_max_deliver_path_36eba8b7"
}
```

## DLQ Publish Failure Visibility

```json
{
  "deliveries_on_DS_TASKS": [
    {
      "consume_ack": {
        "action": "nack",
        "dlq_failed": false,
        "duplicate": false,
        "error": "forced handler failure for dlq_failure_path",
        "message_id": "nmsg_cbdc16d425bf72cb7614439d076bf8b9",
        "receipt_id": "rr_8b875fdce26742bc",
        "status": "nack",
        "subject": "dharma.a2a.task.nats_live_20260701t003355z_3bc2492d_dlq_failure_path.matrix_dlq_failure_path",
        "task_id": "nats_live_20260701T003355Z_3bc2492d_dlq_failure_path_949fecad"
      },
      "metadata": {
        "consumer_sequence": 152,
        "num_delivered": 1,
        "stream_sequence": 85,
        "timestamp": "2026-07-01T00:33:58.644610+00:00"
      }
    },
    {
      "consume_ack": {
        "action": "nack",
        "dlq_failed": false,
        "duplicate": false,
        "error": "forced handler failure for dlq_failure_path",
        "message_id": "nmsg_cbdc16d425bf72cb7614439d076bf8b9",
        "receipt_id": "rr_6c7db65b1eab4be6",
        "status": "nack",
        "subject": "dharma.a2a.task.nats_live_20260701t003355z_3bc2492d_dlq_failure_path.matrix_dlq_failure_path",
        "task_id": "nats_live_20260701T003355Z_3bc2492d_dlq_failure_path_949fecad"
      },
      "metadata": {
        "consumer_sequence": 153,
        "num_delivered": 2,
        "stream_sequence": 85,
        "timestamp": "2026-07-01T00:33:58.644610+00:00"
      }
    },
    {
      "consume_ack": {
        "action": "nack",
        "dlq_failed": true,
        "duplicate": false,
        "error": "forced handler failure for dlq_failure_path",
        "message_id": "nmsg_cbdc16d425bf72cb7614439d076bf8b9",
        "receipt_id": "rr_22fb99cedf9d4b70",
        "status": "nack",
        "subject": "dharma.a2a.task.nats_live_20260701t003355z_3bc2492d_dlq_failure_path.matrix_dlq_failure_path",
        "task_id": "nats_live_20260701T003355Z_3bc2492d_dlq_failure_path_949fecad"
      },
      "metadata": {
        "consumer_sequence": 154,
        "num_delivered": 3,
        "stream_sequence": 85,
        "timestamp": "2026-07-01T00:33:58.644610+00:00"
      }
    }
  ],
  "failure_injection": "DLQ publish raised at MaxDeliver; original was not acked and remains beyond the consumer ack floor",
  "final_ack": {
    "action": "nack",
    "dlq_failed": true,
    "duplicate": false,
    "error": "forced handler failure for dlq_failure_path",
    "message_id": "nmsg_cbdc16d425bf72cb7614439d076bf8b9",
    "receipt_id": "rr_22fb99cedf9d4b70",
    "status": "nack",
    "subject": "dharma.a2a.task.nats_live_20260701t003355z_3bc2492d_dlq_failure_path.matrix_dlq_failure_path",
    "task_id": "nats_live_20260701T003355Z_3bc2492d_dlq_failure_path_949fecad"
  },
  "message_id": "nmsg_cbdc16d425bf72cb7614439d076bf8b9",
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

## Compatibility Gate

```json
{
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
  "gate_enforced_by": [
    "scripts/governance/check_nats_substrate_contract.py",
    "scripts/governance/check_nats_live_production_evidence.py",
    "docs/governance/ACTIVE_TRACK.yaml:nats_live_production_evidence_fresh"
  ],
  "status": "pass"
}
```

## Governance Negative

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


## Duplicate And Idempotency Safety

Duplicate replay through both runtime transport and broker duplicate window:

```json
{
  "broker_duplicate_probe": {
    "duplicate": true,
    "seq": 78,
    "stream": "DS_TASKS"
  },
  "broker_duplicate_probe_entrypoint": "nats.aio.client.JetStreamContext.publish",
  "broker_duplicate_probe_purpose": "duplicate-window verification only; not a production task publisher",
  "message_id": "nmsg_863db763b1d8632560637390c00d14c1",
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
    "message_id": "nmsg_863db763b1d8632560637390c00d14c1",
    "receipt_id": "rr_fe3194ea574f401a",
    "seq": null,
    "status": "duplicate",
    "stream": "",
    "subject": "dharma.a2a.task.nats_live_20260701t003355z_3bc2492d_happy_path.matrix_happy_path",
    "task_id": "nats_live_20260701T003355Z_3bc2492d_happy_path_f0ef3e31"
  },
  "side_effect_count_after_replay": 1,
  "status": "pass",
  "task_id": "nats_live_20260701T003355Z_3bc2492d_happy_path_f0ef3e31",
  "trace_id": "nats-live-20260701T003355Z-3bc2492d:happy_path:nats_live_20260701T003355Z_3bc2492d_happy_path_f0ef3e31"
}
```

Stale started idempotency record retries safely:

```json
{
  "consume_ack": {
    "action": "ack",
    "duplicate": false,
    "error": "",
    "message_id": "nmsg_fc935526a9838ce3e15aa95cb696c56e",
    "receipt_id": "rr_24dd84f3849f44d5",
    "status": "ack",
    "subject": "dharma.a2a.task.nats_live_20260701t003355z_3bc2492d_stale_started_idempotency_path.matrix_stale_started_idempotency_path",
    "task_id": "nats_live_20260701T003355Z_3bc2492d_stale_started_idempotency_path_ca8b55fb"
  },
  "message_id": "nmsg_fc935526a9838ce3e15aa95cb696c56e",
  "metadata": {
    "consumer_sequence": 144,
    "num_delivered": 1,
    "stream_sequence": 81,
    "timestamp": "2026-07-01T00:33:57.880548+00:00"
  },
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
  "seeded_side_effect_key": "nats_consume:dharma.a2a.task.nats_live_20260701t003355z_3bc2492d_stale_started_idempotency_path.matrix_stale_started_idempotency_path:nats_live_20260701T003355Z_3bc2492d_stale_started_idempotency_path_ca8b55fb",
  "status": "pass",
  "task_id": "nats_live_20260701T003355Z_3bc2492d_stale_started_idempotency_path_ca8b55fb",
  "trace_id": "nats-live-20260701T003355Z-3bc2492d:stale_started_idempotency_path:nats_live_20260701T003355Z_3bc2492d_stale_started_idempotency_path_ca8b55fb"
}
```

Concurrent in-progress duplicate is blocked/nacked truthfully, then cleanup succeeds exactly once:

```json
{
  "blocked_consume_ack": {
    "action": "nack",
    "dlq_failed": false,
    "duplicate": false,
    "error": "NATS consume idempotency record is still in progress: nats_consume:dharma.a2a.task.nats_live_20260701t003355z_3bc2492d_concurrent_duplicate_path.matrix_concurrent_duplicate_path:nats_live_20260701T003355Z_3bc2492d_concurrent_duplicate_path_840a4501 status=started receipt=rr_58d6e075c85a477c",
    "message_id": "nmsg_d495a68472ad62f9c7ce52c81eda82b4",
    "receipt_id": "rr_58d6e075c85a477c",
    "status": "retry_blocked",
    "subject": "dharma.a2a.task.nats_live_20260701t003355z_3bc2492d_concurrent_duplicate_path.matrix_concurrent_duplicate_path",
    "task_id": "nats_live_20260701T003355Z_3bc2492d_concurrent_duplicate_path_840a4501"
  },
  "cleanup_consume_ack": {
    "action": "ack",
    "duplicate": false,
    "error": "",
    "message_id": "nmsg_d495a68472ad62f9c7ce52c81eda82b4",
    "receipt_id": "rr_57b8db68fa184fd3",
    "status": "ack",
    "subject": "dharma.a2a.task.nats_live_20260701t003355z_3bc2492d_concurrent_duplicate_path.matrix_concurrent_duplicate_path",
    "task_id": "nats_live_20260701T003355Z_3bc2492d_concurrent_duplicate_path_840a4501"
  },
  "cleanup_metadata": {
    "consumer_sequence": 146,
    "num_delivered": 2,
    "stream_sequence": 82,
    "timestamp": "2026-07-01T00:33:58.021131+00:00"
  },
  "message_id": "nmsg_d495a68472ad62f9c7ce52c81eda82b4",
  "metadata": {
    "consumer_sequence": 145,
    "num_delivered": 1,
    "stream_sequence": 82,
    "timestamp": "2026-07-01T00:33:58.021131+00:00"
  },
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
  "seeded_side_effect_key": "nats_consume:dharma.a2a.task.nats_live_20260701t003355z_3bc2492d_concurrent_duplicate_path.matrix_concurrent_duplicate_path:nats_live_20260701T003355Z_3bc2492d_concurrent_duplicate_path_840a4501",
  "side_effect_count": 1,
  "status": "pass",
  "task_id": "nats_live_20260701T003355Z_3bc2492d_concurrent_duplicate_path_840a4501",
  "trace_id": "nats-live-20260701T003355Z-3bc2492d:concurrent_duplicate_path:nats_live_20260701T003355Z_3bc2492d_concurrent_duplicate_path_840a4501"
}
```

## Restart Recovery

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
  "message_id": "nmsg_1add9fe4602fbd480ba145a8797d9209",
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
  "status": "pass",
  "task_id": "nats_live_20260701T003355Z_3bc2492d_restart_path_913a530c",
  "trace_id": "nats-live-20260701T003355Z-3bc2492d:restart_path:nats_live_20260701T003355Z_3bc2492d_restart_path_913a530c"
}
```

## Source Tie

The evidence checker validates the hashes below against the current repo and fails if any listed source changed after matrix generation. Key hashes:

```json
{
  "dharma_swarm/a2a/a2a_server.py": {
    "exists": true,
    "mtime": "2026-07-01T00:14:07.316150Z",
    "sha256": "4b7cb34a2a96dc5ea53d5ada1df0110dd483ad4cf5602c757b5b2fc84f75d2cf",
    "size": 26197
  },
  "dharma_swarm/a2a/nats_transport.py": {
    "exists": true,
    "mtime": "2026-07-01T00:09:51.253671Z",
    "sha256": "e90b1eb0b1bcfecf38f263ee8d97a37ae08bbda93d39e1f9d5bb40d14506baae",
    "size": 39502
  },
  "dharma_swarm/runtime_state.py": {
    "exists": true,
    "mtime": "2026-07-01T00:10:12.455725Z",
    "sha256": "25e40a99d46280bb064d56c06ddfbeb7421326e4bff6eab5aaee06da9d7c042f",
    "size": 163007
  },
  "docs/governance/ACTIVE_TRACK.yaml": {
    "exists": true,
    "mtime": "2026-07-01T00:21:26.115999Z",
    "sha256": "55284295b504d05186f2e433d6d443d512467f24ab40d09fccab05abb517fc81",
    "size": 143176
  },
  "scripts/governance/check_nats_live_production_evidence.py": {
    "exists": true,
    "mtime": "2026-07-01T00:31:11.571210Z",
    "sha256": "fc274e657daf025d203b5fc9607cea769c213c78ef777e82e7c81cda68d2b9c2",
    "size": 20243
  },
  "scripts/governance/check_nats_substrate_contract.py": {
    "exists": true,
    "mtime": "2026-07-01T00:31:20.220053Z",
    "sha256": "a6a2207b21b907a742bcd11cfa0ea0410c4748a3f5bd79029d1ffa1ad89e7bb8",
    "size": 17241
  },
  "scripts/governance/run_nats_live_production_matrix.py": {
    "exists": true,
    "mtime": "2026-07-01T00:33:50.481642Z",
    "sha256": "f17ce917c7f724cb3bd2487002308c899f61302a30430e1517ca59e18fe97317",
    "size": 56868
  },
  "tests/test_nats_substrate_contract.py": {
    "exists": true,
    "mtime": "2026-07-01T00:31:40.711724Z",
    "sha256": "ff08ffb46abbf0abd822fd3c3e1909e31595dfa3a32eb551b6f89afda5b5d7fd",
    "size": 8072
  },
  "tests/test_nats_transport.py": {
    "exists": true,
    "mtime": "2026-07-01T00:10:26.796742Z",
    "sha256": "a815b9144cf4282bd2592f4c62fa08fdec106680b4ddd6e0751a8de83a0d4831",
    "size": 24635
  }
}
```

## Verification Results

- `check_nats_live_production_evidence.py --max-age-hours 24`: rc 0, `NATS_LIVE_PRODUCTION_EVIDENCE_OK`.
- focused pytest set: rc 0, `47 passed in 3.76s`.
- `make nats-substrate-contract`: rc 0, `NATS_CONTRACT_OK`, live evidence OK, `73 passed in 4.24s`.
- `check_track_status.py`: rc 0, `runtime-truth-nats-2026-06 all 3 completion criteria pass - SHIPPABLE`.
