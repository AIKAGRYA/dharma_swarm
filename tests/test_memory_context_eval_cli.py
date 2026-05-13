from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from scripts.memory_context_eval import main


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _sqlite_db(path: Path, statements: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        for statement in statements:
            conn.execute(statement)
        conn.commit()


def _fixture_memory_home(tmp_path: Path) -> tuple[Path, Path]:
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
    return home, repo


def test_context_eval_cli_defaults_to_no_live_home(capsys, tmp_path: Path) -> None:
    assert main(["--repo-root", str(tmp_path), "--dry-run"]) == 0

    payload = json.loads(capsys.readouterr().out)

    assert payload["current_context"] is None
    assert payload["memory_kernel"] is None
    assert payload["hard_failure_count"] == 0


def test_context_eval_cli_lists_builtin_cases(capsys) -> None:
    assert main(["--list-cases"]) == 0

    payload = json.loads(capsys.readouterr().out)

    case_ids = {case["case_id"] for case in payload["cases"]}
    assert "current_context_redaction" in case_ids
    assert "projection_omitted_by_default" in case_ids


def test_context_eval_cli_runs_builtin_cases(capsys, tmp_path: Path) -> None:
    assert (
        main(
            [
                "--repo-root",
                str(tmp_path),
                "--run-default-cases",
                "--dry-run",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)

    assert isinstance(payload["passed"], bool)
    assert payload["case_count"] >= 6
    assert "/Users/dhyana" not in json.dumps(payload, sort_keys=True)
    assert "abc123" not in json.dumps(payload, sort_keys=True)


def test_context_eval_cli_requires_explicit_memory_home(capsys, tmp_path: Path) -> None:
    assert (
        main(
            [
                "--repo-root",
                str(tmp_path),
                "--memory-surface",
                "home.conversation_log",
                "--dry-run",
            ]
        )
        == 2
    )

    payload = json.loads(capsys.readouterr().out)

    assert "--memory-surface requires explicit --memory-home" in payload["error"]


def test_context_eval_cli_writes_redacted_current_context_reports(tmp_path: Path) -> None:
    out_json = tmp_path / "context_eval.json"
    out_md = tmp_path / "context_eval.md"

    assert (
        main(
            [
                "--repo-root",
                str(tmp_path),
                "--current-context-text",
                "Use /Users/dhyana/.dharma/db/memory_plane.db secret_token=abc123",
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

    assert payload["current_context"]["finding_count"] == 2
    assert payload["current_context"]["hard_failure_count"] == 0
    assert "/Users/dhyana" not in payload_text
    assert "abc123" not in payload_text
    assert "/Users/dhyana" not in markdown
    assert "abc123" not in markdown


def test_context_eval_cli_rejects_memory_surface_outputs(capsys, tmp_path: Path) -> None:
    out_json = tmp_path / ".dharma/context_eval.json"

    assert (
        main(
            [
                "--repo-root",
                str(tmp_path),
                "--current-context-text",
                "safe context",
                "--output-json",
                str(out_json),
            ]
        )
        == 2
    )

    payload = json.loads(capsys.readouterr().out)
    assert "output paths under memory surfaces are not allowed" in payload["error"]
    assert not out_json.exists()


def test_context_eval_cli_rejects_memory_surface_output_override(
    capsys,
    tmp_path: Path,
) -> None:
    out_json = tmp_path / ".dharma/context_eval.json"

    assert (
        main(
            [
                "--repo-root",
                str(tmp_path),
                "--current-context-text",
                "safe context",
                "--output-json",
                str(out_json),
                "--allow-memory-surface-output",
            ]
        )
        == 2
    )

    payload = json.loads(capsys.readouterr().out)
    assert "output paths under memory surfaces are not allowed" in payload["error"]
    assert not out_json.exists()


def test_context_eval_cli_reads_explicit_memory_surface(capsys, tmp_path: Path) -> None:
    home, repo = _fixture_memory_home(tmp_path)

    assert (
        main(
            [
                "--repo-root",
                str(repo),
                "--memory-home",
                str(home),
                "--memory-surface",
                "home.conversation_log",
                "--dry-run",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)

    assert payload["memory_kernel"]["atom_count"] == 1
    assert payload["memory_kernel"]["pack"]["admitted_count"] == 0
    assert payload["current_context"] is None


def test_context_eval_cli_parity_current_text_redacts_path_and_token(
    capsys,
    tmp_path: Path,
) -> None:
    out_json = tmp_path / "context_parity.json"
    out_md = tmp_path / "context_parity.md"

    assert (
        main(
            [
                "--repo-root",
                str(tmp_path),
                "--run-parity-eval",
                "--current-context-text",
                "Use /Users/dhyana/.dharma/db/memory_plane.db secret_token=abc123",
                "--output-json",
                str(out_json),
                "--output-md",
                str(out_md),
            ]
        )
        == 0
    )

    stdout = capsys.readouterr().out
    payload_text = out_json.read_text(encoding="utf-8")
    markdown = out_md.read_text(encoding="utf-8")
    payload = json.loads(payload_text)

    assert payload["legacy_report"]["finding_count"] == 2
    assert payload["memory_report"]["atom_count"] == 0
    assert "<local_path_redacted>" in payload["legacy_report"]["redacted_preview"]
    assert "<secret_like_redacted>" in payload["legacy_report"]["redacted_preview"]
    for text in (stdout, payload_text, markdown):
        assert "/Users/dhyana" not in text
        assert "abc123" not in text


def test_context_eval_cli_parity_uses_explicit_home_without_default_live_home(
    capsys,
    tmp_path: Path,
) -> None:
    home, repo = _fixture_memory_home(tmp_path)

    assert (
        main(
            [
                "--repo-root",
                str(repo),
                "--run-parity-eval",
                "--current-context-text",
                "safe context",
                "--dry-run",
            ]
        )
        == 0
    )
    default_payload = json.loads(capsys.readouterr().out)

    assert default_payload["memory_report"]["atom_count"] == 0
    assert "memory_kernel_lane_has_no_kernel_or_atoms" in default_payload["warnings"]

    assert (
        main(
            [
                "--repo-root",
                str(repo),
                "--run-parity-eval",
                "--memory-home",
                str(home),
                "--memory-surface",
                "home.conversation_log",
                "--dry-run",
            ]
        )
        == 0
    )
    explicit_payload = json.loads(capsys.readouterr().out)

    assert explicit_payload["memory_report"]["atom_count"] == 1
    assert explicit_payload["memory_report"]["pack"]["admitted_count"] == 0
    assert "legacy_current_context_not_read_without_state_dir_or_text" in (
        explicit_payload["warnings"]
    )


def test_context_eval_cli_rejects_memory_surface_outputs_in_parity_mode(
    capsys,
    tmp_path: Path,
) -> None:
    out_json = tmp_path / ".dharma/context_parity.json"

    assert (
        main(
            [
                "--repo-root",
                str(tmp_path),
                "--run-parity-eval",
                "--current-context-text",
                "safe context",
                "--output-json",
                str(out_json),
            ]
        )
        == 2
    )

    payload = json.loads(capsys.readouterr().out)
    assert "output paths under memory surfaces are not allowed" in payload["error"]
    assert not out_json.exists()
