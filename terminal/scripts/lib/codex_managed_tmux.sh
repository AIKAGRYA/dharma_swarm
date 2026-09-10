#!/usr/bin/env bash
# Shared private-server boundary for disposable Helm tmux harnesses.
# Compatible with the macOS system Bash (3.2).

CODEX_MANAGED_TMUX_PURPOSE=""
CODEX_MANAGED_TMUX_OWNER_PID=""
CODEX_MANAGED_TMUX_SOCKET=""
CODEX_MANAGED_TMUX_ROOT=""

_codex_managed_tmux_error() {
  echo "codex_managed_tmux: $1" >&2
  return 2
}

_codex_managed_tmux_validate_purpose() {
  local purpose="${1:-}"

  case "$purpose" in
    ""|[!a-z]*|*[!a-z0-9_]*)
      _codex_managed_tmux_error \
        "purpose must match [a-z][a-z0-9_]* (got '${purpose}')"
      return 2
      ;;
  esac
}

_codex_managed_tmux_validate_owner() {
  local expected_socket

  if [[ -z "${CODEX_MANAGED_TMUX_PURPOSE:-}" \
    || -z "${CODEX_MANAGED_TMUX_OWNER_PID:-}" \
    || -z "${CODEX_MANAGED_TMUX_SOCKET:-}" \
    || -z "${CODEX_MANAGED_TMUX_ROOT:-}" ]]; then
    _codex_managed_tmux_error "private socket is not initialized"
    return 2
  fi
  case "$CODEX_MANAGED_TMUX_ROOT" in
    /*) ;;
    *)
      _codex_managed_tmux_error "managed tmux root is not absolute"
      return 2
      ;;
  esac
  case "$CODEX_MANAGED_TMUX_OWNER_PID" in
    *[!0-9]*)
      _codex_managed_tmux_error "owner PID is not numeric"
      return 2
      ;;
  esac
  if [[ "$CODEX_MANAGED_TMUX_OWNER_PID" != "$$" ]]; then
    _codex_managed_tmux_error \
      "owner PID '${CODEX_MANAGED_TMUX_OWNER_PID}' does not match current shell '$$'"
    return 2
  fi
  _codex_managed_tmux_validate_purpose "$CODEX_MANAGED_TMUX_PURPOSE" || return 2
  expected_socket="CODEX_MANAGED_${CODEX_MANAGED_TMUX_PURPOSE}_${CODEX_MANAGED_TMUX_OWNER_PID}"
  if [[ "$CODEX_MANAGED_TMUX_SOCKET" != "$expected_socket" ]]; then
    _codex_managed_tmux_error \
      "socket '${CODEX_MANAGED_TMUX_SOCKET}' does not match owner '${expected_socket}'"
    return 2
  fi
}

codex_managed_tmux_init() {
  local purpose="${1:-}"
  local tmux_root="${TMUX_TMPDIR:-/tmp}"

  _codex_managed_tmux_validate_purpose "$purpose" || return 2
  case "$tmux_root" in
    /*) ;;
    *)
      _codex_managed_tmux_error "TMUX_TMPDIR must be an absolute path"
      return 2
      ;;
  esac
  if ! command -v tmux >/dev/null 2>&1; then
    _codex_managed_tmux_error "tmux is required"
    return 2
  fi

  CODEX_MANAGED_TMUX_PURPOSE="$purpose"
  CODEX_MANAGED_TMUX_OWNER_PID="$$"
  CODEX_MANAGED_TMUX_SOCKET="CODEX_MANAGED_${purpose}_$$"
  CODEX_MANAGED_TMUX_ROOT="$tmux_root"
  _codex_managed_tmux_validate_owner
}

codex_managed_tmux() {
  _codex_managed_tmux_validate_owner || return 2
  (
    export TMUX_TMPDIR="$CODEX_MANAGED_TMUX_ROOT"
    unset TMUX
    command tmux -L "$CODEX_MANAGED_TMUX_SOCKET" -f /dev/null "$@"
  )
}

_codex_managed_tmux_stop_client() {
  local client_pid="$1"
  local attempt=0
  local timed_out=0

  while kill -0 "$client_pid" >/dev/null 2>&1; do
    if [[ "$attempt" -ge 20 ]]; then
      timed_out=1
      kill -TERM "$client_pid" >/dev/null 2>&1 || true
      break
    fi
    attempt=$((attempt + 1))
    sleep 0.05
  done

  attempt=0
  while kill -0 "$client_pid" >/dev/null 2>&1; do
    if [[ "$attempt" -ge 20 ]]; then
      kill -KILL "$client_pid" >/dev/null 2>&1 || true
      break
    fi
    attempt=$((attempt + 1))
    sleep 0.05
  done
  wait "$client_pid" >/dev/null 2>&1 || true
  [[ "$timed_out" -eq 0 ]]
}

codex_managed_tmux_cleanup() {
  local client_pid
  local socket_path

  if [[ -z "${CODEX_MANAGED_TMUX_SOCKET:-}" ]]; then
    return 0
  fi
  _codex_managed_tmux_validate_owner || return 2

  codex_managed_tmux kill-server >/dev/null 2>&1 &
  client_pid=$!
  if ! _codex_managed_tmux_stop_client "$client_pid"; then
    if codex_managed_tmux list-sessions >/dev/null 2>&1; then
      _codex_managed_tmux_error \
        "kill-server timed out; refusing to unlink a potentially live socket"
      return 1
    fi
  fi

  # tmux can leave a dead socket after kill-server. Remove only the exact,
  # validated socket owned by this shell PID; never use a glob here.
  socket_path="${CODEX_MANAGED_TMUX_ROOT}/tmux-$(id -u)/${CODEX_MANAGED_TMUX_SOCKET}"
  rm -f -- "$socket_path"

  CODEX_MANAGED_TMUX_PURPOSE=""
  CODEX_MANAGED_TMUX_OWNER_PID=""
  CODEX_MANAGED_TMUX_SOCKET=""
  CODEX_MANAGED_TMUX_ROOT=""
}
