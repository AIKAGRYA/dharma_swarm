#!/usr/bin/env python3
"""Seal the Darshan Issue One receipt — fail-closed.

Promotes reports/darshan/issue_one_receipt.DRAFT.json to the canonical path the
track checker reads (reports/darshan/issue_one_receipt.json) ONLY when every
publication fact the receipt asserts is verified live at seal time. If any
check fails, nothing is written and the exit code is non-zero. A receipt that
asserts an unpublished issue must not validate; that is the point.

Run from the repo root, after the operator has read Issue One and merged the
darshan site PR (Pages deploys from main):

    python3 scripts/darshan/seal_issue_one_receipt.py \
        --operator-read-confirmed "<the operator's own words>"

Checks (all mandatory, in order):
  1. completeness: the receipt's articles exactly match the canonical-order
     table in reports/darshan/ISSUE_ONE_MANIFEST.md — same slugs, same order,
     no missing, no extras; slugs, published_urls and repo_files unique; every
     published_url and repo_file derived from its slug;
  2. containment: every repo_file is a relative path that resolves strictly
     under the repo root (no absolute paths, no '..' escapes);
  3. every repo article file re-hashes to the sha256 recorded at assembly
     (content unchanged between what was read and what was published);
  4. every published_url returns HTTP 200 AND the fetched page
       a. does NOT carry the site's draft banner (marker `class="draft-banner"`
          / phrase "Draft — pending discernment pass." from the darshan site
          scripts/build.py template) — a draft-bannered page is NOT published;
       b. contains the piece's title; and
       c. contains the FULL rendered article body — the markdown body is
          rendered with a byte-identical copy of the darshan site renderer
          (scripts/build.py @ c40ae16), both page and rendering are reduced to
          visible text (tags stripped, HTML-unescaped, whitespace collapsed),
          and the entire normalized body must appear as one consecutive run of
          the normalized page text (title-only or truncated pages fail);
  5. every editorial-law gate already established outside this script is
     explicitly true (`both_fires` and `independent_discernment`);
  6. every article carries a digest-bound, article-hash-bound source-review
     receipt with verdict PASS; and
  7. --operator-read-confirmed was provided (recorded verbatim), with no
     remaining item in `pending_operator_actions`.

Then: published=true and per-article status/publication_evidence updated to the
seal-time observation (the sealed receipt is internally consistent — no stale
"awaiting operator read" statuses survive sealing), editorial_law_passes.
operator_read=true, observed_at=utc_now, site_build_sha256 recomputed from the
LIVE pages, and digest = stable_digest(receipt minus digest) — canonicalisation
identical to scripts/governance/check_track_status.py and
memory_kernel.write_receipts.

External evidence doctrine: publication is delivery, nothing more. Evidence of
external consumption (readers, citations, replies, republication) accrues in
the receipt's additive top-level `external_evidence` list — entries shaped
{kind, source, url_or_ref, observed_at, note} — which defaults to [] and is
sealed into the digest like every other key. The tracker criterion's
requires_keys are unaffected: extra keys are permitted. This script validates
the field's shape but never fabricates entries.

The script never promotes editorial or source-review state. Those facts are
produced by independent review and must already be digest-bound PASS evidence
in the draft. A pending action is never silently deleted: the draft must be
updated after each prerequisite is actually discharged, before sealing.
"""

import argparse
import html
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

import httpx

REPO = Path(__file__).resolve().parents[2]
DRAFT = REPO / "reports/darshan/issue_one_receipt.DRAFT.json"
CANONICAL = REPO / "reports/darshan/issue_one_receipt.json"
MANIFEST = REPO / "reports/darshan/ISSUE_ONE_MANIFEST.md"
DARSHAN_PUBLICATION_NETLOC = "amitabhainarunachala.github.io"
ARTICLE_URL_PREFIX = (
    "https://amitabhainarunachala.github.io/darshan/articles/"
)
ARTICLE_REPO_DIR = "reports/darshan/issue_one/articles"

# Exact draft-banner marker emitted by the darshan site template
# (darshan repo scripts/build.py, DRAFT_BANNER, commit c40ae16). A page that
# carries either the attribute marker or the visible phrase is a DRAFT page
# and must never seal as published. Fail-closed: a false refusal is
# acceptable, a false seal is not.
DRAFT_BANNER_MARKER = 'class="draft-banner"'
DRAFT_BANNER_PHRASE = "Draft — pending discernment pass."

