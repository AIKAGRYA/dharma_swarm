"""Stigmergy, strange loop, and forge commands."""

from __future__ import annotations

import asyncio
import json


from dharma_swarm.terminal_commands._helpers import (
    DHARMA_STATE,
    _run,
)

def cmd_stigmergy(file_path: str | None = None, *, as_json: bool = False) -> None:
    """Show recent stigmergic marks, hot paths, and high salience marks."""
    async def _stig() -> None:
        from dharma_swarm.stigmergy import StigmergyStore

        store = StigmergyStore(base_path=DHARMA_STATE / "stigmergy")
        density = store.density()

        if as_json:
            data: dict = {"density": density}
            if file_path:
                marks = await store.read_marks(file_path=file_path, limit=15)
                data["marks"] = [m.model_dump() for m in marks]
            else:
                recent = await store.read_marks(limit=10)
                data["recent"] = [m.model_dump() for m in recent]
                hot = await store.hot_paths(window_hours=48, min_marks=2)
                data["hot_paths"] = [{"path": p, "count": c} for p, c in hot]
                high = await store.high_salience(threshold=0.7, limit=5)
                data["high_salience"] = [m.model_dump() for m in high]
            print(json.dumps(data, indent=2, default=str))
            return

        print(f"=== Stigmergy ({density} marks) ===\n")

        if file_path:
            marks = await store.read_marks(file_path=file_path, limit=15)
            if not marks:
                print(f"No marks for {file_path}")
            else:
                print(f"Marks for {file_path}:")
                for m in marks:
                    ts = m.timestamp.isoformat()[:19]
                    print(f"  [{ts}] {m.agent} ({m.action}): {m.observation} [sal={m.salience:.1f}]")
                    if m.connections:
                        print(f"    connections: {', '.join(m.connections)}")
        else:
            recent = await store.read_marks(limit=10)
            if recent:
                print("Recent marks:")
                for m in recent:
                    ts = m.timestamp.isoformat()[:19]
                    print(f"  [{ts}] {m.agent} -> {m.file_path}")
                    print(f"    {m.action}: {m.observation} [sal={m.salience:.1f}]")

            hot = await store.hot_paths(window_hours=48, min_marks=2)
            if hot:
                print("\nHot paths (last 48h):")
                for path, count in hot:
                    print(f"  {path}: {count} marks")

            high = await store.high_salience(threshold=0.7, limit=5)
            if high:
                print("\nHigh salience marks (>= 0.7):")
                for m in high:
                    ts = m.timestamp.isoformat()[:19]
                    print(f"  [{ts}] {m.agent}: {m.observation} [sal={m.salience:.2f}]")

            if not recent and not hot and not high:
                print("No stigmergic marks yet. The lattice is empty.")

    _run(_stig())


def cmd_hum() -> None:
    """Show recent subconscious associations and strongest resonances."""
    async def _hum() -> None:
        from dharma_swarm.stigmergy import StigmergyStore
        from dharma_swarm.subconscious import SubconsciousStream

        store = StigmergyStore(base_path=DHARMA_STATE / "stigmergy")
        stream = SubconsciousStream(stigmergy=store)

        dreams = await stream.get_recent_dreams(limit=10)
        if not dreams:
            print("No dreams yet. The HUM is silent.")
            return

        print("=== Subconscious HUM ===\n")
        print("Recent associations:")
        for d in dreams:
            ts = d.timestamp.isoformat()[:19]
            print(f"  [{ts}] {d.source_a}")
            print(f"       <-> {d.source_b}")
            print(f"    {d.resonance_type} (strength={d.strength:.2f}): {d.description[:80]}")
            print()

        strong = await stream.strongest_resonances(threshold=0.3)
        if strong:
            print(f"Strongest resonances (>= 0.3): {len(strong)}")
            for s in strong[:5]:
                print(f"  {s.strength:.2f}  {s.resonance_type}: {s.description[:60]}")

    _run(_hum())


