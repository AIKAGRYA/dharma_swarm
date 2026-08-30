#!/usr/bin/env bash
# Read-only status wrapper; never starts, stops, or mutates a lab.
set -euo pipefail

if (($# != 4)) || [[ "$1" != "--config" || "$3" != "--state-root" ]]; then
  printf 'usage: status_lab_supervisor.sh --config PATH --state-root PATH\n' >&2
  exit 2
fi
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
python="${LAB_SUPERVISOR_PYTHON:-$repo/.venv/bin/python}"
exec "$python" "$repo/scripts/runtime/lab_supervisor.py" status --config "$2" --state-root "$4"
