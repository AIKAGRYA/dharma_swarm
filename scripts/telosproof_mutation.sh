#!/usr/bin/env bash
# =====================================================================
# telosproof_mutation.sh  —  ADVISORY mutation-testing gate for the
#                            dharma_swarm.telosproof safety kernel.
# =====================================================================
# OWNED NEW FILE (Generator 3). Pairs with scripts/telosproof_mutmut_setup.cfg.
#
# WHAT IT DOES
#   Runs mutmut (the lighter, lower-config mutation tool — chosen over
#   cosmic-ray, whose session/DB model would risk an implicit new
#   persistence substrate, invariant #7) against the telosproof package:
#       dharma_swarm/telosproof/{allowlist,change_summary,invariants,gate}.py
#   using the telosproof test corpus:
#       tests/test_telosproof*.py   (picks up test_telosproof_allowlist.py
#                                     automatically once G1 lands it)
#   then reports the mutation KILL RATE and gates on a threshold.
#
# TARGET THRESHOLD  >= 80% killed   (survived / total <= 20%)
#   The telosproof package is the proof-carrying safety kernel (ADR-0003
#   names mutation testing as a crossover gate). It is small and heavily
#   branched conservative-on-doubt logic, so a high bar is achievable and
#   meaningful: a surviving mutant that flips a danger-default to the
#   permissive value is the exact false-negative this kernel exists to
#   prevent. Surviving mutants on the safety-critical modules are surfaced
#   by name so a reviewer can confirm none is a false-negative-introducer.
#
# ISOLATION / NON-INVASIVENESS (HARD RULES honoured)
#   * ADVISORY ONLY. No live-path wiring. Imports nothing from
#     diff_applier / dgm_loop / evolution. Pure quality gate.
#   * Touches NO existing config. mutmut 3.x reads paths_to_mutate only
#     from a config file in CWD, so this script builds an EPHEMERAL
#     staging dir under $TMPDIR, symlinks dharma_swarm/ + tests/ into it,
#     copies scripts/telosproof_mutmut_setup.cfg in as `setup.cfg`, and
#     runs mutmut there. The repo-root pyproject.toml / setup.cfg are
#     never read or written. mutmut's own .mutmut-cache / mutants/ live
#     inside the staging dir and are deleted on exit — ephemeral test
#     scaffolding, NOT a tracked persistence store.
#   * No git, no secrets, no daemon. Run once; report the number.
#
# EXIT CODES
#   0  kill rate >= threshold   (or skip-clean when neither tool/pip avail)
#   1  kill rate <  threshold
#   2  hard environment blocker the script could not resolve
#
# USAGE
#   bash scripts/telosproof_mutation.sh            # gate at 80%
#   KILL_THRESHOLD=85 bash scripts/telosproof_mutation.sh
#   bash scripts/telosproof_mutation.sh --no-install   # never pip-install
# =====================================================================
set -uo pipefail

# ---------------------------------------------------------------------
# 0. Locate the repo root (this script lives in <repo>/scripts/).
# ---------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." >/dev/null 2>&1 && pwd)"
CONFIG_SRC="$SCRIPT_DIR/telosproof_mutmut_setup.cfg"

KILL_THRESHOLD="${KILL_THRESHOLD:-80}"   # percent killed required to pass
ALLOW_INSTALL=1
for arg in "$@"; do
    case "$arg" in
        --no-install) ALLOW_INSTALL=0 ;;
        --help|-h)
            sed -n '2,55p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
            exit 0 ;;
    esac
done

say()  { printf '%s\n' "$*"; }
hr()   { printf -- '---------------------------------------------------------------\n'; }
die()  { printf 'ERROR: %s\n' "$*" >&2; exit 2; }

hr
say "telosproof mutation testing  (tool: mutmut, threshold: >= ${KILL_THRESHOLD}% killed)"
hr

# ---------------------------------------------------------------------
# 1. Resolve the Python interpreter. Prefer the repo venv; fall back to
#    python3 on PATH. The venv on this machine symlinks to the base
#    interpreter, so site-packages are shared — that is fine.
# ---------------------------------------------------------------------
PY=""
if [ -x "$REPO_ROOT/.venv/bin/python3" ]; then
    PY="$REPO_ROOT/.venv/bin/python3"
elif command -v python3 >/dev/null 2>&1; then
    PY="$(command -v python3)"
else
    die "no python3 found (looked for $REPO_ROOT/.venv/bin/python3 and PATH)."
fi
say "python: $PY ($("$PY" --version 2>&1))"

# ---------------------------------------------------------------------
# 2. Ensure mutmut is importable. If not: try to pip-install into the
#    venv (when allowed), else degrade GRACEFULLY with instructions and
#    skip-clean (exit 0) so CI / `make test` is never hard-blocked on the
#    optional mutation extra — mirrors the Lean lazy-skip in plan section 7.
# ---------------------------------------------------------------------
have_mutmut() { "$PY" -c "import mutmut" >/dev/null 2>&1; }

