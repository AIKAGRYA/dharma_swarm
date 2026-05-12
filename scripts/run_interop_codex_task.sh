#!/usr/bin/env bash
set -euo pipefail

prompt_file="${1:?prompt file required}"

if ! command -v codex >/dev/null 2>&1; then
  echo "codex CLI is not available on PATH" >&2
  exit 127
fi

codex exec "$(cat "$prompt_file")"
