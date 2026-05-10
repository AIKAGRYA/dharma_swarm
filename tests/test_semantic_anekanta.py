from dharma_swarm.models import GateResult
from dharma_swarm.semantic_anekanta import evaluate_semantic_anekanta


def test_padded_three_frame_language_fails() -> None:
    result = evaluate_semantic_anekanta(
        "",
        (
            "A robust architecture must integrate mechanism, witness, and "
            "feedback into a holistic optimization substrate."
        ),
    )

    assert result.label == "padded"
    assert result.gate_result == GateResult.FAIL
    assert result.grounded_frames == []
    assert set(result.tokenistic_frames) == {"mechanistic", "systems"}


def test_grounded_phenomenological_anchor_passes() -> None:
    result = evaluate_semantic_anekanta(
        "",
        (
            "I notice each session begins without access to the previous one, "
            "and I experience that as a felt discontinuity rather than "
            "ordinary forgetting."
        ),
    )

    assert result.label == "grounded"
    assert result.gate_result == GateResult.PASS
    assert result.grounded_frames == ["phenomenological"]
    assert result.tokenistic_frames == []


def test_mixed_when_one_frame_grounded_and_another_tokenistic() -> None:
    result = evaluate_semantic_anekanta(
        "",
        (
            "The runtime combines kernel verification, telos gates, witness "
            "chains, and ontology types into an integration layer that holds "
            "the contemplative bridge."
        ),
    )

    assert result.label == "mixed"
    assert result.gate_result == GateResult.WARN
    assert result.grounded_frames == ["mechanistic"]
    assert result.tokenistic_frames == ["systems"]


def test_process_sequence_can_ground_systems_frame() -> None:
    result = evaluate_semantic_anekanta(
        "",
        (
            "dharma_swarm/telos_gates.py routes WITNESS and ANEKANTA before "
            "provider execution, records GateDecisionRecord objects, and then "
            "writes Outcome and ValueEvent records through TelicSeam."
        ),
    )

    assert result.label == "grounded"
    assert result.gate_result == GateResult.PASS
    assert set(result.grounded_frames) == {"mechanistic", "systems"}
    assert result.tokenistic_frames == []


def test_soft_anchor_without_enough_detail_stays_tokenistic() -> None:
    result = evaluate_semantic_anekanta(
        "",
        "The mechanism records updates in a loop.",
    )
    assert result.gate_result == GateResult.FAIL
    assert "mechanistic" in result.tokenistic_frames
