"""Tests for the deterministic spine adoption metric tool.

Codex Slice 1 deliverable: tools/spine_adoption_metric.py must
deterministically scan tracked source files and classify each
surface as joined / adapter-ready / missing / quarantine / legacy.

The adoption_pct formula is:
    (joined_count + adapter_ready_count) / total_surfaces * 100
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.spine_adoption_metric import (
    SURFACE_RULES,
    VALID_STATUSES,
    SurfaceRule,
    classify_surface,
    generate_report,
    main,
    summarize_surfaces,
    write_report,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent


def _generate() -> dict:
    return generate_report(REPO_ROOT)


# ---------------------------------------------------------------------------
# Core metric structure tests
# ---------------------------------------------------------------------------


def test_report_has_required_top_level_keys() -> None:
    report = _generate()
    for key in (
        "metric",
        "audit_sha",
        "source_status",
        "source_status_entries",
        "tracked_file_count",
        "classification_vocabulary",
        "classification_rule",
        "summary",
        "surfaces",
        "top_saturation_targets",
    ):
        assert key in report, f"missing top-level key: {key}"
    assert report["metric"] == "spine_adoption_metric"
    assert report["source_status"] in {"clean", "dirty"}
    assert isinstance(report["source_status_entries"], list)


def test_classification_vocabulary_matches_valid_statuses() -> None:
    report = _generate()
    assert tuple(report["classification_vocabulary"]) == VALID_STATUSES


def test_summary_adoption_pct_formula() -> None:
    report = _generate()
    summary = report["summary"]
    total = summary["total_surfaces"]
    joined = summary["joined_count"]
    adapter_ready = summary["adapter_ready_count"]
    expected_pct = round((joined + adapter_ready) / total * 100, 1) if total else 0.0
    assert summary["adoption_pct"] == expected_pct
    assert summary["joined_or_adapter_ready_count"] == joined + adapter_ready


def test_every_surface_rule_is_represented() -> None:
    report = _generate()
    surface_ids = {s["id"] for s in report["surfaces"]}
    rule_ids = {r.surface_id for r in SURFACE_RULES}
    assert surface_ids == rule_ids


def test_every_surface_has_valid_status() -> None:
    report = _generate()
    for surface in report["surfaces"]:
        assert surface["status"] in VALID_STATUSES, (
            f"surface {surface['id']} has invalid status: {surface['status']}"
        )


def test_status_counts_sum_to_total() -> None:
    report = _generate()
    summary = report["summary"]
    total_from_counts = sum(summary["status_counts"].values())
    assert total_from_counts == summary["total_surfaces"]


# ---------------------------------------------------------------------------
# Determinism test
# ---------------------------------------------------------------------------


def test_report_is_deterministic(tmp_path: Path) -> None:
    output = tmp_path / "metric.json"
    report_a = _generate()
    write_report(report_a, output, REPO_ROOT)
    text_a = output.read_text(encoding="utf-8")

    report_b = _generate()
    write_report(report_b, output, REPO_ROOT)
    text_b = output.read_text(encoding="utf-8")

    assert text_a == text_b
    assert json.loads(text_a)["summary"]["adoption_pct"] == report_a["summary"]["adoption_pct"]


def test_require_clean_source_fails_before_writing_when_dirty(monkeypatch, tmp_path: Path) -> None:
    from tools import spine_adoption_metric as metric_module

    output = tmp_path / "should_not_exist.json"
    monkeypatch.setattr(metric_module, "git_status_porcelain", lambda repo_root: [" M fake.py"])

    assert main(["--repo-root", str(REPO_ROOT), "--output", str(output), "--require-clean-source"]) == 1
    assert not output.exists()


def test_cli_checks_are_read_only_without_output(monkeypatch) -> None:
    from tools import spine_adoption_metric as metric_module

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("read-only metric checks must not write reports")

    monkeypatch.setattr(metric_module, "write_report", fail_if_called)

    assert metric_module.main(["--repo-root", str(REPO_ROOT), "--fail-below-adoption", "0"]) == 0


# ---------------------------------------------------------------------------
# Falsification: injecting a missing token must flip a surface to non-joined
# ---------------------------------------------------------------------------


def test_missing_pattern_makes_surface_non_joined() -> None:
    """If a joined-evidence pattern can't match, the surface must NOT be joined."""
    from tools.spine_adoption_metric import PatternSpec, load_tracked_sources, git_tracked_files

    tracked = git_tracked_files(REPO_ROOT)
    source_map = load_tracked_sources(REPO_ROOT, tracked)

    # Take a rule that is currently joined and inject an unmatchable pattern
    joined_rules = [
        r for r in SURFACE_RULES
        if classify_surface(r, source_map)["status"] == "joined"
    ]
    assert joined_rules, "no joined surfaces to test against"
    original = joined_rules[0]
    broken_rule = SurfaceRule(
        surface_id=original.surface_id,
        label=original.label,
        category=original.category,
        path_patterns=original.path_patterns,
        joined=original.joined + (
            PatternSpec(
                key="definitely_missing_token",
                regex=r"XYZZY_IMPOSSIBLE_TOKEN_FOR_FALSIFICATION_42",
                description="impossible token for falsification",
            ),
        ),
        adapter_ready=original.adapter_ready,
        quarantine=original.quarantine,
        legacy=original.legacy,
        priority=original.priority,
    )
    result = classify_surface(broken_rule, source_map)
    assert result["status"] != "joined", (
        f"surface {original.surface_id} still classified as joined after injecting missing pattern"
    )
    missing_keys = [p["key"] for p in result["missing_joined_patterns"]]
    assert "definitely_missing_token" in missing_keys


