from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SITE_ROOT = REPO_ROOT / "reports" / "darshan" / "site"
BUILD_SCRIPT = SITE_ROOT / "scripts" / "build.py"
PAGES_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "darshan-pages.yml"
SPEC = importlib.util.spec_from_file_location("darshan_site_build", BUILD_SCRIPT)
assert SPEC and SPEC.loader
builder = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = builder
SPEC.loader.exec_module(builder)


def test_issue_one_build_is_deterministic_and_complete(tmp_path: Path) -> None:
    content = SITE_ROOT / "content"
    articles = sorted(content.glob("*.md"))
    assert len(articles) == 6

    first = tmp_path / "first"
    second = tmp_path / "second"
    first_manifest = builder.build_site(content, first)
    second_manifest = builder.build_site(content, second)

    assert first_manifest == second_manifest
    assert first_manifest["article_count"] == 6
    assert len(first_manifest["site_build_sha256"]) == 64
    assert (first / "index.html").exists()
    assert len(list((first / "articles").glob("*.html"))) == 6


def test_site_has_no_tracking_or_feed_mechanics(tmp_path: Path) -> None:
    output = tmp_path / "site"
    builder.build_site(SITE_ROOT / "content", output)
    rendered = "\n".join(
        path.read_text(encoding="utf-8") for path in output.rglob("*.html")
    ).lower()

    assert "<script" not in rendered
    assert "google-analytics" not in rendered
    assert "segment.com" not in rendered
    assert "facebook.com/tr" not in rendered


def test_every_article_carries_editorial_reconsideration_and_work(tmp_path: Path) -> None:
    output = tmp_path / "site"
    manifest = builder.build_site(SITE_ROOT / "content", output)

    for article in manifest["articles"]:
        html = (output / article["path"]).read_text(encoding="utf-8")
        assert "What would change this" in html
        assert "Open questions" in html


def test_pages_workflow_is_narrow_and_permission_bounded() -> None:
    workflow = PAGES_WORKFLOW.read_text(encoding="utf-8")

    assert "reports/darshan/site/**" in workflow
    assert "pages: write" in workflow
    assert "id-token: write" in workflow
    assert "contents: read" in workflow
    assert "enablement: true" in workflow
    assert "python3 reports/darshan/site/scripts/build.py" in workflow
    assert "reports/darshan/site/public" in workflow
