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
from typing import Any

# telos-kernel lives under packages/; same resolution as dharma_swarm/merkle_log.py
_KERNEL_PACKAGE_ROOT = Path(__file__).resolve().parents[2] / "packages" / "telos-kernel"
if _KERNEL_PACKAGE_ROOT.exists() and str(_KERNEL_PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(_KERNEL_PACKAGE_ROOT))

from telos_kernel import canonicalize  # noqa: E402


def candidate_id(genome: dict[str, Any]) -> str:
    """``cand_`` + sha256(RFC-8785 canonical JSON of the genome)[:16]."""
    digest = hashlib.sha256(canonicalize(genome)).hexdigest()
    return f"cand_{digest[:16]}"


def experiment_id(*, category: str, benchmark: str, started_at: str, base_sha: str) -> str:
    """Deterministic, filesystem-safe experiment identifier."""
    stamp = re.sub(r"[^0-9TZ]", "", started_at)[:16]
    bench = re.sub(r"[^a-z0-9]+", "", benchmark.lower())[:24]
    return f"exp_{category}_{bench}_{stamp}_{base_sha[:8]}"


__all__ = ["candidate_id", "experiment_id"]
