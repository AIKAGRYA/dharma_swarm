#!/usr/bin/env bash
set -euo pipefail

prompt_file="${1:?prompt file required}"

if ! command -v claude >/dev/null 2>&1; then
  echo "claude CLI is not available on PATH" >&2
  exit 127
fi

claude -p "$(cat "$prompt_file")"
