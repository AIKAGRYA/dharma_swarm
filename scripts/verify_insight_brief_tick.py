#!/usr/bin/env python3
"""Verify one scheduled ontology-native Daily Insight Brief tick."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

WITA = ZoneInfo("Asia/Makassar")


@dataclass(frozen=True)
class ObjectRow:
    object_id: str
    type_name: str
    created_at: str
    created_by: str
    properties: dict


def _parse_date(value: str | None) -> date:
    if value:
        return date.fromisoformat(value)
    return datetime.now(WITA).date()


def _utc_bounds(local_date: date) -> tuple[str, str]:
    start = datetime.combine(local_date, time.min, tzinfo=WITA).astimezone(timezone.utc)
    end = datetime.combine(local_date, time.max, tzinfo=WITA).astimezone(timezone.utc)
    return start.isoformat().replace("+00:00", "Z"), end.isoformat().replace("+00:00", "Z")


def _load_rows(db_path: Path, start_utc: str, end_utc: str) -> list[ObjectRow]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            select id, type_name, created_at, created_by, properties
            from objects
            where type_name in ('KnowledgeArtifact', 'WitnessLog')
              and created_at >= ?
              and created_at <= ?
            order by created_at, id
            """,
            (start_utc, end_utc),
        ).fetchall()

    loaded: list[ObjectRow] = []
    for object_id, type_name, created_at, created_by, raw_props in rows:
        try:
            props = json.loads(raw_props or "{}")
        except json.JSONDecodeError:
            props = {}
        loaded.append(ObjectRow(object_id, type_name, created_at, created_by, props))
    return loaded


def _count(rows: list[ObjectRow], *, type_name: str, created_by: str) -> int:
    return sum(1 for row in rows if row.type_name == type_name and row.created_by == created_by)


def verify(local_date: date, db_path: Path, brief_dir: Path) -> int:
    expected_file = brief_dir / f"{local_date.isoformat()}-brief.md"
    start_utc, end_utc = _utc_bounds(local_date)
    failures: list[str] = []

    if not db_path.exists():
        failures.append(f"ontology db missing: {db_path}")
        rows: list[ObjectRow] = []
    else:
        rows = _load_rows(db_path, start_utc, end_utc)

    insight_artifacts = _count(rows, type_name="KnowledgeArtifact", created_by="insight_brief")
    insight_witnesses = _count(rows, type_name="WitnessLog", created_by="insight_brief")
    operator_rows = sum(1 for row in rows if row.created_by == "operator_brief")

    if insight_artifacts != 1:
        failures.append(f"expected exactly 1 insight_brief KnowledgeArtifact, found {insight_artifacts}")
    if insight_witnesses != 1:
        failures.append(f"expected exactly 1 insight_brief WitnessLog, found {insight_witnesses}")
    if operator_rows:
        failures.append(f"expected 0 operator_brief rows, found {operator_rows}")
    if not expected_file.exists():
        failures.append(f"brief file missing: {expected_file}")

    print(f"date={local_date.isoformat()}")
    print(f"utc_window={start_utc}..{end_utc}")
    print(f"db={db_path}")
    print(f"brief_file={expected_file}")
    print(f"insight_brief KnowledgeArtifact={insight_artifacts}")
    print(f"insight_brief WitnessLog={insight_witnesses}")
    print(f"operator_brief rows={operator_rows}")

    if failures:
        print("status=FAIL")
        for failure in failures:
            print(f"failure={failure}")
        return 1

    print("status=PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", help="Local WITA date to verify, YYYY-MM-DD")
    parser.add_argument(
        "--ontology-db",
        default=str(Path.home() / ".dharma" / "ontology.db"),
        help="Ontology SQLite database path",
    )
    parser.add_argument(
        "--brief-dir",
        default=str(Path.home() / "dharma_briefs"),
        help="Directory containing daily brief markdown files",
    )
    args = parser.parse_args()

    return verify(
        _parse_date(args.date),
        Path(args.ontology_db).expanduser(),
        Path(args.brief_dir).expanduser(),
    )


if __name__ == "__main__":
    sys.exit(main())
