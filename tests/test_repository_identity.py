"""Canonical repository authority is literal, typed, and cutoff-aware."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from dharma_swarm.operator_core.onboarding.repository_identity import (
    CANONICAL_IDENTITY,
    CANONICAL_ORIGIN_URL,
    EXPLICITLY_BLOCKED_IDENTITIES,
    LEGACY_CUTOFF_UTC,
    LEGACY_IDENTITY,
    LOCAL_CONFIG_COMMAND,
    RepositoryIdentitySource,
    RepositoryIdentityStatus,
    observe_repository_identity,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def _git(repo: Path, *args: str, env: dict[str, str] | None = None) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=repo,
        env={**os.environ, **(env or {})},
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.strip()


@pytest.fixture()
def git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    return repo


@pytest.mark.parametrize(
    "origin",
    [
        CANONICAL_ORIGIN_URL,
        "git@github.com:AIKAGRYA/dharma_swarm.git",
        "ssh://git@github.com/AIKAGRYA/dharma_swarm.git",
    ],
)
def test_canonical_github_origin_is_accepted(git_repo: Path, origin: str) -> None:
    _git(git_repo, "remote", "add", "origin", origin)

    observed = observe_repository_identity(git_repo)

    assert observed.status is RepositoryIdentityStatus.CANONICAL
    assert observed.identity == CANONICAL_IDENTITY
    assert observed.blocks is False
    assert observed.provenance.source is RepositoryIdentitySource.RAW_LOCAL_GIT_CONFIG
    assert observed.provenance.key == "remote.origin.url"
    assert observed.provenance.command == LOCAL_CONFIG_COMMAND
    assert observed.provenance.raw_values == (origin,)


def test_global_instead_of_cannot_mask_literal_legacy_origin(
    git_repo: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    legacy_url = "https://github.com/AmitabhainArunachala/dharma_swarm.git"
    _git(git_repo, "remote", "add", "origin", legacy_url)
    global_config = tmp_path / "global.gitconfig"
    global_config.write_text(
        '[url "https://github.com/AIKAGRYA/"]\n'
        "\tinsteadOf = https://github.com/AmitabhainArunachala/\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(global_config))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")

    # This is precisely why repository authority must not use this command.
    assert _git(git_repo, "remote", "get-url", "origin") == CANONICAL_ORIGIN_URL

    observed = observe_repository_identity(
        git_repo, now="2026-08-15T14:59:59Z",
    )
    assert observed.status is RepositoryIdentityStatus.LEGACY_COMPATIBLE
    assert observed.identity == LEGACY_IDENTITY
    assert observed.provenance.raw_values == (legacy_url,)


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        ("2026-08-15T14:59:59Z", RepositoryIdentityStatus.LEGACY_COMPATIBLE),
        (LEGACY_CUTOFF_UTC, RepositoryIdentityStatus.LEGACY_EXPIRED),
        ("2026-08-15T15:00:01Z", RepositoryIdentityStatus.LEGACY_EXPIRED),
    ],
)
def test_legacy_cutoff_boundary_is_exact(
    git_repo: Path,
    now: str,
    expected: RepositoryIdentityStatus,
) -> None:
    _git(
        git_repo,
        "remote",
        "add",
        "origin",
        "git@github.com:AmitabhainArunachala/dharma_swarm.git",
    )

    observed = observe_repository_identity(git_repo, now=now)

    assert observed.status is expected
    assert observed.blocks is (expected is RepositoryIdentityStatus.LEGACY_EXPIRED)


def test_legacy_after_cutoff_blocks(git_repo: Path) -> None:
    """Named negative control required by the cutover work packet."""
    _git(
        git_repo,
        "remote",
        "add",
        "origin",
        "https://github.com/AmitabhainArunachala/dharma_swarm.git",
    )

    observed = observe_repository_identity(
        git_repo, now="2026-08-15T15:00:01Z",
    )

    assert observed.status is RepositoryIdentityStatus.LEGACY_EXPIRED
    assert observed.blocks is True


def test_shakti_saraswati_is_wrong_target_not_compatibility(git_repo: Path) -> None:
    identity = "shakti-saraswati/dharma_swarm"
    assert identity in EXPLICITLY_BLOCKED_IDENTITIES
    _git(
        git_repo,
        "remote",
        "add",
        "origin",
        f"https://github.com/{identity}.git",
    )

    observed = observe_repository_identity(
        git_repo, now="2026-08-15T14:00:00Z",
    )

    assert observed.status is RepositoryIdentityStatus.WRONG_TARGET
    assert observed.identity == identity
    assert observed.blocks is True
    assert "expected AIKAGRYA/dharma_swarm" in observed.reason


def test_other_network_target_is_wrong_even_with_same_repository_name(
    git_repo: Path,
) -> None:
    _git(
        git_repo,
        "remote",
        "add",
        "origin",
        "https://example.invalid/AIKAGRYA/dharma_swarm.git",
    )

    observed = observe_repository_identity(git_repo)

    assert observed.status is RepositoryIdentityStatus.WRONG_TARGET
    assert observed.blocks is True


def test_absent_and_local_origins_are_nonblocking_sterile_clones(
    git_repo: Path,
    tmp_path: Path,
) -> None:
    absent = observe_repository_identity(git_repo)
    assert absent.status is RepositoryIdentityStatus.STERILE
    assert absent.blocks is False
    assert (
        absent.provenance.source
        is RepositoryIdentitySource.RAW_LOCAL_GIT_CONFIG_ABSENT
    )

    local_source = tmp_path / "source.git"
    _git(git_repo, "remote", "add", "origin", str(local_source))
    local = observe_repository_identity(git_repo)
    assert local.status is RepositoryIdentityStatus.STERILE
    assert local.blocks is False
    assert local.origin_url == str(local_source)


def test_multiple_origin_values_fail_closed_as_ambiguous(git_repo: Path) -> None:
    _git(git_repo, "config", "--add", "remote.origin.url", CANONICAL_ORIGIN_URL)
    _git(
        git_repo,
        "config",
        "--add",
        "remote.origin.url",
        "https://github.com/shakti-saraswati/dharma_swarm.git",
    )

    observed = observe_repository_identity(git_repo)

    assert observed.status is RepositoryIdentityStatus.AMBIGUOUS
    assert observed.blocks is True
    assert len(observed.provenance.raw_values) == 2


def test_non_repository_is_typed_not_observed(tmp_path: Path) -> None:
    observed = observe_repository_identity(tmp_path)

    assert observed.status is RepositoryIdentityStatus.NOT_OBSERVED
    assert observed.blocks is True
    assert (
        observed.provenance.source
        is RepositoryIdentitySource.RAW_LOCAL_GIT_CONFIG_ERROR
    )


def test_machine_readable_policy_matches_typed_constants() -> None:
    policy = json.loads(
        (REPO_ROOT / "docs/governance/REPOSITORY_IDENTITY.json").read_text(
            encoding="utf-8"
        )
    )

    assert policy["schema"] == "dharma_swarm.repository_identity.v1"
    assert policy["canonical"] == {
        "identity": CANONICAL_IDENTITY,
        "origin_url": CANONICAL_ORIGIN_URL,
    }
    assert policy["legacy_compatibility"]["identity"] == LEGACY_IDENTITY
    assert policy["legacy_compatibility"]["cutoff_utc"] == LEGACY_CUTOFF_UTC
    assert set(policy["explicitly_blocked"]) == EXPLICITLY_BLOCKED_IDENTITIES
    assert tuple(policy["inspection"]["command"]) == LOCAL_CONFIG_COMMAND
    assert policy["inspection"]["global_url_rewrites"] == "ignored"
