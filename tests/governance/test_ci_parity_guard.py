from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "governance" / "check_ci_parity.py"
MANIFEST = REPO_ROOT / "scripts" / "governance" / "ci_parity_manifest.json"
WORKFLOWS = REPO_ROOT / ".github" / "workflows"


def _load_module():
    spec = importlib.util.spec_from_file_location("check_ci_parity", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


check_ci_parity = _load_module()


def _protection(contexts: list[str]) -> dict:
    return {
        "required_status_checks": {
            "strict": False,
            "contexts": list(contexts),
            "checks": [{"context": c, "app_id": 15368} for c in contexts],
        }
    }


def _manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_manifest_targets_canonical_repository() -> None:
    assert _manifest()["repo"] == "AIKAGRYA/dharma_swarm"


def _run_cli(tmp_path: Path, manifest: dict, protection: dict,
             workflows_dir: Path = WORKFLOWS) -> int:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    prot_path = tmp_path / "protection.json"
    prot_path.write_text(json.dumps(protection), encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--manifest", str(manifest_path),
            "--workflows-dir", str(workflows_dir),
            "--protection-json", str(prot_path),
        ],
        capture_output=True,
        text=True,
    )
    return result.returncode


def test_help_available() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "CI parity guard" in result.stdout


def test_workflow_live_fetch_requires_dedicated_admin_read_secret() -> None:
    workflow = (WORKFLOWS / "ci-parity.yml").read_text(encoding="utf-8")
    secret_binding = "GH_TOKEN: ${{ secrets.CI_PARITY_ADMIN_READ_TOKEN }}"
    assert workflow.count(secret_binding) == 1
    assert "CI_PARITY_ADMIN_READ_TOKEN || github.token" not in workflow
    assert "continue-on-error: true" not in workflow
    assert "CI_PARITY_ADMIN_READ_TOKEN is required" in workflow
    assert "structural-only evidence cannot verify" in workflow
    assert "Run CI parity guard (structural precheck)" in workflow
    assert "Run CI parity guard (structural only)" not in workflow
    assert "steps.fetch.outputs.have_protection" not in workflow

    structural = workflow.index("Run CI parity guard (structural precheck)")
    fetch = workflow.index("Fetch live branch protection")
    live = workflow.index("Run CI parity guard (live)")
    assert structural < fetch < live


def test_aligned_state_is_green(tmp_path: Path) -> None:
    """The committed manifest matched to the real workflows and the actual
    required-context set is aligned -> exit 0."""
    manifest = _manifest()
    actual = [e["context"] for e in manifest["required_contexts"]]
    report = check_ci_parity.run_check(
        manifest, WORKFLOWS, _protection(actual),
    )
    assert report.drift == [], report.drift
    assert report.parity_verified is True
    assert _run_cli(tmp_path, manifest, _protection(actual)) == 0


def test_manifest_drift_away_from_protection_is_red(tmp_path: Path) -> None:
    """Mutating the expected-guard manifest away from actual branch
    protection turns the check RED (core acceptance)."""
    manifest = _manifest()
    actual_contexts = [e["context"] for e in manifest["required_contexts"]]

    # Drop one required context from the manifest while protection still
    # enforces it -> the manifest under-declares -> drift.
    mutated = _manifest()
    mutated["required_contexts"] = mutated["required_contexts"][:-1]
    report = check_ci_parity.run_check(
        mutated, WORKFLOWS, _protection(actual_contexts),
    )
    assert any("PARITY" in d for d in report.drift), report.drift
    assert _run_cli(tmp_path, mutated, _protection(actual_contexts)) == 1


def test_manifest_over_declares_is_red(tmp_path: Path) -> None:
    manifest = _manifest()
    actual_contexts = [e["context"] for e in manifest["required_contexts"]]
    # Protection drops gitleaks; manifest still lists it -> drift.
    shrunk = [c for c in actual_contexts if c != "gitleaks"]
    report = check_ci_parity.run_check(
        manifest, WORKFLOWS, _protection(shrunk),
    )
    assert any("NOT enforced by branch protection" in d for d in report.drift), report.drift
    assert _run_cli(tmp_path, manifest, _protection(shrunk)) == 1


def test_planted_continue_on_error_on_required_context_is_flagged(tmp_path: Path) -> None:
    """A planted job-level continue-on-error on a required context's job is
    flagged as false-green drift (core acceptance)."""
    wf_dir = tmp_path / "workflows"
    wf_dir.mkdir()
    (wf_dir / "gitleaks.yml").write_text(
        "name: gitleaks\n"
        "on:\n"
        "  pull_request:\n"
        "jobs:\n"
        "  gitleaks:\n"
        "    name: gitleaks\n"
        "    runs-on: ubuntu-latest\n"
        "    continue-on-error: true\n"
        "    steps:\n"
        "      - name: Run gitleaks\n"
        "        run: gitleaks detect\n",
        encoding="utf-8",
    )
    manifest = {
        "repo": "x/y",
        "branch": "main",
        "required_contexts": [
            {"context": "gitleaks", "workflow": "gitleaks.yml",
             "job": "gitleaks", "regression_sensitive": False},
        ],
    }
    report = check_ci_parity.run_check(manifest, wf_dir, _protection(["gitleaks"]))
    assert any("continue-on-error" in d and "gitleaks" in d for d in report.drift), report.drift
    assert _run_cli(tmp_path, manifest, _protection(["gitleaks"]), workflows_dir=wf_dir) == 1


