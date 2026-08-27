"""Tests for the rigorous track-closure predicates added to check_track_status.py.

The point: "all completion criteria pass" must NOT mean shippable when the
criteria are existence-only (file_exists / file_contains) or when blocker
next-items are still open. Closure is computed from evidence strength + blocker
state — the antidote to existence-grep sign-off."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts/governance"))

from check_track_status import (  # type: ignore  # noqa: E402
    EXISTENCE_KINDS,
    FINAL_BOSS_DIMENSIONS,
    FINAL_BOSS_MIN_ROUNDS,
    RIGOROUS_KINDS,
    Finding,
    check_commit_on_main,
    check_json_collection_values_match,
    check_json_count_equals,
    check_json_count_greater_than,
    check_json_mapping_keys_nonempty,
    check_receipt_valid,
    check_test_passes,
    evaluate_criterion,
    evaluate_track,
    normalize_portfolio,
    _parse_minimal_yaml,
    validate_portfolio_graph,
)


# --------------------------------------------------------------- new predicates
def test_commit_on_main_true_for_ancestor():
    # The first commit in repo history is an ancestor of HEAD/origin/main.
    import subprocess

    root = subprocess.run(
        ["git", "rev-list", "--max-parents=0", "HEAD"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    ).stdout.split()[0]
    assert check_commit_on_main(root).passed is True


def test_commit_on_main_false_for_unknown_commit():
    # A non-existent commit cannot be proven on main -> conservative fail.
    assert check_commit_on_main("0000000000000000000000000000000000000000").passed is False


def test_test_passes_runs_and_distinguishes_pass_from_fail(tmp_path):
    good = tmp_path / "test_good.py"
    good.write_text("def test_ok():\n    assert 1 == 1\n")
    bad = tmp_path / "test_bad.py"
    bad.write_text("def test_no():\n    assert 1 == 2\n")
    assert check_test_passes(f"{good}::test_ok").passed is True
    # A failing (or trivially-passing-but-wrong) test must NOT pass.
    assert check_test_passes(f"{bad}::test_no").passed is False


def test_test_passes_marks_unverified_when_pytest_absent(monkeypatch):
    """When the test RUNNER itself is missing (minimal-deps governance gate),
    a test_passes check is unverified — executed=False, passed=False — not a
    hard failure. A missing runner is not evidence the code regressed."""
    import subprocess as _sp

    import check_track_status as cts  # type: ignore

    class _FakeProc:
        returncode = 1
        stdout = ""
        stderr = "/usr/bin/python3: No module named pytest\n"

    monkeypatch.setattr(cts.subprocess, "run", lambda *a, **k: _FakeProc())
    r = cts.check_test_passes("tests/test_whatever.py")
    assert r.passed is False
    assert r.executed is False
    assert "could not execute" in r.detail
    del _sp  # silence unused-import lint in some configs


def test_test_passes_executed_true_on_real_run(tmp_path):
    good = tmp_path / "test_good.py"
    good.write_text("def test_ok():\n    assert True\n")
    r = check_test_passes(f"{good}::test_ok")
    assert r.passed is True and r.executed is True


def test_unverified_test_runs_do_not_block_the_gate(tmp_path, monkeypatch):
    """When every test_passes criterion can only report 'could not execute'
    (the minimal-deps governance gate has no pytest), the checker must still
    exit 0. A missing runner is not evidence the code regressed."""
    import argparse

    import check_track_status as cts  # type: ignore

    track_file = tmp_path / "ACTIVE_TRACK.yaml"
    track_file.write_text(
        """
schema_version: 2
active_tracks:
  - id: minimal-test-track
    status: ACTIVE
    verified_at: "2026-06-30"
    ttl_days: 14
    completion_criteria:
      - id: behavior_test
        kind: test_passes
        test: tests/test_track_closure_rigor.py::test_rigor_kind_sets_are_disjoint_and_sane
