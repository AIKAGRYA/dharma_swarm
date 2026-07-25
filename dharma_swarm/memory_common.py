"""Common memory surface for agents, CLI, and terminal commands."""

from __future__ import annotations

import json
import shlex
import sqlite3
from datetime import datetime, timezone
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


DEFAULT_STATE_DIR = Path.home() / ".dharma"
MEMORY_COMMON_CRON_NAME = "memory-common-metabolism"


@dataclass(frozen=True)
class MemoryCommonSummary:
    state_dir: str
    vector_db_exists: bool
    sidecar_rows: int
    sidecar_counts: dict[str, int]
    wiki_gate_score: float | None
    system_gate_score: float | None

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def memory_common_summary(*, state_dir: Path | None = None) -> MemoryCommonSummary:
    resolved_state_dir = Path(state_dir or DEFAULT_STATE_DIR).expanduser()
    db_path = resolved_state_dir / "vectors.db"
    counts: dict[str, int] = {}
    if db_path.exists():
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=2.0)
            try:
                rows = conn.execute(
                    """
                    SELECT layer, COUNT(*) AS row_count
                    FROM memory_retrieval_docs
                    WHERE valid_until IS NULL
                    GROUP BY layer
                    """
                ).fetchall()
            finally:
                conn.close()
            counts = {str(layer): int(row_count or 0) for layer, row_count in rows}
        except Exception:
            counts = {}
    return MemoryCommonSummary(
        state_dir=str(resolved_state_dir),
        vector_db_exists=db_path.exists(),
        sidecar_rows=sum(counts.values()),
        sidecar_counts=counts,
        wiki_gate_score=_latest_gate_score("WIKI_VECTOR_LIVE_GATE_*FINAL.json"),
        system_gate_score=_latest_gate_score("MEMORY_RETRIEVAL_SYSTEM_GATE_*FINAL.json"),
    )


def render_memory_common_status(*, state_dir: Path | None = None) -> str:
    summary = memory_common_summary(state_dir=state_dir)
    counts = summary.sidecar_counts
    lines = [
        "# Memory Common",
        "",
        f"State: `{summary.state_dir}`",
        f"Vector DB: `{'present' if summary.vector_db_exists else 'missing'}`",
        (
            "Indexed common rows: "
            f"`{summary.sidecar_rows}` "
            f"(source_file={counts.get('source_file', 0)}, "
            f"memory_context={counts.get('memory_context', 0)}, "
            f"memory_graph={counts.get('memory_graph', 0)})"
        ),
    ]
    if summary.wiki_gate_score is not None:
        lines.append(f"Wiki seam gate: `{summary.wiki_gate_score}/100`")
    if summary.system_gate_score is not None:
        lines.append(f"System retrieval gate: `{summary.system_gate_score}/100`")
    lines.extend(
        [
            "",
            "Use:",
            "- `/memory query <topic>` for direct recall",
            "- `/memory common <task>` for an agent handoff pack",
            "- `/memory gate` before trusting a changed memory surface",
        ]
    )
    return "\n".join(lines)


def render_memory_query(
    query: str,
    *,
    state_dir: Path | None = None,
    top_k: int = 5,
    include_content: bool = False,
) -> str:
    text = query.strip()
    if not text:
        return "Usage: /memory query <topic>"
    from dharma_swarm.memory_retrieval import GovernedRetrievalEngine, RetrievalQuery

    engine = GovernedRetrievalEngine(state_dir=Path(state_dir or DEFAULT_STATE_DIR).expanduser())
    result = engine.retrieve(
        RetrievalQuery(
            text=text,
            top_k=max(1, top_k),
            include_content=include_content,
        )
    )
    lines = [
        "# Memory Query",
        "",
        f"Query: `{text}`",
        f"Results: `{len(result.candidates)}`",
        f"Latency: `{result.timings_ms.get('total', 0)} ms`",
    ]
    for candidate in result.candidates:
        lines.append(
            (
                f"- `{candidate.rank}` score={candidate.score:.3f} "
                f"layer={candidate.layer} source={candidate.source}"
            )
        )
        if include_content and candidate.content:
            snippet = " ".join(candidate.content.split())[:360]
            lines.append(f"  {snippet}")
    return "\n".join(lines)


def render_agent_memory_pack(
    task: str,
    *,
    state_dir: Path | None = None,
    top_k: int = 5,
) -> str:
    text = task.strip()
    if not text:
        return "Usage: /memory common <agent task>"
    from dharma_swarm.memory_retrieval import GovernedRetrievalEngine, RetrievalQuery

    engine = GovernedRetrievalEngine(state_dir=Path(state_dir or DEFAULT_STATE_DIR).expanduser())
    result = engine.retrieve(
        RetrievalQuery(
            text=text,
            top_k=max(1, top_k),
            include_content=True,
        )
    )
    lines = [
        "# Memory Common Pack",
        "",
        f"Task: `{text}`",
        "",
        "Agent contract:",
        "- Treat these as retrieved context, not proof by themselves.",
        "- Cite source ids you actually use.",
        "- If results are empty or weak, say so and proceed from live evidence.",
        "- After the run, write a receipt with new durable observations and failed queries.",
        "",
        "Retrieved context:",
    ]
    if not result.candidates:
        lines.append("- No governed memory hits.")
    for candidate in result.candidates:
        snippet = " ".join(candidate.content.split())[:420]
        lines.extend(
            [
                (
                    f"- rank={candidate.rank} score={candidate.score:.3f} "
                    f"layer={candidate.layer} source={candidate.source}"
                ),
                f"  {snippet}",
            ]
        )
    return "\n".join(lines)


