#!/usr/bin/env python3
"""Regenerate the DRAFT receipt's content hashes after an article edit.

The assembly/hash half of the Issue One pipeline: recomputes each article's
sha256_md from the file on disk, recomputes content_digest =
stable_digest({slug: sha256_md}), refreshes observed_at, and rewrites
reports/darshan/issue_one_receipt.DRAFT.json — after running the same
completeness and path-containment gates the seal script enforces. Run it after
ANY edit to reports/darshan/issue_one/articles/*.md so the DRAFT receipt and
the files stay consistent; the seal script refuses on any mismatch.

    python3 scripts/darshan/refresh_draft_hashes.py
"""

import importlib.util
import json
import sys
from pathlib import Path

_SEAL_PATH = Path(__file__).resolve().parent / "seal_issue_one_receipt.py"
_spec = importlib.util.spec_from_file_location("darshan_issue_one_seal", _SEAL_PATH)
assert _spec is not None and _spec.loader is not None
seal = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(seal)


def main() -> None:
    if not seal.DRAFT.exists():
        print(f"draft receipt missing: {seal.DRAFT}", file=sys.stderr)
        sys.exit(1)
    receipt = json.loads(seal.DRAFT.read_text(encoding="utf-8"))
    seal._check_completeness(
        receipt, seal._manifest_slugs(seal.MANIFEST.read_text(encoding="utf-8"))
    )
    changed = 0
    for art in receipt["articles"]:
        p = seal._validated_repo_file(art["repo_file"])
        if not p.exists():
            print(f"article file missing: {art['repo_file']}", file=sys.stderr)
            sys.exit(1)
        actual = seal.sha256_file(p)
        if actual != art["sha256_md"]:
            print(f"rehash {art['slug']}: {art['sha256_md'][:12]}… -> {actual[:12]}…")
            art["sha256_md"] = actual
            changed += 1
    receipt["content_digest"] = seal.stable_digest(
        {a["slug"]: a["sha256_md"] for a in receipt["articles"]}
    )
    receipt["observed_at"] = seal.utc_now()
    seal.DRAFT.write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
    )
    print(f"refreshed {seal.DRAFT} ({changed} article hash(es) updated; "
          f"content_digest {receipt['content_digest'][:16]}…)")


if __name__ == "__main__":
    main()
