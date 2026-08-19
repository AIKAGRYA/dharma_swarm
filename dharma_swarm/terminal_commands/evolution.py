"""Evolution engine commands (propose, trend, apply, promote, rollback, auto, daemon)."""

from __future__ import annotations

import json
from pathlib import Path


from dharma_swarm.terminal_commands._helpers import (
    _get_swarm,
    _run,
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


def _load_promotion_packet(promotion_path: str | None) -> dict | None:
    """Parse the promotion packet before any swarm resources exist.

    A missing or malformed packet must fail the command before swarm
    initialization, so no cleanup path is ever owed for an operator typo.
    """
    if not promotion_path:
        return None
    try:
        return json.loads(Path(promotion_path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SystemExit(f"invalid promotion packet {promotion_path}: {exc}")


def cmd_evolve_auto(
    files: list[str] | None, model: str, context: str,
    single_model: bool = False,
    shadow: bool = True,
    token_budget: int = 0,
    promotion_path: str | None = None,
    trusted_judge_public_keys: list[str] | None = None,
) -> None:
    """LLM-powered autonomous evolution cycle."""
    promotion_verification = _load_promotion_packet(promotion_path)

    async def _auto():
        from dharma_swarm.models import ProviderType

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

        # Fallback provider (OpenRouter)
        provider = swarm._router.get_provider(ProviderType.OPENROUTER)

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
            print(f"Auto-evolving {len(source_files)} files with {model}{' [SHADOW]' if shadow else ''}...")
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
            promotion_verification=promotion_verification,
            trusted_judge_public_keys=trusted_judge_public_keys or [],
        )

        print(f"\n=== Auto-Evolution Results ===")
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
    promotion_path: str | None = None,
    trusted_judge_public_keys: list[str] | None = None,
) -> None:
    """Run continuous autonomous evolution daemon."""
    promotion_verification = _load_promotion_packet(promotion_path)

    async def _daemon():
        swarm = await _get_swarm()
        if swarm._engine is None:
            print("Engine not initialized")
            await swarm.shutdown()
            return

        from dharma_swarm.models import ProviderType

        provider = swarm._router.get_provider(ProviderType.OPENROUTER)
        use_router = not single_model

        # Token budget
        if token_budget > 0:
            swarm._engine._max_cycle_tokens = token_budget

        print(f"Darwin daemon starting{' [SHADOW]' if shadow else ''}")
        if use_router:
            from dharma_swarm.evolution_roster import roster_summary
            print(f"  Mode:      MULTI-MODEL (roster)")
            print(roster_summary())
        else:
            print(f"  Model:     {model}")
        print(f"  Interval:  {interval:.0f}s ({interval/60:.0f}min)")
        print(f"  Threshold: {threshold}")
        print(f"  Cycles:    {'infinite' if cycles is None else cycles}")
        if token_budget > 0:
            print(f"  Token cap: {token_budget:,}")
        print(f"  Ctrl+C to stop\n")

        try:
            await swarm._engine.daemon_loop(
                think_provider=provider,
                model=model,
                interval=interval,
                fitness_threshold=threshold,
                max_cycles=cycles,
                router=swarm._router if use_router else None,
                shadow=shadow,
                promotion_verification=promotion_verification,
                trusted_judge_public_keys=trusted_judge_public_keys or [],
            )
        except KeyboardInterrupt:
            pass
        finally:
            await swarm.shutdown()
            print("\nDaemon stopped.")

    _run(_daemon())
