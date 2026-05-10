"""Tests for the Anekanta epistemological gate."""

from dharma_swarm.anekanta_gate import (
    AnekantaResult,
    evaluate_anekanta,
)
from dharma_swarm.models import GateResult


# --- PASS / WARN / FAIL thresholds ---


def test_all_three_frames_pass() -> None:
    text = (
        "Writing this, I notice a felt uncertainty in the claim. "
        "dharma_swarm/telos_gates.py records GateDecisionRecord objects, "
        "and the feedback loop then writes Outcome and ValueEvent records "
        "through TelicSeam."
    )
    result = evaluate_anekanta(text)
    assert result.gate_result == GateResult.PASS
    assert result.frame_count == 3


def test_grounded_plus_tokenistic_frame_warns() -> None:
    text = (
        "The runtime combines kernel verification, telos gates, witness "
        "chains, and ontology types into an integration layer that holds "
        "the contemplative bridge."
    )
    result = evaluate_anekanta(text)
    assert result.gate_result == GateResult.WARN
    assert result.frame_count == 2
    assert "label=mixed" in result.reason


def test_one_frame_fail() -> None:
    text = "The mechanism architecture optimization substrate is robust."
    result = evaluate_anekanta(text)
    assert result.gate_result == GateResult.FAIL
    assert result.frame_count == 1


def test_zero_frames_fail() -> None:
    text = "The quick brown fox jumps over the lazy dog."
    result = evaluate_anekanta(text)
    assert result.gate_result == GateResult.FAIL
    assert result.frame_count == 0
    assert result.frames_detected == []


# --- Single-frame isolation ---


def test_mechanistic_only() -> None:
    text = "The circuit and gradient define the architecture."
    result = evaluate_anekanta(text)
    assert result.gate_result == GateResult.FAIL
    assert result.frames_detected == ["mechanistic"]


def test_phenomenological_only_can_pass_when_grounded() -> None:
    text = "Right now, I notice a felt uncertainty while writing this."
    result = evaluate_anekanta(text)
    assert result.gate_result == GateResult.PASS
    assert result.frames_detected == ["phenomenological"]


def test_systems_only_can_pass_when_grounded() -> None:
    text = "The signal flows through the network and then updates routing."
    result = evaluate_anekanta(text)
    assert result.gate_result == GateResult.PASS
    assert result.frames_detected == ["systems"]


# --- Detected list correctness ---


def test_frames_detected_list() -> None:
    text = (
        "The layer activation mechanism. "
        "Emergence and feedback loops."
    )
    result = evaluate_anekanta(text)
    assert set(result.frames_detected) == {"mechanistic", "systems"}
    assert "phenomenological" not in result.frames_detected


# --- Case insensitivity ---


def test_case_insensitive() -> None:
    text = "MECHANISM and ACTIVATION in the LAYER"
    result = evaluate_anekanta(text)
    assert "mechanistic" in result.frames_detected


# --- Description + content combination ---


def test_content_combined() -> None:
    desc = "dharma_swarm/telos_gates.py records GateDecisionRecord objects."
    content = "Right now, I notice uncertainty in the phenomenological claim."
    result = evaluate_anekanta(desc, content)
    assert "mechanistic" in result.frames_detected
    assert "phenomenological" in result.frames_detected
    assert result.frame_count >= 2


# --- Count accuracy ---


def test_frame_count_accurate() -> None:
    text = (
        "Gradient weight optimization. "
        "Consciousness awareness. "
        "Emergence feedback resilience."
    )
    result = evaluate_anekanta(text)
    assert result.frame_count == len(result.frames_detected)
    assert result.frame_count == 3


# --- Edge case: empty input ---


def test_empty_input_fails() -> None:
    result = evaluate_anekanta("", "")
    assert result.gate_result == GateResult.FAIL
    assert result.frame_count == 0
    assert result.frames_detected == []
