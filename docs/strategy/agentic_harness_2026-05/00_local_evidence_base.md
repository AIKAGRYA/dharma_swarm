# Local Evidence Base

Date read: 2026-05-21
Repo: `/Users/dhyana/dharma_swarm`

Every expert memo in this folder is grounded in this shared local evidence base. This is the minimum antidote to "agent vibes": each strategy file is written after reading or inspecting at least these 33 repo files/modules and current onboarding surfaces.

## Governance And Onboarding

1. `CLAUDE.md`
2. `docs/ops/AGENT_ONBOARDING.md`
3. `docs/ops/CODEX_TOOLBELT_ONBOARDING.md`
4. `docs/ops/context_quorum_policy.json`
5. `scripts/runtime/context_quorum.py`
6. `docs/governance/SOVEREIGN_MANIFEST.md`
7. `docs/governance/BUILD_SESSION_ENTRYPOINT.md`
8. `docs/governance/CANONICAL_DOC_STACK.md`
9. `docs/governance/ANTI_SLOP_RULES.md`
10. `docs/state/BROKEN_REGISTER.md`

## Persistent-Agent And Cultivation Research

11. `docs/research/persistent_agents_census_2026-05/10_cultivation_architecture.md`
12. `docs/research/persistent_agents_census_2026-05/11_tracking_schema.md`
13. `docs/research/persistent_agents_census_2026-05/13_ontology_bridge.md`
14. `docs/research/persistent_agents_census_2026-05/06_world_map.md`
15. `docs/research/persistent_agents_census_2026-05/08_benchmark_matrix.md`
16. `docs/research/persistent_agents_deepdive_2026-05/02_00_synthesis.md`

## Ontology And Command-Plane Planning

17. `docs/research/ontology_promotion_2026-05/O6_ontology_synthesis.md`
18. `docs/research/ontology_promotion_2026-05/O5_promotion_scoring_model.md`
19. `docs/plans/2026-05-21-command-plane-design-lock.md`
20. `docs/plans/2026-05-21-codex-composer-l4-lead-orchestrator-cultivation-plan.md`

## Runtime, Memory, And Coordination Modules

21. `dharma_swarm/memory_palace.py`
22. `dharma_swarm/handoff.py`
23. `dharma_swarm/runtime_contract.py`
24. `dharma_swarm/runtime_artifacts.py`
25. `dharma_swarm/runtime_provider.py`
26. `dharma_swarm/provider_matrix.py`
27. `dharma_swarm/orchestrate_live.py`
28. `dharma_swarm/swarm.py`
29. `dharma_swarm/evolution.py`
30. `dharma_swarm/diversity_archive.py`
31. `dharma_swarm/telos_gates.py`
32. `dharma_swarm/dharma_kernel.py`
33. `dharma_swarm/task_board.py`

## Implications

- The repo already has governance, runtime memory, provider routing, handoff, task-board, evolution, telos, and ontology components. The strategic move is integration and pruning, not another parallel framework.
- `make onboard` is the live state entrypoint. Any strategy that bypasses it will become stale.
- The runtime spine identified by ontology promotion work is the best anchor for future agent coordination: `RuntimeSession`, `SessionEvent`, `TaskClaim`, `DelegationRun`, `ContextBundle`, `RoutingDecision`, `RuntimeArtifact`, `ExternalOutcome`, and `OperatorInterrupt`.
- The persistent-agent census already warns against false L4 promotion. Strategy must preserve that boundary.
- The user complaint about repo sprawl is evidence, not noise. Strategy has to reduce the number of active surfaces a new agent needs to trust.
