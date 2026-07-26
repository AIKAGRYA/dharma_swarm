"""Patch/context helpers for Forge real SWE-bench runs."""
from __future__ import annotations

import re
import subprocess

from dharma_swarm.forge_v1.swebench_real import (
    forge_docker_cli_env,
    instance_image_key,
)


def _target_paths_from_gold(instance: dict) -> list[str]:
    """File paths the gold patch touches. We use the PATHS only (not contents) —
    an agent grepping the repo for the bug would find the same files. This is
    context, not the fix."""
    paths = []
    for line in instance.get("patch", "").splitlines():
        m = re.match(r"^\+\+\+ b/(.+)$", line)
        if m:
            paths.append(m.group(1).strip())
    return paths


def _read_files_from_image(instance: dict, paths: list[str], *, max_chars: int = 400_000) -> dict[str, str]:
    """Read the FULL real file contents AT base_commit from the instance's repo by
    running a throwaway container off the prebuilt image. The repo lives at
    /testbed inside the swebench image. Returns {path: content} (best-effort;
    missing files skipped). This is legitimate working-tree context an agent would
    have — the BUGGY pre-fix source, never the gold patch.

    NOTE: we do NOT truncate to a small window — the bug can be anywhere in the
    file (django/db/models/base.py is ~1900 lines and the fix is near line 850),
    and Gemini's input window is ~1M tokens, so the whole file fits. Truncating
    the context to the first 16KB was why the first run's patches were garbage:
    the model never saw the buggy region. max_chars is just a sanity ceiling."""
    image = instance_image_key(instance)
    out: dict[str, str] = {}
    # Make sure the image is present (pull is slow but one-time; the eval will
    # need it anyway). Best-effort: if pull fails we just skip context.
    subprocess.run(
        ["docker", "pull", image],
        capture_output=True,
        text=True,
        timeout=1800,
        env=forge_docker_cli_env(),
    )
    for p in paths:
        try:
            proc = subprocess.run(
                ["docker", "run", "--rm", "--entrypoint", "cat", image, f"/testbed/{p}"],
                capture_output=True,
                text=True,
                timeout=300,
                env=forge_docker_cli_env(),
            )
        except subprocess.TimeoutExpired:
            continue
        if proc.returncode == 0 and proc.stdout:
            content = proc.stdout
            if len(content) > max_chars:
                content = content[:max_chars] + "\n# ... (file truncated at sanity ceiling)\n"
            out[p] = content
    return out


# --------------------------------------------------------------------------- #
# Repair prompt + patch parsing (unified-diff oriented, swebench-shaped)
# --------------------------------------------------------------------------- #
def build_repair_prompt(instance: dict, file_context: dict[str, str]) -> str:
    """Ask the model for COMPACT SEARCH/REPLACE edits (Aider edit-block format).

    We deliberately do NOT ask for a unified diff (LLM-authored diffs fail at
    `git apply`: miscounted `@@` line counts, drifted context, mid-hunk
    truncation) NOR for the whole corrected file (a ~1900-line/78KB module is too
    much output for slower families — GLM-5.1 on Ollama Cloud TIMED OUT at 240s
    re-emitting it). Instead the model returns small SEARCH/REPLACE blocks: the
    exact original snippet and its replacement. WE apply them to the real base
    content by exact string match, then compute a guaranteed-applicable unified
    diff with difflib. The model only writes the few changed lines — tiny output,
    works across families — and never does diff bookkeeping."""
    repo = instance["repo"]
    problem = instance["problem_statement"]
    ctx_blocks = []
    for path, content in file_context.items():
        ctx_blocks.append(
            f"### File `{path}` (current buggy contents at this commit):\n"
            f"```python\n{content}\n```"
        )
    ctx = "\n\n".join(ctx_blocks) if ctx_blocks else "(no file context available)"
    example_path = next(iter(file_context), "path/to/file.py")
    return (
        f"You are fixing a real bug in the `{repo}` repository.\n\n"
        f"## Bug report / problem statement\n{problem}\n\n"
        f"## Source file(s) you may edit\n{ctx}\n\n"
        "## Your task\n"
        "Make the MINIMAL change needed to fix the bug. Do NOT touch tests. Output "
        "must be valid Python.\n\n"
        "IMPORTANT: Do NOT explain your reasoning, do NOT restate the file, and do NOT "
        "say what you are about to do. Your ENTIRE response must be the edit block(s) "
        "below and nothing else.\n\n"
        "Return ONE OR MORE edits in this exact SEARCH/REPLACE format, and NOTHING "
        "else:\n\n"
        f"<<<<<<< SEARCH path={example_path}\n"
        "<the exact original lines to find, copied verbatim from the file above>\n"
        "=======\n"
        "<the replacement lines>\n"
        ">>>>>>> REPLACE\n\n"
        "Rules: the SEARCH text MUST appear verbatim (character-for-character, same "
        "indentation) in the named file so it can be located exactly. Keep each "
        "SEARCH block small (just the lines you change plus a little surrounding "
        "context to make it unique). Use one block per distinct edit. Put the file "
        "path on the SEARCH marker line as shown.\n"
    )


