"""Tests for quality report ingestion routing."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from dharma_swarm.slop import SlopFinding
from scripts.governance import route_quality_findings as rqf


def _validate(rows: list[dict]) -> list[SlopFinding]:
    return [SlopFinding.model_validate(row) for row in rows]


def test_existing_vulture_parser_emits_normalized_dead_code() -> None:
    rows = rqf.parse_vulture(
        "dharma_swarm/example.py:42: unused function 'unused_fn' (91%)\n"
    )

    findings = _validate(rows)

    assert findings[0].tool == "vulture"
    assert findings[0].detector_family == "dead_code"
    assert findings[0].issue_type == "unused_function"
    assert findings[0].path == "dharma_swarm/example.py"
    assert findings[0].line == 42
    assert rows[0]["kind"] == "function"
    assert rows[0]["confidence_percent"] == 91


def test_existing_radon_parser_emits_normalized_complexity() -> None:
    rows = rqf.parse_radon_cc(
        "dharma_swarm/example.py\n"
        "    F 123:0 complex_function - F\n"
    )

    findings = _validate(rows)

    assert findings[0].tool == "radon-cc"
    assert findings[0].detector_family == "complexity"
    assert findings[0].line == 123
    assert rows[0]["grade"] == "F"


def test_existing_bandit_parser_emits_normalized_security() -> None:
    rows = rqf.parse_bandit(
        ">> Issue: [B602:subprocess_popen_with_shell_equals_true] shell=True\n"
        "   Severity: HIGH   Confidence: HIGH\n"
        "   Location: dharma_swarm/example.py:7\n"
    )

    findings = _validate(rows)

    assert findings[0].tool == "bandit"
    assert findings[0].detector_family == "security"
    assert findings[0].severity == "high"
    assert findings[0].line == 7


def test_pyright_json_parser_emits_type_safety_finding() -> None:
    rows = rqf.parse_pyright_json(
        json.dumps(
            {
                "generalDiagnostics": [
                    {
                        "file": "dharma_swarm/example.py",
                        "severity": "error",
                        "message": "Argument of type str cannot be assigned",
                        "rule": "reportArgumentType",
                        "range": {"start": {"line": 12, "character": 8}},
                    }
                ]
            }
        )
    )

    findings = _validate(rows)

    assert findings[0].tool == "pyright"
    assert findings[0].detector_family == "type_safety"
    assert findings[0].issue_type == "reportArgumentType"
    assert findings[0].line == 12


def test_mypy_text_parser_emits_type_safety_finding() -> None:
    rows = rqf.parse_mypy(
        'dharma_swarm/example.py:5: error: Incompatible return value type [return-value]\n'
    )

    findings = _validate(rows)

    assert findings[0].tool == "mypy"
    assert findings[0].detector_family == "type_safety"
    assert findings[0].issue_type == "return_value"
    assert findings[0].line == 5


def test_since_last_run_dedupes_against_previous_findings_jsonl(
    tmp_path: Path, monkeypatch
) -> None:
    report = tmp_path / "mypy.txt"
    report.write_text(
        'dharma_swarm/example.py:5: error: Incompatible return value type [return-value]\n',
        encoding="utf-8",
    )
    out_dir = tmp_path / "audit" / "2026-05-09"
    (out_dir / "proposals").mkdir(parents=True)

    previous = rqf.parse_mypy(report.read_text(encoding="utf-8"))
    rqf.annotate_keys(previous)
    (out_dir / "findings.jsonl").write_text(
        "\n".join(json.dumps(row) for row in previous) + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(rqf, "AUDIT_BASE", tmp_path / "audit")
    monkeypatch.setattr(rqf, "today_dir", lambda: out_dir)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "route_quality_findings.py",
            "--tool",
            "mypy",
            "--input",
            str(report),
            "--since-last-run",
        ],
    )

    assert rqf.main() == 0
    assert (
        out_dir / "findings.jsonl"
    ).read_text(encoding="utf-8") == "\n".join(
        json.dumps(row) for row in previous
    ) + "\n"


def test_since_last_run_appends_only_new_findings(tmp_path: Path, monkeypatch) -> None:
    report = tmp_path / "mypy.txt"
    report.write_text(
        'dharma_swarm/example.py:5: error: Incompatible return value type [return-value]\n'
        'dharma_swarm/new.py:8: error: Name "x" is not defined [name-defined]\n',
        encoding="utf-8",
    )
    out_dir = tmp_path / "audit" / "2026-05-09"
    (out_dir / "proposals").mkdir(parents=True)

    previous = rqf.parse_mypy(
        'dharma_swarm/example.py:5: error: Incompatible return value type [return-value]\n'
    )
    rqf.annotate_keys(previous)
    previous_payload = "\n".join(json.dumps(row) for row in previous) + "\n"
    (out_dir / "findings.jsonl").write_text(previous_payload, encoding="utf-8")

    monkeypatch.setattr(rqf, "AUDIT_BASE", tmp_path / "audit")
    monkeypatch.setattr(rqf, "today_dir", lambda: out_dir)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "route_quality_findings.py",
            "--tool",
            "mypy",
            "--input",
            str(report),
            "--since-last-run",
        ],
    )

    assert rqf.main() == 0
    rows = [
        json.loads(line)
        for line in (out_dir / "findings.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len(rows) == 2
    assert rows[0]["path"] == "dharma_swarm/example.py"
    assert rows[1]["path"] == "dharma_swarm/new.py"


def test_all_with_missing_reports_and_invalid_json_do_not_crash(
    tmp_path: Path, monkeypatch
) -> None:
    reports = tmp_path / "quality-reports"
    reports.mkdir()
    (reports / "semgrep.json").write_text("not json", encoding="utf-8")
    out_dir = tmp_path / "audit" / "2026-05-09"
    (out_dir / "proposals").mkdir(parents=True)

    monkeypatch.setattr(rqf, "QUALITY_REPORTS", reports)
    monkeypatch.setattr(rqf, "AUDIT_BASE", tmp_path / "audit")
    monkeypatch.setattr(rqf, "today_dir", lambda: out_dir)
    monkeypatch.setattr(sys, "argv", ["route_quality_findings.py", "--all"])

    assert rqf.main() == 0
    assert (out_dir / "findings.jsonl").exists()
