"""Tests for the v2 track-portfolio graph machinery in check_track_status.

These exercise the portfolio invariants the singular v1 schema could never
express: WIP limits, spine resolution + coverage, typed-edge resolution,
dependency-cycle detection, active-active conflict, and owned-surface overlap.
They run the pure validator functions against synthetic portfolios, so they are
fast and independent of the live ACTIVE_TRACK.yaml contents.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts/governance"))

from check_track_status import (  # type: ignore  # noqa: E402
    normalize_portfolio,
    validate_portfolio_graph,
    detect_dependency_cycle,
    _parse_minimal_yaml,
    _resolve_command_for_current_runtime,
    check_command_passes,
    Finding,
)

ACTIVE_TRACK = REPO_ROOT / "docs/governance/ACTIVE_TRACK.yaml"


def _checks(findings: list[Finding]) -> set[str]:
    return {f.check.split(":")[0] for f in findings}


def _by_severity(findings: list[Finding], sev: str) -> list[Finding]:
    return [f for f in findings if f.severity == sev]


def _portfolio(tracks, *, spine=None, policy=None, closed=None):
    raw = {
        "schema_version": 2,
        "spine_objectives": spine if spine is not None else [{"id": "obj-a", "name": "A"}],
        "track_policy": policy or {},
        "active_tracks": tracks,
        "closed_tracks": closed or [],
    }
    return normalize_portfolio(raw)


def _track(tid, **kw):
    base = {
        "id": tid,
        "status": "ACTIVE",
        "serves": "obj-a",
        "verified_at": "2026-06-07",
        "ttl_days": 21,
    }
    base.update(kw)
    return base


# --- v1 backward-compat adapter -------------------------------------------

def test_normalize_v1_singular_becomes_one_track_portfolio() -> None:
    raw = {"schema_version": 1, "active_track": {"id": "t1", "status": "ACTIVE"}}
    p = normalize_portfolio(raw)
    assert [t["id"] for t in p["active_tracks"]] == ["t1"]
    assert p["primary"]["id"] == "t1"


def test_normalize_v2_list_and_primary() -> None:
    p = _portfolio([_track("a"), _track("b")])
    assert [t["id"] for t in p["active_tracks"]] == ["a", "b"]
    assert p["primary"]["id"] == "a"          # primary = first, a compat projection
    assert p["track_policy"]["max_active"] == 10   # default


# --- WIP limit ------------------------------------------------------------

def test_wip_exceeded_is_error() -> None:
    tracks = [_track(f"t{i}") for i in range(4)]
    p = _portfolio(tracks, policy={"max_active": 3, "warn_active": 2})
    findings: list[Finding] = []
    validate_portfolio_graph(p, findings)
    assert "wip-exceeded" in _checks(findings)
    assert _by_severity(findings, "ERROR")


def test_wip_high_is_warn_not_error() -> None:
    tracks = [_track(f"t{i}") for i in range(3)]
    p = _portfolio(tracks, policy={"max_active": 10, "warn_active": 2})
    findings: list[Finding] = []
    validate_portfolio_graph(p, findings)
    assert "wip-high" in _checks(findings)
    assert not any(f.check == "wip-exceeded" for f in findings)


def test_empty_portfolio_warns() -> None:
    p = _portfolio([])
    findings: list[Finding] = []
    validate_portfolio_graph(p, findings)
    assert "portfolio-empty" in _checks(findings)


# --- spine resolution + coverage ------------------------------------------

def test_spine_missing_is_error() -> None:
    p = _portfolio([_track("a", serves=None)])
    findings: list[Finding] = []
    validate_portfolio_graph(p, findings)
    assert "spine-missing" in _checks(findings)


def test_spine_unresolved_is_error() -> None:
    p = _portfolio([_track("a", serves="nope")])
    findings: list[Finding] = []
    validate_portfolio_graph(p, findings)
    assert "spine-unresolved" in _checks(findings)


def test_spine_uncovered_objective_warns() -> None:
    spine = [{"id": "obj-a", "name": "A"}, {"id": "obj-b", "name": "B"}]
    p = _portfolio([_track("a", serves="obj-a")], spine=spine)
    findings: list[Finding] = []
    validate_portfolio_graph(p, findings)
    uncovered = [f for f in findings if f.check.startswith("spine-uncovered")]
    assert any("obj-b" in f.check for f in uncovered)
    assert all(f.severity == "WARN" for f in uncovered)


# --- typed-edge resolution ------------------------------------------------

def test_unresolved_edge_is_error() -> None:
    p = _portfolio([_track("a", complements=["ghost"])])
    findings: list[Finding] = []
    validate_portfolio_graph(p, findings)
    assert "edge-unresolved" in _checks(findings)


def test_edge_to_closed_track_resolves() -> None:
    p = _portfolio([_track("a", depends_on=["old"])],
                   closed=[{"id": "old", "name": "Old", "status": "SHIPPED"}])
    findings: list[Finding] = []
    validate_portfolio_graph(p, findings)
    assert "edge-unresolved" not in _checks(findings)


# --- dependency cycle detection -------------------------------------------

def test_dependency_cycle_detected_with_path() -> None:
    tracks = [
        _track("a", depends_on=["b"]),
        _track("b", depends_on=["c"]),
        _track("c", depends_on=["a"]),
    ]
    findings: list[Finding] = []
    detect_dependency_cycle(tracks, findings)
    cyc = [f for f in findings if f.check == "dependency-cycle"]
    assert cyc, "expected a dependency-cycle finding"
    assert "->" in cyc[0].message


def test_acyclic_dependencies_pass() -> None:
    tracks = [_track("a", depends_on=["b"]), _track("b")]
    findings: list[Finding] = []
    detect_dependency_cycle(tracks, findings)
    assert not findings


# --- active-active conflict -----------------------------------------------

def test_active_active_conflict_is_error() -> None:
    tracks = [_track("a", conflicts_with=["b"]), _track("b")]
    p = _portfolio(tracks)
    findings: list[Finding] = []
    validate_portfolio_graph(p, findings)
    assert "active-conflict" in _checks(findings)


def test_conflict_with_inactive_track_is_ok() -> None:
    tracks = [_track("a", conflicts_with=["b"]), _track("b", status="PAUSED")]
    p = _portfolio(tracks)
    findings: list[Finding] = []
    validate_portfolio_graph(p, findings)
    assert "active-conflict" not in _checks(findings)


# --- owned-surface overlap ------------------------------------------------

def test_surface_overlap_warns_by_default() -> None:
    tracks = [
        _track("a", owned_surfaces=["pkg/x/**"]),
        _track("b", owned_surfaces=["pkg/x/**"]),
    ]
    p = _portfolio(tracks)
    findings: list[Finding] = []
    validate_portfolio_graph(p, findings)
    overlap = [f for f in findings if f.check.startswith("surface-overlap")]
    assert overlap and overlap[0].severity == "WARN"


def test_surface_overlap_error_mode() -> None:
    tracks = [
        _track("a", owned_surfaces=["pkg/x/**"]),
        _track("b", owned_surfaces=["pkg/x/**"]),
    ]
    p = _portfolio(tracks, policy={"surface_overlap": "error"})
    findings: list[Finding] = []
    validate_portfolio_graph(p, findings)
    overlap = [f for f in findings if f.check.startswith("surface-overlap")]
    assert overlap and overlap[0].severity == "ERROR"


def test_stdlib_parser_matches_pyyaml_on_real_file() -> None:
    """The stdlib fallback parser must agree with PyYAML on the structural
    fields the checker acts on — guards the no-PyYAML CI path against the
    flow-list / scalar regressions found in adversarial review."""
    import yaml  # PyYAML is the reference

    text = ACTIVE_TRACK.read_text(encoding="utf-8")
    ref = yaml.safe_load(text)
    mini = _parse_minimal_yaml(text)

    p_ref = normalize_portfolio(ref)
    p_mini = normalize_portfolio(mini)

    assert ref.get("schema_version") == mini.get("schema_version")
    assert [t["id"] for t in p_ref["active_tracks"]] == [t["id"] for t in p_mini["active_tracks"]]
    assert p_ref["track_policy"] == p_mini["track_policy"]
    for a, b in zip(p_ref["active_tracks"], p_mini["active_tracks"]):
        assert a.get("serves") == b.get("serves")
        for kind in ("complements", "depends_on", "conflicts_with", "owned_surfaces"):
            assert (a.get(kind) or []) == (b.get(kind) or []), f"{a['id']}.{kind} parser mismatch"
        assert len(a.get("completion_criteria") or []) == len(b.get("completion_criteria") or [])


def test_scalar_flow_list_matches_pyyaml_incl_quoted_comma() -> None:
    """Stdlib `_scalar` must parse inline flow lists the same as PyYAML,
    including quoted elements that contain commas (round-3 regression guard)."""
    import yaml
    for src in ('k: []', 'k: [a, b]', 'k: [1, 2]', 'k: ["a,b", c]'):
        assert _parse_minimal_yaml(src)["k"] == yaml.safe_load(src)["k"], src


def test_disjoint_surfaces_no_overlap() -> None:
    tracks = [
        _track("a", owned_surfaces=["pkg/x/**"]),
        _track("b", owned_surfaces=["pkg/y/**"]),
    ]
    p = _portfolio(tracks)
    findings: list[Finding] = []
    validate_portfolio_graph(p, findings)
    assert not any(f.check.startswith("surface-overlap") for f in findings)


# --- defensive: parser must not crash on nested flow lists ------------------

def test_scalar_nested_flow_list_degrades_gracefully() -> None:
    """Nested inline flow lists like `k: [[a, b], c]` are intentionally NOT
    supported by the stdlib fallback (PyYAML handles them; we don't).
    What we DO promise is that the parser never crashes on them: it must
    return *something* (even if the inner list is degraded to a string), so
    the checker can still surface other findings instead of stack-tracing.
    Real nested structures should use block style anyway."""
    src = "k: [[a, b], c]"
    out = _parse_minimal_yaml(src)        # must not raise
    assert "k" in out
    assert isinstance(out["k"], list)     # we got a list, not a crash
    # And the same input through the full normalize pipeline must also survive.
    raw = {"schema_version": 2, "active_tracks": [{"id": "a", "depends_on": out["k"]}]}
    p = normalize_portfolio(raw)
    assert p["active_tracks"][0]["id"] == "a"


# --- executable criteria portability ---------------------------------------

def test_command_passes_resolves_pytest_to_current_interpreter() -> None:
    resolved = _resolve_command_for_current_runtime(["pytest", "-q", "tests/test_nats_transport.py"])

    assert resolved[:3] == [sys.executable, "-m", "pytest"]
    assert resolved[3:] == ["-q", "tests/test_nats_transport.py"]


def test_command_passes_resolves_bare_python_to_current_interpreter() -> None:
    for executable in ("python", "python3"):
        resolved = _resolve_command_for_current_runtime(
            [executable, "scripts/governance/check_track_status.py", "--warn-only"]
        )

        assert resolved == [
            sys.executable,
            "scripts/governance/check_track_status.py",
            "--warn-only",
        ]


def test_command_passes_resolves_missing_repo_venv(monkeypatch) -> None:
    monkeypatch.setattr("check_track_status.Path.exists", lambda _path: False)

    resolved = _resolve_command_for_current_runtime(["./.venv/bin/python", "scripts/check.py"])

    assert resolved == [sys.executable, "scripts/check.py"]


def test_command_passes_exports_dharma_python(monkeypatch) -> None:
    """Wrapper-routed criteria (run_python_with_repo_env.sh honors
    DHARMA_PYTHON) must see this checker's dependency-complete interpreter,
    not fall back to a checkout-local `.venv` or bare python3."""
    monkeypatch.delenv("DHARMA_PYTHON", raising=False)
    probe = (
        "import os, sys; "
        "sys.exit(0 if os.environ.get('DHARMA_PYTHON') == sys.executable else 1)"
    )

    result = check_command_passes([sys.executable, "-c", probe])

    assert result.passed
    assert result.executed


def test_command_passes_does_not_export_dharma_python_for_non_python(
    monkeypatch,
) -> None:
    """Non-Python criteria must not inherit the governance interpreter."""
    monkeypatch.delenv("DHARMA_PYTHON", raising=False)

    result = check_command_passes(
        ["bash", "-c", 'test -z "${DHARMA_PYTHON+x}"']
    )

    assert result.passed, result.detail
    assert result.executed


def test_command_passes_removes_preset_dharma_python_for_non_python(
    monkeypatch,
) -> None:
    """An operator Python pin must not alter an unrelated command runtime."""
    monkeypatch.setenv("DHARMA_PYTHON", "/operator/pinned/python")

    result = check_command_passes(
        ["bash", "-c", 'test -z "${DHARMA_PYTHON+x}"']
    )

    assert result.passed, result.detail
    assert result.executed


def test_command_passes_respects_existing_dharma_python(monkeypatch) -> None:
    monkeypatch.setenv("DHARMA_PYTHON", "/operator/pinned/python")
    probe = (
        "import os, sys; "
        "sys.exit(0 if os.environ.get('DHARMA_PYTHON') == '/operator/pinned/python' else 1)"
    )

    result = check_command_passes([sys.executable, "-c", probe])

    assert result.passed


def test_command_passes_missing_third_party_module_is_unverified() -> None:
    """A minimal-deps environment (the governance gate installs only pyyaml)
    cannot RUN import-heavy criteria. That is `executed=False` — could not
    observe — never a hard fail that publishes a fake regression baseline."""
    result = check_command_passes(
        [sys.executable, "-c", "import definitely_absent_third_party_xyz"]
    )

    assert not result.passed
    assert not result.executed
    assert "definitely_absent_third_party_xyz" in result.detail
    assert "not evidence of regression" in result.detail


def test_command_passes_missing_repo_module_stays_a_real_failure() -> None:
    """A repo-local module that fails to import is evidence about the code,
    not the environment — it must remain an executed hard failure."""
    probe = "import dharma_swarm.definitely_absent_internal_module"

    result = check_command_passes([sys.executable, "-c", probe])

    assert not result.passed
    assert result.executed


def test_command_passes_explicit_skip_is_unverified_never_pass(monkeypatch) -> None:
    """DHARMA_TRACK_STATUS_SKIP_COMMANDS=1 (set by callers that own command
    execution, e.g. the enclosing pytest suite) records the criterion as
    UNVERIFIED — passed stays False so a skip can never mint a green."""
    monkeypatch.setenv("DHARMA_TRACK_STATUS_SKIP_COMMANDS", "1")

    result = check_command_passes([sys.executable, "-c", "raise SystemExit(0)"])

    assert not result.passed
    assert not result.executed
    assert "caller owns command execution" in result.detail


# --- closed_tracks shape validation -----------------------------------------

def test_closed_track_non_dict_is_error() -> None:
    p = _portfolio([_track("a")], closed=["not-a-dict"])  # type: ignore[list-item]
    findings: list[Finding] = []
    validate_portfolio_graph(p, findings)
    assert any(f.check == "closed-track-shape" and f.severity == "ERROR" for f in findings)


def test_closed_track_missing_id_is_error() -> None:
    p = _portfolio([_track("a")], closed=[{"status": "CLOSED"}])
    findings: list[Finding] = []
    validate_portfolio_graph(p, findings)
    assert any(f.check == "closed-track-shape" and f.severity == "ERROR" for f in findings)


def test_closed_track_unresolved_edge_is_error() -> None:
    p = _portfolio(
        [_track("a")],
        closed=[{"id": "old", "status": "CLOSED", "depends_on": ["ghost"]}],
    )
    findings: list[Finding] = []
    validate_portfolio_graph(p, findings)
    assert any(
        f.check == "edge-unresolved:old" and f.severity == "ERROR" for f in findings
    )


def test_closed_track_bad_spine_serves_is_error() -> None:
    p = _portfolio(
        [_track("a")],
        spine=[{"id": "obj-a", "name": "A"}],
        closed=[{"id": "old", "status": "CLOSED", "serves": "obj-ghost"}],
    )
    findings: list[Finding] = []
    validate_portfolio_graph(p, findings)
    assert any(
        f.check == "spine-unresolved:old" and f.severity == "ERROR" for f in findings
    )


def test_closed_track_well_formed_is_silent() -> None:
    p = _portfolio(
        [_track("a")],
        spine=[{"id": "obj-a", "name": "A"}],
        closed=[{"id": "old", "status": "CLOSED", "serves": "obj-a"}],
    )
    findings: list[Finding] = []
    validate_portfolio_graph(p, findings)
    assert not any(f.check == "closed-track-shape" for f in findings)
    assert not any(f.check.startswith("edge-unresolved:old") for f in findings)


# --- track_policy explicit tombstone field ----------------------------------

def test_track_policy_grace_enforced_default_is_false() -> None:
    """Downstream JSON consumers must see `min_active_grace_enforced` as a
    first-class field (default False = advisory), not have to infer it."""
    p = _portfolio([_track("a")])
    assert p["track_policy"]["min_active_grace_enforced"] is False


def test_track_policy_grace_enforced_pass_through() -> None:
    p = _portfolio([_track("a")], policy={"min_active_grace_enforced": True})
    assert p["track_policy"]["min_active_grace_enforced"] is True
