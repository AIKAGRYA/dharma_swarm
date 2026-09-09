#!/usr/bin/env bash
# Single entry point; generated applications and receipts live under ~/.dharma.
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
PYTHON_BIN="${DHARMA_PYTHON:-}"
if [[ -z "${PYTHON_BIN}" && -x "${REPO_ROOT}/.venv/bin/python" ]]; then
  PYTHON_BIN="${REPO_ROOT}/.venv/bin/python"
fi
if [[ -z "${PYTHON_BIN}" && -x "${HOME}/dharma_swarm/.venv/bin/python" ]]; then
  PYTHON_BIN="${HOME}/dharma_swarm/.venv/bin/python"
fi
if [[ -z "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="$(command -v python3)"
fi
"${PYTHON_BIN}" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else "Helm Desktop requires Python 3.11+; set DHARMA_PYTHON")'
case "${1:-}" in
  ""|-h|--help|help)
    cat <<'USAGE'
Helm Desktop entry point
  build-menu [--state-dir PATH]   Compile the native macOS status menu
  menu [--state-dir PATH]         Build and request the native menu
  verify [--skip-native] [--skip-live]
                                 Verify installation and a disposable live seat

The following desktop commands use the same CLI as the native menu:
USAGE
    exec "${PYTHON_BIN}" "${SCRIPT_DIR}/helm_desktop.py" --help
    ;;
  build-menu)
    shift
    exec "${PYTHON_BIN}" "${SCRIPT_DIR}/build_helm_menu.py" "$@"
    ;;
  menu)
    shift
    exec "${PYTHON_BIN}" "${SCRIPT_DIR}/build_helm_menu.py" --launch "$@"
    ;;
  verify)
    shift
    exec "${PYTHON_BIN}" "${SCRIPT_DIR}/verify/helm_desktop_verify.py" "$@"
    ;;
  *) exec "${PYTHON_BIN}" "${SCRIPT_DIR}/helm_desktop.py" "$@" ;;
esac
