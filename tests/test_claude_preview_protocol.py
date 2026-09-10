from __future__ import annotations

import pytest

from dharma_swarm.tui.engine.adapters.claude_preview_protocol import (
    STRICT_DROP_TELEMETRY,
    STRICT_REJECT,
    strict_preview_raw_event_disposition,
)


def _current_rate_limit_event() -> dict[str, object]:
    return {
        "type": "rate_limit_event",
        "rate_limit_info": {
            "status": "allowed",
            "resetsAt": 1_800_000_000,
            "rateLimitType": "default_claude_max_5x",
            "overageStatus": "rejected",
            "overageDisabledReason": "not_enabled",
            "isUsingOverage": False,
            "utilization": 0.25,
            "surpassedThreshold": 0.0,
            "unifiedWindows": {
                "five_hour": {
                    "utilization": 0.25,
                    "resetsAt": 1_800_000_000,
                },
                "seven_day": {
                    "utilization": 0.5,
                    "resetsAt": 1_800_604_800,
                },
            },
        },
        "session_id": "session-1",
        "uuid": "event-1",
    }


def test_current_unified_windows_rate_limit_shape_is_dropped() -> None:
    raw = _current_rate_limit_event()

    assert strict_preview_raw_event_disposition(raw) == STRICT_DROP_TELEMETRY


@pytest.mark.parametrize(
    "unified_windows",
    [
        None,
        [],
        {"five_hour": {"utilization": 0.25, "resetsAt": 1}},
        {
            "five_hour": {"utilization": 0.25, "resetsAt": 1},
            "seven_day": {"utilization": 0.5, "resetsAt": 2},
            "monthly": {"utilization": 0.1, "resetsAt": 3},
        },
        {
            "five_hour": {
                "utilization": 0.25,
                "resetsAt": 1,
                "arbitrary": "nested",
            },
            "seven_day": {"utilization": 0.5, "resetsAt": 2},
        },
        {
            "five_hour": {"utilization": 1.01, "resetsAt": 1},
            "seven_day": {"utilization": 0.5, "resetsAt": 2},
        },
        {
            "five_hour": {"utilization": 0.25, "resetsAt": -1},
            "seven_day": {"utilization": 0.5, "resetsAt": 2},
        },
        {
            "five_hour": {"utilization": 0.25, "resetsAt": 1},
            "seven_day": {"utilization": 0.5, "resetsAt": 10**15 + 1},
        },
    ],
)
def test_malformed_unified_windows_rate_limit_shape_is_rejected(
    unified_windows: object,
) -> None:
    raw = _current_rate_limit_event()
    rate_limit_info = raw["rate_limit_info"]
    assert isinstance(rate_limit_info, dict)
    rate_limit_info["unifiedWindows"] = unified_windows

    assert strict_preview_raw_event_disposition(raw) == STRICT_REJECT