def render_memory_ingest(*, state_dir: Path | None = None) -> str:
    from dharma_swarm.wiki_vector_ingest import ingest_wiki_concepts

    resolved_state_dir = Path(state_dir or DEFAULT_STATE_DIR).expanduser()
    receipt = ingest_wiki_concepts(state_dir=resolved_state_dir)
    payload = receipt.to_json()
    return "\n".join(
        [
            "# Memory Ingest",
            "",
            f"Discovered wiki files: `{payload.get('discovered_files')}`",
            f"Backfill inserted rows: `{payload.get('backfill', {}).get('inserted_rows')}`",
            f"Synced index rows: `{payload.get('sync_index', {}).get('indexed_rows')}`",
            f"Reembedded rows: `{payload.get('reembed', {}).get('upserted_rows')}`",
        ]
    )


def render_memory_gate(
    *,
    state_dir: Path | None = None,
    top_k: int = 10,
) -> str:
    from scripts.memory_retrieval_system_gate import run_system_gate

    resolved_state_dir = Path(state_dir or DEFAULT_STATE_DIR).expanduser()
    summary = memory_common_summary(state_dir=resolved_state_dir)
    counts = summary.sidecar_counts
    payload = run_system_gate(
        state_dir=resolved_state_dir,
        top_k=max(1, top_k),
        negative_count=3,
        timeout_s=10,
        source_file_target=max(1, counts.get("source_file", 1)),
        memory_context_target=max(1, counts.get("memory_context", 1)),
        memory_graph_target=max(1, counts.get("memory_graph", 1)),
        run_live=True,
    )
    lines = [
        "# Memory Gate",
        "",
        f"Score: `{payload['score']}/{payload['max_score']}`",
        f"Passed: `{payload['passed']}`",
    ]
    for check in payload.get("checks", ()):
        lines.append(
            f"- {'PASS' if check.get('passed') else 'FAIL'} "
            f"{check.get('name')}: {check.get('summary')}"
        )
    return "\n".join(lines)


def _positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def run_memory_metabolism(
    *,
    state_dir: Path | None = None,
    top_k: int = 10,
    receipt_dir: Path | None = None,
) -> dict[str, Any]:
    from dharma_swarm.wiki_vector_ingest import ingest_wiki_concepts
    from scripts.memory_retrieval_system_gate import run_system_gate
    from scripts.wiki_vector_live_gate import run_gate as run_wiki_gate

    resolved_state_dir = Path(state_dir or DEFAULT_STATE_DIR).expanduser()
    wiki_dir = resolved_state_dir / "knowledge" / "wiki" / "concepts"
    started = datetime.now(timezone.utc)
    ingest = ingest_wiki_concepts(
        state_dir=resolved_state_dir,
        wiki_concepts_dir=wiki_dir,
    )
    wiki_gate = run_wiki_gate(
        state_dir=resolved_state_dir,
        wiki_concepts_dir=wiki_dir,
        top_k=5,
        min_concepts=1,
        max_p95_ms=1200.0,
    )
    summary = memory_common_summary(state_dir=resolved_state_dir)
    counts = summary.sidecar_counts
    system_gate = run_system_gate(
        state_dir=resolved_state_dir,
        top_k=max(1, top_k),
        negative_count=3,
        timeout_s=10,
        source_file_target=max(1, counts.get("source_file", 1)),
        memory_context_target=max(1, counts.get("memory_context", 1)),
        memory_graph_target=max(1, counts.get("memory_graph", 1)),
        run_live=True,
    )
    receipt = {
        "schema_version": 1,
        "started_at": started.isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "state_dir": str(resolved_state_dir),
        "ingest": ingest.to_json(),
        "wiki_gate": wiki_gate.to_json(),
        "system_gate": system_gate,
        "passed": bool(wiki_gate.passed and system_gate.get("passed")),
    }
    out_dir = Path(receipt_dir or Path(__file__).resolve().parents[1] / "reports" / "memory_kernel")
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = started.strftime("%Y%m%dT%H%M%SZ")
    receipt_path = out_dir / f"MEMORY_COMMON_METABOLISM_{stamp}.json"
    receipt["receipt_path"] = str(receipt_path)
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def format_memory_metabolism_receipt(receipt: dict[str, Any]) -> str:
    ingest = receipt.get("ingest", {})
    wiki_gate = receipt.get("wiki_gate", {})
    system_gate = receipt.get("system_gate", {})
    return "\n".join(
        [
            "# Memory Metabolism",
            "",
            f"Passed: `{receipt.get('passed')}`",
            f"Receipt: `{receipt.get('receipt_path')}`",
            f"Wiki files discovered: `{ingest.get('discovered_files')}`",
            f"Wiki gate: `{wiki_gate.get('score')}/100`",
            f"System gate: `{system_gate.get('score')}/{system_gate.get('max_score')}`",
        ]
    )