# Aider-style edit block: <<<<<<< SEARCH path=... \n search \n ======= \n replace \n >>>>>>> REPLACE
_EDIT_BLOCK_RE = re.compile(
    r"<{5,}\s*SEARCH\s+path=([^\s`]+)\s*\n(.*?)\n={5,}\s*\n(.*?)\n>{5,}\s*REPLACE",
    re.DOTALL,
)
# Back-compat: a fenced block whose info line carries `path=<path>` -> full file.
_FILE_BLOCK_RE = re.compile(
    r"```[a-zA-Z0-9_]*\s+path=([^\s`]+)\s*\n(.*?)```", re.DOTALL
)


def parse_edit_blocks(text: str) -> list[tuple[str, str, str]]:
    """Pull (path, search, replace) tuples from the model's SEARCH/REPLACE blocks."""
    out = []
    for m in _EDIT_BLOCK_RE.finditer(text or ""):
        out.append((m.group(1).strip(), m.group(2), m.group(3)))
    return out


def apply_edit_blocks(
    base_files: dict[str, str], edits: list[tuple[str, str, str]]
) -> tuple[dict[str, str], str | None]:
    """Apply SEARCH/REPLACE edits to base file contents by EXACT string match.
    Returns (new_files, error). error is set (and new_files empty) if any edit's
    SEARCH text is not found verbatim or is ambiguous (appears >1 time) — we never
    guess, because a wrong match would corrupt the file silently."""
    new_files = {p: c for p, c in base_files.items()}
    applied = 0
    for path, search, replace in edits:
        if path not in new_files:
            return {}, f"edit targets unknown file {path!r}"
        content = new_files[path]
        count = content.count(search)
        if count == 0:
            return {}, f"SEARCH text not found verbatim in {path}"
        if count > 1:
            return {}, f"SEARCH text ambiguous ({count}x) in {path}"
        new_files[path] = content.replace(search, replace, 1)
        applied += 1
    if applied == 0:
        return {}, "no edits applied"
    # Keep only files that actually changed.
    changed = {p: c for p, c in new_files.items() if c != base_files.get(p)}
    if not changed:
        return {}, "edits produced no change"
    return changed, None


def parse_full_files(text: str) -> dict[str, str]:
    """Back-compat: pull {path: full_content} from `path=` fenced blocks (used if a
    model ignores the SEARCH/REPLACE format and returns whole files instead)."""
    out: dict[str, str] = {}
    for m in _FILE_BLOCK_RE.finditer(text or ""):
        path = m.group(1).strip()
        body = m.group(2)
        if not body.endswith("\n"):
            body += "\n"
        out[path] = body
    return out


def compute_unified_diff(base_files: dict[str, str], new_files: dict[str, str]) -> str:
    """Compute a git-style unified diff from base->new file contents using difflib
    — guaranteed to apply (correct line counts/context by construction) because we
    generate it, not the model. Only paths present in BOTH (and actually changed)
    produce hunks. swebench applies the result with `git apply -p1`."""
    import difflib

    chunks: list[str] = []
    for path, new_content in new_files.items():
        base_content = base_files.get(path)
        if base_content is None or new_content == base_content:
            continue
        diff = difflib.unified_diff(
            base_content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            n=3,
        )
        body = "".join(diff)
        if not body:
            continue
        chunks.append(f"diff --git a/{path} b/{path}\n{body}")
    out = "".join(chunks)
    if out and not out.endswith("\n"):
        out += "\n"
    return out
