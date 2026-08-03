import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "reports/darshan/scripts/seal_issue_one_receipt.py"
DRAFT = REPO_ROOT / "reports/darshan/issue_one_receipt.DRAFT.json"
MANIFEST = REPO_ROOT / "reports/darshan/ISSUE_ONE_MANIFEST.md"


def _load_seal_module():
    spec = importlib.util.spec_from_file_location("darshan_issue_one_seal", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


seal = _load_seal_module()


def test_validated_publication_url_accepts_exact_https_origin() -> None:
    url = "https://amitabhainarunachala.github.io/darshan/the-silenced-no/"

    assert seal._validated_publication_url(url) == url


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "http://amitabhainarunachala.github.io/darshan/article/",
        "//amitabhainarunachala.github.io/darshan/article/",
        "https://evil.example/darshan/article/",
        "https://amitabhainarunachala.github.io.evil.example/darshan/article/",
        "https://evil.example@amitabhainarunachala.github.io/darshan/article/",
        "https://amitabhainarunachala.github.io:443/darshan/article/",
        "https://[::1",
    ],
)
def test_validated_publication_url_rejects_noncanonical_origins(url: str) -> None:
    with pytest.raises(SystemExit) as caught:
        seal._validated_publication_url(url)

    assert caught.value.code == 1


def test_all_draft_publication_urls_use_exact_https_origin() -> None:
    receipt = json.loads(DRAFT.read_text(encoding="utf-8"))

    for article in receipt["articles"]:
        url = article["published_url"]
        assert seal._validated_publication_url(url) == url


def test_fetch_publication_uses_fixed_host_and_path(monkeypatch) -> None:
    calls = []

    class FakeResponse:
        status_code = 200
        content = b"page"

    class FakeClient:
        def __init__(
            self,
            *,
            verify: bool,
            follow_redirects: bool,
            timeout: int,
        ) -> None:
            calls.append(("client", verify, follow_redirects, timeout))

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            calls.append(("close",))

        def get(self, target):
            calls.append(
                (
                    "get",
                    target.scheme,
                    target.host,
                    target.raw_path,
                )
            )
            return FakeResponse()

    monkeypatch.setattr(seal.httpx, "Client", FakeClient)

    status, body = seal._fetch_publication(
        "https://amitabhainarunachala.github.io/darshan/article/?view=full"
    )

    assert (status, body) == (200, b"page")
    assert calls == [
        ("client", True, False, 30),
        (
            "get",
            "https",
            "amitabhainarunachala.github.io",
            b"/darshan/article/?view=full",
        ),
        ("close",),
    ]


# ------------------------------------------------------------ path containment


def test_validated_repo_file_accepts_contained_relative_path() -> None:
    p = seal._validated_repo_file(
        "reports/darshan/issue_one/articles/2026-07-12-the-chamber.md"
    )

    assert p.is_relative_to(seal.REPO.resolve())


@pytest.mark.parametrize(
    "repo_file",
    [
        "/etc/passwd",
        "../outside.md",
        "reports/darshan/../../../etc/passwd",
        "reports/../../sibling/x.md",
        ".",
    ],
)
def test_validated_repo_file_rejects_escapes(repo_file: str) -> None:
    with pytest.raises(SystemExit) as caught:
        seal._validated_repo_file(repo_file)

    assert caught.value.code == 1


# ----------------------------------------------------------- completeness gate


def test_manifest_slugs_match_draft_receipt_exactly() -> None:
    manifest_slugs = seal._manifest_slugs(MANIFEST.read_text(encoding="utf-8"))
    receipt = json.loads(DRAFT.read_text(encoding="utf-8"))

    assert manifest_slugs == [a["slug"] for a in receipt["articles"]]
    seal._check_completeness(receipt, manifest_slugs)


def _real_receipt_and_slugs():
    receipt = json.loads(DRAFT.read_text(encoding="utf-8"))
    manifest_slugs = seal._manifest_slugs(MANIFEST.read_text(encoding="utf-8"))
    return receipt, manifest_slugs


def test_completeness_rejects_missing_article() -> None:
    receipt, manifest_slugs = _real_receipt_and_slugs()
    receipt["articles"] = receipt["articles"][:-1]  # truncated issue

    with pytest.raises(SystemExit) as caught:
        seal._check_completeness(receipt, manifest_slugs)

    assert caught.value.code == 1


def test_completeness_rejects_extra_article() -> None:
    receipt, manifest_slugs = _real_receipt_and_slugs()
    extra = copy.deepcopy(receipt["articles"][0])
    extra["slug"] = "2026-08-01-phantom-piece"
    receipt["articles"].append(extra)

    with pytest.raises(SystemExit) as caught:
        seal._check_completeness(receipt, manifest_slugs)

    assert caught.value.code == 1


def test_completeness_rejects_duplicate_slug() -> None:
    receipt, manifest_slugs = _real_receipt_and_slugs()
    receipt["articles"][1] = copy.deepcopy(receipt["articles"][0])

    with pytest.raises(SystemExit) as caught:
        seal._check_completeness(receipt, manifest_slugs)

    assert caught.value.code == 1