# ---------------------------------------------------------------------------
# Known surface status assertions (grounded in merged PRs #435 + #436)
# ---------------------------------------------------------------------------


def test_known_joined_surfaces() -> None:
    """Surfaces proven joined by PRs #435 and #436."""
    report = _generate()
    surface_map = {s["id"]: s["status"] for s in report["surfaces"]}
    expected_joined = [
        "identity_contract",
        "runtime_state_ledger",
        "runtime_lifecycle_adapter",
        "task_board_ingress",
        "orchestrator_dispatch",
        "message_bus_transport",
        "a2a_server_ingress",
        "artifact_store",
        "tool_registry_dispatch",
    ]
    for sid in expected_joined:
        assert surface_map.get(sid) == "joined", (
            f"expected {sid} to be joined but got {surface_map.get(sid)}"
        )


def test_nats_is_scoped_out() -> None:
    """NATS transport status reflects its SANCTIONED lane, not the old scope-out.

    History: this test originally asserted ('missing', 'quarantine') because the
    spine-adoption track's non-goals scoped NATS out and no source files existed.
    That assumption was superseded: the 2026-05-31 doctrine amendment scoped NATS
    out of the global prohibition, and it now runs as its own ACTIVE track
    (runtime-truth-nats-2026-06, codex lane) with real source files
    (dharma_swarm/a2a/nats_transport.py, PR #514) — so the metric correctly
    reports 'joined'. The spine-adoption track's own non-goal stands unchanged:
    NATS work happens in the NATS lane, never in this one. 'missing'/'quarantine'
    remain acceptable for environments where the transport is absent.
    """
    report = _generate()
    nats = next((s for s in report["surfaces"] if s["id"] == "nats_jetstream_transport"), None)
    assert nats is not None
    assert nats["status"] in ("joined", "missing", "quarantine")


# ---------------------------------------------------------------------------
# Adoption threshold (current state — updated as slices land)
# ---------------------------------------------------------------------------


def test_current_adoption_is_above_baseline() -> None:
    """adoption_pct must exceed the pre-saturation baseline of 56.25%."""
    report = _generate()
    assert report["summary"]["adoption_pct"] > 56.0