if ! have_mutmut; then
    say "mutmut not importable."
    if [ "$ALLOW_INSTALL" -eq 1 ] && "$PY" -m pip --version >/dev/null 2>&1; then
        say "attempting: $PY -m pip install 'mutmut>=3.0'"
        if "$PY" -m pip install --quiet 'mutmut>=3.0' >/dev/null 2>&1 && have_mutmut; then
            say "mutmut installed OK."
        else
            say "pip install failed."
        fi
    fi
fi

if ! have_mutmut; then
    hr
    say "SKIP-CLEAN: mutmut is not available and could not be installed."
    say "This is an OPTIONAL quality gate; the default test path is unaffected."
    say ""
    say "To enable mutation testing, install mutmut into the project venv:"
    say "    $PY -m pip install 'mutmut>=3.0'"
    say "then re-run:"
    say "    bash scripts/telosproof_mutation.sh"
    hr
    exit 0
fi

MUTMUT_VER="$("$PY" -c "import mutmut; print(getattr(mutmut,'__version__','?'))" 2>/dev/null)"
say "mutmut: $MUTMUT_VER"

if [ ! -f "$CONFIG_SRC" ]; then
    die "missing companion config: $CONFIG_SRC"
fi

# ---------------------------------------------------------------------
# 3. Determine the mutation scope: only telosproof modules that exist.
#    (allowlist.py may be authored by a parallel generator; tolerate its
#    absence so this script is order-independent.)
# ---------------------------------------------------------------------
TELOSPROOF_DIR="$REPO_ROOT/dharma_swarm/telosproof"
declare -a MOD_CANDIDATES=(allowlist.py change_summary.py invariants.py gate.py)
declare -a PATHS_TO_MUTATE=()
for m in "${MOD_CANDIDATES[@]}"; do
    if [ -f "$TELOSPROOF_DIR/$m" ]; then
        PATHS_TO_MUTATE+=("dharma_swarm/telosproof/$m")
    fi
done
if [ "${#PATHS_TO_MUTATE[@]}" -eq 0 ]; then
    die "no telosproof modules found under $TELOSPROOF_DIR"
fi
say "mutating: ${PATHS_TO_MUTATE[*]}"

# Discover the telosproof test files (glob tolerates the not-yet-present
# tests/test_telosproof_allowlist.py).
declare -a TEST_FILES=()
for t in "$REPO_ROOT"/tests/test_telosproof*.py; do
    [ -f "$t" ] && TEST_FILES+=("tests/$(basename "$t")")
done
if [ "${#TEST_FILES[@]}" -eq 0 ]; then
    die "no tests/test_telosproof*.py found"
fi
say "tests:    ${TEST_FILES[*]}"

# ---------------------------------------------------------------------
# 4. Build an ephemeral staging dir and wire it up.
# ---------------------------------------------------------------------
STAGE="$(mktemp -d "${TMPDIR:-/tmp}/telosproof_mutation.XXXXXX")" || die "mktemp failed"
cleanup() {
    # Remove the mutants/ subtree first (it can contain a deep copy of the
    # package) using a plain rm, then the staging dir.
    [ -d "$STAGE/mutants" ] && /bin/rm -rf "$STAGE/mutants" 2>/dev/null
    /bin/rm -rf "$STAGE" 2>/dev/null
}
trap cleanup EXIT INT TERM

# Symlink the live package + tests into the stage (no copy: the mutated
# copies are produced by mutmut inside mutants/ via also_copy).
ln -s "$REPO_ROOT/dharma_swarm" "$STAGE/dharma_swarm"
mkdir -p "$STAGE/tests"
# Bring in conftest + only the telosproof test files (keeps collection fast
# and avoids importing the whole heavy test tree).
[ -f "$REPO_ROOT/tests/conftest.py" ] && ln -s "$REPO_ROOT/tests/conftest.py" "$STAGE/tests/conftest.py"
for t in "${TEST_FILES[@]}"; do
    ln -s "$REPO_ROOT/$t" "$STAGE/$t"
done

# --- 4a. macOS / Python 3.13 fork fix -------------------------------------
# mutmut 3.5.0 calls multiprocessing.set_start_method('fork') at module
# import time (__main__.py); when the mutated source's trampoline re-imports
# mutmut in the pytest subprocess, the second call raises
# 'context has already been set' and the whole run fails to collect stats.
# We make set_start_method idempotent via a sitecustomize.py on the stage's
# path (Python auto-imports sitecustomize on startup, including in the
# pytest subprocesses). This is an in-process compatibility shim, not an
# edit to mutmut.
cat > "$STAGE/sitecustomize.py" <<'PYEOF'
import multiprocessing as _mp

