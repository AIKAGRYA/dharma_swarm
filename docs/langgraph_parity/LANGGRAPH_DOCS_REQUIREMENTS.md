# LangGraph Swarm/Supervisor Docs Requirements

Date: 2026-06-29
Role: Agent 2 - Researcher/Mapper
Scope: turn current upstream LangGraph swarm/supervisor APIs into local test acceptance criteria only.

## Sources Verified

- Context7 library docs: `/langchain-ai/langgraph-swarm-py`
- Context7 library docs: `/langchain-ai/langgraph-supervisor-py`
- `langgraph-swarm-py` upstream source:
  - https://github.com/langchain-ai/langgraph-swarm-py/blob/main/langgraph_swarm/swarm.py
  - https://github.com/langchain-ai/langgraph-swarm-py/blob/main/langgraph_swarm/handoff.py
  - https://github.com/langchain-ai/langgraph-swarm-py/blob/main/README.md
- `langgraph-supervisor-py` upstream source:
  - https://github.com/langchain-ai/langgraph-supervisor-py/blob/main/langgraph_supervisor/supervisor.py
  - https://github.com/langchain-ai/langgraph-supervisor-py/blob/main/langgraph_supervisor/handoff.py
  - https://github.com/langchain-ai/langgraph-supervisor-py/blob/main/README.md

## Local Repo Observation

- `pyproject.toml` currently exposes `langgraph>=0.2.0` only under the `infra` extra. It does not declare `langgraph-swarm` or `langgraph-supervisor`.
- The local `dharma_swarm.models.SwarmState` is a Pydantic status snapshot with `agents`, task counts, uptime, timestamp, and optional organism status. It is not equivalent to upstream `langgraph_swarm.SwarmState`, which extends LangGraph `MessagesState` and requires `active_agent: str | None`.
- No current local imports of `langgraph_swarm`, `langgraph_supervisor`, `create_swarm`, or `create_supervisor` were found in `dharma_swarm/`, `tests/`, or this parity docs directory.

Acceptance tests should therefore be added as parity/adapter tests before any runtime integration claims support for the upstream packages. They should also preserve the local `dharma_swarm.models.SwarmState` status-model contract and avoid silently reusing it as a LangGraph swarm state.

## Swarm API Contract

Upstream package: `langgraph-swarm-py`.

### `SwarmState`

Source: `langgraph_swarm/swarm.py`.

Contract:

- `SwarmState` extends LangGraph `MessagesState`.
- It has an optional `active_agent: str | None`.
- `active_agent` is not expected from the user by default. If present, it selects the starting agent.
- If `active_agent` is typed as `str` or optional `str`, `create_swarm` rewrites the state schema annotation to a `Literal` over the actual agent names.

Acceptance criteria:

- `test_langgraph_swarm_state_is_not_local_status_swarm_state`: import upstream `langgraph_swarm.SwarmState` and local `dharma_swarm.models.SwarmState` under aliases. Assert the upstream contract has `messages`/`active_agent` semantics and the local model still has status fields. Any adapter must use the correct state class explicitly.
- `test_create_swarm_rejects_state_schema_without_active_agent`: a custom state schema without `active_agent` must raise `ValueError`.
- `test_create_swarm_narrows_active_agent_annotation_for_str_schemas`: a custom schema with `active_agent: str | None` should produce a builder whose state schema constrains `active_agent` to the provided agent names.

### `create_swarm`

Source: `langgraph_swarm/swarm.py`; README quickstart.

Signature:

```python
create_swarm(
    agents: list[Pregel],
    *,
    default_active_agent: str,
    state_schema: StateSchemaType = SwarmState,
    context_schema: type[Any] | None = None,
    **deprecated_kwargs,
) -> StateGraph
```

Contract:

- Returns an uncompiled `StateGraph`; callers compile it with `.compile(...)`.
- Requires a non-empty `agents` list.
- Every agent must have a `.name`.
- `default_active_agent` must match one of the agent names.
- Adds the active-agent router from `START`.
- Adds each agent node with destinations discovered from handoff tool metadata.
- Multi-turn resume depends on a checkpointer supplied to `.compile(checkpointer=...)`.
- `config_schema` is deprecated in favor of `context_schema`.
- There is no `output_mode` parameter on swarm.

Acceptance criteria:

