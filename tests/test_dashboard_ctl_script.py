from __future__ import annotations

from pathlib import Path


def test_dashboard_ctl_avoids_bare_launchctl_kickstart_targets() -> None:
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "dashboard_ctl.sh"
    )
    text = script.read_text(encoding="utf-8")

    assert 'launchctl kickstart -k "${label}"' not in text


def test_dashboard_ctl_checks_live_services_before_restart() -> None:
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "dashboard_ctl.sh"
    )
    text = script.read_text(encoding="utf-8")

    assert "service_is_ready()" in text
    assert 'if service_is_ready "$label"; then' in text


def test_dashboard_ctl_uses_http_health_probes_for_live_services() -> None:
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "dashboard_ctl.sh"
    )
    text = script.read_text(encoding="utf-8")

    assert "/api/health" in text
    assert "http://127.0.0.1:3420/" in text


def test_dashboard_ctl_reconciles_split_port_owners_before_kickstart() -> None:
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "dashboard_ctl.sh"
    )
    text = script.read_text(encoding="utf-8")

    assert "reconcile_service_owner()" in text
    assert 'reconcile_service_owner "$API_LABEL"' in text
    assert 'reconcile_service_owner "$WEB_LABEL"' in text
    assert "process_descends_from()" in text


def test_dashboard_ctl_waits_for_api_and_web_readiness() -> None:
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "dashboard_ctl.sh"
    )
    text = script.read_text(encoding="utf-8")

    assert "wait_for_service_ready()" in text
    assert 'wait_for_service_ready "$API_LABEL" 20 1' in text
    assert 'wait_for_service_ready "$WEB_LABEL" 20 1' in text


def test_dashboard_ctl_reinstalls_when_plists_are_drifted_or_loaded_from_other_repo() -> None:
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "dashboard_ctl.sh"
    )
    text = script.read_text(encoding="utf-8")

    assert "plist_is_current()" in text
    assert "loaded_service_matches_current_plist()" in text
    assert 'bash "$INSTALL_SCRIPT" install' in text
    assert '! loaded_service_matches_current_plist "$API_LABEL" "$API_PLIST"' in text
    assert '! loaded_service_matches_current_plist "$WEB_LABEL" "$WEB_PLIST"' in text


def test_install_dashboard_launch_agents_reports_plist_drift_and_launchctl_path() -> None:
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "install_dashboard_launch_agents.sh"
    )
    text = script.read_text(encoding="utf-8")

    assert "plist_is_current()" in text
    assert 'echo "- ${label}: drifted (${plist})"' in text
    assert 'launchctl_job_field "${label}" "path"' in text
    assert 'launchctl bootout "${LAUNCH_DOMAIN}/${label}"' in text


def test_run_dashboard_ui_rebuilds_when_sources_are_newer_than_build_id() -> None:
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "run_dashboard_ui.sh"
    )
    text = script.read_text(encoding="utf-8")

    assert "dashboard_build_stale()" in text
    assert '.next/BUILD_ID' in text
    assert '-newer "$build_id"' in text
