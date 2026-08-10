"""Task-clustered uncertainty primitives for paired evaluation."""

from __future__ import annotations

import math
import random
from typing import Any, Iterable, Mapping


def clustered_bootstrap_ci(
    task_differences: Mapping[str, Iterable[float]],
    *,
    samples: int,
    seed: int,
    alpha: float,
    error_type: type[ValueError] = ValueError,
) -> dict[str, Any]:
    if isinstance(samples, bool) or not isinstance(samples, int) or samples <= 0:
        raise error_type("samples must be a positive integer")
    if not 0.0 < float(alpha) < 1.0:
        raise error_type("alpha must be between zero and one")

    cluster_means: list[float] = []
    n_pairs = 0
    for task_id in sorted(task_differences):
        values = tuple(float(value) for value in task_differences[task_id])
        if not values or any(not math.isfinite(value) for value in values):
            raise error_type(f"task {task_id!r} has invalid differences")
        cluster_means.append(sum(values) / len(values))
        n_pairs += len(values)
    n_tasks = len(cluster_means)
    if n_tasks == 0:
        return {
            "n_tasks": 0,
            "n_pairs": 0,
            "mean": 0.0,
            "lower": 0.0,
            "upper": 0.0,
            "p_le_0": 1.0,
            "method": "task_clustered_bootstrap",
        }

    observed = sum(cluster_means) / n_tasks
    rng = random.Random(seed)
    means = [
        sum(cluster_means[rng.randrange(n_tasks)] for _ in range(n_tasks)) / n_tasks
        for _ in range(samples)
    ]
    means.sort()
    lower_index = max(0, min(samples - 1, int((alpha / 2.0) * samples)))
    upper_index = max(0, min(samples - 1, int((1.0 - alpha / 2.0) * samples)))
    return {
        "n_tasks": n_tasks,
        "n_pairs": n_pairs,
        "mean": round(observed, 6),
        "lower": round(means[lower_index], 6),
        "upper": round(means[upper_index], 6),
        "p_le_0": round(sum(mean <= 0.0 for mean in means) / samples, 6),
        "method": "task_clustered_bootstrap",
    }


__all__ = ["clustered_bootstrap_ci"]
