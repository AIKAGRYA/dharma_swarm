from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from scripts.memory_context_shadow_sweep import (
    default_shadow_scenarios,
    main,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _sqlite_db(path: Path, statements: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        for statement in statements:
            conn.execute(statement)
        conn.commit()


def test_shadow_sweep_lists_scenarios(capsys) -> None:
    assert main(["--list-scenarios"]) == 0

    payload = json.loads(capsys.readouterr().out)

    scenario_ids = {scenario["scenario_id"] for scenario in payload["scenarios"]}
    assert payload["scenario_count"] == len(default_shadow_scenarios())
    assert "normal_task_context" in scenario_ids
    assert "sensitive_contamination_context" in scenario_ids
    assert "large_noisy_context" in scenario_ids


def test_shadow_sweep_dry_run_redacts_sensitive_scenario(capsys, tmp_path: Path) -> None:
    assert main(["--repo-root", str(tmp_path), "--dry-run"]) == 0

    stdout = capsys.readouterr().out
    payload = json.loads(stdout)

    assert payload["scenario_count"] == len(default_shadow_scenarios())
    assert payload["hard_failure_count"] == 0
    assert "/Users/dhyana" not in stdout
    assert "sample_placeholder" not in stdout
    assert "aaaaaaaaaaaaaaaa" not in stdout
    assert "API_KEY" not in stdout
    assert "Authorization" not in stdout


def test_shadow_sweep_writes_redacted_json_and_markdown(tmp_path: Path) -> None:
    out_json = tmp_path / "shadow_sweep.json"
    out_md = tmp_path / "shadow_sweep.md"

    assert (
        main(
            [
                "--repo-root",
                str(tmp_path),
                "--scenario",
                "sensitive_contamination_context",
                "--output-json",
                str(out_json),
                "--output-md",
                str(out_md),
            ]
        )
        == 0
    )

    payload_text = out_json.read_text(encoding="utf-8")
    markdown = out_md.read_text(encoding="utf-8")
    payload = json.loads(payload_text)

    assert payload["scenario_count"] == 1
    for text in (payload_text, markdown):
        assert "/Users/dhyana" not in text
        assert "sample_placeholder" not in text
        assert "aaaaaaaaaaaaaaaa" not in text
        assert "API_KEY" not in text
        assert "Authorization" not in text
    assert "# Memory Context Shadow Sweep" in markdown


def test_shadow_sweep_rejects_memory_surface_outputs(capsys, tmp_path: Path) -> None:
    out_json = tmp_path / ".dharma" / "shadow_sweep.json"

    assert (
        main(
            [
                "--repo-root",
                str(tmp_path),
                "--output-json",
                str(out_json),
            ]
        )
        == 2
    )

    payload = json.loads(capsys.readouterr().out)
    assert "output paths under memory surfaces are not allowed" in payload["error"]
    assert not out_json.exists()


def test_shadow_sweep_reads_explicit_memory_surface(capsys, tmp_path: Path) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    _sqlite_db(
        home / ".dharma/db/memory_plane.db",
        [
            "CREATE TABLE conversation_turns(id INTEGER PRIMARY KEY, content TEXT, timestamp TEXT)",
            "INSERT INTO conversation_turns(content, timestamp) VALUES ('turn one', '2026-05-11T01:01:00Z')",
        ],
    )
    _write(home / ".dharma/conversation_log/2026-05-11.jsonl", '{"content": "hidden"}\n')

    assert (
        main(
            [
                "--repo-root",
                str(repo),
                "--memory-home",
                str(home),
                "--memory-surface",
                "home.conversation_log",
                "--scenario",
                "normal_task_context",
                "--dry-run",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    memory_report = payload["reports"][0]["report"]["memory_report"]

    assert memory_report["atom_count"] == 1
