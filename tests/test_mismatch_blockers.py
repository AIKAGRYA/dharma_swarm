"""Pinning tests for interface mismatches documented in docs/interface_mismatches.yaml.

Each test corresponds to a YAML entry. A resolved mismatch has a test that
would fail if the fix were reverted. An open mismatch has a test that
documents the current (broken) state.

Run:
    python -m pytest tests/test_mismatch_blockers.py -v
"""
from __future__ import annotations

import ast
import inspect
import os
import subprocess
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]


# ── Registry integrity ────────────────────────────────────────────


def test_registry_loads_and_is_nonempty() -> None:
    """docs/interface_mismatches.yaml must exist and parse with entries."""
    registry_path = REPO_ROOT / "docs" / "interface_mismatches.yaml"
    assert registry_path.exists(), f"{registry_path} does not exist"
    data = yaml.safe_load(registry_path.read_text())
    assert isinstance(data, dict), "YAML root must be a mapping"
    entries = data.get("entries", [])
    assert len(entries) > 0, "Registry has no entries"


def test_registry_yaml_markdown_count_agree() -> None:
    """Entry IDs in YAML must match the summary table and sections in markdown."""
    registry_path = REPO_ROOT / "docs" / "interface_mismatches.yaml"
    data = yaml.safe_load(registry_path.read_text())
    yaml_ids = {e["id"] for e in data["entries"]}

    md_path = REPO_ROOT / "INTERFACE_MISMATCH_MAP.md"
    md_text = md_path.read_text()
    import re
    md_ids: set[str] = set()
    for line in md_text.splitlines():
        # Match summary table rows "| MM-01: ..." or "| NEW-01: ..."
        m = re.match(r"\|\s*((?:MM-\d+(?:/\d+)?)|(?:NEW-\d+)):", line)
        if m:
            raw = m.group(1)
            if "/" in raw:
                raw = raw.split("/")[0]
            md_ids.add(raw)
        # Match detailed section headers "### MM-XX"
        m2 = re.match(r"###\s+(MM-\d+(?:/\d+)?|NEW-\d+)\s", line)
        if m2:
            raw = m2.group(1)
            if "/" in raw:
                raw = raw.split("/")[0]
            md_ids.add(raw)

    missing_in_yaml = md_ids - yaml_ids
    missing_in_md = yaml_ids - md_ids
    assert not missing_in_yaml, (
        f"IDs in markdown but not YAML: {missing_in_yaml}"
    )
    assert not missing_in_md, (
        f"IDs in YAML but not markdown: {missing_in_md}"
    )


def test_resolved_entries_have_fixed_in() -> None:
    """Every resolved entry must have a non-empty fixed_in field."""
    registry_path = REPO_ROOT / "docs" / "interface_mismatches.yaml"
    data = yaml.safe_load(registry_path.read_text())
    for entry in data["entries"]:
        if entry["status"] == "resolved":
            assert entry.get("fixed_in", "").strip(), (
                f"{entry['id']} is resolved but has no fixed_in"
            )


# ── MM-02: PersistentAgent enum wrapping (RESOLVED) ──────────────


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def test_mm02_persistent_agent_enum() -> None:
    """Replication-path PersistentAgent() must wrap role in AgentRole().

    Regression test: without AgentRole() wrapping, PersistentAgent would
    receive a bare string and crash on enum validation.

    The conductor-configs path (line ~1471) uses pre-constructed enum
    values from CONDUCTOR_CONFIGS (cfg["role"] is already AgentRole.CONDUCTOR),
    so that call site is exempt.
    """
    src = (REPO_ROOT / "dharma_swarm" / "orchestrate_live.py").read_text()
    tree = ast.parse(src)

    # Find PersistentAgent(...) calls that use outcome.child_spec (replication path)
    replication_calls: list[ast.Call] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == "PersistentAgent":
            # Check if this call uses child_spec (replication path)
            uses_child_spec = any(
                "child_spec" in ast.dump(kw.value) for kw in node.keywords
            )
            if not uses_child_spec:
                continue  # conductor-configs path — already enum
            replication_calls.append(node)

    assert replication_calls, "No PersistentAgent child_spec replication call found"
    for node in replication_calls:
        keywords = {kw.arg: kw.value for kw in node.keywords}
        role = keywords.get("role")
        assert isinstance(role, ast.Call), (
            f"PersistentAgent(role=...) at line {node.lineno}: "
            "role must be wrapped in AgentRole(), not a bare value"
        )
        assert _call_name(role.func) == "AgentRole", (
            f"PersistentAgent(role=...) at line {node.lineno}: "
            "role must specifically use AgentRole(...)"
        )

        provider_type = keywords.get("provider_type")
        assert isinstance(provider_type, ast.Call), (
            f"PersistentAgent(provider_type=...) at line {node.lineno}: "
            "provider_type must be wrapped in ProviderType/PT(), not a bare value"
        )
        assert _call_name(provider_type.func) in {"PT", "ProviderType"}, (
            f"PersistentAgent(provider_type=...) at line {node.lineno}: "
            "provider_type must specifically use ProviderType/PT(...)"
        )


