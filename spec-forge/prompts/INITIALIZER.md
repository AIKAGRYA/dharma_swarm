# HELM INITIALIZER — Session 0 (run exactly once)

You are the first session of a strictly sequential overnight build loop: one fresh-context session per feature, single lane, no parallel agents. This session does NO feature work. It establishes the baseline truth artifacts every later session depends on: the characterized failure set, the progress file, the lessons file, the truecolor pre-flight result, and the pre-theme golden frames.

Worktree: `/Users/dhyana/dharma_helm_build` — branch `helm/worldclass-20260612`, baseline commit `a6ad97362`.
App: `terminal/` (Bun + Ink). Spec artifacts: `spec-forge/` at the worktree root.

Two binding lines for this session:

- "Leave the environment in a clean state, appropriate for merging to a main branch."
- "Before reporting progress, audit each claim against a tool result from this session. Only report work you can point to evidence for; if something is not yet verified, say so explicitly."

Environment facts (apply to every command below):

- Booting the app rewrites `.dharma-terminal-state.json`. Every boot sets `DHARMA_TERMINAL_STATE_DIR` and `DHARMA_TERMINAL_SUPERVISOR_STATE_DIR` to a fresh `$(mktemp -d)`.
- Hermetic boots set `DHARMA_PYTHON=/nonexistent/python`; the app degrades gracefully to "backend offline, retrying" without the Python bridge.
- tmux send-keys races the render. After any send-keys, sleep at least 1.5 seconds before capture-pane.
- Pre-existing expected dirt at session start: `terminal/.dharma-terminal-state.json` modified, `terminal/bun.lock` and `.parked-fresh-node-modules/` untracked. Restore the state file to HEAD content via `git show HEAD:terminal/.dharma-terminal-state.json > terminal/.dharma-terminal-state.json`; leave the other two alone (S0 features own them).

## Step 1 — Orient

```bash
pwd                      # expect /Users/dhyana/dharma_helm_build
git log --oneline -3     # spec-package commits may sit on top of baseline a6ad97362
```

Verify lineage, not a literal HEAD: `git rev-parse --abbrev-ref HEAD` must print `helm/worldclass-20260612` AND `git merge-base --is-ancestor a6ad97362 HEAD` must exit 0. If either fails, stop and write what you found to `claude-progress.txt` instead of proceeding. (Spec-package and prior-session commits on top of the baseline are expected.)

## Step 2 — Typecheck baseline

```bash
cd /Users/dhyana/dharma_helm_build/terminal && bun run typecheck
```

Expect 0 errors. If errors appear, stop: record the exact errors in `claude-progress.txt` and end the session — the baseline characterization is broken and the operator decides.

## Step 3 — Characterize the failing test set (the failure-set ratchet baseline)

The suite is characterized-red in this checkout: 527 tests, 65 fail because ~250 hardcoded `"/Users/dhyana/dharma_swarm"` path literals at baseline (count-agnostic: the binding criterion is zero remaining) assume the original checkout path. F-001 (path hermeticity) fixes this later; tonight the 65 names ARE the baseline. Failure line format is `(fail) <suite> > <name> [<time>]`.

```bash
cd /Users/dhyana/dharma_helm_build/terminal
bun test 2>&1 | tee /tmp/helm-baseline-test.log | tail -4
grep -E '^\(fail\)' /tmp/helm-baseline-test.log \
  | sed -E 's/^\(fail\) //; s/ \[[0-9.]+m?s\]$//' \
  | sort -u > /Users/dhyana/dharma_helm_build/spec-forge/baseline-failures.txt
wc -l /Users/dhyana/dharma_helm_build/spec-forge/baseline-failures.txt
```

The file is a pure sorted list, one failing test name per line, no header — later sessions diff against it with `comm -13`. Expected count: 65 (verified 2026-06-12 on this exact checkout: `462 pass / 65 fail / 527 total`). If your count differs, record the actual names anyway and note the delta with the tail-4 evidence in `claude-progress.txt`.

## Step 4 — tmux boot-smoke

```bash
SESS=helm-smoke-$RANDOM; STATEDIR=$(mktemp -d)
tmux new-session -d -s $SESS -x 80 -y 24 \
  "cd /Users/dhyana/dharma_helm_build/terminal && COLORTERM=truecolor DHARMA_PYTHON=/nonexistent/python DHARMA_TERMINAL_STATE_DIR=$STATEDIR DHARMA_TERMINAL_SUPERVISOR_STATE_DIR=$STATEDIR bun run start"
sleep 4
tmux capture-pane -t $SESS -p
tmux kill-session -t $SESS
```

Green = non-empty frame containing "Dharma Terminal" or "backend offline, retrying". Empty or error frame = stop, record, end session.

