"""The dashboard tsconfig must keep `.ts`-suffixed imports compilable.

Observed 2026-08-07: `main`'s advisory `dashboard` CI job failed at the
`next build` type-check step with 20 TS5097 errors ("An import path can only
end with a '.ts' extension when 'allowImportingTsExtensions' is enabled")
plus follow-on errors, byte-identical on unrelated PRs (#1286, #1204).

The `.ts`-suffixed imports are not a mistake. The dashboard's node-native
test suites run under `node --experimental-strip-types --test`, which
resolves imports at runtime and therefore REQUIRES the real on-disk
extension. Stripping the extensions would fix the build and break the test
runner; the only configuration under which both toolchains accept the same
sources is `allowImportingTsExtensions: true`, which TypeScript permits
exactly when the project never emits (`noEmit: true` — the Next.js default,
already pinned in this tsconfig).

This file pins that pair so neither half is reverted in isolation:

  * while any dashboard source imports a `.ts`-suffixed path,
    `allowImportingTsExtensions` must stay enabled, or `next build`'s
    type-check step goes red on every PR;
  * `allowImportingTsExtensions` is only legal alongside `noEmit`, so
    dropping `noEmit` reopens the same failure as TS5096.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TSCONFIG = REPO_ROOT / "dashboard" / "tsconfig.json"
DASHBOARD_SRC = REPO_ROOT / "dashboard" / "src"

_TS_SUFFIXED_IMPORT = re.compile(r"""from\s+["'][^"']+\.ts["']""")


def _compiler_options() -> dict:
    return json.loads(TSCONFIG.read_text(encoding="utf-8"))["compilerOptions"]


def _ts_suffixed_import_files() -> list[str]:
    return sorted(
        str(path.relative_to(REPO_ROOT))
        for path in DASHBOARD_SRC.rglob("*.ts")
        if _TS_SUFFIXED_IMPORT.search(path.read_text(encoding="utf-8"))
    )


def test_ts_suffixed_imports_require_the_extension_flag() -> None:
    """THE regression. Sources import `.ts` paths for the strip-types test
    runner; without the flag, `next build` fails type-check on every PR."""
    importers = _ts_suffixed_import_files()
    if not importers:
        return  # no `.ts`-suffixed imports remain; the flag may be retired
    assert _compiler_options().get("allowImportingTsExtensions") is True, (
        "dashboard/tsconfig.json no longer enables allowImportingTsExtensions "
        "while these files import '.ts'-suffixed paths (required by "
        "node --experimental-strip-types); next build's type-check step will "
        f"fail with TS5097 on every PR: {importers[:5]}"
    )


def test_no_emit_stays_true_so_the_extension_flag_stays_legal() -> None:
    """allowImportingTsExtensions is only valid in a no-emit project; dropping
    noEmit reopens the build failure as TS5096 instead of TS5097."""
    options = _compiler_options()
    if options.get("allowImportingTsExtensions") is not True:
        return  # nothing to keep legal
    assert options.get("noEmit") is True, (
        "dashboard/tsconfig.json enables allowImportingTsExtensions without "
        "noEmit; TypeScript rejects that pairing (TS5096) and next build's "
        "type-check step goes red"
    )
