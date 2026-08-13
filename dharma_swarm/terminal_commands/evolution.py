"""Evolution engine commands (propose, trend, apply, promote, rollback, auto, daemon)."""

from __future__ import annotations

from pathlib import Path
from typing import Any


from dharma_swarm.terminal_commands._helpers import (
    _get_swarm,
    _run,
)


def _provider_candidates_for_model(model: str) -> "list[Any]":
    """Order the provider types that can serve *model*, best lane first.

    Mirrors the model-id prefix routing in
    dharma_swarm/forge_v1/providers.py:_provider_for_model, projected onto
    the router's registered lanes (no provider construction here).
    """
    from dharma_swarm.models import ProviderType

    mid = (model or "").strip().lower()
    if mid in {"claude-code", "claude_code"}:
        return [ProviderType.CLAUDE_CODE]

    candidates: list[ProviderType] = []
    try:
        from dharma_swarm.model_pool import entry_for_model_id

        entry = entry_for_model_id(model)
    except Exception:
        entry = None
    if entry is not None:
        candidates.extend(route.provider for route in entry.routes)

    if mid.startswith(("claude", "opus", "sonnet")):
        candidates.extend((ProviderType.ANTHROPIC, ProviderType.CLAUDE_CODE))
    elif mid.startswith(("gpt", "o1", "o3")):
        candidates.append(ProviderType.OPENAI)
    elif mid.startswith("gemini"):
        candidates.append(ProviderType.GOOGLE_AI)
    elif mid.endswith(":cloud"):
        candidates.append(ProviderType.OLLAMA)
    if "/" in mid or not candidates:
        candidates.append(ProviderType.OPENROUTER)
    return list(dict.fromkeys(candidates))


def _resolve_evolution_provider(
    router: Any, *, model: str, single_model: bool,
) -> "tuple[Any, Any]":
    """Resolve the think-provider for evolve auto/daemon via the router.

    single_model: the provider must serve the requested model (e.g. the
    ClaudeCodeProvider lane for "claude-code") — never an unconditional
    OpenRouter. Multi-model: the roster routes per file, so any available
    registered lane is an honest fallback provider.

    Raises RuntimeError naming the configured providers if nothing matches.
    """
    registered: dict[Any, Any] = dict(getattr(router, "_providers", {}) or {})

    def _available(provider: Any) -> bool:
        return provider is not None and bool(getattr(provider, "available", True))

    if single_model and (model or "").strip():
        candidates = _provider_candidates_for_model(model)
    else:
        candidates = list(registered)

    for provider_type in candidates:
        provider = registered.get(provider_type)
        if _available(provider):
            return (provider_type, provider)

    configured = ", ".join(
        p.value for p in registered if _available(registered.get(p))
    ) or "none"
    wanted = f" for model {model!r}" if single_model and (model or "").strip() else ""
    raise RuntimeError(
        f"No available provider{wanted}. Configured providers: [{configured}]"
    )

def cmd_evolve_propose(component: str, description: str, change_type: str, diff: str) -> None:
    """Propose an evolution and run it through the pipeline."""
    async def _propose():
        swarm = await _get_swarm()
        result = await swarm.evolve(
            component=component,
            change_type=change_type,
            description=description,
            diff=diff,
        )
        if result["status"] == "rejected":
            print(f"REJECTED: {result['reason']}")
        else:
            print(f"ARCHIVED: {result['entry_id']} (fitness: {result['weighted_fitness']:.3f})")
        await swarm.shutdown()

    _run(_propose())


def cmd_evolve_trend(component: str | None) -> None:
    """Show fitness trend over time."""
    async def _trend():
        from dharma_swarm.archive import EvolutionArchive

        archive = EvolutionArchive()
        await archive.load()
        trend = archive.fitness_over_time(component=component)
        if not trend:
            print("No fitness data yet.")
        else:
            print("Fitness Trend:")
            for ts, fitness in trend:
                print(f"  {ts[:19]}  {fitness:.3f}")

    _run(_trend())


def cmd_evolve_apply(component: str, description: str) -> None:
    """Run evolution with sandbox."""
    async def _apply():
        swarm = await _get_swarm()
        if swarm._engine is None:
            print("Engine not initialized")
            await swarm.shutdown()
            return
        proposal = await swarm._engine.propose(
            component=component, change_type="mutation", description=description,
        )
        await swarm._engine.gate_check(proposal)
        if proposal.status.value == "rejected":
            print(f"REJECTED: {proposal.gate_reason}")
            await swarm.shutdown()
            return
        proposal_out, sr = await swarm._engine.apply_in_sandbox(proposal, timeout=30.0)
        test_results = swarm._engine._parse_sandbox_result(sr)
        await swarm._engine.evaluate(proposal_out, test_results=test_results)
        entry_id = await swarm._engine.archive_result(proposal_out)
        fitness = proposal_out.actual_fitness
        print(f"APPLIED: {entry_id} (fitness: {fitness.weighted():.3f}, tests: {test_results.get('pass_rate', 0):.0%})")
        await swarm.shutdown()
    _run(_apply())


