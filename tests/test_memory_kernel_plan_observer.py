from __future__ import annotations

import json
from pathlib import Path

from scripts.memory_kernel_plan_observer import (
    collect_snapshot,
    collect_watched_files,
    main,
    parse_codex_processes,
)


def test_parse_codex_processes_extracts_codex_commands() -> None:
    processes = parse_codex_processes(
        "\n".join(
            [
                "123 1 00:01:02 /opt/bin/codex exec --model gpt-5",
                "456 1 00:00:02 /bin/zsh",
                "789 123 1-02:03:04 node /usr/local/bin/codex-agent",
            ]
        )
    )

    assert [process.pid for process in processes] == [123, 789]
    assert processes[0].ppid == 1
    assert processes[0].command == "codex"
    assert processes[1].elapsed == "1-02:03:04"
    assert len(processes[1].command_sha256) == 64


def test_collect_watched_files_is_bounded_and_hashable(tmp_path: Path) -> None:
    watched = tmp_path / "dharma_swarm/memory_kernel"
    watched.mkdir(parents=True)
    (watched / "atoms.py").write_text("x = 1\n", encoding="utf-8")
    (watched / "__pycache__").mkdir()
    (watched / "__pycache__/atoms.cpython-313.pyc").write_bytes(b"noise")
    (tmp_path / "unwatched.py").write_text("ignore me\n", encoding="utf-8")

    files = collect_watched_files(
        tmp_path,
        watch_paths=("dharma_swarm/memory_kernel",),
        include_file_hashes=True,
    )

    assert len(files) == 1
    assert files[0].path == "dharma_swarm/memory_kernel/atoms.py"
    assert len(files[0].sha256) == 64


def test_collect_snapshot_handles_non_git_repo(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "dharma_swarm/memory_kernel").mkdir(parents=True)
    (tmp_path / "dharma_swarm/memory_kernel/atoms.py").write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setattr(
        "scripts.memory_kernel_plan_observer.collect_codex_processes",
        lambda: (),
    )

    snapshot = collect_snapshot(
        tmp_path,
        watch_paths=("dharma_swarm/memory_kernel",),
    )

    assert snapshot.branch is None
    assert snapshot.head is None
    assert snapshot.watched_file_count == 1
    assert snapshot.codex_process_count == 0


def test_plan_observer_cli_writes_jsonl_once(tmp_path: Path, capsys, monkeypatch) -> None:
    (tmp_path / "dharma_swarm/memory_kernel").mkdir(parents=True)
    (tmp_path / "dharma_swarm/memory_kernel/atoms.py").write_text("x = 1\n", encoding="utf-8")
    output = tmp_path / "observer.jsonl"
    monkeypatch.setattr(
        "scripts.memory_kernel_plan_observer.collect_codex_processes",
        lambda: (),
    )

    assert (
        main(
            [
                "--repo-root",
                str(tmp_path),
                "--output",
                str(output),
                "--once",
                "--watch-path",
                "dharma_swarm/memory_kernel",
            ]
        )
        == 0
    )

    printed = capsys.readouterr().out
    row = json.loads(output.read_text(encoding="utf-8"))
    assert '"watched_file_count"' in printed
    assert row["watched_file_count"] == 1
    assert row["codex_process_count"] == 0
