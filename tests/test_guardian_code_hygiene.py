import asyncio
import json
from pathlib import Path

from dharma_swarm.guardian_crew import _check_code_hygiene


def test_check_code_hygiene_reads_precomputed_findings(tmp_path: Path) -> None:
    findings_dir = tmp_path / "audit" / "quality" / "2026-05-09"
    findings_dir.mkdir(parents=True)
    findings_path = findings_dir / "findings.jsonl"
    findings_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "tool": "bandit",
                        "path": "dharma_swarm/example.py",
                        "line": 12,
                        "severity": "HIGH",
                        "suggested_action": "review",
                    }
                ),
                json.dumps(
                    {
                        "tool": "vulture",
                        "path": "dharma_swarm/example.py",
                        "line": 20,
                        "severity": "LOW",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = asyncio.run(_check_code_hygiene(tmp_path))

    assert len(result) == 1
    finding = result[0]
    assert finding.severity == "DEGRADED"
    assert finding.check == "CODE_HYGIENE:precomputed_findings"
    assert finding.file == str(findings_path)
    assert "2 precomputed code hygiene finding(s)" in finding.detail
    assert "'high': 1" in finding.detail
    assert "'proposed': 1" in finding.detail
    assert "'review': 1" in finding.detail


def test_check_code_hygiene_missing_file_is_warning(tmp_path: Path) -> None:
    result = asyncio.run(_check_code_hygiene(tmp_path))

    assert len(result) == 1
    assert result[0].severity == "WARNING"
    assert result[0].check == "CODE_HYGIENE:precomputed_findings"
