"""Read-only telic value projection from ontology DB.

Extracted from operating_facts.py to stay within the module line budget.
Reads Outcome/ValueEvent/Contribution counts and revenue USD totals.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any
from urllib.parse import quote


def read_telic_value_summary() -> dict[str, Any]:
    """Read-only projection of Outcome/ValueEvent/Contribution counts from ontology DB."""
    db_path = Path.home() / ".dharma" / "ontology.db"
    if not db_path.exists():
        return {}
    uri = "file:" + quote(str(db_path.resolve()), safe="/") + "?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
        try:
            counts: dict[str, int] = {}
            revenue_usd = 0.0
            for type_name in ("Outcome", "ValueEvent", "Contribution"):
                row = conn.execute(
                    "SELECT COUNT(*) FROM objects WHERE type_name = ?",
                    (type_name,),
                ).fetchone()
                counts[type_name] = int(row[0]) if row else 0
            rows = conn.execute(
                "SELECT properties FROM objects WHERE type_name = 'ValueEvent'"
                " ORDER BY created_at DESC LIMIT 100",
            ).fetchall()
            for (raw_props,) in rows:
                try:
                    props = json.loads(raw_props or "{}")
                except (json.JSONDecodeError, TypeError):
                    continue
                if isinstance(props, dict):
                    vk = props.get("value_kind", "")
                    if vk in ("paid_revenue", "contracted_revenue", "compute_reinvestment"):
                        try:
                            revenue_usd += float(props.get("economic_value_usd") or 0)
                        except (TypeError, ValueError):
                            pass
        finally:
            conn.close()
    except Exception:
        return {}
    return {"counts": counts, "revenue_usd": round(revenue_usd, 2)}
