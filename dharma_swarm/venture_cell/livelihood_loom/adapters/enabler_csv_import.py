"""CSV adapter for Livelihood Loom enabler candidates."""

from __future__ import annotations

import csv
from pathlib import Path

from dharma_swarm.venture_cell.livelihood_loom.ontology import EnablerCompany, enabler_from_csv_row


def load_enabler_csv(path: str | Path, *, limit: int | None = None) -> list[EnablerCompany]:
    rows: list[EnablerCompany] = []
    with Path(path).open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            rows.append(enabler_from_csv_row(row))
            if limit is not None and len(rows) >= limit:
                break
    return rows
