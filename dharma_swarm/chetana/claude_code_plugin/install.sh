#!/usr/bin/env bash
# install.sh — one-shot installer for the chetana Claude Code plugin.
#
# Usage:
#   bash dharma_swarm/chetana/claude_code_plugin/install.sh [--symlink]
#
# Default: copies plugin contents into ~/.claude/plugins/marketplaces/local-chetana/.
# With --symlink: symlinks instead, so `git pull` updates the live plugin.
#
# Either way, you still need to enable the plugin in ~/.claude/settings.json:
#   enabledPlugins["chetana@local-chetana"] = true
#   extraKnownMarketplaces["local-chetana"] = {
#     "source": { "source": "directory", "path": "<full path>" }
#   }

set -euo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST_DIR="${HOME}/.claude/plugins/marketplaces/local-chetana"

mode="copy"
if [[ "${1:-}" == "--symlink" ]]; then
  mode="symlink"
fi

if [[ -e "${DEST_DIR}" || -L "${DEST_DIR}" ]]; then
  echo "Destination already exists: ${DEST_DIR}"
  echo "Backing up to ${DEST_DIR}.bak.$(date +%s)"
  mv "${DEST_DIR}" "${DEST_DIR}.bak.$(date +%s)"
fi

mkdir -p "$(dirname "${DEST_DIR}")"

case "${mode}" in
  copy)
    echo "Copying plugin from ${SRC_DIR} → ${DEST_DIR}"
    cp -R "${SRC_DIR}" "${DEST_DIR}"
    ;;
  symlink)
    echo "Symlinking ${DEST_DIR} → ${SRC_DIR}"
    ln -s "${SRC_DIR}" "${DEST_DIR}"
    ;;
esac

# Make sure scripts are executable (cp may not preserve flags depending on flags).
chmod +x "${DEST_DIR}/chetana/scripts/"*.sh 2>/dev/null || true

echo ""
echo "Plugin installed at ${DEST_DIR}"
echo ""
echo "Next steps:"
echo "  1. Add to ~/.claude/settings.json:"
echo '       "enabledPlugins": { "chetana@local-chetana": true }'
echo '       "extraKnownMarketplaces": {'
echo '         "local-chetana": {'
echo '           "source": { "source": "directory", "path": "'"${DEST_DIR}"'" }'
echo '         }'
echo '       }'
echo "  2. Restart Claude Code."
echo "  3. On next SessionStart, chetana will surface decay/gap state."
echo ""
echo "Verify the install at any time:"
echo "  CLAUDE_PLUGIN_ROOT=${DEST_DIR}/chetana \\"
echo "    bash ${DEST_DIR}/chetana/scripts/session_start.sh"
