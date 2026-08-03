# Sarathi Composition Root P0

**Status:** active build contract, not a liveness or completeness claim  
**Owner:** `organism-rewire-2026-07`, item 11  
**Product root:** `dharma_swarm/sarathi/`

## Decision

Sarathi is the repo-owned, mutable persistent-agent product. A caller should not
need to know whether a capability currently lives in the sovereign-holon,
MemoryKernel, Living Agent Kernel, roaming-mailbox, provider, or Sarathi-organ
family. The stable product boundary will be one import:

```python
from dharma_swarm.sarathi import handle_turn

result = await handle_turn(request)
```

This is a composition root, not a new substrate. Shared engines remain in their
current owner modules and are reached through narrow adapters. The June Holon
decision already forbids a second agent system, registry, daemon, or memory store
(`docs/sovereign_holons/README.md:77-83`). The August inventory independently
found plentiful organs but almost no composition
(`docs/reports/hermes_persistent_agent_index_2026-08-01.md:106-115`).

## P0 deliverable

The first implementation slice owns only `dharma_swarm/sarathi/**` and its three
named tests. It must provide:

1. An async, ingress-neutral `handle_turn(request) -> result` Python contract.
2. One generated `turn_id` carried through the result and durable receipt.
3. A version-controlled Sarathi identity/persona that can be revised in Git.
4. A real provider-backed cognition adapter using the canonical runtime-provider
   door, plus dependency injection for hermetic tests.
5. A shared `RuntimeStateStore` adapter for session history and turn receipts;
   no new database schema or store.
6. No tool execution in P0. Requested effects must be represented explicitly and
   denied unless a future, separately admitted authority adapter proves a lease,
   budget, and reversibility decision.
7. Lazy imports: importing `dharma_swarm.sarathi` must create no provider, state
   directory, subprocess, socket, or loop.
8. Compatibility: existing `dharma_swarm.holon_system.sarathi` imports and exports
   remain unchanged.

The slice is **not** a full Hermes/OpenClaw-class shell yet. It closes the missing
product boundary and one real message→model→reply→receipt path; memory retrieval,
tool execution, transports, heartbeat, and self-modification remain explicit
follow-on adapters.

## Public types

- `SarathiTurnRequest`: message, session/caller identity, ingress metadata, and
  optional history/context.
- `SarathiTurnResult`: reply, turn/session identity, provider/model provenance,
  receipt reference, and denied/pending effect intents.
- `SarathiIdentity`: stable source identity and persona revision.
- `SarathiShell`: dependency-injected composition object.
- `build_sarathi_shell(...)`: portable factory; state root is injected or resolved
  through the existing `DHARMA_STATE_DIR`/`DHARMA_HOME` convention.
- `handle_turn(...)`: convenience entrypoint over the default shell.

## Acceptance proof

The implementation packet must run at least:

```bash
python -m pytest -q \
  tests/test_sarathi_public_api.py \
  tests/test_sarathi_shell.py \
  tests/test_sarathi_import_boundaries.py \
  tests/test_holon_system_imports.py
python -m ruff check dharma_swarm/sarathi \
  tests/test_sarathi_public_api.py \
  tests/test_sarathi_shell.py \
  tests/test_sarathi_import_boundaries.py
```

Required negative controls:

- importing the package with an empty temporary home leaves that home empty;
- a cognition response containing effect intents cannot execute them;
- a failed receipt write cannot be reported as a receipted successful turn;
- no module under the new root imports `agent_runner`, `autonomous_agent`, or a
  host-specific runtime script.

## Deferred adapters and ownership doors

- ContextCompiler and MemoryKernel retrieval need a measured adapter and tests.
- Living Agent Kernel is the preferred candidate for governed effects, but its
  owner must admit the integration and prove execution-lease validation.
- HTTP, A2A, MCP, CLI registration, schedulers, and service manifests remain with
  their present owners. Each should become a thin caller of `handle_turn`; none
  may grow a second Sarathi loop.
- Self-modification must produce a proposal, gate, verification, promotion, and
  rollback receipt before it can mutate repo code.

The implementation packet is mandatory even though the new package is not a
global hot path: it binds exact ownership, tests, negative controls, and rollback
before this P0 product seam is introduced.
