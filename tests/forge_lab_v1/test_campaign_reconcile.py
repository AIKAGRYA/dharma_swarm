from __future__ import annotations

import json
from pathlib import Path
import sqlite3

import pytest

from dharma_swarm.forge_lab import campaign_reconcile as reconcile
from dharma_swarm.forge_lab.campaign_contract import build_manifest
from dharma_swarm.forge_lab.campaign_profile import PROFILE, campaign_definition


CAMPAIGN = "forge-lab-n30-to-1000-v1"


def _campaign_root(state: Path) -> Path:
    return state / ".dharma" / "forge_lab" / "campaigns" / CAMPAIGN


def _make_roots(state: Path) -> None:
    (state / ".dharma" / "forge_lab" / "manifests").mkdir(parents=True)
    for category in ("control", "receipts", "events", "checkpoints"):
        (_campaign_root(state) / category).mkdir(parents=True)


def _valid_manifest(state: Path, *, filename_digest: str | None = None) -> Path:
    manifest = build_manifest(campaign_definition(PROFILE))
    digest = filename_digest or manifest["manifest_digest"]
    path = (
        state
        / ".dharma"
        / "forge_lab"
        / "manifests"
        / f"{digest.removeprefix('sha256:')}.json"
    )
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _tree_bytes(root: Path) -> list[tuple[str, str, bytes | None]]:
    if not root.exists():
        return []
    result: list[tuple[str, str, bytes | None]] = []
    for path in sorted(root.rglob("*")):
        kind = "symlink" if path.is_symlink() else "dir" if path.is_dir() else "file"
        data = path.read_bytes() if kind == "file" else None
        result.append((path.relative_to(root).as_posix(), kind, data))
    return result


def _redigest(report: dict) -> str:
    body = dict(report)
    body.pop("report_digest", None)
    digest = reconcile.content_digest(body)
    report["report_digest"] = digest
    return digest


def test_dry_run_is_byte_for_byte_mutation_free_and_deterministic(
    tmp_path: Path,
) -> None:
    state = tmp_path / "canonical-state"
    _make_roots(state)
    _valid_manifest(state)
    before = _tree_bytes(state)

    first = reconcile.reconcile_state(state, campaign_id=CAMPAIGN)
    second = reconcile.reconcile_state(state, campaign_id=CAMPAIGN)

    assert _tree_bytes(state) == before
    assert first == second
    assert first["schema"] == reconcile.REPORT_SCHEMA
    assert first["report_digest"] == reconcile.content_digest(
        {key: value for key, value in first.items() if key != "report_digest"}
    )
    assert first["summary"]["status"] == "clean"
    assert first["authority"]["creates_scientific_evidence"] is False
    assert not any(
        finding["code"] == "CAS_DIGEST_MISMATCH"
        for finding in first["findings"]
    )


def test_scan_reports_missing_corrupt_and_conflicting_artifacts(
    tmp_path: Path,
) -> None:
    state = tmp_path / "canonical-state"
    _make_roots(state)
    _valid_manifest(state, filename_digest=f"sha256:{'a' * 64}")
    manifests = state / ".dharma" / "forge_lab" / "manifests"
    (manifests / f"{'0' * 64}.json").write_text("{}", encoding="utf-8")
    (_campaign_root(state) / "control" / "broken.json").write_text(
        "{not-json", encoding="utf-8"
    )
    receipts = _campaign_root(state) / "receipts"
    (receipts / "one.json").write_text(
        json.dumps({"schema": "test.receipt.v1", "receipt_id": "same", "value": 1}),
        encoding="utf-8",
    )
    (receipts / "two.json").write_text(
        json.dumps({"schema": "test.receipt.v1", "receipt_id": "same", "value": 2}),
        encoding="utf-8",
    )
    expected = [{
        "category": "receipts",
        "path": "terminal.json",
        "digest": f"sha256:{'b' * 64}",
    }]

    report = reconcile.reconcile_state(
        state, campaign_id=CAMPAIGN, expected_artifacts=expected
    )
    codes = {finding["code"] for finding in report["findings"]}

    assert {
        "CAS_DIGEST_MISMATCH",
        "CONFLICTING_ARTIFACT_IDENTITY",
        "CORRUPT_JSON",
        "CORRUPT_MANIFEST",
        "MISSING_ARTIFACT",
    } <= codes