def cmd_evolve_promote(entry_id: str) -> None:
    """Promote a canary deployment."""
    async def _promote():
        swarm = await _get_swarm()
        if swarm._canary is None:
            print("Canary not initialized")
            await swarm.shutdown()
            return
        ok = await swarm._canary.promote(entry_id)
        print(f"Promoted: {entry_id}" if ok else f"Entry not found: {entry_id}")
        await swarm.shutdown()
    _run(_promote())


def cmd_evolve_rollback(entry_id: str, reason: str = "Manual rollback") -> None:
    """Rollback a deployment."""
    async def _rollback():
        swarm = await _get_swarm()
        if swarm._canary is None:
            print("Canary not initialized")
            await swarm.shutdown()
            return
        ok = await swarm._canary.rollback(entry_id, reason=reason)
        print(f"Rolled back: {entry_id} ({reason})" if ok else f"Entry not found: {entry_id}")
        await swarm.shutdown()
    _run(_rollback())


def cmd_evolve_auto(
    files: list[str] | None, model: str, context: str,
    single_model: bool = False,
    shadow: bool = True,
    token_budget: int = 0,
) -> None:
    """LLM-powered autonomous evolution cycle."""
    async def _auto():
        swarm = await _get_swarm()
        if swarm._engine is None:
            print("Engine not initialized")
            await swarm.shutdown()
            return

        # Default: core modules worth evolving
        if files:
            source_files = [Path(f) for f in files]
        else:
            src = Path.home() / "dharma_swarm" / "dharma_swarm"
            source_files = [
                src / "evolution.py",
                src / "selector.py",
                src / "archive.py",
                src / "monitor.py",
                src / "telos_gates.py",
                src / "context.py",
            ]

        # Resolve the think-provider honestly: single-model must get the lane
        # serving the requested model; multi-model gets any available fallback
        # lane (the router does the real per-file routing).
        try:
            provider_type, provider = _resolve_evolution_provider(
                swarm._router, model=model, single_model=single_model,
            )
        except RuntimeError as exc:
            print(f"ERROR: {exc}")
            await swarm.shutdown()
            return

        # Token budget
        if token_budget > 0:
            swarm._engine._max_cycle_tokens = token_budget
            print(f"Token budget: {token_budget:,}")

        # Multi-model mode (default) vs single-model
        use_router = not single_model
        if use_router:
            from dharma_swarm.evolution_roster import roster_summary
            print("Multi-model evolution enabled")
            print(roster_summary())
            print(f"\nEvolving {len(source_files)} files{' [SHADOW]' if shadow else ''}...")
        else:
            print(f"Auto-evolving {len(source_files)} files with {model} via {provider_type.value}{' [SHADOW]' if shadow else ''}...")
        for sf in source_files:
            print(f"  {sf.name}")
        print()

        result = await swarm._engine.auto_evolve(
            provider=provider,
            source_files=source_files,
            model=model,
            context=context,
            router=swarm._router if use_router else None,
            shadow=shadow,
        )

        print("\n=== Auto-Evolution Results ===")
        print(f"Proposals generated: {result.proposals_submitted}")
        print(f"Passed gates:        {result.proposals_gated}")
        print(f"Tested:              {result.proposals_tested}")
        print(f"Archived:            {result.proposals_archived}")
        print(f"Best fitness:        {result.best_fitness:.3f}")
        print(f"Duration:            {result.duration_seconds:.1f}s")
        if result.reflection:
            print(f"Reflection:          {result.reflection[:200]}")
        if result.lessons_learned:
            print("Lessons:")
            for lesson in result.lessons_learned:
                print(f"  - {lesson}")
        await swarm.shutdown()

    _run(_auto())


def cmd_evolve_daemon(
    interval: float, threshold: float, model: str, cycles: int | None,
    single_model: bool = False,
    shadow: bool = True,
    token_budget: int = 0,
) -> None:
    """Run continuous autonomous evolution daemon."""
    async def _daemon():
        swarm = await _get_swarm()
        if swarm._engine is None:
            print("Engine not initialized")
            await swarm.shutdown()
            return

        try:
            provider_type, provider = _resolve_evolution_provider(
                swarm._router, model=model, single_model=single_model,
            )
        except RuntimeError as exc:
            print(f"ERROR: {exc}")
            await swarm.shutdown()
            return
        use_router = not single_model

        # Token budget
        if token_budget > 0:
            swarm._engine._max_cycle_tokens = token_budget

        print(f"Darwin daemon starting{' [SHADOW]' if shadow else ''}")
        if use_router:
            from dharma_swarm.evolution_roster import roster_summary
            print("  Mode:      MULTI-MODEL (roster)")
            print(roster_summary())
        else:
            print(f"  Model:     {model} via {provider_type.value}")
        print(f"  Interval:  {interval:.0f}s ({interval/60:.0f}min)")
        print(f"  Threshold: {threshold}")
        print(f"  Cycles:    {'infinite' if cycles is None else cycles}")
        if token_budget > 0:
            print(f"  Token cap: {token_budget:,}")
        print("  Ctrl+C to stop\n")

        try:
            await swarm._engine.daemon_loop(
                think_provider=provider,
                model=model,
                interval=interval,
                fitness_threshold=threshold,
                max_cycles=cycles,
                router=swarm._router if use_router else None,
                shadow=shadow,
            )
        except KeyboardInterrupt:
            pass
        finally:
            await swarm.shutdown()
            print("\nDaemon stopped.")

    _run(_daemon())
