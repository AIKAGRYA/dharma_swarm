"""Input readers for the Shakti executive.

These readers deliberately stay boring: they normalize existing Dharma state
files into ExecutiveSignal objects and never call providers or mutate runtime.
"""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from typing import Any
from urllib.parse import quote

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
    signals.extend(read_telic_feedback(state_dir))
    signals.extend(read_dispatcher_health(state_dir))
    signals.extend(read_campaign_manifests(state_dir))
    signals.extend(read_sealed_packet_archive_results(state_dir))
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
        if _is_legacy_internal_zeitgeist_row(row):
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


def _is_legacy_internal_zeitgeist_row(row: dict[str, Any]) -> bool:
    """Filter pre-split internal health rows out of the external S4 reader."""
    if str(row.get("source") or "") == "local_scan":
        return True
    title = str(row.get("title") or "").lower()
    keywords = {str(k).lower() for k in list(row.get("keywords") or [])}
    internal_keywords = {"gate_block", "gate_warn", "witness", "telos_gates"}
    if keywords & internal_keywords:
        return True
    return title.startswith("keywords in ") or "gate block rate" in title


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


def read_telic_feedback(state_dir: Path, *, max_rows: int = 40) -> list[ExecutiveSignal]:
    """Read Outcome / ValueEvent / Contribution rows from the ontology DB."""
    rows = _read_ontology_objects(
        state_dir / "ontology.db",
        ("Outcome", "ValueEvent", "Contribution"),
        limit=max_rows,
    )
    signals: list[ExecutiveSignal] = []
    for row in rows:
        type_name = str(row.get("type_name") or "")
        props = dict(row.get("properties") or {})
        obj_id = str(row.get("id") or "")
        if type_name == "Outcome":
            signals.append(_outcome_signal(obj_id, props, row))
        elif type_name == "ValueEvent":
            signals.append(_value_event_signal(obj_id, props, row))
        elif type_name == "Contribution":
            signals.append(_contribution_signal(obj_id, props, row))
    return signals


def read_dispatcher_health(state_dir: Path) -> list[ExecutiveSignal]:
    """Read the opportunity dispatcher health facade as feedback."""
    path = state_dir / "meta" / "opportunity_dispatcher.health.json"
    row = _read_json(path)
    if not isinstance(row, dict):
        return []

    failures = int(_float(row.get("consecutive_failures"), default=0.0))
    pending = int(_float(row.get("last_run_pending_count"), default=0.0))
    dispatched = int(_float(row.get("last_run_dispatched"), default=0.0))
    in_flight = int(_float(row.get("last_run_observed_in_flight"), default=0.0))
    errors = [str(e) for e in list(row.get("last_run_errors") or [])[:3]]
    paused = bool(row.get("last_run_paused") or False)

    relevance = 0.45
    title = "Opportunity dispatcher health summary"
    suggested = "Keep monitoring dispatcher throughput."
    if failures:
        relevance = min(1.0, 0.72 + failures * 0.08)
        title = f"Opportunity dispatcher has {failures} consecutive failure(s)"
        suggested = "Investigate dispatcher failures before adding more opportunities."
    elif paused:
        relevance = 0.78
        title = "Opportunity dispatcher is paused"
        suggested = "Resolve dispatcher pause before promoting new opportunity work."
    elif pending and dispatched == 0:
        relevance = 0.7
        title = "Opportunity dispatcher has pending work but dispatched nothing"
        suggested = "Check promotion gates, budget, and campaign manifests."

    description = (
        f"pending={pending}; dispatched={dispatched}; in_flight={in_flight}; "
        f"errors={'; '.join(errors) if errors else 'none'}"
    )
    return [
        ExecutiveSignal(
            source="dispatcher_health",
            title=title,
            category="dispatcher_health",
            description=description,
            relevance_score=relevance,
            confidence=0.82,
            domain_hint="runtime_feedback",
            evidence_ref=str(path),
            keywords=("dispatcher", "campaign", "feedback", "opportunity"),
            suggested_action=suggested,
            raw=row,
        )
    ]


