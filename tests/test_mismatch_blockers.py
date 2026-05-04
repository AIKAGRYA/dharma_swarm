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
import textwrap
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
    """Number of entries in YAML must match the summary table in markdown."""
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
            for kw in node.keywords:
                if kw.arg == "role":
                    assert isinstance(kw.value, ast.Call), (
                        f"PersistentAgent(role=...) at line {node.lineno}: "
                        "role must be wrapped in AgentRole(), not a bare value"
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


def test_mm17_gnani_task_board() -> None:
    """TaskBoard has no get_by_title method — gnani_lodestone.py will crash.

    When a get_by_title (or equivalent) is added, update this test and
    mark MM-17 as resolved.
    """
    from dharma_swarm.task_board import TaskBoard

    has_method = hasattr(TaskBoard, "get_by_title")
    if not has_method:
        # Expected: method missing. Document the mismatch.
        src = (REPO_ROOT / "dharma_swarm" / "gnani_lodestone.py").read_text()
        assert "get_by_title" in src, (
            "gnani_lodestone.py no longer calls get_by_title — remove MM-17"
        )
    # If method exists, the mismatch is resolved — test passes either way


# ── MM-18: gnani_lodestone → TelosGraph.get_by_name (OPEN/DEGRADED) ──


def test_mm18_gnani_telos_graph() -> None:
    """TelosGraph has no get_by_name method — gnani_lodestone.py will crash.

    When a get_by_name (or equivalent) is added, update this test and
    mark MM-18 as resolved.
    """
    from dharma_swarm.telos_graph import TelosGraph

    has_method = hasattr(TelosGraph, "get_by_name")
    if not has_method:
        # Expected: method missing. Document the mismatch.
        src = (REPO_ROOT / "dharma_swarm" / "gnani_lodestone.py").read_text()
        assert "get_by_name" in src, (
            "gnani_lodestone.py no longer calls get_by_name — remove MM-18"
        )
    # If method exists, the mismatch is resolved — test passes either way


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