closed_tracks: []
""".lstrip(),
        encoding="utf-8",
    )

    def _unverified(_target, timeout=180):
        return cts.CriterionResult(id="", kind="test_passes", passed=False,
                                   executed=False,
                                   detail="pytest not installed (could not execute)")

    prior = {"minimal-test-track": {"behavior_test"}}
    monkeypatch.setattr(cts, "ACTIVE_TRACK_PATH", track_file)
    monkeypatch.setattr(cts, "check_test_passes", _unverified)
    monkeypatch.setattr(cts, "_load_prior_passed", lambda _findings: prior)
    monkeypatch.setattr(cts, "emit_reports", lambda *_a, **_k: None)
    args = argparse.Namespace(enforce_ttl=False)
    assert cts.run(args) == 0  # unverified must not block


def test_receipt_valid_requires_keys(tmp_path):
    receipt = tmp_path / "r.json"
    receipt.write_text('{"closeout_state": "positive_lift_candidate", "score": 1.0}')
    assert check_receipt_valid(str(receipt), ["closeout_state", "score"]).passed is True
    assert check_receipt_valid(str(receipt), ["missing_key"]).passed is False
    assert check_receipt_valid(str(tmp_path / "nope.json"), []).passed is False


def test_json_count_equals_counts_structured_rows(tmp_path):
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({
            "loop_statuses": [
                {"verdict": "HARNESS_PROVEN"},
                {"verdict": "HARNESS_PROVEN"},
                {"verdict": "BLOCKED"},
            ],
        }),
        encoding="utf-8",
    )

    assert check_json_count_equals(str(audit), "loop_statuses", "verdict", "HARNESS_PROVEN", 2).passed
    assert not check_json_count_equals(str(audit), "loop_statuses", "verdict", "CLOSED_LIVE", 1).passed
    assert "0 == 0" in check_json_count_equals(
        str(audit), "loop_statuses", "verdict", "CLOSED_LIVE", 0
    ).detail
    assert check_json_count_greater_than(
        str(audit), "loop_statuses", "verdict", "HARNESS_PROVEN", 0
    ).passed
    assert not check_json_count_greater_than(
        str(audit), "loop_statuses", "verdict", "CLOSED_LIVE", 0
    ).passed
    assert check_json_collection_values_match(
        str(audit),
        "loop_statuses",
        "verdict",
        "verdict",
        {"HARNESS_PROVEN": "HARNESS_PROVEN", "BLOCKED": "BLOCKED"},
    ).passed
    assert not check_json_collection_values_match(
        str(audit),
        "loop_statuses",
        "verdict",
        "verdict",
        {"HARNESS_PROVEN": "BLOCKED"},
    ).passed


def test_json_mapping_keys_nonempty_checks_required_keys(tmp_path):
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({"live_owner_surface_criteria": {"loop1": "criterion", "loop2": ""}}),
        encoding="utf-8",
    )

    assert check_json_mapping_keys_nonempty(
        str(audit), "live_owner_surface_criteria", ["loop1"]
    ).passed
    assert not check_json_mapping_keys_nonempty(
        str(audit), "live_owner_surface_criteria", ["loop1", "loop2"]
    ).passed


def test_minimal_yaml_parser_unquotes_mapping_keys():
    parsed = _parse_minimal_yaml(
        """
expected:
  "1": HARNESS_PROVEN
  '2': BLOCKED
  3: CLOSED_LIVE
