#!/usr/bin/env bash
set -euo pipefail

CANONICAL_REPOSITORY="AIKAGRYA/dharma_swarm"
EXPECTED_REPOSITORY_ID="1176966970"
EXPECTED_VISIBILITY="public"
EXPECTED_DEFAULT_BRANCH="main"
CANONICAL_URL="https://github.com/${CANONICAL_REPOSITORY}.git"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
REPAIR_ORIGIN=0

usage() {
  cat <<'EOF'
Usage: scripts/publish_canonical.sh [--repair-origin]

Verify that this checkout and the live GitHub repository both identify the
canonical public repository. By default this command is read-only. The
--repair-origin option permits only a local origin URL repair.
EOF
}

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repair-origin)
      [[ "${REPAIR_ORIGIN}" -eq 0 ]] || die "--repair-origin was provided more than once."
      REPAIR_ORIGIN=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage >&2
      die "Unknown argument: $1"
      ;;
  esac
  shift
done

command -v gh >/dev/null 2>&1 || die "GitHub CLI (gh) is not installed."
command -v git >/dev/null 2>&1 || die "git is not installed."

cd "${ROOT_DIR}"

if ! GIT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"; then
  die "${ROOT_DIR} is not a Git working tree."
fi
if ! GIT_ROOT="$(cd "${GIT_ROOT}" && pwd -P)"; then
  die "Unable to resolve the Git working-tree root."
fi
[[ "${GIT_ROOT}" == "${ROOT_DIR}" ]] || die \
  "Script root ${ROOT_DIR} does not match Git root ${GIT_ROOT}."

if ! gh auth status --hostname github.com >/dev/null 2>&1; then
  cat >&2 <<'EOF'
ERROR: GitHub authentication is not valid for github.com in this shell.
Authenticate with:
  env -u GITHUB_TOKEN -u GH_TOKEN gh auth login --hostname github.com --git-protocol https --web
EOF
  exit 1
fi

if ! LIVE_METADATA="$(
  gh api --method GET "repos/${CANONICAL_REPOSITORY}" \
    --jq '[.full_name, (.id | tostring), (.private | tostring), .visibility, .default_branch] | @tsv'
)"; then
  die "Unable to read live metadata for ${CANONICAL_REPOSITORY}."
fi

LIVE_FULL_NAME=""
LIVE_ID=""
LIVE_PRIVATE=""
LIVE_VISIBILITY=""
LIVE_DEFAULT_BRANCH=""
LIVE_EXTRA=""
IFS=$'\t' read -r \
  LIVE_FULL_NAME LIVE_ID LIVE_PRIVATE LIVE_VISIBILITY LIVE_DEFAULT_BRANCH LIVE_EXTRA \
  <<< "${LIVE_METADATA}"

if [[ -n "${LIVE_EXTRA}" || "${LIVE_METADATA}" == *$'\n'* ]]; then
  die "GitHub returned malformed repository identity metadata."
fi
[[ "${LIVE_FULL_NAME}" == "${CANONICAL_REPOSITORY}" ]] || die \
  "Live full_name mismatch: expected ${CANONICAL_REPOSITORY}, observed ${LIVE_FULL_NAME:-<empty>}."
[[ "${LIVE_ID}" == "${EXPECTED_REPOSITORY_ID}" ]] || die \
  "Live repository ID mismatch: expected ${EXPECTED_REPOSITORY_ID}, observed ${LIVE_ID:-<empty>}."
[[ "${LIVE_PRIVATE}" == "false" ]] || die \
  "Live repository is not public: private=${LIVE_PRIVATE:-<empty>}."
[[ "${LIVE_VISIBILITY}" == "${EXPECTED_VISIBILITY}" ]] || die \
  "Live visibility mismatch: expected ${EXPECTED_VISIBILITY}, observed ${LIVE_VISIBILITY:-<empty>}."
[[ "${LIVE_DEFAULT_BRANCH}" == "${EXPECTED_DEFAULT_BRANCH}" ]] || die \
  "Live default branch mismatch: expected ${EXPECTED_DEFAULT_BRANCH}, observed ${LIVE_DEFAULT_BRANCH:-<empty>}."

