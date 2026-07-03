"""Tests for dharma_swarm/ginko_cron_loop.py (compose cron entrypoint)."""

from __future__ import annotations

from unittest import mock

from dharma_swarm import ginko_cron_loop


def test_loop_survives_failing_cycles_and_counts_them():
    sleeps: list[float] = []
    with mock.patch.object(
        ginko_cron_loop, "run_cycle", side_effect=RuntimeError("boom")
    ):
        failures = ginko_cron_loop.main(
            max_cycles=3, interval_seconds=0.01, sleep=sleeps.append
        )
    assert failures == 3
    assert sleeps == [0.01, 0.01, 0.01]


def test_loop_resets_failure_count_on_success():
    outcomes = iter([RuntimeError("boom"), {"ok": True}])

    async def fake_cycle():
        result = next(outcomes)
        if isinstance(result, Exception):
            raise result
        return result

    with mock.patch.object(ginko_cron_loop, "run_cycle", fake_cycle):
        failures = ginko_cron_loop.main(
            max_cycles=2, interval_seconds=0, sleep=lambda _: None
        )
    assert failures == 0


def test_module_is_the_compose_cron_entrypoint():
    import yaml
    from pathlib import Path

    compose = yaml.safe_load(
        (Path(__file__).resolve().parents[1] / "docker-compose.yml").read_text()
    )
    assert compose["services"]["cron"]["entrypoint"] == [
        "python3",
        "-m",
        "dharma_swarm.ginko_cron_loop",
    ]
