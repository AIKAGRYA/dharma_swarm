from __future__ import annotations

from dharma_swarm.memory_lattice import RetrievalAdmissionPolicy
from dharma_swarm.retrieval.contradiction_detector import detect_contradictions
from dharma_swarm.retrieval.retrieval_effect_logger import citation_handle_for_fact_id


def test_retrieval_policy_defaults_and_strict() -> None:
    default = RetrievalAdmissionPolicy.default()
    strict = RetrievalAdmissionPolicy.strict()

    assert default.min_truth_state == "candidate"
    assert default.min_confidence == 0.0
    assert strict.min_truth_state == "promoted"
    assert strict.min_confidence == 0.6
    assert strict.max_age_days == 90
    assert strict.as_dict()["source_scope"] == []


def test_contradiction_detector_flags_negation_flip() -> None:
    contradictions = detect_contradictions(
        [
            {"id": "a", "text": "The daemon should start archaeology when enabled."},
            {"id": "b", "text": "The daemon should not start archaeology when enabled."},
        ]
    )

    assert len(contradictions) == 1
    assert contradictions[0].reason == "negation_flip"


def test_contradiction_detector_flags_numeric_disagreement() -> None:
    contradictions = detect_contradictions(
        [
            {"id": "a", "text": "The budget limit is 100 USD for the run."},
            {"id": "b", "text": "The budget limit is 300 USD for the run."},
        ]
    )

    assert len(contradictions) == 1
    assert contradictions[0].reason == "numeric_disagreement"


def test_citation_handle_is_stable() -> None:
    handle = citation_handle_for_fact_id("fact-abc")

    assert handle == citation_handle_for_fact_id("fact-abc")
    assert handle.startswith("PR-")
    assert len(handle) == 29
