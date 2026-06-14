import re

from dharma_swarm.versioning import daemon_version as dv


def test_version_stamp_has_all_five_keys():
    stamp = dv.version_stamp()
    assert set(stamp) == {"build_id", "daemon_version", "git_sha", "started_at", "pid"}


def test_build_id_format_matches_pattern():
    dv.daemon_version.cache_clear()
    dv.git_short_sha.cache_clear()
    build_id = dv.daemon_version()
    # accepts a real short sha OR the "unknown" fallback
    assert re.match(r"^\d+\.\d+\.\d+\+([0-9a-f]+|unknown)$", build_id), build_id


def test_never_raises_on_git_failure(monkeypatch):
    dv.git_short_sha.cache_clear()
    dv.daemon_version.cache_clear()
    monkeypatch.delenv("DHARMA_BUILD_SHA", raising=False)

    def boom(*a, **k):
        raise FileNotFoundError("git missing")

    monkeypatch.setattr(dv.subprocess, "run", boom)
    assert dv.git_short_sha() == "unknown"
    assert dv.daemon_version().endswith("+unknown")
    dv.git_short_sha.cache_clear()
    dv.daemon_version.cache_clear()


def test_build_sha_override(monkeypatch):
    dv.git_short_sha.cache_clear()
    dv.daemon_version.cache_clear()
    monkeypatch.setenv("DHARMA_BUILD_SHA", "deadbeef0000")
    assert dv.git_short_sha() == "deadbeef0000"
    dv.git_short_sha.cache_clear()
    dv.daemon_version.cache_clear()
