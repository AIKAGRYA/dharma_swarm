# Forge Lab legacy v0 control-script custody

> **NONCANONICAL EVIDENCE — DO NOT EXECUTE, SOURCE, COPY INTO `PATH`, OR
> INSTALL THESE FILES.**

This directory preserves the 13 `rsi-*` control-script sources found under
`/root/rsi-lab/bin` on 2026-07-11.  They are custody evidence for the v0 run
substrate, not a supported control surface.  The canonical Forge Lab base is
`/root/rsi-lab/current`; the canonical launcher, when present, is
`scripts/forge_lab/rsi`, outside this legacy directory.

## Hazard boundary

The snapshots retain their legacy behavior.  Depending on the file, merely
running or sourcing one can:

- load or stage provider secrets, including material read from a production
  environment file;
- make live provider requests and spend model budget;
- create, attach to, signal, or inspect tmux sessions;
- write run state, key-liveness receipts, generated shell scripts, or Git
  refs;
- fetch Git refs, detach a worktree, or patch Forge Python implementation
  files.

Archival custody does **not** make those behaviors safe.  The files are stored
without executable mode, but that is only a warning rail: passing one to a
shell can still run it.  Review `inventory.json` before inspecting an
individual source.  Do not source key files or copy secret values while
working with this archive.

## Verbatim custody

The tracked files are byte-for-byte snapshots of the host sources. They retain
historical `/root/rsi-lab/current-main` paths and all other unsafe behavior;
those strings are evidence, not supported configuration. Canonicalization
belongs only in the new launcher outside this directory.

`inventory.json` records both:

- `source_sha256`: the SHA-256 of the host source as captured; and
- `archived_sha256`: the SHA-256 of the file tracked here.

The two digests and sizes are identical for every entry, and the empty
`transformations` arrays make that claim machine-checkable. The original
executable mode is recorded as provenance; tracked copies are mode `0644` data,
not launchers.
