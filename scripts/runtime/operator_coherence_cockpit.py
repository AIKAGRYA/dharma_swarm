#!/usr/bin/env python3
"""Generate the Operator Coherence Cockpit JSON + Markdown receipt.

Read-only probes:
  git/governance/live process dashboard/preservation/GitHub (when available)

Output is a projection, not a new source of truth.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dharma_swarm.operator_core.operator_coherence_cockpit import (
    DEFAULT_JSON_OUTPUT,
    DEFAULT_MARKDOWN_OUTPUT,
    DEFAULT_REPO_ROOT,
    build_operator_coherence_cockpit,
    render_markdown_report,
    write_operator_coherence_outputs,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the read-only Operator Coherence Cockpit projection.")
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    parser.add_argument("--stdout", action="store_true", help="print JSON to stdout instead of writing files")
    parser.add_argument("--markdown-stdout", action="store_true", help="print Markdown receipt to stdout instead of writing files")
    parser.add_argument("--no-github", action="store_true", help="skip gh auth/pr probes")
    parser.add_argument("--no-live-probes", action="store_true", help="skip tmux/launchctl/ps probes")
    args = parser.parse_args()

    payload = build_operator_coherence_cockpit(
        args.repo_root,
        include_github=not args.no_github,
        include_live_probes=not args.no_live_probes,
    )
    if args.stdout:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    if args.markdown_stdout:
        print(render_markdown_report(payload), end="")
        return 0
    json_path, markdown_path = write_operator_coherence_outputs(
        payload,
        json_output=args.output,
        markdown_output=args.markdown,
    )
    print(json_path)
    print(markdown_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
