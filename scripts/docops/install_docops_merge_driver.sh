#!/usr/bin/env bash
# Register the `dharma-docops-counter` merge driver for this clone.
#
# A custom git merge driver named in .gitattributes only runs if it is also
# registered in the repo's git config (git does not auto-discover drivers, for
# security). This wires the driver named in .gitattributes to
# scripts/docops/docops_counter_merge_driver.sh so merges of the generated
# count files (AUTO_INVENTORY.md, SOVEREIGN_MANIFEST.md) resolve cleanly to
# ours instead of conflicting. Idempotent; safe to run repeatedly.
#
# Run once per clone (also invoked by `make onboard`):
#     scripts/docops/install_docops_merge_driver.sh
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
driver="${repo_root}/scripts/docops/docops_counter_merge_driver.sh"

if [ ! -x "${driver}" ]; then
  chmod +x "${driver}" 2>/dev/null || true
fi

git config merge.dharma-docops-counter.name \
  "Keep-ours for generated DocOps count files; values healed post-merge"
# %A is the result file; %B/%O/%P are passed for completeness/logging.
git config merge.dharma-docops-counter.driver \
  "${driver} %O %A %B %P"

echo "Registered merge driver dharma-docops-counter -> ${driver}"