_orig = _mp.set_start_method


def _idempotent_set_start_method(method=None, force=False):
    try:
        return _orig(method, force=True)
    except (RuntimeError, ValueError):
        return None


_mp.set_start_method = _idempotent_set_start_method
try:
    import multiprocessing.context as _ctx

    _ctx.BaseContext.set_start_method = (
        lambda self, method=None, force=False: None
    )
except Exception:
    pass
PYEOF

# --- 4b. Materialise the mutmut config in the stage ------------------------
# Start from the owned companion config, then overwrite paths_to_mutate and
# the test selection with the concrete, existing values resolved above.
CFG="$STAGE/setup.cfg"
{
    # Copy every line EXCEPT the dynamic config keys and the indented
    # continuation lines that belong to them; we re-emit those with the
    # concrete resolved values. mutmut 3.x splits list-valued config ONLY
    # on newlines (verified in __main__.config_reader), so multi-value
    # keys MUST be emitted as one indented path per line — a comma-joined
    # single line is parsed as ONE bogus path and yields ZERO mutants.
    "$PY" - "$CONFIG_SRC" <<'PYEOF'
import sys
dynamic = {"paths_to_mutate", "pytest_add_cli_args_test_selection"}
skip_block = False
with open(sys.argv[1]) as fh:
    for line in fh:
        stripped = line.lstrip()
        if not line.startswith((" ", "\t")) and "=" in line:
            key = line.split("=", 1)[0].strip()
            skip_block = key in dynamic
            if skip_block:
                continue
        elif skip_block and line.startswith((" ", "\t")):
            # indented continuation of a skipped multi-line value
            continue
        else:
            skip_block = False
        sys.stdout.write(line)
PYEOF
    # Re-emit the two dynamic keys as newline-delimited lists.
    printf 'paths_to_mutate=\n'
    for p in "${PATHS_TO_MUTATE[@]}"; do
        printf '    %s\n' "$p"
    done
    printf 'pytest_add_cli_args_test_selection=\n'
    for t in "${TEST_FILES[@]}"; do
        printf '    %s\n' "$t"
    done
} > "$CFG"

say ""
say "staging dir: $STAGE"

# ---------------------------------------------------------------------
# 5. Run mutmut from the staging dir.
# ---------------------------------------------------------------------
export PYTHONPATH="$STAGE${PYTHONPATH:+:$PYTHONPATH}"
RUN_LOG="$STAGE/mutmut_run.log"
hr
say "running mutmut (this mutates the telosproof package and runs the corpus)..."
(
    cd "$STAGE" || exit 2
    "$PY" -m mutmut run
) >"$RUN_LOG" 2>&1
RUN_RC=$?

# A non-zero rc from `mutmut run` is normal when mutants survive; only treat
# a stats-collection failure (no scored mutants) as a hard blocker below.
# Surface the last meaningful progress line for transparency.
LAST_PROGRESS="$(tr '\r' '\n' < "$RUN_LOG" | grep -E '[0-9]+/[0-9]+' | tail -1)"
[ -n "$LAST_PROGRESS" ] && say "progress: $LAST_PROGRESS"

if grep -qiE 'failed to collect stats|context has already been set|Interrupted: .* error during collection' "$RUN_LOG"; then
    say ""
    say "mutmut failed before scoring any mutant. Tail of run log:"
    tr '\r' '\n' < "$RUN_LOG" | grep -vE 'Generating mutants|Running stats|Running clean|forced fail|also copying' | tail -20
    exit 2
fi

# ---------------------------------------------------------------------
# 6. Extract machine-readable stats and compute the kill rate.
# ---------------------------------------------------------------------
(
    cd "$STAGE" || exit 2
    "$PY" -m mutmut export-cicd-stats
) >/dev/null 2>&1

STATS_JSON="$STAGE/mutants/mutmut-cicd-stats.json"
if [ ! -f "$STATS_JSON" ]; then
    say "stats JSON not produced; falling back to parsing the progress line."
fi

