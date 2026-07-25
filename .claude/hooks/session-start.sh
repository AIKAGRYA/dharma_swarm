#!/bin/bash
# SessionStart hook for dharma_swarm.
# Installs Python deps so tests (pytest) and the linter (ruff) work in
# Claude Code on the web sessions. Synchronous: the session waits until
# dependencies are installed, avoiding races where Claude runs tests/lint
# before they're ready.
set -euo pipefail

# Only run in the remote (Claude Code on the web) environment; local
# machines manage their own venvs.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-.}"

# Editable install with dev extras → runtime deps + pytest, pytest-asyncio,
# pytest-cov, pytest-timeout, ruff, hypothesis. Idempotent and cache-friendly.
python3 -m pip install --quiet -e ".[dev]"

echo "dharma_swarm session-start hook: dependencies installed."
