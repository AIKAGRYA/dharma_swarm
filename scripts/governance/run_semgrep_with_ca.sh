#!/usr/bin/env bash
set -euo pipefail

ca_bundle=""

if [[ -n "${SSL_CERT_FILE:-}" && -s "${SSL_CERT_FILE}" ]]; then
  ca_bundle="${SSL_CERT_FILE}"
fi

if [[ -z "${ca_bundle}" ]]; then
  certifi_bundle="$(
    python3 -c 'import certifi; print(certifi.where())' 2>/dev/null || true
  )"
  if [[ -n "${certifi_bundle}" && -s "${certifi_bundle}" ]]; then
    ca_bundle="${certifi_bundle}"
  fi
fi

if [[ -z "${ca_bundle}" ]]; then
  python_ssl_bundle="$(
    python3 -c 'import ssl; print(ssl.get_default_verify_paths().cafile or "")' 2>/dev/null || true
  )"
  if [[ -n "${python_ssl_bundle}" && -s "${python_ssl_bundle}" ]]; then
    ca_bundle="${python_ssl_bundle}"
  fi
fi

if [[ -z "${ca_bundle}" ]]; then
  for candidate in \
    /opt/homebrew/etc/ca-certificates/cert.pem \
    /opt/homebrew/etc/openssl@3/cert.pem \
    /usr/local/etc/ca-certificates/cert.pem \
    /usr/local/etc/openssl@3/cert.pem \
    /usr/local/etc/openssl/cert.pem \
    /etc/ssl/cert.pem \
    /etc/ssl/certs/ca-certificates.crt \
    /etc/pki/tls/certs/ca-bundle.crt \
    /etc/ca-certificates/extracted/tls-ca-bundle.pem; do
    if [[ -s "${candidate}" ]]; then
      ca_bundle="${candidate}"
      break
    fi
  done
fi

if [[ -n "${ca_bundle}" ]]; then
  export SSL_CERT_FILE="${ca_bundle}"
  export REQUESTS_CA_BUNDLE="${ca_bundle}"
  export CURL_CA_BUNDLE="${ca_bundle}"
fi

export SEMGREP_SEND_METRICS=off

args=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --config)
      if [[ "${2:-}" == ".semgrep" ]]; then
        args+=(--config .semgrep/dharma-anti-slop.yml --config .semgrep/security.yml)
        shift 2
      else
        args+=("$1")
        shift
        if [[ $# -gt 0 ]]; then
          args+=("$1")
          shift
        fi
      fi
      ;;
    --config=.semgrep)
      args+=(--config .semgrep/dharma-anti-slop.yml --config .semgrep/security.yml)
      shift
      ;;
    *)
      args+=("$1")
      shift
      ;;
  esac
done

# WP-0C1 (TIT-004): required scans fail closed. A missing or wrong-version
# scanner is a named nonzero failure, never a green skip. Advisory callers
# opt out explicitly with DHARMA_SEMGREP_ALLOW_MISSING=1; the version pin is
# enforced only when DHARMA_SEMGREP_EXPECTED_VERSION is set (the Makefile
# required target pins the ratified 1.168.0; the CI container carries its
# own image pin). DHARMA_SEMGREP_WALLCLOCK bounds both version probing and scan.
sem_bin="${DHARMA_SEMGREP_BIN:-semgrep}"
if ! command -v "${sem_bin}" &>/dev/null; then
  if [[ "${DHARMA_SEMGREP_ALLOW_MISSING:-}" == "1" ]]; then
    echo "SEMGREP_SKIPPED: '${sem_bin}' not found on PATH — advisory scan skipped by DHARMA_SEMGREP_ALLOW_MISSING=1" >&2
    exit 0
  fi
  echo "SEMGREP_MISSING: '${sem_bin}' not found on PATH — required scan cannot run (install: pip install \"semgrep==${DHARMA_SEMGREP_EXPECTED_VERSION:-1.168.0}\")" >&2
  exit 2
fi

# Use Python's cross-platform subprocess timeout rather than GNU `timeout`.
# macOS does not ship coreutils timeout, and falling back to an unbounded exec
# would recreate the exact hang/false-green class this packet is meant to close.
if ! command -v python3 &>/dev/null; then
  echo "SEMGREP_TIMEOUT_RUNNER_MISSING: python3 is required to enforce the scan wall clock" >&2
  exit 2
fi
wallclock="${DHARMA_SEMGREP_WALLCLOCK:-900}"
expected="${DHARMA_SEMGREP_EXPECTED_VERSION:-}"
exec python3 - "${wallclock}" "${expected}" "${sem_bin}" "${args[@]}" <<'PY'
import subprocess
import sys

raw_wallclock = sys.argv[1]
expected = sys.argv[2]
command = sys.argv[3:]
try:
    wallclock = float(raw_wallclock)
except ValueError:
    print(
        f"SEMGREP_TIMEOUT_CONFIG_INVALID: DHARMA_SEMGREP_WALLCLOCK={raw_wallclock!r} "
        "must be a positive number",
        file=sys.stderr,
    )
    raise SystemExit(2)
if wallclock <= 0:
    print(
        f"SEMGREP_TIMEOUT_CONFIG_INVALID: DHARMA_SEMGREP_WALLCLOCK={raw_wallclock!r} "
        "must be a positive number",
        file=sys.stderr,
    )
    raise SystemExit(2)

if expected:
    version_timeout = min(wallclock, 30.0)
    try:
        version_proc = subprocess.run(
            [command[0], "--version"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=version_timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        print(
            f"SEMGREP_VERSION_TIMEOUT: version probe exceeded {version_timeout:g}s "
            "wall clock",
            file=sys.stderr,
        )
        raise SystemExit(2)
    first_line = version_proc.stdout.splitlines()[0] if version_proc.stdout else ""
    found = "".join(first_line.split())
    if version_proc.returncode != 0 or found != expected:
        print(
            f"SEMGREP_VERSION_MISMATCH: found {found or 'unknown'!r}, require "
            f"{expected!r} (ratified pin; install: pip install \"semgrep=={expected}\")",
            file=sys.stderr,
        )
        raise SystemExit(2)

try:
    proc = subprocess.run(
        command,
        stdin=subprocess.DEVNULL,
        timeout=wallclock,
        check=False,
    )
except subprocess.TimeoutExpired:
    print(
        f"SEMGREP_TIMEOUT: scan exceeded {raw_wallclock}s wall clock "
        "(named nonzero failure; raise DHARMA_SEMGREP_WALLCLOCK only with cause)",
        file=sys.stderr,
    )
    raise SystemExit(2)
raise SystemExit(proc.returncode)
PY