def cmd_cascade(
    domain: str = "code",
    seed_path: str | None = None,
    seed_skill: str | None = None,
    seed_project: str | None = None,
    track: str | None = None,
    max_iter: int | None = None,
) -> None:
    """Run a strange loop cascade domain."""

    async def _run():
        from dharma_swarm.cascade import get_registered_domains, run_domain

        if domain == "all":
            domains = get_registered_domains()
            for name in sorted(domains):
                try:
                    config = {"max_iterations": max_iter} if max_iter else None
                    r = await run_domain(name, resume=False, config=config)
                    status = "EIGENFORM" if r.eigenform_reached else ("CONVERGED" if r.converged else "INCOMPLETE")
                    print(f"  [{name}] {status} iter={r.iterations_completed} fitness={r.best_fitness:.3f} ({r.duration_seconds:.1f}s)")
                except Exception as e:
                    print(f"  [{name}] ERROR: {e}")
            return

        seed = None
        if seed_path:
            seed = {"path": seed_path}
            if track:
                seed["track"] = track
        elif seed_skill:
            seed = {"skill_name": seed_skill}
        elif seed_project:
            seed = {"project_path": seed_project}

        config = {"max_iterations": max_iter} if max_iter else None
        r = await run_domain(domain, seed=seed, resume=False, config=config)
        status = "EIGENFORM" if r.eigenform_reached else ("CONVERGED" if r.converged else "INCOMPLETE")
        print(f"Domain:     {r.domain}")
        print(f"Status:     {status}")
        print(f"Iterations: {r.iterations_completed}")
        print(f"Best fit:   {r.best_fitness:.3f}")
        if r.convergence_reason:
            print(f"Reason:     {r.convergence_reason}")
        print(f"Duration:   {r.duration_seconds:.1f}s")
        if r.fitness_trajectory:
            print(f"Trajectory: {' → '.join(f'{f:.3f}' for f in r.fitness_trajectory[-5:])}")

    asyncio.run(_run())


def cmd_forge(path: str | None = None, batch: str | None = None) -> None:
    """Score artifact(s) through the quality forge."""
    from pathlib import Path as P

    def _score_file(filepath: str) -> None:
        p = P(filepath).resolve()
        if not p.exists():
            print(f"  {filepath}: NOT FOUND")
            return

        content = p.read_text()
        scores: dict[str, float] = {}

        if p.suffix == ".py":
            try:
                from dharma_swarm.elegance import evaluate_elegance
                e = evaluate_elegance(content)
                scores["elegance"] = e.overall
            except Exception:
                scores["elegance"] = 0.0

        try:
            from dharma_swarm.metrics import MetricsAnalyzer
            sig = MetricsAnalyzer().analyze(content)
            scores["swabhaav"] = sig.swabhaav_ratio
            scores["entropy"] = sig.entropy
            scores["mimicry"] = 1.0 if sig.recognition_type.value == "MIMICRY" else 0.0
        except Exception:
            pass

        # Composite
        elegance = scores.get("elegance", 0.5)
        swabhaav = scores.get("swabhaav", 0.5)
        stars = elegance * 0.5 + swabhaav * 0.3 + (1.0 - scores.get("mimicry", 0.0)) * 0.2
        print(f"  {p.name}: {stars*10:.1f}★  elegance={elegance:.2f} swabhaav={swabhaav:.2f}")

    if batch:
        bp = P(batch)
        files = sorted(bp.glob("**/*.py")) + sorted(bp.glob("**/*.md"))
        print(f"Scoring {len(files)} files in {batch}:")
        for f in files[:20]:
            _score_file(str(f))
        if len(files) > 20:
            print(f"  ... and {len(files) - 20} more")
    elif path:
        print("Forge Score:")
        _score_file(path)
    else:
        print("Usage: dgc forge <path> | dgc forge --batch <dir>")