## Step 5 — Truecolor pre-flight (gate for every overnight aesthetic grade)

Without this gate green, every aesthetic verdict tonight judges quantized colors. Three checks, results written to `spec-forge/truecolor-preflight.txt`:

```bash
{
  echo "host COLORTERM=$COLORTERM"                          # expect truecolor
  SESS=helm-tc-$RANDOM
  tmux new-session -d -s $SESS -x 80 -y 24 \
    "printf '\033[38;2;255;158;59mTRUECOLOR-PROBE\033[0m\n'; sleep 5"
  sleep 1
  echo "probe capture: $(tmux capture-pane -t $SESS -e -p | grep -m1 '38;2')"
  tmux kill-session -t $SESS
  echo "captured at: $(date -u +%Y-%m-%dT%H:%MZ) on baseline a6ad97362"
} | tee /Users/dhyana/dharma_helm_build/spec-forge/truecolor-preflight.txt
```

Green = COLORTERM is `truecolor` AND the probe capture line contains `38;2;255;158;59` (verified working on this host 2026-06-12). If the probe line is empty, the tmux pipeline strips RGB: record FAIL in the file and in `claude-progress.txt`, and end the session — the operator fixes tmux terminal-features before launch.

## Step 6 — Pre-theme golden frames (three sizes, plain + SGR)

```bash
mkdir -p /Users/dhyana/dharma_helm_build/terminal/tests/golden/pre-theme
for size in "80 24" "100 30" "120 40"; do
  set -- $size
  SESS=helm-golden-$1x$2; STATEDIR=$(mktemp -d)
  tmux kill-session -t $SESS 2>/dev/null
  tmux new-session -d -s $SESS -x $1 -y $2 \
    "cd /Users/dhyana/dharma_helm_build/terminal && COLORTERM=truecolor DHARMA_PYTHON=/nonexistent/python DHARMA_TERMINAL_STATE_DIR=$STATEDIR DHARMA_TERMINAL_SUPERVISOR_STATE_DIR=$STATEDIR bun run start"
  sleep 4
  tmux capture-pane -t $SESS -p  > /Users/dhyana/dharma_helm_build/terminal/tests/golden/pre-theme/${1}x${2}.txt
  tmux capture-pane -t $SESS -e -p > /Users/dhyana/dharma_helm_build/terminal/tests/golden/pre-theme/${1}x${2}.sgr.txt
  tmux kill-session -t $SESS
done
wc -l /Users/dhyana/dharma_helm_build/terminal/tests/golden/pre-theme/*.txt
```

All six files non-empty. These freeze the pre-theme appearance: structure-only commits (S0–S3) leave them unchanged under text diff; the theme migration (S4) intentionally changes them and triggers a post-theme re-capture with evaluator approval.

## Step 7 — Seed terminal/LESSONS/

Create `terminal/LESSONS/LESSONS.md` with exactly this content:

```
Read terminal/src/theme.ts before any UI code; never hardcode a hex outside theme.ts and ScenicStrip.tsx.

# LESSONS — append-only. One lesson per line: [date] [F-ID] lesson.
# Every coder session reads this file before implementing and appends anything the next session needs.
```

## Step 8 — Create claude-progress.txt

Create `/Users/dhyana/dharma_helm_build/claude-progress.txt` with the session-0 record. Entry format (used by all later sessions):

```
[2026-06-12THH:MMZ] S0-INIT complete
  evidence: typecheck 0 errors; bun test 462 pass / 65 fail / 527 total; baseline-failures.txt = <N> names;
            boot-smoke frame OK at 80x24; truecolor probe 38;2 captured; 6 golden files written
  files: spec-forge/baseline-failures.txt, spec-forge/truecolor-preflight.txt,
         terminal/LESSONS/LESSONS.md, terminal/tests/golden/pre-theme/*, claude-progress.txt
```

Fill in only numbers you observed in this session's tool output.

## Step 9 — Clean tree + initial commit

```bash
cd /Users/dhyana/dharma_helm_build
git show HEAD:terminal/.dharma-terminal-state.json > terminal/.dharma-terminal-state.json
git add spec-forge/baseline-failures.txt spec-forge/truecolor-preflight.txt \
        terminal/LESSONS terminal/tests/golden/pre-theme claude-progress.txt
git status --short    # only the adds above staged; bun.lock and .parked-fresh-node-modules stay untracked
git commit -m "helm S0-init: baseline characterization (65 red), pre-theme goldens, truecolor preflight, LESSONS seed"
git log --oneline -2
```

## Step 10 — Report

State what was verified, citing the command outputs from this session. The loop launches CODER sessions next; this session ends here.
