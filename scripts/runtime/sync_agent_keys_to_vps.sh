#!/usr/bin/env bash
# Safely MERGE the canonical dharma_swarm model/API key store to a VPS.
#
# SECURITY CONTRACT:
# - Never prints key values.
# - Requires an explicit host.
# - Refuses known exposed/high-risk hosts unless --allow-risky-host is passed.
# - Backs up any remote ~/.dharma/agent_keys.env with a timestamp before writing.
# - Preserves remote-only variables (Telegram/gateway/proxy config, host-local auth).
# - Layers local canonical vars on top when names collide (Mac/dkeys is the source of truth).
# - Verifies by VARIABLE NAMES + mode 0600, not by file SHA (merged files should differ).
# - Dry-run is read-only on the remote host.
# - Writes a redacted movement ledger for apply runs.
set -euo pipefail
umask 077

usage() {
  cat >&2 <<'USAGE'
Usage:
  scripts/runtime/sync_agent_keys_to_vps.sh --host <ssh-host> [--remote-path ~/.dharma/agent_keys.env] [--receipt-dir ~/.dharma/security/secret_sync_receipts] [--allow-risky-host] [--operator-approved] [--dry-run]

Examples:
  scripts/runtime/sync_agent_keys_to_vps.sh --host agni --dry-run
  scripts/runtime/sync_agent_keys_to_vps.sh --host agni --operator-approved

What it does:
  - canonical local source: ~/.dharma/agent_keys.env
  - dry-run prints variable NAMES only: local-only, remote-only, overlap
  - dry-run does not create remote directories or files
  - apply preserves remote-only names and updates/adds local names
  - apply requires --operator-approved and writes a redacted ledger receipt
  - values are never printed

What it does NOT do:
  - does not copy OAuth stores (~/.codex/auth.json, ~/.qwen, macOS Keychain)
  - does not install model weights
  - refuses known exposed hosts such as meghadharma unless explicitly overridden
USAGE
}

HOST=""
REMOTE_PATH='~/.dharma/agent_keys.env'
RECEIPT_DIR="${HOME}/.dharma/security/secret_sync_receipts"
ALLOW_RISKY=0
OPERATOR_APPROVED=0
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) HOST="${2:-}"; shift 2 ;;
    --remote-path) REMOTE_PATH="${2:-}"; shift 2 ;;
    --receipt-dir) RECEIPT_DIR="${2:-}"; shift 2 ;;
    --allow-risky-host) ALLOW_RISKY=1; shift ;;
    --operator-approved) OPERATOR_APPROVED=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown arg: $1" >&2; usage; exit 2 ;;
  esac
done

if [[ "${RECEIPT_DIR}" == "~/"* ]]; then
  RECEIPT_DIR="${HOME}/${RECEIPT_DIR#"~/"}"
fi

if [[ -z "${HOST}" ]]; then
  echo "ERROR: --host is required" >&2
  usage
  exit 2
fi

if [[ "${HOST}" =~ [^A-Za-z0-9._@:-] ]]; then
  echo "ERROR: --host contains unsupported characters" >&2
  exit 2
fi

if [[ "${REMOTE_PATH}" =~ [^A-Za-z0-9._/~:-] ]]; then
  echo "ERROR: --remote-path contains unsupported characters" >&2
  exit 2
fi

case "${HOST}" in
  meghadharma|meghadharma_cloud|178.128.87.170)
    if [[ "${ALLOW_RISKY}" != "1" ]]; then
      echo "REFUSING: ${HOST} is a known high-risk/exposed host. Use --allow-risky-host only after remediation." >&2
      exit 3
    fi
    ;;
esac

if [[ "${DRY_RUN}" != "1" && "${OPERATOR_APPROVED}" != "1" ]]; then
  echo "REFUSING: apply mode requires --operator-approved" >&2
  exit 3
fi

LOCAL="${HOME}/.dharma/agent_keys.env"
if [[ ! -f "${LOCAL}" ]]; then
  echo "ERROR: local key file missing: ${LOCAL}" >&2
  exit 4
fi
if [[ "$(stat -f '%Lp' "${LOCAL}")" != "600" ]]; then
  echo "ERROR: local key file must be mode 0600: ${LOCAL}" >&2
  exit 5
fi

REMOTE_DIR="$(dirname "${REMOTE_PATH}")"
TMP_LOCAL_NAMES="$(mktemp)"
TMP_REMOTE_NAMES="$(mktemp)"
TMP_MERGED="$(mktemp)"
TMP_REMOTE_NAMES_AFTER="$(mktemp)"
trap 'rm -f "${TMP_LOCAL_NAMES}" "${TMP_REMOTE_NAMES}" "${TMP_MERGED}" "${TMP_REMOTE_NAMES_AFTER}"' EXIT

