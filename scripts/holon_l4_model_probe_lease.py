#!/usr/bin/env python3
"""Issue a reviewed lease receipt for one L4 HOLON live model probe."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dharma_swarm.holon_bridge import AGENTS_ROOT  # noqa: E402
from dharma_swarm.holon_l4_model_probe_lease import (  # noqa: E402
    default_model_probe_lease_path,
    issue_model_probe_lease,
    write_model_probe_lease,
)
from dharma_swarm.holon_l4_smoke import utc_compact  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", nargs="?", default="codex_composer")
    parser.add_argument("--agents-root", type=Path, default=AGENTS_ROOT)
    parser.add_argument("--session-id", default="")
    parser.add_argument("--lease-id", default="")
    parser.add_argument("--duration-seconds", type=int, default=900)
    parser.add_argument("--allow-subprocess-provider", action="store_true")
    parser.add_argument(
        "--purpose",
        default="Operator-governed L4 HOLON live model responsiveness probe.",
    )
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--write", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    session_id = args.session_id or f"l4-model-probe-{utc_compact()}"
    lease_id = args.lease_id or f"lease:l4-model-probe:{session_id}"
    payload = issue_model_probe_lease(
        name=args.name,
        session_id=session_id,
        lease_id=lease_id,
        agents_root=args.agents_root,
        duration_seconds=args.duration_seconds,
        allow_subprocess_provider=args.allow_subprocess_provider,
        purpose=args.purpose,
    )
    output = args.output or default_model_probe_lease_path(
        args.name,
        lease_id=lease_id,
        agents_root=args.agents_root,
    )
    if args.write:
        output = write_model_probe_lease(payload, output)
        payload = {**payload, "path": str(output)}
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
