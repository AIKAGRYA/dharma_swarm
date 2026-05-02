from __future__ import annotations

import argparse
from pathlib import Path

from dharma_swarm.telic_seam import TelicSeam


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Record an inquiry Claim")
    parser.add_argument("--statement", required=True)
    parser.add_argument("--proposer-ref", default="manual_operator")
    parser.add_argument("--confidence", type=float, default=0.5)
    parser.add_argument("--parent-question-id", default="")
    parser.add_argument("--ontology-path", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    ontology_path = Path(args.ontology_path).expanduser() if args.ontology_path else None
    seam = TelicSeam(path=ontology_path)
    obj_id = seam.record_claim(
        args.statement,
        args.proposer_ref,
        confidence=args.confidence,
        parent_question_id=args.parent_question_id or None,
    )
    if obj_id is None:
        print("Claim: failed")
        return 1
    print(f"Claim: {obj_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