def read_campaign_manifests(state_dir: Path, *, max_manifests: int = 40) -> list[ExecutiveSignal]:
    """Read campaign manifests as opportunity feedback."""
    root = state_dir / "campaigns"
    if not root.exists():
        return []

    manifests = sorted(
        (path for path in root.glob("*/manifest.json") if path.is_file()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )[:max_manifests]
    signals: list[ExecutiveSignal] = []
    for path in manifests:
        row = _read_json(path)
        if not isinstance(row, dict):
            continue
        opp_id = str(row.get("opportunity_id") or path.parent.name)
        stages = dict(row.get("stages") or {})
        counts: dict[str, int] = {}
        for stage in stages.values():
            if isinstance(stage, dict):
                status = str(stage.get("status") or "unknown")
                counts[status] = counts.get(status, 0) + 1
        bad = sum(counts.get(s, 0) for s in ("failed", "quarantined", "abandoned", "blocked"))
        completed = counts.get("completed", 0)
        in_flight = sum(counts.get(s, 0) for s in ("promoted", "dispatched"))
        if bad:
            relevance = min(1.0, 0.78 + bad * 0.06)
            title = f"Campaign {opp_id} has blocked or failed stage feedback"
            suggested = "Use campaign failure evidence before selecting the next opportunity move."
        elif completed and completed == len(stages):
            relevance = 0.58
            title = f"Campaign {opp_id} completed all tracked stages"
            suggested = "Promote the proven campaign pattern or harvest a knowledge artifact."
        elif in_flight:
            relevance = 0.5
            title = f"Campaign {opp_id} is still in flight"
            suggested = "Avoid duplicate opportunity expansion until in-flight stages settle."
        else:
            relevance = 0.42
            title = f"Campaign {opp_id} is present but has no decisive feedback"
            suggested = "Monitor the campaign before changing priority."
        signals.append(
            ExecutiveSignal(
                source="campaign_manifest",
                title=title,
                category="campaign_feedback",
                description=f"stage_counts={counts}",
                relevance_score=relevance,
                confidence=0.78,
                domain_hint="runtime_feedback",
                evidence_ref=str(path),
                keywords=("campaign", "opportunity", "feedback", *counts.keys()),
                suggested_action=suggested,
                raw=row,
            )
        )
    return signals


def read_sealed_packet_archive_results(state_dir: Path, *, max_lines: int = 80) -> list[ExecutiveSignal]:
    """Read Darwin archive entries produced by sealed packet shadow application."""
    path = state_dir / "evolution" / "archive.jsonl"
    rows = _read_jsonl_tail(path, max_lines=max_lines)
    signals: list[ExecutiveSignal] = []
    for idx, row in enumerate(rows):
        test_results = dict(row.get("test_results") or {})
        sealed = dict(test_results.get("sealed_packet") or {})
        if not sealed and row.get("change_type") != "sealed_packet":
            continue
        shadow = bool(sealed.get("shadow") if sealed else True)
        diff_missing = bool(sealed.get("diff_missing") or False)
        pass_rate = _float(test_results.get("pass_rate"), default=0.5)
        relevance = 0.58 if pass_rate >= 1.0 and not diff_missing else 0.82
        mode = "shadow" if shadow else "live"
        title = f"Sealed packet archived through Darwin {mode} evaluation"
        if diff_missing:
            title = "Sealed packet archived without diff artifact"
        signals.append(
            ExecutiveSignal(
                source="darwin_archive",
                title=title,
                category="sealed_packet_archive",
                description=str(row.get("description") or "")[:600],
                relevance_score=relevance,
                confidence=0.8,
                domain_hint="runtime_feedback",
                evidence_ref=f"{path}:tail:{idx}",
                keywords=("sealed", "packet", "darwin", "shadow", "proof"),
                suggested_action="Use sealed packet proof results when selecting the next build move.",
                raw=row,
            )
        )
    return signals


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _read_ontology_objects(
    path: Path,
    type_names: tuple[str, ...],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    if not path.exists() or not type_names:
        return []
    uri = "file:" + quote(str(path.resolve()), safe="/") + "?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
        conn.row_factory = sqlite3.Row
        try:
            rows = []
            for type_name in type_names:
                rows.extend(
                    conn.execute(
                        """
                        SELECT id, type_name, properties, created_at
                        FROM objects
                        WHERE type_name = ?
                        ORDER BY created_at DESC
                        LIMIT ?
                        """,
                        (type_name, int(limit)),
                    ).fetchall()
                )
            rows.sort(key=lambda row: str(row["created_at"] or ""), reverse=True)
            rows = rows[: int(limit)]
        finally:
            conn.close()
    except Exception:
        return []

    out: list[dict[str, Any]] = []
    for row in rows:
        try:
            properties = json.loads(row["properties"] or "{}")
        except json.JSONDecodeError:
            properties = {}
        out.append({
            "id": row["id"],
            "type_name": row["type_name"],
            "properties": properties if isinstance(properties, dict) else {},
            "created_at": row["created_at"],
        })
    return out


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


def _outcome_signal(obj_id: str, props: dict[str, Any], raw: dict[str, Any]) -> ExecutiveSignal:
    success = bool(props.get("success"))
    task_id = str(props.get("task_id") or "")
    summary = str(props.get("result_summary") or "")
    error = str(props.get("error") or "")
    outcome_kind = str(props.get("outcome_kind") or "task")
    is_revenue = outcome_kind == "revenue" or task_id.startswith("revenue-")
    try:
        amount = float(props.get("economic_amount_usd") or 0)
    except (TypeError, ValueError):
        amount = 0.0
    if is_revenue:
        title = f"Revenue {'payment' if success else 'failure'}"
        if amount:
            title = f"{title}: ${amount:.2f}"
    else:
        title = f"{'Successful' if success else 'Failed'} task outcome"
    if task_id:
        title = f"{title}: {task_id}"
    domain_hint = "external_revenue" if is_revenue else "runtime_feedback"
    relevance = 0.78 if is_revenue and success else (0.58 if success else 0.88)
    keywords = ["outcome", "telic", "feedback"]
    keywords.append("revenue" if is_revenue else ("success" if success else "failure"))
    if is_revenue:
        keywords.append("paid" if success else "failed_revenue")
    return ExecutiveSignal(
        source="telic:Outcome",
        title=title,
        category="runtime_outcome",
        description=(summary or error)[:700],
        relevance_score=relevance,
        confidence=0.82,
        domain_hint=domain_hint,
        evidence_ref=f"ontology://Outcome/{obj_id}",
        keywords=tuple(keywords),
        suggested_action=(
            "Increase opportunity ranking for proven revenue patterns."
            if is_revenue and success
            else "Investigate failed outcome before expanding this opportunity lane."
            if not success
            else "Harvest the successful outcome as a reusable pattern."
        ),
        raw=raw,
    )


def _value_event_signal(obj_id: str, props: dict[str, Any], raw: dict[str, Any]) -> ExecutiveSignal:
    composite = _float(props.get("composite_value"), default=0.5)
    value_kind = str(props.get("value_kind") or "task")
    is_revenue = value_kind in ("paid_revenue", "contracted_revenue", "compute_reinvestment")
    task_type = str(props.get("task_type") or "")
    try:
        usd = float(props.get("economic_value_usd") or 0)
    except (TypeError, ValueError):
        usd = 0.0
    low_value = composite < 0.45 and not is_revenue
    if is_revenue:
        title = f"Revenue ValueEvent: ${usd:.2f} ({value_kind})"
        relevance = min(0.92, 0.72 + min(usd, 10000.0) / 50000.0)
    else:
        title = f"ValueEvent composite score {composite:.2f}"
        relevance = max(0.45, 1.0 - composite) if low_value else 0.54
    domain_hint = "external_revenue" if is_revenue else "runtime_feedback"
    keywords = ["value_event", "telic", "feedback"]
    if is_revenue:
        keywords.extend(["revenue", "paid", value_kind])
    elif low_value:
        keywords.append("low_value")
    else:
        keywords.append("value")
    return ExecutiveSignal(
        source="telic:ValueEvent",
        title=title,
        category="value_event_feedback",
        description=(
            f"task_id={props.get('task_id') or ''}; "
            f"agent_id={props.get('agent_id') or ''}; "
            f"task_type={task_type}; "
            f"value_kind={value_kind}; usd={usd}"
        ),
        relevance_score=relevance,
        confidence=0.82 if is_revenue else 0.78,
        domain_hint=domain_hint,
        evidence_ref=f"ontology://ValueEvent/{obj_id}",
        keywords=tuple(keywords),
        suggested_action=(
            "Increase opportunity ranking for proven revenue patterns."
            if is_revenue
            else "Review low-value execution before selecting similar work."
            if low_value
            else "Prefer patterns that produced measurable value."
        ),
        raw=raw,
    )


def _contribution_signal(obj_id: str, props: dict[str, Any], raw: dict[str, Any]) -> ExecutiveSignal:
    attributed = _float(props.get("attributed_value"), default=0.5)
    agent_id = str(props.get("agent_id") or "unknown")
    revenue_ref = str(props.get("revenue_ref") or "")
    beneficiary_type = str(props.get("beneficiary_type") or "")
    is_revenue = bool(revenue_ref) or beneficiary_type in ("compute", "training", "operations")
    domain_hint = "external_revenue" if is_revenue else "runtime_feedback"
    keywords = ["contribution", "credit", "telic", "feedback"]
    if is_revenue:
        keywords.append("revenue")
    return ExecutiveSignal(
        source="telic:Contribution",
        title=f"Contribution feedback for {agent_id}",
        category="contribution_feedback",
        description=(
            f"task_type={props.get('task_type') or ''}; "
            f"credit_share={props.get('credit_share') or ''}; "
            f"attributed_value={attributed:.2f}"
        ),
        relevance_score=max(0.4, min(0.85, 1.0 - attributed)),
        confidence=0.72,
        domain_hint=domain_hint,
        evidence_ref=f"ontology://Contribution/{obj_id}",
        keywords=tuple(keywords),
        suggested_action="Use contribution feedback when assigning future work.",
        raw=raw,
    )


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
