#!/usr/bin/env bash
# Run the governance hygiene scan. This is non-blocking and writes a dated
# baseline under docs/governance/hygiene/baselines/ by default.

set -euo pipefail
cd "$(dirname "$0")/../../.."

scripts/governance/run_python_with_repo_env.sh scripts/governance/hygiene/scan.py "$@"
