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
ONE_DOOR_SPEC = (
    REPO_ROOT / "docs/plans/ONBOARD_ONE_DOOR_HARDENING_SPEC_2026-07-10.md"
)
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
    REPO_ROOT / "docs/governance/BUILD_SESSION_ENTRYPOINT.md",
]

ONE_DOOR_PACKET_DIR = REPO_ROOT / "reports/agentops/work_packets"
ADMITTED_ONE_DOOR_PACKET_NAMES = {
    "onboard-one-door-WP-O1.json",
    "onboard-one-door-WP-O1R.json",
    "onboard-one-door-WP-O2.json",
    "onboard-one-door-WP-O2-B0.json",
    "onboard-one-door-WP-O2-B1.json",
    "onboard-one-door-WP-O2-B2.json",
    "onboard-one-door-WP-O2-B3.json",
    "onboard-one-door-WP-O2R.json",
    "onboard-one-door-WP-O3.json",
    "onboard-one-door-WP-O3-P.json",
    "onboard-one-door-WP-O3-D3.json",
    "onboard-one-door-WP-O3-A.json",
    "onboard-one-door-WP-O4.json",
    "onboard-one-door-WP-O4R.json",
    "onboard-one-door-WP-O4-B0.json",
    "onboard-one-door-WP-O4-B1.json",
    "onboard-one-door-WP-O4-B1-CLOSE.json",
    "onboard-one-door-WP-O4-B9.json",
    "onboard-one-door-WP-O4-B2.json",
    "onboard-one-door-WP-O4-POLICY.json",
    "onboard-one-door-WP-O4-C1.json",
    "onboard-one-door-WP-O4-C1-CLOSE.json",
    "onboard-one-door-WP-O5.json",
    "onboard-one-door-WP-O5-D2.json",
    "onboard-one-door-WP-O6.json",
    "onboard-one-door-WP-O6-M6.json",
    "onboard-one-door-WP-O6-CLOSE.json",
    "onboard-one-door-WP-O6-FINAL.json",
}
POST_B2_ONE_DOOR_PACKET_NAMES = {
    "onboard-one-door-WP-O3-P.json",
    "onboard-one-door-WP-O3-D3.json",
    "onboard-one-door-WP-O3-A.json",
    "onboard-one-door-WP-O4-POLICY.json",
    "onboard-one-door-WP-O4-C1.json",
    "onboard-one-door-WP-O4-C1-CLOSE.json",
    "onboard-one-door-WP-O5.json",
    "onboard-one-door-WP-O5-D2.json",
    "onboard-one-door-WP-O6.json",
    "onboard-one-door-WP-O6-M6.json",
    "onboard-one-door-WP-O6-CLOSE.json",
    "onboard-one-door-WP-O6-FINAL.json",
}


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