def test_completeness_rejects_noncanonical_published_url() -> None:
    receipt, manifest_slugs = _real_receipt_and_slugs()
    receipt["articles"][0]["published_url"] = (
        "https://amitabhainarunachala.github.io/darshan/articles/other-page.html"
    )

    with pytest.raises(SystemExit) as caught:
        seal._check_completeness(receipt, manifest_slugs)

    assert caught.value.code == 1


# ------------------------------------------------- end-to-end seal (fixture)


FIXTURE_BODY_ONE = """
## The First Fixture Heading

This paragraph exists so the rendered body is long enough to count as
substantial publication evidence. It carries **bold text**, *emphasis*, an
inline `code span`, and a [link](https://example.invalid/ref) so every inline
rule of the site renderer is exercised at least once in this fixture body.

A second paragraph follows the first one, because a single paragraph would be
too short to clear the minimum-body-length gate that the seal script enforces
before it will accept a page as publication evidence for any article.

- first list item with enough words to matter
- second list item, *also* rendered through the inline rules

> A blockquote closes the fixture body so block-level recursion is covered.

The closing paragraph states a number the mismatch test will alter: the
headline effect is g = -1.864 with CI [-2.280, -1.532], and that exact claim
must be on the live page for the seal to pass.
"""

FIXTURE_BODY_TWO = """
## The Second Fixture Heading

An entirely different body for the second fixture article, long enough on its
own to clear the minimum-length gate. It repeats no sentence from the first
fixture so a page-swap would be caught immediately by the body containment
check rather than slipping through on shared boilerplate.

Second paragraph of the second article, with an ordered list after it:

1. one numbered item
2. two numbered items

And a final paragraph so the rendered visible text comfortably exceeds the
five-hundred-character floor the seal script demands of a real essay body.
"""


def _page_for(title: str, body_md: str, banner: str = "") -> bytes:
    body_html = seal.md_to_html(body_md)
    return (
        "<!doctype html><html><head><title>%s</title></head><body>"
        '<article><p class="article-meta">12 July 2026 · Issue One</p>'
        '<h1 class="article-title">%s</h1>%s%s</article>'
        "<footer>Darshan</footer></body></html>" % (title, title, banner, body_html)
    ).encode("utf-8")


@pytest.fixture()
def fixture_repo(tmp_path, monkeypatch):
    """A miniature repo: 2 articles + manifest + honest DRAFT receipt."""
    articles_dir = tmp_path / "reports/darshan/issue_one/articles"
    articles_dir.mkdir(parents=True)
    specs = [
        ("2026-07-12-fixture-one", "Fixture Article One", FIXTURE_BODY_ONE),
        ("2026-07-13-fixture-two", "Fixture Article Two", FIXTURE_BODY_TWO),
    ]
    rows = []
    articles = []
    for i, (slug, title, body) in enumerate(specs, start=1):
        md = "---\ntitle: %s\ndate: 2026-07-12\nstatus: draft\n---\n%s" % (
            title,
            body,
        )
        path = articles_dir / f"{slug}.md"
        path.write_text(md, encoding="utf-8")
        rows.append(f"| {i} | {title} | {slug} | drafts/{slug}.md | ASSEMBLED |")
        articles.append(
            {
                "order": i,
                "slug": slug,
                "title": title,
                "repo_file": f"reports/darshan/issue_one/articles/{slug}.md",
                "sha256_md": hashlib.sha256(path.read_bytes()).hexdigest(),
                "published_url": (
                    "https://amitabhainarunachala.github.io/darshan/articles/"
                    f"{slug}.html"
                ),
                "published": False,
                "publication_evidence": "PENDING",
                "status": "ASSEMBLED — awaiting operator read + merge",
            }
        )
    manifest = tmp_path / "reports/darshan/ISSUE_ONE_MANIFEST.md"
    manifest.write_text(
        "# Fixture Manifest\n\n"
        "| # | Title | Slug | Source draft (seat) | Status |\n"
        "|---|-------|------|--------------------|--------|\n"
        + "\n".join(rows)
        + "\n",
        encoding="utf-8",
    )
    receipt = {
        "schema": "darshan.issue_one_receipt.v1",
        "receipt_state": "DRAFT_PENDING_OPERATOR_PUBLICATION",
        "observed_at": "2026-08-03T00:00:00Z",
        "articles": articles,
        "content_digest": seal.stable_digest(
            {a["slug"]: a["sha256_md"] for a in articles}
        ),
        "site_build_sha256": "branch-provisional",
        "editorial_law_passes": {
            "both_fires": True,
            "independent_discernment": True,
            "operator_read": False,
            "operator_read_evidence": "PENDING",
        },
        "external_evidence": [],
        "digest": None,
    }
    draft = tmp_path / "reports/darshan/issue_one_receipt.DRAFT.json"
    draft.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    canonical = tmp_path / "reports/darshan/issue_one_receipt.json"

    monkeypatch.setattr(seal, "REPO", tmp_path)
    monkeypatch.setattr(seal, "DRAFT", draft)
    monkeypatch.setattr(seal, "CANONICAL", canonical)
    monkeypatch.setattr(seal, "MANIFEST", manifest)

    pages = {
        a["published_url"]: _page_for(title, body)
        for a, (_slug, title, body) in zip(articles, specs)
    }

    def fake_fetch(url):
        return 200, pages[url]

    monkeypatch.setattr(seal, "_fetch_publication", fake_fetch)
    return {
        "tmp_path": tmp_path,
        "draft": draft,
        "canonical": canonical,
        "pages": pages,
        "specs": specs,
        "articles": articles,
    }


