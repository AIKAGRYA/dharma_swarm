"""CLI for the Shakti executive opportunity-board bridge."""

from __future__ import annotations

import argparse
import json

from dharma_swarm.shakti_executive import ShaktiExecutive


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Populate or preview opportunity_board.json from live signals.",
    )
    parser.add_argument("--state-dir", default=None)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--top-k", type=int, default=12)
    parser.add_argument("--min-score", type=float, default=45.0)
    parser.add_argument("--preview", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    executive = ShaktiExecutive(state_dir=args.state_dir)
    if args.preview:
        print(json.dumps(executive.preview(top_k=args.top_k, min_score=args.min_score), indent=2))
        return 0
    result = executive.run(
        write=args.write,
        top_k=args.top_k,
        min_score=args.min_score,
    )
    print(json.dumps(result.__dict__, indent=2, sort_keys=True))
    return 0 if not result.errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
