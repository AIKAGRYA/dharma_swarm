#!/usr/bin/env python3
"""One-shot semantic rebase for the Humming V2 A0 admission branch.

This script is executed only from a temporary synchronization branch. It starts
from current merged main, overlays the already-hardened A0 intent and ledger,
then preserves the serialized Titanium WP-0D amendment before projections are
regenerated. It creates no runtime surface and grants no implementation,
deployment, credential, review, or merge authority.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

EXPECTED_NEXT_ITEMS = {
    "loop-closure-2026-06": {
        "humming-v2-p0-b-root-loop",
        "humming-v2-e1-cron-authority",
    },
    "merge-master-mike-d4-2026-06": {"humming-v2-enforcement-ack"},
    "organism-rewire-2026-07": {"humming-v2-host-ack"},
    "dharmagraph-engine-2026-07": {"humming-v2-p0-graph-adapter"},
    "sovereign-safety-tcb-2026-07": {
        "humming-v2-p0-k",
        "humming-v2-p0-h1a",
        "humming-v2-p0-h1b",
        "humming-v2-p0-h2a",
        "humming-v2-p0-h3-contract",
        "humming-v2-p0-b-contract",
    },
    "repository-titanium-hardening-2026-07": {
        "humming-v2-p0-harness-consumers",
        "humming-v2-p0-h6",
        "humming-v2-p0-b-adapters",
    },
}

WP0D_WHAT = (
    "First land the 2026-08-01 bounded specification amendment and ownership "
    "admission for tests/test_agent_work_packet.py and "
    "tests/test_make_onboarding_contract.py (approval is that PR's human "
    "merge). Then repair the current-main repeatability defects without "
    "weakening the 10-second item budget: split the six independent AgentOps "
    "closeout scenarios in tests/test_agent_work_packet.py, replace its "
    "environment-dependent hollow-module fixture with a deterministically "
    "absent module, add the measured pytest.mark.timeout repo-scale override "
    "for tests/test_make_onboarding_contract.py::"
    "test_make_report_root_rejects_hypothesis_cache_symlink registered in "
    "REPO_SCALE_OVERRIDES, and prove two consecutive clean make test-fast runs "
    "plus make test."
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--main-sha", required=True)
    parser.add_argument("--prior-head", required=True)
    return parser.parse_args()


def load_tracks(raw: str) -> tuple[dict, dict[str, dict]]:
    data = yaml.safe_load(raw)
    tracks = {track["id"]: track for track in data["active_tracks"]}
    return data, tracks


def preserve_wp0d(track_path: Path) -> None:
    raw = track_path.read_text(encoding="utf-8")

    anchor = "      - tests/test_fast_suite_isolation.py\n"
    if raw.count(anchor) != 1:
        raise SystemExit(
            "cannot bind WP-0D ownership: expected one fast-suite anchor, "
            f"observed {raw.count(anchor)}"
        )
    additions = []
    for path in (
        "tests/test_agent_work_packet.py",
        "tests/test_make_onboarding_contract.py",
    ):
        if f"      - {path}\n" not in raw:
            additions.append(f"      - {path}\n")
    if additions:
        raw = raw.replace(anchor, anchor + "".join(additions), 1)

    item_marker = "      - id: WP-0D\n"
    item_start = raw.find(item_marker)
    if item_start < 0:
        raise SystemExit("cannot bind WP-0D scope: item missing")
    what_start = raw.find("        what:", item_start)
    kind_start = raw.find("        kind:", what_start)
    if what_start < 0 or kind_start < 0:
        raise SystemExit("cannot delimit WP-0D what/kind fields")
    raw = (
        raw[:what_start]
        + f'        what: "{WP0D_WHAT}"\n'
        + raw[kind_start:]
    )
    track_path.write_text(raw, encoding="utf-8")


def append_sync_record(
    ledger_path: Path, *, main_sha: str, prior_head: str
) -> None:
    raw = ledger_path.read_text(encoding="utf-8")
    marker = "## A0 post-WP-0D branch synchronization"
    if marker in raw:
        return
    raw = raw.rstrip() + f"""

## A0 post-WP-0D branch synchronization

- 2026-08-01: merged main advanced to `{main_sha}` through PR #1177 after the
  original A0 branch was generated. The A0 branch was rebuilt from that exact
  main commit rather than textually force-merging divergent projections.
- The prior hardened A0 head was `{prior_head}`. Its governance intent and
  append-only ledger were overlaid onto current main; the two WP-0D owned test
  surfaces and the complete three-repair WP-0D task text were then preserved
  from merged main before all managed projections and DocOps counts were
  regenerated.
