#!/usr/bin/env bash
# Git merge driver for generated DocOps count files (AUTO_INVENTORY.md,
# SOVEREIGN_MANIFEST.md). See .gitattributes (merge=dharma-docops-counter).
#
# These files are fully derivable from the tree, so a three-way textual merge
# conflict on them is never meaningful. This driver resolves every such merge
# to "ours" and exits 0 (clean). The values are then healed to the merged tree
# by `check_docops_integrity.py --write-auto-sections --write-manifest-counts`,
# which both the local workflow and docops-autorefresh.yml run after merging.
#
# Git invokes the driver as:
#     driver %O %A %B %P
#   %O = common-ancestor version   (unused)
#   %A = current/"ours" version    (also the OUTPUT path git reads back)
#   %B = other/"theirs" version    (discarded)
#   %P = pathname being merged      (for logging only)
#
# %A already holds our content and is the file git reads as the merge result,
# so keeping ours is a no-op write + exit 0. We never leave conflict markers.
set -euo pipefail

ours="${2:-}"
path="${4:-<unknown>}"

if [ -z "${ours}" ]; then
  echo "docops-counter merge driver: missing %A argument" >&2
  exit 1
fi

# Keep ours verbatim (%A is already the result file). Heal happens downstream.
echo "docops-counter merge driver: kept ours for ${path} (values healed post-merge)" >&2
exit 0
