#!/usr/bin/env bash
# Run the governance hygiene scan. This is non-blocking and writes a dated
# baseline under docs/governance/hygiene/baselines/ by default.

set -euo pipefail
cd "$(dirname "$0")/../../.."

.venv/bin/python scripts/governance/hygiene/scan.py "$@"
