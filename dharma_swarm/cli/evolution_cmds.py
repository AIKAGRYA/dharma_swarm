"""CLI commands for evolution pipeline (propose, trend, apply, promote, etc.).

Extracted from dgc_cli.py for module budget compliance.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dharma_swarm.cli._helpers import _run, DHARMA_STATE

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


def cmd_dharma_status() -> None:
    """Show kernel integrity, principle count, and corpus claim counts by status."""
    async def _status() -> None:
        from dharma_swarm.dharma_kernel import KernelGuard
        from dharma_swarm.dharma_corpus import DharmaCorpus, ClaimStatus
        from dharma_swarm.stigmergy import StigmergyStore
        from collections import Counter

        print("=== Dharma Kernel ===")
        guard = KernelGuard(kernel_path=DHARMA_STATE / "kernel.json")
        try:
            kernel = await guard.load()
            integrity = kernel.verify_integrity()
            print(f"  Integrity:  {'OK' if integrity else 'TAMPERED'}")
            print(f"  Principles: {len(kernel.principles)}")
            print(f"  Signature:  {kernel.signature[:16]}...")
            critical = [p for p in kernel.principles.values() if p.severity == "critical"]
            print(f"  Critical:   {len(critical)}  High: {len(kernel.principles) - len(critical)}")
        except FileNotFoundError:
            print("  Kernel not initialized (run swarm init to create default)")
        except ValueError as exc:
            print(f"  Kernel INVALID: {exc}")

        print("\n=== Dharma Corpus ===")
        corpus = DharmaCorpus(path=DHARMA_STATE / "corpus.jsonl")
        await corpus.load()
        all_claims = await corpus.list_claims()
        if not all_claims:
            print("  No claims in corpus.")
        else:
            counts: Counter[str] = Counter()
            for cl in all_claims:
                counts[cl.status.value] += 1
            print(f"  Total claims: {len(all_claims)}")
            for status_val in ClaimStatus:
                c = counts.get(status_val.value, 0)
                if c > 0:
                    print(f"    {status_val.value:<14} {c}")

        print("\n=== Stigmergy ===")
        store = StigmergyStore(base_path=DHARMA_STATE / "stigmergy")
        density = store.density()
        print(f"  Mark density: {density}")
        if density > 0:
            hot = await store.hot_paths(window_hours=48, min_marks=2)
            print(f"  Hot paths (48h): {len(hot)}")

    _run(_status())


def cmd_dharma_corpus(status_filter: str | None = None, category_filter: str | None = None) -> None:
    """List corpus claims with optional status/category filters."""
    async def _corpus() -> None:
        from dharma_swarm.dharma_corpus import DharmaCorpus, ClaimStatus, ClaimCategory

        corpus = DharmaCorpus(path=DHARMA_STATE / "corpus.jsonl")
        await corpus.load()
        s = ClaimStatus(status_filter) if status_filter else None
        c = ClaimCategory(category_filter) if category_filter else None
        claims = await corpus.list_claims(status=s, category=c)
        if not claims:
            print("No claims found.")
        else:
            print(f"{'ID':<16}  {'STATUS':<14}  {'CAT':<18}  {'CONF':>4}  STATEMENT")
            print("-" * 80)
            for cl in claims:
                print(
                    f"{cl.id:<16}  {cl.status.value:<14}  {cl.category.value:<18}  "
                    f"{cl.confidence:.1f}   {cl.statement[:40]}"
                )
            print(f"\n{len(claims)} claim(s) shown.")
    _run(_corpus())


def cmd_dharma_review(claim_id: str) -> None:
    """Show full claim details for review."""
    async def _review() -> None:
        from dharma_swarm.dharma_corpus import DharmaCorpus

        corpus = DharmaCorpus(path=DHARMA_STATE / "corpus.jsonl")
        await corpus.load()
        claim = await corpus.get(claim_id)
        if claim is None:
            print(f"Claim not found: {claim_id}")
            return

        print(f"=== Claim {claim.id} ===")
        print(f"  Status:     {claim.status.value}")
        print(f"  Category:   {claim.category.value}")
        print(f"  Confidence: {claim.confidence:.2f}")
        print(f"  Enforcement:{claim.enforcement}")
        print(f"  Created by: {claim.created_by}")
        print(f"  Created at: {claim.created_at}")
        if claim.parent_id:
            print(f"  Parent ID:  {claim.parent_id}")
        if claim.tags:
            print(f"  Tags:       {', '.join(claim.tags)}")
        if claim.parent_axiom:
            print(f"  Axioms:     {', '.join(claim.parent_axiom)}")

        print(f"\n  Statement:\n    {claim.statement}")

        if claim.evidence_links:
            print(f"\n  Evidence ({len(claim.evidence_links)}):")
            for ev in claim.evidence_links:
                print(f"    [{ev.type}] {ev.url_or_ref}")
                print(f"      {ev.description}")

        if claim.counterarguments:
            print(f"\n  Counterarguments ({len(claim.counterarguments)}):")
            for ca in claim.counterarguments:
                print(f"    - {ca}")

        if claim.review_history:
            print(f"\n  Review History ({len(claim.review_history)}):")
            for rr in claim.review_history:
                print(f"    [{rr.timestamp[:19]}] {rr.reviewer}: {rr.action}")
                print(f"      {rr.comment}")

        # Show lineage if this claim has a parent
        lineage = await corpus.get_lineage(claim_id)
        if len(lineage) > 1:
            print(f"\n  Lineage ({len(lineage)} claims):")
            for lc in lineage:
                marker = " <-- current" if lc.id == claim_id else ""
                print(f"    {lc.id} ({lc.status.value}){marker}")

    _run(_review())


def cmd_evolve_apply(component: str, description: str) -> None:
    """Run evolution with sandbox."""
    async def _apply():
        swarm = await _get_swarm()
        if swarm._engine is None:
            print("Engine not initialized")
            await swarm.shutdown()
            return
        from dharma_swarm.evolution import Proposal
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
    shadow: bool = False,
    token_budget: int = 0,
) -> None:
    """LLM-powered autonomous evolution cycle."""
    async def _auto():
        from pathlib import Path
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
    shadow: bool = False,
    token_budget: int = 0,
) -> None:
    """Run continuous autonomous evolution daemon."""
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
            )
        except KeyboardInterrupt:
            pass
        finally:
            await swarm.shutdown()
            print("\nDaemon stopped.")

    _run(_daemon())
