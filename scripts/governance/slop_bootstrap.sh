#!/usr/bin/env bash
# slop_bootstrap.sh — make slop-verify reflexive.
#
# Idempotent. Safe to re-run. Skips work that's already done.
#
# Installs:
#   - Python detectors (vulture, ai-slop-detector, sloppylint, semgrep, grimp)
#   - System tools where available (npm-global: knip, jscpd, dependency-cruiser, oxlint, fallow)
#   - Project node_modules for dashboard/, terminal/, terminal-v2/, desktop-shell/, codex_skills/
#
# Wires:
#   - Pre-commit hook (slop-verify on changed files, fast lane <5s)
#   - Optional cron entry for nightly full scan
#
# Usage:
#   bash scripts/governance/slop_bootstrap.sh [--no-npm] [--no-node-modules] [--with-cron]

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

NO_NPM=0
NO_NODE_MODULES=0
WITH_CRON=0
for arg in "$@"; do
  case "$arg" in
    --no-npm) NO_NPM=1 ;;
    --no-node-modules) NO_NODE_MODULES=1 ;;
    --with-cron) WITH_CRON=1 ;;
    --help|-h)
      grep '^#' "$0" | head -25
      exit 0
      ;;
  esac
done

log() { printf '\033[1;36m[slop-bootstrap]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n' "$*"; }
ok() { printf '\033[1;32m[ok]\033[0m %s\n' "$*"; }

ensure_python() {
  local pkg="$1"
  local import_name="${2:-$1}"
  if python3 -c "import $import_name" 2>/dev/null; then
    ok "python: $pkg already importable"
  elif command -v "$pkg" >/dev/null 2>&1; then
    ok "python: $pkg binary already available"
  else
    log "installing python: $pkg"
    pip install --quiet "$pkg" || warn "$pkg install failed; continuing"
  fi
}

ensure_npm_global() {
  local pkg="$1"
  local bin="${2:-$1}"
  if command -v "$bin" >/dev/null 2>&1; then
    ok "npm-global: $bin already on PATH"
  elif [ "$NO_NPM" -eq 1 ]; then
    warn "skipping npm install of $pkg (--no-npm)"
  else
    log "installing npm-global: $pkg"
    npm install --silent --global "$pkg" || warn "$pkg install failed; continuing"
  fi
}

ensure_project_node_modules() {
  local project="$1"
  if [ ! -f "$project/package.json" ]; then return; fi
  if [ -d "$project/node_modules" ]; then
    ok "node_modules: $project already installed"
    return
  fi
  if [ "$NO_NODE_MODULES" -eq 1 ]; then
    warn "skipping npm install in $project (--no-node-modules)"
    return
  fi
  log "installing node_modules in $project"
  (cd "$project" && npm install --silent) || warn "npm install failed in $project; continuing"
}

# 1. Python detector tier
log "ensuring Python detectors"
ensure_python vulture
ensure_python ai-slop-detector ai_slop_detector
ensure_python sloppylint
ensure_python grimp
ensure_python semgrep
ensure_python pip-audit

# 2. JS/TS detector tier
log "ensuring JS/TS detectors (npm-global)"
ensure_npm_global knip
ensure_npm_global jscpd
ensure_npm_global dependency-cruiser depcruise
ensure_npm_global oxlint
ensure_npm_global fallow

# 3. Per-project node_modules (so tsc/eslint adapters can run)
log "ensuring per-project node_modules"
for project in dashboard terminal terminal-v2 desktop-shell codex_skills; do
  ensure_project_node_modules "$project"
done

# 4. Pre-commit hook check (if pre-commit is installed)
if command -v pre-commit >/dev/null 2>&1; then
  if grep -q "slop-verify" .pre-commit-config.yaml 2>/dev/null; then
    ok "pre-commit: slop-verify hook already present"
  else
    warn "pre-commit hook not present in .pre-commit-config.yaml — add the slop-verify block manually"
  fi
  log "running pre-commit install"
  pre-commit install --install-hooks >/dev/null 2>&1 || warn "pre-commit install had errors"
else
  warn "pre-commit not installed; skipping hook setup"
fi

# 5. Optional cron entry
if [ "$WITH_CRON" -eq 1 ]; then
  log "writing nightly cron entry to ~/.dharma/cron/jobs.json"
  python3 - "$REPO_ROOT" <<'PY'
import json, os, sys
from pathlib import Path
repo = Path(sys.argv[1])
cron_dir = Path.home() / ".dharma" / "cron"
cron_dir.mkdir(parents=True, exist_ok=True)
jobs_file = cron_dir / "jobs.json"
jobs = []
if jobs_file.exists():
    try:
        jobs = json.loads(jobs_file.read_text())
        if not isinstance(jobs, list): jobs = []
    except Exception: jobs = []
job_id = "slop-verify-nightly"
jobs = [j for j in jobs if isinstance(j, dict) and j.get("id") != job_id]
jobs.append({
    "id": job_id,
    "cron": "0 3 * * *",
    "cwd": str(repo),
    "cmd": ["python3", "scripts/governance/slop_verify.py", str(repo / "dharma_swarm"), "--mode", "nightly"],
    "description": "Nightly full slop verification scan",
})
jobs_file.write_text(json.dumps(jobs, indent=2))
print(f"  cron job written: {jobs_file}")
PY
fi

# 6. Sanity scan
log "running sanity scan (vulture only, fastest detector)"
python3 scripts/governance/slop_verify.py dharma_swarm/slop --mode pre-commit --no-ledger --detector vulture >/dev/null 2>&1 \
  && ok "sanity scan succeeded — slop-verify is wired" \
  || warn "sanity scan failed; check output of: python3 scripts/governance/slop_verify.py dharma_swarm/slop --mode pre-commit"

ok "bootstrap complete"