""".strip()
    )

    assert parsed["expected"] == {
        "1": "HARNESS_PROVEN",
        "2": "BLOCKED",
        3: "CLOSED_LIVE",
    }


def test_new_kinds_dispatch_through_evaluate_criterion():
    r = evaluate_criterion({"id": "x", "kind": "commit_on_main", "commit": "deadbeef"})
    assert r.kind == "commit_on_main" and r.passed is False
    # malformed -> failing result, never an exception
    assert evaluate_criterion({"id": "y", "kind": "test_passes"}).passed is False
    assert evaluate_criterion({"id": "z", "kind": "receipt_valid"}).passed is False
    assert evaluate_criterion({"id": "j", "kind": "json_count_equals"}).passed is False
    assert evaluate_criterion({"id": "g", "kind": "json_count_greater_than"}).passed is False
    assert evaluate_criterion({
        "id": "jv",
        "kind": "json_count_equals",
        "file": "reports/loop_closure/cybernetics_codex/latest_audit.json",
        "collection": "loop_statuses",
        "field": "verdict",
        "expected": 0,
    }).passed is False
    assert evaluate_criterion({
        "id": "gv",
        "kind": "json_count_greater_than",
        "file": "reports/loop_closure/cybernetics_codex/latest_audit.json",
        "collection": "loop_statuses",
        "field": "verdict",
        "threshold": 0,
    }).passed is False
    assert evaluate_criterion({"id": "m", "kind": "json_collection_values_match"}).passed is False
    assert evaluate_criterion({"id": "k", "kind": "json_mapping_keys_nonempty"}).passed is False


def test_json_count_criteria_require_explicit_value() -> None:
    base = {
        "file": "reports/loop_closure/cybernetics_codex/latest_audit.json",
        "collection": "loop_statuses",
        "field": "verdict",
    }

    equals_missing_value = evaluate_criterion({
        "id": "j",
        "kind": "json_count_equals",
        "expected": 0,
        **base,
    })
    greater_missing_value = evaluate_criterion({
        "id": "g",
        "kind": "json_count_greater_than",
        "threshold": 0,
        **base,
    })

    assert equals_missing_value.passed is False
    assert "missing value" in equals_missing_value.detail
    assert greater_missing_value.passed is False
    assert "missing value" in greater_missing_value.detail


# ------------------------------------------------------------------ rigor gate
def _track(criteria, *, next_items=None, status="ACTIVE"):
    return {
        "id": "t",
        "status": status,
        "completion_criteria": criteria,
        "next_items": next_items or [],
    }


def test_existence_only_criteria_are_not_shippable():
    """All file_exists/file_contains pass -> criteria_pass True, but NOT shippable
    (no rigorous evidence). This is the core anti-theater invariant."""
    t = _track([
        {"id": "a", "kind": "file_exists", "file": "CLAUDE.md"},
        {"id": "b", "kind": "file_contains", "file": "CLAUDE.md", "pattern": "dharma"},
    ])
    r = evaluate_track(t)
    assert r["criteria_pass"] is True
    assert r["shippable"] is False
    assert r["has_rigorous_evidence"] is False
    assert any("existence-only" in b for b in r["ship_blocks"])


def test_prerequisite_receipt_does_not_count_as_completion_or_rigorous_evidence(
    tmp_path,
):
    """Admission authority can be a prerequisite without inflating product progress."""
    receipt = tmp_path / "authority.json"
    receipt.write_text('{"schema":"authority.v1"}', encoding="utf-8")
    t = {
        "id": "t",
        "status": "ACTIVE",
        "prerequisites": [
            {
                "id": "authority",
                "kind": "receipt_valid",
                "file": str(receipt),
                "requires_keys": ["schema"],
            }
        ],
        "completion_criteria": [
            {"id": "surface", "kind": "file_exists", "file": "CLAUDE.md"}
        ],
        "next_items": [],
    }

    result = evaluate_track(t)

    assert result["prereqs_ok"] is True
    assert result["passed"] == 1
    assert result["total"] == 1
    assert result["has_rigorous_evidence"] is False
    assert result["shippable"] is False


def _root_commit() -> str:
    import subprocess

    return subprocess.run(
        ["git", "rev-list", "--max-parents=0", "HEAD"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    ).stdout.split()[0]


def test_open_blocker_blocks_shippable_even_with_rigorous_evidence():
    t = _track(
        [{"id": "c", "kind": "commit_on_main", "commit": _root_commit()}],
        next_items=[{"id": 1, "what": "do the thing", "blocker": True}],
    )
    r = evaluate_track(t)
    assert r["has_rigorous_evidence"] is True  # the commit IS on main
    assert r["open_blocker_count"] == 1
    assert r["shippable"] is False  # ...but an open blocker still blocks it
    assert any("open blocker" in b for b in r["ship_blocks"])


def test_ship_veto_blocks_shippable_even_when_criteria_pass(tmp_path):
    audit = tmp_path / "audit.json"
    audit.write_text(
        json.dumps({"loop_statuses": [{"verdict": "HARNESS_PROVEN"}]}),
        encoding="utf-8",
    )
    t = _track([{"id": "c", "kind": "commit_on_main", "commit": _root_commit()}])
    t["ship_vetoes"] = [{
        "id": "harness_blocks_ship",
        "kind": "json_count_greater_than",
        "file": str(audit),
        "collection": "loop_statuses",
        "field": "verdict",
        "value": "HARNESS_PROVEN",
        "threshold": 0,
    }]

    r = evaluate_track(t)

    assert r["criteria_pass"] is True
    assert r["shippable"] is False
    assert r["active_ship_veto_count"] == 1
    assert any("active ship veto" in b for b in r["ship_blocks"])


def test_rigorous_evidence_plus_no_blockers_earns_shippable():
    t = _track(
        [
            {"id": "a", "kind": "file_exists", "file": "CLAUDE.md"},
            {"id": "b", "kind": "commit_on_main", "commit": _root_commit()},
        ],
        next_items=[{"id": 1, "what": "polish", "blocker": False}],
    )
    r = evaluate_track(t)
    assert r["has_rigorous_evidence"] is True
    assert r["ship_blocks"] == []
    assert r["shippable"] is True


def test_substrate_trusted_target_requires_final_boss_review():
    """Generic rigorous evidence proves a verified slice, not trusted substrate.

    This is the Active Track Final Boss invariant: the last gate cannot let a
    track become production/substrate truth until the final_boss_review packet
    exists and passes the profile-specific bar.
    """
    t = _track(
        [{"id": "landed", "kind": "commit_on_main", "commit": _root_commit()}],
    )
    t.update({
        "target_closure_kind": "SUBSTRATE_TRUSTED",
        "graduation_profile": "runtime_transport",
    })
    r = evaluate_track(t)
    assert r["criteria_pass"] is True
    assert r["has_rigorous_evidence"] is True
    assert r["shippable"] is False
    assert r["final_boss_blocks"]
    assert any("final_boss_review" in block for block in r["final_boss_blocks"])


def test_verified_slice_target_can_close_without_final_boss_review():
    t = _track(
        [{"id": "landed", "kind": "commit_on_main", "commit": _root_commit()}],
    )
    t.update({
        "target_closure_kind": "VERIFIED_SLICE",
        "graduation_profile": "runtime_transport",
    })
    r = evaluate_track(t)
    assert r["target_closure_kind"] == "VERIFIED_SLICE"
    assert r["final_boss_blocks"] == []
    assert r["shippable"] is True


def test_recent_closed_track_requires_typed_closure_kind():
    p = normalize_portfolio({
        "schema_version": 2,
        "spine_objectives": [{"id": "obj-a", "name": "A"}],
        "active_tracks": [{
            "id": "keep-active",
            "status": "ACTIVE",
            "serves": "obj-a",
            "verified_at": "2026-06-30",
            "ttl_days": 21,
        }],
        "closed_tracks": [{
            "id": "new-closed",
            "status": "SHIPPED",
            "closed_at": "2026-07-01",
            "serves": "obj-a",
        }],
    })
    findings: list[Finding] = []
    validate_portfolio_graph(p, findings)
    assert any(f.check == "closure-kind-missing:new-closed" for f in findings)


def test_closed_substrate_claim_requires_final_boss_review():
    p = normalize_portfolio({
        "schema_version": 2,
        "spine_objectives": [{"id": "obj-a", "name": "A"}],
        "active_tracks": [{
            "id": "keep-active",
            "status": "ACTIVE",
            "serves": "obj-a",
            "verified_at": "2026-06-30",
            "ttl_days": 21,
        }],
        "closed_tracks": [{
            "id": "new-closed",
            "status": "SHIPPED",
            "closed_at": "2026-07-01",
            "serves": "obj-a",
            "closure_kind": "SUBSTRATE_TRUSTED",
            "graduation_profile": "runtime_transport",
        }],
    })
    findings: list[Finding] = []
    validate_portfolio_graph(p, findings)
    assert any(f.check == "final-boss-block:new-closed" for f in findings)


def _valid_final_boss_dossier(tmp_path, *, track_id="t", kind="SUBSTRATE_TRUSTED", profile="generic"):
    path = tmp_path / "dossier.json"
    path.write_text(
        json.dumps({
            "track_id": track_id,
            "target_closure_kind": kind,
            "graduation_profile": profile,
            "review_dimensions": sorted(FINAL_BOSS_DIMENSIONS),
            "profile_requirements": {
                "required_evidence_themes": ["claim boundary is explicit"],
                "hard_rejects": ["confidence language replaces executable evidence"],
            },
        }),
        encoding="utf-8",
    )
    return path


def _thin_final_boss_dossier(tmp_path, *, track_id="t", kind="SUBSTRATE_TRUSTED", profile="generic"):
    path = tmp_path / "thin-dossier.json"
    path.write_text(
        json.dumps({
            "track_id": track_id,
            "target_closure_kind": kind,
            "graduation_profile": profile,
            "review_dimensions": sorted(FINAL_BOSS_DIMENSIONS),
        }),
        encoding="utf-8",
    )
    return path


def _council_receipt(tmp_path, *, gate="pass_fullness", score=100, blockers=None, name="council"):
    path = tmp_path / f"{name}.json"
    critics = []
    for i in range(6):
        critics.append({
            "lane_id": f"lane-{i}",
            "ok": True,
            "required": True,
            "parsed": {
                "verdict": "approve",
                "score": score,
                "explicit_disagreement": "",
            },
        })
    path.write_text(
        json.dumps({
            "conviction_gate": gate,
            "target_score": 100,
            "score_min": score,
            "critic_count": 6,
            "required_critic_count": 6,
            "blockers": blockers or [],
            "persistent_agent_witness": {"fresh": True},
            "critics": critics,
        }),
        encoding="utf-8",
    )
    return path


def _final_boss_coverage(receipts, *, rounds=FINAL_BOSS_MIN_ROUNDS):
    rows = []
    receipt_iter = iter(receipts)
    for round_index in range(1, rounds + 1):
        for dimension in sorted(FINAL_BOSS_DIMENSIONS):
            rows.append({
                "round": round_index,
                "dimension": dimension,
                "council_receipt": str(next(receipt_iter)),
            })
    return rows


def test_failed_council_receipt_cannot_satisfy_substrate_claim(tmp_path):
    dossier = _valid_final_boss_dossier(tmp_path)
    receipt = _council_receipt(tmp_path, gate="hold_blockers", score=100, blockers=["real issue"])
    t = _track(
        [{"id": "landed", "kind": "commit_on_main", "commit": _root_commit()}],
    )
    t.update({
        "target_closure_kind": "SUBSTRATE_TRUSTED",
        "graduation_profile": "generic",
        "final_boss_review": {
            "dossier": str(dossier),
            "council_receipt": str(receipt),
            "reviewer_count": 6,
            "score_min": 100,
            "explicit_disagreements": 0,
            "local_verifiers_passed": True,
            "local_verifier_results": [{
                "id": "track_status",
                "command": "python scripts/governance/check_track_status.py",
                "passed": True,
                "returncode": 0,
            }],
            "rounds": 1,
            "dimensions": sorted(FINAL_BOSS_DIMENSIONS),
        },
    })
    r = evaluate_track(t)
    assert r["shippable"] is False
    assert any("conviction_gate" in block for block in r["final_boss_blocks"])
    assert any("has blockers" in block for block in r["final_boss_blocks"])


def test_thin_final_boss_dossier_cannot_satisfy_substrate_claim(tmp_path):
    dossier = _thin_final_boss_dossier(tmp_path)
    receipts = [
        _council_receipt(tmp_path, name=f"council-{i}")
        for i in range(FINAL_BOSS_MIN_ROUNDS * len(FINAL_BOSS_DIMENSIONS))
    ]
    t = _track(
        [{"id": "landed", "kind": "commit_on_main", "commit": _root_commit()}],
    )
    t.update({
        "target_closure_kind": "SUBSTRATE_TRUSTED",
        "graduation_profile": "generic",
        "final_boss_review": {
            "dossier": str(dossier),
            "council_receipt": str(receipts[0]),
            "council_receipts": [str(receipt) for receipt in receipts],
            "council_coverage": _final_boss_coverage(receipts),
            "reviewer_count": 6,
            "score_min": 100,
            "explicit_disagreements": 0,
            "local_verifiers_passed": True,
            "local_verifier_results": [{
                "id": "track_status",
                "command": "python scripts/governance/check_track_status.py",
                "passed": True,
                "returncode": 0,
            }],
            "rounds": FINAL_BOSS_MIN_ROUNDS,
            "dimensions": sorted(FINAL_BOSS_DIMENSIONS),
        },
    })
    r = evaluate_track(t)
    assert r["shippable"] is False
    assert any("profile_requirements missing" in block for block in r["final_boss_blocks"])


def test_valid_final_boss_receipt_allows_substrate_claim(tmp_path):
    dossier = _valid_final_boss_dossier(tmp_path)
    receipts = [
        _council_receipt(tmp_path, name=f"council-{i}")
        for i in range(FINAL_BOSS_MIN_ROUNDS * len(FINAL_BOSS_DIMENSIONS))
    ]
    t = _track(
        [{"id": "landed", "kind": "commit_on_main", "commit": _root_commit()}],
    )
    t.update({
        "target_closure_kind": "SUBSTRATE_TRUSTED",
        "graduation_profile": "generic",
        "final_boss_review": {
            "dossier": str(dossier),
            "council_receipt": str(receipts[0]),
            "council_receipts": [str(receipt) for receipt in receipts],
            "council_coverage": _final_boss_coverage(receipts),
            "reviewer_count": 6,
            "score_min": 100,
            "explicit_disagreements": 0,
            "local_verifiers_passed": True,
            "local_verifier_results": [{
                "id": "track_status",
                "command": "python scripts/governance/check_track_status.py",
                "passed": True,
                "returncode": 0,
            }],
            "rounds": FINAL_BOSS_MIN_ROUNDS,
            "dimensions": sorted(FINAL_BOSS_DIMENSIONS),
        },
    })
    r = evaluate_track(t)
    assert r["final_boss_blocks"] == []
    assert r["shippable"] is True


def test_rigor_kind_sets_are_disjoint_and_sane():
    assert RIGOROUS_KINDS.isdisjoint(EXISTENCE_KINDS)
    assert "test_passes" in RIGOROUS_KINDS and "commit_on_main" in RIGOROUS_KINDS
    assert "json_count_equals" in RIGOROUS_KINDS
    assert "json_count_greater_than" in RIGOROUS_KINDS
    assert "json_collection_values_match" in RIGOROUS_KINDS
    assert "json_mapping_keys_nonempty" in RIGOROUS_KINDS
    assert "file_exists" in EXISTENCE_KINDS and "file_contains" in EXISTENCE_KINDS


def test_provider_routing_track_is_closed_with_rigorous_evidence_receipt():
    """Once provider-routing graduates, it must leave an auditable closed-track
    receipt instead of remaining active just to keep this test green."""
    from check_track_status import _parse_minimal_yaml, normalize_portfolio

    raw = _parse_minimal_yaml((REPO_ROOT / "docs/governance/ACTIVE_TRACK.yaml").read_text())
    portfolio = normalize_portfolio(raw)
    track = next(
        t for t in portfolio["closed_tracks"]
        if t.get("id") == "provider-routing-consolidation-2026-06"
    )
    assert track["status"] == "SHIPPED"
    assert track["closure_kind"] == "VERIFIED_SLICE"
    assert track["graduation_profile"] == "provider_routing"
    evidence = "\n".join(track.get("evidence") or [])
    assert "ACTIVE_TRACK_CLOSEOUT_2026-06-30.md" in evidence
    assert "test_precedence_explicit_beats_power_beats_cost" in evidence
    assert "bc110d84" in evidence


def test_nats_track_is_verified_slice_not_production_substrate():
    from check_track_status import _parse_minimal_yaml, normalize_portfolio

    raw = _parse_minimal_yaml((REPO_ROOT / "docs/governance/ACTIVE_TRACK.yaml").read_text())
    portfolio = normalize_portfolio(raw)
    track = next(
        t for t in portfolio["closed_tracks"]
        if t.get("id") == "runtime-truth-nats-2026-06"
    )
    assert track["status"] == "SHIPPED"
    assert track["closure_kind"] == "VERIFIED_SLICE"
    assert track["graduation_profile"] == "runtime_transport"
    assert track.get("closure_kind") != "SUBSTRATE_TRUSTED"


def test_test_passes_track_eval_is_repo_root_anchored(tmp_path, monkeypatch):
    """Track criteria are authored as repo-relative paths and pytest targets.
    Evaluation must not depend on the caller's current working directory."""
    monkeypatch.chdir(tmp_path)

    track = _track(
        [
            {
                "id": "precedence_test_exists",
                "kind": "file_contains",
                "file": "tests/test_provider_routing_explicit.py",
                "pattern": "test_precedence_explicit_beats_power_beats_cost",
            },
            {
                "id": "precedence_test_passes",
                "kind": "test_passes",
                "test": "tests/test_provider_routing_explicit.py::test_precedence_explicit_beats_power_beats_cost",
            },
        ]
    )
    r = evaluate_track(track)
    assert r["criteria_pass"] is True, [c.detail for c in r["completion"] if not c.passed]
    assert r["shippable"] is True, r["ship_blocks"]
