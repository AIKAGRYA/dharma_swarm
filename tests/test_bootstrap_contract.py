"""Bootstrap contract (WP-0A / TIT-004).

Reads the real Makefile, hermetic workflow, and Dockerfile and fails if the
frozen dependency path regresses: the exact uv pin, lock-check-before-sync
ordering, frozen sync, in-venv tool resolution, install delegation, or Docker
failure propagation. Authority:
docs/plans/TITANIUM_GRADE_REPOSITORY_HARDENING_2026-07-10.md (WP-0A).
"""
from __future__ import annotations

import re
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_MAKEFILE = (_REPO / "Makefile").read_text(encoding="utf-8")
_HERMETIC = (_REPO / ".github" / "workflows" / "hermetic.yml").read_text(
    encoding="utf-8"
)
_DOCKERFILE = (_REPO / "Dockerfile").read_text(encoding="utf-8")


def _recipe(target: str) -> str:
    match = re.search(rf"^{target}:[^\n]*\n((?:\t.*\n)+)", _MAKEFILE, flags=re.M)
    assert match, f"Makefile must define target {target!r} with a recipe"
    return match.group(1)


def test_uv_version_is_pinned_and_matches_ci() -> None:
    make_pin = re.search(r"^UV_VERSION \?= (\S+)$", _MAKEFILE, flags=re.M)
    assert make_pin, "Makefile must pin UV_VERSION ?= <exact version>"
    ci_pin = re.search(r'UV_VERSION:\s*"([^"]+)"', _HERMETIC)
    assert ci_pin, "hermetic.yml must pin UV_VERSION"
    assert make_pin.group(1) == ci_pin.group(1), (
        "Makefile and hermetic.yml must pin the same uv version: "
        f"{make_pin.group(1)} != {ci_pin.group(1)}"
    )


def test_bootstrap_checks_lock_before_frozen_sync() -> None:
    recipe = _recipe("bootstrap")
    check = recipe.find("lock --check")
    sync = recipe.find("sync --frozen --extra dev")
    assert check != -1, "bootstrap must run uv lock --check (the drift oracle)"
    assert sync != -1, "bootstrap must run uv sync --frozen --extra dev"
    assert check < sync, "uv lock --check must run before the frozen sync"


def test_bootstrap_installs_and_confirms_exact_pinned_uv() -> None:
    recipe = _recipe("bootstrap")
    assert 'pip install --user --quiet "uv==$(UV_VERSION)"' in recipe, (
        "bootstrap must install the exact pinned uv through the current Python"
    )
    assert "site --user-base" in recipe, (
        "bootstrap must resolve the user-base uv executable, not trust PATH"
    )
    assert recipe.count('grep -Eq "^uv $(UV_VERSION)( |$$)"') >= 1, (
        "bootstrap must confirm the resolved uv is exactly the pinned version "
        "(accepting both 'uv X.Y.Z (target)' and bare 'uv X.Y.Z' output)"
    )


def test_hermetic_workflow_checks_lock_before_frozen_sync() -> None:
    check = _HERMETIC.find("uv lock --check")
    sync = _HERMETIC.find("uv sync --frozen --extra dev")
    assert check != -1, "hermetic.yml must run uv lock --check"
    assert sync != -1, "hermetic.yml must run uv sync --frozen --extra dev"
    assert check < sync, "hermetic.yml must check the lock before the frozen sync"


def test_install_delegates_to_frozen_path() -> None:
    match = re.search(r"^install:([^\n]*)\n((?:\t.*\n)*)", _MAKEFILE, flags=re.M)
    assert match, "Makefile must define an install target"
    prerequisites, recipe = match.group(1), match.group(2)
    assert "bootstrap" in prerequisites, "install must delegate to bootstrap"
    assert "pip install -e" not in recipe, (
        "install may not return to unpinned editable installation"
    )


def test_verification_resolves_venv_tools() -> None:
    assert re.search(r"^PYTHON := .*\.venv/bin/python", _MAKEFILE, flags=re.M), (
        "PYTHON must resolve .venv/bin/python when present"
    )
    assert re.search(r"^RUFF = .*\.venv/bin/ruff", _MAKEFILE, flags=re.M), (
        "RUFF must lazily resolve .venv/bin/ruff when present (recursive '=', "
        "so a bootstrap in the same make invocation is seen)"
    )
    for target in ("lint", "lint-blockers"):
        assert "$(RUFF) check" in _recipe(target), (
            f"{target} must use the resolved $(RUFF), not a bare PATH lookup"
        )


def test_docker_dependency_failure_propagates() -> None:
    assert "2>/dev/null ||" not in _DOCKERFILE, (
        "Dockerfile may not hide install stderr behind a fallback chain"
    )
    assert "|| true" not in _DOCKERFILE, (
        "Dockerfile may not swallow command failure with '|| true'"
    )
    for line in _DOCKERFILE.splitlines():
        if line.startswith("RUN") and "pip install" in line:
            assert "||" not in line, (
                f"Docker dependency installation may not swallow failure: {line!r}"
            )


def test_docker_lane_is_labeled_non_hermetic() -> None:
    assert "NON-HERMETIC" in _DOCKERFILE, (
        "the live-resolution Docker lane must carry an explicit non-hermetic label"
    )


def test_no_unpinned_script_downloads_in_required_lanes() -> None:
    for text, name in ((_MAKEFILE, "Makefile"), (_HERMETIC, "hermetic.yml")):
        assert "astral.sh/uv/install.sh" not in text, (
            f"{name} must not download the unpinned uv install script"
        )
        assert not re.search(r"curl[^\n]*\|\s*(?:ba)?sh\b", text), (
            f"{name} must not pipe a downloaded script into a shell"
        )
