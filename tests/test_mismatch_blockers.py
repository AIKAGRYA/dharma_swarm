"""Pinning tests for interface mismatches documented in docs/interface_mismatches.yaml."""

from __future__ import annotations

import ast
import inspect
import os
import re
import subprocess
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_registry_loads_and_is_nonempty() -> None:
    registry_path = REPO_ROOT / "docs" / "interface_mismatches.yaml"
    assert registry_path.exists(), f"{registry_path} does not exist"
    data = yaml.safe_load(registry_path.read_text())
    assert isinstance(data, dict), "YAML root must be a mapping"
    assert data.get("entries"), "Registry has no entries"


def test_registry_yaml_markdown_count_agree() -> None:
    registry_path = REPO_ROOT / "docs" / "interface_mismatches.yaml"
    data = yaml.safe_load(registry_path.read_text())
    yaml_ids = {entry["id"] for entry in data["entries"]}

    md_text = (REPO_ROOT / "INTERFACE_MISMATCH_MAP.md").read_text()
    md_ids: set[str] = set()
    for line in md_text.splitlines():
        match = re.match(r"\|\s*((?:MM-\d+(?:/\d+)?)|(?:NEW-\d+)):", line)
        if match:
            raw = match.group(1).split("/")[0]
            md_ids.add(raw)
        match = re.match(r"###\s+(MM-\d+(?:/\d+)?|NEW-\d+)\s", line)
        if match:
            raw = match.group(1).split("/")[0]
            md_ids.add(raw)

    assert not (md_ids - yaml_ids), f"IDs in markdown but not YAML: {md_ids - yaml_ids}"
    assert not (yaml_ids - md_ids), f"IDs in YAML but not markdown: {yaml_ids - md_ids}"


def test_resolved_entries_have_fixed_in() -> None:
    registry_path = REPO_ROOT / "docs" / "interface_mismatches.yaml"
    data = yaml.safe_load(registry_path.read_text())
    for entry in data["entries"]:
        if entry["status"] == "resolved":
            assert entry.get("fixed_in", "").strip(), (
                f"{entry['id']} is resolved but has no fixed_in"
            )


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def test_mm02_persistent_agent_enum() -> None:
    src = (REPO_ROOT / "dharma_swarm" / "orchestrate_live.py").read_text()
    tree = ast.parse(src)

    replication_calls: list[ast.Call] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name) and node.func.id == "PersistentAgent":
            if any("child_spec" in ast.dump(keyword.value) for keyword in node.keywords):
                replication_calls.append(node)

    assert replication_calls, "No PersistentAgent child_spec replication call found"
    for node in replication_calls:
        keywords = {keyword.arg: keyword.value for keyword in node.keywords}
        role = keywords.get("role")
        assert isinstance(role, ast.Call), "role must be wrapped in AgentRole()"
        assert _call_name(role.func) == "AgentRole"

        provider_type = keywords.get("provider_type")
        assert isinstance(provider_type, ast.Call), (
            "provider_type must be wrapped in ProviderType/PT()"
        )
        assert _call_name(provider_type.func) in {"PT", "ProviderType"}


def test_new03_telic_seam_constructor() -> None:
    from dharma_swarm.telic_seam import TelicSeam

    sig = inspect.signature(TelicSeam.__init__)
    params = list(sig.parameters.keys())
    assert "path" in params
    assert "registry_path" not in params

    src = (REPO_ROOT / "dharma_swarm" / "orchestrator.py").read_text()
    assert "registry_path=" not in src
    assert "TelicSeam(registry=registry, path=" in src


def test_mm05_orchestrator_private_methods() -> None:
    from dharma_swarm.orchestrator import Orchestrator

    assert hasattr(Orchestrator, "_classify_failure")
    assert hasattr(Orchestrator, "_resolve_retry_policy")
    assert hasattr(Orchestrator, "_apply_failure_retry_defaults")

    src = (REPO_ROOT / "dharma_swarm" / "swarm.py").read_text()
    assert "_classify_failure" in src
    assert "_resolve_retry_policy" in src


def test_mm07_meta_evolution_cadence() -> None:
    src = (REPO_ROOT / "dharma_swarm" / "orchestrate_live.py").read_text()
    count = src.count("observe_cycle_result(")
    assert count >= 2, (
        f"Expected >=2 observe_cycle_result calls, found {count}. "
        "If this is 1, mark MM-07 resolved."
    )


def test_mismatch_registry_guard_loads() -> None:
    from scripts.uplift_guards.mismatch_registry import load_mismatch_registry

    registry = load_mismatch_registry(REPO_ROOT)
    assert registry.entries
    assert registry.open_blockers() == []


def test_mismatch_registry_missing_is_fail_closed_with_valid_remediation(
    tmp_path: Path,
) -> None:
    from scripts.uplift_guards.mismatch_registry import check_mismatch_adjacency

    ok, message = check_mismatch_adjacency(tmp_path)

    assert not ok
    assert "MISMATCH REGISTRY MISSING" in message
    assert "make mismatch-check" in message
    assert "mismatch-sync" not in message


def test_mismatch_registry_empty_is_fail_closed_with_valid_remediation(
    tmp_path: Path,
) -> None:
    from scripts.uplift_guards.mismatch_registry import check_mismatch_adjacency

    registry_path = tmp_path / "docs" / "interface_mismatches.yaml"
    registry_path.parent.mkdir(parents=True)
    registry_path.write_text("entries: []\n")

    ok, message = check_mismatch_adjacency(tmp_path)

    assert not ok
    assert "MISMATCH REGISTRY EMPTY" in message
    assert "make mismatch-check" in message
    assert "mismatch-sync" not in message


def test_mismatch_registry_matches_dotted_callee_paths() -> None:
    from scripts.uplift_guards.mismatch_registry import Mismatch, MismatchRegistry

    registry = MismatchRegistry(
        entries=[
            Mismatch(
                id="NEW-03",
                severity="BLOCKER",
                status="resolved",
                caller="dharma_swarm/orchestrator.py:204",
                callee="dharma_swarm.telic_seam.TelicSeam.__init__",
                summary="constructor kwarg mismatch",
            )
        ]
    )

    matches = registry.matching_paths(["dharma_swarm/telic_seam.py"])
    assert [m.id for m in matches] == ["NEW-03"]


def test_semgrep_skip_env_exits_before_invoking_semgrep() -> None:
    env = {**os.environ, "DHARMA_SKIP_SEMGREP": "1"}
    result = subprocess.run(
        ["bash", "scripts/governance/run_semgrep_with_ca.sh", "--version"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "SEMGREP SKIPPED" in result.stderr
    assert result.stdout == ""
