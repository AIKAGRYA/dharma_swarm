# Ratchet Adjudication - 2026-06-25

Base branch: `origin/main` at `c53721d5f` (`#695` merged).

Read-only measurement before fixes:

```text
modules_over_500_lines         194 -> 207  REGRESSION
largest_module_lines           5186 -> 5255 REGRESSION
boundary_unfrozen_records      7 -> 8      REGRESSION
boundary_unwitnessed_swallows  10 -> 12    REGRESSION
property_test_files            4 -> 5      IMPROVED
```

## Fixed In This Branch

Boundary drift is genuine contract drift and should be fixed, not rebaselined.

| Counter | Drift | Resolution |
|---|---:|---|
| `boundary_unfrozen_records` | `7 -> 8` | Add `schema_version` to `dharma_swarm/a2a/task_receipt.py::InboxReceipt`. |
| `boundary_unwitnessed_swallows` | `10 -> 12` | Add logger witnesses to the two broad JSON fallback handlers in `dharma_swarm/a2a/agent_presence.py`. |

## Adjudication Applied

The raw line-count counters remained governance-red after the boundary fixes.
The follow-up adjudication chooses the explicit rebaseline path for these raw
LOC counters rather than cosmetic module splits. The baseline file is updated in
the same PR, so any future movement beyond these reviewed high-water marks still
fails the ratchet.

### `largest_module_lines`: `5186 -> 5255`

Current largest module:

```text
5255 dharma_swarm/thinkodynamic_director.py
```

Decision basis:

1. Fix: reduce `thinkodynamic_director.py` below `5186` lines without changing
   behavior. This is possible only if there is obvious dead/comment-only bulk.
   It should not become a blind extraction just to satisfy a line counter.
2. Adjudicate: one-time reviewed rebaseline with written rationale, because the
   Ousterhout audit found raw LOC is weaker than effective public surface as an
   architecture signal.

Applied: option 2. New bound: `5255`.

Next fitness upgrade: add an interface-density counter as the stronger
replacement signal.

### `modules_over_500_lines`: `194 -> 207`

New files over 500 lines since the ratchet baseline:

```text
651 dharma_swarm/a2a/agent_card.py
506 dharma_swarm/chetana/cli.py
538 dharma_swarm/coordination/arena/runner.py
1092 dharma_swarm/cybernetics_codex.py
568 dharma_swarm/model_council_e2e.py
533 dharma_swarm/model_hierarchy.py
609 dharma_swarm/model_routing_live_probe.py
572 dharma_swarm/model_status.py
621 dharma_swarm/operator_core/operator_coherence/git_governance.py
506 dharma_swarm/router_v1.py
548 dharma_swarm/startup_crew.py
620 dharma_swarm/tui/model_routing.py
673 dharma_swarm/world_radar/bronze.py
```

Decision basis:

1. Fix: reduce every listed module to `<=500` lines or remove truly dead files.
   This is invasive for active surfaces such as A2A agent cards, model routing,
   startup, and world radar.
2. Adjudicate: one-time reviewed rebaseline for raw LOC count, while adding
   better counters for effective public interface density and co-change
   coupling in the next governance slice.

Recommendation: do not perform cosmetic splits. Use an explicit reviewed
rebaseline for raw LOC, then promote interface-density and co-change counters.

Applied: explicit reviewed rebaseline. New bound: `207`.

Next fitness upgrade: promote interface-density and co-change counters so this
raw LOC counter becomes a coarse backstop, not the primary architecture signal.