- `test_create_swarm_rejects_empty_agents`: empty `agents` raises `ValueError`.
- `test_create_swarm_rejects_unknown_default_active_agent`: `default_active_agent` not in agent names raises `ValueError`.
- `test_create_swarm_returns_uncompiled_state_graph`: the wrapper/adapter exposes a `StateGraph` until explicitly compiled.
- `test_create_swarm_adds_agent_nodes_and_handoff_destinations`: agents with upstream handoff tools must be added with destinations from `__handoff_destination` metadata.
- `test_swarm_multiturn_resume_requires_checkpointer`: with `InMemorySaver` and a stable `thread_id`, a handoff that sets `active_agent` to `Bob` makes the next turn start at `Bob`; without a checkpointer, code must not claim persistence across turns.
- `test_swarm_contract_has_no_output_mode`: `inspect.signature(create_swarm)` or any local parity adapter must not expose or silently accept `output_mode`.

### `add_active_agent_router`

Source: `langgraph_swarm/swarm.py`; README manual customization example.

Signature:

```python
add_active_agent_router(
    builder: StateGraph,
    *,
    route_to: list[str],
    default_active_agent: str,
) -> StateGraph
```

Contract:

- Adds conditional edges from `START`.
- Routes to `state["active_agent"]` when present.
- Routes to `default_active_agent` when state has no active agent.
- Requires the builder state schema to include `active_agent`.
- Requires `default_active_agent` to exist in `route_to`.

Acceptance criteria:

- `test_add_active_agent_router_requires_active_agent_key`: a builder whose state schema lacks `active_agent` raises `ValueError`.
- `test_add_active_agent_router_rejects_default_not_in_routes`: `default_active_agent` outside `route_to` raises `ValueError`.
- `test_add_active_agent_router_routes_default_when_state_empty`: an invoke with no `active_agent` starts at the default node.
- `test_add_active_agent_router_routes_to_prior_active_agent`: an invoke with `active_agent="Bob"` starts at `Bob`, not the default.

### Swarm `create_handoff_tool`

Source: `langgraph_swarm/handoff.py`; README customization section.

Signature:

```python
create_handoff_tool(
    *,
    agent_name: str,
    name: str | None = None,
    description: str | None = None,
) -> BaseTool
```

Contract:

- Default tool name is `transfer_to_<normalized_agent_name>`, where whitespace is collapsed to underscores and the result is lowercase.
- Default description is `Ask agent '<agent_name>' for help`.
- Tool metadata contains `{"__handoff_destination": agent_name}`.
- The generated tool accepts injected state and tool call id, not ordinary LLM-supplied arguments.
- On execution, returns `Command(goto=agent_name, graph=Command.PARENT, update={...})`.
- The update appends a `ToolMessage` named after the handoff tool with content `Successfully transferred to <agent_name>`.
- The update sets `active_agent` to the target agent.
- The update preserves full prior `messages`.
- The implementation can read state from dict, dataclass, or Pydantic model objects.
- There are no `add_handoff_messages` or `add_handoff_back_messages` knobs in the swarm handoff tool.

Acceptance criteria:

- `test_swarm_handoff_tool_default_name_description_and_metadata`: default name, description, and `__handoff_destination` metadata match upstream.
- `test_swarm_handoff_tool_custom_name_description`: custom `name` and `description` are preserved.
- `test_swarm_handoff_tool_command_shape`: executing the tool returns a parent `Command` that goes to the target agent, appends the `ToolMessage`, preserves previous messages, and sets `active_agent`.
- `test_swarm_handoff_tool_accepts_supported_state_shapes`: dict plus any local wrapper-supported dataclass/Pydantic state shapes return the same update.
- `test_swarm_handoff_tool_does_not_support_supervisor_history_flags`: no local swarm wrapper should accept `add_handoff_messages` or `add_handoff_back_messages` unless it is explicitly a custom tool outside upstream parity.

## Supervisor API Contract

Upstream package: `langgraph-supervisor-py`.

### `create_supervisor`

Source: `langgraph_supervisor/supervisor.py`; README quickstart and history-management sections.

Signature excerpt:

```python
create_supervisor(
    agents: list[Pregel],
    *,
    model: LanguageModelLike,
    tools: list[BaseTool | Callable] | ToolNode | None = None,
    prompt: Prompt | None = None,
    response_format: StructuredResponseSchema | tuple[str, StructuredResponseSchema] | None = None,
    pre_model_hook: RunnableLike | None = None,
    post_model_hook: RunnableLike | None = None,
    parallel_tool_calls: bool = False,
    state_schema: StateSchemaType | None = None,
    context_schema: type[Any] | None = None,
    output_mode: Literal["full_history", "last_message"] = "last_message",
    add_handoff_messages: bool = True,
    handoff_tool_prefix: str | None = None,
    add_handoff_back_messages: bool | None = None,
    supervisor_name: str = "supervisor",
    include_agent_name: AgentNameMode | None = None,
    **deprecated_kwargs,
) -> StateGraph
```

