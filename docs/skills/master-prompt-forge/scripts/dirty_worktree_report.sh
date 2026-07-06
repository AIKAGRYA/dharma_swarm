#!/usr/bin/env bash
# Read-only inventory of a git repo's workspace state, for use before any
# cleanup/hygiene decision. Never writes, stages, stashes, or deletes
# anything. Usage: dirty_worktree_report.sh [path-to-repo]  (defaults to .)
set -euo pipefail

target="${1:-.}"

if ! repo_root="$(git -C "$target" rev-parse --show-toplevel 2>/dev/null)"; then
    echo "Not a git repository: $target" >&2
    exit 1
fi

echo "== Repo root =="
echo "$repo_root"

echo
echo "== Branch / upstream =="
branch="$(git -C "$repo_root" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "(detached HEAD)")"
echo "branch: $branch"
upstream="$(git -C "$repo_root" rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null || echo "(no upstream)")"
echo "upstream: $upstream"

echo
echo "== Worktrees =="
git -C "$repo_root" worktree list

echo
echo "== Dirty state =="
dirty_count="$(git -C "$repo_root" status --porcelain | wc -l | tr -d ' ')"
echo "modified/untracked file count: $dirty_count"
if [ "$dirty_count" -gt 0 ] && [ "$dirty_count" -le 20 ]; then
    git -C "$repo_root" status --short
elif [ "$dirty_count" -gt 20 ]; then
    echo "(more than 20 entries — showing status by top-level directory)"
    git -C "$repo_root" status --porcelain | awk '{print $2}' | cut -d/ -f1 | sort | uniq -c | sort -rn
fi

echo
echo "== Lockfiles / dependency manager =="
for f in package-lock.json pnpm-lock.yaml yarn.lock poetry.lock Pipfile.lock \
         Cargo.lock go.sum composer.lock Gemfile.lock uv.lock; do
    if [ -f "$repo_root/$f" ]; then
        echo "found: $f"
    fi
done

echo
echo "== Generated / vendor / cache directories present =="
for d in node_modules dist build .venv venv __pycache__ target .next .turbo \
         .parcel-cache vendor .tox; do
    if [ -d "$repo_root/$d" ]; then
        echo "present: $d"
    fi
done

echo
echo "== Test/build entry points (informational — none executed) =="
for f in Makefile package.json pyproject.toml Cargo.toml go.mod; do
    if [ -f "$repo_root/$f" ]; then
        echo "found: $f"
    fi
done

echo
echo "(read-only report complete — nothing was modified, staged, or deleted)"
