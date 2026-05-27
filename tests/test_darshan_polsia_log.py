from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from dharma_swarm.venture_cell.darshan.polsia_log import (
    append_observation,
    read_observations,
)
from dharma_swarm.venture_cell.darshan.schema import PolsiaObservation


def test_append_and_read_polsia_observation(tmp_path: Path) -> None:
    path = tmp_path / "polsia_observations.jsonl"
    observation = PolsiaObservation(
        track="collaborator",
        prompt_given="Build a Season 0 calendar.",
        expected_output="30-day operating calendar",
        polsia_actions_observed=["created milestones"],
        quality_score=0.8,
    )

    written = append_observation(observation, path=path)
    loaded = read_observations(path)

    assert written == path
    assert len(loaded) == 1
    assert loaded[0].track == "collaborator"
    assert loaded[0].prompt_given == "Build a Season 0 calendar."
    assert loaded[0].quality_score == 0.8


def test_polsia_observation_rejects_invalid_track() -> None:
    with pytest.raises(ValidationError):
        PolsiaObservation(track="publisher", prompt_given="Publish this now.")


def test_polsia_observation_requires_prompt() -> None:
    with pytest.raises(ValidationError):
        PolsiaObservation(track="observatory", prompt_given=" ")
