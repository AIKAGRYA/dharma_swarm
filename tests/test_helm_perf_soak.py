"""Hermetic tests for the Helm P4 performance/soak receipt composer."""

from __future__ import annotations

import importlib.util
import json
import math
import os
from pathlib import Path
import stat
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "verify" / "helm_perf_soak.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("helm_perf_soak", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def harness():
    return _load_module()


def _measurement() -> dict[str, object]:
    return {
        "schema_version": "dharma.helm.perf_soak_measurement.v1",
        "measurement_id": "helm-p4-test",
        "captured_at": "2026-09-02T08:00:00Z",
        "clock": "perf_counter_ns",
        "tmux": {
            "socket": "CODEX_MANAGED_helm_p4_test",
            "session": "helm_p4_test",
        },
        "execution": {
            "offline": True,
            "network_attempted": False,
            "provider_mode": "offline_stub",
        },
        "samples": {
            "boot_ms": [100.0, 120.0],
            "intent_parse_ms": [1.0, 2.0, 3.0],
            "provider_turn_ms": [4.0, 5.0, 6.0],
            "render_ms": [2.0, 3.0, 4.0, 5.0],
        },
        "soak": {
            "duration_ms": 2_500.0,
            "journeys": [
                {
                    "sequence": 1,
                    "ok": True,
                    "rss_bytes": 1_000_000,
                    "fd_count": 10,
                },
                {
                    "sequence": 2,
                    "ok": True,
                    "rss_bytes": 1_500_000,
                    "fd_count": 12,
                },
                {
                    "sequence": 3,
                    "ok": True,
                    "rss_bytes": 1_200_000,
                    "fd_count": 11,
                },
            ],
        },
        "rollback": {
            "steps": [
                {
                    "sequence": 1,
                    "action": "stop",
                    "input_state": "live",
                    "exit_code": 0,
                    "elapsed_ms": 20.0,
                    "observed_state": "stopped",
                },
                {
                    "sequence": 2,
                    "action": "start",
                    "input_state": "stopped",
                    "exit_code": 0,
                    "elapsed_ms": 100.0,
                    "observed_state": "live",
                },
                {
                    "sequence": 3,
                    "action": "replay-valid",
                    "input_state": "live",
                    "exit_code": 0,
                    "elapsed_ms": 5.0,
                    "observed_state": "replay_valid",
                },
            ]
        },
    }


def _baseline() -> dict[str, object]:
    return {
        "schema_version": "dharma.helm.perf_soak_baseline.v1",
        "baseline_id": "helm-legone-locked-plus-p4-local",
        "recorded_at": "2026-09-02T07:59:00Z",
        "source": "HELM_LEGONE_SPEC section 2.5 plus explicit P4 local budgets",
        "limits": {
            "boot_ms_p95": 150.0,
            "intent_parse_ms_p95": 10.0,
            "provider_turn_ms_p95": 2_000.0,
            "render_ms_p95": 10.0,
            "soak_duration_ms": 2_700_000.0,
            "journey_failures": 0,
            "rss_peak_growth_bytes": 10_000_000,
            "fd_peak_growth": 3,
        },
        "require_rollback_success": True,
    }


def test_report_preserves_raw_samples_and_compares_every_metric(harness) -> None:
    measurement = harness.parse_measurement_payload(_measurement())
    baseline = harness.parse_baseline_payload(_baseline())

    report = harness.build_report(measurement=measurement, baseline=baseline)

    assert report["state"] == "PASS"
    assert report["authority"] == "MEASURED_LOCAL_ONLY"
    assert report["provider_truth"] == "OFFLINE_STUB_NOT_LIVE_PROVIDER"
    assert report["raw_measurement"] == _measurement()
    summary = report["summary"]
    assert summary["boot_ms_p95"] == 120.0
    assert summary["render_ms_p95"] == 5.0
    assert summary["rss_peak_growth_bytes"] == 500_000
    assert summary["rss_end_growth_bytes"] == 200_000
    assert summary["fd_peak_growth"] == 2
    assert summary["fd_end_growth"] == 1
    assert summary["journey_failures"] == 0
    assert summary["rollback_success"] is True
    assert {row["metric"] for row in report["comparisons"]} == {
        "boot_ms_p95",
        "intent_parse_ms_p95",
        "provider_turn_ms_p95",
        "render_ms_p95",
        "soak_duration_ms",
        "journey_failures",
        "rss_peak_growth_bytes",
        "fd_peak_growth",
        "rollback_success",
    }
    assert all(row["passed"] for row in report["comparisons"])


def test_regression_and_failed_replay_are_reported_fail_not_relabelled(harness) -> None:
    raw = _measurement()
    raw["samples"]["render_ms"] = [11.0]  # type: ignore[index]
    raw["soak"]["journeys"][1]["ok"] = False  # type: ignore[index]
    raw["rollback"]["steps"][2]["exit_code"] = 1  # type: ignore[index]
    raw["rollback"]["steps"][2]["observed_state"] = "replay_invalid"  # type: ignore[index]

    report = harness.build_report(
        measurement=harness.parse_measurement_payload(raw),
        baseline=harness.parse_baseline_payload(_baseline()),
    )

    assert report["state"] == "FAIL"
    failures = {row["metric"] for row in report["comparisons"] if not row["passed"]}
    assert failures == {"render_ms_p95", "journey_failures", "rollback_success"}
    assert report["summary"]["rollback_success"] is False
    assert report["raw_measurement"]["rollback"]["steps"][2]["exit_code"] == 1