# A real essay's rendered body is thousands of characters; anything shorter
# indicates a parsing failure and must not be used as matching evidence.
MIN_BODY_CHARS = 500

try:
    from dharma_swarm.memory_kernel.write_receipts import stable_digest, utc_now
except Exception:  # stdlib fallback, byte-identical canonicalisation
    import hashlib
    from datetime import datetime, timezone

    def stable_digest(payload: object) -> str:
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    def utc_now() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fail(msg: str) -> None:
    print(f"SEAL REFUSED: {msg}", file=sys.stderr)
    sys.exit(1)


def _validated_publication_url(url: str) -> str:
    """Admit only the exact HTTPS origin owned by the Darshan publication."""
    try:
        parsed = urlsplit(url)
    except (TypeError, ValueError) as exc:
        fail(f"invalid published_url {url!r}: {exc}")
    if (
        parsed.scheme != "https"
        or parsed.netloc != DARSHAN_PUBLICATION_NETLOC
    ):
        fail("published_url must use the exact HTTPS Darshan publication origin")
    return url


def _validated_repo_file(repo_file: str) -> Path:
    """repo_file must be relative and resolve strictly under the repo root."""
    rel = Path(repo_file)
    if rel.is_absolute() or ".." in rel.parts:
        fail(f"repo_file {repo_file!r} must be a relative path with no '..' "
             "components")
    resolved = (REPO / rel).resolve()
    root = REPO.resolve()
    if resolved == root or not resolved.is_relative_to(root):
        fail(f"repo_file {repo_file!r} escapes the repo root")
    return resolved


def sha256_file(p: Path) -> str:
    import hashlib
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ------------------------------------------------------------------ manifest

def _manifest_slugs(manifest_text: str) -> list[str]:
    """Slugs, in canonical order, from the manifest's canonical-order table."""
    slugs: list[str] = []
    for line in manifest_text.splitlines():
        if not re.match(r"^\|\s*\d+\s*\|", line):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3 or not cells[2]:
            fail(f"manifest canonical-order row malformed: {line!r}")
        if int(cells[0]) != len(slugs) + 1:
            fail(f"manifest canonical-order numbering broken at: {line!r}")
        slugs.append(cells[2])
    if not slugs:
        fail(f"no canonical-order table rows found in {MANIFEST}")
    if len(set(slugs)) != len(slugs):
        fail("manifest canonical-order table contains duplicate slugs")
    return slugs


def _check_completeness(receipt: dict, manifest_slugs: list[str]) -> None:
    """Receipt articles must exactly match the manifest article set."""
    articles = receipt.get("articles")
    if not isinstance(articles, list) or not articles:
        fail("receipt has no articles list")
    receipt_slugs = [str(a.get("slug", "")) for a in articles]
    if receipt_slugs != manifest_slugs:
        missing = sorted(set(manifest_slugs) - set(receipt_slugs))
        extra = sorted(set(receipt_slugs) - set(manifest_slugs))
        fail(
            "receipt articles do not match the ISSUE_ONE_MANIFEST canonical "
            f"set (missing: {missing or 'none'}; extra: {extra or 'none'}; "
            f"order/duplicates checked): {receipt_slugs!r} != {manifest_slugs!r}"
        )
    urls = [str(a.get("published_url", "")) for a in articles]
    if len(set(urls)) != len(urls):
        fail("receipt published_urls are not unique")
    repo_files = [str(a.get("repo_file", "")) for a in articles]
    if len(set(repo_files)) != len(repo_files):
        fail("receipt repo_files are not unique")
    for i, art in enumerate(articles):
        slug = str(art.get("slug", ""))
        if art.get("order") != i + 1:
            fail(f"article {slug!r} order field is {art.get('order')!r}, "
                 f"expected {i + 1}")
        expected_url = f"{ARTICLE_URL_PREFIX}{slug}.html"
        if art.get("published_url") != expected_url:
            fail(f"article {slug!r} published_url {art.get('published_url')!r} "
                 f"is not the canonical {expected_url!r}")
        expected_file = f"{ARTICLE_REPO_DIR}/{slug}.md"
        if art.get("repo_file") != expected_file:
            fail(f"article {slug!r} repo_file {art.get('repo_file')!r} is not "
                 f"the canonical {expected_file!r}")


