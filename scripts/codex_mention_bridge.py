#!/usr/bin/env python3
"""Local webhook bridge for GitHub @codex PR comments.

The GitHub workflow forwards mention events here. This server verifies the
shared token, fetches PR context with gh, runs Codex CLI once, and posts the
result back to the PR conversation.
"""

from __future__ import annotations

import argparse
import hmac
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


COMMENT_LIMIT = 62_000
DEFAULT_MAX_DIFF_CHARS = 120_000
MAX_EVENT_BYTES = 2_000_000


@dataclass(frozen=True)
class BridgeConfig:
    repo_path: Path
    token: str
    model: str
    mention_handle: str
    host: str
    port: int
    allowed_repos: frozenset[str]
    max_diff_chars: int
    codex_timeout: int
    dry_run: bool


@dataclass(frozen=True)
class MentionEvent:
    event_name: str
    repo_full_name: str
    pr_number: int
    comment_body: str
    comment_url: str
    author_login: str
    author_association: str
    inline_path: str | None = None
    inline_diff_hunk: str | None = None


review_lock = threading.Lock()


def log(message: str) -> None:
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{stamp}] {message}", flush=True)


def run_cmd(
    args: list[str],
    *,
    cwd: Path,
    timeout: int = 120,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(cwd),
        input=input_text,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def require_success(result: subprocess.CompletedProcess[str], label: str) -> str:
    if result.returncode == 0:
        return result.stdout
    detail = result.stderr.strip() or result.stdout.strip() or "no output"
    raise RuntimeError(f"{label} failed with exit {result.returncode}: {detail}")


def gh_json(config: BridgeConfig, args: list[str], *, timeout: int = 120) -> Any:
    result = run_cmd(["gh", *args], cwd=config.repo_path, timeout=timeout)
    output = require_success(result, "gh")
    return json.loads(output)


def gh_api_json(
    config: BridgeConfig,
    args: list[str],
    payload: dict[str, Any],
    *,
    timeout: int = 120,
) -> Any:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json") as tmp:
        json.dump(payload, tmp)
        tmp.flush()
        result = run_cmd(
            ["gh", "api", *args, "--input", tmp.name],
            cwd=config.repo_path,
            timeout=timeout,
        )
    output = require_success(result, "gh api")
    return json.loads(output) if output.strip() else {}


def detect_local_repo(repo_path: Path) -> str:
    result = run_cmd(
        ["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"],
        cwd=repo_path,
        timeout=30,
    )
    return require_success(result, "gh repo view").strip()


def parse_allowed_repos(raw: str | None, repo_path: Path) -> frozenset[str]:
    if raw:
        return frozenset(part.strip() for part in raw.split(",") if part.strip())
    return frozenset({detect_local_repo(repo_path)})


def extract_event(
    payload: dict[str, Any],
    event_name: str,
    mention_handle: str,
) -> MentionEvent:
    repo = payload.get("repository") or {}
    comment = payload.get("comment") or {}
    user = comment.get("user") or {}
    repo_full_name = str(repo.get("full_name") or "")
    body = str(comment.get("body") or "")

    pr_number: int | None = None
    issue = payload.get("issue") or {}
    pull_request = payload.get("pull_request") or {}
    if issue.get("pull_request"):
        pr_number = int(issue["number"])
    elif pull_request.get("number"):
        pr_number = int(pull_request["number"])

    if not repo_full_name:
        raise ValueError("payload is missing repository.full_name")
    if pr_number is None:
        raise ValueError("mention bridge only handles pull request comments")
    if mention_handle not in body:
        raise ValueError(f"comment does not contain {mention_handle}")

    return MentionEvent(
        event_name=event_name,
        repo_full_name=repo_full_name,
        pr_number=pr_number,
        comment_body=body,
        comment_url=str(comment.get("html_url") or ""),
        author_login=str(user.get("login") or "unknown"),
        author_association=str(comment.get("author_association") or "UNKNOWN"),
        inline_path=comment.get("path"),
        inline_diff_hunk=comment.get("diff_hunk"),
    )


def truncate_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    omitted = len(text) - limit
    return (
        text[:limit]
        + f"\n\n[diff truncated by codex_mention_bridge: omitted {omitted} chars]\n"
    )


def pr_context(config: BridgeConfig, event: MentionEvent) -> tuple[dict[str, Any], str]:
    pr = gh_json(
        config,
        [
            "pr",
            "view",
            str(event.pr_number),
            "--repo",
            event.repo_full_name,
            "--json",
            "number,title,body,author,baseRefName,headRefName,url,additions,deletions,changedFiles,isDraft,state,reviewDecision",
        ],
    )
    diff_result = run_cmd(
        [
            "gh",
            "pr",
            "diff",
            str(event.pr_number),
            "--repo",
            event.repo_full_name,
            "--color",
            "never",
        ],
        cwd=config.repo_path,
        timeout=180,
    )
    diff = require_success(diff_result, "gh pr diff")
    return pr, truncate_text(diff, config.max_diff_chars)


def build_prompt(event: MentionEvent, pr: dict[str, Any], diff: str) -> str:
    author = pr.get("author") or {}
    inline_context = ""
    if event.inline_path or event.inline_diff_hunk:
        inline_context = f"""
Inline comment context:
- Path: {event.inline_path or "unknown"}
- Diff hunk:
{event.inline_diff_hunk or "not provided"}
"""

    return textwrap.dedent(
        f"""
        You are Codex running as a local GitHub PR mention reviewer.

        Return one concise GitHub Markdown comment. Do not modify files. Do not ask
        for permissions. Focus on correctness bugs, security issues, behavioral
        regressions, missing tests, and operational risks. If there are no blocking
        issues, say that clearly and mention any residual test gap.

        Trigger:
        - Event: {event.event_name}
        - Repository: {event.repo_full_name}
        - PR: #{event.pr_number}
        - Requested by: @{event.author_login} ({event.author_association})
        - Comment URL: {event.comment_url or "not provided"}

        User comment:
        {event.comment_body}

        Pull request:
        - Title: {pr.get("title", "")}
        - URL: {pr.get("url", "")}
        - State: {pr.get("state", "")}
        - Draft: {pr.get("isDraft", "")}
        - Author: {author.get("login", "unknown")}
        - Base: {pr.get("baseRefName", "")}
        - Head: {pr.get("headRefName", "")}
        - Changed files: {pr.get("changedFiles", "")}
        - Additions: {pr.get("additions", "")}
        - Deletions: {pr.get("deletions", "")}
        - Review decision: {pr.get("reviewDecision", "")}

        PR body:
        {pr.get("body") or ""}

        {inline_context}
        Unified diff:
        ```diff
        {diff}
        ```
        """
    ).strip()


def comment_body(prefix: str, body: str) -> str:
    full = f"{prefix}\n\n{body.strip()}"
    if len(full) <= COMMENT_LIMIT:
        return full
    return full[: COMMENT_LIMIT - 80] + "\n\n[truncated to fit GitHub comment limit]"


def create_status_comment(config: BridgeConfig, event: MentionEvent) -> int | None:
    body = comment_body(
        "Codex is reviewing this PR locally.",
        f"Triggered by @{event.author_login}: {event.comment_url}",
    )
    if config.dry_run:
        log(f"DRY RUN create comment on {event.repo_full_name}#{event.pr_number}: {body}")
        return None
    response = gh_api_json(
        config,
        [
            "--method",
            "POST",
            f"repos/{event.repo_full_name}/issues/{event.pr_number}/comments",
        ],
        {"body": body},
    )
    comment_id = response.get("id")
    return int(comment_id) if comment_id else None


def update_status_comment(
    config: BridgeConfig,
    event: MentionEvent,
    comment_id: int | None,
    body: str,
) -> None:
    if config.dry_run:
        log(f"DRY RUN final comment on {event.repo_full_name}#{event.pr_number}:\n{body}")
        return
    if comment_id is None:
        gh_api_json(
            config,
            [
                "--method",
                "POST",
                f"repos/{event.repo_full_name}/issues/{event.pr_number}/comments",
            ],
            {"body": body},
        )
        return
    gh_api_json(
        config,
        [
            "--method",
            "PATCH",
            f"repos/{event.repo_full_name}/issues/comments/{comment_id}",
        ],
        {"body": body},
    )


def run_codex(config: BridgeConfig, prompt: str) -> str:
    with tempfile.NamedTemporaryFile("w+", encoding="utf-8", suffix=".md") as output:
        cmd = [
            "codex",
            "exec",
            "-m",
            config.model,
            "-C",
            str(config.repo_path),
            "-s",
            "read-only",
            "-o",
            output.name,
            "-",
        ]
        result = run_cmd(
            cmd,
            cwd=config.repo_path,
            timeout=config.codex_timeout,
            input_text=prompt,
        )
        output.seek(0)
        last_message = output.read().strip()

    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "no output"
        raise RuntimeError(f"codex exec failed with exit {result.returncode}: {detail}")
    return last_message or result.stdout.strip() or "Codex returned no review text."


def process_event(config: BridgeConfig, payload: dict[str, Any], event_name: str) -> None:
    status_comment_id: int | None = None
    try:
        event = extract_event(payload, event_name, config.mention_handle)
        if event.repo_full_name not in config.allowed_repos:
            raise ValueError(
                f"repository {event.repo_full_name} is not in CODEX_ALLOWED_REPOS"
            )

        log(
            f"accepted @{event.author_login} mention for "
            f"{event.repo_full_name}#{event.pr_number}"
        )
        status_comment_id = create_status_comment(config, event)

        with review_lock:
            pr, diff = pr_context(config, event)
            prompt = build_prompt(event, pr, diff)
            review = run_codex(config, prompt)

        final = comment_body(
            f"Codex review for PR #{event.pr_number}",
            f"Triggered by @{event.author_login}: {event.comment_url}\n\n{review}",
        )
        update_status_comment(config, event, status_comment_id, final)
        log(f"posted Codex review for {event.repo_full_name}#{event.pr_number}")
    except Exception as exc:  # noqa: BLE001 - top-level worker must report failures.
        log(f"ERROR processing event: {exc}")
        try:
            repo = (payload.get("repository") or {}).get("full_name")
            issue = payload.get("issue") or payload.get("pull_request") or {}
            pr_number = issue.get("number")
            if repo and pr_number:
                event = MentionEvent(
                    event_name=event_name,
                    repo_full_name=repo,
                    pr_number=int(pr_number),
                    comment_body="",
                    comment_url="",
                    author_login="codex-bridge",
                    author_association="OWNER",
                )
                failure = comment_body(
                    "Codex bridge failed before completing the review.",
                    f"```text\n{exc}\n```",
                )
                update_status_comment(config, event, status_comment_id, failure)
        except Exception as post_exc:  # noqa: BLE001
            log(f"ERROR posting failure comment: {post_exc}")


class Handler(BaseHTTPRequestHandler):
    server: "BridgeServer"

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/github":
            self.send_error(404, "expected POST /github")
            return

        config = self.server.config
        auth = self.headers.get("Authorization", "")
        expected = f"Bearer {config.token}"
        if not hmac.compare_digest(auth, expected):
            self.send_error(401, "invalid Authorization header")
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_error(400, "invalid Content-Length")
            return
        if length <= 0 or length > MAX_EVENT_BYTES:
            self.send_error(413, "invalid event size")
            return

        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            self.send_error(400, f"invalid JSON: {exc}")
            return

        event_name = self.headers.get("X-GitHub-Event", "unknown")
        thread = threading.Thread(
            target=process_event,
            args=(config, payload, event_name),
            daemon=True,
        )
        thread.start()

        self.send_response(202)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status":"accepted"}\n')

    def log_message(self, fmt: str, *args: Any) -> None:
        log(f"{self.address_string()} {fmt % args}")


class BridgeServer(ThreadingHTTPServer):
    def __init__(self, address: tuple[str, int], config: BridgeConfig) -> None:
        super().__init__(address, Handler)
        self.config = config


def build_config(argv: list[str]) -> BridgeConfig:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.environ.get("CODEX_BRIDGE_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("CODEX_BRIDGE_PORT", "8787")))
    parser.add_argument(
        "--repo-path",
        default=os.environ.get("CODEX_BRIDGE_REPO_PATH", os.getcwd()),
        help="Local checkout used for gh and codex commands.",
    )
    parser.add_argument("--dry-run", action="store_true", default=os.environ.get("CODEX_DRY_RUN") == "1")
    args = parser.parse_args(argv)

    token = os.environ.get("CODEX_WEBHOOK_TOKEN", "")
    if not token:
        raise SystemExit("CODEX_WEBHOOK_TOKEN is required")

    repo_path = Path(args.repo_path).expanduser().resolve()
    if not repo_path.exists():
        raise SystemExit(f"repo path does not exist: {repo_path}")

    return BridgeConfig(
        repo_path=repo_path,
        token=token,
        model=os.environ.get("CODEX_MODEL", "gpt-5.5"),
        mention_handle=os.environ.get("CODEX_MENTION_HANDLE", "@terminal-review"),
        host=args.host,
        port=args.port,
        allowed_repos=parse_allowed_repos(os.environ.get("CODEX_ALLOWED_REPOS"), repo_path),
        max_diff_chars=int(os.environ.get("CODEX_MAX_DIFF_CHARS", str(DEFAULT_MAX_DIFF_CHARS))),
        codex_timeout=int(os.environ.get("CODEX_TIMEOUT_SECONDS", "1200")),
        dry_run=bool(args.dry_run),
    )


def main(argv: list[str]) -> int:
    config = build_config(argv)
    server = BridgeServer((config.host, config.port), config)
    log(
        f"listening on http://{config.host}:{config.port}/github "
        f"for {', '.join(sorted(config.allowed_repos))} "
        f"with trigger {config.mention_handle}"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log("shutting down")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