Contract:

- Returns an uncompiled `StateGraph`.
- Every managed agent must have a non-null name that is not the default `"LangGraph"`.
- Agent names must be unique.
- If custom handoff tools are provided, they must cover all managed agents.
- If no handoff tools are provided, supervisor creates one per agent.
- `handoff_tool_prefix` changes generated names to `<prefix><normalized_agent_name>`.
- The supervisor model is bound to all tools when the model supports tool binding. `parallel_tool_calls` defaults to `False`.
- `START` routes to the supervisor node. The supervisor has destinations to all agents and `END`. Each agent routes back to the supervisor.
- `add_handoff_back_messages is None` means it follows the value of `add_handoff_messages`.
- `config_schema` is deprecated in favor of `context_schema`.

Acceptance criteria:

- `test_create_supervisor_rejects_unnamed_or_default_named_agents`: unnamed agents and agents named `"LangGraph"` raise `ValueError`.
- `test_create_supervisor_rejects_duplicate_agent_names`: duplicate managed agent names raise `ValueError`.
- `test_create_supervisor_autogenerates_handoff_tools_for_all_agents`: when no handoff tools are supplied, generated tools cover every agent.
- `test_create_supervisor_rejects_partial_custom_handoff_tools`: custom handoff tools with missing destinations raise `ValueError`.
- `test_create_supervisor_handoff_tool_prefix`: `handoff_tool_prefix="delegate_to_"` generates names like `delegate_to_research_expert`.
- `test_create_supervisor_graph_topology`: compiled or introspected graph starts at supervisor, supervisor can route to each agent and end, and each agent returns to supervisor.
- `test_create_supervisor_add_handoff_back_default_tracks_add_handoff_messages`: when `add_handoff_back_messages` is omitted, it is true when `add_handoff_messages=True` and false when `add_handoff_messages=False`.

### Supervisor `output_mode`

Source: `langgraph_supervisor/supervisor.py`; README message-history section.

Contract:

- Valid values are `"full_history"` and `"last_message"`.
- Default is `"last_message"`.
- `"full_history"` adds the entire agent message history to the multi-agent workflow history.
- `"last_message"` adds only the last agent message.
- If the last message is a `ToolMessage`, `"last_message"` keeps the last two messages so the tool result remains paired with its AI tool call context.
- Invalid values raise `ValueError`.

Acceptance criteria:

- `test_supervisor_output_mode_default_is_last_message`: default supervisor construction uses `"last_message"` behavior.
- `test_supervisor_output_mode_full_history_preserves_all_agent_messages`: fake agent output with multiple messages is fully retained.
- `test_supervisor_output_mode_last_message_trims_to_final_ai_message`: fake agent output with normal final AI message is trimmed to one message.
- `test_supervisor_output_mode_last_message_keeps_tool_pair`: fake agent output ending in a `ToolMessage` is trimmed to the final two messages.
- `test_supervisor_output_mode_rejects_invalid_value`: invalid output mode raises `ValueError`.

### Supervisor `create_handoff_tool` and `add_handoff_messages`

Source: `langgraph_supervisor/handoff.py`; README customization section.

Signature:

```python
create_handoff_tool(
    *,
    agent_name: str,
    name: str | None = None,
    description: str | None = None,
    add_handoff_messages: bool = True,
) -> BaseTool
```

Contract:

- Default tool name and description match the swarm naming convention.
- Metadata contains `{"__handoff_destination": agent_name}`.
- The generated `ToolMessage` carries `response_metadata={"__handoff_destination": agent_name}`.
- For a single tool call and `add_handoff_messages=True`, the returned parent `Command` goes to the target agent and updates state with existing messages plus the tool message.
- For a single tool call and `add_handoff_messages=False`, the returned parent `Command` goes to the target agent and updates state with `state["messages"][:-1]`, omitting the supervisor tool-call message and the handoff tool message.
- For parallel tool calls, the returned parent `Command` uses `Send(agent_name, state)` in `goto` so LangGraph can merge parallel sends.
- For parallel tool calls and `add_handoff_messages=True`, message history is filtered to retain only the AI tool call meant for that destination plus its matching tool message.
- For parallel tool calls and `add_handoff_messages=False`, the last supervisor AI tool-call message is omitted.
- Supervisor handoff does not set `active_agent`; that is swarm-specific.

Acceptance criteria:

