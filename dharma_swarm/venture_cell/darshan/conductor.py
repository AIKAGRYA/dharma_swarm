"""Thin Darshan conductor for manual Season 0 artifact transactions."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from dharma_swarm.venture_cell.darshan.bundle import (
    BundleValidationResult,
    create_bundle,
    validate_bundle,
)


def run_once(
    *,
    title: str,
    slug: str | None = None,
    root: Path | None = None,
    bundle_date: date | None = None,
    overwrite: bool = False,
) -> BundleValidationResult:
    bundle_path = create_bundle(
        title=title,
        slug=slug,
        root=root,
        bundle_date=bundle_date,
        overwrite=overwrite,
    )
    return validate_bundle(bundle_path)
