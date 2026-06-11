#!/usr/bin/env bash
# vibe_code_scan.sh — surface vibe-coding antipatterns in dharma_swarm
#
# This is a SCAN, not a gate. It prints counts and samples for each
# antipattern. It does NOT block any PR. The numbers it prints feed
# docs/governance/VIBE_CODE_HYGIENE.md.
#
# Run from repo root: bash scripts/governance/vibe_code_scan.sh
# Counts are heuristic; treat as signal, not proof.

set -uo pipefail
cd "$(dirname "$0")/../.."

bold() { printf "\n\033[1m=== %s ===\033[0m\n" "$1"; }
sub()  { printf "\n  -- %s --\n" "$1"; }
note() { printf "  %s\n" "$1"; }

CODE_DIRS="dharma_swarm api scripts"
TEST_DIR="tests"

bold "A. TEST QUALITY"

sub "A1: Happy-path tunnel vision (positive vs exception assertions)"
POS=$(grep -rn "assert " "$TEST_DIR" 2>/dev/null | grep -v "raises\|Exception\|Error" | wc -l)
EXC=$(grep -rn "pytest.raises\|assertRaises\|with pytest.raises" "$TEST_DIR" 2>/dev/null | wc -l)
RATIO=$(awk "BEGIN{if($EXC>0) printf \"%.1f\", $POS/$EXC; else print \"inf\"}")
note "Positive asserts:  $POS"
note "Exception asserts: $EXC"
note "Ratio (>15:1 is concerning): $RATIO"

sub "A2: Assertion-free / trivially-true tests"
TRIV=$(grep -rn "assert True\|assert .* is not None *$\|assert result *$\|assert response *$" "$TEST_DIR" 2>/dev/null | wc -l)
note "Trivial-shape assertions: $TRIV"

sub "A3: Mock-heavy"
MOCKS=$(grep -rn "MagicMock\|patch(\|mock_" "$TEST_DIR" 2>/dev/null | wc -l)
INTEG=$(find "$TEST_DIR" -path '*integration*' -name '*.py' 2>/dev/null | wc -l)
note "Mock references: $MOCKS"
note "Integration test files: $INTEG"

sub "G4: Sleep in tests"
SLEEPS=$(grep -rn "time\.sleep\|asyncio\.sleep" "$TEST_DIR" 2>/dev/null | wc -l)
note "sleep() calls in tests: $SLEEPS"

sub "G2: Skipped tests (workaround accumulation)"
SKIPS=$(grep -rn "pytest\.mark\.skip\|@skip\|@unittest\.skip\|skipTest" "$TEST_DIR" 2>/dev/null | wc -l)
XFAILS=$(grep -rn "pytest\.mark\.xfail" "$TEST_DIR" 2>/dev/null | wc -l)
note "Skipped: $SKIPS    xfail: $XFAILS"

bold "B. DOCUMENTATION QUALITY"

sub "B1: README forward-looking language"
README_FUTURE=$(grep -in "coming soon\|planned\|will be\|future support\|in the future" README.md 2>/dev/null | wc -l)
note "README forward-looking lines: $README_FUTURE"

sub "B2: Docstring inflation"
FUNCS=$(grep -rn "^def \|^    def \|^async def \|^    async def " $CODE_DIRS 2>/dev/null | wc -l)
DOCSTRS=$(grep -rn '"""' $CODE_DIRS 2>/dev/null | wc -l)
note "Function defs: $FUNCS"
note "Triple-quote occurrences: $DOCSTRS"

sub "B5: Instruction file bloat"
for f in CLAUDE.md AGENTS.md DEVIN.md .cursorrules; do
  if [ -f "$f" ]; then
    L=$(wc -l < "$f")
    MUSTS=$(grep -c "must\|never\|always\|don't\|do not" "$f" 2>/dev/null)
    note "$f: $L lines, $MUSTS imperatives (target <500 lines per file)"
  fi
done

bold "C. ARCHITECTURE & STRUCTURE"

