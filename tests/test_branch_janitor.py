"""Policy tests for scripts/governance/branch_janitor.py.

Fixture-only: no git fetch, no gh, no network. The live collectors are
bypassed via classify_* directly and via the --branches-json/--prs-json
fixture path of main().
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "governance" / "branch_janitor.py"
REGISTRY = REPO_ROOT / "docs" / "governance" / "BRANCH_REGISTRY.yaml"

NOW = datetime(2026, 7, 4, 12, 0, 0, tzinfo=timezone.utc)


def _load_module():
    spec = importlib.util.spec_from_file_location("branch_janitor", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


bj = _load_module()


def _branch(name: str, tip: str = "a" * 40, days_idle: int = 100) -> "bj.Branch":
    return bj.Branch(name=name, tip_oid=tip, tip_date=NOW - timedelta(days=days_idle))


def _pr(
    number: int,
    state: str,
    head_ref: str,
    head_oid: str,
    closed_days_ago: int | None = None,
) -> "bj.PullRequest":
    closed = NOW - timedelta(days=closed_days_ago) if closed_days_ago is not None else None
    return bj.PullRequest(
        number=number,
        state=state,
        head_ref=head_ref,
        head_oid=head_oid,
        merged_at=closed if state == "MERGED" else None,
        closed_at=closed,
    )


def classify(branch, prs, registry=()):
    return bj.classify_branch(branch, list(prs), list(registry), NOW)


def test_merged_head_oid_is_hard_evidence() -> None:
    branch = _branch("codex/trace-attractor-ledger-spec", tip="e" * 40, days_idle=60)
    verdict = classify(branch, [_pr(100, "MERGED", branch.name, "e" * 40, 60)])
    assert verdict.klass == bj.CLASS_DELETE_MERGED
    assert verdict.deletable is True
    assert verdict.pr_number == 100
    assert verdict.tag_name == "archive/pr100--codex/trace-attractor-ledger-spec"
    assert "MERGED PR #100" in verdict.evidence


def test_closed_pr_idle_past_window_is_deletable() -> None:
    branch = _branch("ops/report-old", tip="b" * 40, days_idle=40)
    verdict = classify(branch, [_pr(722, "CLOSED", branch.name, "b" * 40, 20)])
    assert verdict.klass == bj.CLASS_DELETE_CLOSED_IDLE
    assert verdict.deletable is True
    assert verdict.tag_name == "archive/pr722--ops/report-old"


def test_closed_pr_inside_window_waits() -> None:
    branch = _branch("ops/report-fresh", tip="c" * 40, days_idle=40)
    verdict = classify(branch, [_pr(730, "CLOSED", branch.name, "c" * 40, 5)])
    assert verdict.klass == bj.CLASS_WAITING
    assert verdict.deletable is False


def test_tip_idle_but_recent_close_waits() -> None:
    # Idle window keys off max(tip date, closedAt): an old tip whose PR
    # closed yesterday is still inside the window.
    branch = _branch("ops/report-reclosed", tip="c" * 40, days_idle=90)
    verdict = classify(branch, [_pr(731, "CLOSED", branch.name, "c" * 40, 1)])
    assert verdict.klass == bj.CLASS_WAITING
    assert verdict.deletable is False


def test_repushed_after_merge_needs_operator() -> None:
    # Dive precedent: codex/local-risk-final-boss-20260702 — merged PR #750
    # but re-pushed with unique commits. Never auto-deleted.
    branch = _branch("codex/local-risk-final-boss-20260702", tip="d" * 40, days_idle=2)
    verdict = classify(branch, [_pr(750, "MERGED", branch.name, "9" * 40, 2)])
    assert verdict.klass == bj.CLASS_CANDIDATE_TIP_MOVED
    assert verdict.deletable is False
    assert "matches no PR head OID" in verdict.evidence


def test_repushed_after_close_needs_operator() -> None:
    branch = _branch("claude/a2a-nats-review-test", tip="f" * 40, days_idle=90)
    verdict = classify(branch, [_pr(729, "CLOSED", branch.name, "8" * 40, 90)])
    assert verdict.klass == bj.CLASS_CANDIDATE_TIP_MOVED
    assert verdict.deletable is False


def test_never_prd_idle_is_candidate_not_deletable() -> None:
    branch = _branch("roaming-daemon-20260326", days_idle=100)
    verdict = classify(branch, [])
    assert verdict.klass == bj.CLASS_CANDIDATE_NO_PR
    assert verdict.deletable is False
    assert verdict.tag_name is None


def test_never_prd_recent_is_active() -> None:
    branch = _branch("vps/new-work", days_idle=3)
    verdict = classify(branch, [])
    assert verdict.klass == bj.CLASS_ACTIVE
    assert verdict.deletable is False


def test_open_pr_head_is_protected_even_when_stale() -> None:
    branch = _branch("fix/council-loop-aware-completion", tip="1" * 40, days_idle=400)
    verdict = classify(branch, [_pr(775, "OPEN", branch.name, "1" * 40)])
    assert verdict.klass == bj.CLASS_PROTECTED
    assert verdict.deletable is False


def test_default_branch_is_protected() -> None:
    verdict = classify(_branch("main", days_idle=0), [])
    assert verdict.klass == bj.CLASS_PROTECTED


def test_registry_exact_name_exempts() -> None:
    registry = [bj.RegistryEntry("branch", "agent/magpie-seed", "live lineage")]
    branch = _branch("agent/magpie-seed", days_idle=300)
    verdict = classify(branch, [], registry)
    assert verdict.klass == bj.CLASS_EXEMPT
    assert verdict.deletable is False


def test_registry_pattern_exempts() -> None:
    registry = [bj.RegistryEntry("pattern", "titanium/*", "active stack")]
    verdict = classify(_branch("titanium/phase-0-kernel-skeleton", days_idle=300), [], registry)
    assert verdict.klass == bj.CLASS_EXEMPT


def test_registry_beats_hard_evidence() -> None:
    registry = [bj.RegistryEntry("branch", "agent/magpie-seed", "live lineage")]
    branch = _branch("agent/magpie-seed", tip="7" * 40, days_idle=300)
    verdict = classify(branch, [_pr(10, "MERGED", branch.name, "7" * 40, 300)], registry)
    assert verdict.klass == bj.CLASS_EXEMPT
    assert verdict.deletable is False


def test_highest_pr_number_wins_for_evidence_and_tag() -> None:
    # feat/s4-zeitgeist-llm-scan pattern: #60 CLOSED + #61 MERGED, tip == #61.
    branch = _branch("feat/s4-zeitgeist-llm-scan", tip="6" * 40, days_idle=60)
    prs = [
        _pr(60, "CLOSED", branch.name, "5" * 40, 60),
        _pr(61, "MERGED", branch.name, "6" * 40, 60),
    ]
    verdict = classify(branch, prs)
    assert verdict.klass == bj.CLASS_DELETE_MERGED
    assert verdict.pr_number == 61


def test_seeded_registry_file_parses_and_covers_dive_lineages() -> None:
    entries = bj.load_registry(REGISTRY)
    assert entries, "seeded registry must not be empty"
    for name in (
        "agent/magpie-seed",
        "feat/rsi-lab",
        "titanium/phase-0-kernel-skeleton",
        "titanium/phase-1e-ci-wiring",
        "telos_titanium/naga_ir",
        "telos_titanium/dharma_lane_research",
        "weaver/br003-orgcode-ratchet-spec",
        "weaver/waste-recycling",
    ):
        assert bj.registry_match(name, entries) is not None, name
    assert bj.registry_match("devin/1780424084-pr-janitor-session", entries) is None


def test_minimal_parser_matches_constrained_schema() -> None:
    entries = bj.parse_registry_text(REGISTRY.read_text(encoding="utf-8"))
    kinds = {(e.kind, e.value) for e in entries}
    assert ("branch", "agent/magpie-seed") in kinds
    assert ("pattern", "titanium/*") in kinds
    for entry in entries:
        assert entry.reason, f"registry entry {entry.value} needs a reason"


def test_execute_plan_only_covers_deletable_classes(tmp_path: Path) -> None:
    branches = [
        {"name": "merged-safe", "tip_oid": "a" * 40, "tip_date": "2026-05-01T00:00:00Z"},
        {"name": "no-pr-old", "tip_oid": "b" * 40, "tip_date": "2026-01-01T00:00:00Z"},
    ]
    prs = [
        {
            "number": 40,
            "state": "MERGED",
            "headRefName": "merged-safe",
            "headRefOid": "a" * 40,
            "mergedAt": "2026-05-01T00:00:00Z",
            "closedAt": "2026-05-01T00:00:00Z",
        }
    ]
    verdicts = bj.classify_all(
        [bj.branch_from_dict(b) for b in branches],
        [bj.pr_from_dict(p) for p in prs],
        [],
        NOW,
    )
    deletable = [v for v in verdicts if v.deletable]
    assert [v.branch.name for v in deletable] == ["merged-safe"]
    assert all(v.klass in bj.DELETABLE_CLASSES for v in deletable)


def test_main_dry_run_offline_writes_receipt(tmp_path: Path) -> None:
    branches = [
        {"name": "main", "tip_oid": "0" * 40, "tip_date": "2026-07-04T00:00:00Z"},
        {"name": "merged-safe", "tip_oid": "a" * 40, "tip_date": "2026-05-01T00:00:00Z"},
        {"name": "closed-idle", "tip_oid": "b" * 40, "tip_date": "2026-05-01T00:00:00Z"},
        {"name": "no-pr-old", "tip_oid": "c" * 40, "tip_date": "2026-01-01T00:00:00Z"},
        {"name": "agent/magpie-seed", "tip_oid": "d" * 40, "tip_date": "2026-01-01T00:00:00Z"},
    ]
    prs = [
        {
            "number": 40,
            "state": "MERGED",
            "headRefName": "merged-safe",
            "headRefOid": "a" * 40,
            "mergedAt": "2026-05-01T00:00:00Z",
            "closedAt": "2026-05-01T00:00:00Z",
        },
        {
            "number": 41,
            "state": "CLOSED",
            "headRefName": "closed-idle",
            "headRefOid": "b" * 40,
            "mergedAt": None,
            "closedAt": "2026-05-01T00:00:00Z",
        },
    ]
    branches_file = tmp_path / "branches.json"
    prs_file = tmp_path / "prs.json"
    branches_file.write_text(json.dumps(branches), encoding="utf-8")
    prs_file.write_text(json.dumps(prs), encoding="utf-8")
    report_dir = tmp_path / "reports"

    rc = bj.main(
        [
            "--dry-run",
            "--branches-json",
            str(branches_file),
            "--prs-json",
            str(prs_file),
            "--registry",
            str(REGISTRY),
            "--report-dir",
            str(report_dir),
            "--now",
            "2026-07-04T12:00:00Z",
        ]
    )
    assert rc == 0
    receipt = report_dir / "branch_janitor_2026-07-04.md"
    assert receipt.exists()
    text = receipt.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "mode: dry-run" in text
    assert "`merged-safe`" in text
    assert "`archive/pr40--merged-safe`" in text
    assert "`archive/pr41--closed-idle`" in text
    assert "Deletable now: 2" in text
    assert "`agent/magpie-seed`" in text
    assert "registry" in text
