"""Governance tests for the ACTIVE_TRACK self-healing layer.

These tests guard the governance system itself \u2014 the prerequisites for
ACTIVE_TRACK.yaml, the renderer, and the track-status checker. They are
intentionally small and fast: they assert structural invariants, not the
contents of the current track.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
ACTIVE_TRACK = REPO_ROOT / "docs/governance/ACTIVE_TRACK.yaml"
SOURCE_REPORTS_DIR = REPO_ROOT / "reports/governance"
DERIVED_REPORT_NAMES = {
    "active_track_evidence.json",
    "active_track_evidence.md",
    "track_portfolio.json",
}

CHECK_SCRIPT = REPO_ROOT / "scripts/governance/check_track_status.py"
RENDER_SCRIPT = REPO_ROOT / "scripts/governance/render_active_track_includes.py"
ONBOARD_SCRIPT = REPO_ROOT / "scripts/governance/agent_onboard.py"

MANAGED_FILES = [
    REPO_ROOT / "CLAUDE.md",
    REPO_ROOT / "docs/governance/SOVEREIGN_MANIFEST.md",
]


def _run(
    script: Path, *args: str, timeout: int = 60, skip_commands: bool = False,
) -> subprocess.CompletedProcess:
    env = None
    if skip_commands:
        # This suite already executes every pytest-battery criterion as
        # first-class tests; re-running them inside the checker is quadratic
        # (suite → checker → suite) and grows with the portfolio. The checker
        # records them as UNVERIFIED under this flag — never a fake pass.
        import os

        env = {**os.environ, "DHARMA_TRACK_STATUS_SKIP_COMMANDS": "1"}
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=timeout, env=env,
    )


def _report_snapshot(directory: Path) -> dict[str, tuple[int, bytes] | None]:
    snapshot: dict[str, tuple[int, bytes] | None] = {}
    for name in DERIVED_REPORT_NAMES:
        path = directory / name
        snapshot[name] = (
            (path.stat().st_mtime_ns, path.read_bytes()) if path.exists() else None
        )
    return snapshot


def test_active_track_yaml_exists() -> None:
    assert ACTIVE_TRACK.exists(), "ACTIVE_TRACK.yaml is the single source of truth for the current track."


def test_active_track_loads() -> None:
    sys.path.insert(0, str(REPO_ROOT / "scripts/governance"))
    from check_track_status import (  # type: ignore
        load_active_track, normalize_portfolio, SUPPORTED_SCHEMA_VERSIONS)

    track = load_active_track(ACTIVE_TRACK)
    assert track.get("schema_version") in SUPPORTED_SCHEMA_VERSIONS
    p = normalize_portfolio(track)
    assert p["active_tracks"], "ACTIVE_TRACK.yaml must declare at least one active track."
    for t in p["active_tracks"]:
        assert t.get("id"), "every track requires an id."
        assert t.get("status") in {"ACTIVE", "SHIPPABLE"}, \
            f"unexpected status: {t.get('status')!r}"
        assert t.get("verified_at"), f"{t.get('id')} requires verified_at."
    # v2: every active track must serve a declared spine objective.
    spine_ids = {o.get("id") for o in p["spine_objectives"]}
    if spine_ids:
        for t in p["active_tracks"]:
            assert t.get("serves") in spine_ids, \
                f"{t.get('id')} serves '{t.get('serves')}' not in spine objectives {sorted(spine_ids)}"


@pytest.mark.timeout(270)
def test_check_track_status_runs(tmp_path: Path) -> None:
    """The checker runs to completion and writes evidence JSON."""
    # Command criteria are skipped here (recorded UNVERIFIED): this suite
    # already runs every pytest-battery criterion directly, and executing
    # them again inside the checker made the checker's wall-clock grow with
    # the portfolio until it starved CI runners (2026-07-12, PR #894).
    reports_dir = tmp_path / "governance-reports"
    source_before = _report_snapshot(SOURCE_REPORTS_DIR)
    result = _run(
        CHECK_SCRIPT,
        "--warn-only",
        "--reports-dir",
        str(reports_dir),
        timeout=240,
        skip_commands=True,
    )
    assert result.returncode == 0, result.stderr
    assert {path.name for path in reports_dir.iterdir()} == DERIVED_REPORT_NAMES
    payload = json.loads((reports_dir / "active_track_evidence.json").read_text())
    assert "active_track_id" in payload
    assert "criteria" in payload
    assert isinstance(payload["criteria"], list)
    assert _report_snapshot(SOURCE_REPORTS_DIR) == source_before


@pytest.mark.parametrize(
    ("enforce_ttl", "expected_severity", "expected_exit"),
    [(False, "WARN", 0), (True, "ERROR", 1)],
)
def test_freshness_regression_is_warning_until_ttl_enforced(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    enforce_ttl: bool,
    expected_severity: str,
    expected_exit: int,
) -> None:
    """Elapsed receipt age follows the same PR/scheduled authority split as track TTL."""
    import argparse

    sys.path.insert(0, str(REPO_ROOT / "scripts/governance"))
    import check_track_status as cts  # type: ignore

    receipt = tmp_path / "stale-receipt.json"
    receipt.write_text(
        json.dumps({"claim_id": "C1", "produced_at": "2000-01-01T00:00:00Z"}),
        encoding="utf-8",
    )
    track_file = tmp_path / "ACTIVE_TRACK.yaml"
    track_file.write_text(
        f"""
