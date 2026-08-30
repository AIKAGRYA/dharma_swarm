"""CLI wiring: dgc rudra run|status|stop through the dgc entrypoint."""

from __future__ import annotations

from pathlib import Path


from dharma_swarm import dgc_cli
from dharma_swarm.terminal_commands.rudra import (
    cmd_rudra_run,
    cmd_rudra_status,
    cmd_rudra_stop,
)
from tests.fixtures.rudra.helpers import (
    make_base_repo,
    make_mission_yaml,
    write_mission,
)


def test_parser_accepts_rudra_subcommands() -> None:
    parser = dgc_cli._build_parser()
    args = parser.parse_args(["rudra", "run", "m.yaml"])
    assert args.command == "rudra" and args.rudra_cmd == "run"
    args = parser.parse_args(["rudra", "status", "some-id", "--json"])
    assert args.rudra_cmd == "status" and args.json
    args = parser.parse_args(["rudra", "stop", "some-id", "--reason", "done"])
    assert args.rudra_cmd == "stop" and args.reason == "done"


def test_rudra_no_subcommand_has_no_dispatch_target() -> None:
    parser = dgc_cli._build_parser()
    args = parser.parse_args(["rudra"])
    assert args.command == "rudra"
    assert getattr(args, "rudra_cmd", None) is None


def test_status_unknown_mission(tmp_path: Path, capsys) -> None:
    repo, _base = make_base_repo(tmp_path)
    code = cmd_rudra_status(
        "no-such-mission", repo_path=str(repo), state_dir=str(tmp_path / "state")
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "UNKNOWN" in out


def test_stop_unknown_mission(tmp_path: Path) -> None:
    repo, _base = make_base_repo(tmp_path)
    code = cmd_rudra_stop(
        "no-such-mission", "why", repo_path=str(repo),
        state_dir=str(tmp_path / "state"),
    )
    assert code == 1


def test_run_admission_rejection_exit_code(tmp_path: Path, capsys) -> None:
    """An already-green base is ALREADY_SATISFIED, not a RUDRA success."""
    repo, base = make_base_repo(tmp_path, fixed=True)
    mission_path = write_mission(tmp_path, make_mission_yaml(repo, base))
    code = cmd_rudra_run(
        str(mission_path), repo_path=str(repo), state_dir=str(tmp_path / "state")
    )
    assert code == 3
    assert "ALREADY_SATISFIED" in capsys.readouterr().out


def test_run_blocked_environment_exit_code(tmp_path: Path, capsys) -> None:
    """No executor binding: nonzero BLOCKED_ENVIRONMENT, never a skip."""
    repo, base = make_base_repo(tmp_path)
    mission_path = write_mission(tmp_path, make_mission_yaml(repo, base))
    code = cmd_rudra_run(
        str(mission_path), repo_path=str(repo), state_dir=str(tmp_path / "state")
    )
    assert code == 2
    assert "BLOCKED_ENVIRONMENT" in capsys.readouterr().out
