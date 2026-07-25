import importlib.util
import json
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "reports/darshan/scripts/seal_issue_one_receipt.py"
DRAFT = REPO_ROOT / "reports/darshan/issue_one_receipt.DRAFT.json"


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
