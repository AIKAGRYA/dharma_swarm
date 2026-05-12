"""Executive bridge that populates the opportunity board from live signals."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from dharma_swarm.shakti_executive.inputs import read_all_signals
from dharma_swarm.shakti_executive.models import ExecutiveResult, OpportunityCandidate
from dharma_swarm.shakti_executive.scoring import candidates_from_signals


class ShaktiExecutive:
    """Layer C populator for ``meta/opportunity_board.json``.

    The executive is intentionally thin. It reads existing perception outputs,
    ranks them, and updates the canonical board consumed by opportunity_refill.
    It does not write frontier tasks, spawn agents, mutate code, or bypass
    TelicSeam; downstream execution remains owned by existing lanes.
    """

    def __init__(self, state_dir: str | Path | None = None) -> None:
        self.state_dir = _state_dir(state_dir)
        self.meta_dir = self.state_dir / "meta"
        self.board_path = self.meta_dir / "opportunity_board.json"
        self.report_path = self.meta_dir / "shakti_executive_latest.md"

    def run(
        self,
        *,
        write: bool = False,
        top_k: int = 12,
        min_score: float = 45.0,
    ) -> ExecutiveResult:
        """Run the executive and optionally publish selected opportunities."""
        errors: list[str] = []
        existing = _read_board(self.board_path, errors=errors)
        signals = read_all_signals(self.state_dir)
        candidates = candidates_from_signals(signals)
        selected = [
            candidate for candidate in candidates
            if candidate.final_score >= min_score
        ][:top_k]
        merged = _merge_board(existing, selected)

        report_path: str | None = None
        if write:
            self.meta_dir.mkdir(parents=True, exist_ok=True)
            _write_board_atomic(self.board_path, merged)
            self.report_path.write_text(
                _render_report(selected, before=len(existing), after=len(merged)),
                encoding="utf-8",
            )
            report_path = str(self.report_path)

        return ExecutiveResult(
            dry_run=not write,
            scanned_signals=len(signals),
            generated_candidates=len(candidates),
            selected_candidates=len(selected),
            board_count_before=len(existing),
            board_count_after=len(merged) if write else len(existing),
            board_path=str(self.board_path),
            report_path=report_path,
            errors=tuple(errors),
        )

    def preview(
        self,
        *,
        top_k: int = 12,
        min_score: float = 45.0,
    ) -> list[dict[str, Any]]:
        """Return selected board entries without writing state."""
        signals = read_all_signals(self.state_dir)
        candidates = candidates_from_signals(signals)
        return [
            candidate.to_board_entry()
            for candidate in candidates
            if candidate.final_score >= min_score
        ][:top_k]


def _state_dir(state_dir: str | Path | None) -> Path:
    if state_dir is not None:
        return Path(state_dir).expanduser()
    configured = os.getenv("DHARMA_HOME") or os.getenv("DHARMA_STATE_DIR")
    if configured:
        return Path(configured).expanduser()
    return Path("~/.dharma").expanduser()


def _read_board(path: Path, *, errors: list[str]) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8") or "[]")
    except json.JSONDecodeError as exc:
        errors.append(f"malformed_board: {exc}")
        return []
    if not isinstance(raw, list):
        errors.append("malformed_board: root is not a list")
        return []
    return [
        entry
        for entry in raw
        if isinstance(entry, dict) and not _is_legacy_internal_board_entry(entry)
    ]


def _merge_board(
    existing: list[dict[str, Any]],
    candidates: Iterable[OpportunityCandidate],
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for entry in existing:
        key = _entry_key(entry)
        merged[key] = entry
    for candidate in candidates:
        entry = candidate.to_board_entry()
        key = _entry_key(entry)
        prior = merged.get(key)
        if prior is None:
            merged[key] = entry
            continue
        prior_score = _as_float(prior.get("final_score"))
        if candidate.final_score >= prior_score:
            merged[key] = _combine_entry(prior, entry)
    rows = list(merged.values())
    rows.sort(key=lambda entry: _as_float(entry.get("final_score")), reverse=True)
    return rows


def _write_board_atomic(path: Path, rows: list[dict[str, Any]]) -> None:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    if path.exists():
        backup = path.with_name(f"{path.name}.bak.{timestamp}")
        backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(rows, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def _render_report(
    candidates: list[OpportunityCandidate],
    *,
    before: int,
    after: int,
) -> str:
    lines = [
        "# Shakti Executive Latest",
        "",
        f"- board_count_before: {before}",
        f"- board_count_after: {after}",
        f"- selected_candidates: {len(candidates)}",
        "",
    ]
    for candidate in candidates:
        lines.append(
            f"- {candidate.final_score:.2f} [{candidate.domain}] {candidate.title}"
        )
        lines.append(f"  why_now: {candidate.why_now}")
    return "\n".join(lines).rstrip() + "\n"


def _entry_key(entry: dict[str, Any]) -> str:
    opp_id = str(entry.get("opportunity_id") or "").strip()
    if opp_id:
        return f"id:{opp_id}"
    title = str(entry.get("title") or "").lower().strip()
    domain = str(entry.get("domain") or "").lower().strip()
    return f"title:{domain}:{title}"


def _is_legacy_internal_board_entry(entry: dict[str, Any]) -> bool:
    """Drop pre-split internal rows that were incorrectly stored as zeitgeist."""
    title = str(entry.get("title") or "").lower()
    if title.startswith("keywords in ") or title.startswith("repair: high gate block rate"):
        return True
    if title == "high stigmergy density":
        return True
    evidence = " ".join(str(item).lower() for item in entry.get("evidence_signals") or [])
    return "gate block rate" in evidence or "source: local_scan" in evidence


def _combine_entry(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    combined = dict(old)
    combined.update(new)
    old_evidence = list(old.get("evidence_signals") or [])
    new_evidence = list(new.get("evidence_signals") or [])
    evidence: list[str] = []
    for item in old_evidence + new_evidence:
        text = str(item)
        if text not in evidence:
            evidence.append(text)
    combined["evidence_signals"] = evidence[:12]
    return combined


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
