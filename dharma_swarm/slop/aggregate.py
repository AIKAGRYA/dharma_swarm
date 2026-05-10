"""Cross-validator: noisy-OR over family scores with agreement cap.

Single-detector findings can WARN but cannot BLOCK. Two or more
detector families must agree (each contributing >= AGREEMENT_THRESHOLD)
before the aggregated probability is allowed past the warn-band cap.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from typing import Mapping

from dharma_swarm.slop.models import (
    DetectorFamily,
    DetectorResult,
    Finding,
    ModuleScore,
)

FAMILY_WEIGHTS: dict[DetectorFamily, float] = {
    DetectorFamily.STRUCTURE: 0.25,
    DetectorFamily.DEAD_CODE: 0.20,
    DetectorFamily.COMPLEXITY: 0.20,
    DetectorFamily.AI_SLOP: 0.20,
    DetectorFamily.PROVENANCE: 0.15,
    DetectorFamily.BEHAVIORAL: 0.10,
    DetectorFamily.ADVERSARIAL: 0.10,
    DetectorFamily.SECURITY: 0.15,
    DetectorFamily.DUPLICATION: 0.15,
    DetectorFamily.TYPE_DRIFT: 0.15,
    DetectorFamily.BOUNDARY: 0.20,
}

AGREEMENT_THRESHOLD = 0.35
WARN_BAND_CAP = 0.49
MIN_AGREEMENT = 2


def family_score(findings: Iterable[Finding]) -> float:
    """Reduce per-family findings to a single 0..1 score.

    Strategy: take the maximum confidence across findings in this family
    for this module. (Multiple findings in the same family are not
    additive — one strong signal is the family's verdict.)
    """
    return max((f.confidence for f in findings), default=0.0)


def aggregate_path(
    path: str,
    findings_for_path: list[Finding],
    weights: Mapping[DetectorFamily, float] = FAMILY_WEIGHTS,
) -> ModuleScore:
    by_family: dict[DetectorFamily, list[Finding]] = defaultdict(list)
    for f in findings_for_path:
        by_family[f.family].append(f)
    family_scores: dict[str, float] = {}
    p_factors: list[float] = []
    agreement = 0
    for fam, fs in by_family.items():
        s = family_score(fs)
        family_scores[fam.value] = round(s, 4)
        if s >= AGREEMENT_THRESHOLD:
            agreement += 1
        w = weights.get(fam, 0.10)
        p_factors.append(1.0 - w * s)
    if not p_factors:
        return ModuleScore(
            path=path,
            p_raw=0.0,
            p=0.0,
            agreement=0,
            family_scores={},
            finding_count=0,
            capped=False,
        )
    p_raw = 1.0
    for factor in p_factors:
        p_raw *= factor
    p_raw = 1.0 - p_raw
    capped = agreement < MIN_AGREEMENT and p_raw > WARN_BAND_CAP
    p = WARN_BAND_CAP if capped else p_raw
    return ModuleScore(
        path=path,
        p_raw=round(p_raw, 4),
        p=round(p, 4),
        agreement=agreement,
        family_scores=family_scores,
        finding_count=len(findings_for_path),
        capped=capped,
    )


def aggregate_results(
    results: Iterable[DetectorResult],
    weights: Mapping[DetectorFamily, float] = FAMILY_WEIGHTS,
) -> dict[str, ModuleScore]:
    by_path: dict[str, list[Finding]] = defaultdict(list)
    for r in results:
        for f in r.findings:
            by_path[f.path].append(f)
    return {path: aggregate_path(path, fs, weights) for path, fs in by_path.items()}


__all__ = [
    "AGREEMENT_THRESHOLD",
    "FAMILY_WEIGHTS",
    "MIN_AGREEMENT",
    "WARN_BAND_CAP",
    "aggregate_path",
    "aggregate_results",
    "family_score",
]
