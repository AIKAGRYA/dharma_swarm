"""telos_kernel._io \u2014 the I/O rim.

Every function in this subpackage is annotated with an @effect(...) tag
declaring the external effects it may perform. The core (all sibling
modules of _io/) is pure: no `open`, no `subprocess`, no `yaml.safe_load`,
no `Path.rglob`, no network.

Trust-boundary contract
-----------------------
- Core \u2192 rim: allowed, but only via the functions exported here.
- Rim \u2192 core: allowed (rim consumes core types like Leaf, Manifest).
- Rim functions MUST NOT be called from within a hot-path signing routine;
  their effects (filesystem, subprocess, yaml, git) are opaque to
  titanium-verify and their latency is unbounded.

The `_io_boundary_test.py` in the test suite enforces at import-boundary
level that no core module calls into `_io`.
"""
from __future__ import annotations

from telos_kernel.effects import Effect, effect
from telos_kernel._io.manifest_loader import load_manifest_from_disk
from telos_kernel._io.merkle_file_backend import FileBackendIO
from telos_kernel._io.notary_fs import GitBoundLocalFileAnchor
from telos_kernel._io.sbom import compute_sbom_digest

__all__ = [
    "Effect",
    "effect",
    "load_manifest_from_disk",
    "FileBackendIO",
    "GitBoundLocalFileAnchor",
    "compute_sbom_digest",
]
