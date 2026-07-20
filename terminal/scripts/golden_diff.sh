#!/usr/bin/env bash
# Golden-diff checker (F-018): captures a fresh offline frame corpus into a
# mktemp dir via golden_capture.sh (GOLDEN_OUT_DIR override) and compares it
# file-by-file against the committed corpus under tests/golden/.
#
#   exit 0 — every fresh frame is byte-identical to its committed golden
#   exit 1 — drift: every drifted frame is named, the first one is shown
#            as a unified diff excerpt
#
# Approval doctrine: approved drift is an explicit re-capture commit —
# run scripts/golden_capture.sh and commit the regenerated corpus; never
# edit a golden frame in place. This checker only reports; it never writes
# into tests/golden/ and leaves zero worktree churn (the fresh capture lands
# in a temp dir cleaned on exit).
#
# Scope: the three capture sizes only (80x24/100x30/120x40). The pre-theme/
# corpus is owned by the boot-smoke goldens, not by golden_capture.sh.
set -u

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
TERMINAL_DIR=$(dirname "$SCRIPT_DIR")
GOLDEN_ROOT=$TERMINAL_DIR/tests/golden
SIZES="80x24 100x30 120x40"

FRESH=""
# Invoked indirectly by the EXIT trap.
# shellcheck disable=SC2329
cleanup() {
  if [ -n "$FRESH" ]; then
    find "$FRESH" -mindepth 1 -delete 2>/dev/null
    rmdir "$FRESH" 2>/dev/null
    FRESH=""
  fi
}
trap cleanup EXIT

fail() {
  echo "golden_diff: FAIL — $1" >&2
  exit 1
}

for size in $SIZES; do
  [ -d "$GOLDEN_ROOT/$size" ] || fail "committed corpus missing $GOLDEN_ROOT/$size — run golden_capture.sh and commit the corpus (F-017) first"
done

FRESH=$(mktemp -d)
GOLDEN_OUT_DIR=$FRESH bash "$SCRIPT_DIR/golden_capture.sh" >&2 \
  || fail "fresh capture failed (golden_capture.sh nonzero) — cannot judge drift; fix the capture before trusting goldens"

drifted=""
ndrift=0
for size in $SIZES; do
  for committed in "$GOLDEN_ROOT/$size"/*.txt; do
    name=$(basename "$committed")
    freshf=$FRESH/$size/$name
    if [ ! -f "$freshf" ]; then
      drifted="$drifted $size/$name(missing-from-fresh-capture)"
      ndrift=$(( ndrift + 1 ))
    elif ! cmp -s "$committed" "$freshf"; then
      drifted="$drifted $size/$name"
      ndrift=$(( ndrift + 1 ))
    fi
  done
  for freshf in "$FRESH/$size"/*.txt; do
    name=$(basename "$freshf")
    if [ ! -f "$GOLDEN_ROOT/$size/$name" ]; then
      drifted="$drifted $size/$name(uncommitted-new-frame)"
      ndrift=$(( ndrift + 1 ))
    fi
  done
done

if [ "$ndrift" -gt 0 ]; then
  # Intentional word-split of the drift list.
  # shellcheck disable=SC2086
  set -- $drifted
  first=$1
  echo "golden_diff: DRIFT — $ndrift frame(s) differ from the committed golden corpus" >&2
  echo "golden_diff: first drifted frame: tests/golden/$first" >&2
  for f in "$@"; do
    echo "golden_diff:   drifted: tests/golden/$f" >&2
  done
  firstpath=${first%%(*}
  if [ -f "$GOLDEN_ROOT/$firstpath" ] && [ -f "$FRESH/$firstpath" ]; then
    echo "golden_diff: unified diff excerpt (committed vs fresh) for tests/golden/$firstpath:" >&2
    diff -u "$GOLDEN_ROOT/$firstpath" "$FRESH/$firstpath" | head -40 >&2
  fi
  echo "golden_diff: approved drift = re-capture and commit via scripts/golden_capture.sh; never edit a golden in place" >&2
  exit 1
fi

echo "golden_diff: OK (fresh capture matches tests/golden for $SIZES)"
exit 0