sub "C2: Interface archaeology (versioned/legacy/new/old in class names)"
ARCH=$(grep -rn "^class .*\(V[0-9]\|New\|Old\|Refactored\|Legacy\|Tmp\|Deprecated\)" $CODE_DIRS 2>/dev/null | grep -v "Veracode\|Version" | head -20)
ARCH_COUNT=$(grep -rn "^class .*\(V[0-9]\|New\|Old\|Refactored\|Legacy\|Tmp\|Deprecated\)" $CODE_DIRS 2>/dev/null | grep -v "Veracode\|Version" | wc -l)
note "Archaeology-shaped class names: $ARCH_COUNT"
[ -n "$ARCH" ] && echo "$ARCH" | sed 's/^/    /' | head -10

sub "C4: God files (top 15 by LOC)"
find $CODE_DIRS -name '*.py' -not -path '*/__pycache__/*' 2>/dev/null \
  | xargs wc -l 2>/dev/null | sort -rn | head -16 | sed 's/^/    /'

sub "C6: Files with high lateral import count (>20 internal imports)"
for f in $(find dharma_swarm -maxdepth 1 -name '*.py' 2>/dev/null); do
  COUNT=$(grep -c "^from dharma_swarm\|^from \." "$f" 2>/dev/null)
  if [ "$COUNT" -gt 20 ]; then
    printf "    %s: %d internal imports\n" "$f" "$COUNT"
  fi
done

sub "J3: Stub leakage (NotImplementedError, TODO-implement, lone pass)"
STUBS=$(grep -rn "raise NotImplementedError" $CODE_DIRS 2>/dev/null | wc -l)
TODOS=$(grep -rn "TODO.*implement\|TODO:.*implement\|FIXME.*implement" $CODE_DIRS 2>/dev/null | wc -l)
note "NotImplementedError: $STUBS"
note "TODO-implement markers: $TODOS"

bold "D. PHANTOM DEPENDENCIES"

sub "D3: Pinning hygiene (requirements*.txt)"
for r in $(find . -maxdepth 3 -name 'requirements*.txt' -not -path './.git/*' 2>/dev/null | head -5); do
  TOTAL=$(grep -c "^[a-zA-Z]" "$r" 2>/dev/null)
  UNPINNED=$(grep -c "^[a-zA-Z][a-zA-Z0-9_\-]*$" "$r" 2>/dev/null)
  note "$r: $TOTAL deps, $UNPINNED unpinned"
done

sub "D4: Deprecated API patterns"
OAI_V0=$(grep -rn "openai\.ChatCompletion\|openai\.Engine\|text-davinci" $CODE_DIRS 2>/dev/null | wc -l)
SQA_V1=$(grep -rn "\.query(" $CODE_DIRS 2>/dev/null | grep -v "session\.execute" | wc -l)
note "OpenAI v0 patterns (ChatCompletion/Engine/davinci): $OAI_V0"
note ".query( calls (SQLAlchemy v1 style — verify): $SQA_V1"

bold "E. SECURITY"

sub "E2: Hardcoded credentials (heuristic — verify by hand)"
HARDCODED=$(grep -rn "API_KEY\s*=\s*[\"'][a-zA-Z0-9_\-]\{20,\}\|password\s*=\s*[\"'][^\"']\{8,\}" $CODE_DIRS 2>/dev/null | grep -v test_ | grep -v "example\|placeholder\|YOUR_\|FAKE_\|EXAMPLE\|os.environ\|getenv" | wc -l)
note "Suspicious literal API_KEY/password assignments: $HARDCODED"

sub "E4: Weak crypto"
WEAK=$(grep -rn "hashlib\.md5\|hashlib\.sha1\|DES\|ECB" $CODE_DIRS 2>/dev/null | grep -v "checksum\|content-id\|integrity\|cache_key\|etag" | wc -l)
note "Weak crypto references (non-checksum): $WEAK"

sub "E5: Prompt injection — user input directly in f-string prompts"
PI=$(grep -rEn 'f["\x27].*\{(user|message|query|input|prompt)' $CODE_DIRS 2>/dev/null | grep -i "system\|instruction\|completion\|chat\|prompt" | wc -l)
note "User-input-in-prompt f-strings: $PI"

