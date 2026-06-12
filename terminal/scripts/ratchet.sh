#!/usr/bin/env bash
# S0 ratchet (F-008): one-directional code-quality counters for terminal/.
# Each counter is measured fresh and compared against the recorded baseline
# in scripts/ratchet_baselines.txt. Counters may only fall; any increase
# over baseline is a regression and exits 1.
#
# Counters:
#   max_file_lines — largest source file (lines) across terminal/src
#                    (*.ts, *.tsx, recursive). Baseline 4064 = protocol.ts;
#                    end target <=400 per file.
#   dup_functions  — identically-named top-level function declarations
#                    shared between Sidebar.tsx and RepoPane.tsx.
#                    Baseline 40; end target 0.
#
# F-010 (record_unknown) and F-012 (hex_violations) extend this script
# with their own counters when they land.
set -u

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
TERMINAL_DIR=$(dirname "$SCRIPT_DIR")
BASELINES_FILE="$SCRIPT_DIR/ratchet_baselines.txt"

fail() {
  echo "ratchet: FAIL — $1" >&2
  exit 1
}

[ -f "$BASELINES_FILE" ] || fail "baselines file missing: $BASELINES_FILE"

read_baseline() {
  local key="$1" value
  value=$(grep -E "^${key}=" "$BASELINES_FILE" | head -n 1 | cut -d= -f2)
  case "$value" in
    ''|*[!0-9]*) fail "baseline '$key' missing or non-numeric in $BASELINES_FILE" ;;
  esac
  printf '%s' "$value"
}

# Counter: max_file_lines (F-008)
max_file_lines=0
max_file=""
while IFS= read -r src_file; do
  lines=$(( $(wc -l < "$src_file") ))
  if [ "$lines" -gt "$max_file_lines" ]; then
    max_file_lines=$lines
    max_file=$src_file
  fi
done < <(find "$TERMINAL_DIR/src" -type f \( -name '*.ts' -o -name '*.tsx' \))

[ -n "$max_file" ] || fail "no source files found under $TERMINAL_DIR/src"

baseline_max_file_lines=$(read_baseline max_file_lines)
echo "max_file_lines=$max_file_lines"

if [ "$max_file_lines" -gt "$baseline_max_file_lines" ]; then
  fail "max_file_lines $max_file_lines exceeds baseline $baseline_max_file_lines (largest: ${max_file#"$TERMINAL_DIR"/})"
fi
if [ "$max_file_lines" -lt "$baseline_max_file_lines" ]; then
  echo "ratchet: max_file_lines improved ($max_file_lines < baseline $baseline_max_file_lines) — tighten $BASELINES_FILE" >&2
fi

# Counter: dup_functions (F-009)
sidebar_file="$TERMINAL_DIR/src/components/Sidebar.tsx"
repopane_file="$TERMINAL_DIR/src/components/RepoPane.tsx"
[ -f "$sidebar_file" ] || fail "missing source file: $sidebar_file"
[ -f "$repopane_file" ] || fail "missing source file: $repopane_file"

top_level_fn_names() {
  grep -oE '^(export )?function [A-Za-z0-9_]+' "$1" | sed -E 's/^(export )?function //' | sort -u
}

dup_functions=$(( $(comm -12 <(top_level_fn_names "$sidebar_file") <(top_level_fn_names "$repopane_file") | wc -l) ))
baseline_dup_functions=$(read_baseline dup_functions)
echo "dup_functions=$dup_functions"

if [ "$dup_functions" -gt "$baseline_dup_functions" ]; then
  fail "dup_functions $dup_functions exceeds baseline $baseline_dup_functions (top-level function names shared by Sidebar.tsx and RepoPane.tsx)"
fi
if [ "$dup_functions" -lt "$baseline_dup_functions" ]; then
  echo "ratchet: dup_functions improved ($dup_functions < baseline $baseline_dup_functions) — tighten $BASELINES_FILE" >&2
fi

echo "ratchet: OK"
exit 0
