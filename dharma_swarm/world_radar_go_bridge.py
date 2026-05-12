"""Bridge the Go world-radar prototype into the Python S4 loop.

The Go layer owns fast deterministic sensing/triage. Python owns ingestion,
strategic digestion, scoring, and dispatch. This bridge keeps that membrane
explicit: it runs the Go CLI against a raw observation inbox and leaves the
result as a world-feed JSONL file for ``ZeitgeistScanner`` to consume.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from dharma_swarm.daemon_config import dharma_state_dir


@dataclass(frozen=True)
class WorldRadarGoResult:
    success: bool
    skipped: bool = False
    input_path: str = ""
    output_path: str = ""
    emitted_rows: int = 0
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
) -> WorldRadarGoResult:
    """Run the Go world radar once if the raw observation inbox exists."""
    state = state_dir or dharma_state_dir()
    raw_inbox = input_path or state / "meta" / "world_radar_observations.jsonl"
    world_feed = output_path or state / "world_feeds" / "world_radar_go.jsonl"
    if not raw_inbox.exists():
        return WorldRadarGoResult(
            success=True,
            skipped=True,
            input_path=str(raw_inbox),
            output_path=str(world_feed),
        )

    root = Path(__file__).resolve().parent.parent
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
        return WorldRadarGoResult(
            success=False,
            input_path=str(raw_inbox),
            output_path=str(world_feed),
            error=str(exc),
        )

    if proc.returncode != 0:
        return WorldRadarGoResult(
            success=False,
            input_path=str(raw_inbox),
            output_path=str(world_feed),
            error=(proc.stderr or proc.stdout).strip(),
        )

    emitted = _count_jsonl_rows(world_feed)
    return WorldRadarGoResult(
        success=True,
        input_path=str(raw_inbox),
        output_path=str(world_feed),
        emitted_rows=emitted,
    )


def _count_jsonl_rows(path: Path) -> int:
    try:
        return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    except OSError:
        return 0


__all__ = ["WorldRadarGoResult", "run_world_radar_go_once"]