def test_one_door_pre_b2_packet_names_and_state_implications_are_closed() -> None:
    """Reject suffix escapes and out-of-order packets before B2 exists."""
    governance_path = str(REPO_ROOT / "scripts/governance")
    if governance_path not in sys.path:
        sys.path.insert(0, governance_path)
    from check_track_status import load_active_track, normalize_portfolio  # type: ignore

    actual_names: set[str] = set()
    for path in ONE_DOOR_PACKET_DIR.glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if (
            payload.get("session_entry", {}).get("active_track")
            != "onboard-one-door-2026-07"
        ):
            continue
        assert payload.get("id") == path.stem, (
            f"One-Door packet id/filename mismatch: {path.name}"
        )
        actual_names.add(path.name)
    assert actual_names <= ADMITTED_ONE_DOOR_PACKET_NAMES, (
        "unadmitted One-Door packet filename(s): "
        f"{sorted(actual_names - ADMITTED_ONE_DOOR_PACKET_NAMES)}"
    )

    portfolio = normalize_portfolio(load_active_track(ACTIVE_TRACK))
    matches = [
        track
        for family in (portfolio["active_tracks"], portfolio["closed_tracks"])
        for track in family
        if track["id"] == "onboard-one-door-2026-07"
    ]
    assert len(matches) == 1
    items = {str(item["id"]): item for item in matches[0]["next_items"]}
    wp_o2r_done = items["WP-O2R"]["blocker"] is False
    wp_o4_done = items["WP-O4"]["blocker"] is False
    b2_done = items["WP-O4-B2"]["blocker"] is False

    b1_close = "onboard-one-door-WP-O4-B1-CLOSE.json"
    b9 = "onboard-one-door-WP-O4-B9.json"
    b2 = "onboard-one-door-WP-O4-B2.json"
    assert not wp_o2r_done or b1_close in actual_names
    assert not wp_o4_done or b9 in actual_names
    assert not b2_done or b2 in actual_names
    assert b9 not in actual_names or b1_close in actual_names
    assert b2 not in actual_names or {b1_close, b9} <= actual_names
    if b2 not in actual_names:
        assert (b1_close in actual_names) == wp_o2r_done
        assert (b9 in actual_names) == wp_o4_done
        assert not wp_o4_done or wp_o2r_done
        assert not (actual_names & POST_B2_ONE_DOOR_PACKET_NAMES), (
            "post-B2 One-Door packet appeared before B2 cleared: "
            f"{sorted(actual_names & POST_B2_ONE_DOOR_PACKET_NAMES)}"
        )
    else:
        b2_what = str(items["WP-O4-B2"]["what"])
        assert (
            "stage=WP-O4-B2-DONE" in b2_what
            or "stage=WP-O4-B2-POLICY-v" in b2_what
        ), "B2 file exists without a mechanically installed controller stage"


