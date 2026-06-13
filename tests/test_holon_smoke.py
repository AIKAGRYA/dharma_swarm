"""Regression tests for the live holon smoke script's false-green guards."""

from scripts import holon_smoke


def test_provider_failure_text_is_not_success() -> None:
    assert holon_smoke._looks_like_provider_failure("Credit balance is too low")
    assert holon_smoke._looks_like_provider_failure(
        "You've hit your session limit · resets 4:40am"
    )


def test_in_character_reply_classifier_accepts_holon_identity() -> None:
    reply = (
        "I am opus_composer, a contemplative-engineering orchestrator for "
        "dharma_swarm whose telos is bounded evidence-grounded action."
    )
    assert not holon_smoke._looks_like_provider_failure(reply)
    assert holon_smoke._looks_in_character("opus_composer", reply)


def test_generic_provider_error_is_not_in_character() -> None:
    assert not holon_smoke._looks_in_character(
        "opus_composer",
        "Credit balance is too low",
    )
