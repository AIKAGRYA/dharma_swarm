"""Post-cutoff PR-suite harvester for Forge fresh taskbed intake.

The harvester discovers candidate tasks only.  It does not claim that changed
tests are FAIL_TO_PASS.  Rows become CONFIRM-eligible only after a later validator
adds explicit ``fail_to_pass`` evidence consumed by ``fresh_task_oracle``.
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .fresh_task_oracle import parse_timestamp

SCHEMA_VERSION = "forge_v2.post_cutoff_pr_suite_harvester.v1"
DEFAULT_API_ROOT = "https://api.github.com"

Fetcher = Callable[[str, dict[str, str]], Any]


def _headers(token: str | None = None) -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "dharma-forge-pr-suite-harvester",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def token_from_env_spec(env_spec: str) -> str | None:
    """Return the first non-empty token from a comma-separated env-var spec.

    The harvester historically defaulted to ``GITHUB_TOKEN`` only, while many
    GitHub CLI shells expose ``GH_TOKEN``.  Accepting both avoids silently
    dropping into the low unauthenticated rate limit during overnight harvests.
    """

    for name in str(env_spec or "").split(","):
        token = os.environ.get(name.strip())
        if token:
            return token
    return None


def fetch_json(url: str, headers: dict[str, str]) -> Any:
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - fixed GitHub API URL.
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"GitHub API error {exc.code}: {body}") from exc


def _api_url(api_root: str, path: str, params: dict[str, Any] | None = None) -> str:
    query = urllib.parse.urlencode(params or {})
    return f"{api_root.rstrip('/')}/{path.lstrip('/')}" + (f"?{query}" if query else "")


def _is_test_path(path: str) -> bool:
    lowered = path.lower()
    name = lowered.rsplit("/", 1)[-1]
    return (
        lowered.startswith("tests/")
        or "/tests/" in lowered
        or name.startswith("test_")
        or name.endswith("_test.py")
        or name.endswith(".test.ts")
        or name.endswith(".test.tsx")
        or name.endswith(".spec.ts")
        or name.endswith(".spec.tsx")
    )


def _parse_repo(value: str) -> str:
    repo = value.strip().strip("/")
    if repo.startswith("https://github.com/"):
        repo = repo[len("https://github.com/"):]
    parts = repo.split("/")
    if len(parts) < 2 or not parts[0] or not parts[1]:
        raise ValueError(f"repo must be owner/name: {value!r}")
    return "/".join(parts[:2])


def _page_urls(api_root: str, path: str, *, per_page: int, max_pages: int, **params: Any) -> list[str]:
    return [
        _api_url(api_root, path, {**params, "per_page": per_page, "page": page})
        for page in range(1, max_pages + 1)
    ]


def harvest_repo(
    repo: str,
    *,
    since: datetime,
    limit: int,
    api_root: str = DEFAULT_API_ROOT,
    token: str | None = None,
    fetcher: Fetcher = fetch_json,
    max_pages: int = 5,
) -> list[dict[str, Any]]:
    repo = _parse_repo(repo)
    headers = _headers(token)
    rows: list[dict[str, Any]] = []
    for url in _page_urls(
        api_root,
        f"/repos/{repo}/pulls",
        per_page=50,
        max_pages=max_pages,
        state="closed",
        sort="updated",
        direction="desc",
    ):
        pulls = fetcher(url, headers)
        if not isinstance(pulls, list):
            continue
        if not pulls:
            break
        for pr in pulls:
            if len(rows) >= limit:
                return rows
            if not isinstance(pr, dict):
                continue
            merged_at = parse_timestamp(pr.get("merged_at"))
            if merged_at is None or merged_at <= since:
                continue
            number = int(pr.get("number") or 0)
            if number <= 0:
                continue
            files = _pull_files(
                repo,
                number,
                api_root=api_root,
                headers=headers,
                fetcher=fetcher,
            )
            test_files = [path for path in files if _is_test_path(path)]
            if not test_files:
                continue
            rows.append(
                {
                    "schema": SCHEMA_VERSION,
                    "source_kind": "post_cutoff_pr_suite_candidate",
                    "repo": repo,
                    "pr_number": number,
                    "created_at": pr.get("created_at") or "",
                    "merged_at": pr.get("merged_at") or "",
                    "title": pr.get("title") or "",
                    "html_url": pr.get("html_url") or "",
                    "base_sha": ((pr.get("base") or {}) or {}).get("sha") or "",
                    "head_sha": ((pr.get("head") or {}) or {}).get("sha") or "",
                    "merge_commit_sha": pr.get("merge_commit_sha") or "",
                    "test_files": test_files,
                    "fail_to_pass": [],
                    "validation_state": "needs_fail_to_pass_validation",
                    "requires_fail_to_pass_validation": True,
                    "harvested_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }
            )
    return rows


def _pull_files(
    repo: str,
    number: int,
    *,
    api_root: str,
    headers: dict[str, str],
    fetcher: Fetcher,
) -> list[str]:
    out: list[str] = []
    for url in _page_urls(api_root, f"/repos/{repo}/pulls/{number}/files", per_page=100, max_pages=3):
        rows = fetcher(url, headers)
        if not isinstance(rows, list) or not rows:
            break
        for row in rows:
            if isinstance(row, dict) and row.get("filename"):
                out.append(str(row["filename"]))
    return out


def harvest_repos(
    repos: list[str],
    *,
    since: str | datetime,
    limit_per_repo: int,
    api_root: str = DEFAULT_API_ROOT,
    token: str | None = None,
    fetcher: Fetcher = fetch_json,
    max_pages: int = 5,
) -> dict[str, Any]:
    cutoff = parse_timestamp(since) if isinstance(since, str) else since
    if cutoff is None:
        raise ValueError("since must be an ISO timestamp or date")
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=timezone.utc)
    cutoff = cutoff.astimezone(timezone.utc)
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for repo in repos:
        try:
            rows.extend(
                harvest_repo(
                    repo,
                    since=cutoff,
                    limit=limit_per_repo,
                    api_root=api_root,
                    token=token,
                    fetcher=fetcher,
                    max_pages=max_pages,
                )
            )
        except Exception as exc:  # noqa: BLE001 - receipt per repo, continue.
            errors.append({"repo": repo, "error": f"{type(exc).__name__}: {exc}"})
    return {
        "schema": SCHEMA_VERSION,
        "since": cutoff.isoformat().replace("+00:00", "Z"),
        "repos": repos,
        "candidate_count": len(rows),
        "rows": rows,
        "errors": errors,
    }


def write_manifest(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True, default=str) + "\n" for row in rows))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Harvest post-cutoff PR-suite candidate tasks")
    parser.add_argument("--repo", action="append", default=[], help="GitHub repo owner/name; repeatable")
    parser.add_argument("--repos-file", default="", help="Optional newline-delimited repo list")
    parser.add_argument("--since", required=True, help="ISO timestamp/date cutoff")
    parser.add_argument("--limit-per-repo", type=int, default=25)
    parser.add_argument("--max-pages", type=int, default=5)
    parser.add_argument("--api-root", default=DEFAULT_API_ROOT)
    parser.add_argument("--github-token-env", default="GITHUB_TOKEN,GH_TOKEN")
    parser.add_argument("--out", required=True, help="Output JSONL manifest")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repos = list(args.repo)
    if args.repos_file:
        repos.extend(
            line.strip()
            for line in Path(args.repos_file).expanduser().read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        )
    if not repos:
        raise SystemExit("at least one --repo or --repos-file entry is required")
    summary = harvest_repos(
        repos,
        since=args.since,
        limit_per_repo=args.limit_per_repo,
        api_root=args.api_root,
        token=token_from_env_spec(args.github_token_env),
        max_pages=args.max_pages,
    )
    write_manifest(Path(args.out).expanduser(), list(summary["rows"]))
    if args.json:
        print(json.dumps({**summary, "rows": summary["rows"][:20]}, indent=2, sort_keys=True, default=str))
    else:
        print(
            f"[pr_suite_harvester] candidates={summary['candidate_count']} errors={len(summary['errors'])} out={args.out}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
