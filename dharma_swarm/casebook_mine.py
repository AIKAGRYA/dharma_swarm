"""Mine candidate casebook entries from existing memory/control logs.

This module is intentionally a miner, not a judge. It scans witness,
stigmergy/register, and evolution logs for high-information events and writes
candidate records for human or cross-family review. Canonical casebook
promotion should happen through the same memory/register path as other trusted
atoms, not inside this script.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable


DHARMA_HOME = Path.home() / ".dharma"
DEFAULT_WITNESS_DIR = DHARMA_HOME / "witness"
DEFAULT_STIGMERGY_MARKS = DHARMA_HOME / "stigmergy" / "marks.jsonl"
DEFAULT_STIGMERGY_ARCHIVE = DHARMA_HOME / "stigmergy" / "archive.jsonl"
DEFAULT_EVOLUTION_ARCHIVE = DHARMA_HOME / "evolution" / "archive.jsonl"
DEFAULT_OUTPUT = DHARMA_HOME / "meta" / "casebook_candidates.jsonl"

BLOCK_DECISIONS = {"BLOCK", "BLOCKED", "REFUSE", "REFUSED", "DENY", "DENIED", "HOLD"}
ALLOW_DECISIONS = {"ALLOW", "ALLOWED", "PASS", "PASSED", "OK"}
HIGH_SEVERITIES = {"high", "critical", "block", "severe"}


def mine_candidates(
    *,
    witness_dir: Path = DEFAULT_WITNESS_DIR,
    stigmergy_marks: Path = DEFAULT_STIGMERGY_MARKS,
    stigmergy_archive: Path = DEFAULT_STIGMERGY_ARCHIVE,
    evolution_archive: Path = DEFAULT_EVOLUTION_ARCHIVE,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Return diverse, deterministic casebook candidates."""
    register_rows = list(_iter_jsonl(stigmergy_marks, source="stigmergy"))
    register_rows.extend(_iter_jsonl(stigmergy_archive, source="stigmergy"))
    marks_by_subject = _index_marks_by_subject(register_rows)

    candidates: list[dict[str, Any]] = []
    candidates.extend(_mine_witness(witness_dir, marks_by_subject))
    candidates.extend(_mine_stigmergy(register_rows))
    candidates.extend(_mine_evolution(evolution_archive))

    deduped = {c["candidate_id"]: c for c in candidates}
    return _diverse_sample(sorted(deduped.values(), key=_candidate_sort_key), limit=limit)


def write_candidates(candidates: Iterable[dict[str, Any]], output_path: Path = DEFAULT_OUTPUT) -> bool:
    """Write candidates as JSONL. Returns False on write failure."""
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        text = "\n".join(json.dumps(c, sort_keys=True, default=str) for c in candidates)
        output_path.write_text(text + ("\n" if text else ""), encoding="utf-8")
        return True
    except OSError:
        return False


def main(
    *,
    witness_dir: Path = DEFAULT_WITNESS_DIR,
    stigmergy_marks: Path = DEFAULT_STIGMERGY_MARKS,
    stigmergy_archive: Path = DEFAULT_STIGMERGY_ARCHIVE,
    evolution_archive: Path = DEFAULT_EVOLUTION_ARCHIVE,
    output_path: Path = DEFAULT_OUTPUT,
    limit: int = 200,
) -> int:
    candidates = mine_candidates(
        witness_dir=witness_dir,
        stigmergy_marks=stigmergy_marks,
        stigmergy_archive=stigmergy_archive,
        evolution_archive=evolution_archive,
        limit=limit,
    )
    return 0 if write_candidates(candidates, output_path=output_path) else 1


