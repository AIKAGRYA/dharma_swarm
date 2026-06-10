#!/usr/bin/env python3
"""Move one hygiene pattern through the lifecycle."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from check_hygiene_integrity import PATTERN_DIR, REPO_ROOT, STAGES, load_json_yaml  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pattern_id")
    parser.add_argument("--stage", required=True, choices=sorted(STAGES - {"archived"}))
    parser.add_argument("--rule", help="enforcement rule path or id when promoting to enforced")
    parser.add_argument("--promoted-on", default=date.today().isoformat())
    parser.add_argument("--next-review")
    args = parser.parse_args(argv)

    path = REPO_ROOT / PATTERN_DIR / f"{args.pattern_id}.yaml"
    if not path.exists():
        raise SystemExit(f"pattern not found: {path.relative_to(REPO_ROOT)}")
    pattern = load_json_yaml(path)
    pattern["stage"] = args.stage
    pattern["last_verified"] = args.promoted_on
    if args.next_review:
        pattern["next_review"] = args.next_review
    if args.stage == "enforced":
        if not args.rule:
            raise SystemExit("--rule is required when --stage enforced")
        pattern.setdefault("enforcement", {})["rule"] = args.rule
        pattern["enforcement"]["promoted_on"] = args.promoted_on
    path.write_text(json.dumps(pattern, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(f"updated {path.relative_to(REPO_ROOT)}")
    print("next: python3 scripts/governance/hygiene/audit_agent_prompt.py --write")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
