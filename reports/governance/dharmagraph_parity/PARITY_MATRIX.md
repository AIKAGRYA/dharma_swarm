# DharmaGraph x LangGraph parity: 31.00/100

**Verdict: NOT_FINISHED. Closeout blocked: true.**

Target: LangGraph `1.2.4` at tag SHA `054a6f3d8b48d022a4881af3ba3dc0ddc3ac0690`. Rubric commit: `7b8662ed5f1bed2eb2ed4a7d7ea21df42bb3a99a`. Dharma SHA: `5453c6dd981f308fea31f88702c420fa8afa2a31`.

## Gaps

- `LG01` — State, input, output, and context schemas with partial updates (1/2, weight 4); card `parity-gap-lg01-schemas`.
- `LG02` — Node registration metadata, schemas, destinations, and default policies (0/2, weight 2); card `parity-gap-lg02-node-policies`.
- `LG03` — Deferred and finalization nodes (0/2, weight 1); card `parity-gap-lg03-defer`.
- `LG04` — Static topology, sequence, entry/finish, and ALL barrier edges (1/2, weight 2); card `parity-gap-lg04-topology`.
- `LG06` — Bulk-synchronous parallel supersteps and step atomicity (1/2, weight 2); card `parity-gap-lg06-supersteps`.
- `LG07` — Dynamic Send fan-out and map-reduce (1/2, weight 1); card `parity-gap-lg07-send`.
- `LG08` — Command update, multi-target goto, parent routing, and resume (1/2, weight 2); card `parity-gap-lg08-command`.
- `LG09` — Cycles, recursion caps, and managed remaining-step state (1/2, weight 1); card `parity-gap-lg09-cycles`.
- `LG10` — Reducer and channel semantics with concurrent-write conflicts (1/2, weight 4); card `parity-gap-lg10-reducers`.
- `LG11` — Message accumulation, replacement, removal, and formatting (0/2, weight 2); card `parity-gap-lg11-messages`.
- `LG12` — Compilation and sync/async single-run interfaces (1/2, weight 4); card `parity-gap-lg12-invocation`.
- `LG13` — Batch, as-completed, and max-concurrency interfaces (0/2, weight 1); card `parity-gap-lg13-batch`.
- `LG14` — Checkpoint schema, saver protocol, pending writes, lineage, and serializer (1/2, weight 4); card `parity-gap-lg14-checkpoint-protocol`.
- `LG15` — Thread-scoped continuity and resume (0/2, weight 9); card `parity-gap-lg15-thread-resume`.
- `LG16` — State inspection, history, and replay (1/2, weight 2); card `parity-gap-lg16-history`.
- `LG17` — Manual state update, bulk update, fork, and time travel (1/2, weight 8); card `parity-gap-lg17-fork-time-travel`.
- `LG18` — Durability ordering and process-restart recovery (1/2, weight 10); card `parity-gap-lg18-process-restart`.
- `LG19` — Static interrupt-before and interrupt-after (0/2, weight 1); card `parity-gap-lg19-static-interrupts`.
- `LG20` — Dynamic HITL interrupt and resume (0/2, weight 2); card `parity-gap-lg20-dynamic-interrupt`.
- `LG21` — Seven standard stream modes, multi-mode, typed v2, and subgraph namespaces (0/2, weight 1); card `parity-gap-lg21-streaming`.
- `LG22` — Experimental event stream v3 and transformer projections (0/2, weight 1); card `parity-gap-lg22-stream-v3`.
- `LG23` — Nested graphs, parent commands, inheritance, nested state, and streaming (0/2, weight 1); card `parity-gap-lg23-subgraphs`.
- `LG24` — Retry selection, backoff, jitter, attempts, and write clearing (0/2, weight 4); card `parity-gap-lg24-retry`.
- `LG25` — Hard/idle timeout, heartbeat, and retry interaction (0/2, weight 2); card `parity-gap-lg25-timeout`.
- `LG26` — Error propagation, sibling cancellation, handlers, and atomic writes (1/2, weight 4); card `parity-gap-lg26-errors`.
- `LG27` — Long-term Store CRUD, namespaces, filters, paging, async, and batch (0/2, weight 1); card `parity-gap-lg27-store`.
- `LG28` — Store semantic/vector indexing and TTL (0/2, weight 1); card `parity-gap-lg28-store-vector`.
- `LG29` — Node/task result caching and TTL/backend protocol (0/2, weight 1); card `parity-gap-lg29-cache`.
- `LG30` — Config, context, runtime injection, and propagation (0/2, weight 4); card `parity-gap-lg30-config-context`.
- `LG31` — Graph lifecycle callbacks and interrupt/resume events (0/2, weight 1); card `parity-gap-lg31-callbacks`.
- `LG32` — Functional task/entrypoint API (0/2, weight 1); card `parity-gap-lg32-functional-api`.
- `LG33` — Low-level Pregel and channel composition API (0/2, weight 1); card `parity-gap-lg33-pregel`.
- `LG34` — Topology introspection and schema export (0/2, weight 1); card `parity-gap-lg34-introspection`.
- `LG35` — Cooperative drain with checkpointed continuation (0/2, weight 1); card `parity-gap-lg35-drain`.
- `APP01` — Active-agent state and handoff ownership through DharmaGraph integration (1/2, weight 4); card `parity-gap-app01-handoff`.
- `APP02` — Supervisor final authority through DharmaGraph integration (1/2, weight 1); card `parity-gap-app02-supervisor`.
- `APP03` — Message history filtering and output modes through DharmaGraph integration (1/2, weight 2); card `parity-gap-app03-history`.
- `APP04` — Tool/domain/memory isolation and subagents-as-tools through DharmaGraph integration (1/2, weight 3); card `parity-gap-app04-isolation`.
- `PB01` — Prebuilt agent and tool execution, validation, injection, parallel calls, errors, and Command updates (0/2, weight 1); card `parity-gap-pb01-prebuilt-tools`.

