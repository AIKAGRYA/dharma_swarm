"""Bridge Python runtime loops to the Go world scout and signal ingestor."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
from typing import Any

from dharma_swarm.daemon_config import dharma_state_dir
from dharma_swarm.world_signal_analysis import (
    build_world_signal_board,
    incubating_movements,
    promotion_ready_signals,
    render_world_signal_brief,
)
from dharma_swarm.world_signal_incubator import write_incubations


@dataclass(frozen=True)
class WorldRadarGoResult:
    ok: bool
    raw_observations: int
    emitted_signals: int
    promotion_ready: int
    incubations_written: int
    board_path: str
    brief_path: str
    health_path: str
    errors: tuple[str, ...] = ()


def run_world_radar_go_once(
    *,
    state_dir: Path | str | None = None,
    scout_fetch: bool = False,
    min_score: float = 0.45,
    timeout_s: int = 60,
) -> WorldRadarGoResult:
    """Run one world-radar pass and publish board, brief, and promotions."""
    state = Path(state_dir).expanduser() if state_dir is not None else dharma_state_dir()
    meta = state / "meta"
    radar = meta / "world_radar"
    radar.mkdir(parents=True, exist_ok=True)
    raw_path = radar / "raw_observations.jsonl"
    signal_path = meta / "world_signal_feed.jsonl"
    inbox_path = meta / "world_zeitgeist_inbox.jsonl"
    board_path = meta / "world_signal_board.json"
    brief_path = meta / "world_signal_brief.md"
    health_path = radar / "world_scout_health.json"
    errors: list[str] = []

    raw_rows = _collect_raw_rows(meta)
    if scout_fetch:
        scout_rows, scout_error = _run_go_scout(
            state=state,
            output_path=radar / "world_scout_observations.jsonl",
            health_path=health_path,
            timeout_s=timeout_s,
        )
        raw_rows.extend(scout_rows)
        if scout_error:
            errors.append(scout_error)
    _write_jsonl(raw_path, raw_rows)

    ingested_rows, ingest_error = _run_go_ingestor(
        input_path=raw_path,
        output_path=signal_path,
        min_score=min_score,
        timeout_s=timeout_s,
    )
    if ingest_error:
        errors.append(ingest_error)
        ingested_rows = _read_jsonl(signal_path)

    board = build_world_signal_board(ingested_rows)
    incubation_paths = write_incubations(
        incubating_movements(board),
        output_dir=radar / "incubations",
    )
    board_path.write_text(json.dumps(board, indent=2, sort_keys=True), encoding="utf-8")
    brief_path.write_text(render_world_signal_brief(board), encoding="utf-8")
    promotions = promotion_ready_signals(board)
    _write_jsonl(inbox_path, promotions)

    return WorldRadarGoResult(
        ok=not errors,
        raw_observations=len(raw_rows),
        emitted_signals=len(ingested_rows),
        promotion_ready=len(promotions),
        incubations_written=len(incubation_paths),
        board_path=str(board_path),
        brief_path=str(brief_path),
        health_path=str(health_path),
        errors=tuple(errors),
    )


def _collect_raw_rows(meta: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in (
        meta / "world_operator_drops.jsonl",
        meta / "world_scout_observations.jsonl",
        meta / "world_radar_observations.jsonl",
    ):
        rows.extend(_read_jsonl(path))
    feed_dir = meta / "world_feeds"
    if feed_dir.exists():
        for path in sorted(feed_dir.glob("*.jsonl")):
            rows.extend(_read_jsonl(path))
    return rows


def _run_go_scout(
    *,
    state: Path,
    output_path: Path,
    health_path: Path,
    timeout_s: int,
) -> tuple[list[dict[str, Any]], str | None]:
    module_dir = _repo_root() / "tools" / "world_scout_go"
    if not module_dir.exists():
        return [], f"missing Go scout module: {module_dir}"
    cmd = [
        "go",
        "run",
        ".",
        "--state-dir",
        str(state),
        "--output",
        str(output_path),
        "--health",
        str(health_path),
        "--fetch",
    ]
    proc = subprocess.run(cmd, cwd=module_dir, capture_output=True, text=True, timeout=timeout_s)
    if proc.returncode != 0:
        return [], (proc.stderr or proc.stdout or "world_scout_go failed").strip()[:1000]
    return _read_jsonl(output_path), None


def _run_go_ingestor(
    *,
    input_path: Path,
    output_path: Path,
    min_score: float,
    timeout_s: int,
) -> tuple[list[dict[str, Any]], str | None]:
    module_dir = _repo_root() / "tools" / "world_signal_ingestor_go"
    if not module_dir.exists():
        return [], f"missing Go ingestor module: {module_dir}"
    cmd = [
        "go",
        "run",
        ".",
        "--input",
        str(input_path),
        "--output",
        str(output_path),
        "--min-score",
        str(min_score),
    ]
    proc = subprocess.run(cmd, cwd=module_dir, capture_output=True, text=True, timeout=timeout_s)
    if proc.returncode != 0:
        return [], (proc.stderr or proc.stdout or "world_signal_ingestor_go failed").strip()[:1000]
    return _read_jsonl(output_path), None


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    lines: list[str] = []
    for row in rows:
        key = str(row.get("id") or row.get("url") or row.get("title") or json.dumps(row, sort_keys=True))
        if key in seen:
            continue
        seen.add(key)
        lines.append(json.dumps(row, sort_keys=True))
    path.write_text(("\n".join(lines) + "\n") if lines else "", encoding="utf-8")


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent
