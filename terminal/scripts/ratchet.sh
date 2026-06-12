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
#   record_unknown — lines containing Record<string, unknown> in
#                    src/protocol.ts plus its successor src/protocol/
#                    modules (grep -c semantics). Baseline 97; end
#                    target <=1 at the single typed ingress.
#
# Baseline persistence (F-011): baselines live in the git-tracked
# scripts/ratchet_baselines.txt. A regression versus a stored value exits 1.
# An improvement REWRITES the stored value in place — commit the tightened
# baselines file together with the improving change, making every ratchet
# one-directional. Tightening happens only at the end of a fully green run;
# a red run never mutates the baselines file.
#
# F-012 (hex_violations) extends this script with its own counter when
# it lands.
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

# F-011: rewrite one key=value line in the baselines file (in-place truncate,
# preserves every other line byte-for-byte).
tighten_baseline() {
  local key="$1" new_value="$2" rewritten
  rewritten=$(awk -v key="$key" -v val="$new_value" -F= \
    '$1 == key { print key "=" val; next } { print }' "$BASELINES_FILE")
  printf '%s\n' "$rewritten" > "$BASELINES_FILE"
}

# Improvements collected as "key value" lines, applied only on a green run.
TIGHTENS=""

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
  echo "ratchet: max_file_lines improved ($max_file_lines < baseline $baseline_max_file_lines) — tightening $BASELINES_FILE" >&2
  TIGHTENS="${TIGHTENS}max_file_lines $max_file_lines
"
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
  echo "ratchet: dup_functions improved ($dup_functions < baseline $baseline_dup_functions) — tightening $BASELINES_FILE" >&2
  TIGHTENS="${TIGHTENS}dup_functions $dup_functions
"
fi

# Counter: record_unknown (F-010)
protocol_file="$TERMINAL_DIR/src/protocol.ts"
protocol_dir="$TERMINAL_DIR/src/protocol"
record_unknown=0
record_sources_found=0
if [ -f "$protocol_file" ]; then
  record_sources_found=1
  record_unknown=$(( record_unknown + $(grep -c 'Record<string, unknown>' "$protocol_file") ))
fi
if [ -d "$protocol_dir" ]; then
  while IFS= read -r proto_file; do
    record_sources_found=1
    record_unknown=$(( record_unknown + $(grep -c 'Record<string, unknown>' "$proto_file") ))
  done < <(find "$protocol_dir" -type f \( -name '*.ts' -o -name '*.tsx' \))
fi
[ "$record_sources_found" -eq 1 ] || fail "no protocol sources found (src/protocol.ts or src/protocol/)"

baseline_record_unknown=$(read_baseline record_unknown)
echo "record_unknown=$record_unknown"

if [ "$record_unknown" -gt "$baseline_record_unknown" ]; then
  fail "record_unknown $record_unknown exceeds baseline $baseline_record_unknown (Record<string, unknown> lines in src/protocol.ts + src/protocol/)"
fi
if [ "$record_unknown" -lt "$baseline_record_unknown" ]; then
  echo "ratchet: record_unknown improved ($record_unknown < baseline $baseline_record_unknown) — tightening $BASELINES_FILE" >&2
  TIGHTENS="${TIGHTENS}record_unknown $record_unknown
"
fi

# F-011: all counters green — persist any improvements so the ratchet is
# one-directional from here on. Commit the rewritten baselines file with
# the improving change.
if [ -n "$TIGHTENS" ]; then
  printf '%s' "$TIGHTENS" | while read -r t_key t_value; do
    [ -n "$t_key" ] || continue
    tighten_baseline "$t_key" "$t_value"
    echo "ratchet: tightened $t_key baseline to $t_value in $BASELINES_FILE — commit it with this change" >&2
  done
fi

echo "ratchet: OK"
exit 0