ARGS = ["--operator-read-confirmed", "read every word — fixture operator"]


def test_seal_happy_path_seals_and_is_internally_consistent(fixture_repo) -> None:
    seal.main(ARGS)

    canonical = fixture_repo["canonical"]
    assert canonical.exists()
    sealed = json.loads(canonical.read_text(encoding="utf-8"))
    assert sealed["receipt_state"] == "SEALED"
    assert sealed["editorial_law_passes"]["operator_read"] is True
    assert sealed["external_evidence"] == []
    for art in sealed["articles"]:
        assert art["published"] is True
        assert art["status"].startswith("SEALED — live page verified")
        assert "full rendered body" in art["publication_evidence"]
    # digest recomputes under the checker's canonicalisation
    assert sealed["digest"] == seal.stable_digest(
        {k: v for k, v in sealed.items() if k != "digest"}
    )


def test_seal_refuses_draft_bannered_page(fixture_repo) -> None:
    slug, title, body = fixture_repo["specs"][0]
    url = fixture_repo["articles"][0]["published_url"]
    banner = (
        '<div class="draft-banner"><strong>Draft — pending discernment '
        "pass.</strong> This piece has not yet survived both fires of the "
        "editorial law and has not received sign-off. It appears here as a "
        "working document; do not cite or circulate.</div>"
    )
    fixture_repo["pages"][url] = _page_for(title, body, banner=banner)

    with pytest.raises(SystemExit) as caught:
        seal.main(ARGS)

    assert caught.value.code == 1
    assert not fixture_repo["canonical"].exists()


def test_seal_refuses_body_mismatched_page(fixture_repo) -> None:
    slug, title, body = fixture_repo["specs"][0]
    url = fixture_repo["articles"][0]["published_url"]
    altered = body.replace("g = -1.864", "g = -1.846")
    assert altered != body
    fixture_repo["pages"][url] = _page_for(title, altered)

    with pytest.raises(SystemExit) as caught:
        seal.main(ARGS)

    assert caught.value.code == 1
    assert not fixture_repo["canonical"].exists()


def test_seal_refuses_truncated_page(fixture_repo) -> None:
    slug, title, body = fixture_repo["specs"][0]
    url = fixture_repo["articles"][0]["published_url"]
    truncated = body[: len(body) // 2]
    fixture_repo["pages"][url] = _page_for(title, truncated)

    with pytest.raises(SystemExit) as caught:
        seal.main(ARGS)

    assert caught.value.code == 1
    assert not fixture_repo["canonical"].exists()


def test_seal_refuses_title_only_page(fixture_repo) -> None:
    slug, title, _body = fixture_repo["specs"][0]
    url = fixture_repo["articles"][0]["published_url"]
    fixture_repo["pages"][url] = _page_for(title, "Just the title, no essay.")

    with pytest.raises(SystemExit) as caught:
        seal.main(ARGS)

    assert caught.value.code == 1
    assert not fixture_repo["canonical"].exists()


def test_seal_refuses_truncated_receipt(fixture_repo) -> None:
    draft = fixture_repo["draft"]
    receipt = json.loads(draft.read_text(encoding="utf-8"))
    receipt["articles"] = receipt["articles"][:1]  # article missing vs manifest
    draft.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(SystemExit) as caught:
        seal.main(ARGS)

    assert caught.value.code == 1
    assert not fixture_repo["canonical"].exists()


def test_seal_refuses_article_edited_after_assembly(fixture_repo) -> None:
    slug, _title, _body = fixture_repo["specs"][0]
    path = (
        fixture_repo["tmp_path"]
        / f"reports/darshan/issue_one/articles/{slug}.md"
    )
    path.write_text(
        path.read_text(encoding="utf-8") + "\nA sentence added after assembly.\n",
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as caught:
        seal.main(ARGS)

    assert caught.value.code == 1
    assert not fixture_repo["canonical"].exists()


def test_seal_refuses_malformed_external_evidence(fixture_repo) -> None:
    draft = fixture_repo["draft"]
    receipt = json.loads(draft.read_text(encoding="utf-8"))
    receipt["external_evidence"] = [{"kind": "citation"}]  # missing keys
    draft.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(SystemExit) as caught:
        seal.main(ARGS)

    assert caught.value.code == 1
    assert not fixture_repo["canonical"].exists()
