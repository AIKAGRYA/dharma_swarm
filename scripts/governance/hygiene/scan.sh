#!/usr/bin/env bash
# Run the governance hygiene scan. This is non-blocking and writes a dated
# baseline under docs/governance/hygiene/baselines/ by default.

set -euo pipefail
cd "$(dirname "$0")/../../.."

python3 scripts/governance/hygiene/scan.py "$@"
