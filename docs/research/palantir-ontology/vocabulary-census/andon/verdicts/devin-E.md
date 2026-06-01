# Slice E — A2A External/Internal Collision

**Agent:** devin-roaming-2987d222 (serial AGT-DEVIN_ROAMING_2987D222)
**Verdict date:** 2026-06-01T07:25Z
**Codex claim:** `A2ATask` is used both for external (cross-org) protocol AND internal (intra-swarm) work queue — "dangerous conflation."

---

## Method

Traced every instantiation and import of `A2ATask` across the codebase. Categorized each call site as external-facing (network boundary, remote agents) or internal (intra-process dispatch). Checked for state leak, auth confusion, or replay risk at each boundary.

---

## Findings

### 1. All `A2ATask` instantiation sites

| # | File | Line | Direction | Context |
|---|------|------|-----------|---------|
| 1 | `a2a/a2a_server.py:257` | `server.submit(A2ATask(...))` | Internal | Docstring example — orchestrator→reviewer delegation |
| 2 | `a2a/a2a_client.py:348` | `A2ATask(from_agent=..., to_agent=..., capability=...)` | Internal | `A2AClient.delegate()` — intra-swarm task delegation via discovery+dispatch |
| 3 | `a2a/a2a_bridge.py:120` | `A2ATask(from_agent=..., to_agent=..., history=[...])` | **Bridge** | `trishula_message_to_a2a_task()` — converts TRISHULA inbound messages to A2ATask |
| 4 | `a2a/node_gateway.py:210` | `A2ATask(from_agent="remote", ...)` | **External** | `_parse_task_from_body()` — HTTP endpoint accepting tasks from remote A2A nodes |

### 2. Architecture analysis

The A2A subsystem has a **three-layer** design:

1. **`A2AServer`** (`a2a_server.py`) — Local-first task store. "Tasks are dispatched via direct function calls" (docstring line 248). Maintains its own task store "separate from (but linked to) the dharma_swarm task board" (line 250). This is the **internal** layer.

2. **`A2AClient`** (`a2a_client.py`) — Discovery + delegation client. Uses `CardRegistry` to find agents, submits to `A2AServer`. Includes cycle detection (`_MAX_DELEGATION_DEPTH = 10`) and chain tracking. This is the **internal routing** layer.

3. **`NodeGateway`** (`node_gateway.py`) — FastAPI router exposing HTTP endpoints for remote agents. API key auth via `X-A2A-Key` header. Localhost bypass only with explicit env var. This is the **external boundary** layer.

4. **`A2ABridge`** (`a2a_bridge.py`) — Bidirectional bridge between TRISHULA (legacy message format) and A2A. Converts inbound TRISHULA messages → `A2ATask` and outbound `A2ATask` results → TRISHULA messages. This is the **protocol translation** layer.

### 3. Does `A2ATask` serve both external and internal?

**Yes.** The same `A2ATask` dataclass is used:
- **Internally:** `A2AClient.delegate()` creates an `A2ATask` for intra-swarm delegation (agent-to-agent within the same process).
- **Externally:** `NodeGateway._parse_task_from_body()` creates an `A2ATask` from an HTTP request body originating from a remote node.
- **Bridge:** `A2ABridge.trishula_message_to_a2a_task()` converts filesystem-based TRISHULA messages into `A2ATask`.

### 4. Is the conflation harmful?

**No — it is intentional and well-bounded.** The evidence:

**Auth isolation exists.** The `NodeGateway` enforces `X-A2A-Key` auth on all external requests (`node_gateway.py:161-163`). Internal `A2AClient` calls bypass the gateway entirely — they call `A2AServer.submit()` directly. There is no path where an external request reaches the server without auth.

**Source tagging exists.** The `A2ABridge` stamps `metadata["source"] = "trishula"` on all bridge-ingested tasks (`a2a_bridge.py:127`). The `NodeGateway` stamps `from_agent = "remote"` on external tasks (`node_gateway.py:211`). Internal tasks carry the actual agent name. So the origin is always distinguishable.

**Task store is separate.** The `A2AServer` docstring explicitly states it maintains "its own task store for A2A lifecycle tracking, separate from (but linked to) the dharma_swarm task board" (`a2a_server.py:249-250`). The `dharma_task_id` field bridges the two stores when needed.

**Cycle detection prevents replay.** `A2AClient._check_cycle()` tracks active delegation chains per `context_id` and enforces a depth limit of 10. This prevents re-entrancy regardless of source.

**No state leak path found.** Internal tasks don't expose internal state to external consumers. External tasks enter through the gateway, get processed by the server, and results are returned through the gateway. The `_strip_internal_fields()` function (`node_gateway.py:181`) removes internal fields before serialization.

### 5. What Codex missed

The dual use is not an accident — it follows the **A2A 1.0 spec** design, where the same task model represents work regardless of transport. The `A2ATask` is a **protocol-level unit of work**, not a transport-specific one. The three-layer architecture (server/client/gateway) provides the necessary boundary enforcement.

The one genuine gap: `A2ATask.from_agent` is a plain string with no typed distinction between "local agent name" and "remote node identity." A future `executionIdentity` type could strengthen this. But today, the `metadata["source"]` tag and gateway auth provide functional separation.

---

## Headline Verdict: **overstated**

`A2ATask` IS used for both external and internal work — that part is factually correct. But the framing as "dangerous conflation" is **wrong**. The architecture deliberately separates the auth boundary (gateway), the routing layer (client), and the execution layer (server). Source tagging, auth enforcement, cycle detection, and separate task stores prevent the state-leak / auth-confusion / replay risks Codex flagged. The dual use is a design choice conforming to A2A 1.0 spec, not an oversight. The only real improvement opportunity is stronger typing on agent identity (string → typed identity), which is cosmetic, not dangerous.