- `test_supervisor_handoff_tool_default_name_description_and_metadata`: default tool shape matches upstream.
- `test_supervisor_handoff_tool_single_call_adds_handoff_messages`: single handoff with `add_handoff_messages=True` appends a destination-tagged tool message and routes to the target.
- `test_supervisor_handoff_tool_single_call_omits_handoff_messages`: single handoff with `add_handoff_messages=False` drops the supervisor tool-call message from the child-agent input.
- `test_supervisor_handoff_tool_parallel_uses_send`: parallel handoff returns `Command.goto` containing `Send` to the target.
- `test_supervisor_handoff_tool_parallel_filters_non_target_tool_calls`: child-agent state contains only the target tool call and matching tool message when handoff messages are enabled.
- `test_supervisor_handoff_does_not_write_active_agent`: no supervisor handoff acceptance test should expect `active_agent` updates.

### `create_handoff_back_messages` and `add_handoff_back_messages`

Source: `langgraph_supervisor/handoff.py`; `langgraph_supervisor/supervisor.py`.

Contract:

- `create_handoff_back_messages(agent_name, supervisor_name)` returns `(AIMessage, ToolMessage)`.
- Tool name is `transfer_back_to_<normalized_supervisor_name>`.
- The AI message has `name=agent_name`, content `Transferring back to <supervisor_name>`, a matching tool call, and `response_metadata={"__is_handoff_back": True}`.
- The tool message has content `Successfully transferred back to <supervisor_name>`, matching `tool_call_id`, name equal to the transfer-back tool, and `response_metadata={"__is_handoff_back": True}`.
- In `create_supervisor`, agent outputs append this pair only when `add_handoff_back_messages` is true. If omitted, the flag mirrors `add_handoff_messages`.

Acceptance criteria:

- `test_create_handoff_back_messages_shape_and_metadata`: message pair content, names, matching tool call id, and `__is_handoff_back` metadata match upstream.
- `test_supervisor_add_handoff_back_messages_appends_pair`: agent output processing appends the pair when enabled.
- `test_supervisor_add_handoff_back_messages_can_be_disabled`: agent output processing does not append the pair when disabled.
- `test_forward_message_ignores_handoff_back_messages`: forward-message lookup must skip AI messages marked `__is_handoff_back`.

### `create_forward_message_tool`

Source: `langgraph_supervisor/handoff.py`; README message forwarding section.

Signature:

```python
create_forward_message_tool(supervisor_name: str = "supervisor") -> BaseTool
```

Contract:

- Creates a tool named `forward_message`.
- The tool takes `from_agent: str` plus injected state.
- It finds the latest `AIMessage` whose `name` matches `from_agent` case-insensitively.
- It ignores messages marked as handoff-back messages via `__is_handoff_back`.
- If a source message is found, it returns a parent `Command` with `goto="__end__"`.
- The update writes one new `AIMessage` with identical content and `name=supervisor_name`.
- If no source message is found, it returns a string describing the missing source and found names.

Acceptance criteria:

- `test_forward_message_tool_name_and_schema`: tool name is `forward_message` and requires `from_agent`.
- `test_forward_message_tool_forwards_latest_matching_agent_message_exactly`: content is copied exactly, not summarized or rewritten.
- `test_forward_message_tool_uses_supervisor_name_for_forwarded_message`: forwarded message name equals the configured supervisor name.
- `test_forward_message_tool_ends_graph`: successful forward returns parent `Command` with `goto="__end__"`.
- `test_forward_message_tool_case_insensitive_agent_lookup`: `from_agent` matching ignores case.
- `test_forward_message_tool_missing_agent_returns_diagnostic`: missing source returns a string with available names.

## Cross-Package Parity Rules

- Swarm and supervisor both use default handoff tool names of the form `transfer_to_<normalized_agent_name>`.
- Swarm handoff updates `active_agent`; supervisor handoff does not.
- Swarm remembers the last active agent through `active_agent` and checkpointer-backed graph state; supervisor returns control to a central supervisor node after each agent call.
- Supervisor owns `output_mode`, `add_handoff_messages`, `add_handoff_back_messages`, and `create_forward_message_tool`.
- `add_handoff_messages` and `add_handoff_back_messages` are parameters/behaviors, not standalone public functions in the verified upstream source.
- Local tests should make these distinctions explicit so future adapters do not merge the swarm and supervisor semantics into one ambiguous "handoff" behavior.

## Suggested Test Placement

- `tests/langgraph_parity/test_swarm_contract.py`
- `tests/langgraph_parity/test_supervisor_contract.py`
- `tests/langgraph_parity/test_local_state_boundary.py`

If the repo does not add `langgraph-swarm` and `langgraph-supervisor` as dependencies, these tests should either be adapter-only tests using local shims or use `pytest.importorskip` with an explicit skip reason. Silent absence of these packages should not count as parity.
