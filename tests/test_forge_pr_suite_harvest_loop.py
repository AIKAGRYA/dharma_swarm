from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

from dharma_swarm.forge_v1.forge_v2 import pr_suite_harvest_loop


def test_harvest_loop_continues_when_validator_finds_no_fail_to_pass(tmp_path: Path) -> None:
    commands: list[list[str]] = []

    def fake_runner(argv: Sequence[str], _cwd: Path, _timeout: int) -> pr_suite_harvest_loop.CommandResult:
        args = list(argv)
        commands.append(args)
        if "forge_pr_suite_harvester.py" in args[1]:
            out = Path(args[args.index("--out") + 1])
            out.write_text(json.dumps({"repo": "example/project", "pr_number": 1}) + "\n", encoding="utf-8")
            return pr_suite_harvest_loop.CommandResult(args, 0, json.dumps({"candidate_count": 1}))
        if "forge_pr_suite_validator.py" in args[1]:
            out = Path(args[args.index("--out") + 1])
            out.write_text("", encoding="utf-8")
            return pr_suite_harvest_loop.CommandResult(args, 1, json.dumps({"validated_count": 0, "failed_count": 1}))
        raise AssertionError(f"unexpected command: {args}")

    closeout = pr_suite_harvest_loop.run_harvest_loop(
        root=tmp_path,
        repo_root=tmp_path,
        db_path=tmp_path / "taskbed.db",
        run_id="loop-no-ftp",
        repos=["example/project"],
        duration_seconds=60,
        max_cycles=1,
        sleep_seconds=0,
        command_runner=fake_runner,
        sleep_fn=lambda _seconds: None,
    )

    assert closeout["candidate_count"] == 1
    assert closeout["validated_count"] == 0
    assert closeout["imported_count"] == 0
    assert closeout["authority"]["live_apply_performed"] is False
    assert (tmp_path / "loop-no-ftp" / "closeout.json").exists()
    assert not any("forge_fresh_task_oracle.py" in command[1] for command in commands)


def test_harvest_loop_imports_validated_rows_and_receipts_closeout(tmp_path: Path) -> None:
    def fake_runner(argv: Sequence[str], _cwd: Path, _timeout: int) -> pr_suite_harvest_loop.CommandResult:
        args = list(argv)
        if "forge_pr_suite_harvester.py" in args[1]:
            out = Path(args[args.index("--out") + 1])
            out.write_text(json.dumps({"repo": "example/project", "pr_number": 2}) + "\n", encoding="utf-8")
            return pr_suite_harvest_loop.CommandResult(args, 0, json.dumps({"candidate_count": 1}))
        if "forge_pr_suite_validator.py" in args[1]:
            out = Path(args[args.index("--out") + 1])
            receipt_root = Path(args[args.index("--receipt-root") + 1])
            receipt_root.mkdir(parents=True, exist_ok=True)
            (receipt_root / "validation.json").write_text("{}", encoding="utf-8")
            out.write_text(
                json.dumps(
                    {
                        "repo": "example/project",
                        "pr_number": 2,
                        "fail_to_pass": ["tests/test_regression.py"],
                        "validation_state": "fail_to_pass_validated",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            return pr_suite_harvest_loop.CommandResult(args, 0, json.dumps({"validated_count": 1, "failed_count": 0}))
        if "forge_fresh_task_oracle.py" in args[1]:
            return pr_suite_harvest_loop.CommandResult(
                args,
                0,
                json.dumps({"imported_count": 1, "skipped_count": 0, "ledger_state_counts": {"fresh_heldout": 1}}),
            )
        raise AssertionError(f"unexpected command: {args}")

    closeout = pr_suite_harvest_loop.run_harvest_loop(
        root=tmp_path,
        repo_root=tmp_path,
        db_path=tmp_path / "taskbed.db",
        run_id="loop-imports",
        repos=["example/project"],
        duration_seconds=60,
        max_cycles=1,
        sleep_seconds=0,
        command_runner=fake_runner,
        sleep_fn=lambda _seconds: None,
    )

    closeout_path = tmp_path / "loop-imports" / "closeout.json"
    payload = json.loads(closeout_path.read_text(encoding="utf-8"))
    assert payload["closeout_sha256"] == closeout["closeout_sha256"]
    assert payload["validated_count"] == 1
    assert payload["imported_count"] == 1
    assert payload["validation_receipt_count"] == 1
    assert payload["authority"]["archive_fitness_mutated"] is False
