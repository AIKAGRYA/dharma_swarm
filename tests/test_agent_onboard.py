"""Tests for the truthful, compact session-status CLI shim."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
ONBOARD_SCRIPT = REPO_ROOT / "scripts/governance/agent_onboard.py"


@pytest.fixture(autouse=True)
def _isolate_ops_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Every test writes its machine receipt to a tmp dir."""
    monkeypatch.setenv("DHARMA_OPS_DIR", str(tmp_path / "ops"))


def _load_module() -> Any:
    """Import agent_onboard.py without executing main()."""
    spec = importlib.util.spec_from_file_location("agent_onboard", ONBOARD_SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run(
    *args: str,
    ops_dir: Path | None = None,
    env: dict[str, str] | None = None,
    timeout: int = 60,
) -> subprocess.CompletedProcess[str]:
    run_env = dict(env or os.environ)
    if ops_dir is not None:
        run_env["DHARMA_OPS_DIR"] = str(ops_dir)
    run_env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    return subprocess.run(
        [sys.executable, str(ONBOARD_SCRIPT), *args],
        cwd=REPO_ROOT,
        env=run_env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def test_onboard_returns_its_truth_and_delegates_to_compact_cli() -> None:
    """The public command renders compact output and returns its typed truth."""
    truth = json.loads(_run("--json").stdout)
    result = _run()
    assert result.returncode == truth["exit_code"], result.stderr[-400:]
    assert "DHARMA ONBOARD" in result.stdout
    assert "ACTIVE PORTFOLIO" in result.stdout
    assert "LIVING AXIOMS" in result.stdout
    assert "WHAT TO DO NEXT" in result.stdout
    assert "Authority: none" in result.stdout
    assert "NATS SUBSTRATE — LOCAL OBSERVATION ONLY" in result.stdout
    assert "No JetStream ack or live contact is claimed." in result.stdout
    assert truth["nats_substrate"]["spec_path"] == (
        "docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md"
    )
    assert truth["nats_substrate"]["mirrors_are_live_transport_proof"] is False


def test_loader_selects_bootstrap_mode_by_interpreter() -> None:
    """Pre-3.11 skips package init; supported Python keeps the normal import."""

    def probe(*, emulate_pre311: bool) -> dict[str, Any]:
        version_override = """
class _VersionInfo(tuple):
    major = property(lambda self: self[0])
    minor = property(lambda self: self[1])
    micro = property(lambda self: self[2])

sys.version_info = _VersionInfo((3, 9, 0, 'final', 0))
if hasattr(datetime_module, 'UTC'):
    delattr(datetime_module, 'UTC')
if hasattr(enum_module, 'StrEnum'):
    delattr(enum_module, 'StrEnum')
""" if emulate_pre311 else ""
        code = f"""
import datetime as datetime_module
import enum as enum_module
import importlib.util
import json
import sys

spec = importlib.util.spec_from_file_location('agent_onboard_probe', {str(ONBOARD_SCRIPT)!r})
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
{version_override}
cli = module._load_cli_module()
package = sys.modules['dharma_swarm']
print(json.dumps({{
    'cli': cli.__name__,
    'namespace_bootstrap': package.__spec__ is None,
    'operator_core_namespace': sys.modules['dharma_swarm.operator_core'].__spec__ is None,
    'onboarding_namespace': sys.modules['dharma_swarm.operator_core.onboarding'].__spec__ is None,
    'memory_kernel_namespace': sys.modules['dharma_swarm.memory_kernel'].__spec__ is None,
    'package_file': getattr(package, '__file__', None),
    'compat_cleaned': not hasattr(datetime_module, 'UTC') and not hasattr(enum_module, 'StrEnum'),
}}))
"""
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)

    legacy = probe(emulate_pre311=True)
    assert legacy["cli"] == "dharma_swarm.operator_core.onboarding.cli"
    assert legacy["namespace_bootstrap"] is True
    assert legacy["operator_core_namespace"] is True
    assert legacy["onboarding_namespace"] is True
    assert legacy["memory_kernel_namespace"] is True
    assert legacy["package_file"] is None
    assert legacy["compat_cleaned"] is True

    native = probe(emulate_pre311=False)
    assert native["cli"] == "dharma_swarm.operator_core.onboarding.cli"
    if sys.version_info >= (3, 11):
        assert native["namespace_bootstrap"] is False
        assert native["package_file"].endswith("dharma_swarm/__init__.py")
    else:
        assert native["namespace_bootstrap"] is True
        assert native["compat_cleaned"] is True


def test_onboard_json_emits_machine_projection() -> None:
    result = _run("--json")
    payload = json.loads(result.stdout)
    assert result.returncode == payload["exit_code"], result.stderr
    assert payload["schema"] == "dharma_swarm.onboard_json.v1"
    assert payload["verdict"] in {
        "READY", "BLOCKED", "NEEDS_HOST", "CONFIG_ERROR", "TOOLCHAIN_MISSING", "USAGE_ERROR",
    }
    assert "exit_code" in payload
    assert "conditions" in payload
    assert payload["nats_substrate"]["tcp_host"] == "127.0.0.1"
    assert payload["nats_substrate"]["tcp_port"] == 4222
    assert payload["nats_substrate"]["jetstream_ack_verified"] is False
    assert payload["nats_substrate"]["live_contact_claim"] is False


def test_onboard_strict_exits_true_exit_code() -> None:
    """The deprecated --strict flag is a behavior-preserving no-op."""
    truth = json.loads(_run("--json").stdout)
    strict = _run("--strict")
    default = _run()
    assert default.returncode == truth["exit_code"]
    assert strict.returncode == truth["exit_code"]


def test_onboard_unknown_flag_exits_two() -> None:
    result = _run("--definitely-not-a-real-flag")
    assert result.returncode == 2


def test_onboard_fast_is_deprecated() -> None:
    truth = json.loads(_run("--json").stdout)
    result = _run("--fast")
    assert result.returncode == truth["exit_code"]
    assert "deprecated" in result.stderr


def test_onboard_does_not_write_in_repo() -> None:
    before = subprocess.run(
        ["git", "status", "--porcelain", "--ignored=matching"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    ).stdout
    result = _run()
    truth = json.loads(_run("--json").stdout)
    assert result.returncode == truth["exit_code"]
    after = subprocess.run(
        ["git", "status", "--porcelain", "--ignored=matching"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    ).stdout
    assert before == after, "agent_onboard.py must not mutate the worktree"


def test_receipt_is_written_to_ops_dir(tmp_path: Path) -> None:
    ops = tmp_path / "ops"
    result = _run(ops_dir=ops)
    truth_result = _run("--json", ops_dir=ops)
    truth = json.loads(truth_result.stdout)
    assert result.returncode == truth["exit_code"]
    assert (ops / "onboard_receipt.json").exists()


def test_parse_broken_register_counts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load_module()
    sample = tmp_path / "BROKEN_REGISTER.md"
    sample.write_text(
        """# BROKEN REGISTER
## OPEN ITEMS (2 open/partial)
### BR-001 — first
- **status:** OPEN
### BR-002 — second
- **status:** PARTIAL
## CLOSED ITEMS
### BR-100 — done
- **status:** FIXED
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "BROKEN_REGISTER", sample)

    info = mod._parse_broken_register()
    assert info["present"] is True
    assert info["total"] == 3
    assert info["open_count"] == 2
    assert info["closed_count"] == 1
    assert info["unknown_count"] == 0
    assert len(info["top_open"]) == 2
    assert info["top_open"][0]["status_word"] == "OPEN"


def test_parse_broken_register_missing_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load_module()
    monkeypatch.setattr(mod, "BROKEN_REGISTER", tmp_path / "does_not_exist.md")
    info = mod._parse_broken_register()
    assert info == {"present": False}


def test_receipt_payload_v1_only() -> None:
    mod = _load_module()
    payload = mod._receipt_payload({}, {}, [], [], None, {})
    assert payload["schema"] == "dharma_swarm.onboard_receipt.v1"
    assert "dharma_swarm.onboard_receipt.v2" not in str(payload)


def test_scrape_tracks_matches_top_level_declarations(tmp_path: Path) -> None:
    """O3R-B3: the dependency-free fallback returns exactly the top-level
    ``active_tracks`` declarations — nested ``- id:`` rows (next_items,
    prerequisites, completion_criteria) are not tracks."""
    from dharma_swarm.operator_core.onboarding import evidence

    fixture = tmp_path / "ACTIVE_TRACK.yaml"
    fixture.write_text(
        "meta: 1\n"
        "active_tracks:\n"
        "  - id: track-alpha\n"
        "    next_items:\n"
        "      - id: 1\n"
        "        what: nested\n"
        "      - id: WP-X1\n"
        "  - id: track-beta\n"
        "    prerequisites:\n"
        "      - id: nested_prereq\n"
        "closed_tracks:\n"
        "  - id: not-a-live-track\n",
        encoding="utf-8",
    )
    rows = evidence._scrape_tracks(fixture)
    assert [row["id"] for row in rows] == ["track-alpha", "track-beta"]

    yaml = pytest.importorskip("yaml")
    real = REPO_ROOT / "docs" / "governance" / "ACTIVE_TRACK.yaml"
    declared = [
        str(row.get("id"))
        for row in yaml.safe_load(real.read_text(encoding="utf-8"))["active_tracks"]
        if isinstance(row, dict) and row.get("id")
    ]
    scraped = [row["id"] for row in evidence._scrape_tracks(real)]
    assert scraped == declared
    assert len(scraped) == len(set(scraped))
