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

if ! command -v semgrep &>/dev/null; then
  echo "semgrep not found on PATH — skipping (install with 'pip install semgrep' or 'brew install semgrep')" >&2
  exit 0
fi

exec semgrep "${args[@]}"