@pytest.mark.parametrize(
    ("socket", "match"),
    [
        # Empty text is refused by the generic one-line-text gate before the
        # socket-shape gate can name CODEX_MANAGED — both are hard rejections.
        ("", "non-empty text"),
        ("default", "CODEX_MANAGED"),
        ("CODEX_MANAGED", "CODEX_MANAGED"),
        ("helm_p4", "CODEX_MANAGED"),
    ],
)
def test_default_or_non_managed_tmux_socket_is_rejected(
    harness, socket: str, match: str
) -> None:
    raw = _measurement()
    raw["tmux"]["socket"] = socket  # type: ignore[index]

    with pytest.raises(harness.HarnessInputError, match=match):
        harness.parse_measurement_payload(raw)


def test_oversized_soak_is_rejected_even_if_baseline_attempts_to_allow_it(harness) -> None:
    baseline = _baseline()
    baseline["limits"]["soak_duration_ms"] = 2_700_001.0  # type: ignore[index]
    with pytest.raises(harness.HarnessInputError, match="45-minute"):
        harness.parse_baseline_payload(baseline)

    raw = _measurement()
    raw["soak"]["duration_ms"] = 2_700_001.0  # type: ignore[index]
    with pytest.raises(harness.HarnessInputError, match="45-minute"):
        harness.parse_measurement_payload(raw)


def test_out_of_order_or_duplicate_journey_sequence_is_rejected(harness) -> None:
    raw = _measurement()
    raw["soak"]["journeys"][1]["sequence"] = 1  # type: ignore[index]

    with pytest.raises(harness.HarnessInputError, match="journey sequence"):
        harness.parse_measurement_payload(raw)


def test_execution_must_be_offline_stub_without_network(harness) -> None:
    for key, value in (
        ("offline", False),
        ("network_attempted", True),
        ("provider_mode", "live"),
    ):
        raw = _measurement()
        raw["execution"][key] = value  # type: ignore[index]
        with pytest.raises(harness.HarnessInputError, match="offline_stub"):
            harness.parse_measurement_payload(raw)


@pytest.mark.parametrize("bad", [math.nan, math.inf, -1.0, True, "1.0"])
def test_samples_reject_nonfinite_negative_boolean_or_text(harness, bad: object) -> None:
    raw = _measurement()
    raw["samples"]["boot_ms"] = [bad]  # type: ignore[index]

    with pytest.raises(harness.HarnessInputError, match="boot_ms"):
        harness.parse_measurement_payload(raw)


def test_schema_is_closed_and_rollback_order_is_exact(harness) -> None:
    extra = _measurement()
    extra["surprise"] = "silently ignored fields make receipts ambiguous"
    with pytest.raises(harness.HarnessInputError, match="unexpected field"):
        harness.parse_measurement_payload(extra)

    reordered = _measurement()
    reordered["rollback"]["steps"].reverse()  # type: ignore[index]
    with pytest.raises(harness.HarnessInputError, match="rollback steps"):
        harness.parse_measurement_payload(reordered)


def test_json_loader_rejects_duplicate_keys_and_nonstandard_constants(
    harness, tmp_path: Path
) -> None:
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"schema_version":"x","schema_version":"y"}', encoding="utf-8")
    with pytest.raises(harness.HarnessInputError, match="duplicate JSON key"):
        harness.load_json(duplicate)

    nan_file = tmp_path / "nan.json"
    nan_file.write_text('{"sample":NaN}', encoding="utf-8")
    with pytest.raises(harness.HarnessInputError, match="non-standard JSON constant"):
        harness.load_json(nan_file)


def test_cli_writes_once_beneath_dharma_with_mode_0600(
    harness, tmp_path: Path, monkeypatch
) -> None:
    fake_home = tmp_path / "home"
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    measurement_path = inputs / "measurement.json"
    baseline_path = inputs / "baseline.json"
    measurement_path.write_text(json.dumps(_measurement()), encoding="utf-8")
    baseline_path.write_text(json.dumps(_baseline()), encoding="utf-8")
    safe_output = fake_home / ".dharma" / "campaign" / "p4.json"
    unsafe_output = tmp_path / "repo" / "p4.json"
    monkeypatch.setattr(harness.Path, "home", classmethod(lambda cls: fake_home))

    assert harness.main(
        [
            "--measurement",
            str(measurement_path),
            "--baseline",
            str(baseline_path),
            "--output",
            str(unsafe_output),
        ]
    ) == 2
    assert not unsafe_output.exists()

    argv = [
        "--measurement",
        str(measurement_path),
        "--baseline",
        str(baseline_path),
        "--output",
        str(safe_output),
    ]
    assert harness.main(argv) == 0
    assert stat.S_IMODE(safe_output.stat().st_mode) == 0o600
    payload = json.loads(safe_output.read_text(encoding="utf-8"))
    assert payload["state"] == "PASS"
    assert harness.main(argv) == 2


def test_output_symlink_is_refused(harness, tmp_path: Path, monkeypatch) -> None:
    if not hasattr(os, "symlink"):
        pytest.skip("symlinks unavailable")
    fake_home = tmp_path / "home"
    output_root = fake_home / ".dharma" / "campaign"
    output_root.mkdir(parents=True)
    target = output_root / "target.json"
    target.write_text("preserve", encoding="utf-8")
    link = output_root / "link.json"
    link.symlink_to(target)
    monkeypatch.setattr(harness.Path, "home", classmethod(lambda cls: fake_home))

    with pytest.raises(harness.HarnessInputError, match="symlink"):
        harness.validate_output_path(link)
    assert target.read_text(encoding="utf-8") == "preserve"
