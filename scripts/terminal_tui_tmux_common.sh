#!/usr/bin/env bash
# Persistent, cross-process tmux boundary for the HELM terminal control scripts.
# Compatible with the macOS system Bash (3.2).

TERMINAL_TUI_TMUX_SOCKET=""
TERMINAL_TUI_TMUX_SESSION=""
TERMINAL_TUI_TMUX_TMPDIR=""
TERMINAL_TUI_TMUX_STATE_DIR=""

_terminal_tui_tmux_error() {
  echo "terminal_tui_tmux: $1" >&2
  return 2
}

_terminal_tui_tmux_validate_path() {
  local label="$1"
  local value="$2"

  case "${value}" in
    /*) ;;
    *)
      _terminal_tui_tmux_error "${label} must be an absolute path (got '${value}')"
      return 2
      ;;
  esac

  case "${value}" in
    *$'\n'*|*$'\r'*)
      _terminal_tui_tmux_error "${label} must not contain newlines"
      return 2
      ;;
  esac
}

terminal_tui_tmux_init() {
  local socket_path
  local socket_path_bytes
  local socket_pattern='^CODEX_MANAGED_[A-Za-z0-9][A-Za-z0-9_-]*$'
  local session_pattern='^[A-Za-z0-9][A-Za-z0-9 _-]*$'

  if [[ -n "${DHARMA_TERMINAL_TUI_STATE_DIR:-}" ]]; then
    TERMINAL_TUI_TMUX_STATE_DIR="${DHARMA_TERMINAL_TUI_STATE_DIR}"
  elif [[ -n "${HOME:-}" ]]; then
    TERMINAL_TUI_TMUX_STATE_DIR="${HOME}/.dharma/terminal_tui"
  else
    _terminal_tui_tmux_error \
      "set DHARMA_TERMINAL_TUI_STATE_DIR when HOME is unavailable"
    return 2
  fi

  TERMINAL_TUI_TMUX_SOCKET="${DHARMA_TERMINAL_TMUX_SOCKET:-CODEX_MANAGED_helm_tui}"
  TERMINAL_TUI_TMUX_SESSION="${DHARMA_TERMINAL_TMUX_SESSION:-${SESSION_NAME:-dharma_terminal_tui}}"
  # Keep the Unix-domain socket path short.  State directories routinely live
  # under long worktree/test paths, while tmux sockets have a portable limit of
  # roughly 103 bytes.  Durable logs still belong under ~/.dharma; the socket is
  # transient and remains isolated by the explicit CODEX_MANAGED_* label.
  TERMINAL_TUI_TMUX_TMPDIR="${DHARMA_TERMINAL_TMUX_TMPDIR:-/tmp}"

  if [[ ! "${TERMINAL_TUI_TMUX_SOCKET}" =~ ${socket_pattern} ]]; then
    _terminal_tui_tmux_error \
      "DHARMA_TERMINAL_TMUX_SOCKET must match CODEX_MANAGED_<name> (got '${TERMINAL_TUI_TMUX_SOCKET}')"
    return 2
  fi
  if [[ ! "${TERMINAL_TUI_TMUX_SESSION}" =~ ${session_pattern} ]]; then
    _terminal_tui_tmux_error \
      "DHARMA_TERMINAL_TMUX_SESSION contains unsupported characters (got '${TERMINAL_TUI_TMUX_SESSION}')"
    return 2
  fi

  _terminal_tui_tmux_validate_path \
    "DHARMA_TERMINAL_TUI_STATE_DIR" "${TERMINAL_TUI_TMUX_STATE_DIR}" || return 2
  _terminal_tui_tmux_validate_path \
    "DHARMA_TERMINAL_TMUX_TMPDIR" "${TERMINAL_TUI_TMUX_TMPDIR}" || return 2

  socket_path="${TERMINAL_TUI_TMUX_TMPDIR}/tmux-$(id -u)/${TERMINAL_TUI_TMUX_SOCKET}"
  socket_path_bytes="$(LC_ALL=C printf '%s' "${socket_path}" | wc -c | tr -d '[:space:]')"
  if [[ "${socket_path_bytes}" -gt 103 ]]; then
    _terminal_tui_tmux_error \
      "managed socket path exceeds the portable 103-byte limit (${socket_path_bytes}: '${socket_path}')"
    return 2
  fi

  if ! command -v tmux >/dev/null 2>&1; then
    _terminal_tui_tmux_error "tmux is required"
    return 2
  fi

  mkdir -p -- "${TERMINAL_TUI_TMUX_STATE_DIR}" "${TERMINAL_TUI_TMUX_TMPDIR}"
}

terminal_tui_tmux() {
  if [[ -z "${TERMINAL_TUI_TMUX_SOCKET:-}" \
    || -z "${TERMINAL_TUI_TMUX_SESSION:-}" \
    || -z "${TERMINAL_TUI_TMUX_TMPDIR:-}" ]]; then
    _terminal_tui_tmux_error "terminal_tui_tmux_init must run first"
    return 2
  fi

  env -u TMUX \
    TMUX_TMPDIR="${TERMINAL_TUI_TMUX_TMPDIR}" \
    tmux -L "${TERMINAL_TUI_TMUX_SOCKET}" -f /dev/null "$@"
}

terminal_tui_print_tmux_command() {
  local argument

  printf 'env -u TMUX TMUX_TMPDIR=%q tmux -L %q -f /dev/null' \
    "${TERMINAL_TUI_TMUX_TMPDIR}" "${TERMINAL_TUI_TMUX_SOCKET}"
  for argument in "$@"; do
    printf ' %q' "${argument}"
  done
  printf '\n'
}

terminal_tui_print_receipt() {
  local capture_lines="${1:-120}"

  echo "Socket: ${TERMINAL_TUI_TMUX_SOCKET}"
  echo "Session: ${TERMINAL_TUI_TMUX_SESSION}"
  printf 'Attach: '
  terminal_tui_print_tmux_command attach -t "=${TERMINAL_TUI_TMUX_SESSION}"
  printf 'Capture: '
  terminal_tui_print_tmux_command \
    capture-pane -p -t "=${TERMINAL_TUI_TMUX_SESSION}:" -S "-${capture_lines}"
}