_extract_names() {
  grep -oE '^[[:space:]]*(export[[:space:]]+)?[A-Z0-9_]+=' "$1" \
    | sed -E 's/^[[:space:]]*(export[[:space:]]+)?//; s/=$//' \
    | sort -u
}

_extract_names "${LOCAL}" > "${TMP_LOCAL_NAMES}"
LOCAL_COUNT="$(wc -l < "${TMP_LOCAL_NAMES}" | tr -d ' ')"

ssh -o BatchMode=yes -o ConnectTimeout=10 "${HOST}" \
  "set -e; if [ -f ${REMOTE_PATH} ]; then grep -oE '^[[:space:]]*(export[[:space:]]+)?[A-Z0-9_]+=' ${REMOTE_PATH} | sed -E 's/^[[:space:]]*(export[[:space:]]+)?//; s/=\$//' | sort -u; fi" \
  > "${TMP_REMOTE_NAMES}"
REMOTE_COUNT="$(wc -l < "${TMP_REMOTE_NAMES}" | tr -d ' ')"

echo "sync-agent-keys: host=${HOST}"
echo "sync-agent-keys: local=${LOCAL} names=${LOCAL_COUNT}"
echo "sync-agent-keys: remote=${REMOTE_PATH} names=${REMOTE_COUNT}"
echo "sync-agent-keys: values will NOT be printed"
echo "sync-agent-keys: names only preview follows"

echo "--- local-only names (will be added) ---"
comm -23 "${TMP_LOCAL_NAMES}" "${TMP_REMOTE_NAMES}" || true
echo "--- remote-only names (will be preserved) ---"
comm -13 "${TMP_LOCAL_NAMES}" "${TMP_REMOTE_NAMES}" || true
echo "--- overlapping names (local value will win) ---"
comm -12 "${TMP_LOCAL_NAMES}" "${TMP_REMOTE_NAMES}" || true

if [[ "${DRY_RUN}" == "1" ]]; then
  ssh -o BatchMode=yes -o ConnectTimeout=10 "${HOST}" \
    "set -e; echo remote_host=\$(hostname); echo remote_user=\$(id -un); if [ -f ${REMOTE_PATH} ]; then stat -c '%A %U:%G %s %n' ${REMOTE_PATH}; else echo remote_current=missing; fi"
  echo "DRY_RUN: no copy performed"
  exit 0
fi

REMOTE_COPY="$(mktemp)"
trap 'rm -f "${TMP_LOCAL_NAMES}" "${TMP_REMOTE_NAMES}" "${TMP_MERGED}" "${TMP_REMOTE_NAMES_AFTER}" "${REMOTE_COPY}"' EXIT
if ssh -o BatchMode=yes -o ConnectTimeout=10 "${HOST}" "test -f ${REMOTE_PATH}"; then
  scp -q "${HOST}:${REMOTE_PATH}" "${REMOTE_COPY}"
else
  : > "${REMOTE_COPY}"
fi

python3 - "${REMOTE_COPY}" "${LOCAL}" "${TMP_MERGED}" <<'PY'
from pathlib import Path
import re, sys
remote = Path(sys.argv[1])
local = Path(sys.argv[2])
out = Path(sys.argv[3])
rx = re.compile(r'^\s*(?:export\s+)?([A-Z0-9_]+)=')

def parse(path):
    order=[]; values={}; passthrough=[]
    if not path.exists():
        return order, values, passthrough
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        m=rx.match(line)
        if m:
            name=m.group(1)
            if name not in values:
                order.append(name)
            values[name]=line
        else:
            passthrough.append(line)
    return order, values, passthrough

r_order, r_values, r_pass = parse(remote)
l_order, l_values, l_pass = parse(local)
merged=[]
seen=set()
merged.append('# ~/.dharma/agent_keys.env - merged by sync_agent_keys_to_vps.sh')
merged.append('# Remote-only variables preserved; local canonical variables layered on top by name.')
for line in r_pass:
    if line.strip() and not line.lstrip().startswith('#'):
        continue
    if line not in merged:
        merged.append(line)
for name in r_order + l_order:
    if name in seen:
        continue
    seen.add(name)
    merged.append(l_values.get(name, r_values.get(name, '')))
out.write_text('\n'.join(merged).rstrip() + '\n', encoding='utf-8')
PY