- The temporary synchronization branch and workflow are execution scaffolding
  only. They are not part of the A0 diff and must never merge into main.
"""
    ledger_path.write_text(raw, encoding="utf-8")


def assert_final(track_path: Path, ledger_path: Path) -> None:
    raw = track_path.read_text(encoding="utf-8")
    data, tracks = load_tracks(raw)
    if len(data["active_tracks"]) != 10:
        raise SystemExit(
            f"active-track count changed: {len(data['active_tracks'])}"
        )
    if any(track_id.startswith("humming-") for track_id in tracks):
        raise SystemExit("forbidden Humming active track created")

    expected_all = set().union(*EXPECTED_NEXT_ITEMS.values())
    observed_all: list[str] = []
    for owner, expected in EXPECTED_NEXT_ITEMS.items():
        ids = [
            str(item.get("id"))
            for item in tracks[owner].get("next_items") or []
        ]
        observed_all.extend(item_id for item_id in ids if item_id in expected_all)
        bad = sorted(item_id for item_id in expected if ids.count(item_id) != 1)
        if bad:
            raise SystemExit(f"{owner}: Humming queue multiplicity failure: {bad}")

    duplicates = sorted(
        item_id for item_id in expected_all if observed_all.count(item_id) != 1
    )
    if duplicates:
        raise SystemExit(f"portfolio-wide Humming multiplicity failure: {duplicates}")

    for owner, track in tracks.items():
        criterion_ids = {
            str(item.get("id"))
            for item in track.get("completion_criteria") or []
        }
        misplaced = sorted(criterion_ids & expected_all)
        if misplaced:
            raise SystemExit(
                f"{owner}: Humming items remain in completion criteria: "
                f"{misplaced}"
            )

    safety_owned = set(tracks["sovereign-safety-tcb-2026-07"]["owned_surfaces"])
    required_safety = {
        "dharma_swarm/action_effects/__init__.py",
        "dharma_swarm/action_effects/envelope.py",
        "dharma_swarm/action_effects/dispatcher.py",
        "dharma_swarm/action_effects/budget.py",
        "tests/test_action_budget.py",
    }
    missing_safety = sorted(required_safety - safety_owned)
    if missing_safety:
        raise SystemExit(f"missing exact action-effect surfaces: {missing_safety}")
    if "dharma_swarm/action_effects/**" in safety_owned:
        raise SystemExit("broad action_effects ownership remains")

    titanium = tracks["repository-titanium-hardening-2026-07"]
    titanium_owned = set(titanium["owned_surfaces"])
    required_wp0d = {
        "tests/test_agent_work_packet.py",
        "tests/test_make_onboarding_contract.py",
    }
    missing_wp0d = sorted(required_wp0d - titanium_owned)
    if missing_wp0d:
        raise SystemExit(f"merged WP-0D ownership lost: {missing_wp0d}")
    wp0d_items = [
        item for item in titanium.get("next_items") or [] if str(item.get("id")) == "WP-0D"
    ]
    if len(wp0d_items) != 1:
        raise SystemExit(f"WP-0D item multiplicity: {len(wp0d_items)}")
    wp0d_text = str(wp0d_items[0].get("what", ""))
    for token in (
        "tests/test_agent_work_packet.py",
        "tests/test_make_onboarding_contract.py",
        "REPO_SCALE_OVERRIDES",
        "two consecutive clean make test-fast runs plus make test",
    ):
        if token not in wp0d_text:
            raise SystemExit(f"WP-0D task lost required token: {token}")

    for token in (
        "SemanticActionProposal",
        "dharma_swarm/graph/effects.py",
        "dharma_swarm/action_effects/budget.py",
        "tests/test_action_budget.py",
    ):
        if token not in raw:
            raise SystemExit(f"A0 exact boundary missing: {token}")

    ledger = ledger_path.read_text(encoding="utf-8")
    for heading in (
        "## A0 pre-merge correction log",
        "## A0 post-WP-0D branch synchronization",
    ):
        if heading not in ledger:
            raise SystemExit(f"ledger evidence missing: {heading}")

    print("Humming A0 semantic rebase assertions: PASS")


def main() -> int:
    args = parse_args()
    root = args.repo_root.resolve()
    track_path = root / "docs/governance/ACTIVE_TRACK.yaml"
    ledger_path = (
        root
        / "docs/plans/handoffs/HUMMING_V2_EXECUTION_LEDGER_2026-08-01.md"
    )
    preserve_wp0d(track_path)
    append_sync_record(
        ledger_path, main_sha=args.main_sha, prior_head=args.prior_head
    )
    assert_final(track_path, ledger_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