def _validated_external_evidence(receipt: dict) -> list:
    """external_evidence: additive top-level list, [] by default, shape-checked."""
    evidence = receipt.get("external_evidence", [])
    if not isinstance(evidence, list):
        fail("external_evidence must be a list")
    required = {"kind", "source", "url_or_ref", "observed_at", "note"}
    for i, entry in enumerate(evidence):
        if not isinstance(entry, dict) or not required <= set(entry):
            fail(f"external_evidence[{i}] must be an object with keys "
                 f"{sorted(required)}")
    return evidence


def _require_editorial_gates(receipt: dict) -> None:
    """Refuse to promote publication unless every non-live editorial gate passed."""
    laws = receipt.get("editorial_law_passes")
    if not isinstance(laws, dict):
        fail("editorial_law_passes must be an object")
    for gate in ("both_fires", "independent_discernment"):
        if laws.get(gate) is not True:
            fail(
                f"editorial_law_passes.{gate} is {laws.get(gate)!r}; the "
                "editorial law must pass before the receipt can seal"
            )


def _require_no_pending_actions(receipt: dict) -> None:
    """A sealer may prove facts, but it may not erase unresolved obligations."""
    actions = receipt.get("pending_operator_actions")
    if not isinstance(actions, list):
        fail("pending_operator_actions must be a list")
    if actions:
        fail(
            "pending_operator_actions is not empty; discharge and record every "
            "listed prerequisite before sealing (nothing is cleared implicitly)"
        )


def _expected_content_digest(receipt: dict) -> str:
    """Derive the aggregate article fingerprint from the checked article rows."""
    return stable_digest(
        {str(article["slug"]): str(article["sha256_md"])
         for article in receipt["articles"]}
    )


def _validated_source_verification(
    receipt: dict, manifest_slugs: list[str]
) -> None:
    """Validate one independent, digest-bound source-review receipt per article.

    Promotion is deliberately typed: a prose assertion or boolean is not
    enough. Each PASS must bind reviewer, article bytes, source checks, and its
    own canonical digest in a contained repository artifact.
    """
    records = receipt.get("source_verification")
    if not isinstance(records, dict):
        fail("source_verification must be an object keyed by article slug")
    if set(records) != set(manifest_slugs):
        fail("source_verification keys must exactly match the manifest slugs")

    required_check_keys = {"source", "access", "disposition", "note"}
    allowed_access = {"FULL_TEXT_READ", "PRIMARY_SOURCE_READ"}
    allowed_dispositions = {
        "SUPPORTED",
        "ATTRIBUTED",
        "NOT_LOAD_BEARING",
        "CORRECTED",
        "REMOVED",
    }
    articles = {str(a["slug"]): a for a in receipt["articles"]}
    for slug in manifest_slugs:
        record = records[slug]
        if not isinstance(record, dict) or record.get("status") != "VERIFIED":
            status = record.get("status") if isinstance(record, dict) else None
            fail(f"source_verification[{slug!r}] is {status!r}, not VERIFIED")
        reviewer = record.get("reviewer")
        observed_at = record.get("observed_at")
        evidence_file = record.get("evidence_file")
        evidence_sha256 = record.get("evidence_sha256")
        if not all(isinstance(v, str) and v.strip() for v in (
            reviewer, observed_at, evidence_file, evidence_sha256
        )):
            fail(f"source_verification[{slug!r}] has incomplete evidence metadata")

        evidence_path = _validated_repo_file(evidence_file)
        expected_parent = (REPO / "reports/darshan/source_verification").resolve()
        if not evidence_path.is_relative_to(expected_parent):
            fail(
                f"source_verification[{slug!r}] evidence_file must be under "
                "reports/darshan/source_verification/"
            )
        if not evidence_path.is_file():
            fail(f"source-verification evidence missing: {evidence_file}")
        if sha256_file(evidence_path) != evidence_sha256:
            fail(f"source-verification evidence hash mismatch for {slug!r}")

        try:
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            fail(f"source-verification evidence unreadable for {slug!r}: {exc}")
        if evidence.get("schema") != "darshan.source_verification.v1":
            fail(f"source-verification evidence schema invalid for {slug!r}")
        if evidence.get("article_slug") != slug:
            fail(f"source-verification evidence slug mismatch for {slug!r}")
        if evidence.get("article_sha256_md") != articles[slug]["sha256_md"]:
            fail(f"source-verification evidence article hash mismatch for {slug!r}")
        if evidence.get("reviewer") != reviewer or evidence.get("observed_at") != observed_at:
            fail(f"source-verification evidence metadata mismatch for {slug!r}")
        if evidence.get("verdict") != "PASS":
            fail(f"source-verification evidence verdict is not PASS for {slug!r}")
        checks = evidence.get("source_checks")
        if not isinstance(checks, list) or not checks:
            fail(f"source-verification evidence has no source_checks for {slug!r}")
        for index, check in enumerate(checks):
            if not isinstance(check, dict) or not required_check_keys <= set(check):
                fail(
                    f"source-verification {slug!r} check {index} must contain "
                    f"{sorted(required_check_keys)}"
                )
            if check["access"] not in allowed_access:
                fail(f"source-verification {slug!r} check {index} has invalid access")
            if check["disposition"] not in allowed_dispositions:
                fail(
                    f"source-verification {slug!r} check {index} has unresolved "
                    "or invalid disposition"
                )
            if not all(isinstance(check[key], str) and check[key].strip()
                       for key in required_check_keys):
                fail(f"source-verification {slug!r} check {index} has empty fields")
        digest = evidence.get("digest")
        expected_digest = stable_digest(
            {k: v for k, v in evidence.items() if k != "digest"}
        )
        if not isinstance(digest, str) or digest != expected_digest:
            fail(f"source-verification evidence digest invalid for {slug!r}")