def test_apply_is_exact_non_destructive_and_request_idempotent(
    tmp_path: Path,
) -> None:
    state = tmp_path / "canonical-state"
    state.mkdir()
    report = reconcile.reconcile_state(state, campaign_id=CAMPAIGN)

    first = reconcile.reconcile_state(
        state,
        campaign_id=CAMPAIGN,
        apply=True,
        report=report,
        report_digest=report["report_digest"],
        request_id="repair-roots-001",
    )
    second = reconcile.reconcile_state(
        state,
        campaign_id=CAMPAIGN,
        apply=True,
        report=report,
        report_digest=report["report_digest"],
        request_id="repair-roots-001",
    )

    assert second == first
    assert first["schema"] == reconcile.RECEIPT_SCHEMA
    assert first["scientific_evidence_created"] is False
    assert first["provider_evidence_created"] is False
    assert {item["operation"] for item in first["operations_applied"]} == {
        "create_directory"
    }
    assert all(
        (_campaign_root(state) / category).is_dir()
        for category in ("control", "receipts", "events", "checkpoints")
    )

    changed_report = reconcile.reconcile_state(state, campaign_id=CAMPAIGN)
    with pytest.raises(reconcile.ReconciliationError) as conflict:
        reconcile.reconcile_state(
            state,
            campaign_id=CAMPAIGN,
            apply=True,
            report=changed_report,
            report_digest=changed_report["report_digest"],
            request_id="repair-roots-001",
        )
    assert conflict.value.code == "REQUEST_ID_CONFLICT"


def test_apply_rejects_stale_or_non_enumerated_repairs(tmp_path: Path) -> None:
    state = tmp_path / "canonical-state"
    state.mkdir()
    stale = reconcile.reconcile_state(state, campaign_id=CAMPAIGN)
    (_campaign_root(state) / "control").mkdir(parents=True)
    with pytest.raises(reconcile.ReconciliationError) as changed:
        reconcile.reconcile_state(
            state,
            apply=True,
            report=stale,
            report_digest=stale["report_digest"],
            request_id="stale-report-001",
        )
    assert changed.value.code == "STALE_RECONCILIATION_REPORT"

    unsafe = reconcile.reconcile_state(state, campaign_id=CAMPAIGN)
    unsafe["repairs"] = [{
        "category": "receipts",
        "operation": "delete",
        "path": ".dharma/forge_lab/campaigns/unsafe",
    }]
    digest = _redigest(unsafe)
    with pytest.raises(reconcile.ReconciliationError) as refused:
        reconcile.reconcile_state(
            state,
            apply=True,
            report=unsafe,
            report_digest=digest,
            request_id="unsafe-repair-001",
        )
    assert refused.value.code == "UNSAFE_REPAIR"


def test_cleanup_plans_residuals_and_blocked_scratch_without_deleting(
    tmp_path: Path,
) -> None:
    state = tmp_path / "canonical-state"
    scratch = state / ".dharma" / "forge_lab" / "scratch" / CAMPAIGN
    scratch.mkdir(parents=True)
    payload = scratch / "candidate.txt"
    payload.write_bytes(b"preserve-me")
    before = _tree_bytes(state)

    plan = reconcile.plan_cleanup(
        state,
        CAMPAIGN,
        lifecycle_state="FUSE_TRIPPED",
        scratch_path=scratch,
        residual_paths=[payload],
    )

    assert _tree_bytes(state) == before
    assert plan["scratch"]["state"] == "present"
    assert plan["residuals_before_action"]
    assert plan["actions"] == []
    assert plan["deletion_performed"] is False
    assert plan["plan_digest"] == reconcile.content_digest(
        {key: value for key, value in plan.items() if key != "plan_digest"}
    )

    blocked_root = tmp_path / "never-created-state"
    blocked = reconcile.plan_cleanup(
        blocked_root,
        CAMPAIGN,
        lifecycle_state="BLOCKED_BEFORE_START",
    )
    assert blocked["scratch"] == {
        "action": "none",
        "path": None,
        "state": "not_created",
    }
    assert not blocked_root.exists()


def test_state_root_is_explicit_absolute_and_home_is_ignored(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "decoy"))
    with pytest.raises(reconcile.ReconciliationError) as relative:
        reconcile.reconcile_state(Path("relative-state"))
    assert relative.value.code == "STATE_ROOT_NOT_ABSOLUTE"


def test_reconcile_does_not_false_green_a_sqlite_header_without_schema(
    tmp_path: Path,
) -> None:
    state = tmp_path / "canonical-state"
    _make_roots(state)
    _valid_manifest(state)
    db_path = state / ".dharma" / "forge_lab" / "campaigns" / "control.sqlite3"
    with sqlite3.connect(db_path) as db:
        db.execute("CREATE TABLE decoy(value TEXT)")

    report = reconcile.reconcile_state(state, campaign_id=CAMPAIGN)

    assert report["summary"]["status"] == "divergent"
    assert "DB_SCHEMA_MISSING" in {
        finding["code"] for finding in report["findings"]
    }
