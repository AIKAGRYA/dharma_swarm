# Terminal Operating Model

Last updated: 2026-04-10 Asia/Makassar

This document sets the current operating model for Dharma Swarm terminal work so humans and agents stop treating multiple terminal surfaces as equal sources of truth.

## Current Status

- `terminal/` is the canonical Bun + Ink operator shell.
- `dharma_swarm/tui/` is a legacy Textual surface still relevant for some flows and migrations.
- `terminal-v2/` is experimental and frozen as a product surface.
- `dharma_swarm/terminal_bridge.py` is a transport seam under reduction, not the place to keep growing shell-local policy.

## Working Rules

- Ship operator-facing terminal changes in `terminal/` unless a human explicitly changes the canonical surface.
- Do not add new product features directly to `terminal-v2/`.
- Use `terminal-v2/` as a reference for decomposition patterns, not as a second live terminal to keep in parity.
- Preserve good UI work by promoting visual decisions, layout lessons, and component boundaries from `terminal-v2/` only after they are reimplemented against the canonical `terminal/` protocol/state model.
- Move shared contracts toward `operator_core` or other canonical runtime modules.
- Keep shell-local rendering and presentation logic in the shell, not in the Python bridge.

## Clean UI Policy

The goal is not an ugly minimal shell. The goal is one clean operator shell with a strong UI and one source of runtime truth.

- Good visual design belongs in `terminal/`.
- `terminal-v2/` may be mined for visual language, spacing, panel structure, model-picker ideas, and interaction references.
- `terminal-v2/` must not regain independent routing, protocol, session, or bridge semantics.
- A UI improvement is promotable only when it consumes the existing typed protocol or extends that protocol explicitly.
- A UI improvement is not promotable if it requires keeping a second terminal runtime alive.

## Bridge Boundary

The bridge should own:

- transport
- typed request and response delivery
- projection of shared runtime facts

The bridge should not keep accumulating:

- shell-specific text rendering
- pane-target assumptions
- presentation-only summaries
- UI reconciliation logic that belongs in the Bun shell

Current reduction status:

- bootstrap context and working-memory assembly are isolated in `dharma_swarm/terminal_bridge_context.py`
- compatibility text renderers are isolated in `dharma_swarm/terminal_bridge_renderers.py`
- command graph and command registry payload construction are owned by `dharma_swarm/operator_core/command_payloads.py`
- model-policy summary construction is owned by `dharma_swarm/operator_core/routing_payloads.py`
- the bridge still owns adapter lifecycle, stdio transport, request dispatch, and compatibility wrappers

## Migration Priority

1. Reduce `terminal/src/app.tsx` by extracting stable shell helpers into dedicated modules inside `terminal/src/`.
2. Consolidate duplicated semantic core only after one Bun shell is clearly canonical.
3. Trim `terminal_bridge.py` by moving presentation logic outward and durable contracts inward.
4. Revisit whether any `terminal-v2/` modules should be promoted only after the bridge boundary is cleaner.

## Autonomous Lane

For bounded unattended terminal cleanup, use:

- [2026-04-09-terminal-autonomous-build-control.md](/Users/dhyana/dharma_swarm/docs/plans/2026-04-09-terminal-autonomous-build-control.md)
- `bash scripts/start_terminal_autonomous_build_tmux.sh`
- `bash scripts/status_terminal_autonomous_build_tmux.sh`
- `bash scripts/stop_terminal_autonomous_build_tmux.sh`

## Promotion Gate For Any Future Terminal

A future terminal surface should not be promoted unless it:

- reuses the canonical shared contract surface
- does not fork protocol and state semantics again
- has focused smoke coverage for session, routing, approvals, and resync flows
- has an explicit migration path from the current canonical shell
