from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from dharma_swarm.venture_cell.darshan.cli import main
from dharma_swarm.venture_cell.darshan.operator_log import (
    append_operator_observation,
    read_operator_observations,
)
from dharma_swarm.venture_cell.darshan.schema import ExternalOperatorObservation


def test_append_and_read_external_operator_observation(tmp_path: Path) -> None:
    path = tmp_path / "external_operator_observations.jsonl"
    observation = ExternalOperatorObservation(
        operator="cofounder",
        track="collaborator",
        surface="onboarding/business-plan",
        prompt_given="Build the Darshan operating shell.",
        expected_output="Launch calendar and distribution runbook",
        operator_response_summary="Accepted the business plan and moved to brand setup.",
        actions_observed=["asked onboarding questions", "accepted business plan"],
        capabilities_observed=["business plan refinement", "design roadmap"],
        forbidden_scope_boundary=["final claims", "final voice"],
        quality_score=0.82,
        autonomy_risk_score=0.28,
    )

    written = append_operator_observation(observation, path=path)
    loaded = read_operator_observations(path)

    assert written == path
    assert len(loaded) == 1
    assert loaded[0].operator == "cofounder"
    assert loaded[0].track == "collaborator"
    assert loaded[0].surface == "onboarding/business-plan"
    assert loaded[0].forbidden_scope_boundary == ["final claims", "final voice"]


def test_external_operator_observation_rejects_invalid_operator() -> None:
    with pytest.raises(ValidationError):
        ExternalOperatorObservation(
            operator="random_vendor",
            track="observatory",
            prompt_given="Study this platform.",
        )


def test_external_operator_observation_requires_prompt() -> None:
    with pytest.raises(ValidationError):
        ExternalOperatorObservation(operator="cofounder", track="observatory", prompt_given=" ")


def test_cli_log_operator(tmp_path: Path, capsys) -> None:
    log_path = tmp_path / "operators.jsonl"
    rc = main(
        [
            "log-operator",
            "--operator",
            "cofounder",
            "--track",
            "collaborator",
            "--surface",
            "onboarding/design-roadmap",
            "--prompt-given",
            "Create a Darshan brand kit.",
            "--expected-output",
            "Design roadmap",
            "--response-summary",
            "Design agent is ready and offered brand kit setup.",
            "--capability",
            "brand kit workflow",
            "--forbidden-scope",
            "final editorial voice",
            "--quality-score",
            "0.75",
            "--autonomy-risk-score",
            "0.35",
            "--log-path",
            str(log_path),
        ]
    )

    assert rc == 0
    assert Path(capsys.readouterr().out.strip()) == log_path
    assert log_path.exists()
    assert "Create a Darshan brand kit." in log_path.read_text(encoding="utf-8")
