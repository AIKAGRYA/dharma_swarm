"""Policy tests for scripts/governance/branch_ttl_check.py.

Fixture-only: no git, no network. The live collector is bypassed via the
--branches-json fixture path of main() and by calling stale_branches()
directly.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "governance" / "branch_ttl_check.py"

NOW = datetime(2026, 8, 30, 12, 0, 0, tzinfo=timezone.utc)


def _load_module():
    spec = importlib.util.spec_from_file_location("branch_ttl_check", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ttl = _load_module()


def _record(
    name: str,
    *,
    days_idle: float = 30,
    merged: bool = False,
    ahead: int | None = 1,
    behind: int | None = 100,
) -> "ttl.BranchRecord":
    return ttl.BranchRecord(
        name=name,
        tip_oid="b" * 40,
        tip_date=NOW - timedelta(days=days_idle),
        merged=merged,
        ahead=ahead,
        behind=behind,
    )


def test_stale_requires_idle_past_ttl_and_unmerged() -> None:
    records = [
        _record("stale/unmerged", days_idle=30),
        _record("fresh/unmerged", days_idle=3),
        _record("stale/merged", days_idle=90, merged=True),
        _record("edge/exactly-ttl", days_idle=14),
    ]

    stale = ttl.stale_branches(records, NOW, ttl_days=14)

    assert [record.name for record in stale] == ["stale/unmerged"]


def test_stale_sorted_oldest_first() -> None:
    records = [
        _record("b/newer-stale", days_idle=20),
        _record("a/older-stale", days_idle=60),
    ]

    stale = ttl.stale_branches(records, NOW, ttl_days=14)

    assert [record.name for record in stale] == ["a/older-stale", "b/newer-stale"]


def _write_fixture(tmp_path: Path, records: list["ttl.BranchRecord"]) -> Path:
    fixture = tmp_path / "branches.json"
    fixture.write_text(
        json.dumps(
            [
                {
                    "name": record.name,
                    "tip_oid": record.tip_oid,
                    "tip_date": record.tip_date.isoformat(),
                    "merged": record.merged,
                    "ahead": record.ahead,
                    "behind": record.behind,
                }
                for record in records
            ]
        ),
        encoding="utf-8",
    )
    return fixture


def test_advisory_prints_to_stderr_and_writes_nothing(
    tmp_path: Path,
    capsys,
) -> None:
    fixture = _write_fixture(
        tmp_path,
        [_record("stale/one"), _record("stale/two"), _record("fresh/three", days_idle=1)],
    )
    register = tmp_path / "BRANCH_TTL_REGISTER.md"

    exit_code = ttl.main(
        [
            "--advisory",
            "--branches-json",
            str(fixture),
            "--register",
            str(register),
            "--now",
            NOW.isoformat(),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == ""
    assert "2 stale local branch(es)" in captured.err
    assert str(register) in captured.err
    assert not register.exists()


def test_write_mode_renders_generated_register(
    tmp_path: Path,
    capsys,
) -> None:
    fixture = _write_fixture(
        tmp_path,
        [
            _record("stale/one", ahead=3, behind=70),
            _record("fresh/two", days_idle=1),
            _record("stale/merged", days_idle=90, merged=True),
        ],
    )
    register = tmp_path / "BRANCH_TTL_REGISTER.md"

    exit_code = ttl.main(
        [
            "--branches-json",
            str(fixture),
            "--register",
            str(register),
            "--now",
            NOW.isoformat(),
        ]
    )

    assert exit_code == 0
    text = register.read_text(encoding="utf-8")
    assert "role: report" in text
    assert "Generated artifact — do not hand-edit" in text
    assert "scripts/governance/branch_ttl_check.py" in text
    assert "stale: 1" in text
    assert "`stale/one`" in text
    assert "| 3 | 70 |" in text
    assert "fresh/two" not in text
    assert "stale/merged" not in text
    summary = capsys.readouterr().out
    assert "surveyed=3" in summary
    assert "stale=1" in summary


def test_write_mode_with_no_stale_branches_says_none(tmp_path: Path) -> None:
    fixture = _write_fixture(tmp_path, [_record("fresh/only", days_idle=1)])
    register = tmp_path / "BRANCH_TTL_REGISTER.md"

    exit_code = ttl.main(
        [
            "--branches-json",
            str(fixture),
            "--register",
            str(register),
            "--now",
            NOW.isoformat(),
        ]
    )

    assert exit_code == 0
    text = register.read_text(encoding="utf-8")
    assert "## Stale branches (0)" in text
    assert "None." in text
