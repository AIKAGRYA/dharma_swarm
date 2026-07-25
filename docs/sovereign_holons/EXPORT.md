# Sovereign Holon Harness — Export Notes (superseded standalone fork)

> 2026-07-07 update: the former repo-local `holon/` standalone fork was
> collapsed by the Sarathi v1.1 holon-system lane. Canonical runtime imports are
> now `dharma_swarm.holon_bridge` and `dharma_swarm.holon_runtime`. This document
> remains as historical export-design context only; do not recreate a second
> `holon/` package inside this repo.

**Goal:** The core harness (governed runnable shell + verification + context-bridging) must be usable as a clean, minimal, standalone package or Git subtree exactly like hermes-m5, without pulling the entire dharma_swarm.

## Minimal Surface (what is exported)

- `dharma_swarm/holon_runtime.py` + `holon_bridge.py` + thin supporting `holon_*.py` (kill, budget, compass, persistence projections)
- `dharma_swarm/memory_kernel/` (facade, context_admission, preview, atoms, writers inventory, write_receipts, context_eval — read-only proposal path)
- `dharma_swarm/runtime_provider.py` + `model_hierarchy.py` (the one provider door)
- `dharma_swarm/persistent_agent.py` (optional, for sleep-time reorg + compaction when you want the full conductor)
- `scripts/verify_holon_harness_prod.py` (the canonical external verifier)
- Dependencies: pydantic, aiosqlite (for persistence projections), typing extensions as needed. No full swarm.

## How to use standalone (example)

```bash
git subtree add --prefix holon https://.../dharma_swarm.git main --squash   # or copy the surface
cd my-project
python -m venv .venv
source .venv/bin/activate
pip install pydantic aiosqlite

# Then, from this repo's canonical package:
from dharma_swarm.holon_runtime import holon_wake_cycle, run_holon_loop
from dharma_swarm.memory_kernel import MemoryKernel
from dharma_swarm.runtime_provider import resolve_runtime_provider_config, create_runtime_provider

# Your runner (the "hands")
async def my_runner(task: str) -> tuple[str, str]:
    # ... call your model via the provider or directly ...
    return task, "reply"

mk = MemoryKernel()  # or your own surface adapters
result = await holon_wake_cycle("my-holon", my_runner, spent_usd=0, cap_usd=5, memory_kernel=mk)
```

The injected `AgentRunner` keeps it model-agnostic. All durable state is MemoryKernel atoms + local state_dir appends + write_receipts.

## Verification in the exported package

The same command must work:

```bash
python3 scripts/verify_holon_harness_prod.py --mode prod --require-live-smoke --require-passk 0.6 --require-exportable
```

`--require-exportable` creates a temp venv with *only* the declared minimal deps, adds the surface to PYTHONPATH, and asserts the core imports + a full governed cycle (with mk) succeeds.

## Packaging (for real distribution)

- A thin `pyproject.toml` or `setup.py` at the export root that declares only the minimal deps + the canonical `dharma_swarm` holon and memory-kernel subpackages.
- Do not add an in-repo `holon/__init__.py` fork; use packaging metadata or an out-of-repo distribution surface if a standalone name is needed.
- README in the exported tree points back to the full sovereign_holons docs for governance, telos, etc., but the runtime itself is self-contained.

## Non-goals for the export

- No full conductor/orchestrator swarm.
- No launchd, no ds-goal, no full governance UI.
- The harness is the "governed body" + context front-door. Higher policy (kill budget telos) is supplied by the caller or the thin organs.

This surface is deliberately small so it can be dropped into another repo and "just work" like hermes.

Receipt: written as part of the long autonomous drive for the SOTA harness mission (2026-06-10).
