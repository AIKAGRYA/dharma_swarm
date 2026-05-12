#!/usr/bin/env python3
"""Audit a proof artifact with the existing JK credibility gates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.jk_credibility_gates import audit_proof_artifact, save_audit  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit a proof artifact with existing credibility gates.",
    )
    parser.add_argument("artifact", type=Path, help="Markdown/text artifact to audit")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Where to write audit JSON (default: <artifact parent>/audits)",
    )
    parser.add_argument(
        "--fail-on-not-ready",
        action="store_true",
        help="Exit 1 when the artifact is not submission-ready",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    artifact = args.artifact.expanduser()
    output_dir = (
        args.output_dir.expanduser()
        if args.output_dir is not None
        else artifact.parent / "audits"
    )

    audit = audit_proof_artifact(artifact)
    audit_path = save_audit(audit, output_dir)
    payload = audit.to_dict()
    payload["audit_path"] = str(audit_path)
    print(json.dumps(payload, indent=2, sort_keys=True))

    if args.fail_on_not_ready and not audit.submission_ready:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