MERGED_NAMES="$(mktemp)"
trap 'rm -f "${TMP_LOCAL_NAMES}" "${TMP_REMOTE_NAMES}" "${TMP_MERGED}" "${TMP_REMOTE_NAMES_AFTER}" "${REMOTE_COPY}" "${MERGED_NAMES}"' EXIT
_extract_names "${TMP_MERGED}" > "${MERGED_NAMES}"
MISSING_AFTER="$(comm -23 "${TMP_LOCAL_NAMES}" "${MERGED_NAMES}" || true)"
if [[ -n "${MISSING_AFTER}" ]]; then
  echo "ERROR: merge output missing local names:" >&2
  echo "${MISSING_AFTER}" >&2
  exit 6
fi

TMP_REMOTE_NAME=".agent_keys.env.merged.$$"
ssh -o BatchMode=yes -o ConnectTimeout=10 "${HOST}" "set -e; umask 077; mkdir -p ${REMOTE_DIR}; chmod 700 ${REMOTE_DIR}"
scp -q "${TMP_MERGED}" "${HOST}:${REMOTE_DIR}/${TMP_REMOTE_NAME}"
ssh -o BatchMode=yes -o ConnectTimeout=10 "${HOST}" \
  "set -e; umask 077; if [ -f ${REMOTE_PATH} ]; then cp -p ${REMOTE_PATH} ${REMOTE_PATH}.bak.\$(date -u +%Y%m%dT%H%M%SZ); fi; mv ${REMOTE_DIR}/${TMP_REMOTE_NAME} ${REMOTE_PATH}; chmod 600 ${REMOTE_PATH}; stat -c '%A %U:%G %s %n' ${REMOTE_PATH}"

ssh -o BatchMode=yes -o ConnectTimeout=10 "${HOST}" \
  "grep -oE '^[[:space:]]*(export[[:space:]]+)?[A-Z0-9_]+=' ${REMOTE_PATH} | sed -E 's/^[[:space:]]*(export[[:space:]]+)?//; s/=\$//' | sort -u" \
  > "${TMP_REMOTE_NAMES_AFTER}"

MISSING_REMOTE="$(comm -23 "${TMP_LOCAL_NAMES}" "${TMP_REMOTE_NAMES_AFTER}" || true)"
if [[ -n "${MISSING_REMOTE}" ]]; then
  echo "ERROR: remote after-merge missing local names:" >&2
  echo "${MISSING_REMOTE}" >&2
  exit 7
fi

RECEIPT_TS="$(date -u +%Y%m%dT%H%M%SZ)"
RECEIPT_HOST="$(printf '%s' "${HOST}" | tr -c 'A-Za-z0-9_.-' '_')"
RECEIPT_PATH="${RECEIPT_DIR}/${RECEIPT_TS}-${RECEIPT_HOST}-agent_keys.redacted.json"
mkdir -p "${RECEIPT_DIR}"
python3 - "${RECEIPT_PATH}" "${HOST}" "${LOCAL}" "${REMOTE_PATH}" "${LOCAL_COUNT}" "${OPERATOR_APPROVED}" "${TMP_LOCAL_NAMES}" "${TMP_REMOTE_NAMES}" "${TMP_REMOTE_NAMES_AFTER}" <<'PY'
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

receipt_path = Path(sys.argv[1]).expanduser()
host = sys.argv[2]
source = sys.argv[3]
destination = sys.argv[4]
names_count = int(sys.argv[5])
operator_approved = sys.argv[6] == "1"
local_names = set(Path(sys.argv[7]).read_text(encoding="utf-8").splitlines())
before_names = set(Path(sys.argv[8]).read_text(encoding="utf-8").splitlines())
after_names = set(Path(sys.argv[9]).read_text(encoding="utf-8").splitlines())

provider_keys = {
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_AI_API_KEY",
    "GROQ_API_KEY",
    "NVIDIA_API_KEY",
    "NGC_API_KEY",
    "OPENROUTER_API_KEY",
    "SAKANA_API_KEY",
}

payload = {
    "schema": "dharma.secret_sync_receipt.redacted.v1",
    "timestamp": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    "host": host,
    "source": source,
    "destination": destination,
    "names_count": names_count,
    "remote_names_before_count": len(before_names),
    "remote_names_after_count": len(after_names),
    "local_only_added": sorted(local_names - before_names),
    "remote_only_preserved": sorted(before_names - local_names),
    "overlap_names": sorted(local_names & before_names),
    "missing_after": sorted(local_names - after_names),
    "mode": "0600",
    "values_printed": False,
    "operator_approved": operator_approved,
    "overlap_policy": "local_wins",
    "verified_provider_names": sorted(provider_keys & after_names),
}
receipt_path.parent.mkdir(parents=True, exist_ok=True)
receipt_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
chmod 600 "${RECEIPT_PATH}"

echo "sync-agent-keys: OK merged; all ${LOCAL_COUNT} local names present on remote; remote-only names preserved"
echo "sync-agent-keys: redacted receipt=${RECEIPT_PATH}"