## Capability matrix

| ID | Capability | Weight | Points | Contribution | Evidence | Caveats |
|---|---|---:|---:|---:|---|---|
| `LG01` | State, input, output, and context schemas with partial updates | 4 | 1 | 2.00 | context_schema:surface-lg01-context_schema, input_schema:surface-lg01-input_schema, output_schema:surface-lg01-output_schema | unproven facets: typed_state_schema, input_schema, output_schema, context_schema |
| `LG02` | Node registration metadata, schemas, destinations, and default policies | 2 | 0 | 0.00 | destinations:surface-lg02-destinations, node_cache:surface-lg02-node_cache, node_defaults:surface-lg02-node_defaults | unproven facets: node_metadata, node_input_schema, destinations, node_defaults, node_retry, node_cache, node_error_handler, node_timeout |
| `LG03` | Deferred and finalization nodes | 1 | 0 | 0.00 | after_finish_trigger:surface-lg03-after_finish_trigger, deferred_node:surface-lg03-deferred_node | unproven facets: deferred_node, after_finish_trigger |
| `LG04` | Static topology, sequence, entry/finish, and ALL barrier edges | 2 | 1 | 1.00 | barrier_edges:surface-lg04-barrier_edges, compile_validation:surface-lg04-compile_validation, entry_finish:surface-lg04-entry_finish | unproven facets: sequence |
| `LG05` | Conditional routing and conditional entry | 1 | 2 | 1.00 | conditional_edges:surface-lg05-conditional_edges, conditional_entry:surface-lg05-conditional_entry, multi_target_branch:surface-lg05-multi_target_branch | — |
| `LG06` | Bulk-synchronous parallel supersteps and step atomicity | 2 | 1 | 1.00 | barrier_visibility:surface-lg06-barrier_visibility, parallel_actor_overlap:surface-lg06-parallel_actor_overlap, sibling_failure_stops_step:surface-lg06-sibling_failure_stops_step | unproven facets: parallel_actor_overlap, step_atomicity, sibling_failure_stops_step |
| `LG07` | Dynamic Send fan-out and map-reduce | 1 | 1 | 0.50 | custom_branch_state:surface-lg07-custom_branch_state, map_reduce:surface-lg07-map_reduce, send_dynamic_fanout:surface-lg07-send_dynamic_fanout | unproven facets: send_timeout |
| `LG08` | Command update, multi-target goto, parent routing, and resume | 2 | 1 | 1.00 | command_goto:surface-lg08-command_goto, command_multi_target:surface-lg08-command_multi_target, command_parent:surface-lg08-command_parent | unproven facets: command_parent, command_resume |
| `LG09` | Cycles, recursion caps, and managed remaining-step state | 1 | 1 | 0.50 | cycles:surface-lg09-cycles, limit_error:surface-lg09-limit_error, recursion_limit:surface-lg09-recursion_limit | unproven facets: remaining_steps |
| `LG10` | Reducer and channel semantics with concurrent-write conflicts | 4 | 1 | 2.00 | any_value:surface-lg10-any_value, barrier:surface-lg10-barrier, binary_reducer:surface-lg10-binary_reducer | unproven facets: topic, barrier, ephemeral, any_value, untracked_value, delta_channel, last_value_after_finish, named_barrier_after_finish |
| `LG11` | Message accumulation, replacement, removal, and formatting | 2 | 0 | 0.00 | append_message:surface-lg11-append_message, invalid_remove:surface-lg11-invalid_remove, openai_format:surface-lg11-openai_format | unproven facets: append_message, replace_by_id, remove_message, remove_all, invalid_remove, openai_format, ui_message_helpers |
| `LG12` | Compilation and sync/async single-run interfaces | 4 | 1 | 2.00 | async_invoke:surface-lg12-async_invoke, async_stream:surface-lg12-async_stream, compile:surface-lg12-compile | unproven facets: sync_invoke, sync_stream, async_stream, typed_v2_invoke, typed_v2_ainvoke |
| `LG13` | Batch, as-completed, and max-concurrency interfaces | 1 | 0 | 0.00 | abatch:surface-lg13-abatch, abatch_as_completed:surface-lg13-abatch_as_completed, batch:surface-lg13-batch | unproven facets: batch, abatch, batch_as_completed, abatch_as_completed, max_concurrency |
| `LG14` | Checkpoint schema, saver protocol, pending writes, lineage, and serializer | 4 | 1 | 2.00 | async_checkpoint_lifecycle:surface-lg14-async_checkpoint_lifecycle, async_saver:surface-lg14-async_saver, checkpoint_schema:surface-lg14-checkpoint_schema | unproven facets: sync_saver, async_saver, pending_writes, serializer, delete_thread, delete_for_runs, copy_thread, prune, get_delta_channel_history, async_checkpoint_lifecycle |
| `LG15` | Thread-scoped continuity and resume | 9 | 0 | 0.00 | checkpoint_id:surface-lg15-checkpoint_id, checkpoint_parent:surface-lg15-checkpoint_parent, multi_turn_state:surface-lg15-multi_turn_state | unproven facets: thread_id, checkpoint_id, thread_resume, checkpoint_parent, multi_turn_state |
| `LG16` | State inspection, history, and replay | 2 | 1 | 1.00 | async_state_api:surface-lg16-async_state_api, get_state:surface-lg16-get_state, get_state_history:surface-lg16-get_state_history | unproven facets: get_state, get_state_history, async_state_api |
| `LG17` | Manual state update, bulk update, fork, and time travel | 8 | 1 | 4.00 | bulk_update_state:surface-lg17-bulk_update_state, fork:surface-lg17-fork, new_branch:surface-lg17-new_branch | unproven facets: update_state, bulk_update_state |
| `LG18` | Durability ordering and process-restart recovery | 10 | 1 | 5.00 | delta_channel_durable_history:surface-lg18-delta_channel_durable_history, durability_async:surface-lg18-durability_async, durability_exit:surface-lg18-durability_exit | unproven facets: durability_sync, durability_async, durability_exit, persistent_process_restart, pending_write_recovery, delta_channel_durable_history |
| `LG19` | Static interrupt-before and interrupt-after | 1 | 0 | 0.00 | interrupt_after:surface-lg19-interrupt_after, interrupt_before:surface-lg19-interrupt_before | unproven facets: interrupt_before, interrupt_after |
| `LG20` | Dynamic HITL interrupt and resume | 2 | 0 | 0.00 | dynamic_interrupt:surface-lg20-dynamic_interrupt, interrupt_order:surface-lg20-interrupt_order, multiple_interrupts:surface-lg20-multiple_interrupts | unproven facets: dynamic_interrupt, resume_value, multiple_interrupts, interrupt_order, node_reexecution |
| `LG21` | Seven standard stream modes, multi-mode, typed v2, and subgraph namespaces | 1 | 0 | 0.00 | checkpoints_stream:surface-lg21-checkpoints_stream, custom_stream:surface-lg21-custom_stream, debug_stream:surface-lg21-debug_stream | unproven facets: values_stream, updates_stream, messages_stream, custom_stream, checkpoints_stream, tasks_stream, debug_stream, multi_mode, typed_v2, subgraph_namespace |
| `LG22` | Experimental event stream v3 and transformer projections | 1 | 0 | 0.00 | builtin_transformers:surface-lg22-builtin_transformers, stream_events_v3:surface-lg22-stream_events_v3, stream_transformers:surface-lg22-stream_transformers | unproven facets: stream_events_v3, stream_transformers, builtin_transformers |
| `LG23` | Nested graphs, parent commands, inheritance, nested state, and streaming | 1 | 0 | 0.00 | checkpointer_inheritance:surface-lg23-checkpointer_inheritance, compiled_graph_as_node:surface-lg23-compiled_graph_as_node, nested_state_history:surface-lg23-nested_state_history | unproven facets: compiled_graph_as_node, recursive_discovery, parent_command, checkpointer_inheritance, nested_state_history, nested_streaming |
| `LG24` | Retry selection, backoff, jitter, attempts, and write clearing | 4 | 0 | 0.00 | backoff:surface-lg24-backoff, jitter:surface-lg24-jitter, max_attempts:surface-lg24-max_attempts | unproven facets: retry_selection, backoff, jitter, max_attempts, retry_on, writes_cleared |
| `LG25` | Hard/idle timeout, heartbeat, and retry interaction | 2 | 0 | 0.00 | hard_timeout:surface-lg25-hard_timeout, heartbeat_refresh:surface-lg25-heartbeat_refresh, idle_timeout:surface-lg25-idle_timeout | unproven facets: hard_timeout, idle_timeout, heartbeat_refresh, timeout_retry |
| `LG26` | Error propagation, sibling cancellation, handlers, and atomic writes | 4 | 1 | 2.00 | atomic_writes:surface-lg26-atomic_writes, error_handler:surface-lg26-error_handler, invalid_update:surface-lg26-invalid_update | unproven facets: sibling_cancellation, user_cancellation, error_handler, atomic_writes |
| `LG27` | Long-term Store CRUD, namespaces, filters, paging, async, and batch | 1 | 0 | 0.00 | async_store:surface-lg27-async_store, batch_store:surface-lg27-batch_store, filters:surface-lg27-filters | unproven facets: store_get, store_put, store_delete, store_search, namespaces, filters, paging, async_store, batch_store |
| `LG28` | Store semantic/vector indexing and TTL | 1 | 0 | 0.00 | semantic_query:surface-lg28-semantic_query, store_filter:surface-lg28-store_filter, store_ttl:surface-lg28-store_ttl | unproven facets: vector_index, semantic_query, store_filter, store_ttl, supports_ttl |
| `LG29` | Node/task result caching and TTL/backend protocol | 1 | 0 | 0.00 | cache_backend:surface-lg29-cache_backend, cache_clear:surface-lg29-cache_clear, cache_key_func:surface-lg29-cache_key_func | unproven facets: cache_policy, cache_backend, cache_ttl, cache_clear, cache_key_func |
| `LG30` | Config, context, runtime injection, and propagation | 4 | 0 | 0.00 | context_schema:surface-lg30-context_schema, execution_info:surface-lg30-execution_info, get_config:surface-lg30-get_config | unproven facets: runnable_config, context_schema, runtime_injection, execution_info, get_runtime, get_config, get_store, stream_writer, propagation |
| `LG31` | Graph lifecycle callbacks and interrupt/resume events | 1 | 0 | 0.00 | graph_callback_handler:surface-lg31-graph_callback_handler, interrupt_event:surface-lg31-interrupt_event, lifecycle_observability:surface-lg31-lifecycle_observability | unproven facets: graph_callback_handler, interrupt_event, resume_event, lifecycle_observability |
| `LG32` | Functional task/entrypoint API | 1 | 0 | 0.00 | entrypoint:surface-lg32-entrypoint, entrypoint_final:surface-lg32-entrypoint_final, functional_checkpoint:surface-lg32-functional_checkpoint | unproven facets: task_decorator, task_futures, parallel_tasks, entrypoint, previous, entrypoint_final, functional_checkpoint, functional_store, functional_retry_timeout_context |
| `LG33` | Low-level Pregel and channel composition API | 1 | 0 | 0.00 | do:surface-lg33-do, low_level_retry_cache_timeout:surface-lg33-low_level_retry_cache_timeout, managed_values:surface-lg33-managed_values | unproven facets: pregel, node_builder, subscribe, read, do, write, meta, low_level_retry_cache_timeout, managed_values |
| `LG34` | Topology introspection and schema export | 1 | 0 | 0.00 | config_json_schema:surface-lg34-config_json_schema, context_json_schema:surface-lg34-context_json_schema, get_graph:surface-lg34-get_graph | unproven facets: get_graph, xray_graph, get_subgraphs, input_json_schema, output_json_schema, context_json_schema, with_config, config_json_schema |
| `LG35` | Cooperative drain with checkpointed continuation | 1 | 0 | 0.00 | checkpointed_drain:surface-lg35-checkpointed_drain, continuation:surface-lg35-continuation, graph_drained:surface-lg35-graph_drained | unproven facets: run_control, graph_drained, checkpointed_drain, continuation |
| `APP01` | Active-agent state and handoff ownership through DharmaGraph integration | 4 | 1 | 2.00 | accepted_handoff:surface-app01-accepted_handoff, checkpoint_restart:surface-app01-checkpoint_restart, default_active_agent:surface-app01-default_active_agent | unproven facets: neutral_engine_integration; Existing application oracle exercises the clone lineage, not the neutral DharmaGraph engine; row is capped below 2. |
| `APP02` | Supervisor final authority through DharmaGraph integration | 1 | 1 | 0.50 | delegate:surface-app02-delegate, evidence_synthesis:surface-app02-evidence_synthesis, forward_exact:surface-app02-forward_exact | unproven facets: neutral_engine_integration; Existing application oracle exercises the clone lineage, not the neutral DharmaGraph engine; row is capped below 2. |
| `APP03` | Message history filtering and output modes through DharmaGraph integration | 2 | 1 | 1.00 | distractor_isolation:surface-app03-distractor_isolation, full_history:surface-app03-full_history, last_message:surface-app03-last_message | unproven facets: neutral_engine_integration; Existing application oracle exercises the clone lineage, not the neutral DharmaGraph engine; row is capped below 2. |
| `APP04` | Tool/domain/memory isolation and subagents-as-tools through DharmaGraph integration | 3 | 1 | 1.50 | domain_isolation:surface-app04-domain_isolation, memory_isolation:surface-app04-memory_isolation, neutral_engine_integration:surface-app04-neutral_engine_integration | unproven facets: domain_isolation, memory_isolation, neutral_engine_integration; Existing application oracle exercises the clone lineage, not the neutral DharmaGraph engine; row is capped below 2. |
| `PERF01` | Equivalent-workload wall-clock and overhead ratios | 1 | 2 | 1.00 | checkpoint_timing:surface-perf01-checkpoint_timing, environment_metadata:surface-perf01-environment_metadata, linear_timing:surface-perf01-linear_timing | — |
| `PB01` | Prebuilt agent and tool execution, validation, injection, parallel calls, errors, and Command updates | 1 | 0 | 0.00 | command_state_updates:surface-pb01-command_state_updates, create_react_agent:surface-pb01-create_react_agent, injected_state:surface-pb01-injected_state | unproven facets: create_react_agent, tool_node, parallel_tool_calls, tool_error_handling, tool_call_transformer, validation_node, tools_condition, injected_state, injected_store, tool_runtime, command_state_updates |

