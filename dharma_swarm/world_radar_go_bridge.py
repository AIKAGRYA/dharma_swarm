"""Bridge Go world scouts and radar into the Python S4 loop."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dharma_swarm.daemon_config import dharma_state_dir
from dharma_swarm.world_signal_analysis import (
    build_world_signal_board,
    render_world_signal_brief,
    update_source_weights_from_opportunities,
)

WORLD_SCOUT_FETCH_ENV = "DHARMA_WORLD_SCOUT_FETCH"
WORLD_SCOUT_TIMEOUT_ENV = "DHARMA_WORLD_SCOUT_TIMEOUT_MS"
WORLD_SCOUT_MAX_BODY_ENV = "DHARMA_WORLD_SCOUT_MAX_BODY_BYTES"


@dataclass(frozen=True)
class WorldRadarGoResult:
    success: bool
    skipped: bool = False
    input_path: str = ""
    output_path: str = ""
    emitted_rows: int = 0
    scout_success: bool = True
    scout_skipped: bool = True
    scout_rows: int = 0
    board_path: str = ""
    brief_path: str = ""
    health_path: str = ""
    error: str = ""


def run_world_radar_go_once(
    *,
    state_dir: Path | None = None,
    input_path: Path | None = None,
    output_path: Path | None = None,
    observed_at: str = "",
    min_score: float = 0.45,
    timeout_s: float = 30.0,
    go_cmd: str = "go",
    module_dir: Path | None = None,
    scout_module_dir: Path | None = None,
    manual_input_path: Path | None = None,
    scout_output_path: Path | None = None,
    board_path: Path | None = None,
    brief_path: Path | None = None,
    health_path: Path | None = None,
    scout_fetch: bool | None = None,
) -> WorldRadarGoResult:
    """Run scout merge and Go radar once if any raw observations exist."""
    state = state_dir or dharma_state_dir()
    raw_inbox = input_path or state / "meta" / "world_radar_observations.jsonl"
    world_feed = output_path or state / "world_feeds" / "world_radar_go.jsonl"
    manual_inbox = manual_input_path or state / "meta" / "world_operator_drops.jsonl"
    scout_output = scout_output_path or state / "meta" / "world_scout_observations.jsonl"
    signal_board = board_path or state / "meta" / "world_signal_board.json"
    signal_brief = brief_path or state / "meta" / "world_signal_brief.md"
    scout_health = health_path or state / "meta" / "world_scout_health.json"
    source_weights = state / "meta" / "world_source_weights.json"
    root = Path(__file__).resolve().parent.parent

    scout = _run_world_scout_if_enabled(
        output_path=scout_output,
        health_path=scout_health,
        observed_at=observed_at,
        timeout_s=timeout_s,
        go_cmd=go_cmd,
        module_dir=scout_module_dir or root / "tools" / "world_scout_go",
        fetch=scout_fetch,
    )
    _merge_observation_inputs(raw_inbox, [manual_inbox, scout_output])

    if not raw_inbox.exists():
        return WorldRadarGoResult(
            success=True,
            skipped=True,
            input_path=str(raw_inbox),
            output_path=str(world_feed),
            scout_success=scout.success,
            scout_skipped=scout.skipped,
            scout_rows=scout.rows,
            board_path=str(signal_board),
            brief_path=str(signal_brief),
            health_path=str(scout_health),
            error=scout.error,
        )

    go_module = module_dir or root / "tools" / "world_signal_ingestor_go"
    cmd = [
        go_cmd,
        "run",
        ".",
        "--input",
        str(raw_inbox),
        "--output",
        str(world_feed),
        "--replace",
        "--min-score",
        str(min_score),
    ]
    if observed_at:
        cmd.extend(["--observed-at", observed_at])

    try:
        proc = subprocess.run(
            cmd,
            cwd=go_module,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except Exception as exc:
        return _result(False, raw_inbox, world_feed, scout, signal_board, signal_brief, scout_health, str(exc))

    if proc.returncode != 0:
        return _result(
            False,
            raw_inbox,
            world_feed,
            scout,
            signal_board,
            signal_brief,
            scout_health,
            (proc.stderr or proc.stdout).strip(),
        )

    emitted = _count_jsonl_rows(world_feed)
    _write_world_signal_outputs(
        world_feed,
        signal_board,
        signal_brief,
        scout_health=scout_health,
        source_weights=source_weights,
        opportunity_board=state / "meta" / "opportunity_board.json",
    )
    return WorldRadarGoResult(
        success=True,
        input_path=str(raw_inbox),
        output_path=str(world_feed),
        emitted_rows=emitted,
        scout_success=scout.success,
        scout_skipped=scout.skipped,
        scout_rows=scout.rows,
        board_path=str(signal_board),
        brief_path=str(signal_brief),
        health_path=str(scout_health),
        error=scout.error,
    )


@dataclass(frozen=True)
class _ScoutRun:
    success: bool
    skipped: bool = False
    rows: int = 0
    error: str = ""


def _run_world_scout_if_enabled(
    *,
    output_path: Path,
    health_path: Path,
    observed_at: str,
    timeout_s: float,
    go_cmd: str,
    module_dir: Path,
    fetch: bool | None,
) -> _ScoutRun:
    enabled = _env_enabled(WORLD_SCOUT_FETCH_ENV) if fetch is None else fetch
    if not enabled:
        return _ScoutRun(success=True, skipped=True)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        go_cmd,
        "run",
        ".",
        "--output",
        str(output_path),
        "--health-output",
        str(health_path),
        "--replace",
        "--fetch",
        "--timeout-ms",
        str(_env_int(WORLD_SCOUT_TIMEOUT_ENV, 750)),
        "--max-body-bytes",
        str(_env_int(WORLD_SCOUT_MAX_BODY_ENV, 1 << 20)),
    ]
    if observed_at:
        cmd.extend(["--observed-at", observed_at])

    try:
        proc = subprocess.run(cmd, cwd=module_dir, capture_output=True, text=True, timeout=timeout_s, check=False)
    except Exception as exc:
        return _ScoutRun(success=False, error=str(exc))
    if proc.returncode != 0:
        return _ScoutRun(success=False, error=(proc.stderr or proc.stdout).strip())
    return _ScoutRun(success=True, rows=_count_jsonl_rows(output_path))


def _merge_observation_inputs(target: Path, extra_paths: list[Path]) -> int:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in [target, *extra_paths]:
        if not path.exists():
            continue
        for row in _read_jsonl(path):
            key = _observation_key(row)
            if key in seen:
                continue
            seen.add(key)
            rows.append(row)
    if not rows:
        return 0

    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as fh:
        for row in rows[-1000:]:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    return len(rows)


def _write_world_signal_outputs(
    feed_path: Path,
    board_path: Path,
    brief_path: Path,
    *,
    scout_health: Path,
    source_weights: Path,
    opportunity_board: Path,
) -> None:
    signals = _read_jsonl(feed_path)
    if not signals:
        return
    update_source_weights_from_opportunities(
        opportunity_board=opportunity_board,
        weights_path=source_weights,
    )
    payload = build_world_signal_board(
        signals,
        opportunity_board=opportunity_board,
        scout_health=scout_health,
        source_weights=source_weights,
        source_feed=feed_path,
    )
    board_path.parent.mkdir(parents=True, exist_ok=True)
    board_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    brief_path.parent.mkdir(parents=True, exist_ok=True)
    brief_path.write_text(render_world_signal_brief(payload), encoding="utf-8")


def _result(
    success: bool,
    raw_inbox: Path,
    world_feed: Path,
    scout: _ScoutRun,
    board_path: Path,
    brief_path: Path,
    health_path: Path,
    error: str,
) -> WorldRadarGoResult:
    return WorldRadarGoResult(
        success=success,
        input_path=str(raw_inbox),
        output_path=str(world_feed),
        scout_success=scout.success,
        scout_skipped=scout.skipped,
        scout_rows=scout.rows,
        board_path=str(board_path),
        brief_path=str(brief_path),
        health_path=str(health_path),
        error=error,
    )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return rows
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _opportunity_lookup(path: Path) -> dict[str, str]:
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(rows, list):
        return {}
    out: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or "").strip()
        vision = row.get("strategic_vision") if isinstance(row.get("strategic_vision"), dict) else {}
        source_url = str(vision.get("source_url") or "").strip()
        opp_id = str(row.get("opportunity_id") or "").strip()
        if title and opp_id:
            out[_signal_lookup_key(title, source_url)] = opp_id
            out[_signal_lookup_key(title, "")] = opp_id
    return out


def _count_jsonl_rows(path: Path) -> int:
    try:
        return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    except OSError:
        return 0


def _observation_key(row: dict[str, Any]) -> str:
    for key in ("id", "signal_id"):
        value = str(row.get(key) or "").strip()
        if value:
            return f"{key}:{value}"
    return _signal_lookup_key(str(row.get("title") or ""), str(row.get("source_url") or row.get("url") or ""))


def _signal_lookup_key(title: str, source_url: str) -> str:
    return "\0".join((title.strip().lower(), source_url.strip().lower()))


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _why_it_matters(row: dict[str, Any]) -> str:
    category = str(row.get("category") or "opportunity").replace("_", " ")
    title = str(row.get("title") or "external signal").strip()
    return f"{category} pressure: verify, map adjacency, and decide the next move for {title}."


def _env_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


__all__ = ["WorldRadarGoResult", "run_world_radar_go_once"]