def test_one_door_c1_has_ordered_pre_and_post_wp_o5_proofs() -> None:
    """C1 must unlock WP-O5 before plain-command enforcement can close C1."""
    governance_path = str(REPO_ROOT / "scripts/governance")
    if governance_path not in sys.path:
        sys.path.insert(0, governance_path)
    from check_track_status import load_active_track, normalize_portfolio  # type: ignore

    portfolio = normalize_portfolio(load_active_track(ACTIVE_TRACK))
    track_id = "onboard-one-door-2026-07"
    active_matches = [
        item for item in portfolio["active_tracks"] if item["id"] == track_id
    ]
    closed_matches = [
        item for item in portfolio["closed_tracks"] if item["id"] == track_id
    ]
    assert len(active_matches) + len(closed_matches) == 1, (
        "onboard-one-door-2026-07 must exist exactly once across active and "
        "closed portfolios"
    )
    track = (active_matches or closed_matches)[0]
    if closed_matches:
        assert track["status"] == "SHIPPED"
        assert track["closure_kind"] == "CLOSED_NOT_PROD"
        assert track.get("closed_at")
        assert track.get("closed_by")
        assert track.get("final_audit_digest")
        restoration = track.get("wip_limit_at_closure")
        assert isinstance(restoration, dict)
        assert restoration.get("base_max_active") in {10, 11}
        assert restoration.get("resulting_max_active") == 10
        assert restoration.get("restored_by") in {
            "onboard-one-door-WP-O6-FINAL",
            "prior-track-closure",
        }
    else:
        assert track["status"] in {"ACTIVE", "SHIPPABLE"}
        assert track["target_closure_kind"] == "CLOSED_NOT_PROD"
    ordered_items = track["next_items"]
    ordered_ids = [str(item["id"]) for item in ordered_items]
    items = {str(item["id"]): item for item in ordered_items}

    assert ordered_ids.count("C1") == 1, "C1 must remain one formal node"
    sequential_spine = [
        "WP-O4R",
        "WP-O2R",
        "WP-O4",
        "WP-O4-B2",
        "C1",
        "D2",
        "WP-O5",
        "WP-O6",
    ]
    positions = [ordered_ids.index(node_id) for node_id in sequential_spine]
    assert positions == sorted(positions), (
        "One-Door next_items must preserve the reseal and C1/WP-O5/WP-O6 order"
    )
    assert (
        ordered_ids.index("WP-O4-B2")
        < ordered_ids.index("D3")
        < ordered_ids.index("WP-O3")
        < ordered_ids.index("WP-O6")
    ), "D3/WP-O3 must branch after WP-O4-B2 and join before WP-O6"
    assert (
        ordered_ids.index("WP-O4-B2")
        < ordered_ids.index("M6-1")
        < ordered_ids.index("WP-O6")
    ), "M6-1 must branch after WP-O4-B2 and join before WP-O6"

    def assert_transition_safe(
        item: dict[str, object],
        *,
        pending_markers: tuple[str, ...] | tuple[tuple[str, ...], ...],
        done_markers: tuple[str, ...] | tuple[tuple[str, ...], ...],
    ) -> None:
        what = str(item["what"])
        markers = pending_markers if item["blocker"] else done_markers
        variants = markers if markers and isinstance(markers[0], tuple) else (markers,)
        assert any(all(marker in what for marker in variant) for variant in variants), (
            f"{item['id']} does not match an admitted pending/done stage"
        )

    assert_transition_safe(
        items["WP-O2R"],
        pending_markers=(
            "exact #932 successor",
            "onboard-one-door-WP-O4-B1-CLOSE",
            "WP-O4-B9 cannot begin before that record merges",
        ),
        done_markers=(
            "stage=WP-O2R-DONE",
            "onboard-one-door-WP-O4-B1-CLOSE",
            "council",
            "approval",
            "main",
        ),
    )
    c1_item = items["C1"]
    assert_transition_safe(
        c1_item,
        pending_markers=(
            (
                "exact WP-O4-C1",
                "external RUNNER_TEMP",
                "JSON companion are semantically READY",
                "strict/JSON projection-only BLOCKED control",
                "WP-O5-D2 records that receipt here without closing C1",
                "actual merge_group ejection",
                "WP-O4-C1-CLOSE",
            ),
            (
                "stage=WP-O4-C1-TRACKED",
                "pre-WP-O5",
                "post-WP-O5",
                "WP-O4-C1-CLOSE",
            ),
            (
                "stage=C1-PRE-O5-PROVEN",
                "WP-O5-D2",
                "post-WP-O5",
                "WP-O4-C1-CLOSE",
            ),
            (
                "stage=C1-PR-NEGATIVE",
                "c1-proof-pr-projection-block",
                "WP-O4-C1-CLOSE",
            ),
            (
                "stage=C1-MERGE-GROUP-NEGATIVE",
                "c1-proof-merge-group-projection-block",
                "WP-O4-C1-CLOSE",
            ),
        ),
        done_markers=(
            "stage=C1-DONE",
            "WP-O4-C1-CLOSE",
            "pull-request",
            "merge_group",
        ),
    )
    b2_item = items["WP-O4-B2"]
    assert_transition_safe(
        b2_item,
        pending_markers=(
            "mandatory semantic track_effect admission",
            "FIRST AFTER WP-O4-B9",
            "atomically change this primary ACTIVE_TRACK owner",
        ),
        done_markers=(
            ("stage=WP-O4-B2-DONE", "track_effect", "ACTIVE_TRACK"),
            ("stage=WP-O4-B2-POLICY-v", "track_effect", "ACTIVE_TRACK"),
        ),
    )
    wp_o4 = items["WP-O4"]
    assert_transition_safe(
        wp_o4,
        pending_markers=(
            "WP-O4 TAIL REPAIR PENDING AFTER WP-O2R",
            "make agent-build-preflight",
            "HYPOTHESIS_STORAGE_DIRECTORY",
            "zero ordinary and ignored source leaves",
        ),
        done_markers=(
            "stage=WP-O4-B9-DONE",
            "onboard-one-door-WP-O4-B9",
            "combined-main preflight",
            "zero ordinary and ignored source leaves",
        ),
    )
    assert (
        "does not cover the Make verifier-selfcheck presteps"
        in items["WP-O4R"]["what"]
    )
    assert items["WP-O4R"]["blocker"] is False
    assert "runner/checker envelope" in items["WP-O4R"]["what"]
    assert_transition_safe(
        items["WP-O3"],
        pending_markers=(
            (
                "WP-O3-P AFTER WP-O4-B2",
                "finite producer/input/HEAD/expiry binding",
                "D3 and WP-O3-P jointly gate exact WP-O3-A",
            ),
            (
                "stage=WP-O3-P-DONE",
                "WP-O3-A",
                "D3",
                "v2",
            ),
        ),
        done_markers=("stage=WP-O3-A-DONE", "WP-O3-A", "D3", "v2", "cache"),
    )
    assert_transition_safe(
        items["D3"],
        pending_markers=(
            "D3 PENDING",
            "onboard-one-door-WP-O3-D3",
            "Unobserved",
        ),
        done_markers=(
            "stage=D3-DONE",
            "onboard-one-door-WP-O3-D3",
            "census",
            "digest",
        ),
    )
    assert_transition_safe(
        items["D2"],
        pending_markers=("self-referential merge SHA",),
        done_markers=(
            "D2 RATIFIED",
            "decision_packet=reports/agentops/work_packets/"
            "onboard-one-door-WP-O5-D2.json",
            "decision_digest=",
            "scope=WP-O5-strict-default",
        ),
    )
    assert_transition_safe(
        items["WP-O5"],
        pending_markers=(
            "exact operator packet WP-O5-D2",
            "atomically update this item via track_effect",
        ),
        done_markers=("stage=WP-O5-DONE", "strict", "--no-strict"),
    )
    assert_transition_safe(
        items["M6-1"],
        pending_markers=(
            "M6-1 PENDING",
            "onboard-one-door-WP-O6-M6",
            "DharmaGraph owner",
        ),
        done_markers=(
            "stage=M6-1-DONE",
            "onboard-one-door-WP-O6-M6",
            "owner",
            "ancestry",
        ),
    )
    assert_transition_safe(
        items["WP-O6"],
        pending_markers=(
            "merged WP-O4-C1-CLOSE",
            "WP-O6-CLOSE",
            "SHIPPABLE",
            "fresh-main audit",
            "WP-O6-FINAL",
        ),
        done_markers=(
            ("stage=WP-O6-DONE", "WP-O6-CLOSE", "independent"),
            ("stage=WP-O6-SEALED", "WP-O6-CLOSE", "SHIPPABLE", "independent"),
        ),
    )
    assert_transition_safe(
        items["TERMINAL-PROOF"],
        pending_markers=(
            "TERMINAL PROOF PENDING",
            "WP-O6-CLOSE",
            "SHIPPABLE",
            "fresh main",
            "WP-O6-FINAL",
            "CLOSED_NOT_PROD",
            "Titanium",
        ),
        done_markers=(
            "stage=WP-O6-SEALED",
            "WP-O6-CLOSE",
            "SHIPPABLE",
            "fresh-main",
            "WP-O6-FINAL",
            "CLOSED_NOT_PROD",
            "Titanium",
        ),
    )
    owned_surfaces = {str(surface) for surface in track["owned_surfaces"]}
    assert "docs/plans/ONBOARD_ONE_DOOR_HARDENING_SPEC_2026-07-10.md" in owned_surfaces
    assert "docs/ops/ONBOARD_RECEIPT_READER_CENSUS.yaml" in owned_surfaces

    spec_text = ONE_DOOR_SPEC.read_text(encoding="utf-8")
    wp_o5 = " ".join(
        spec_text
        .split("### WP-O5 —", maxsplit=1)[1]
        .split("\n### ", maxsplit=1)[0]
        .split()
    )
    assert (
        "pre-WP-O5 C1 authority/unlock proof has made the canonical admission "
        "context a required merge-blocking context, has proven the documented "
        "untimed projection bootstrap bound to its producer, inputs, and exact "
        "event head before the normal plain `make onboard`, and has separately "
        "retained the controlled `make onboard ARGS=--strict` BLOCKED result"
    ) in wp_o5
    assert wp_o5.index("normal plain `make onboard`") < wp_o5.index(
        "separately retained the controlled `make onboard ARGS=--strict`"
    )
    assert (
        "WP-O4-B1/#932 → WP-O4-B1-CLOSE reseal record → "
        "WP-O4 O4-B9 tail repair → WP-O4-B2 → "
        "WP-O3-P safety → tracked WP-O4-C1 "
        "implementation → pre-WP-O5 C1 authority proof"
    ) in " ".join(spec_text.split())
    assert "reports/agentops/work_packets/<packet.id>.json" in spec_text
    assert "onboard-one-door-WP-O3-P" in spec_text
    assert "onboard-one-door-WP-O4-B1-CLOSE" in spec_text
    assert "onboard-one-door-WP-O4-B9" in spec_text
    assert "onboard-one-door-WP-O4-C1" in spec_text
    assert "track_effect.next_items: [WP-O3]" in spec_text
    assert "track_effect.next_items: [C1]" in spec_text
    assert "make onboard ARGS=--json" in spec_text
    assert 'make onboard ARGS="--strict --json"' in spec_text

    wp_o6 = " ".join(
        spec_text
        .split("### WP-O6 —", maxsplit=1)[1]
        .split("\n### ", maxsplit=1)[0]
        .split()
    )
    assert (
        "full WP-O3 activation, WP-O5, the final post-WP-O5 C1 enforcement "
        "proof, and M6-1 must all be merged"
    ) in wp_o6

    controller_graph = (
        spec_text
        .split("### 14.1 One campaign, narrow merge nodes", maxsplit=1)[1]
        .split("```text", maxsplit=1)[1]
        .split("```", maxsplit=1)[0]
    )
    graph_steps = [line.strip() for line in controller_graph.splitlines()]
    baseline_step = "-> WP-O4 baseline (merged)"
    b1_step = "-> WP-O4-B1 / #932 exact-head council + merge"
    wp_o2r_step = "-> WP-O4-B1-CLOSE WP-O2R reseal record"
    wp_o4_b9_step = "-> WP-O4 O4-B9 tail repair (same formal node)"
    b2_step = "-> WP-O4-B2 semantic ACTIVE_TRACK effect admission"
    ready_step = "[READY IN PARALLEL IMMEDIATELY AFTER WP-O4-B2]"
    wp_o3_p_lane = "[S] WP-O3-P projection-binding/diagnostic safety slice"
    d3_lane = "[D] D3 fleet-seat census and reader classification"
    m6_lane = "[M] M6-1 ownership reconciliation"
    wp_o3_p_done = "[S] WP-O3-P"
    c1_post_step = "-> WP-O4-C1-CLOSE"
    c1_tracked_step = "-> C1 tracked WP-O4-C1 implementation slice"
    c1_pre_step = (
        "-> C1 pre-WP-O5 authority/unlock proof (bound projection bootstrap "
        "-> plain `make onboard`; separate controlled "
        "`make onboard ARGS=--strict` BLOCKED)"
    )
    d2_step = "-> operator WP-O5-D2 record (C1 partial proof + D2)"
    wp_o5_step = "-> WP-O5"
    c1_proof_step = "-> C1 post-WP-O5 proof-only PR + merge_group vehicles"
    wp_o3_join = "[S] WP-O3-P + [D] D3"
    wp_o3_a_step = "-> WP-O3-A activation"
    join_step = "WP-O4-C1-CLOSE + WP-O3-A + [M] M6-1"
    wp_o6_step = "-> WP-O6 candidate"
    wp_o6_proof_step = "-> §13 independent clean-room proof"
    wp_o6_merge_step = "-> merge WP-O6 + proof candidate"
    wp_o6_seal_step = "-> WP-O6-CLOSE SHIPPABLE/evidence PR"
    terminal_audit_step = "-> fresh-main terminal audit of the SHIPPABLE merge"
    wp_o6_final_step = "-> WP-O6-FINAL closed-track PR"
    assert (
        graph_steps.index(baseline_step)
        < graph_steps.index(b1_step)
        < graph_steps.index(wp_o2r_step)
        < graph_steps.index(wp_o4_b9_step)
        < graph_steps.index(b2_step)
        < graph_steps.index(ready_step)
    )
    for lane in (wp_o3_p_lane, d3_lane, m6_lane):
        assert graph_steps.index(ready_step) < graph_steps.index(lane)
    assert (
        graph_steps.index(wp_o3_p_lane)
        < graph_steps.index(wp_o3_p_done)
        < graph_steps.index(c1_tracked_step)
        < graph_steps.index(c1_pre_step)
        < graph_steps.index(d2_step)
        < graph_steps.index(wp_o5_step)
        < graph_steps.index(c1_proof_step)
        < graph_steps.index(c1_post_step)
    )
    assert (
        graph_steps.index(wp_o3_p_lane)
        < graph_steps.index(wp_o3_join)
        < graph_steps.index(wp_o3_a_step)
        < graph_steps.index(join_step)
        < graph_steps.index(wp_o6_step)
    )
    assert (
        graph_steps.index(d3_lane)
        < graph_steps.index(wp_o3_join)
        < graph_steps.index(wp_o3_a_step)
        < graph_steps.index(join_step)
    )
    assert (
        graph_steps.index(m6_lane)
        < graph_steps.index(join_step)
        < graph_steps.index(wp_o6_step)
    )
    assert (
        graph_steps.index(c1_post_step)
        < graph_steps.index(join_step)
        < graph_steps.index(wp_o6_step)
    )
    assert (
        graph_steps.index(wp_o6_step)
        < graph_steps.index(wp_o6_proof_step)
        < graph_steps.index(wp_o6_merge_step)
        < graph_steps.index(wp_o6_seal_step)
        < graph_steps.index(terminal_audit_step)
        < graph_steps.index(wp_o6_final_step)
    )
    resumption = " ".join(
        spec_text
        .split("### 14.3 Resumption without another ledger", maxsplit=1)[1]
        .split("### 14.4", maxsplit=1)[0]
        .split()
    )
    assert "ready set, not a textual serial cursor" in resumption
    assert "ready nodes = every unclosed §14.1 node" in resumption
    assert "next work = every collision-free ready node" in resumption
    assert "WP-O3-P, D3, and M6-1 are all eligible immediately" in resumption
    assert "first node in §14.1" not in resumption

    wp_o4_tail = spec_text.index(
        "local scope result from base/head, strict default cannot proceed."
    )
    wp_o4_b1 = spec_text.index("#### WP-O4-B1 —")
    wp_o5_start = spec_text.index("### WP-O5 —")
    assert wp_o4_tail < wp_o4_b1 < wp_o5_start, (
        "WP-O4-B1 must follow the complete WP-O4 tail and precede WP-O5"
    )
    wp_o4_spec = " ".join(
        spec_text
        .split("### WP-O4 —", maxsplit=1)[1]
        .split("### WP-O5 —", maxsplit=1)[0]
        .split()
    )
    assert "This remains an O4-B9 repair under WP-O4" in wp_o4_spec
    assert "does not create a new formal closure node" in wp_o4_spec
    assert "does not gate the reopened O4-B9 tail on residual WP-O3 or D3" in wp_o4_spec
    assert (
        "complete merge prerequisites are the already-landed WP-O4 baseline "
        "and the merged WP-O4-B1-CLOSE record"
    ) in wp_o4_spec
    assert (
        "prove a fresh exact-main preflight leaves zero ordinary and ignored "
        "source leaves"
    ) in wp_o4_spec

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
