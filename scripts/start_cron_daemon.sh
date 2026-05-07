#!/bin/bash
# Wrapper script for com.dharma.cron-daemon launchd plist.
#
# Sources ~/.dharma/.env (if present) so the daemon and its subprocesses
# inherit ANTHROPIC_API_KEY and any other secrets without hardcoding them
# in the plist.
#
# The .env file lives in $HOME/.dharma/.env (gitignored) with permissions 600.
# Required keys for full cron operation:
#   ANTHROPIC_API_KEY=sk-ant-...   # for jobs that invoke `claude --bare`
#
# Optional keys:
#   OPENAI_API_KEY=sk-...
#   OPENROUTER_API_KEY=sk-or-...
#
# To install locally for the first time:
#   1. echo "ANTHROPIC_API_KEY=$YOUR_KEY" > ~/.dharma/.env && chmod 600 ~/.dharma/.env
#   2. launchctl bootout gui/$(id -u)/com.dharma.cron-daemon
#   3. launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.dharma.cron-daemon.plist
#
# This wrapper is invoked from the launchd plist `ProgramArguments`.

set -euo pipefail

ENV_FILE="${HOME}/.dharma/.env"
DGC_BIN="${DGC_BIN:-/opt/homebrew/bin/dgc}"

# Parse the .env file safely if it exists. We do NOT `source` it because
# `source` would execute any shell code in the file (RCE if the file is
# tampered with). Instead we read line by line, accept only KEY=VALUE pairs
# where KEY matches [A-Z_][A-Z0-9_]* (POSIX env var convention), strip
# surrounding quotes from VALUE, and export the result.
#
# Lines starting with `#` are treated as comments. Blank lines are skipped.
# A line that does not match the KEY=VALUE pattern is silently skipped (with
# a stderr warning) — this lets future-you discover bad lines without
# blocking the daemon.
if [[ -f "${ENV_FILE}" ]]; then
    while IFS= read -r line || [[ -n "${line}" ]]; do
        # Strip leading/trailing whitespace.
        line="${line#"${line%%[![:space:]]*}"}"
        line="${line%"${line##*[![:space:]]}"}"
        # Skip blank lines and comments.
        [[ -z "${line}" || "${line:0:1}" == "#" ]] && continue
        # Match KEY=VALUE where KEY is POSIX env-var-shaped.
        if [[ "${line}" =~ ^([A-Z_][A-Z0-9_]*)=(.*)$ ]]; then
            key="${BASH_REMATCH[1]}"
            value="${BASH_REMATCH[2]}"
            # Strip exactly one pair of surrounding single or double quotes.
            if [[ "${value}" =~ ^\"(.*)\"$ ]] || [[ "${value}" =~ ^\'(.*)\'$ ]]; then
                value="${BASH_REMATCH[1]}"
            fi
            export "${key}=${value}"
        else
            echo "WARN: skipping unparseable .env line: ${line}" >&2
        fi
    done < "${ENV_FILE}"
fi

# Verify the daemon binary exists and is executable.
if [[ ! -x "${DGC_BIN}" ]]; then
    echo "FATAL: dgc binary not found or not executable at ${DGC_BIN}" >&2
    echo "       set DGC_BIN env var to override (e.g. for venv-installed dgc)" >&2
    exit 127
fi

# Replace this process with the daemon. Subprocesses inherit the env we just
# sourced (if any).
exec "${DGC_BIN}" cron daemon