# ------------------------------------------------------- site renderer copy
# Byte-identical copy of the darshan site renderer (darshan repo
# scripts/build.py @ c40ae16: _inline, md_to_html body, _is_block_start,
# front-matter split). Copied, not imported, so the seal verifies against the
# exact transformation the published site applies — renderer drift between the
# copies shows up as a seal REFUSAL, never as a silent pass.

def _split_front_matter(text: str) -> str:
    body = text
    if text.startswith("---"):
        parts = text.split("\n")
        end = None
        for i, line in enumerate(parts[1:], start=1):
            if line.strip() == "---":
                end = i
                break
        if end is not None:
            body = "\n".join(parts[end + 1:])
    return body


def _inline(text):
    """Inline markdown on already-escaped text: code, links, bold, italic."""
    stash = []

    def keep(fragment):
        stash.append(fragment)
        return "\x00%d\x00" % (len(stash) - 1)

    text = re.sub(
        r"`([^`]+)`", lambda m: keep("<code>%s</code>" % m.group(1)), text
    )
    text = re.sub(
        r"\[([^\]]+)\]\(([^)\s]+)\)",
        lambda m: keep('<a href="%s">%s</a>' % (m.group(2), m.group(1))),
        text,
    )
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", text)
    return re.sub(r"\x00(\d+)\x00", lambda m: stash[int(m.group(1))], text)


def md_to_blocks(md):
    lines = md.split("\n")
    out = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        if stripped.startswith("```"):
            block = []
            i += 1
            while i < n and not lines[i].strip().startswith("```"):
                block.append(lines[i])
                i += 1
            i += 1
            out.append(
                "<pre><code>%s</code></pre>"
                % html.escape("\n".join(block), quote=False)
            )
            continue

        if re.fullmatch(r"(-{3,}|\*{3,}|_{3,})", stripped):
            out.append("<hr>")
            i += 1
            continue

        m = re.match(r"(#{1,6})\s+(.*)", stripped)
        if m:
            level = len(m.group(1))
            text = _inline(html.escape(m.group(2), quote=False))
            out.append("<h%d>%s</h%d>" % (level, text, level))
            i += 1
            continue

        if stripped.startswith(">"):
            quote_lines = []
            while i < n and lines[i].strip().startswith(">"):
                quote_lines.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            inner = md_to_html("\n".join(quote_lines))
            out.append("<blockquote>%s</blockquote>" % inner)
            continue

        if re.match(r"[-*]\s+", stripped):
            items = []
            while i < n and re.match(r"[-*]\s+", lines[i].strip()):
                item = re.sub(r"^[-*]\s+", "", lines[i].strip())
                i += 1
                while i < n and lines[i].startswith("  ") and lines[i].strip():
                    item += " " + lines[i].strip()
                    i += 1
                items.append(item)
            out.append(
                "<ul>%s</ul>"
                % "".join(
                    "<li>%s</li>" % _inline(html.escape(t, quote=False))
                    for t in items
                )
            )
            continue

        if re.match(r"\d+\.\s+", stripped):
            items = []
            while i < n and re.match(r"\d+\.\s+", lines[i].strip()):
                item = re.sub(r"^\d+\.\s+", "", lines[i].strip())
                i += 1
                while i < n and lines[i].startswith("  ") and lines[i].strip():
                    item += " " + lines[i].strip()
                    i += 1
                items.append(item)
            out.append(
                "<ol>%s</ol>"
                % "".join(
                    "<li>%s</li>" % _inline(html.escape(t, quote=False))
                    for t in items
                )
            )
            continue

        para = []
        while i < n and lines[i].strip() and not _is_block_start(lines[i].strip()):
            para.append(lines[i].strip())
            i += 1
        out.append("<p>%s</p>" % _inline(html.escape(" ".join(para), quote=False)))

    return out


