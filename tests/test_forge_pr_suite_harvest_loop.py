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
    harvest_command = next(command for command in commands if "forge_pr_suite_harvester.py" in command[1])
    assert harvest_command[harvest_command.index("--github-token-env") + 1] == "GITHUB_TOKEN,GH_TOKEN"


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


def test_harvest_loop_dedupes_candidates_across_cycles(tmp_path: Path) -> None:
    validation_invocations = 0

    def fake_runner(argv: Sequence[str], _cwd: Path, _timeout: int) -> pr_suite_harvest_loop.CommandResult:
        nonlocal validation_invocations
        args = list(argv)
        if "forge_pr_suite_harvester.py" in args[1]:
            out = Path(args[args.index("--out") + 1])
            out.write_text(
                json.dumps(
                    {
                        "repo": "example/project",
                        "pr_number": 7,
                        "base_sha": "base",
                        "head_sha": "head",
                        "merge_commit_sha": "merge",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            return pr_suite_harvest_loop.CommandResult(args, 0, json.dumps({"candidate_count": 1}))
        if "forge_pr_suite_validator.py" in args[1]:
            validation_invocations += 1
            out = Path(args[args.index("--out") + 1])
            out.write_text("", encoding="utf-8")
            assert "candidates_unique_c00" in args[args.index("--manifest") + 1]
            return pr_suite_harvest_loop.CommandResult(args, 1, json.dumps({"validated_count": 0, "failed_count": 1}))
        raise AssertionError(f"unexpected command: {args}")

    closeout = pr_suite_harvest_loop.run_harvest_loop(
        root=tmp_path,
        repo_root=tmp_path,
        db_path=tmp_path / "taskbed.db",
        run_id="loop-dedupe",
        repos=["example/project"],
        duration_seconds=60,
        max_cycles=2,
        sleep_seconds=0,
        command_runner=fake_runner,
        sleep_fn=lambda _seconds: None,
    )

    assert validation_invocations == 1
    assert closeout["candidate_count"] == 2
    assert closeout["unique_candidate_count"] == 1
    assert closeout["seen_candidate_count"] == 1
    events = [event["event"] for event in closeout["events"]]
    assert "validation_skipped_no_new_candidates" in events


def test_harvest_loop_forwards_setup_command_template(tmp_path: Path) -> None:
    validation_commands: list[list[str]] = []

    def fake_runner(argv: Sequence[str], _cwd: Path, _timeout: int) -> pr_suite_harvest_loop.CommandResult:
        args = list(argv)
        if "forge_pr_suite_harvester.py" in args[1]:
            out = Path(args[args.index("--out") + 1])
            out.write_text(json.dumps({"repo": "example/project", "pr_number": 5}) + "\n", encoding="utf-8")
            return pr_suite_harvest_loop.CommandResult(args, 0, json.dumps({"candidate_count": 1}))
        if "forge_pr_suite_validator.py" in args[1]:
            validation_commands.append(args)
            out = Path(args[args.index("--out") + 1])
            out.write_text("", encoding="utf-8")
            return pr_suite_harvest_loop.CommandResult(args, 1, json.dumps({"validated_count": 0, "failed_count": 1}))
        raise AssertionError(f"unexpected command: {args}")

    pr_suite_harvest_loop.run_harvest_loop(
        root=tmp_path,
        repo_root=tmp_path,
        db_path=tmp_path / "taskbed.db",
        run_id="loop-setup",
        repos=["example/project"],
        duration_seconds=60,
        max_cycles=1,
        sleep_seconds=0,
        setup_command_template="{python} -m pip install -e .",
        setup_timeout_seconds=1200,
        command_runner=fake_runner,
        sleep_fn=lambda _seconds: None,
    )

    assert validation_commands, "validator should have been invoked"
    cmd = validation_commands[0]
    assert "--setup-command-template" in cmd
    assert cmd[cmd.index("--setup-command-template") + 1] == "{python} -m pip install -e ."
    assert cmd[cmd.index("--setup-timeout-seconds") + 1] == "1200"


def test_harvest_loop_forwards_separate_validator_python(tmp_path: Path) -> None:
    validation_commands: list[list[str]] = []

    def fake_runner(argv: Sequence[str], _cwd: Path, _timeout: int) -> pr_suite_harvest_loop.CommandResult:
        args = list(argv)
        if "forge_pr_suite_harvester.py" in args[1]:
            out = Path(args[args.index("--out") + 1])
            out.write_text(json.dumps({"repo": "example/project", "pr_number": 8}) + "\n", encoding="utf-8")
            return pr_suite_harvest_loop.CommandResult(args, 0, json.dumps({"candidate_count": 1}))
        if "forge_pr_suite_validator.py" in args[1]:
            validation_commands.append(args)
            out = Path(args[args.index("--out") + 1])
            out.write_text("", encoding="utf-8")
            return pr_suite_harvest_loop.CommandResult(args, 1, json.dumps({"validated_count": 0, "failed_count": 1}))
        raise AssertionError(f"unexpected command: {args}")

    pr_suite_harvest_loop.run_harvest_loop(
        root=tmp_path,
        repo_root=tmp_path,
        db_path=tmp_path / "taskbed.db",
        run_id="loop-validator-python",
        repos=["example/project"],
        duration_seconds=60,
        max_cycles=1,
        sleep_seconds=0,
        python="/repo/python",
        validator_python="/target/venv/python",
        command_runner=fake_runner,
        sleep_fn=lambda _seconds: None,
    )

    assert validation_commands, "validator should have been invoked"
    cmd = validation_commands[0]
    assert cmd[0] == "/repo/python"
    assert cmd[cmd.index("--python") + 1] == "/target/venv/python"


def test_harvest_loop_omits_setup_flag_when_not_configured(tmp_path: Path) -> None:
    validation_commands: list[list[str]] = []

    def fake_runner(argv: Sequence[str], _cwd: Path, _timeout: int) -> pr_suite_harvest_loop.CommandResult:
        args = list(argv)
        if "forge_pr_suite_harvester.py" in args[1]:
            out = Path(args[args.index("--out") + 1])
            out.write_text(json.dumps({"repo": "example/project", "pr_number": 6}) + "\n", encoding="utf-8")
            return pr_suite_harvest_loop.CommandResult(args, 0, json.dumps({"candidate_count": 1}))
        if "forge_pr_suite_validator.py" in args[1]:
            validation_commands.append(args)
            out = Path(args[args.index("--out") + 1])
            out.write_text("", encoding="utf-8")
            return pr_suite_harvest_loop.CommandResult(args, 1, json.dumps({"validated_count": 0, "failed_count": 1}))
        raise AssertionError(f"unexpected command: {args}")

    pr_suite_harvest_loop.run_harvest_loop(
        root=tmp_path,
        repo_root=tmp_path,
        db_path=tmp_path / "taskbed.db",
        run_id="loop-nosetup",
        repos=["example/project"],
        duration_seconds=60,
        max_cycles=1,
        sleep_seconds=0,
        command_runner=fake_runner,
        sleep_fn=lambda _seconds: None,
    )

    assert validation_commands, "validator should have been invoked"
    assert "--setup-command-template" not in validation_commands[0]


def test_safe_run_id_rejects_dot_only_names() -> None:
    for bad in (".", "..", "..."):
        try:
            pr_suite_harvest_loop._safe_run_id(bad)
        except ValueError as exc:
            assert "dot-only" in str(exc)
        else:
            raise AssertionError(f"expected ValueError for {bad!r}")


def test_harvest_loop_rejects_run_id_that_escapes_root(tmp_path: Path) -> None:
    try:
        pr_suite_harvest_loop.run_harvest_loop(
            root=tmp_path,
            repo_root=tmp_path,
            db_path=tmp_path / "taskbed.db",
            run_id="../escape",
            repos=["example/project"],
            duration_seconds=60,
            max_cycles=1,
            sleep_seconds=0,
            command_runner=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not run")),
            sleep_fn=lambda _seconds: None,
        )
    except ValueError as exc:
        assert "single path segment" in str(exc)
    else:
        raise AssertionError("expected run_id escape to be rejected")
