"""Candidate -> Chetana staged atom adapter (the gated, non-bypass path).

Every IdeaSparkCandidate can become a STAGED (untrusted) Chetana atom via
``chetana.ingest.ingest`` — never a direct write to the trusted tier. The
candidate_id and correlation_id are carried in the atom's frontmatter tags
(Chetana has no native correlation field), so the chain round-trips by
``correlation_id`` through ``graph_unifier.query`` and the lifecycle can re-find
its staged atom.

The atom also carries the sentinel tag ``idea_spark_lifecycle``. The bulk
cron promoter (``scripts/consume_review_marks.py``) refuses any atom bearing
that tag, so lifecycle-governed knowledge can only graduate to trusted through
``chetana.promote`` (telos gate-check + axiom signature + provenance) — closing
the Hermes/cron bypass for this lineage.

Promotion to the trusted tier goes through ``promote_candidate_atom`` which is a
thin wrapper over ``chetana.promote.promote`` — the only sanctioned staged->trusted
path. No raw ``shutil.move``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dharma_swarm.chetana.ingest import ingest
from dharma_swarm.chetana.promote import promote

from .schemas import IdeaSparkCandidate

# Shared contract string. Mirrored as a literal in scripts/consume_review_marks.py
# (which deliberately avoids importing dharma_swarm for cron portability).
IDEA_SPARK_LIFECYCLE_TAG = "idea_spark_lifecycle"


@dataclass(frozen=True)
class StagedCandidate:
    candidate_id: str
    correlation_id: str
    atom_id: str
    path: Path
    tags: list[str]


def lifecycle_tags(candidate: IdeaSparkCandidate) -> list[str]:
    tags = [
        IDEA_SPARK_LIFECYCLE_TAG,
        f"corr:{candidate.correlation_id}",
        f"candidate:{candidate.candidate_id}",
    ]
    if candidate.domain:
        tags.append(f"domain:{candidate.domain}")
    return tags


def _staging_confidence(candidate: IdeaSparkCandidate) -> float:
    raw = candidate.triage.get("triage_score") if candidate.triage else None
    try:
        value = float(raw) if raw is not None else 0.5
    except (TypeError, ValueError):
        value = 0.5
    return max(0.0, min(1.0, value))


def stage_candidate(
    candidate: IdeaSparkCandidate,
    *,
    captured_by: str = "operator",
    source_kind: str = "note",
    body: str | None = None,
    confidence: float | None = None,
) -> StagedCandidate:
    """Ingest a candidate as a STAGED (untrusted) Chetana atom.

    Provenance is absent by construction (Chetana sets it only on promote), so
    this never touches trusted memory. ``source_kind`` defaults to ``note``;
    pass ``synthesis`` for agent-generated content.
    """
    tags = lifecycle_tags(candidate)
    result = ingest(
        source=body if body is not None else candidate.claim,
        source_kind=source_kind,  # type: ignore[arg-type]
        title=candidate.title,
        confidence=confidence if confidence is not None else _staging_confidence(candidate),
        captured_by=captured_by,
        tags=tags,
    )
    if not result.atoms:
        raise RuntimeError(
            f"chetana ingest produced no staged atom for candidate {candidate.candidate_id}: "
            f"{result.notes}"
        )
    path = result.atoms[0]
    return StagedCandidate(
        candidate_id=candidate.candidate_id,
        correlation_id=candidate.correlation_id,
        atom_id=path.stem,
        path=path,
        tags=tags,
    )


def promote_candidate_atom(
    staged_path: Path,
    *,
    promoted_by: str = "idea_spark.lifecycle",
    reviewer: str = "operator",
    auto_promote: bool = False,
    confidence_override: float | None = None,
):
    """Promote a staged candidate atom through the gated Chetana path only."""
    return promote(
        staged_path=staged_path,
        promoted_by=promoted_by,
        reviewer=reviewer,
        auto_promote=auto_promote,
        confidence_override=confidence_override,
    )