# Parse the JSON (preferred) or the final progress line (fallback) and
# compute kill rate = killed / scored, where scored = killed + survived
# (+ timeout + suspicious treated as kills per mutmut's exit-code model,
# but counted explicitly so the report is honest).
read -r KILLED SURVIVED TIMEOUT SUSPICIOUS SKIPPED NOTESTS TOTAL RATE <<EOF
$("$PY" - "$STATS_JSON" "$RUN_LOG" <<'PYEOF'
import json, re, sys
stats_path, run_log = sys.argv[1], sys.argv[2]
killed = survived = timeout = suspicious = skipped = no_tests = total = 0
loaded = False
try:
    with open(stats_path) as fh:
        d = json.load(fh)
    killed = int(d.get("killed", 0))
    survived = int(d.get("survived", 0))
    timeout = int(d.get("timeout", 0))
    suspicious = int(d.get("suspicious", 0))
    skipped = int(d.get("skipped", 0))
    no_tests = int(d.get("no_tests", 0))
    total = int(d.get("total", killed + survived + timeout + suspicious + skipped + no_tests))
    loaded = True
except Exception:
    pass

if not loaded:
    # Fallback: parse the last emoji progress line. Glyphs:
    #   N/M  🎉 killed  🫥 no_tests  ⏰ timeout  🤔 suspicious  🙁 survived  🔇 skipped
    try:
        with open(run_log, encoding="utf-8", errors="replace") as fh:
            txt = fh.read().replace("\r", "\n")
        line = ""
        for ln in txt.splitlines():
            if re.search(r"\d+/\d+", ln) and "🎉" in ln:
                line = ln
        def g(glyph):
            m = re.search(re.escape(glyph) + r"\s*(\d+)", line)
            return int(m.group(1)) if m else 0
        killed, no_tests, timeout = g("🎉"), g("🫥"), g("⏰")
        suspicious, survived, skipped = g("🤔"), g("🙁"), g("🔇")
        mt = re.search(r"(\d+)/(\d+)", line)
        total = int(mt.group(2)) if mt else (killed + survived + timeout + suspicious + skipped + no_tests)
    except Exception:
        pass

# scored = mutants that actually exercised the tests (exclude no_tests/skipped).
scored = killed + survived + timeout + suspicious
# Honest kill rate: only `survived` is an unambiguous miss; timeout &
# suspicious are mutmut-classified kills. Denominator excludes survived? No:
# rate = (killed + timeout + suspicious) / scored.
effective_kills = killed + timeout + suspicious
rate = (100.0 * effective_kills / scored) if scored else 0.0
print(killed, survived, timeout, suspicious, skipped, no_tests, total, f"{rate:.2f}")
PYEOF
)
EOF

# ---------------------------------------------------------------------
# 7. Surface surviving mutants on the safety-critical modules by name.
#    A surviving mutant that flips a danger-default to a permissive value
#    is a hard concern even under threshold — list them for human review.
# ---------------------------------------------------------------------
SURVIVORS_RAW="$(cd "$STAGE" && "$PY" -m mutmut results --all true 2>/dev/null | tr '\r' '\n' | grep -iE ': survived$' | sed 's/^[[:space:]]*//')"

hr
say "MUTATION RESULTS (telosproof package)"
hr
printf '  killed      : %s\n' "${KILLED:-0}"
printf '  survived    : %s   <-- not caught by the test corpus\n' "${SURVIVED:-0}"
printf '  timeout     : %s\n' "${TIMEOUT:-0}"
printf '  suspicious  : %s\n' "${SUSPICIOUS:-0}"
printf '  skipped     : %s\n' "${SKIPPED:-0}"
printf '  no_tests    : %s\n' "${NOTESTS:-0}"
printf '  total       : %s\n' "${TOTAL:-0}"
printf '  KILL RATE   : %s%%   (threshold >= %s%%)\n' "${RATE:-0.00}" "$KILL_THRESHOLD"

if [ -n "$SURVIVORS_RAW" ]; then
    hr
    say "SURVIVING MUTANTS (review each — a danger-default flipped to permissive is a hard fail):"
    # Highlight survivors on the safety-critical modules.
    printf '%s\n' "$SURVIVORS_RAW" | while IFS= read -r s; do
        case "$s" in
            *allowlist*|*invariants*|*gate*|*change_summary*)
                printf '  [SAFETY] %s\n' "$s" ;;
            *)
                printf '          %s\n' "$s" ;;
        esac
    done
    say ""
    say "Inspect any survivor with:  (in the staging run) mutmut show <name>"
    say "A survivor that makes the gate MORE permissive (e.g. flips a"
    say "deny-by-default branch to allow) must be killed with a new test"
    say "before this gate is trusted, regardless of the aggregate rate."
fi

# ---------------------------------------------------------------------
# 8. Gate.
# ---------------------------------------------------------------------
hr
PASS="$("$PY" -c "import sys; r=float('${RATE:-0}'); t=float('$KILL_THRESHOLD'); print('1' if r>=t else '0')" 2>/dev/null)"
if [ "$PASS" = "1" ]; then
    say "RESULT: PASS  (kill rate ${RATE:-0.00}% >= ${KILL_THRESHOLD}%)"
    exit 0
else
    say "RESULT: FAIL  (kill rate ${RATE:-0.00}% < ${KILL_THRESHOLD}%)"
    say "Add targeted tests that die when the surviving mutants are applied,"
    say "then re-run. The telosproof kernel must not ship under-tested."
    exit 1
fi
