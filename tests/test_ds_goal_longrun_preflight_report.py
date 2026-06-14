from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load_report_module():
    spec = importlib.util.spec_from_file_location(
        "ds_goal_longrun_preflight_report",
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "governance"
        / "ds_goal_longrun_preflight_report.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_ds_goal_preflight_report_flags_command_shaped_unpinned_lines(
    tmp_path: Path,
) -> None:
    mod = _load_report_module()
    doc = tmp_path / "docs" / "agent_tasks" / "goal.md"
    doc.parent.mkdir(parents=True)
    doc.write_text(
        "\n".join(
            [
                "# Goal",
                "Narrative mention: an earlier true Hydra launch using `ds-goal run`.",
                "- `ds-goal status --mission-id m1 --json --board-cards`",
                (
                    "DHARMA_SWARM_REPO=/Users/dhyana/dharma_swarm "
                    "/Users/dhyana/.dharma/bin/ds-goal run --mission-id m1"
                ),
            ]
        ),
        encoding="utf-8",
    )

    entries = mod.scan_ds_goal_commands(
        repo_root=tmp_path,
        scan_paths=[Path("docs/agent_tasks")],
    )

    assert [(entry.classification, entry.verb) for entry in entries] == [
        ("unsafe_unpinned", "status"),
        ("pinned", "run"),
    ]
    report = mod.build_report(entries)
    assert report["strict_passed"] is False
    assert report["unsafe_unpinned"] == 1


def test_ds_goal_preflight_report_counts_blocked_prevention_receipts(
    tmp_path: Path,
) -> None:
    mod = _load_report_module()
    state_root = tmp_path / "state"
    kernel_store = tmp_path / "kernel"
    mission_dir = state_root / "blocked-proof"
    mission_dir.mkdir(parents=True)
    (mission_dir / "mission.json").write_text(
        json.dumps(
            {
                "mission_id": "blocked-proof",
                "state_root": str(state_root),
                "kernel_store": str(kernel_store),
            }
        ),
        encoding="utf-8",
    )
    (mission_dir / "receipts.jsonl").write_text(
        json.dumps(
            {
                "event": "ds_goal_run",
                "status": "preflight_blocked",
                "mission_id": "blocked-proof",
                "task_id": "blocked-proof-t01",
                "created_at": "2026-06-14T00:00:00Z",
                "record_hash": "sha256:block",
                "ds_goal_longrun_preflight": {
                    "status": "blocked_unpinned_default_target",
                    "longrun_start_allowed": False,
                    "default_target_repo": "/Users/dhyana/dharma_swarm_main",
                    "repo_pin_source": "none",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    receipts = mod.scan_preflight_prevention_receipts(
        repo_root=tmp_path,
        receipt_roots=[state_root],
    )
    report = mod.build_report([], prevention_receipts=receipts)

    assert report["strict_passed"] is True
    assert report["preflight_prevention_receipts"] == 1
    assert report["valid_preflight_blocks"] == 1
    receipt = report["valid_prevention_receipts"][0]
    assert receipt["classification"] == "valid_preflight_block"
    assert receipt["runtime_db_evidence"] == "runtime_db_absent_under_state_root"
    assert receipt["kernel_store_evidence"] == "kernel_store_absent"


def test_ds_goal_preflight_report_fails_conflicting_prevention_receipts(
    tmp_path: Path,
) -> None:
    mod = _load_report_module()
    state_root = tmp_path / "state"
    mission_dir = state_root / "conflict-proof"
    mission_dir.mkdir(parents=True)
    (mission_dir / "mission.json").write_text(
        json.dumps(
            {
                "mission_id": "conflict-proof",
                "state_root": str(state_root),
                "kernel_store": str(tmp_path / "kernel"),
            }
        ),
        encoding="utf-8",
    )
    (mission_dir / "receipts.jsonl").write_text(
        json.dumps(
            {
                "event": "ds_goal_run",
                "status": "preflight_blocked",
                "mission_id": "conflict-proof",
                "task_id": "conflict-proof-t01",
                "ds_goal_longrun_preflight": {
                    "status": "pass_explicit_audited_checkout_pin",
                    "longrun_start_allowed": True,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    receipts = mod.scan_preflight_prevention_receipts(
        repo_root=tmp_path,
        receipt_roots=[state_root],
    )
    report = mod.build_report([], prevention_receipts=receipts)

    assert report["strict_passed"] is False
    assert report["conflicting_prevention_receipts"] == 1
    assert report["conflicting_prevention_entries"][0]["classification"] == (
        "conflicting_prevention_receipt"
    )


def test_ds_goal_preflight_report_strict_passes_for_current_repo(capsys) -> None:
    mod = _load_report_module()

    rc = mod.main(["--strict", "--json"])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["strict_passed"] is True
    assert payload["unsafe_unpinned"] == 0


def test_ds_goal_preflight_report_is_wired_into_governance_all() -> None:
    makefile = (Path(__file__).resolve().parents[1] / "Makefile").read_text(
        encoding="utf-8"
    )

    assert "ds-goal-longrun-preflight-check" in makefile.splitlines()[3]
    assert (
        "ds-goal-longrun-preflight-check:\n"
        "\t$(PYTHON) scripts/governance/ds_goal_longrun_preflight_report.py --strict"
    ) in makefile
    assert (
        "governance-all: semgrep gitleaks test-hygiene test-contracts "
        "nats-substrate-contract uplift-guards module-budget "
        "ds-goal-longrun-preflight-check docops-integrity"
    ) in makefile
