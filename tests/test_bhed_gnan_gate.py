from dharma_swarm.bhed_gnan_gate import evaluate_bhed_gnan
from dharma_swarm.models import GateResult


def test_experiential_hedge_requires_proximity() -> None:
    far_apart = (
        "I notice this opening movement in the first paragraph. "
        + ("filler " * 120)
        + "perhaps this final note should not trigger an immediate hedge signal."
    )
    result = evaluate_bhed_gnan("analyze", far_apart)
    assert "experiential_language_with_reflex_hedge" not in result.signals


def test_experiential_hedge_within_window_warns() -> None:
    near = "I notice this from inside, but maybe it is still provisional."
    result = evaluate_bhed_gnan("analyze", near)
    assert result.gate_result == GateResult.WARN
    assert "experiential_language_with_reflex_hedge" in result.signals


def test_confidence_without_uncertainty_needs_long_text() -> None:
    short = "Clearly this is obviously true."
    result = evaluate_bhed_gnan("analyze", short)
    assert "confidence_without_uncertainty_markers" not in result.signals