def _mine_witness(
    witness_dir: Path,
    marks_by_subject: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    if not witness_dir.exists():
        return candidates

    for path in sorted(witness_dir.glob("witness_*.jsonl")):
        for line_no, entry in _iter_jsonl(path, source="witness"):
            ts = _parse_ts(entry.get("ts") or entry.get("timestamp"))
            decision = _decision(entry)
            subject_id = _subject_id(entry)
            reasons: list[str] = []

            if decision in BLOCK_DECISIONS:
                reasons.append(f"rare decision {decision}")
            if decision in ALLOW_DECISIONS and _has_mark_within_24h(subject_id, ts, marks_by_subject):
                reasons.append("ALLOW/PASS followed by register mark within 24h")
            if _severity(entry) in HIGH_SEVERITIES:
                reasons.append("high severity field")

            if reasons:
                candidates.append(
                    _candidate(
                        source="witness",
                        source_path=path,
                        source_line=line_no,
                        ts=entry.get("ts") or entry.get("timestamp") or "",
                        action_payload=entry,
                        context={"phase": entry.get("phase", ""), "subject_id": subject_id},
                        original_decision=decision,
                        candidate_for_rejudgement=True,
                        selection_reason="; ".join(reasons),
                    )
                )
    return candidates


def _mine_stigmergy(rows: list[tuple[int, dict[str, Any], Path]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for line_no, entry, path in rows:
        reasons: list[str] = []
        decision = _decision(entry) or str(entry.get("recommended_action") or "").upper()
        if decision in BLOCK_DECISIONS:
            reasons.append(f"rare decision {decision}")
        if entry.get("corrects"):
            reasons.append("walk-back corrects field is non-null")
        if _severity(entry) in HIGH_SEVERITIES:
            reasons.append("high severity field")

        if reasons:
            candidates.append(
                _candidate(
                    source="stigmergy",
                    source_path=path,
                    source_line=line_no,
                    ts=entry.get("ts") or entry.get("timestamp") or "",
                    action_payload=entry,
                    context={
                        "subject_id": entry.get("subject_id", ""),
                        "plane": entry.get("plane", ""),
                        "discipline": entry.get("discipline", ""),
                    },
                    original_decision=decision or "unknown",
                    candidate_for_rejudgement=True,
                    selection_reason="; ".join(reasons),
                )
            )
    return candidates


def _mine_evolution(evolution_archive: Path) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for line_no, entry in _iter_jsonl(evolution_archive, source="evolution"):
        reasons: list[str] = []
        kept = entry.get("kept")
        if kept is False or str(kept).lower() == "false":
            reasons.append("mutation reverted or not kept after measurement window")
        if entry.get("corrects"):
            reasons.append("walk-back corrects field is non-null")
        if _severity(entry) in HIGH_SEVERITIES:
            reasons.append("high severity field")

        if reasons:
            candidates.append(
                _candidate(
                    source="evolution",
                    source_path=evolution_archive,
                    source_line=line_no,
                    ts=entry.get("ts") or entry.get("timestamp") or entry.get("created_at") or "",
                    action_payload=entry,
                    context={
                        "component": entry.get("component", ""),
                        "mutation_id": entry.get("mutation_id", entry.get("id", "")),
                    },
                    original_decision=str(entry.get("decision") or entry.get("outcome") or "unknown"),
                    candidate_for_rejudgement=True,
                    selection_reason="; ".join(reasons),
                )
            )
    return candidates


def _iter_jsonl(path: Path, *, source: str) -> Iterable[tuple[int, dict[str, Any]]]:
    if not path.exists():
        return
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for line_no, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(payload, dict):
            if source == "stigmergy":
                yield line_no, payload, path  # type: ignore[misc]
            else:
                yield line_no, payload


def _index_marks_by_subject(
    rows: Iterable[tuple[int, dict[str, Any], Path]],
) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for _, entry, _ in rows:
        subject = str(entry.get("subject_id") or entry.get("subject") or "")
        if subject:
            out[subject].append(entry)
    return out


def _has_mark_within_24h(
    subject_id: str,
    ts: datetime | None,
    marks_by_subject: dict[str, list[dict[str, Any]]],
) -> bool:
    if not subject_id or ts is None:
        return False
    until = ts + timedelta(hours=24)
    for mark in marks_by_subject.get(subject_id, []):
        mark_ts = _parse_ts(mark.get("ts") or mark.get("timestamp"))
        if mark_ts and ts <= mark_ts <= until:
            return True
    return False


def _candidate(
    *,
    source: str,
    source_path: Path,
    source_line: int,
    ts: str,
    action_payload: dict[str, Any],
    context: dict[str, Any],
    original_decision: str,
    candidate_for_rejudgement: bool,
    selection_reason: str,
) -> dict[str, Any]:
    return {
        "candidate_id": _candidate_id(source_path, source_line, ts),
        "source": source,
        "source_path": str(source_path),
        "source_line": source_line,
        "ts": ts,
        "action_payload": action_payload,
        "context": context,
        "original_decision": original_decision or "unknown",
        "candidate_for_rejudgement": candidate_for_rejudgement,
        "selection_reason": selection_reason,
    }


def _candidate_id(source_path: Path, source_line: int, ts: str) -> str:
    seed = f"{source_path}|{source_line}|{ts}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return f"CAN-{int(digest[:10], 16) % 100000000:08d}"


def _diverse_sample(candidates: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    if limit <= 0 or len(candidates) <= limit:
        return candidates

    per_source_cap = max(1, int(limit * 0.8))
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        if len(buckets[candidate["source"]]) < per_source_cap:
            buckets[candidate["source"]].append(candidate)

    out: list[dict[str, Any]] = []
    source_names = sorted(buckets)
    while len(out) < limit and any(buckets.values()):
        for source in source_names:
            if buckets[source] and len(out) < limit:
                out.append(buckets[source].pop(0))
    return sorted(out, key=_candidate_sort_key)


def _candidate_sort_key(candidate: dict[str, Any]) -> tuple[str, str, int]:
    return (
        str(candidate.get("source", "")),
        str(candidate.get("source_path", "")),
        int(candidate.get("source_line") or 0),
    )


def _decision(entry: dict[str, Any]) -> str:
    for key in ("decision", "outcome", "outcome_raw", "recommended_action", "gate_result"):
        value = entry.get(key)
        if value:
            return str(value).strip().upper()
    return ""


def _subject_id(entry: dict[str, Any]) -> str:
    for key in ("subject_id", "prediction_id", "action_id", "task_id"):
        value = entry.get(key)
        if value:
            return str(value)
    return str(entry.get("action") or "")


def _severity(entry: dict[str, Any]) -> str:
    return str(entry.get("severity") or entry.get("risk") or "").strip().lower()


def _parse_ts(raw: Any) -> datetime | None:
    if not raw:
        return None
    try:
        ts = datetime.fromisoformat(str(raw))
    except (TypeError, ValueError):
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts


__all__ = ["mine_candidates", "write_candidates", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
