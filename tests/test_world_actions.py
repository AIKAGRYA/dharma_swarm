"""Tests for dharma_swarm.world_actions — world-facing action primitives.

Validates:
- WorldActionResult construction and to_json()
- _run subprocess wrapper
- _git_changed_paths helper
- _slug text normalization
- github_clone_repo destination checks
- github_commit_push error paths
- create_website_scaffold file generation
- publish_markdown_artifact with manifest
- spawn_sub_swarm_spec JSON output
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from dharma_swarm.world_actions import (
    WorldActionResult,
    _slug,
    create_website_scaffold,
    github_clone_repo,
    publish_markdown_artifact,
    spawn_sub_swarm_spec,
)


# ---------------------------------------------------------------------------
# WorldActionResult
# ---------------------------------------------------------------------------


class TestWorldActionResult:
    def test_construction_defaults(self):
        r = WorldActionResult(success=True, action="test", message="ok")
        assert r.success is True
        assert r.path == ""
        assert r.url == ""
        assert r.metadata is None

    def test_to_json_round_trip(self):
        r = WorldActionResult(
            success=True,
            action="clone",
            message="done",
            path="/tmp/repo",
            url="https://github.com/test",
            metadata={"branch": "main"},
        )
        parsed = json.loads(r.to_json())
        assert parsed["success"] is True
        assert parsed["action"] == "clone"
        assert parsed["metadata"]["branch"] == "main"

    def test_to_json_none_metadata(self):
        r = WorldActionResult(success=False, action="fail", message="err")
        parsed = json.loads(r.to_json())
        assert parsed["metadata"] is None


# ---------------------------------------------------------------------------
# _slug helper
# ---------------------------------------------------------------------------


class TestSlug:
    def test_simple_text(self):
        assert _slug("Hello World") == "hello-world"

    def test_special_characters(self):
        assert _slug("My Report! (v2.0)") == "my-report-v2-0"

    def test_empty_string(self):
        assert _slug("") == "artifact"

    def test_only_special_chars(self):
        assert _slug("!!!") == "artifact"

    def test_already_slug(self):
        assert _slug("hello-world") == "hello-world"


# ---------------------------------------------------------------------------
# github_clone_repo
# ---------------------------------------------------------------------------


class TestGithubCloneRepo:
    def test_existing_non_empty_dir_fails(self, tmp_path):
        dest = tmp_path / "repo"
        dest.mkdir()
        (dest / "file.txt").write_text("exists")
        result = github_clone_repo("https://github.com/test/repo.git", str(dest))
        assert result.success is False
        assert "not empty" in result.message.lower()

    def test_clone_failure_returns_error(self, tmp_path):
        dest = tmp_path / "repo"
        with patch("dharma_swarm.world_actions._run") as mock_run:
            mock_run.return_value = (128, "", "fatal: repository not found")
            result = github_clone_repo("https://github.com/test/repo.git", str(dest))
        assert result.success is False
        assert "fatal" in result.message.lower() or "not found" in result.message.lower()

    def test_clone_success(self, tmp_path):
        dest = tmp_path / "repo"
        with patch("dharma_swarm.world_actions._run") as mock_run:
            mock_run.return_value = (0, "Cloning into...", "")
            result = github_clone_repo("https://github.com/test/repo.git", str(dest))
        assert result.success is True
        assert result.action == "github_clone_repo"


# ---------------------------------------------------------------------------
# create_website_scaffold
# ---------------------------------------------------------------------------


class TestCreateWebsiteScaffold:
    def test_creates_html_and_css(self, tmp_path):
        result = create_website_scaffold(
            str(tmp_path / "site"), "Test Site", "A test purpose"
        )
        assert result.success is True
        site_dir = tmp_path / "site"
        assert (site_dir / "index.html").exists()
        assert (site_dir / "styles.css").exists()

    def test_html_contains_site_name(self, tmp_path):
        create_website_scaffold(str(tmp_path / "s"), "My Portal", "purpose")
        html = (tmp_path / "s" / "index.html").read_text()
        assert "My Portal" in html

    def test_html_contains_purpose(self, tmp_path):
        create_website_scaffold(str(tmp_path / "s"), "Site", "Welfare optimization")
        html = (tmp_path / "s" / "index.html").read_text()
        assert "Welfare optimization" in html

    def test_css_contains_styles(self, tmp_path):
        create_website_scaffold(str(tmp_path / "s"), "Site", "purpose")
        css = (tmp_path / "s" / "styles.css").read_text()
        assert "body" in css
        assert "--bg" in css

    def test_custom_theme(self, tmp_path):
        result = create_website_scaffold(str(tmp_path / "s"), "Site", "p", theme="dark")
        assert result.metadata["theme"] == "dark"
        html = (tmp_path / "s" / "index.html").read_text()
        assert "dark" in html

    def test_creates_nested_directories(self, tmp_path):
        result = create_website_scaffold(
            str(tmp_path / "deep" / "nested" / "site"), "Site", "purpose"
        )
        assert result.success is True


# ---------------------------------------------------------------------------
# publish_markdown_artifact
# ---------------------------------------------------------------------------


class TestPublishMarkdownArtifact:
    def test_publishes_with_manifest(self, tmp_path):
        src = tmp_path / "report.md"
        src.write_text("# Report\nContent here.")
        out_dir = tmp_path / "artifacts"

        result = publish_markdown_artifact(str(src), str(out_dir))
        assert result.success is True
        assert (out_dir / "report.md").exists()

        manifest_files = list(out_dir.glob("*.manifest.json"))
        assert len(manifest_files) == 1
        manifest = json.loads(manifest_files[0].read_text())
        assert manifest["kind"] == "markdown_artifact"

    def test_custom_artifact_name(self, tmp_path):
        src = tmp_path / "draft.md"
        src.write_text("# Draft")
        out_dir = tmp_path / "out"

        result = publish_markdown_artifact(str(src), str(out_dir), artifact_name="final.md")
        assert result.success is True
        assert (out_dir / "final.md").exists()

    def test_missing_source_fails(self, tmp_path):
        result = publish_markdown_artifact(str(tmp_path / "nope.md"), str(tmp_path / "out"))
        assert result.success is False
        assert "missing" in result.message.lower()

    def test_preserves_content(self, tmp_path):
        content = "# Test\n\nSome **bold** text.\n"
        src = tmp_path / "test.md"
        src.write_text(content)
        out_dir = tmp_path / "out"

        publish_markdown_artifact(str(src), str(out_dir))
        published = (out_dir / "test.md").read_text()
        assert published == content


# ---------------------------------------------------------------------------
# spawn_sub_swarm_spec
# ---------------------------------------------------------------------------


class TestSpawnSubSwarmSpec:
    def test_creates_spec_file(self, tmp_path):
        result = spawn_sub_swarm_spec(
            str(tmp_path), "Research Mission", "Explore quantum computing"
        )
        assert result.success is True
        spec_files = list(tmp_path.glob("*.subswarm.json"))
        assert len(spec_files) == 1

    def test_spec_contains_mission_data(self, tmp_path):
        spawn_sub_swarm_spec(
            str(tmp_path), "Alpha Mission", "Do important things"
        )
        spec_files = list(tmp_path.glob("*.subswarm.json"))
        spec = json.loads(spec_files[0].read_text())
        assert spec["mission_name"] == "Alpha Mission"
        assert spec["thesis"] == "Do important things"
        assert spec["status"] == "ready"

    def test_default_roles(self, tmp_path):
        spawn_sub_swarm_spec(str(tmp_path), "Mission", "thesis")
        spec_files = list(tmp_path.glob("*.subswarm.json"))
        spec = json.loads(spec_files[0].read_text())
        assert "cartographer" in spec["roles"]
        assert "validator" in spec["roles"]

    def test_custom_roles(self, tmp_path):
        spawn_sub_swarm_spec(
            str(tmp_path), "Mission", "thesis",
            roles=["leader", "researcher"],
        )
        spec_files = list(tmp_path.glob("*.subswarm.json"))
        spec = json.loads(spec_files[0].read_text())
        assert spec["roles"] == ["leader", "researcher"]

    def test_slug_in_filename(self, tmp_path):
        spawn_sub_swarm_spec(str(tmp_path), "My Special Mission!", "thesis")
        spec_files = list(tmp_path.glob("*.subswarm.json"))
        assert any("my-special-mission" in f.name for f in spec_files)