RAW_ORIGIN_URL=""
RAW_ORIGIN_PRESENT=0
read_raw_origin() {
  local status

  if RAW_ORIGIN_URL="$(git config --local --get remote.origin.url 2>/dev/null)"; then
    RAW_ORIGIN_PRESENT=1
    return 0
  else
    status=$?
  fi
  RAW_ORIGIN_URL=""
  RAW_ORIGIN_PRESENT=0
  [[ "${status}" -eq 1 ]] && return 0
  return "${status}"
}

if ! read_raw_origin; then
  die "Unable to inspect the raw local remote.origin.url setting."
fi
if [[ "${RAW_ORIGIN_PRESENT}" -eq 1 ]] && \
   [[ -z "${RAW_ORIGIN_URL}" || "${RAW_ORIGIN_URL}" == *$'\n'* ]]; then
  die "The raw local remote.origin.url setting is malformed."
fi

if [[ "${RAW_ORIGIN_PRESENT}" -eq 0 ]]; then
  if [[ "${REPAIR_ORIGIN}" -eq 0 ]]; then
    printf 'ERROR: Local origin URL is not configured.\n' >&2
    printf 'Safe repair command:\n' >&2
    printf '  git remote add origin %s\n' "${CANONICAL_URL}" >&2
    exit 1
  fi
  if ! git remote add origin "${CANONICAL_URL}"; then
    die "Unable to add the canonical local origin URL."
  fi
elif [[ "${RAW_ORIGIN_URL}" != "${CANONICAL_URL}" ]]; then
  if [[ "${REPAIR_ORIGIN}" -eq 0 ]]; then
    printf 'ERROR: Raw local origin URL mismatch.\n' >&2
    printf 'Observed raw origin: %q\n' "${RAW_ORIGIN_URL}" >&2
    printf 'Expected raw origin: %s\n' "${CANONICAL_URL}" >&2
    printf 'Safe repair command:\n' >&2
    printf '  git remote set-url origin %s\n' "${CANONICAL_URL}" >&2
    exit 1
  fi
  if ! git remote set-url origin "${CANONICAL_URL}"; then
    die "Unable to repair the local origin URL."
  fi
fi

if ! read_raw_origin; then
  die "Unable to re-read the raw local remote.origin.url setting."
fi
[[ "${RAW_ORIGIN_PRESENT}" -eq 1 && "${RAW_ORIGIN_URL}" == "${CANONICAL_URL}" ]] || die \
  "Raw local origin URL is not canonical after verification or repair."

if ! REMOTE_MAIN_RECORD="$(
  git ls-remote --exit-code "${CANONICAL_URL}" "refs/heads/${EXPECTED_DEFAULT_BRANCH}"
)"; then
  die "Unable to verify refs/heads/${EXPECTED_DEFAULT_BRANCH} at ${CANONICAL_URL}."
fi
if [[ -z "${REMOTE_MAIN_RECORD}" || "${REMOTE_MAIN_RECORD}" == *$'\n'* ]]; then
  die "Remote main verification returned an empty or ambiguous result."
fi

REMOTE_MAIN_SHA=""
REMOTE_MAIN_REF=""
REMOTE_MAIN_EXTRA=""
IFS=$' \t' read -r REMOTE_MAIN_SHA REMOTE_MAIN_REF REMOTE_MAIN_EXTRA \
  <<< "${REMOTE_MAIN_RECORD}"
case "${REMOTE_MAIN_SHA}" in
  ''|*[!0-9a-fA-F]*) die "Remote main verification returned an invalid object ID." ;;
esac
if [[ "${#REMOTE_MAIN_SHA}" -ne 40 && "${#REMOTE_MAIN_SHA}" -ne 64 ]]; then
  die "Remote main verification returned an object ID with an invalid length."
fi
[[ "${REMOTE_MAIN_REF}" == "refs/heads/${EXPECTED_DEFAULT_BRANCH}" && \
   -z "${REMOTE_MAIN_EXTRA}" ]] || die \
  "Remote main verification returned an unexpected ref record."

printf 'Canonical repository identity verified: %s (ID %s, public, default %s).\n' \
  "${CANONICAL_REPOSITORY}" "${EXPECTED_REPOSITORY_ID}" "${EXPECTED_DEFAULT_BRANCH}"
printf 'Raw origin verified: %s\n' "${CANONICAL_URL}"
printf 'Remote main verified at: %s\n' "${REMOTE_MAIN_SHA}"
