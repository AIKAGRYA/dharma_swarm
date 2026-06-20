# High-ROI Branch Closeout — 2026-06-20

**Branch:** `gpt55/high-roi-spine-mcp-orchestrator-20260620`  
**Base:** `main`  
**Mode:** GitHub connector only / mobile-safe edits  
**Status:** draft PR candidate

## What changed

1. Seeded an external-outcome packet for Darshan:
   - `reports/external_outcomes/DARSHAN_FIRST_READER_REPLY_LOOP_20260620.md`
   - Does not claim a shipped outcome.
   - Defines the smallest reader/reply loop needed before opening a real active track.

2. Wired MCP tool access toward the Runtime Truth Spine:
   - `dharma_swarm/mcp_server.py`
   - Each MCP `call_tool` now creates an `ExecutionIdentity`.
   - Tool calls are wrapped with best-effort `RuntimeStateStore` side-effect intent/completion receipts.
   - Receipt payloads record the tool name and argument keys, not full user/tool payload bodies.
   - Receipt writes fail open with warnings so MCP functionality is not broken by local runtime DB issues.

3. Made the control-surface rows hook consume the existing SSE stream:
   - `dashboard/src/hooks/useControlSurface.ts`
   - Uses `/api/control-surface/stream` to update the React Query cache when row projections change.
   - Keeps existing polling as fallback.

## What was intentionally not changed

- Did not mutate `ACTIVE_TRACK.yaml`; the Darshan loop needs an operator-selected artifact and channel before it becomes active state.
- Did not hand-edit generated `spine_adoption_metric.json`; regenerate it through the existing metric tool.
- Did not attempt the `orchestrator.py` extraction in this branch. The GitHub connector requires whole-file replacement for edits, and a 2.9k-line hot-path rewrite was too risky without local checkout/tests.
- Did not attempt DGC live-apply. That requires local runtime state and explicit operator execution.

## Recommended verification

```bash
python3 tools/spine_adoption_metric.py --print
python3 -m pytest tests/test_mcp_server.py -q
npm --prefix dashboard run lint
make agent-build-closeout
```

## Expected ROI

- `mcp_tool_access` should move closer to joined when the adoption metric is regenerated because the surface now contains `ExecutionIdentity`, `RuntimeStateStore`, and side-effect receipt calls.
- The cockpit should feel more live because it now subscribes to the backend's existing stream instead of relying only on polling.
- The Darshan packet creates a non-phantom path toward the missing `revenue-external-humans-served` spine objective without claiming contact before it exists.
