"""Contract test for the Thinkodynamic Director remix exemplar (v0.0.0.1).

This is the validation evidence for the remix. It proves three things:

1. BEHAVIOUR PRESERVED — driving the world through the remix's narrow public
   surface yields the same signals/opportunities/plan the original engine
   produces directly (Strangler-Fig: no behaviour drift).
2. FITNESS HOLDS — the embedded fitness functions (Ford/Parsons) pass, and the
   constructor refuses to build in strict mode if they ever stop passing.
3. FAIL-CLOSED — the DirectorOutcome envelope reports failure (witnessed, never
   silent) instead of leaking exceptions or returning a bare None, and
   invariant breaches raise InvariantViolation.

The remix lives in dharma_swarm/_remix and is imported by nothing in production;
this test is its only consumer.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from dharma_swarm._remix.thinkodynamic_director_remix_v0_0_0_1 import (
    DirectorOutcome,
    InvariantViolation,
    ThinkodynamicDirectorRemix,
    _REQUIRED_SEAMS,
)
from dharma_swarm.thinkodynamic_director import ThinkodynamicDirector


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _build_engine(tmp_path: Path) -> ThinkodynamicDirector:
    """Mirror tests/test_thinkodynamic_director.py::director so the contract is
    validated against the same fixture the original characterization tests use."""
    repo_root = tmp_path / "repo"
    state_dir = tmp_path / ".dharma"
    _write(
        repo_root / "docs" / "reports" / "VISION.md",
        "# World Impact Autonomy\n\n"
        "Thinkodynamic director for swarm workflow delegate task board world impact.\n"
        "Research packet, deployment, product, revenue, and validation.\n",
    )
    _write(
        repo_root / "dharma_swarm" / "runtime.py",
        "def run():\n"
        "    # TODO: delegate workflow and validate runtime health\n"
        "    return 'swarm autonomy'\n",
    )
    _write(repo_root / "tests" / "test_runtime.py", "def test_runtime():\n    assert True\n")
    return ThinkodynamicDirector(
        repo_root=repo_root,
        state_dir=state_dir,
        scan_roots=("docs", "dharma_swarm", "tests"),
        external_roots=(),
        mission_brief=(
            "Find the highest-leverage workflow for autonomy, world impact, "
            "revenue, and delegation."
        ),
        signal_limit=8,
        max_candidates=24,
        max_active_tasks=8,
    )


@pytest.fixture
def engine(tmp_path: Path) -> ThinkodynamicDirector:
    return _build_engine(tmp_path)


@pytest.fixture
def remix(engine: ThinkodynamicDirector) -> ThinkodynamicDirectorRemix:
    # strict=True ⇒ the constructor itself runs self_audit and fails closed.
    return ThinkodynamicDirectorRemix(engine=engine, strict=True)


# --- 1. behaviour preserved -------------------------------------------------
def test_survey_matches_engine_signals_and_opportunities(
    engine: ThinkodynamicDirector,
    remix: ThinkodynamicDirectorRemix,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("dharma_swarm.thinkodynamic_director.time.time", lambda: 1782922342.0)

    direct_signals = engine.rank_file_signals()
    direct_opps = engine.build_opportunities(direct_signals)

    outcome = remix.survey()
    assert outcome.ok, outcome.error
    survey = outcome.unwrap()

    assert [s.path for s in survey.signals] == [s.path for s in direct_signals]
    assert [o.opportunity_id for o in survey.opportunities] == [
        o.opportunity_id for o in direct_opps
    ]
    if direct_opps:
        assert survey.primary is not None
        assert survey.primary.score == max(o.score for o in direct_opps)


def test_seams_delegate_to_the_proven_engine(
    engine: ThinkodynamicDirector,
    remix: ThinkodynamicDirectorRemix,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("dharma_swarm.thinkodynamic_director.time.time", lambda: 1782922342.0)

    # Feathers: the capability views are the engine, exposed through narrow protocols.
    signals_via_seam = remix.signals.rank_file_signals()
    assert [s.path for s in signals_via_seam] == [s.path for s in engine.rank_file_signals()]
    opps_via_seam = remix.opportunities.build_opportunities(signals_via_seam)
    assert [o.opportunity_id for o in opps_via_seam] == [
        o.opportunity_id for o in engine.build_opportunities(engine.rank_file_signals())
    ]
    assert isinstance(remix.sensor.sense(), dict)


# --- 2. fitness holds -------------------------------------------------------
def test_self_audit_passes(remix: ThinkodynamicDirectorRemix) -> None:
    report = remix.self_audit()
    assert report.passed, [c.detail for c in report.failures]
    names = {c.name for c in report.checks}
    assert {
        "interface_budget",
        "seam_integrity",
        "no_silent_swallow",
        "invariants_hold",
        "swarm_decoupled",
    } <= names


def test_public_interface_stays_narrow(remix: ThinkodynamicDirectorRemix) -> None:
    public = [n for n in dir(type(remix)) if not n.startswith("_")]
    assert len(public) <= ThinkodynamicDirectorRemix.PUBLIC_INTERFACE_BUDGET, public


def test_engine_satisfies_every_required_seam(engine: ThinkodynamicDirector) -> None:
    for seam in _REQUIRED_SEAMS:
        assert isinstance(engine, seam), seam.__name__


# --- 3. fail-closed ---------------------------------------------------------
def test_strict_construction_refuses_engine_missing_seams() -> None:
    class NotADirector:
        """Missing every capability seam."""

    with pytest.raises(InvariantViolation):
        ThinkodynamicDirectorRemix(engine=NotADirector(), strict=True)  # type: ignore[arg-type]


def test_outcome_failure_is_witnessed_not_silent(remix: ThinkodynamicDirectorRemix) -> None:
    boom = RuntimeError("sense exploded")

    def explode() -> dict:
        raise boom

    # Force the deep body to fail; the envelope must report failure + a witness.
    object.__setattr__(remix._engine, "sense", explode)  # type: ignore[attr-defined]
    outcome = remix.survey()
    assert outcome.ok is False
    assert "survey failed" in outcome.error
    assert outcome.witness and outcome.witness[0].error_type == "RuntimeError"
    assert outcome.witness[0].recovered is True


def test_unwrap_fails_closed_on_failure() -> None:
    failed: DirectorOutcome[int] = DirectorOutcome.failure("nope")
    with pytest.raises(InvariantViolation):
        failed.unwrap()


def test_failure_outcome_requires_nonempty_error() -> None:
    with pytest.raises(InvariantViolation):
        DirectorOutcome.failure("")


def test_think_once_wraps_run_cycle_in_outcome(
    remix: ThinkodynamicDirectorRemix, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_run_cycle(*, delegate: bool, model: str) -> dict[str, object]:
        assert delegate is False
        assert model == "sonnet"
        return {"cycle_id": "contract-stub", "delegated": delegate, "model": model}

    monkeypatch.setattr(remix._engine, "run_cycle", fake_run_cycle)

    # The remix contract is the envelope around the engine call; keep this
    # hermetic so fast/no-network CI never invokes live director providers.
    outcome = asyncio.run(remix.think_once(delegate=False))
    assert isinstance(outcome, DirectorOutcome)
    assert outcome.ok, outcome.error
    assert outcome.unwrap()["cycle_id"] == "contract-stub"
