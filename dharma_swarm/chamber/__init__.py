"""Hyperbolic Time Chamber — afferent-open / efferent-closed evolution substrate.

Track ``hyperbolic-time-chamber-2026-07``. Doctrine:
``docs/vision_maps/MASTER_2026-07-07_hyperbolic_time_chamber.md``; engineering
spec ``docs/plans/HYPERBOLIC_CHAMBER_ELEVATION_SPEC_2026-07-07.md``.

Modules:
- ``traces``       — chamber_gym_trace.v1, the E5 mandate (no gym run without it)
- ``gym_git_history`` — G1: the git-history repo gym (taskpack + scorer + leak guard)
- ``daily_delta``  — E4: the causal daily delta chain (the chamber's heartbeat)
- ``predictions``  — E3: micro-prediction lane on the existing ginko store

Hard boundaries (track non-goals): never imports from
``dharma_swarm.coordination`` or ``dharma_swarm.council`` (arena-owned);
class-2 signal only; no new truth stores; no efferent action.
"""
