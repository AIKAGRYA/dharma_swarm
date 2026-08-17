"""Structural contract for the required license-free Gitleaks workflow."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "gitleaks.yml"
WORKFLOW_TEXT = WORKFLOW_PATH.read_text(encoding="utf-8")
GITLEAKS_VERSION = "8.30.1"
GITLEAKS_LINUX_X64_SHA256 = (
    "551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb"
)
CHECKOUT_SHA = "34e114876b0b11c390a56381ad16ebd13914f8d5"
UPLOAD_ARTIFACT_SHA = "ea165f8d65b6e75b540449e92b4886f43607fa02"


def _workflow(text: str = WORKFLOW_TEXT) -> dict[str, object]:
    parsed = yaml.load(text, Loader=yaml.BaseLoader)
    assert isinstance(parsed, dict)
    return parsed


def _job(text: str = WORKFLOW_TEXT) -> dict[str, object]:
    jobs = _workflow(text)["jobs"]
    assert isinstance(jobs, dict)
    job = jobs["gitleaks"]
    assert isinstance(job, dict)
    return job


def _steps(text: str = WORKFLOW_TEXT) -> dict[str, dict[str, object]]:
    steps = _job(text)["steps"]
    assert isinstance(steps, list)
    result: dict[str, dict[str, object]] = {}
    for step in steps:
        assert isinstance(step, dict)
        name = step.get("name")
        assert isinstance(name, str) and name not in result
        result[name] = step
    return result


def _active_shell(step: dict[str, object]) -> str:
    script = step.get("run")
    assert isinstance(script, str)
    return "\n".join(
        line for line in script.splitlines()
        if not line.lstrip().startswith("#")
    )


def _assert_supply_chain_contract(text: str) -> None:
    job = _job(text)
    assert job["env"] == {
        "GITLEAKS_VERSION": GITLEAKS_VERSION,
        "GITLEAKS_LINUX_X64_SHA256": GITLEAKS_LINUX_X64_SHA256,
    }
    steps = _steps(text)
    install = _active_shell(steps["Install checksum-pinned Gitleaks CLI"])
    assert "curl --fail --show-error --silent --location" in install
    assert "--retry 3 --retry-all-errors" in install
    assert (
        "https://github.com/gitleaks/gitleaks/releases/download/"
        "v${GITLEAKS_VERSION}/${asset}"
    ) in install
    assert "sha256sum --check --strict" in install
    assert '"${install_dir}/gitleaks" version' in install
    assert '>> "${GITHUB_PATH}"' in install


def test_required_check_identity_events_and_permissions() -> None:
    workflow = _workflow()
    assert workflow["name"] == "gitleaks"
    assert workflow["permissions"] == {"contents": "read"}
    triggers = workflow["on"]
    assert isinstance(triggers, dict)
    assert set(triggers) == {
        "push", "pull_request", "merge_group", "workflow_dispatch",
    }
    assert triggers["merge_group"] == {"types": ["checks_requested"]}

    job = _job()
    assert job["name"] == "gitleaks"
    assert job["runs-on"] == "ubuntu-latest"
    assert job["timeout-minutes"] == "10"


def test_cli_install_is_exactly_versioned_and_checksum_pinned() -> None:
    _assert_supply_chain_contract(WORKFLOW_TEXT)
    steps = _steps()
    checkout = steps["Checkout (full history)"]
    assert checkout["uses"] == f"actions/checkout@{CHECKOUT_SHA}"
    assert checkout["with"] == {
        "fetch-depth": "0",
        "persist-credentials": "false",
    }

    assert "gitleaks/gitleaks-action@" not in WORKFLOW_TEXT
    assert "GITLEAKS_LICENSE" not in WORKFLOW_TEXT
    assert "GITHUB_TOKEN" not in WORKFLOW_TEXT
    assert "pull-requests: write" not in WORKFLOW_TEXT
    for step in steps.values():
        uses = step.get("uses")
        if uses is not None:
            assert re.fullmatch(r"[^@]+@[0-9a-f]{40}", str(uses))


def test_checksum_pin_negative_control() -> None:
    mutated = WORKFLOW_TEXT.replace(GITLEAKS_LINUX_X64_SHA256, "0" * 64, 1)
    assert mutated != WORKFLOW_TEXT
    with pytest.raises(AssertionError):
        _assert_supply_chain_contract(mutated)


def test_every_event_selects_an_explicit_fail_closed_revision_range() -> None:
    step = _steps()["Select revision range"]
    assert step["env"] == {
        "EVENT_NAME": "${{ github.event_name }}",
        "PUSH_BEFORE": "${{ github.event.before }}",
        "PUSH_AFTER": "${{ github.event.after }}",
        "PR_BASE_SHA": "${{ github.event.pull_request.base.sha }}",
        "PR_HEAD_SHA": "${{ github.event.pull_request.head.sha }}",
        "MERGE_GROUP_BASE_SHA": "${{ github.event.merge_group.base_sha }}",
        "MERGE_GROUP_HEAD_SHA": "${{ github.event.merge_group.head_sha }}",
    }
    script = _active_shell(step)
    for token in (
        'grep -Eq \'^[0-9a-f]{40}$\'',
        'git cat-file -e "${sha}^{commit}"',
        'select_range "${PUSH_BEFORE}" "${PUSH_AFTER}"',
        'select_range "${PR_BASE_SHA}" "${PR_HEAD_SHA}"',
        'select_range "${MERGE_GROUP_BASE_SHA}" "${MERGE_GROUP_HEAD_SHA}"',
        "--diff-merges=first-parent ${base}..${head}",
        "--full-history --diff-merges=first-parent ${PUSH_AFTER}",
        "--full-history --all --diff-merges=first-parent --diff-filter=tuxdb",
        'printf \'log_opts=%s\\n\' "${log_opts}" >> "${GITHUB_OUTPUT}"',
    ):
        assert token in script
    assert '::error::Unsupported event ${EVENT_NAME}' in script
    assert "exit 2" in script


def test_scan_is_redacted_fail_closed_and_preserves_sarif_evidence() -> None:
    steps = _steps()
    scan = steps["Scan selected revisions"]
    assert scan["env"] == {
        "GITLEAKS_LOG_OPTS": "${{ steps.scan-range.outputs.log_opts }}",
    }
    script = _active_shell(scan)
    for token in (
        "set -euo pipefail",
        "gitleaks git",
        "--config .gitleaks.toml",
        "--redact=100",
        "--verbose",
        "--no-banner",
        "--no-color",
        "--platform github",
        "--exit-code 1",
        "--report-format sarif",
        "--report-path gitleaks-results.sarif",
        '--log-opts="${GITLEAKS_LOG_OPTS}"',
    ):
        assert token in script
    assert "continue-on-error" not in WORKFLOW_TEXT
    assert "|| true" not in script

    upload = steps["Upload redacted Gitleaks SARIF"]
    assert upload["if"] == "${{ always() }}"
    assert upload["uses"] == f"actions/upload-artifact@{UPLOAD_ARTIFACT_SHA}"
    assert upload["with"] == {
        "name": "gitleaks-results-${{ github.run_id }}-${{ github.run_attempt }}",
        "path": "gitleaks-results.sarif",
        "if-no-files-found": "ignore",
        "retention-days": "7",
    }