## Harness integrity

- Broken control `CTRL01` verdict: `mismatch`.
- Required failure observed: `true`.
- Completeness control `COMPLETE01` recorded: `true`.

## Latest-stable drift (reported, non-gating)

- Status: `DRIFT_OBSERVED`.
- Behavioral execution: `true`.
- Target: `1.2.8`; frozen grade remains `1.2.4`.

## Performance (reported, not a win requirement)

```json
{
  "clock": "time.perf_counter",
  "environment_metadata": {
    "langgraph_version": "1.2.4",
    "platform": "macOS-26.5.1-arm64-arm-64bit-Mach-O",
    "python_executable": "/Users/dhyana/dharma_swarm/.venv/bin/python",
    "python_version": "3.13.12"
  },
  "iterations": 5,
  "timing_decides_semantic_parity": false,
  "unit": "seconds",
  "workloads": {
    "seeded_checkpoint_resume_fork": {
      "dharma": {
        "median_seconds": 0.0006890829972689971,
        "samples_seconds": [
          0.0006890829972689971,
          0.0007074159948388115,
          0.0006065420020604506,
          0.0006831249920651317,
          0.000818375003291294
        ]
      },
      "dharma_median_seconds": 0.0006890829972689971,
      "iterations": 5,
      "langgraph": {
        "median_seconds": 0.0025457919982727617,
        "samples_seconds": [
          0.0026645410107448697,
          0.0023750830005155876,
          0.0025457919982727617,
          0.0024143329937942326,
          0.0026047499995911494
        ]
      },
      "langgraph_median_seconds": 0.0025457919982727617,
      "overhead_ratio_dharma_to_langgraph": 0.2706752938718159,
      "semantic_parity_all_iterations": true
    },
    "seeded_linear_reducer_chain": {
      "dharma": {
        "median_seconds": 0.0003295420028734952,
        "samples_seconds": [
          0.000763167001423426,
          0.0003757909871637821,
          0.0003020000003743917,
          0.0003295420028734952,
          0.0002917499950854108
        ]
      },
      "dharma_median_seconds": 0.0003295420028734952,
      "iterations": 5,
      "langgraph": {
        "median_seconds": 0.00160995899932459,
        "samples_seconds": [
          0.00193237500207033,
          0.00160995899932459,
          0.0017193329986184835,
          0.0015095830021891743,
          0.001549708002130501
        ]
      },
      "langgraph_median_seconds": 0.00160995899932459,
      "overhead_ratio_dharma_to_langgraph": 0.20468968651483962,
      "semantic_parity_all_iterations": true
    },
    "seeded_send_map_reduce": {
      "dharma": {
        "median_seconds": 0.00030179200985003263,
        "samples_seconds": [
          0.00030179200985003263,
          0.00032574999204371125,
          0.0002765829995041713,
          0.0003226670087315142,
          0.0002869580057449639
        ]
      },
      "dharma_median_seconds": 0.00030179200985003263,
      "iterations": 5,
      "langgraph": {
        "median_seconds": 0.0012445419997675344,
        "samples_seconds": [
          0.001356207998469472,
          0.0011385410034563392,
          0.0011409999860916287,
          0.0013282079889904708,
          0.0012445419997675344
        ]
      },
      "langgraph_median_seconds": 0.0012445419997675344,
      "overhead_ratio_dharma_to_langgraph": 0.2424924268577547,
      "semantic_parity_all_iterations": true
    }
  }
}
```

Receipt stable digest: `40d0c923118caa9041c73dc76fd873396f72e78b7d6da30b72a977f26b84b3d6`.
