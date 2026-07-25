"""Tests for the merge-time lifecycle-transition invariants in
scripts/governance/check_track_status.py (closes the track-resurrection
class: a stale-branch merge silently re-activating a SHIPPED track)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts/governance/check_track_status.py"

spec = importlib.util.spec_from_file_location("check_track_status", SCRIPT)
cts = importlib.util.module_from_spec(spec)
sys.modules["check_track_status"] = cts
spec.loader.exec_module(cts)


def _p(active=(), closed=()):
    return {
        "active_tracks": [dict(t) for t in active],
        "closed_tracks": [dict(t) for t in closed],
    }


BASE = _p(
    active=[{"id": "current-track", "status": "ACTIVE"}],
    closed=[{"id": "shipped-track", "status": "SHIPPED", "closed_at": "2026-06-06"}],
)


def _slugs(findings):
    return {f.slug if hasattr(f, "slug") else f.check for f in findings}


def _mk(base, head):
    return cts._lifecycle_findings(base, head)


def test_clean_transition_no_findings():
    head = _p(
        active=[{"id": "current-track", "status": "ACTIVE"},
                {"id": "new-track", "status": "ACTIVE"}],
        closed=[{"id": "shipped-track", "status": "SHIPPED", "closed_at": "2026-06-06"}],
    )
    assert _mk(BASE, head) == []


def test_resurrection_without_reopened_at_is_error():
    head = _p(
        active=[{"id": "shipped-track", "status": "ACTIVE"}],
        closed=[{"id": "shipped-track", "status": "SHIPPED", "closed_at": "2026-06-06"}],
    )
    findings = _mk(BASE, head)
    assert any("closed-track-resurrected:shipped-track" in str(f) for f in findings)
    assert all(f.severity == "ERROR" for f in findings)


def test_resurrection_with_reopened_at_is_allowed():
    head = _p(
        active=[{"id": "shipped-track", "status": "ACTIVE",
                 "reopened_at": "2026-07-07"}],
        closed=[{"id": "shipped-track", "status": "SHIPPED", "closed_at": "2026-06-06"}],
    )
    assert _mk(BASE, head) == []


def test_closed_entry_removal_is_error():
    head = _p(active=[{"id": "current-track", "status": "ACTIVE"}], closed=[])
    findings = _mk(BASE, head)
    assert any("closed-track-removed:shipped-track" in str(f) for f in findings)


def test_active_closed_overlap_at_head_is_error():
    head = _p(
        active=[{"id": "double-booked", "status": "ACTIVE"}],
        closed=[{"id": "double-booked", "status": "SHIPPED", "closed_at": "2026-07-01"}],
    )
    findings = _mk(_p(), head)
    assert any("active-closed-overlap:double-booked" in str(f) for f in findings)


def test_the_actual_2026_06_incident_shape():
    # Reconstruction of the PR #555 overwrite: base had the track closed;
    # the stale branch's file re-listed it ACTIVE and dropped the closure.
    head = _p(active=[{"id": "shipped-track", "status": "ACTIVE"}], closed=[])
    slugs = {str(f) for f in _mk(BASE, head)}
    assert any("closed-track-removed:shipped-track" in s for s in slugs)
    assert any("closed-track-resurrected:shipped-track" in s for s in slugs)


def test_verified_slice_cannot_erase_same_id_open_blockers():
    base = _p(
        active=[{
            "id": "campaign",
            "status": "ACTIVE",
            "next_items": [
                {"id": "proof", "blocker": True},
                {"id": "advisory", "blocker": False},
            ],
        }]
    )
    head = _p(
        closed=[{
            "id": "campaign",
            "status": "SHIPPED",
            "closure_kind": "VERIFIED_SLICE",
        }]
    )

    findings = _mk(base, head)

    assert any(
        "verified-slice-erases-blockers:campaign" in str(finding)
        for finding in findings
    )


def test_retired_campaign_and_distinct_verified_slice_preserve_claim_types():
    base = _p(
        active=[{
            "id": "campaign",
            "status": "ACTIVE",
            "next_items": [{"id": "proof", "blocker": True}],
        }]
    )
    head = _p(
        closed=[
            {
                "id": "campaign",
                "status": "RETIRED",
                "closure_kind": "RETIRED",
            },
            {
                "id": "retained-slice",
                "status": "SHIPPED",
                "closure_kind": "VERIFIED_SLICE",
            },
        ]
    )

    assert _mk(base, head) == []
