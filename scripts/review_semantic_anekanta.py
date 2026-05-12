#!/usr/bin/env python3
"""Review an artifact with the existing Semantic Anekanta evaluator."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.semantic_anekanta import evaluate_semantic_anekanta  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Review an artifact with existing Semantic Anekanta v0.",
    )
    parser.add_argument("artifact", type=Path, help="Markdown/text artifact to review")
    parser.add_argument(
        "--description",
        default="",
        help="Optional short description passed to the evaluator",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional JSON output path",
    )
    parser.add_argument(
        "--fail-on-fail",
        action="store_true",
        help="Exit 1 when Semantic Anekanta returns FAIL",
    )
    return parser


def _result_payload(artifact: Path, description: str, content: str) -> dict:
    result = evaluate_semantic_anekanta(description, content)
    if hasattr(result, "model_dump_json"):
        payload = json.loads(result.model_dump_json())
    else:  # pragma: no cover - pydantic v1 fallback
        payload = json.loads(result.json())
    payload.update({
        "artifact_path": str(artifact),
        "artifact_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "reviewer": "semantic_anekanta_v0",
    })
    return payload


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    artifact = args.artifact.expanduser()
    content = artifact.read_text(encoding="utf-8")
    description = args.description or artifact.stem.replace("_", " ")
    payload = _result_payload(artifact, description, content)

    if args.output is not None:
        output = args.output.expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps(payload, indent=2, sort_keys=True))
    if args.fail_on_fail and payload.get("gate_result") == "FAIL":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
