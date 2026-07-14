"""Tests for the v2 track-portfolio graph machinery in check_track_status.

These exercise the portfolio invariants the singular v1 schema could never
express: WIP limits, spine resolution + coverage, typed-edge resolution,
dependency-cycle detection, active-active conflict, and owned-surface overlap.
They run the pure validator functions against synthetic portfolios, so they are
fast and independent of the live ACTIVE_TRACK.yaml contents.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts/governance"))

from check_track_status import (  # type: ignore  # noqa: E402
    EXTERNAL_ACTED_RECEIPT_REQUIRED_FIELDS,
    check_gauntlet_verified,
    evaluate_criterion,
    normalize_portfolio,
    validate_portfolio_graph,
    validate_readiness_score_caps,
    readiness_score_cap,
    detect_dependency_cycle,
    _parse_minimal_yaml,
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


# --- external acted receipt predicate --------------------------------------

def _receipt_criterion(path: Path) -> dict[str, str]:
    return {
        "id": "first_external_receipt_exists",
        "kind": "external_acted_receipt",
        "file": str(path),
    }


def test_external_acted_receipt_missing_fails(tmp_path: Path) -> None:
    missing = tmp_path / "FIRST_EXTERNAL_ACTED_RECEIPT.md"

    result = evaluate_criterion(_receipt_criterion(missing))

    assert result.id == "first_external_receipt_exists"
    assert result.kind == "external_acted_receipt"
    assert result.passed is False
    assert "MISSING" in result.detail


def test_external_acted_receipt_rejects_operator_packet_or_template(tmp_path: Path) -> None:
    fake = tmp_path / "FIRST_EXTERNAL_ACTED_RECEIPT.md"
    lines = [
        "# Fake receipt",
        "**Status:** operator handoff only; not an external acted receipt",
        *[f"- `{field}`: filled" for field in EXTERNAL_ACTED_RECEIPT_REQUIRED_FIELDS],
    ]
    fake.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = evaluate_criterion(_receipt_criterion(fake))

    assert result.passed is False
    assert "forbidden non-receipt marker" in result.detail


def test_external_acted_receipt_accepts_minimal_redacted_receipt(tmp_path: Path) -> None:
    receipt = tmp_path / "FIRST_EXTERNAL_ACTED_RECEIPT.md"
    lines = ["# First External Acted Receipt"]
    lines.extend(f"{field}: redacted proof value" for field in EXTERNAL_ACTED_RECEIPT_REQUIRED_FIELDS)
    receipt.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = evaluate_criterion(_receipt_criterion(receipt))

    assert result.passed is True
    assert "required acted-receipt fields" in result.detail


# --- executable command predicate ------------------------------------------

def test_command_passes_predicate_reports_exit_status() -> None:
    passed = evaluate_criterion(
        {
            "id": "focused_gate",
            "kind": "command_passes",
            "command": [sys.executable, "-c", "print('ok')"],
            "timeout_s": 10,
        }
    )
    failed = evaluate_criterion(
        {
            "id": "focused_gate",
            "kind": "command_passes",
            "command": [sys.executable, "-c", "import sys; print('bad'); sys.exit(3)"],
            "timeout_s": 10,
        }
    )

    assert passed.passed is True
    assert "exited 0" in passed.detail
    assert failed.passed is False
    assert "exited 3" in failed.detail
    assert "bad" in failed.detail


def test_command_passes_rejects_shell_string() -> None:
    result = evaluate_criterion(
        {
            "id": "focused_gate",
            "kind": "command_passes",
            "command": f"{sys.executable} -c 'print(1)'",
        }
    )

    assert result.passed is False
    assert "list of strings" in result.detail


def test_hardening_score_at_least_blocks_flat_score() -> None:
    track = {"hardening_status": {"current_score": 70, "scale": 100}}
    result = evaluate_criterion(
        {
            "id": "score_gate",
            "kind": "hardening_score_at_least",
            "minimum": 75,
        },
        track=track,
    )

    assert result.id == "score_gate"
    assert result.kind == "hardening_score_at_least"
    assert result.passed is False
    assert "70/100" in result.detail


def test_hardening_score_at_least_passes_when_threshold_met() -> None:
    track = {"hardening_status": {"current_score": 75, "scale": 100}}
    result = evaluate_criterion(
        {
            "kind": "hardening_score_at_least",
            "minimum": 75,
        },
        track=track,
    )

    assert result.passed is True


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


# --- readiness score cap ----------------------------------------------------

def _runtime_score_track(current_score: int, gates_passed: list[str]):
    return _track(
        "runtime-truth-spine-adoption-2026-06",
        readiness_baseline={"score": 54, "scale": 100},
        hardening_status={
            "current_score": current_score,
            "scale": 100,
            "gates_passed": gates_passed,
        },
    )


def test_readiness_score_cap_allows_current_score_at_declared_gate() -> None:
    track = _runtime_score_track(
        70,
        [
            "54_to_60: baseline visible in active governance",
            "60_to_65: bypass list has no unknowns",
            "65_to_70: dispatch strict gate passes",
        ],
    )

    cap = readiness_score_cap(track)

    assert cap is not None
    assert cap["cap_score"] == 70
    assert cap["current_score"] == 70
    assert cap["within_cap"] is True


def test_readiness_score_cap_blocks_current_score_above_declared_gate() -> None:
    track = _runtime_score_track(
        75,
        [
            "54_to_60: baseline visible in active governance",
            "60_to_65: bypass list has no unknowns",
            "65_to_70: dispatch strict gate passes",
        ],
    )
    findings: list[Finding] = []

    validate_readiness_score_caps([track], findings)

    assert any(
        f.severity == "ERROR"
        and f.check == "score-cap:runtime-truth-spine-adoption-2026-06"
        and "exceeds executable gate cap 70/100" in f.message
        for f in findings
    )


def test_readiness_score_cap_ignores_scoped_post_gate_prose() -> None:
    track = _runtime_score_track(
        75,
        [
            "54_to_60: baseline visible in active governance",
            "60_to_65: bypass list has no unknowns",
            "65_to_70: dispatch strict gate passes",
            (
                "post_70_fresh_dropoff_field_gate: scoped proof mentions "
                "the 70->75 receipt field gate but is not production readiness"
            ),
        ],
    )

    cap = readiness_score_cap(track)

    assert cap is not None
    assert cap["cap_score"] == 70
    assert cap["within_cap"] is False


def test_readiness_score_cap_advances_only_on_contiguous_gate_label() -> None:
    track = _runtime_score_track(
        75,
        [
            "54_to_60: baseline visible in active governance",
            "60_to_65: bypass list has no unknowns",
            "65_to_70: dispatch strict gate passes",
            "70_to_75: strict receipt coverage gate passes",
        ],
    )

    cap = readiness_score_cap(track)

    assert cap is not None
    assert cap["cap_score"] == 75
    assert cap["within_cap"] is True


# --- gauntlet_verified predicate -------------------------------------------

def _write_gauntlet_receipt(path: Path, *, score=0.9, passed=4, total=4,
                            tiers=(1, 2, 3, 4, 5), ts=None, **extra) -> Path:
    receipt = {
        "run_id": "gauntlet-test",
        "timestamp": ts or datetime.now(timezone.utc).isoformat(),
        "tiers_run": list(tiers),
        "gauntlet_score": score,
        "task_scores": [{"task_id": f"t{i}", "passed": i < passed} for i in range(total)],
    }
    receipt.update(extra)
    path.write_text(json.dumps(receipt), encoding="utf-8")
    return path


def _gauntlet_criterion(path: Path, **kw) -> dict:
    crit = {"id": "gauntlet_verified", "kind": "gauntlet_verified", "receipt": str(path)}
    crit.update(kw)
    return crit


def test_gauntlet_verified_fresh_green_passes(tmp_path: Path) -> None:
    receipt = _write_gauntlet_receipt(tmp_path / "g.json", score=0.9, passed=4, total=4)
    res = evaluate_criterion(_gauntlet_criterion(receipt))
    assert res.id == "gauntlet_verified"
    assert res.kind == "gauntlet_verified"
    assert res.passed is True


def test_gauntlet_verified_missing_receipt_fails(tmp_path: Path) -> None:
    res = evaluate_criterion(_gauntlet_criterion(tmp_path / "nope.json"))
    assert res.passed is False
    assert "MISSING" in res.detail


def test_gauntlet_verified_stale_receipt_fails(tmp_path: Path) -> None:
    old = (datetime.now(timezone.utc) - timedelta(hours=200)).isoformat()
    receipt = _write_gauntlet_receipt(tmp_path / "g.json", ts=old)
    res = evaluate_criterion(_gauntlet_criterion(receipt, max_age_hours=168))
    assert res.passed is False
    assert "stale" in res.detail


def test_gauntlet_verified_failed_task_fails(tmp_path: Path) -> None:
    receipt = _write_gauntlet_receipt(tmp_path / "g.json", passed=3, total=4)
    res = evaluate_criterion(_gauntlet_criterion(receipt))
    assert res.passed is False
    assert "pass ratio" in res.detail


def test_gauntlet_verified_low_score_fails(tmp_path: Path) -> None:
    receipt = _write_gauntlet_receipt(tmp_path / "g.json", score=0.4, passed=4, total=4)
    res = evaluate_criterion(_gauntlet_criterion(receipt, min_score=0.7))
    assert res.passed is False
    assert "min_score" in res.detail


def test_gauntlet_verified_missing_required_tier_fails(tmp_path: Path) -> None:
    receipt = _write_gauntlet_receipt(tmp_path / "g.json", tiers=(1, 2))
    res = evaluate_criterion(_gauntlet_criterion(receipt, required_tiers=[1, 4]))
    assert res.passed is False
    assert "required tiers" in res.detail


def test_gauntlet_verified_malformed_receipt_field() -> None:
    res = evaluate_criterion({"id": "g", "kind": "gauntlet_verified"})
    assert res.passed is False
    assert "receipt" in res.detail


def test_gauntlet_verified_independent_verifier_rejects_self_grade(tmp_path: Path) -> None:
    receipt = _write_gauntlet_receipt(tmp_path / "g.json", verified_by="@owner")
    res = evaluate_criterion(
        _gauntlet_criterion(receipt, require_independent_verifier=True),
        track={"owner": "@owner"},
    )
    assert res.passed is False
    assert "worker must not judge" in res.detail


def test_gauntlet_verified_independent_verifier_accepts_distinct(tmp_path: Path) -> None:
    receipt = _write_gauntlet_receipt(
        tmp_path / "g.json", verified_by="@verifier", produced_by="@owner")
    res = evaluate_criterion(
        _gauntlet_criterion(receipt, require_independent_verifier=True),
        track={"owner": "@owner"},
    )
    assert res.passed is True


def test_gauntlet_verified_now_injection_is_deterministic(tmp_path: Path) -> None:
    ts = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
    receipt = _write_gauntlet_receipt(tmp_path / "g.json", ts=ts.isoformat())
    fresh = check_gauntlet_verified(str(receipt), max_age_hours=24,
                                    now=ts + timedelta(hours=1))
    stale = check_gauntlet_verified(str(receipt), max_age_hours=24,
                                    now=ts + timedelta(days=10))
    assert fresh.passed is True
    assert stale.passed is False


# --- shippable-requires-gauntlet portfolio invariant ------------------------

def test_track_policy_require_gauntlet_default_false() -> None:
    p = _portfolio([_track("a")])
    assert p["track_policy"]["require_gauntlet_for_shippable"] is False


def test_gauntlet_gate_missing_warns_by_default() -> None:
    p = _portfolio([_track("a")])
    findings: list[Finding] = []
    validate_portfolio_graph(p, findings)
    gm = [f for f in findings if f.check.startswith("gauntlet-gate-missing")]
    assert gm and gm[0].severity == "WARN"


def test_gauntlet_gate_missing_is_error_when_armed() -> None:
    p = _portfolio([_track("a")], policy={"require_gauntlet_for_shippable": True})
    findings: list[Finding] = []
    validate_portfolio_graph(p, findings)
    gm = [f for f in findings if f.check.startswith("gauntlet-gate-missing")]
    assert gm and gm[0].severity == "ERROR"


def test_gauntlet_gate_declared_is_silent() -> None:
    t = _track("a", completion_criteria=[
        {"id": "g", "kind": "gauntlet_verified", "receipt": "reports/x.json"}])
    p = _portfolio([t])
    findings: list[Finding] = []
    validate_portfolio_graph(p, findings)
    assert not any(f.check.startswith("gauntlet-gate-missing") for f in findings)
