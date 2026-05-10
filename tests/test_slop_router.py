"""Tests for action router thresholds."""

from __future__ import annotations

from dharma_swarm.slop.models import ModuleScore
from dharma_swarm.slop.router import Action, route_score, severity_summary


def make_score(p: float, path: str = "a.py") -> ModuleScore:
    return ModuleScore(
        path=path,
        p_raw=p,
        p=p,
        agreement=2,
        family_scores={"ai_slop": p},
        finding_count=1,
        capped=False,
    )


class TestRouteScore:
    def test_low_probability_ledger_only(self) -> None:
        assert route_score(make_score(0.0)) == Action.LEDGER_ONLY
        assert route_score(make_score(0.29)) == Action.LEDGER_ONLY

    def test_warn_band(self) -> None:
        assert route_score(make_score(0.30)) == Action.PR_WARNING
        assert route_score(make_score(0.49)) == Action.PR_WARNING

    def test_block_band(self) -> None:
        assert route_score(make_score(0.50)) == Action.BLOCK_ON_REGRESSION
        assert route_score(make_score(0.79)) == Action.BLOCK_ON_REGRESSION

    def test_refactor_band(self) -> None:
        assert route_score(make_score(0.80)) == Action.REFACTOR_PROPOSAL
        assert route_score(make_score(1.00)) == Action.REFACTOR_PROPOSAL

    def test_boundary_exact_30(self) -> None:
        assert route_score(make_score(0.30)) == Action.PR_WARNING

    def test_boundary_exact_50(self) -> None:
        assert route_score(make_score(0.50)) == Action.BLOCK_ON_REGRESSION

    def test_boundary_exact_80(self) -> None:
        assert route_score(make_score(0.80)) == Action.REFACTOR_PROPOSAL


class TestSeveritySummary:
    def test_empty(self) -> None:
        assert all(v == 0 for v in severity_summary([]).values())

    def test_distribution(self) -> None:
        scores = [
            make_score(0.10),
            make_score(0.40),
            make_score(0.40),
            make_score(0.60),
            make_score(0.85),
        ]
        s = severity_summary(scores)
        assert s["ledger_only"] == 1
        assert s["pr_warning"] == 2
        assert s["block_on_regression"] == 1
        assert s["refactor_proposal"] == 1