schema_version: 2
active_tracks:
  - id: freshness-track
    status: ACTIVE
    verified_at: "2099-01-01"
    ttl_days: 14
    completion_criteria:
      - id: fresh_receipt
        kind: receipt_valid
        file: "{receipt.as_posix()}"
        requires_keys:
          - claim_id
        fresh_ttl_days: 7
closed_tracks: []
""".lstrip(),
        encoding="utf-8",
    )
    emitted: list[cts.Finding] = []

    def _capture(findings, *_args, **_kwargs) -> None:
        emitted.extend(findings)

    monkeypatch.setattr(cts, "ACTIVE_TRACK_PATH", track_file)
    monkeypatch.setattr(
        cts,
        "_load_prior_passed",
        lambda _findings: {"freshness-track": {"fresh_receipt"}},
    )
    monkeypatch.setattr(cts, "emit_reports", _capture)

    args = argparse.Namespace(
        enforce_ttl=enforce_ttl,
        base=None,
        reports_dir=tmp_path / "reports",
    )
    assert cts.run(args) == expected_exit
    regression = next(
        finding
        for finding in emitted
        if finding.check == "regression:freshness-track:fresh_receipt"
    )
    assert regression.severity == expected_severity


@pytest.mark.parametrize("enforce_ttl", [False, True])
def test_stale_low_mutation_regression_remains_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    enforce_ttl: bool,
) -> None:
    """Freshness cannot downgrade a concurrent mutation-score regression."""
    import argparse

    sys.path.insert(0, str(REPO_ROOT / "scripts/governance"))
    import check_track_status as cts  # type: ignore

    report = tmp_path / "mutation-score.json"
    report.write_text(
        json.dumps(
            {
                "score": 0.5,
                "killed": 1,
                "total": 2,
                "produced_at": "2000-01-01T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    track_file = tmp_path / "ACTIVE_TRACK.yaml"
    track_file.write_text(
        f"""
schema_version: 2
active_tracks:
  - id: mutation-track
    status: ACTIVE
    verified_at: "2099-01-01"
    ttl_days: 14
    completion_criteria:
      - id: mutation_floor
        kind: mutation_score_gte
        file: "{report.as_posix()}"
        threshold: 0.6
        fresh_ttl_days: 7