bold "F. CONTEXT-WINDOW ARTIFACTS"

sub "F2: Copy-paste duplication candidates (functions with same name in different files)"
DUP=$(grep -rh "^def [a-z_][a-z_0-9]*(" $CODE_DIRS 2>/dev/null | sort | uniq -c | sort -rn | awk '$1 > 5 {print}' | head -10)
note "Function names defined >5 times across files:"
[ -n "$DUP" ] && echo "$DUP" | sed 's/^/    /'

sub "F5: Naming entropy — single-letter / generic names in non-loop contexts"
GENERIC=$(grep -rEn "^def (data|info|stuff|thing|process|handle|do|run)\(" $CODE_DIRS 2>/dev/null | wc -l)
note "Generic function names (data/info/stuff/thing/process/handle/do/run): $GENERIC"

bold "G. AGENT-LOOP PATHOLOGIES"

sub "G1: Recent commit velocity (commits/day, last 14 days)"
git log --since="14 days ago" --format='%cI' 2>/dev/null | cut -dT -f1 | sort | uniq -c | sort -rn | head -10 | sed 's/^/    /'

sub "G2: Suppression density (# type: ignore / noqa / pylint disable)"
SUPP=$(grep -rn "# type: ignore\|# noqa\|# pylint: disable" $CODE_DIRS 2>/dev/null | wc -l)
note "Total suppressions: $SUPP"

sub "G2: Bare-except / Exception-swallow blocks"
BARE=$(grep -rn "except:\s*$\|except Exception:\s*$\|except Exception as.*:\s*$" $CODE_DIRS 2>/dev/null | wc -l)
note "Bare/wide excepts: $BARE"

sub "G5: Fabricated commit messages (low-information shapes)"
git log --oneline -200 2>/dev/null | grep -iE "^[a-f0-9]+ (fix|update|improve|wip|stuff|things)( |$)" | wc -l | xargs printf "    Low-info commits in last 200: %s\n"

bold "H. PERFORMANCE"

sub "H2: Sync blocking calls inside async functions (heuristic AST scan)"
python3 - <<'PY'
import ast, glob, os
hits = []
for fn in glob.glob('dharma_swarm/**/*.py', recursive=True):
    if '__pycache__' in fn: continue
    try:
        tree = ast.parse(open(fn).read())
    except Exception:
        continue
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef):
            for child in ast.walk(node):
                if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
                    full = ast.unparse(child.func) if hasattr(ast, 'unparse') else child.func.attr
                    if full in ('time.sleep', 'requests.get', 'requests.post', 'requests.put', 'requests.delete', 'subprocess.run', 'subprocess.call'):
                        hits.append(f"  {fn}:{child.lineno}: {full} inside async {node.name}")
print(f"  Suspicious sync-in-async sites: {len(hits)}")
for h in hits[:10]:
    print(h)
PY

sub "H3: Round-trip serialization"
RT=$(grep -rEn "json\.loads\(.*json\.dumps|json\.dumps\(.*json\.loads" $CODE_DIRS 2>/dev/null | wc -l)
note "Round-trip json.loads/json.dumps in one line: $RT"

bold "I. DISTRIBUTED SYSTEMS CORRECTNESS"

sub "I5: Async error swallowing (except without raise/log)"
SWALLOW=$(grep -rn -A1 "except Exception:\|except:" $CODE_DIRS 2>/dev/null | grep -A0 "pass$" | wc -l)
note "except blocks followed by bare pass: $SWALLOW"

sub "I4: Unprotected self-state mutations (heuristic)"
MUT=$(grep -rEn "self\.[a-z_]+\s*\+=" $CODE_DIRS 2>/dev/null | wc -l)
LOCKED=$(grep -rEn "asyncio\.Lock|threading\.Lock|trio\.Lock" $CODE_DIRS 2>/dev/null | wc -l)
note "self.x += pattern occurrences: $MUT"
note "Lock declarations: $LOCKED"

bold "DONE"