# ── NEW-03: TelicSeam constructor kwarg (RESOLVED) ───────────────


def test_new03_telic_seam_constructor() -> None:
    """orchestrator.py must call TelicSeam(path=...), not TelicSeam(registry_path=...).

    Regression test: TelicSeam.__init__ accepts `path=`, not `registry_path=`.
    """
    from dharma_swarm.telic_seam import TelicSeam

    sig = inspect.signature(TelicSeam.__init__)
    params = list(sig.parameters.keys())
    assert "path" in params, "TelicSeam.__init__ must accept 'path' parameter"
    assert "registry_path" not in params, (
        "TelicSeam.__init__ must NOT accept 'registry_path'"
    )

    # Verify orchestrator.py uses the correct kwarg
    src = (REPO_ROOT / "dharma_swarm" / "orchestrator.py").read_text()
    assert "registry_path=" not in src, (
        "orchestrator.py still uses registry_path= (should be path=)"
    )
    assert "TelicSeam(registry=registry, path=" in src, (
        "orchestrator.py must call TelicSeam(registry=..., path=...)"
    )


# ── MM-05: Private Orchestrator method coupling (OPEN/DEGRADED) ──


def test_mm05_orchestrator_private_methods() -> None:
    """Document that swarm.py couples to private Orchestrator methods.

    This test PASSES to document the current (broken) state — the private
    methods exist on Orchestrator, so the code doesn't crash. But the
    coupling is fragile. When Orchestrator exposes a public retry API,
    update this test.
    """
    from dharma_swarm.orchestrator import Orchestrator

    # These private methods exist — the coupling works at runtime
    assert hasattr(Orchestrator, "_classify_failure"), (
        "Orchestrator._classify_failure removed — swarm.py:1978 will crash"
    )
    assert hasattr(Orchestrator, "_resolve_retry_policy"), (
        "Orchestrator._resolve_retry_policy removed — swarm.py:1986 will crash"
    )
    assert hasattr(Orchestrator, "_apply_failure_retry_defaults"), (
        "Orchestrator._apply_failure_retry_defaults removed — swarm.py:1987 will crash"
    )

    # Verify swarm.py still references them
    src = (REPO_ROOT / "dharma_swarm" / "swarm.py").read_text()
    assert "_classify_failure" in src, "swarm.py no longer references _classify_failure"
    assert "_resolve_retry_policy" in src, "swarm.py no longer references _resolve_retry_policy"


# ── MM-07: MetaEvolutionEngine cadence (OPEN/DEGRADED) ───────────


def test_mm07_meta_evolution_cadence() -> None:
    """Document that observe_cycle_result is called multiple times per cycle.

    This test counts call sites in orchestrate_live.py. When the cadence
    fix lands (single call per cycle), update the expected count.
    """
    src = (REPO_ROOT / "dharma_swarm" / "orchestrate_live.py").read_text()
    count = src.count("observe_cycle_result(")
    assert count >= 2, (
        f"Expected >=2 observe_cycle_result calls, found {count}. "
        "If this is 1, the cadence fix may have landed — update MM-07 status."
    )


# ── MM-17: gnani_lodestone → TaskBoard.get_by_title (OPEN/DEGRADED) ──


def _registry_entry(entry_id: str) -> dict:
    registry_path = REPO_ROOT / "docs" / "interface_mismatches.yaml"
    data = yaml.safe_load(registry_path.read_text())
    for entry in data["entries"]:
        if entry["id"] == entry_id:
            return entry
    raise AssertionError(f"{entry_id} missing from interface mismatch registry")


