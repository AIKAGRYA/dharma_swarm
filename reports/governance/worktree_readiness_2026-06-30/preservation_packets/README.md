# Preservation Packet Payloads

This directory intentionally tracks only `MANIFEST.json`.

The full preservation packet payloads contain local Git bundles and untracked-file
archives for dirty worktrees. They are too large and too machine-local for a
normal repository PR. The payloads remain preserved under the local closeout
bundle recorded in:

`reports/governance/worktree_readiness_2026-06-30/tab_closeout_receipt_20260701T025940Z.md`

Use the manifest to identify preserved worktree packets, then retrieve the
payloads from the local tab closeout bundle when operating on the same machine.
