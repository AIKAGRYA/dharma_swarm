from __future__ import annotations

import argparse
from pathlib import Path

from dharma_swarm.telic_seam import TelicSeam


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Record an inquiry Signal")
    parser.add_argument("--source", required=True)
    parser.add_argument("--payload", required=True)
    parser.add_argument("--observer-ref", default="manual_operator")
    parser.add_argument("--source-kind", default="manual")
    parser.add_argument("--sensitivity", default="internal")
    parser.add_argument("--ontology-path", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    ontology_path = Path(args.ontology_path).expanduser() if args.ontology_path else None
    seam = TelicSeam(path=ontology_path)
    obj_id = seam.record_signal(
        args.source,
        args.payload,
        args.observer_ref,
        source_kind=args.source_kind,
        sensitivity=args.sensitivity,
    )
    if obj_id is None:
        print("Signal: failed")
        return 1
    print(f"Signal: {obj_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