def md_to_html(md):
    return "\n".join(md_to_blocks(md))


def _is_block_start(stripped):
    return bool(
        stripped.startswith(("#", ">", "```"))
        or re.fullmatch(r"(-{3,}|\*{3,}|_{3,})", stripped)
        or re.match(r"[-*]\s+", stripped)
        or re.match(r"\d+\.\s+", stripped)
    )


# -------------------------------------------------------- body verification

_TAG_RE = re.compile(r"<[^>]*>")


def _visible_text(html_text: str) -> str:
    """Reduce HTML to normalized visible text: strip script/style blocks and
    tags (tags become spaces), HTML-unescape, collapse all whitespace."""
    text = re.sub(r"(?is)<(script|style)\b.*?</\1\s*>", " ", html_text)
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _rendered_body_text(article_path: Path) -> str:
    """Normalized visible text of the article body rendered exactly as the
    site renders it."""
    body_md = _split_front_matter(article_path.read_text(encoding="utf-8"))
    return _visible_text(md_to_html(body_md))


def _check_page_publishes_body(
    url: str, page_raw: str, article_path: Path
) -> str:
    """The live page must carry no draft banner and must contain the full
    rendered article body. Returns the normalized body's sha256."""
    if DRAFT_BANNER_MARKER in page_raw:
        fail(f"{url} carries the site draft banner ({DRAFT_BANNER_MARKER}) — "
             "a draft-bannered page is NOT published")
    page_text = _visible_text(page_raw)
    if DRAFT_BANNER_PHRASE in page_text:
        fail(f"{url} carries the draft-banner phrase "
             f"{DRAFT_BANNER_PHRASE!r} — a draft-bannered page is NOT "
             "published")
    body_text = _rendered_body_text(article_path)
    if len(body_text) < MIN_BODY_CHARS:
        fail(f"rendered body of {article_path.name} is only "
             f"{len(body_text)} chars (< {MIN_BODY_CHARS}) — refusing to use "
             "it as publication evidence")
    if body_text not in page_text:
        first_bad = ""
        body_md = _split_front_matter(article_path.read_text(encoding="utf-8"))
        for block in md_to_blocks(body_md):
            block_text = _visible_text(block)
            if len(block_text) >= 40 and block_text not in page_text:
                first_bad = block_text[:120]
                break
        fail(f"{url} is live but does not contain the full rendered article "
             f"body — the repo text is not what the page shows (first "
             f"missing/altered block starts: {first_bad!r})")
    import hashlib
    return hashlib.sha256(body_text.encode("utf-8")).hexdigest()


