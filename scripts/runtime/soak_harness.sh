#!/usr/bin/env bash
# soak_harness.sh — orchestrates a versioned daemon soak on a single host.
# Mac-pulls-only topology (Bali NAT): the VPS NEVER pushes; the Mac initiates
# all rsync. This script is meant to run ON THE MAC and reach out to the VPS.
#
# --dry-run prints every command and executes NONE. Default is dry-run for
# safety; pass --execute to actually run.
set -euo pipefail

MODE="dry-run"
VPS_HOST="${DHARMA_VPS_HOST:-agni}"
STATE_DIR="${DHARMA_STATE_DIR:-$HOME/.dharma}"
REMOTE_METRICS="${VPS_HOST}:~/.dharma/evolution/version_metrics/"
LOCAL_METRICS="${STATE_DIR}/evolution/version_metrics/"

if [ -z "${BUILD_ID:-}" ]; then
  BUILD_ID="$(python3 -c 'from dharma_swarm.versioning.daemon_version import daemon_version; print(daemon_version())')"
fi
if [ -z "${BUILD_SHA:-}" ]; then
  BUILD_SHA="$(python3 -c 'from dharma_swarm.versioning.daemon_version import git_short_sha; print(git_short_sha())')"
fi
if [ -z "${BUILD_TAG:-}" ]; then
  BUILD_TAG="$(printf '%s' "$BUILD_ID" | tr '+/' '._' | tr -cd 'A-Za-z0-9_.-')"
fi

for arg in "$@"; do
  case "$arg" in
    --execute) MODE="execute" ;;
    --dry-run) MODE="dry-run" ;;
    *) echo "unknown arg: $arg" >&2; exit 2 ;;
  esac
done

run() {
  echo "+ $*"
  if [ "$MODE" = "execute" ]; then
    "$@"
  fi
}

echo "=== dharma daemon soak harness (mode=$MODE, build_id=$BUILD_ID) ==="
echo "docker_tag=$BUILD_TAG build_sha=$BUILD_SHA"
echo "--- 1. build the versioned image on the VPS (operator-initiated) ---"
run ssh "$VPS_HOST" "cd ~/dharma_swarm && BUILD_ID=$BUILD_ID BUILD_SHA=$BUILD_SHA BUILD_TAG=$BUILD_TAG docker compose -f deploy/daemon/compose.daemon.yml up -d --build"

echo "--- 2. confirm liveness (depends on H1+H2 non-blocking /health) ---"
run ssh "$VPS_HOST" "curl -fsm1 http://localhost:7433/health"

echo "--- 3. let it soak (>= 12h per gate SOAK_MIN); no action here ---"

echo "--- 4. Mac PULLS the per-version metrics (NAT-safe, Mac initiates) ---"
run mkdir -p "$LOCAL_METRICS"
run rsync -avz "$REMOTE_METRICS" "$LOCAL_METRICS"

echo "--- 5. run the recommend-only gate locally on the Mac ---"
run python3 -c "from dharma_swarm.versioning.promote_gate import VersionPromotionGate; print('gate import ok')"

echo "=== done (mode=$MODE) ==="
