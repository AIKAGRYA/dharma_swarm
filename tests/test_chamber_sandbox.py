"""Scorer sandbox hardening — diff policy, env scrub, containment (R2/R3)."""

from __future__ import annotations

from pathlib import Path

import pytest

from dharma_swarm.chamber.sandbox import (
    DiffPolicyError,
    assert_within,
    diff_policy_reason,
    find_symlinks,
    scrubbed_env,
)


def _newfile_diff(path: str, body: str = "x = 1\n", mode: str = "100644") -> str:
    return (f"diff --git a/{path} b/{path}\n"
            f"new file mode {mode}\nindex 0000000..1111111\n"
            f"--- /dev/null\n+++ b/{path}\n@@ -0,0 +1,1 @@\n+{body}")


@pytest.mark.parametrize("path", [
    "conftest.py", "pkg/conftest.py", "sitecustomize.py", "usercustomize.py",
    "pytest.ini", "tox.ini", "setup.cfg", "pyproject.toml", "evil.pth",
])
def test_execution_env_files_are_rejected(path):
    reason = diff_policy_reason(_newfile_diff(path))
    assert reason and "rejected" in reason


def test_symlink_diff_is_rejected():
    reason = diff_policy_reason(_newfile_diff("tests", "../../../etc", mode="120000"))
    assert reason and "symlink" in reason


@pytest.mark.parametrize("path", ["../escape.py", "/etc/passwd", "a/../../b.py"])
def test_out_of_tree_paths_are_rejected(path):
    reason = diff_policy_reason(_newfile_diff(path))
    assert reason and ("out-of-tree" in reason or "symlink" in reason)


def test_ordinary_source_diff_is_allowed():
    assert diff_policy_reason(_newfile_diff("mymod.py")) is None
    assert diff_policy_reason(_newfile_diff("pkg/sub/module.py")) is None


def test_scrubbed_env_drops_secrets_and_redirects_home(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-secret")
    monkeypatch.setenv("MY_TOKEN", "t")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "a")
    monkeypatch.setenv("PATH", "/usr/bin")
    env = scrubbed_env(tmp_path / "sb")
    assert "ANTHROPIC_API_KEY" not in env
    assert "MY_TOKEN" not in env
    assert "AWS_SECRET_ACCESS_KEY" not in env
    assert env["PATH"] == "/usr/bin"
    assert env["HOME"] == str(tmp_path / "sb")  # away from real ~/.dharma
    assert env["GIT_CEILING_DIRECTORIES"] == str(tmp_path)
    assert env["PYTHONNOUSERSITE"] == "1"


def test_assert_within_blocks_escape(tmp_path):
    root = tmp_path / "sb"
    root.mkdir()
    assert_within(root, root / "ok.py")
    with pytest.raises(DiffPolicyError):
        assert_within(root, tmp_path / "outside.py")


def test_find_symlinks_detects_planted_link(tmp_path):
    root = tmp_path / "sb"
    root.mkdir()
    assert find_symlinks(root) == []
    (root / "link").symlink_to(tmp_path)
    assert len(find_symlinks(root)) == 1
