from __future__ import annotations

from pathlib import Path

from dharma_swarm.venture_cell.darshan.cli import main


def test_cli_build_and_validate_bundle(tmp_path: Path, capsys) -> None:
    root = tmp_path / "artifacts"
    rc = main(
        [
            "build-bundle",
            "--title",
            "After the Feed",
            "--date",
            "2026-05-26",
            "--root",
            str(root),
        ]
    )
    assert rc == 0
    bundle_path = Path(capsys.readouterr().out.strip())
    assert bundle_path.exists()

    rc = main(["validate-bundle", str(bundle_path)])
    assert rc == 0
    assert "valid:" in capsys.readouterr().out


def test_cli_validate_bundle_reports_missing_file(tmp_path: Path, capsys) -> None:
    root = tmp_path / "artifacts"
    main(["build-bundle", "--title", "Broken", "--root", str(root)])
    bundle_path = Path(capsys.readouterr().out.strip())
    (bundle_path / "article.md").unlink()

    rc = main(["validate-bundle", str(bundle_path)])

    captured = capsys.readouterr()
    assert rc == 2
    assert "missing required file: article.md" in captured.err


def test_cli_log_polsia(tmp_path: Path, capsys) -> None:
    log_path = tmp_path / "polsia.jsonl"
    rc = main(
        [
            "log-polsia",
            "--track",
            "observatory",
            "--prompt-given",
            "Create a source-pack workflow.",
            "--expected-output",
            "Checklist",
            "--quality-score",
            "0.7",
            "--log-path",
            str(log_path),
        ]
    )

    assert rc == 0
    assert Path(capsys.readouterr().out.strip()) == log_path
    assert log_path.exists()
    assert "Create a source-pack workflow." in log_path.read_text(encoding="utf-8")


def test_cli_emit_handoff(tmp_path: Path, capsys) -> None:
    root = tmp_path / "artifacts"
    main(["build-bundle", "--title", "Handoff", "--root", str(root)])
    bundle_path = Path(capsys.readouterr().out.strip())

    rc = main(["emit-handoff", str(bundle_path)])

    assert rc == 0
    assert Path(capsys.readouterr().out.strip()).name == "polsia_handoff.json"
