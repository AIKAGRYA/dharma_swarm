"""Repo-wide governance fitness functions that must hold continuously."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HYGIENE_DIR = REPO_ROOT / "scripts" / "governance" / "hygiene"


def _load_hygiene_module(name: str):
    spec = importlib.util.spec_from_file_location(name, HYGIENE_DIR / f"{name}.py")
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load hygiene module {name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


counters_mod = _load_hygiene_module("ratchet_counters")
ratchet = _load_hygiene_module("ratchet")


@pytest.mark.timeout(60)
def test_repo_quality_ratchet_has_no_regressions() -> None:
    """QL-R1: every tracked quality counter must respect its stored bound.

    A repo-wide AST/quality sweep (~7-8s standalone on this checkout) scales
    with repo size; under the full ``tests/`` collection (14k+ items) its
    wall time crosses ``test-fast``'s blanket 10s budget even though nothing
    regressed (WP-0D suite-context timeout). ``@pytest.mark.slow`` was
    rejected here: both required CI contexts and ``make test`` filter with
    ``-m "not slow"`` (``.github/workflows/tests.yml``, ``Makefile``), so
    that marker would silently drop this ratchet from every automated gate
    instead of fixing its timing. A per-test override keeps it running
    everywhere with headroom proportional to repo growth instead.
    """
    baseline_path = REPO_ROOT / ratchet.BASELINE_PATH
    try:
        baselines = ratchet.load_baselines(baseline_path)
        comparisons = ratchet.compare_all(REPO_ROOT, baselines)
    except counters_mod.BrokenCounter as exc:
        pytest.fail(f"quality ratchet could not measure repo state: {exc}")

    regressions = [comparison for comparison in comparisons if comparison.regressed]
    assert regressions == [], "\n".join(
        (
            "quality ratchet regression(s):",
            *(
                f"{item.name}: baseline={item.baseline} current={item.value} direction={item.direction}"
                for item in regressions
            ),
        )
    )
