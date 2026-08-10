"""Content-addressed identity for evolved candidates.

Identity is the genome content and nothing else: not the harness version, not
the base SHA, not the lineage. The same genome reached twice is the same
candidate (and is never re-graded); everything else is a RECORDED field on the
archive row, never a hash input.
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path
from typing import Any, Iterable

# telos-kernel lives under packages/; same resolution as dharma_swarm/merkle_log.py
_KERNEL_PACKAGE_ROOT = Path(__file__).resolve().parents[2] / "packages" / "telos-kernel"
if _KERNEL_PACKAGE_ROOT.exists() and str(_KERNEL_PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(_KERNEL_PACKAGE_ROOT))

from telos_kernel import canonicalize  # noqa: E402


def content_digest(value: Any) -> str:
    """Full SHA-256 digest of RFC-8785 canonical JSON ``value``.

    Full digests are used in evidence records.  The short public identifiers
    below remain unchanged for compatibility with existing archive rows.
    """
    return hashlib.sha256(canonicalize(value)).hexdigest()


def genome_digest(genome: dict[str, Any]) -> str:
    """Return the full content digest for a raw genome."""
    return content_digest(genome)


def candidate_id(genome: dict[str, Any]) -> str:
    """``cand_`` + sha256(RFC-8785 canonical JSON of the genome)[:16]."""
    return f"cand_{genome_digest(genome)[:16]}"


def phenotype_payload(
    genome: dict[str, Any],
    *,
    executed_fields: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Canonical payload for the genome fields the executor actually honors.

    Raw candidate identity intentionally continues to include every genome
    field.  Phenotype identity is the companion deduplication key callers use
    to close the stochastic-retry loophole created by notes or compost edits.
    Missing v0 fields are filled with the same defaults used by experiments so
    omitted and explicitly-defaulted genes describe the same phenotype.
    """
    if not isinstance(genome, dict):
        raise TypeError("genome must be a dict")

    # Local import avoids making genome validation depend on identity helpers.
    from dharma_swarm.forge_lab.genome_spec import check_genome, merged_with_defaults

    effective = merged_with_defaults(genome)
    if executed_fields is None:
        checked = check_genome(effective)
        if not checked.executable:
            raise ValueError("cannot identify a non-executable phenotype: " + ",".join(checked.reasons))
        fields = checked.executed_fields
    else:
        fields = tuple(str(field) for field in executed_fields)
        if not fields or len(set(fields)) != len(fields):
            raise ValueError("executed_fields must be non-empty and unique")
    return {field: effective.get(field) for field in sorted(fields)}


def phenotype_digest(
    genome: dict[str, Any],
    *,
    executed_fields: Iterable[str] | None = None,
) -> str:
    """Full digest of the executed phenotype."""
    return content_digest(phenotype_payload(genome, executed_fields=executed_fields))


def phenotype_id(
    genome: dict[str, Any],
    *,
    executed_fields: Iterable[str] | None = None,
) -> str:
    """Stable short identity for an executable phenotype."""
    return f"pheno_{phenotype_digest(genome, executed_fields=executed_fields)[:16]}"


def experiment_id(*, category: str, benchmark: str, started_at: str, base_sha: str) -> str:
    """Deterministic, filesystem-safe experiment identifier."""
    stamp = re.sub(r"[^0-9TZ]", "", started_at)[:16]
    bench = re.sub(r"[^a-z0-9]+", "", benchmark.lower())[:24]
    return f"exp_{category}_{bench}_{stamp}_{base_sha[:8]}"


__all__ = [
    "candidate_id",
    "content_digest",
    "experiment_id",
    "genome_digest",
    "phenotype_digest",
    "phenotype_id",
    "phenotype_payload",
]
