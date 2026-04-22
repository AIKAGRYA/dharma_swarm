from __future__ import annotations

from pathlib import Path


def test_start_review_readiness_night_wires_baseline_and_final_probes() -> None:
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "start_review_readiness_night.sh"
    )
    text = script.read_text(encoding="utf-8")

    assert "review_readiness_probe.py" in text
    assert "--phase baseline" in text
    assert "--phase final" in text
    assert "final_probe.pid" in text
    assert 'DEFAULT_REPO_PYTHON="${ROOT}/.venv/bin/python"' in text
    assert 'run_optional baseline_probe "${PYTHON_BIN}" scripts/review_readiness_probe.py' in text


def test_start_review_readiness_night_uses_codex_verification_and_caffeine_lanes() -> None:
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "start_review_readiness_night.sh"
    )
    text = script.read_text(encoding="utf-8")

    assert "start_codex_overnight_tmux.sh" in text
    assert "start_verification_lane.sh" in text
    assert "start_caffeine_tmux.sh" in text
    assert "REVIEW_READINESS_NIGHT_2026-04-22.md" in text


def test_codex_and_verification_lanes_prefer_repo_python() -> None:
    root = Path(__file__).resolve().parents[1]
    codex_text = (root / "scripts" / "start_codex_overnight_tmux.sh").read_text(encoding="utf-8")
    verify_text = (root / "scripts" / "start_verification_lane.sh").read_text(encoding="utf-8")

    assert 'DEFAULT_REPO_PYTHON="${ROOT}/.venv/bin/python"' in codex_text
    assert "scripts/codex_overnight_autopilot.py" in codex_text
    assert 'DEFAULT_REPO_PYTHON="${ROOT}/.venv/bin/python"' in verify_text
    assert '"${PYTHON_BIN}" - "$ROOT"' in verify_text


def test_status_review_readiness_night_surfaces_runtime_and_probe_state() -> None:
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "status_review_readiness_night.sh"
    )
    text = script.read_text(encoding="utf-8")

    assert "dashboard_ctl.sh" in text
    assert "status_codex_overnight_tmux.sh" in text
    assert "status_caffeine_tmux.sh" in text
    assert "Latest Probes" in text


def test_stop_review_readiness_night_stops_scheduler_and_tmux_lanes() -> None:
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "stop_review_readiness_night.sh"
    )
    text = script.read_text(encoding="utf-8")

    assert "stop_codex_overnight_tmux.sh" in text
    assert "stop_verification_lane.sh" in text
    assert "stop_caffeine_tmux.sh" in text
    assert "final_probe.pid" in text
