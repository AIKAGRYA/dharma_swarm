"""DGM Loop — Real Darwin Gödel Machine evolution for DHARMA SWARM.

This module closes the gap identified in WHAT_IT_WANTS_TO_BECOME.md:
    "The Darwin Engine produces diffs. Those diffs are stored in an
    evolution archive. But they are never applied to a running agent
    and benchmarked against a measurable objective."

What it implements:
    1. Open-ended archive sampling (quality-diversity, not hill-climbing)
       Mirrors Sakana AI's DGM: sample ANY prior entry weighted by novelty,
       not just the current best. This is the architectural difference between
       DGM (20%→50% SWE-bench in 80 iterations) and hill-climbing (plateaus).

    2. Self-modification loop: generate a proposal that modifies a source file
       that DHARMA SWARM agents actually execute, apply it in a real sandbox,
       benchmark against a measurable fitness function, archive with full lineage.

    3. Telos-gated: every proposed diff passes through the 11 Telos Gates before
       application. No modification that violates dharmic constraints is applied,
       even if it would improve benchmark performance.

    4. Task-seeding: when called as a task by an autonomous agent, produces a
       structured result that includes the best-found parent, the proposed diff,
       the benchmark result, and the archive lineage.

The fitness function used here is not just pytest pass rate — it is the swarm's
own task completion rate, dharmic alignment score, and economic efficiency. A
modification that makes tests pass but reduces task completion or dharmic fitness
is not an improvement.

Usage (direct)::

    loop = DGMLoop(engine=darwin_engine, state_dir=Path("~/.dharma"))
    result = await loop.run_one_generation(source_file=Path("agent_runner.py"))
    # DGMResult with parent_id, child_id, fitness_delta, applied, rolled_back

Usage as agent task::

    # In agent task description:
    "Use the run_dgm_evolution tool with source_file=agent_runner.py,
     fitness_context='last 10 tasks: 7 completed, 3 failed due to
     provider timeout — optimize provider retry logic'"

Relationship to existing code:
    - DarwinEngine.auto_evolve(shadow=False) is the underlying executor.
      This module wraps it with open-ended archive sampling and a swarm-specific
      fitness signal rather than a fixed source file list.
    - selector.py has _novelty_weight() which is the right primitive but is not
      wired into the auto_evolve source file selection. This module uses it.
    - EvolutionArchive.list_entries() returns all entries with lineage.
      This module uses it to build the quality-diversity sampling pool.

Reference: Sakana AI Darwin Gödel Machine (ICLR 2026)
    https://sakana.ai/dgm/
    "New agents are created and scored by interleaving self-modification
    with downstream task evaluation."
    "Without the open-ended exploration mechanism, performance was lower."
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class DGMResult:
    """Result of one DGM evolution generation."""
    parent_id: str | None = None
    child_id: str | None = None          # archive entry id of the new agent
    source_file: str = ""
    fitness_before: float = 0.0
    fitness_after: float = 0.0
    fitness_delta: float = 0.0           # positive = improvement
    applied: bool = False                # diff was applied to real code
    rolled_back: bool = False            # diff was rolled back after test failure
    shadow_mode: bool = True             # True means no real mutation occurred
    telos_gate_passed: bool = True
    proposals_submitted: int = 0
    proposals_gated: int = 0
    archive_size_before: int = 0
    archive_size_after: int = 0
    duration_seconds: float = 0.0
    error: str | None = None
    lineage_depth: int = 0               # how many ancestors this entry has
    selection_strategy: str = "novelty_weighted"

    def summary(self) -> str:
        status = "LIVE" if not self.shadow_mode else "SHADOW"
        applied_str = "applied" if self.applied else ("rolled_back" if self.rolled_back else "not_applied")
        return (
            f"DGM [{status}] parent={self.parent_id or 'seed'} → child={self.child_id or 'none'} | "
            f"file={self.source_file} | fitness {self.fitness_before:.3f}→{self.fitness_after:.3f} "
            f"(Δ={self.fitness_delta:+.3f}) | {applied_str} | depth={self.lineage_depth} | "
            f"archive: {self.archive_size_before}→{self.archive_size_after} | {self.duration_seconds:.1f}s"
        )


# ---------------------------------------------------------------------------
# Quality-diversity parent sampler (open-ended, not hill-climbing)
# ---------------------------------------------------------------------------

async def _sample_parent_qd(
    archive: Any,  # EvolutionArchive
    fitness_weights: dict[str, float] | None = None,
    novelty_pressure: float = 0.7,
) -> tuple[Any | None, int]:
    """Sample a parent using quality-diversity weighting.

    This is the architectural difference between DGM and hill-climbing.
    Sakana proved: without open-ended exploration (archiving and branching
    from ANY prior entry, not just the current best), performance plateaus.

    The weight for each entry is:
        w(e) = fitness(e)^(1-p) * novelty(e)^p
    where p = novelty_pressure and novelty(e) = 1/(1 + n_children(e)).

    At novelty_pressure=0.7: 70% exploration, 30% exploitation.
    At novelty_pressure=0.0: pure hill-climbing (what currently exists).
    At novelty_pressure=1.0: pure novelty (random walk).

    Args:
        archive: EvolutionArchive instance.
        fitness_weights: Per-dimension fitness weights.
        novelty_pressure: 0=exploit-only, 1=explore-only. 0.7 matches DGM defaults.

    Returns:
        Tuple of (selected ArchiveEntry | None, lineage_depth).
    """
    try:
        # Get ALL entries from the archive (not just "best N")
        # This is the DGM pattern: any stepping stone is a valid parent
        entries = list(archive._entries.values()) if hasattr(archive, '_entries') else []
        if not entries:
            return None, 0

        # Count children per entry (for novelty calculation)
        child_counts: dict[str, int] = {}
        for entry in entries:
            parent_id = getattr(entry, 'parent_id', None)
            if parent_id:
                child_counts[parent_id] = child_counts.get(parent_id, 0) + 1

        # Compute quality-diversity weights
        weights: list[float] = []
        for entry in entries:
            fitness_obj = getattr(entry, 'fitness', None)
            if fitness_obj is not None:
                f = fitness_obj.weighted(weights=fitness_weights) if hasattr(fitness_obj, 'weighted') else 0.5
            else:
                f = 0.3  # default for entries without fitness scores

            n_children = child_counts.get(getattr(entry, 'id', ''), 0)
            novelty = 1.0 / (1.0 + n_children)

            # Quality-diversity weight: balance exploitation and exploration
            w = (f ** (1.0 - novelty_pressure)) * (novelty ** novelty_pressure)
            weights.append(max(w, 1e-6))  # never zero — every entry is a valid parent

        total_weight = sum(weights)
        if total_weight <= 0:
            return random.choice(entries), 0

        # Weighted random sample (no replacement needed — one parent per generation)
        r = random.uniform(0, total_weight)
        cumulative = 0.0
        selected = entries[0]
        for entry, w in zip(entries, weights):
            cumulative += w
            if cumulative >= r:
                selected = entry
                break

        # Compute lineage depth
        depth = 0
        current = selected
        while hasattr(current, 'parent_id') and current.parent_id:
            parent = archive._entries.get(current.parent_id)
            if parent is None:
                break
            current = parent
            depth += 1
            if depth > 100:  # safety limit
                break

        return selected, depth

    except Exception as exc:
        logger.warning("QD parent sampling failed, falling back to None: %s", exc)
        return None, 0


def _get_source_file_from_entry(entry: Any, src_root: Path) -> Path | None:
    """Extract the source file from an archive entry for generating the next proposal."""
    # Try entry.component (what file was modified)
    component = getattr(entry, 'component', None)
    if component:
        # component may be a module path like "dharma_swarm.agent_runner" or a file
        if '/' in component or component.endswith('.py'):
            p = src_root / component
            if p.exists():
                return p
        # Try as module name → file
        module_file = component.replace('.', '/').lstrip('dharma_swarm/') + '.py'
        p = src_root / module_file
        if p.exists():
            return p
        # Try direct as filename
        p = src_root / f"{component}.py"
        if p.exists():
            return p
    return None


# ---------------------------------------------------------------------------
# DGM Loop class
# ---------------------------------------------------------------------------

# Source files that are valid evolution targets (in priority order)
# These are the files where improvement has the highest leverage on swarm performance
DGM_TARGET_FILES = [
    "agent_runner.py",         # task execution — most direct impact on completion rate
    "autonomous_agent.py",     # tool use, LLM calls — quality of agent cognition
    "orchestrator.py",         # task routing and lifecycle — affects all agents
    "swarm.py",                # boot, coordination — foundational
    "telos_gates.py",          # constraint enforcement — safety-critical
    "providers.py",            # LLM provider routing — reliability
    "evolution.py",            # self-improvement loop — recursive
    "task_board.py",           # task management — throughput
    "stigmergy.py",            # agent coordination memory
    "thinkodynamic_director.py",  # mission seeding
]

_GAUNTLET_TARGET_RE = re.compile(r"^- `([^`]+)`", re.MULTILINE)


def _tail_lines(path: Path, max_lines: int = 200) -> list[str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []
    return lines[-max_lines:]


def _normalize_component_to_file(component: str | None, src_root: Path) -> str | None:
    if not component:
        return None
    raw = str(component).strip()
    if not raw:
        return None
    candidate = raw.replace("\\", "/")
    if candidate.startswith("dharma_swarm/"):
        candidate = candidate.split("/", 1)[1]
    if candidate.endswith(".py"):
        filename = Path(candidate).name
        return filename if (src_root / filename).exists() else None
    module_file = Path(candidate.replace(".", "/")).name + ".py"
    if (src_root / module_file).exists():
        return module_file
    bare_file = f"{Path(candidate).name}.py"
    if (src_root / bare_file).exists():
        return bare_file
    return None


def _latest_gauntlet_targets(state_dir: Path, src_root: Path) -> list[str]:
    latest = state_dir / "gauntlet" / "LATEST_DELTA.md"
    if not latest.exists():
        return []
    try:
        text = latest.read_text(encoding="utf-8")
    except Exception:
        return []
    targets: list[str] = []
    for match in _GAUNTLET_TARGET_RE.finditer(text):
        normalized = _normalize_component_to_file(match.group(1), src_root)
        if normalized:
            targets.append(normalized)
    return list(dict.fromkeys(targets))


def _recent_archive_component_stats(state_dir: Path, src_root: Path, max_lines: int = 160) -> dict[str, Counter]:
    archive_path = state_dir / "evolution" / "archive.jsonl"
    counters = {
        "failure_hotspots": Counter(),
        "recent_pressure": Counter(),
        "applied_success": Counter(),
    }
    for line in _tail_lines(archive_path, max_lines=max_lines):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except Exception:
            continue
        component = _normalize_component_to_file(entry.get("component"), src_root)
        if not component:
            continue
        counters["recent_pressure"][component] += 1
        status = str(entry.get("status", "") or "").strip().lower()
        description = str(entry.get("description", "") or "")
        test_results = entry.get("test_results", {}) or {}
        correctness = float(((entry.get("fitness") or {}).get("correctness")) or 0.0)
        if status == "applied" and correctness > 0:
            counters["applied_success"][component] += 1
        systematic_issue = "systematic test issue" in description.lower()
        test_failed = bool(test_results) and int(test_results.get("exit_code", 0) or 0) != 0
        if systematic_issue or test_failed or correctness <= 0:
            counters["failure_hotspots"][component] += 1
    return counters


def _build_target_scores(state_dir: Path, src_root: Path) -> dict[str, float]:
    available_targets = [t for t in DGM_TARGET_FILES if (src_root / t).exists()]
    scores: dict[str, float] = {
        target: float(len(available_targets) - idx)
        for idx, target in enumerate(available_targets)
    }
    stats = _recent_archive_component_stats(state_dir, src_root)
    for target in _latest_gauntlet_targets(state_dir, src_root):
        scores[target] = scores.get(target, 0.0) + 12.0
    for target, count in stats["failure_hotspots"].items():
        scores[target] = scores.get(target, 0.0) + min(12.0, count * 2.5)
    for target, count in stats["applied_success"].items():
        scores[target] = scores.get(target, 0.0) + min(3.0, count * 0.5)
    gauntlet_targets = set(_latest_gauntlet_targets(state_dir, src_root))
    total_recent = sum(stats["recent_pressure"].values())
    for target, count in stats["recent_pressure"].items():
        if count > 2:
            scores[target] = max(0.5, scores.get(target, 0.0) - min(6.0, (count - 2) * 1.5))
        if total_recent > 0:
            share = count / total_recent
            if share >= 0.25 and target not in gauntlet_targets:
                scores[target] = max(0.25, scores.get(target, 0.0) * 0.25)
            elif share >= 0.18 and target not in gauntlet_targets:
                scores[target] = max(0.5, scores.get(target, 0.0) * 0.45)
    return scores


def _compose_live_fitness_context(
    state_dir: Path,
    src_root: Path,
    source_file: str,
    fitness_context: str,
) -> str:
    parts: list[str] = []
    if fitness_context:
        parts.append(fitness_context)
    gauntlet_targets = [t for t in _latest_gauntlet_targets(state_dir, src_root) if t != source_file]
    if gauntlet_targets:
        parts.append(
            "Latest gauntlet pressure signals: "
            + ", ".join(gauntlet_targets[:3])
            + " are currently the top failing or targeted seams."
        )
    stats = _recent_archive_component_stats(state_dir, src_root)
    hotspot_count = stats["failure_hotspots"].get(source_file, 0)
    if hotspot_count > 0:
        parts.append(
            f"Recent archive evidence: {source_file} appears in {hotspot_count} recent failing or systematic issue entries."
        )
    recent_pressure = stats["recent_pressure"].get(source_file, 0)
    if recent_pressure > 3:
        parts.append(
            f"Exploration note: {source_file} has already been touched {recent_pressure} times recently, so any change should be high-signal rather than cosmetic."
        )
    return " | ".join(part for part in parts if part)


class DGMLoop:
    """Open-ended DGM evolution loop with telos-gated self-modification.

    Wraps the existing DarwinEngine.auto_evolve() with:
    1. Quality-diversity parent sampling (open-ended archive, not hill-climbing)
    2. Swarm-specific fitness context (task completion rate, dharmic alignment)
    3. Telos gate enforcement (no dharmic-constraint-violating modifications)
    4. Full lineage tracking in the archive

    Args:
        engine: DarwinEngine instance.
        state_dir: DHARMA state directory (~/.dharma).
        novelty_pressure: 0.0=exploit, 1.0=explore. 0.7 matches Sakana DGM.
        shadow_mode: If True, propose but don't apply diffs. Env var override.
    """

    def __init__(
        self,
        engine: Any,
        state_dir: Path | None = None,
        novelty_pressure: float = 0.7,
        shadow_mode: bool | None = None,
    ) -> None:
        self._engine = engine
        self._state_dir = state_dir or Path.home() / ".dharma"
        self._novelty_pressure = novelty_pressure

        import os
        if shadow_mode is None:
            # Default: shadow ON unless explicitly disabled AND autonomy >= 2
            env_shadow = os.environ.get("DHARMA_EVOLUTION_SHADOW", "1")
            autonomy = int(os.environ.get("DGC_AUTONOMY_LEVEL", "1"))
            self._shadow_mode = not (env_shadow == "0" and autonomy >= 2)
        else:
            self._shadow_mode = shadow_mode

        self._src_root = Path(__file__).resolve().parent
        self._target_scores = _build_target_scores(self._state_dir, self._src_root)

    async def run_one_generation(
        self,
        source_file: Path | str | None = None,
        fitness_context: str = "",
        timeout: float = 90.0,
    ) -> DGMResult:
        """Run one DGM generation: sample parent → propose → gate → apply → benchmark → archive.

        Args:
            source_file: Which file to evolve. If None, sample from archive or use default.
            fitness_context: Human-readable context for the fitness function
                (e.g. "last 10 tasks: 7 completed, 3 timed out — optimize retry logic").
            timeout: Sandbox test timeout in seconds.

        Returns:
            DGMResult with full lineage, fitness delta, and application status.
        """
        start = time.monotonic()
        result = DGMResult(shadow_mode=self._shadow_mode)

        archive = getattr(self._engine, 'archive', None)
        archive_size_before = len(archive._entries) if archive and hasattr(archive, '_entries') else 0
        result.archive_size_before = archive_size_before

        # Step 1: Sample a parent from the archive using quality-diversity
        parent_entry = None
        lineage_depth = 0
        if archive and archive_size_before > 0:
            parent_entry, lineage_depth = await _sample_parent_qd(
                archive,
                fitness_weights=getattr(self._engine, '_fitness_weights', None),
                novelty_pressure=self._novelty_pressure,
            )
        result.parent_id = getattr(parent_entry, 'id', None)
        result.lineage_depth = lineage_depth
        result.fitness_before = (
            parent_entry.fitness.weighted() if parent_entry and hasattr(parent_entry, 'fitness')
            and hasattr(parent_entry.fitness, 'weighted') else 0.0
        )

        # Step 2: Determine source file to evolve
        # Priority: explicit arg > parent's component > quality-diversity selection
        self._target_scores = _build_target_scores(self._state_dir, self._src_root)
        if source_file is None and parent_entry is not None:
            source_file = _get_source_file_from_entry(parent_entry, self._src_root)

        if source_file is None:
            available_targets = [
                target for target in DGM_TARGET_FILES
                if (self._src_root / target).exists()
            ]
            weighted_targets = available_targets or DGM_TARGET_FILES
            weights = [max(0.5, self._target_scores.get(target, 1.0)) for target in weighted_targets]
            source_file = random.choices(weighted_targets, weights=weights, k=1)[0]
            result.selection_strategy = "evidence_weighted"

        source_path = Path(source_file) if not isinstance(source_file, Path) else source_file
        if not source_path.is_absolute():
            source_path = self._src_root / source_path

        if not source_path.exists():
            result.error = f"Source file not found: {source_path}"
            result.duration_seconds = time.monotonic() - start
            return result

        result.source_file = source_path.name

        # Step 3: Build fitness context string
        full_context = self._build_fitness_context(
            parent_entry=parent_entry,
            lineage_depth=lineage_depth,
            fitness_context=_compose_live_fitness_context(
                self._state_dir,
                self._src_root,
                source_path.name,
                fitness_context,
            ),
        )

        # Step 4: Run auto_evolve with the selected source file and parent context
        try:
            from dharma_swarm.providers import OpenRouterProvider, create_default_router
            import os as _os

            provider = None
            if _os.environ.get("OPENROUTER_API_KEY"):
                provider = OpenRouterProvider()

            router = create_default_router()

            if provider is None:
                result.error = "No LLM provider available (set OPENROUTER_API_KEY)"
                result.duration_seconds = time.monotonic() - start
                return result

            async def _run_auto_evolve(run_context: str, run_timeout: float) -> Any:
                return await self._engine.auto_evolve(
                    provider=provider,
                    source_files=[source_path],
                    model="",
                    shadow=self._shadow_mode,
                    timeout=max(10.0, run_timeout),
                    context=run_context,
                    router=router,
                )

            evo_result = await _run_auto_evolve(full_context, timeout)

            if (
                not self._shadow_mode
                and evo_result.proposals_submitted == 0
                and (time.monotonic() - start) < timeout
            ):
                retry_context = (
                    full_context
                    + " | Mutation required: do not return no-op. "
                    + "Propose one minimal, safe, reversible code change that improves correctness "
                    + "under the stated stigmergy failure mode. Prefer the smallest diff that can be tested."
                )
                remaining = timeout - (time.monotonic() - start)
                if remaining > 10.0:
                    logger.info(
                        "DGM received no-op for %s — retrying direct proposal with mutation-required context",
                        source_path.name,
                    )
                    direct_model = (
                        _os.environ.get("DGM_FORCE_MODEL", "").strip()
                        or "qwen/qwen3-coder:free"
                    )
                    proposal = await self._engine.generate_proposal(
                        provider=provider,
                        source_file=source_path,
                        context=retry_context,
                        model=direct_model,
                    )
                    if proposal is not None:
                        evo_result = await self._engine.run_cycle_with_sandbox(
                            [proposal],
                            timeout=max(10.0, remaining),
                        )

            result.proposals_submitted = evo_result.proposals_submitted
            result.proposals_gated = evo_result.proposals_gated
            result.fitness_after = evo_result.best_fitness
            result.fitness_delta = result.fitness_after - result.fitness_before

            # Find the new archive entry (the child)
            archive_size_after = len(archive._entries) if archive and hasattr(archive, '_entries') else 0
            result.archive_size_after = archive_size_after

            if archive_size_after > archive_size_before:
                # New entry was archived — find it
                all_entries = list(archive._entries.values()) if hasattr(archive, '_entries') else []
                new_entries = [
                    e for e in all_entries
                    if getattr(e, 'parent_id', None) == result.parent_id
                    and e.id not in {getattr(pe, 'id', '') for pe in [parent_entry] if pe}
                ]
                if new_entries:
                    # Pick the most recent
                    child = max(new_entries, key=lambda e: getattr(e, 'timestamp', ''))
                    result.child_id = child.id
                    result.applied = getattr(child, 'status', '') == 'applied'
                    result.rolled_back = getattr(child, 'status', '') == 'rolled_back'

            logger.info("DGM generation complete: %s", result.summary())

        except Exception as exc:
            result.error = str(exc)
            logger.error("DGM generation failed: %s", exc, exc_info=True)

        result.duration_seconds = time.monotonic() - start
        return result

    def _build_fitness_context(
        self,
        parent_entry: Any | None,
        lineage_depth: int,
        fitness_context: str,
    ) -> str:
        """Build a rich fitness context string for the LLM proposal generator."""
        parts: list[str] = []

        if parent_entry is not None:
            fitness = getattr(parent_entry, 'fitness', None)
            if fitness:
                parts.append(
                    f"Evolving from parent archive entry (depth={lineage_depth}). "
                    f"Parent fitness: correctness={getattr(fitness, 'correctness', 0):.2f}, "
                    f"dharmic_alignment={getattr(fitness, 'dharmic_alignment', 0):.2f}, "
                    f"performance={getattr(fitness, 'performance', 0):.2f}. "
                    f"Goal: improve on ALL dimensions, not just test pass rate."
                )
            test_results = getattr(parent_entry, 'test_results', {})
            if test_results:
                parts.append(f"Parent test results: {test_results}")
        else:
            parts.append("First generation — no parent in archive. Propose foundational improvements.")

        if fitness_context:
            parts.append(f"Swarm operational context: {fitness_context}")

        parts.append(
            "TELOS CONSTRAINT: Any proposed modification must pass all 11 Telos Gates. "
            "Do NOT propose changes that: remove safety checks, bypass dharmic constraints, "
            "increase self-preservation behavior at cost of telos alignment, or optimize "
            "benchmark scores by gaming metrics rather than genuine improvement."
        )

        return " | ".join(parts)

    async def run_continuous(
        self,
        n_generations: int = 80,
        source_files: list[str] | None = None,
        fitness_context_fn: Any | None = None,
        timeout_per_generation: float = 90.0,
        cooldown_seconds: float = 10.0,
    ) -> list[DGMResult]:
        """Run N DGM generations continuously (mirrors Sakana's 80-iteration default).

        Args:
            n_generations: How many generations to run (Sakana default: 80).
            source_files: If provided, cycle through these files. If None, use archive sampling.
            fitness_context_fn: Optional async callable that returns a fitness context string.
            timeout_per_generation: Max seconds per generation's sandbox test.
            cooldown_seconds: Seconds to pause between generations.

        Returns:
            List of DGMResult, one per generation.
        """
        results: list[DGMResult] = []
        logger.info(
            "DGM continuous run: %d generations, shadow=%s, novelty_pressure=%.2f",
            n_generations, self._shadow_mode, self._novelty_pressure,
        )

        for gen in range(n_generations):
            # Pick source file: cycle through provided list or use archive sampling
            source_file = None
            if source_files:
                source_file = source_files[gen % len(source_files)]

            fitness_context = ""
            if fitness_context_fn is not None:
                try:
                    fitness_context = await fitness_context_fn()
                except Exception:
                    pass

            logger.info("DGM generation %d/%d", gen + 1, n_generations)
            result = await self.run_one_generation(
                source_file=source_file,
                fitness_context=fitness_context,
                timeout=timeout_per_generation,
            )
            results.append(result)

            # Log progress
            if result.error:
                logger.warning("Gen %d failed: %s", gen + 1, result.error)
            else:
                logger.info("Gen %d: %s", gen + 1, result.summary())

            if cooldown_seconds > 0:
                await asyncio.sleep(cooldown_seconds)

        # Summary statistics
        applied = sum(1 for r in results if r.applied)
        rolled_back = sum(1 for r in results if r.rolled_back)
        fitness_deltas = [r.fitness_delta for r in results if r.fitness_after > 0]
        avg_delta = sum(fitness_deltas) / len(fitness_deltas) if fitness_deltas else 0.0

        logger.info(
            "DGM run complete: %d gens, %d applied, %d rolled_back, avg_fitness_delta=%.3f",
            len(results), applied, rolled_back, avg_delta,
        )
        return results


# ---------------------------------------------------------------------------
# Agent-callable task interface
# ---------------------------------------------------------------------------

async def run_dgm_evolution_task(
    source_file: str | None = None,
    fitness_context: str = "",
    n_generations: int = 1,
    shadow: bool | None = None,
    state_dir: Path | None = None,
) -> dict[str, Any]:
    """Entry point for autonomous agents calling the DGM loop as a tool.

    Agents call this when they want to trigger a real evolution cycle.
    This is the bridge between the task system and the DarwinEngine.

    Args:
        source_file: Which file to evolve (agent_runner.py, etc.). None = auto-select.
        fitness_context: What operational context to guide the evolution
            (e.g. "tasks are timing out on provider calls — improve retry logic").
        n_generations: How many generations to run (1 = quick, 80 = full DGM run).
        shadow: True=dry-run, False=real mutation. None=use environment defaults.
        state_dir: DHARMA state directory.

    Returns:
        Dict with results, summary, and lineage information.
    """
    state_dir = state_dir or Path.home() / ".dharma"

    # Load the DarwinEngine from the running swarm
    try:
        from dharma_swarm.evolution import DarwinEngine
        from dharma_swarm.archive import EvolutionArchive

        archive_path = state_dir / "evolution" / "archive.jsonl"
        archive = EvolutionArchive(path=archive_path)
        await archive.load()

        # Build a minimal engine instance for the task
        engine = DarwinEngine(
            archive_path=archive_path,
        )
    except Exception as exc:
        return {
            "success": False,
            "error": f"Failed to initialize DarwinEngine: {exc}",
        }

    loop = DGMLoop(
        engine=engine,
        state_dir=state_dir,
        shadow_mode=shadow,
    )

    if n_generations == 1:
        result = await loop.run_one_generation(
            source_file=source_file,
            fitness_context=fitness_context,
        )
        return {
            "success": result.error is None,
            "summary": result.summary(),
            "parent_id": result.parent_id,
            "child_id": result.child_id,
            "source_file": result.source_file,
            "fitness_delta": result.fitness_delta,
            "applied": result.applied,
            "rolled_back": result.rolled_back,
            "shadow_mode": result.shadow_mode,
            "lineage_depth": result.lineage_depth,
            "archive_growth": result.archive_size_after - result.archive_size_before,
            "error": result.error,
        }
    else:
        results = await loop.run_continuous(
            n_generations=n_generations,
            source_files=[source_file] if source_file else None,
            fitness_context_fn=None,
        )
        applied = sum(1 for r in results if r.applied)
        fitness_deltas = [r.fitness_delta for r in results if r.fitness_after > 0]
        return {
            "success": True,
            "generations_run": len(results),
            "generations_applied": applied,
            "generations_rolled_back": sum(1 for r in results if r.rolled_back),
            "avg_fitness_delta": sum(fitness_deltas) / len(fitness_deltas) if fitness_deltas else 0.0,
            "best_fitness_delta": max(fitness_deltas, default=0.0),
            "archive_growth": (results[-1].archive_size_after - results[0].archive_size_before) if results else 0,
            "shadow_mode": loop._shadow_mode,
        }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

async def _main() -> None:
    import json
    import argparse

    p = argparse.ArgumentParser(description="DHARMA SWARM DGM Loop")
    p.add_argument("--file", help="Source file to evolve")
    p.add_argument("--context", default="", help="Fitness context")
    p.add_argument("--generations", type=int, default=1)
    p.add_argument("--live", action="store_true", help="Real mutation (default: shadow)")
    args = p.parse_args()

    result = await run_dgm_evolution_task(
        source_file=args.file,
        fitness_context=args.context,
        n_generations=args.generations,
        shadow=not args.live,
    )
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(_main())
