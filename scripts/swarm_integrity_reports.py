#!/usr/bin/env python3
"""Run Swarm Integrity v0/v1 and write proof-packet reports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dharma_swarm.event_log import EventLog
from dharma_swarm.swarm_integrity_benchmark import (
    render_swarm_integrity_markdown,
    run_swarm_integrity_v0,
    run_swarm_integrity_v1,
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event-log-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("reports/recursive_shadow_foundry"))
    parser.add_argument("--session-id", default="governed-recursive-proof")
    parser.add_argument("--trace-id", default=None)
    args = parser.parse_args(argv)

    event_log = EventLog(args.event_log_dir)
    v0 = run_swarm_integrity_v0(
        event_log=event_log,
        session_id=args.session_id,
        trace_id=args.trace_id,
    )
    v1 = run_swarm_integrity_v1(
        event_log=event_log,
        session_id=args.session_id,
        trace_id=args.trace_id,
    )
    out = args.output_dir
    _write(
        out / "swarm_integrity_v0_report.json",
        json.dumps(v0.to_json(), indent=2, sort_keys=True) + "\n",
    )
    _write(out / "swarm_integrity_v0_report.md", render_swarm_integrity_markdown(v0))
    _write(
        out / "swarm_integrity_v1_report.json",
        json.dumps(v1.to_json(), indent=2, sort_keys=True) + "\n",
    )
    _write(out / "swarm_integrity_v1_report.md", render_swarm_integrity_markdown(v1))
    print(
        json.dumps(
            {
                "swarm_integrity_v0": v0.all_passed,
                "swarm_integrity_v1": v1.all_passed,
                "output_dir": str(out),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if v0.all_passed and v1.all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