def test_regression_sensitive_step_continue_on_error_is_flagged(tmp_path: Path) -> None:
    wf_dir = tmp_path / "workflows"
    wf_dir.mkdir()
    (wf_dir / "tests.yml").write_text(
        "name: tests\n"
        "on:\n"
        "  pull_request:\n"
        "  merge_group:\n"
        "jobs:\n"
        "  pytest:\n"
        "    runs-on: ubuntu-latest\n"
        "    strategy:\n"
        "      matrix:\n"
        "        python-version: [\"3.11\", \"3.12\"]\n"
        "    steps:\n"
        "      - name: Run tests\n"
        "        continue-on-error: true\n"
        "        run: pytest\n",
        encoding="utf-8",
    )
    manifest = {
        "required_contexts": [
            {"context": "pytest (3.11)", "workflow": "tests.yml",
             "job": "pytest", "regression_sensitive": True},
        ],
    }
    report = check_ci_parity.run_check(manifest, wf_dir, _protection(["pytest (3.11)"]))
    assert any("regression-sensitive" in d and "continue-on-error" in d for d in report.drift), report.drift


def test_regression_sensitive_self_skip_on_merge_group_is_flagged(tmp_path: Path) -> None:
    wf_dir = tmp_path / "workflows"
    wf_dir.mkdir()
    (wf_dir / "tests.yml").write_text(
        "name: tests\n"
        "on:\n"
        "  pull_request:\n"
        "  merge_group:\n"
        "jobs:\n"
        "  pytest:\n"
        "    runs-on: ubuntu-latest\n"
        "    if: github.event_name != 'merge_group'\n"
        "    steps:\n"
        "      - name: Run tests\n"
        "        run: pytest\n",
        encoding="utf-8",
    )
    manifest = {
        "required_contexts": [
            {"context": "pytest", "workflow": "tests.yml",
             "job": "pytest", "regression_sensitive": True},
        ],
    }
    report = check_ci_parity.run_check(manifest, wf_dir, _protection(["pytest"]))
    assert any("MERGE-QUEUE-BLIND" in d for d in report.drift), report.drift


def test_non_regression_sensitive_self_skip_is_allowed() -> None:
    """Coherence Delta PR body legitimately self-skips on merge_group and has
    a best-effort continue-on-error step; that must NOT be drift."""
    manifest = {
        "required_contexts": [
            {"context": "Coherence Delta PR body",
             "workflow": "coherence-delta.yml",
             "job": "coherence-delta", "regression_sensitive": False},
        ],
    }
    report = check_ci_parity.run_check(
        manifest, WORKFLOWS, _protection(["Coherence Delta PR body"]),
    )
    assert report.drift == [], report.drift
    assert any("DEAD-TRIGGER" in w for w in report.warnings), report.warnings


def test_job_rename_orphans_required_context(tmp_path: Path) -> None:
    wf_dir = tmp_path / "workflows"
    wf_dir.mkdir()
    (wf_dir / "gitleaks.yml").write_text(
        "name: gitleaks\n"
        "on:\n"
        "  pull_request:\n"
        "jobs:\n"
        "  gitleaks:\n"
        "    name: secret-scan\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - name: Run gitleaks\n"
        "        run: gitleaks detect\n",
        encoding="utf-8",
    )
    manifest = {
        "required_contexts": [
            {"context": "gitleaks", "workflow": "gitleaks.yml",
             "job": "gitleaks", "regression_sensitive": False},
        ],
    }
    report = check_ci_parity.run_check(manifest, wf_dir, _protection(["gitleaks"]))
    assert any("MAPPING" in d and "renders as 'secret-scan'" in d for d in report.drift), report.drift


def test_missing_producing_job_is_drift(tmp_path: Path) -> None:
    wf_dir = tmp_path / "workflows"
    wf_dir.mkdir()
    (wf_dir / "gitleaks.yml").write_text(
        "name: gitleaks\non:\n  pull_request:\njobs:\n  other:\n    name: other\n    steps: []\n",
        encoding="utf-8",
    )
    manifest = {
        "required_contexts": [
            {"context": "gitleaks", "workflow": "gitleaks.yml",
             "job": "gitleaks", "regression_sensitive": False},
        ],
    }
    report = check_ci_parity.run_check(manifest, wf_dir, _protection(["gitleaks"]))
    assert any("does not exist" in d for d in report.drift), report.drift


def test_missing_live_without_allow_is_env_error() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--manifest", str(MANIFEST)],
        capture_output=True, text=True,
    )
    assert result.returncode == 2
    assert "environment error" in result.stderr


def test_allow_missing_live_runs_structural_only() -> None:
    result = subprocess.run(
        [
            sys.executable, str(SCRIPT),
            "--manifest", str(MANIFEST),
            "--workflows-dir", str(WORKFLOWS),
            "--allow-missing-live",
        ],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "NOT" in result.stdout and "verified" in result.stdout


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