def _fetch_publication(url: str) -> tuple[int, bytes]:
    """Fetch one validated page without allowing redirects or a dynamic host."""
    safe_url = _validated_publication_url(url)
    parsed = urlsplit(safe_url)
    request_target = httpx.URL(
        scheme="https",
        host=DARSHAN_PUBLICATION_NETLOC,
        path=parsed.path or "/",
        query=parsed.query.encode("utf-8"),
    )
    with httpx.Client(
        verify=True,
        follow_redirects=False,
        timeout=30,
    ) as client:
        response = client.get(request_target)
    return response.status_code, response.content


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--operator-read-confirmed", required=False, default="",
                    help="The operator's own confirmation words. Mandatory.")
    args = ap.parse_args(argv)

    if not args.operator_read_confirmed.strip():
        fail("--operator-read-confirmed is mandatory (the operator-read gate "
             "cannot be sealed silently)")
    if not DRAFT.exists():
        fail(f"draft receipt missing: {DRAFT}")
    if CANONICAL.exists():
        fail(f"{CANONICAL} already exists; refusing to overwrite a sealed receipt")
    if not MANIFEST.exists():
        fail(f"manifest missing: {MANIFEST}")

    receipt = json.loads(DRAFT.read_text(encoding="utf-8"))

    # 1. Completeness: articles exactly match the manifest canonical set.
    manifest_slugs = _manifest_slugs(MANIFEST.read_text(encoding="utf-8"))
    _check_completeness(receipt, manifest_slugs)

    # external_evidence: additive, [] by default, sealed into the digest.
    receipt["external_evidence"] = _validated_external_evidence(receipt)

    # Non-live publication authority is never inferred from reachable pages.
    # These checks run before network contact so a known editorial blocker
    # cannot accidentally be obscured by a successful deployment probe.
    _require_editorial_gates(receipt)
    _validated_source_verification(receipt, manifest_slugs)
    _require_no_pending_actions(receipt)

    # 2 + 3. Repo article paths contained; content unchanged since assembly.
    article_paths: dict[str, Path] = {}
    for art in receipt["articles"]:
        p = _validated_repo_file(art["repo_file"])
        if not p.exists():
            fail(f"article file missing: {art['repo_file']}")
        actual = sha256_file(p)
        if actual != art["sha256_md"]:
            fail(f"{art['repo_file']} sha256 changed since assembly "
                 f"({actual[:12]}… != {art['sha256_md'][:12]}…); re-run assembly "
                 "or regenerate the draft receipt so the operator reads what ships")
        article_paths[art["slug"]] = p

    expected_content_digest = _expected_content_digest(receipt)
    if receipt.get("content_digest") != expected_content_digest:
        fail(
            "content_digest does not match stable_digest({slug: sha256_md}) "
            "for the verified article set"
        )

    # 4. Every article live: HTTP 200, no draft banner, title AND full
    #    rendered body on the page.
    sealed_at = utc_now()
    live_pages: dict[str, str] = {}
    for art in receipt["articles"]:
        url = art["published_url"]
        try:
            status, body = _fetch_publication(url)
        except Exception as exc:
            fail(f"{url} unreachable: {type(exc).__name__}: {exc}")
        if status != 200:
            fail(f"{url} returned HTTP {status}")
        page_raw = body.decode("utf-8", errors="replace")
        text = _visible_text(page_raw)
        if art["title"] not in text:
            fail(f"{url} is live but does not contain the title "
                 f"{art['title']!r} — wrong or stale page")
        body_sha = _check_page_publishes_body(
            url, page_raw, article_paths[art["slug"]]
        )
        live_pages[url] = stable_digest(text)
        art["published"] = True
        art["publication_evidence"] = (
            f"HTTP 200 + no-draft-banner + title + full rendered body "
            f"verified on the live page at seal time; rendered_body_sha256 "
            f"{body_sha[:16]}…; page stable_digest {live_pages[url][:16]}…"
        )
        art["status"] = (
            f"SEALED — live page verified {sealed_at} (HTTP 200, no draft "
            "banner, full rendered body on page)"
        )
        print(f"live  {url}")

    # 5. Seal.
    receipt["receipt_state"] = "SEALED"
    receipt["observed_at"] = sealed_at
    receipt["editorial_law_passes"]["operator_read"] = True
    receipt["editorial_law_passes"]["operator_read_evidence"] = (
        args.operator_read_confirmed.strip()
    )
    receipt["site_build_sha256"] = stable_digest(live_pages)
    receipt["site_build_sha256_kind"] = (
        "live_pages_sealed — stable_digest over {published_url: page_stable_digest} "
        "of every Issue One page fetched HTTP-200 at seal time"
    )
    # pending_operator_actions was required to be empty above. Preserve it
    # verbatim so the permanent record never acquires a false assertion by
    # seal-time deletion.
    receipt["digest_policy"] = (
        "digest = stable_digest(receipt minus digest); canonicalisation identical "
        "to scripts/governance/check_track_status.py. Sealed by "
        "scripts/darshan/seal_issue_one_receipt.py after live verification."
    )
    receipt["digest"] = None
    receipt["digest"] = stable_digest(
        {k: v for k, v in receipt.items() if k != "digest"}
    )

    CANONICAL.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(f"\nSEALED -> {CANONICAL}")
    print(f"digest: {receipt['digest']}")
    print("Verify with: python3 scripts/governance/check_track_status.py")


if __name__ == "__main__":
    main()
