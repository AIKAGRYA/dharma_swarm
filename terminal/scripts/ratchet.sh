#!/usr/bin/env bash
# Terminal hardening ratchet: one-directional code-quality counters plus
# type safety, the routing/compact-shell regressions, and all 42 hermetic
# golden frames.
# Each counter is measured fresh and compared against the recorded baseline
# in scripts/ratchet_baselines.txt. Counters may only fall; any increase
# over baseline is a regression and exits 1.
#
# Counters:
#   max_file_lines — largest source file (lines) across terminal/src
#                    (*.ts, *.tsx, recursive). The exact ceiling is tracked;
#                    end target <=400 per file.
#   dup_functions  — identically-named top-level function declarations
#                    shared between Sidebar.tsx and RepoPane.tsx.
#                    Baseline 40; end target 0.
#   record_unknown — lines containing Record<string, unknown> in
#                    src/protocol.ts plus its successor src/protocol/
#                    modules (grep -c semantics). Baseline 97; end
#                    target <=1 at the single typed ingress.
#   hex_violations — hex color literal occurrences (#RGB/#RGBA/#RRGGBB/
#                    #RRGGBBAA) across terminal/src EXCLUDING the two
#                    allowlisted files src/theme.ts and
#                    src/components/ScenicStrip.tsx (the theme law:
#                    colors are consumed via THEME tokens). Baseline 0 —
#                    already at the end target, so any hex outside the
#                    allowlist is an immediate regression.
#
# Baseline persistence (F-011): baselines live in the git-tracked
# scripts/ratchet_baselines.txt. A regression versus a stored value exits 1.
# An improvement REWRITES the stored value in place — commit the tightened
# baselines file together with the improving change, making every ratchet
# one-directional. Tightening happens only at the end of a fully green run;
# a red run never mutates the baselines file.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERMINAL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BASELINES_FILE="${SCRIPT_DIR}/ratchet_baselines.txt"

if ! BUN_BIN="$(command -v bun)"; then
  echo "ratchet: bun is required" >&2
  exit 127
fi

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
  record_count=$(grep -c 'Record<string, unknown>' "$protocol_file" || true)
  record_unknown=$(( record_unknown + record_count ))
fi
if [ -d "$protocol_dir" ]; then
  while IFS= read -r proto_file; do
    record_sources_found=1
    record_count=$(grep -c 'Record<string, unknown>' "$proto_file" || true)
    record_unknown=$(( record_unknown + record_count ))
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

# Counter: hex_violations (F-012)
theme_file="$TERMINAL_DIR/src/theme.ts"
scenic_file="$TERMINAL_DIR/src/components/ScenicStrip.tsx"
# scenicArt.ts is GENERATED image data (scripts/scenic_generate.py output —
# Hokusai pixels as hex), not styling: same theme-law exemption as the strip.
scenic_data_file="$TERMINAL_DIR/src/components/scenicArt.ts"
HEX_RE='#([0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})\b'
hex_violations=0
hex_worst_file=""
hex_worst_count=0
while IFS= read -r src_file; do
  hex_count=$(grep -oE "$HEX_RE" "$src_file" | wc -l || true)
  if [ "$hex_count" -gt 0 ]; then
    hex_violations=$(( hex_violations + hex_count ))
    if [ "$hex_count" -gt "$hex_worst_count" ]; then
      hex_worst_count=$hex_count
      hex_worst_file=$src_file
    fi
  fi
done < <(find "$TERMINAL_DIR/src" -type f \( -name '*.ts' -o -name '*.tsx' \) \
  ! -path "$theme_file" ! -path "$scenic_file" ! -path "$scenic_data_file")

baseline_hex_violations=$(read_baseline hex_violations)
echo "hex_violations=$hex_violations"

if [ "$hex_violations" -gt "$baseline_hex_violations" ]; then
  fail "hex_violations $hex_violations exceeds baseline $baseline_hex_violations (hex color literals are banned outside theme.ts/ScenicStrip.tsx — use THEME tokens; worst offender: ${hex_worst_file#"$TERMINAL_DIR"/} with $hex_worst_count)"
fi
if [ "$hex_violations" -lt "$baseline_hex_violations" ]; then
  echo "ratchet: hex_violations improved ($hex_violations < baseline $baseline_hex_violations) — tightening $BASELINES_FILE" >&2
  TIGHTENS="${TIGHTENS}hex_violations $hex_violations
"
fi

# Preserve the current-main active-track gate while retaining the richer
# whole-corpus harness. Baselines tighten only after every executable check
# below is green.
cd "${TERMINAL_DIR}"
"${BUN_BIN}" run typecheck
STUB_BRIDGE_SCENARIO=quiet DHARMA_PYTHON="${SCRIPT_DIR}/stub_bridge.py" \
  "${BUN_BIN}" test tests/app.test.ts tests/compactShell.test.tsx
"${SCRIPT_DIR}/golden_diff.sh"

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
