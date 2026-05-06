"""Input readers for the Shakti executive.

These readers deliberately stay boring: they normalize existing Dharma state
files into ExecutiveSignal objects and never call providers or mutate runtime.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dharma_swarm.shakti_executive.models import ExecutiveSignal


def read_all_signals(state_dir: Path, *, max_zeitgeist: int = 80) -> list[ExecutiveSignal]:
    """Read supported signal sources under ``state_dir``."""
    signals: list[ExecutiveSignal] = []
    signals.extend(read_zeitgeist_history(state_dir, max_lines=max_zeitgeist))
    signals.extend(read_latest_scout_reports(state_dir))
    seed = read_recognition_seed(state_dir)
    if seed is not None:
        signals.append(seed)
    signals.extend(read_operator_directives(state_dir))
    return signals


def read_zeitgeist_history(state_dir: Path, *, max_lines: int = 80) -> list[ExecutiveSignal]:
    """Read recent ``meta/zeitgeist.jsonl`` entries."""
    path = state_dir / "meta" / "zeitgeist.jsonl"
    rows = _read_jsonl_tail(path, max_lines=max_lines)
    signals: list[ExecutiveSignal] = []
    for idx, row in enumerate(rows):
        title = str(row.get("title") or "").strip()
        if not title:
            continue
        category = str(row.get("category") or "zeitgeist").strip() or "zeitgeist"
        keywords = tuple(str(k) for k in list(row.get("keywords") or [])[:8])
        signals.append(
            ExecutiveSignal(
                source="zeitgeist",
                title=title,
                category=category,
                description=str(row.get("description") or ""),
                relevance_score=_float(row.get("relevance_score"), default=0.3),
                confidence=0.75,
                evidence_ref=str(row.get("id") or f"line:{idx}"),
                keywords=keywords,
                raw=row,
            )
        )
    return signals


def read_latest_scout_reports(state_dir: Path) -> list[ExecutiveSignal]:
    """Read ``scouts/*/latest.json`` without depending on global SCOUTS_DIR."""
    root = state_dir / "scouts"
    if not root.exists():
        return []

    signals: list[ExecutiveSignal] = []
    for latest in sorted(root.glob("*/latest.json")):
        row = _read_json(latest)
        if not isinstance(row, dict):
            continue
        domain = str(row.get("domain") or latest.parent.name)
        for idx, finding in enumerate(list(row.get("findings") or [])):
            if not isinstance(finding, dict):
                continue
            title = str(finding.get("title") or "").strip()
            if not title:
                continue
            evidence_ref = str(finding.get("file_path") or latest)
            line_number = finding.get("line_number")
            if line_number:
                evidence_ref = f"{evidence_ref}:{line_number}"
            signals.append(
                ExecutiveSignal(
                    source=f"scout:{domain}",
                    title=title,
                    category=str(finding.get("category") or "finding"),
                    description=str(finding.get("description") or ""),
                    relevance_score=_severity_relevance(str(finding.get("severity") or "")),
                    confidence=_float(finding.get("confidence"), default=0.7),
                    domain_hint=domain,
                    evidence_ref=evidence_ref,
                    suggested_action=str(finding.get("suggested_action") or ""),
                    raw={"report": row, "finding": finding, "index": idx},
                )
            )
    return signals


def read_recognition_seed(state_dir: Path, *, max_chars: int = 900) -> ExecutiveSignal | None:
    """Read the current recognition seed as one strategic signal."""
    path = state_dir / "meta" / "recognition_seed.md"
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        return None
    compact = " ".join(line.strip() for line in text.splitlines() if line.strip())
    compact = compact[:max_chars]
    return ExecutiveSignal(
        source="recognition_seed",
        title="Recognition seed strategic attractor",
        category="strategic_context",
        description=compact,
        relevance_score=0.55,
        confidence=0.65,
        domain_hint="strategic_vision",
        evidence_ref=str(path),
        keywords=tuple(_extract_keywords(compact)),
    )


def read_operator_directives(state_dir: Path) -> list[ExecutiveSignal]:
    """Read optional operator directive files as high-priority signals."""
    candidates = [
        state_dir / "meta" / "operator_directives.md",
        state_dir / "meta" / "OPERATOR_DIRECTIVES.md",
        state_dir / "OPERATOR_DIRECTIVES.md",
    ]
    signals: list[ExecutiveSignal] = []
    seen_files: set[tuple[int, int]] = set()
    for path in candidates:
        if not path.exists():
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        file_key = (stat.st_dev, stat.st_ino)
        if file_key in seen_files:
            continue
        seen_files.add(file_key)
        text = path.read_text(encoding="utf-8", errors="replace")
        for line_number, line in _directive_lines(text):
            signals.append(
                ExecutiveSignal(
                    source="operator_directive",
                    title=_short_title(line),
                    category="operator_directive",
                    description=line,
                    relevance_score=0.9,
                    confidence=0.95,
                    domain_hint="operator_priority",
                    evidence_ref=f"{path}:{line_number}",
                    keywords=tuple(_extract_keywords(line)),
                )
            )
    return signals


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _read_jsonl_tail(path: Path, *, max_lines: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return []
    rows: list[dict[str, Any]] = []
    for line in lines[-max_lines:]:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _float(value: Any, *, default: float) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def _severity_relevance(severity: str) -> float:
    return {
        "critical": 1.0,
        "high": 0.85,
        "medium": 0.65,
        "low": 0.4,
        "info": 0.25,
    }.get(severity.lower(), 0.45)


def _directive_lines(text: str) -> list[tuple[int, str]]:
    lines: list[tuple[int, str]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith("#"):
            continue
        stripped = _clean_directive_line(line)
        if not stripped:
            continue
        if len(stripped) < 8:
            continue
        lines.append((line_number, stripped))
    return lines[:12]


def _clean_directive_line(line: str) -> str:
    stripped = line.strip()
    if stripped.startswith(("- ", "* ")):
        stripped = stripped[2:].strip()
    marker, dot, rest = stripped.partition(".")
    if dot and marker.isdigit() and rest.startswith(" "):
        stripped = rest.strip()
    return stripped.strip(" \t-*#")


def _short_title(text: str, *, limit: int = 140) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    head = compact[:limit].rsplit(" ", 1)[0]
    return head.rstrip(".,:;")


def _extract_keywords(text: str) -> list[str]:
    words = []
    for raw in text.lower().replace("/", " ").replace("_", " ").split():
        word = raw.strip(".,:;()[]{}'\"")
        if len(word) < 5:
            continue
        if word in {"there", "their", "about", "which", "should"}:
            continue
        words.append(word)
    seen: set[str] = set()
    out: list[str] = []
    for word in words:
        if word in seen:
            continue
        seen.add(word)
        out.append(word)
        if len(out) >= 8:
            break
    return out
