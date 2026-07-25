#!/usr/bin/env python3
"""Seal the Darshan Issue One receipt — fail-closed.

Promotes reports/darshan/issue_one_receipt.DRAFT.json to the canonical path the
track checker reads (reports/darshan/issue_one_receipt.json) ONLY when every
publication fact the receipt asserts is verified live at seal time. If any
check fails, nothing is written and the exit code is non-zero. A receipt that
asserts an unpublished issue must not validate; that is the point.

Run from the repo root, after the operator has read Issue One and merged the
darshan site PR (Pages deploys from main):

    python3 reports/darshan/scripts/seal_issue_one_receipt.py \
        --operator-read-confirmed "<the operator's own words>"

Checks (all mandatory, in order):
  1. every repo article file re-hashes to the sha256 recorded at assembly
     (content unchanged between what was read and what was published);
  2. every published_url returns HTTP 200 and the fetched page contains the
     piece's title (live evidence, not narration);
  3. --operator-read-confirmed was provided (recorded verbatim).

Then: published=true per article, editorial_law_passes.operator_read=true,
observed_at=utc_now, site_build_sha256 recomputed from the LIVE pages, and
digest = stable_digest(receipt minus digest) — canonicalisation identical to
scripts/governance/check_track_status.py and memory_kernel.write_receipts.
"""

import argparse
import html
import json
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

REPO = Path(__file__).resolve().parents[3]
DRAFT = REPO / "reports/darshan/issue_one_receipt.DRAFT.json"
CANONICAL = REPO / "reports/darshan/issue_one_receipt.json"
DARSHAN_PUBLICATION_NETLOC = "amitabhainarunachala.github.io"

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


def sha256_file(p: Path) -> str:
    import hashlib
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--operator-read-confirmed", required=False, default="",
                    help="The operator's own confirmation words. Mandatory.")
    args = ap.parse_args()

    if not args.operator_read_confirmed.strip():
        fail("--operator-read-confirmed is mandatory (the operator-read gate "
             "cannot be sealed silently)")
    if not DRAFT.exists():
        fail(f"draft receipt missing: {DRAFT}")
    if CANONICAL.exists():
        fail(f"{CANONICAL} already exists; refusing to overwrite a sealed receipt")

    receipt = json.loads(DRAFT.read_text(encoding="utf-8"))

    # 1. Repo article content unchanged since assembly.
    for art in receipt["articles"]:
        p = REPO / art["repo_file"]
        if not p.exists():
            fail(f"article file missing: {art['repo_file']}")
        actual = sha256_file(p)
        if actual != art["sha256_md"]:
            fail(f"{art['repo_file']} sha256 changed since assembly "
                 f"({actual[:12]}… != {art['sha256_md'][:12]}…); re-run assembly "
                 "or regenerate the draft receipt so the operator reads what ships")

    # 2. Every article live, title on page.
    live_pages: dict[str, str] = {}
    for art in receipt["articles"]:
        url = art["published_url"]
        safe_url = _validated_publication_url(url)
        try:
            with urllib.request.urlopen(  # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
                safe_url,
                timeout=30,
            ) as resp:
                status = resp.status
                body = resp.read()
        except Exception as exc:
            fail(f"{url} unreachable: {type(exc).__name__}: {exc}")
        if status != 200:
            fail(f"{url} returned HTTP {status}")
        text = html.unescape(body.decode("utf-8", errors="replace"))
        if art["title"] not in text:
            fail(f"{url} is live but does not contain the title "
                 f"{art['title']!r} — wrong or stale page")
        live_pages[url] = stable_digest(text)
        art["published"] = True
        art["publication_evidence"] = (
            f"HTTP 200 + title-on-page verified at seal time; "
            f"page stable_digest {live_pages[url][:16]}…"
        )
        print(f"live  {url}")

    # 3. Seal.
    receipt["receipt_state"] = "SEALED"
    receipt["observed_at"] = utc_now()
    receipt["editorial_law_passes"]["operator_read"] = True
    receipt["editorial_law_passes"]["operator_read_evidence"] = (
        args.operator_read_confirmed.strip()
    )
    receipt["site_build_sha256"] = stable_digest(live_pages)
    receipt["site_build_sha256_kind"] = (
        "live_pages_sealed — stable_digest over {published_url: page_stable_digest} "
        "of every Issue One page fetched HTTP-200 at seal time"
    )
    receipt["pending_operator_actions"] = []
    receipt["digest_policy"] = (
        "digest = stable_digest(receipt minus digest); canonicalisation identical "
        "to scripts/governance/check_track_status.py. Sealed by "
        "reports/darshan/scripts/seal_issue_one_receipt.py after live verification."
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