def test_mm17_gnani_task_board() -> None:
    """TaskBoard has no get_by_title method — gnani_lodestone.py will crash.

    When a get_by_title (or equivalent) is added, update this test and
    mark MM-17 as resolved.
    """
    from dharma_swarm.task_board import TaskBoard

    entry = _registry_entry("MM-17")
    has_method = hasattr(TaskBoard, "get_by_title")
    src = (REPO_ROOT / "dharma_swarm" / "gnani_lodestone.py").read_text()
    still_calls_missing_method = "get_by_title" in src
    if entry["status"] == "open":
        assert not has_method, "TaskBoard.get_by_title exists — mark MM-17 resolved"
        assert still_calls_missing_method, (
            "gnani_lodestone.py no longer calls get_by_title — mark MM-17 resolved"
        )
    else:
        assert has_method or not still_calls_missing_method, (
            "MM-17 is resolved, but gnani_lodestone.py still calls missing get_by_title"
        )


# ── MM-18: gnani_lodestone → TelosGraph.get_by_name (OPEN/DEGRADED) ──


def test_mm18_gnani_telos_graph() -> None:
    """TelosGraph has no get_by_name method — gnani_lodestone.py will crash.

    When a get_by_name (or equivalent) is added, update this test and
    mark MM-18 as resolved.
    """
    from dharma_swarm.telos_graph import TelosGraph

    entry = _registry_entry("MM-18")
    has_method = hasattr(TelosGraph, "get_by_name")
    src = (REPO_ROOT / "dharma_swarm" / "gnani_lodestone.py").read_text()
    still_calls_missing_method = "get_by_name" in src
    if entry["status"] == "open":
        assert not has_method, "TelosGraph.get_by_name exists — mark MM-18 resolved"
        assert still_calls_missing_method, (
            "gnani_lodestone.py no longer calls get_by_name — mark MM-18 resolved"
        )
    else:
        assert has_method or not still_calls_missing_method, (
            "MM-18 is resolved, but gnani_lodestone.py still calls missing get_by_name"
        )


# ── Mismatch Registry Guard ──────────────────────────────────────


def test_mismatch_registry_guard_loads() -> None:
    """scripts/uplift_guards/mismatch_registry.py loads YAML correctly."""
    from scripts.uplift_guards.mismatch_registry import load_mismatch_registry

    registry = load_mismatch_registry(REPO_ROOT)
    assert len(registry.entries) > 0, "Registry loaded 0 entries from YAML"
    # Verify open blockers
    open_blockers = registry.open_blockers()
    # MM-02 is now resolved — no open blockers expected
    assert len(open_blockers) == 0, (
        f"Expected 0 open BLOCKERs, found {len(open_blockers)}: "
        f"{[m.id for m in open_blockers]}"
    )


def test_mismatch_registry_missing_is_fail_closed_with_valid_remediation(
    tmp_path: Path,
) -> None:
    """Missing registry diagnostics must not point at nonexistent Make targets."""
    from scripts.uplift_guards.mismatch_registry import check_mismatch_adjacency

    ok, message = check_mismatch_adjacency(tmp_path)

    assert not ok
    assert "MISMATCH REGISTRY MISSING" in message
    assert "make mismatch-check" in message
    assert "mismatch-sync" not in message


def test_mismatch_registry_empty_is_fail_closed_with_valid_remediation(
    tmp_path: Path,
) -> None:
    """Empty registry diagnostics must not point at nonexistent Make targets."""
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
    """Dotted callee refs should match concrete repo file paths."""
    from scripts.uplift_guards.mismatch_registry import Mismatch, MismatchRegistry

    registry = MismatchRegistry(
        entries=[
            Mismatch(
                id="NEW-03",
                severity="BLOCKER",
                status="resolved",
                caller="dharma_swarm/orchestrator.py:154",
                callee="dharma_swarm.telic_seam.TelicSeam.__init__",
                summary="constructor kwarg mismatch",
            )
        ]
    )

    matches = registry.matching_paths(["dharma_swarm/telic_seam.py"])
    assert [m.id for m in matches] == ["NEW-03"]


def test_semgrep_skip_env_exits_before_invoking_semgrep() -> None:
    """DHARMA_SKIP_SEMGREP=1 must skip even when semgrep is installed."""
    env = {**os.environ, "DHARMA_SKIP_SEMGREP": "1"}
    result = subprocess.run(
        [
            "bash",
            "scripts/governance/run_semgrep_with_ca.sh",
            "--version",
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "SEMGREP SKIPPED" in result.stderr
    assert result.stdout == ""
