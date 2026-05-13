"""Bridge the Go world scout/radar into Python runtime state."""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dharma_swarm.daemon_config import dharma_state_dir
from dharma_swarm.world_signal_analysis import (
    build_world_signal_board,
    render_world_signal_brief,
    update_source_weights_from_opportunities,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WorldRadarGoResult:
    """Summary of one world radar bridge run."""

    ok: bool
    raw_observations: int
    emitted_signals: int
    board_path: Path
    brief_path: Path
    health_path: Path
    errors: tuple[str, ...] = ()


def run_world_radar_go_once(
    *,
    state_dir: Path | None = None,
    repo_root: Path | None = None,
    scout_fetch: bool = False,
    min_score: float = 0.45,
    timeout_s: int = 45,
) -> WorldRadarGoResult:
    """Run a gated world scout + ingestor cycle once."""
    state = state_dir or dharma_state_dir()
    root = repo_root or Path(__file__).resolve().parent.parent
    meta = state / "meta"
    world_feeds = state / "world_feeds"
    meta.mkdir(parents=True, exist_ok=True)
    world_feeds.mkdir(parents=True, exist_ok=True)

    operator_drops = meta / "world_operator_drops.jsonl"
    scout_observations = meta / "world_scout_observations.jsonl"
    radar_observations = meta / "world_radar_observations.jsonl"
    ingestor_input = meta / "world_signal_ingestor_input.jsonl"
    feed_path = world_feeds / "world_signal_feed.jsonl"
    inbox_path = meta / "world_zeitgeist_inbox.jsonl"
    board_path = meta / "world_signal_board.json"
    brief_path = meta / "world_signal_brief.md"
    health_path = meta / "world_scout_health.json"
    source_weights_path = meta / "world_source_weights.json"
    opportunity_board_path = meta / "opportunity_board.json"

    errors: list[str] = []
    if scout_fetch:
        scout_result = _run_world_scout(
            root=root,
            output_path=scout_observations,
            health_path=health_path,
            timeout_s=timeout_s,
        )
        if scout_result:
            errors.append(scout_result)

    raw_rows = []
    for path in (operator_drops, scout_observations, radar_observations):
        raw_rows.extend(_read_jsonl(path))
    _write_jsonl(ingestor_input, raw_rows)

    if raw_rows:
        err = _run_world_signal_ingestor(
            root=root,
            input_path=ingestor_input,
            output_path=feed_path,
            min_score=min_score,
            timeout_s=timeout_s,
        )
        if err:
            errors.append(err)
    elif feed_path.exists():
        feed_path.unlink(missing_ok=True)

    signals = _read_jsonl(feed_path)
    _write_jsonl(inbox_path, signals)
    opportunity_board = _read_json(opportunity_board_path, default=[])
    scout_health = _read_json(health_path, default={})
    weights = update_source_weights_from_opportunities(
        opportunity_board if isinstance(opportunity_board, list) else [],
        source_weights_path,
    )
    board = build_world_signal_board(
        signals,
        opportunity_board=opportunity_board if isinstance(opportunity_board, list) else [],
        scout_health=scout_health if isinstance(scout_health, dict) else {},
        source_weights=weights,
        source_feed=str(feed_path),
    )
    board_path.write_text(json.dumps(board, indent=2, sort_keys=True), encoding="utf-8")
    brief_path.write_text(render_world_signal_brief(board), encoding="utf-8")

    return WorldRadarGoResult(
        ok=not errors,
        raw_observations=len(raw_rows),
        emitted_signals=len(signals),
        board_path=board_path,
        brief_path=brief_path,
        health_path=health_path,
        errors=tuple(errors),
    )


def _run_world_scout(
    *,
    root: Path,
    output_path: Path,
    health_path: Path,
    timeout_s: int,
) -> str:
    tool = root / "tools" / "world_scout_go"
    return _run_go_tool(
        tool,
        [
            "--fetch",
            "--output",
            str(output_path),
            "--health-output",
            str(health_path),
            "--timeout-ms",
            str(max(500, timeout_s * 1000)),
        ],
        timeout_s=timeout_s,
    )


def _run_world_signal_ingestor(
    *,
    root: Path,
    input_path: Path,
    output_path: Path,
    min_score: float,
    timeout_s: int,
) -> str:
    tool = root / "tools" / "world_signal_ingestor_go"
    return _run_go_tool(
        tool,
        [
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--min-score",
            str(min_score),
        ],
        timeout_s=timeout_s,
    )


def _run_go_tool(tool_dir: Path, args: list[str], *, timeout_s: int) -> str:
    if not tool_dir.exists():
        return f"missing Go tool: {tool_dir}"
    try:
        proc = subprocess.run(
            ["go", "run", ".", *args],
            cwd=str(tool_dir),
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except Exception as exc:
        return str(exc)
    if proc.returncode != 0:
        return (proc.stderr or proc.stdout or f"go tool failed in {tool_dir}").strip()
    return ""


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            logger.debug("Skipping malformed JSONL row in %s", path)
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
    path.write_text(text, encoding="utf-8")


def _read_json(path: Path, *, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default