closed_tracks: []
""".lstrip(),
        encoding="utf-8",
    )
    emitted: list[cts.Finding] = []

    def _capture(findings, *_args, **_kwargs) -> None:
        emitted.extend(findings)

    monkeypatch.setattr(cts, "ACTIVE_TRACK_PATH", track_file)
    monkeypatch.setattr(
        cts,
        "_load_prior_passed",
        lambda _findings: {"mutation-track": {"mutation_floor"}},
    )
    monkeypatch.setattr(cts, "emit_reports", _capture)

    args = argparse.Namespace(
        enforce_ttl=enforce_ttl,
        base=None,
        reports_dir=tmp_path / "reports",
    )
    assert cts.run(args) == 1
    regression = next(
        finding
        for finding in emitted
        if finding.check == "regression:mutation-track:mutation_floor"
    )
    assert regression.severity == "ERROR"
    assert "0.50 < 0.60" in regression.message
    assert "stale" in regression.message


def test_managed_blocks_in_sync() -> None:
    """All managed files have the ACTIVE_TRACK block matching the YAML."""
    result = _run(RENDER_SCRIPT, "--check")
    assert result.returncode == 0, (
        "Managed governance blocks are out of sync with ACTIVE_TRACK.yaml. "
        "Run: python3 scripts/governance/render_active_track_includes.py\n\n"
        f"stderr:\n{result.stderr}"
    )


def test_managed_files_have_markers() -> None:
    for path in MANAGED_FILES:
        text = path.read_text(encoding="utf-8")
        assert "<!-- ACTIVE_TRACK:START -->" in text, \
            f"{path} missing ACTIVE_TRACK start marker"
        assert "<!-- ACTIVE_TRACK:END -->" in text, \
            f"{path} missing ACTIVE_TRACK end marker"


@pytest.mark.timeout(75)
def test_onboard_command_succeeds() -> None:
    """agent_onboard.py runs end-to-end and prints the active track section."""
    result = _run(ONBOARD_SCRIPT)
    # Return code may be 1 if prereqs fail; that's a real signal, not a test failure.
    # We just check the command produced the structural sections.
    assert "ACTIVE PORTFOLIO" in result.stdout
    assert "LIVING AXIOMS" in result.stdout
    assert "WHAT TO DO NEXT" in result.stdout


def test_underclaim_detector_flags_shipped_but_open_items() -> None:
    """A next-item whose linked evidence criterion passes must WARN track-underclaim.

    This is the inverse of the false-shippable trap: every other defense catches
    claims ahead of reality; this one catches the ledger falling behind it.
    """
    sys.path.insert(0, str(REPO_ROOT / "scripts/governance"))
    from check_track_status import evaluate_track  # type: ignore

    track = {
        "id": "t-underclaim",
        "status": "ACTIVE",
        "completion_criteria": [
            {"id": "shipped_thing", "kind": "file_exists",
             "file": "docs/governance/ACTIVE_TRACK.yaml"},
        ],
        "next_items": [
            # open blocker whose evidence already passes -> underclaim
            {"id": 1, "what": "(blocker) build the shipped thing",
             "kind": "code", "blocker": True,
             "evidence_criterion": "shipped_thing"},
            # reconciled in prose -> NOT an underclaim
            {"id": 2, "what": "DONE 2026-07-03: other thing", "kind": "code",
             "blocker": False, "evidence_criterion": "shipped_thing"},
            # evidence criterion does not pass -> NOT an underclaim
            {"id": 3, "what": "future thing", "kind": "code", "blocker": False,
             "evidence_criterion": "no_such_criterion"},
            # no evidence link -> NOT an underclaim (opt-in mechanism)
            {"id": 4, "what": "unlinked thing", "kind": "code", "blocker": True},
        ],
    }
    r = evaluate_track(track)
    ucs = r["underclaims"]
    assert [uc["item_id"] for uc in ucs] == [1]
    assert ucs[0]["evidence_criterion"] == "shipped_thing"
    assert ucs[0]["blocker"] is True


def test_outcome_verdict_gates_shippability(tmp_path: Path) -> None:
    """A digest-valid receipt that reports a non-passing verdict (AMBER, 45%)
    must block shippability — the exact company-builder-parity false positive:
    the receipt_valid criterion proves the scoreboard is real, this proves it
    says the game was won. A GREEN verdict passes; no receipt is unaffected."""
    sys.path.insert(0, str(REPO_ROOT / "scripts/governance"))
    from check_track_status import _outcome_verdict_blocks  # type: ignore

    def _receipt(verdict: str, **extra) -> str:
        rel = f"reports/r_{verdict.lower()}.json"
        payload = {"schema": "x", "verdict": verdict, **extra}
        (tmp_path / "reports").mkdir(exist_ok=True)
        (tmp_path / rel).write_text(json.dumps(payload), encoding="utf-8")
        return rel

    amber = {"completion_criteria": [
        {"id": "r", "kind": "receipt_valid",
         "file": _receipt("AMBER", parity_pct=45.0)}]}
    blocks = _outcome_verdict_blocks(amber, repo_root=tmp_path)
    assert blocks and "AMBER" in blocks[0] and "45.0" in blocks[0]

    green = {"completion_criteria": [
        {"id": "r", "kind": "receipt_valid", "file": _receipt("GREEN")}]}
    assert _outcome_verdict_blocks(green, repo_root=tmp_path) == []

    # A track with no receipt_valid criteria is untouched.
    assert _outcome_verdict_blocks(
        {"completion_criteria": [{"id": "x", "kind": "file_exists", "file": "y"}]},
        repo_root=tmp_path,
    ) == []

    # A receipt with NO `verdict` key is opt-out: it is not a scoreboard, so the
    # gate stays silent (blocking every verdict-less receipt would over-fire).
    no_verdict_rel = "reports/r_none.json"
    (tmp_path / no_verdict_rel).write_text(
        json.dumps({"schema": "x", "parity_pct": 12.0}), encoding="utf-8")
    assert _outcome_verdict_blocks(
        {"completion_criteria": [
            {"id": "r", "kind": "receipt_valid", "file": no_verdict_rel}]},
        repo_root=tmp_path,
    ) == []

    # But a PRESENT-yet-malformed (non-string) verdict must NOT bypass the gate:
    # `verdict: ["AMBER"]` / `verdict: null` are treated as failing, not skipped
    # (greptile P1, PR #900).
    for bad in ([{"AMBER": True}], None, 45, ["AMBER"]):
        bad_rel = f"reports/r_bad_{abs(hash(repr(bad)))}.json"
        (tmp_path / bad_rel).write_text(
            json.dumps({"schema": "x", "verdict": bad}), encoding="utf-8")
        got = _outcome_verdict_blocks(
            {"completion_criteria": [
                {"id": "r", "kind": "receipt_valid", "file": bad_rel}]},
            repo_root=tmp_path,
        )
        assert got and "malformed" in got[0], f"malformed verdict {bad!r} bypassed the gate"


def test_outcome_verdict_triggers_hard_false_shippable_claim() -> None:
    """A track that DECLARES `status: shippable` while its own outcome receipt
    reports a non-passing verdict must trip the hard `false-shippable-claim`
    ERROR — not merely the advisory ship_block. The outcome-verdict signal reads
    committed file data, so it is always a REAL false claim, never a "could not
    observe" (devin, PR #900)."""
    sys.path.insert(0, str(REPO_ROOT / "scripts/governance"))
    from check_track_status import _real_false_shippable_claim  # type: ignore

    # A shippable declaration on a passing (GREEN) receipt is NOT a false claim.
    green_result = {"shippable": True, "completion": [], "prereqs": [],
                    "open_blocker_count": 0, "active_ship_veto_count": 0,
                    "outcome_verdict_blocks": []}
    assert _real_false_shippable_claim({"status": "shippable"}, green_result) is False

    # Same declaration, but evaluate_track said not-shippable BECAUSE the outcome
    # receipt is non-passing (and NOTHING else is wrong: rigorous criterion
    # declared, nothing executed-failed, no open blockers). Pre-fix this slipped
    # through real_false_claim; it must now fire.
    from check_track_status import CriterionResult  # type: ignore

    passing_receipt = CriterionResult(
        id="r", kind="receipt_valid", passed=True, detail="digest ok")
    amber_result = {
        "shippable": False,
        "completion": [passing_receipt],
        "prereqs": [],
        "open_blocker_count": 0,
        "active_ship_veto_count": 0,
        "outcome_verdict_blocks": ["outcome receipt reports verdict='AMBER' ..."],
    }
    assert _real_false_shippable_claim({"status": "shippable"}, amber_result) is True

    # An ACTIVE (non-shippable-declaring) track is never a false claim, however
    # bad its receipt — the ERROR is only for tracks that CLAIM shippable.
    assert _real_false_shippable_claim({"status": "ACTIVE"}, amber_result) is False


@pytest.mark.timeout(270)
def test_underclaims_surface_in_evidence_payload(tmp_path: Path) -> None:
    """Every track payload carries the underclaims field, and any underclaim in
    the payload also surfaces as a WARN line in the checker output — the ledger
    can fall behind reality, but never silently."""
    # Same command-skip doctrine as test_check_track_status_runs above.
    reports_dir = tmp_path / "governance-reports"
    source_before = _report_snapshot(SOURCE_REPORTS_DIR)
    result = _run(
        CHECK_SCRIPT,
        "--reports-dir",
        str(reports_dir),
        timeout=240,
        skip_commands=True,
    )
    assert {path.name for path in reports_dir.iterdir()} == DERIVED_REPORT_NAMES
    payload = json.loads(
        (reports_dir / "active_track_evidence.json").read_text(encoding="utf-8")
    )
    out = result.stdout + result.stderr
    for tr in payload.get("active_tracks", []):
        assert "underclaims" in tr, f"track {tr.get('id')} missing underclaims field"
        for uc in tr["underclaims"]:
            assert f"track-underclaim:{tr['id']}:{uc['item_id']}" in out
    assert _report_snapshot(SOURCE_REPORTS_DIR) == source_before
