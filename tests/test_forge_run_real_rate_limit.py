from __future__ import annotations

import pytest

from dharma_swarm.forge_v1.run_real import _rate_limit_wait_s


class RateLimitError(Exception):
    pass


@pytest.mark.parametrize(
    "message",
    [
        "Error code: 429 - {'error': {'code': '1113', 'message': "
        "'Insufficient balance or no resource package. Please recharge.'}}",
        "insufficient_quota for this key",
        "Credit balance is too low",
        "Error code: 402 - Insufficient credits",
        "HTTP error 402 Payment Required",
    ],
)
def test_rate_limit_wait_does_not_retry_non_retryable_quota_errors(message: str) -> None:
    assert _rate_limit_wait_s(RateLimitError(message)) is None


def test_rate_limit_wait_still_retries_transient_429_with_hint() -> None:
    assert _rate_limit_wait_s(RateLimitError("HTTP error 429: retry in 2s")) == 3.5


def test_rate_limit_wait_still_retries_resource_exhausted_without_hint() -> None:
    assert _rate_limit_wait_s(Exception("RESOURCE_EXHAUSTED")) == 21.5