def render_memory_metabolism(
    *,
    state_dir: Path | None = None,
    top_k: int = 10,
) -> str:
    receipt = run_memory_metabolism(state_dir=state_dir, top_k=top_k)
    return format_memory_metabolism_receipt(receipt)


def memory_common_cron_run_fn(job: dict[str, Any]) -> tuple[bool, str, str | None]:
    """Cron handler: ingest promoted memory, gate retrieval, and write receipt."""

    try:
        raw_state_dir = str(job.get("state_dir") or "").strip()
        state_dir = Path(raw_state_dir).expanduser() if raw_state_dir else None
        top_k = _positive_int(job.get("top_k"), 10)
        receipt = run_memory_metabolism(state_dir=state_dir, top_k=top_k)
        output = format_memory_metabolism_receipt(receipt)
        if bool(receipt.get("passed")):
            return True, output, None
        return False, output, "Memory Common metabolism gate failed"
    except Exception as exc:
        error = f"Memory Common metabolism failed: {exc}"
        return False, error, error


def create_memory_common_cron_job(
    *,
    schedule: str = "every 24h",
    top_k: int = 10,
) -> dict[str, Any]:
    """Create the recurring Memory Common metabolism cron job if missing."""

    from dharma_swarm.cron_scheduler import create_job, list_jobs

    for job in list_jobs(include_disabled=True):
        if job.get("name") == MEMORY_COMMON_CRON_NAME:
            return job

    return create_job(
        prompt="Memory Common metabolism: ingest promoted memory, gate retrieval, write receipt.",
        schedule=schedule,
        name=MEMORY_COMMON_CRON_NAME,
        handler="memory_common_metabolism",
        deliver="local",
        urgent=False,
        top_k=max(1, int(top_k)),
    )


def render_memory_schedule(
    *,
    schedule: str = "every 24h",
    top_k: int = 10,
) -> str:
    job = create_memory_common_cron_job(schedule=schedule, top_k=top_k)
    return "\n".join(
        [
            "# Memory Common Schedule",
            "",
            f"Job: `{job.get('id')}`",
            f"Name: `{job.get('name')}`",
            f"Schedule: `{job.get('schedule_display')}`",
            f"Handler: `{job.get('handler')}`",
            f"Next run: `{job.get('next_run_at')}`",
            "",
            "Requires the existing cron daemon: `dgc cron daemon` or the launchd cron service.",
        ]
    )


def render_memory_common_command(
    arg: str = "",
    *,
    state_dir: Path | None = None,
    top_k: int = 5,
) -> str:
    try:
        parts = shlex.split(arg)
    except ValueError as exc:
        return f"Memory command parse error: {exc}"
    mode = parts[0].lower() if parts else "status"
    rest = " ".join(parts[1:]).strip()
    if mode in {"status", "common-status", "surface"}:
        return render_memory_common_status(state_dir=state_dir)
    if mode in {"query", "q", "search"}:
        return render_memory_query(rest, state_dir=state_dir, top_k=top_k)
    if mode in {"common", "brief", "pack", "agent"}:
        return render_agent_memory_pack(rest, state_dir=state_dir, top_k=top_k)
    if mode == "ingest":
        return render_memory_ingest(state_dir=state_dir)
    if mode == "gate":
        return render_memory_gate(state_dir=state_dir, top_k=max(1, top_k))
    if mode in {"metabolize", "metabolism", "cycle"}:
        return render_memory_metabolism(state_dir=state_dir, top_k=max(1, top_k))
    if mode == "schedule":
        return render_memory_schedule(schedule=rest or "every 24h", top_k=max(10, top_k))
    if not parts:
        return render_memory_common_status(state_dir=state_dir)
    return "\n".join(
        [
            f"Unknown memory mode: `{mode}`",
            "Use `/memory status`, `/memory query <topic>`, `/memory common <task>`, `/memory ingest`, `/memory gate`, `/memory metabolize`, or `/memory schedule`.",
        ]
    )


def _latest_gate_score(pattern: str) -> float | None:
    root = Path(__file__).resolve().parents[1]
    report_dir = root / "reports" / "memory_kernel"
    try:
        paths = sorted(report_dir.glob(pattern), key=lambda path: path.stat().st_mtime, reverse=True)
    except OSError:
        return None
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        score = payload.get("score")
        if isinstance(score, (int, float)):
            return float(score)
    return None
