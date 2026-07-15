from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "pr-dedupe.yml"
DOCOPS_RECONCILE = REPO_ROOT / ".github" / "workflows" / "docops-reconcile-main.yml"


def _snapshot_filter() -> str:
    text = WORKFLOW.read_text(encoding="utf-8")
    match = re.search(
        r"^\s*SNAPSHOT_FILTER=\"\$\(cat <<'JQ'\n"
        r"(?P<program>.*?)"
        r"^\s*JQ\n^\s*\)\"",
        text,
        flags=re.DOTALL | re.MULTILINE,
    )
    assert match is not None, "snapshot filter must be an extractable jq program"
    return match.group("program")


def _matching_numbers(rows: list[dict[str, object]]) -> list[int]:
    result = subprocess.run(
        ["jq", "-c", _snapshot_filter(), "--arg", "repo_owner", "owner"],
        input=json.dumps(rows),
        text=True,
        capture_output=True,
        check=True,
    )
    return [
        int(json.loads(line)["number"])
        for line in result.stdout.splitlines()
        if line.strip()
    ]


def _pr(
    number: int,
    *,
    title: str,
    head: str,
    owner: str = "owner",
) -> dict[str, object]:
    return {
        "number": number,
        "title": title,
        "headRefName": head,
        "headRepositoryOwner": {"login": owner},
    }


def test_snapshot_filter_closes_trusted_unmarked_ops_reports() -> None:
    rows = [
        _pr(
            950,
            title="chore(governance): ops report 2026-07-15 — spine 93.8%",
            head="chore/ops-report-20260715",
        ),
        _pr(
            953,
            title="chore(governance): ops report 2026-07-15T0600Z",
            head="chore/ops-report-20260715T0600",
        ),
    ]

    assert _matching_numbers(rows) == [950, 953]


def test_snapshot_filter_remains_fail_closed_for_untrusted_or_real_work() -> None:
    rows = [
        _pr(
            1,
            title="chore(governance): ops report 2026-07-15",
            head="chore/ops-report-20260715",
            owner="fork-owner",
        ),
        _pr(
            2,
            title="ops report parser implementation",
            head="feature/ops-report-parser",
        ),
        _pr(
            3,
            title="chore(docops): reconcile generated counts",
            head="chore/docops-autorefresh",
        ),
        _pr(
            4,
            title="[automated] ordinary dependency update",
            head="chore/dependency-update",
        ),
    ]

    assert _matching_numbers(rows) == []


def test_docops_reconcile_skips_remote_byte_identical_refresh() -> None:
    text = DOCOPS_RECONCILE.read_text(encoding="utf-8")

    remote_compare = 'git diff --quiet "FETCH_HEAD" --'
    assert remote_compare in text
    assert "Canonical DocOps bytes already match the open rolling PR" in text
    assert text.index(remote_compare) < text.index("git commit")
    assert text.index(remote_compare) < text.index('git push --force origin')
