#!/usr/bin/env python3
"""Verify DharmaVerifier-Ranker v0 starter package artifacts and hashes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.verifier_ranker_v0.package import build_manifest, write_manifest  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-dir", default="reports/agentops/verifier_ranker_v0")
    parser.add_argument("--write-manifest", action="store_true")
    args = parser.parse_args()

    package_dir = REPO_ROOT / args.package_dir
    if args.write_manifest:
        manifest_path = write_manifest(package_dir)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        print(manifest_path)
    else:
        manifest = build_manifest(package_dir)
        print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0 if manifest.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
