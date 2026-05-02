"""Render the repair score as a one-line morning briefing."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any


DEFAULT_SCORE_PATH = Path.home() / ".dharma" / "meta" / "r_repair_score.json"
NO_DATA_LINE = "Repair: no data yet (Component 1.7 awaiting first 30d of marks)"
MAX_LINE_CHARS = 200
NEAR_EIGENFORM_PREFIX = "⚠️ NEAR_EIGENFORM ⚠️ "


def render_repair_briefing(score_path: Path = DEFAULT_SCORE_PATH) -> str:
    payload = _load_payload(score_path)
    if not payload:
        return NO_DATA_LINE

    near_eigenform = bool(payload.get("near_eigenform"))
    prefix = NEAR_EIGENFORM_PREFIX if near_eigenform else ""
    notes = payload.get("notes") if isinstance(payload.get("notes"), list) else []
    first_note = str(notes[0]) if notes else ""

    line = (
        f"{prefix}Repair: agg={_fmt_rate(payload.get('r_aggregate'))} "
        f"(gate={_fmt_rate(payload.get('r_gate'))} "
        f"mut={_fmt_rate(payload.get('r_mutation'))} "
        f"wel={_fmt_rate(payload.get('r_welfare'))}) "
        f"n={int(payload.get('n_predictions_total') or 0)} "
        f"conf={_fmt_conf(payload.get('confidence'))} "
        f"{'[provisional] ' if payload.get('provisional') else ''}"
        f"[near_eigenform={near_eigenform}]"
    )
    if first_note:
        line = f"{line} notes: {first_note}"
    return _fit_line(line)


def main(score_path: Path = DEFAULT_SCORE_PATH) -> int:
    print(render_repair_briefing(score_path))
    return 0


def _load_payload(path: Path) -> dict[str, Any] | None:
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not text:
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _fmt_rate(value: Any) -> str:
    number = _coerce_number(value)
    if number is None:
        return "N/A"
    return f"{number:.2f}"


def _fmt_conf(value: Any) -> str:
    number = _coerce_number(value)
    if number is None:
        return "N/A"
    return f"{number:.1f}"


def _coerce_number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _fit_line(line: str) -> str:
    if len(line) <= MAX_LINE_CHARS:
        return line
    suffix = "..."
    return line[: MAX_LINE_CHARS - len(suffix)].rstrip() + suffix


__all__ = ["MAX_LINE_CHARS", "NO_DATA_LINE", "render_repair_briefing", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
