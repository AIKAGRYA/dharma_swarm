"""Private mechanical command-lexical helpers for the onboarding contract."""

from __future__ import annotations

import re
import shlex
import unicodedata
from pathlib import PurePosixPath
from typing import Collection

def split_command(command: str) -> list[str]:
    return shlex.split(command)

def _win32_path_canonical(value: str) -> str:
    separator_canonical = value.replace("\\", "/")
    drive = ""
    drive_match = re.match(r"^([a-zA-Z]:)(.*)$", separator_canonical)
    if drive_match is not None:
        drive, separator_canonical = drive_match.groups()
    components: list[str] = []
    for component in separator_canonical.split("/"):
        component = component.split(":", 1)[0]
        while component not in {".", ".."} and component.endswith((" ", ".")):
            component = component[:-1]
        components.append(component)
    return drive + "/".join(components)

def command_token_forms(token: str) -> set[str]:
    raw = token.casefold()
    separator_canonical = raw.replace("\\", "/")
    win32_canonical = _win32_path_canonical(raw)
    basenames = {
        separator_canonical.rsplit("/", 1)[-1],
        win32_canonical.rsplit("/", 1)[-1],
    }
    basenames.update(
        basename[2:]
        for basename in tuple(basenames)
        if re.match(r"^[a-zA-Z]:", basename)
    )
    forms = {raw, separator_canonical, win32_canonical, *basenames}
    forms.update(PurePosixPath(basename).stem for basename in basenames)
    forms.update(basename.rsplit(".", 1)[-1] for basename in basenames)
    return {form.replace("_", "-") for form in forms if form}

def _git_executable_forms(token: str) -> tuple[str, str]:
    raw = token.lower().replace("\\", "/")
    canonical = _win32_path_canonical(raw)
    forms = [
        (leaf[2:] if leaf == value and re.match(r"^[a-zA-Z]:", leaf) else leaf).replace("_", "-")
        for value in (raw, canonical)
        for leaf in (value.rsplit("/", 1)[-1],)
    ]
    return forms[0], forms[1]

def git_executable_identity(token: str, git_executable: str) -> str | None:
    raw, canonical = _git_executable_forms(token)
    allowed = (git_executable, f"{git_executable}.exe")
    path = token.lower().replace("\\", "/")
    compatibility = _git_executable_forms(unicodedata.normalize("NFKC", token))
    trusted = path in allowed or path == "/usr/bin/git" or re.fullmatch(r"c:/program files/git/cmd/git\.exe", path) is not None
    prefixes = (f"{git_executable}-", f"{git_executable}.")
    embedded = raw[2:] if re.match(r"^[a-zA-Z]:", raw) else ""
    embedded_canonical = _win32_path_canonical(embedded)
    alias = (raw != canonical and canonical in allowed) or embedded in allowed or embedded_canonical in allowed
    direct = next(
        (form for form in (raw, canonical, embedded, embedded_canonical) if form.startswith(prefixes) and form != allowed[1]),
        None,
    )
    if alias or direct or (not path.isascii() and any(form in allowed or form.startswith(prefixes) and form != allowed[1] for form in compatibility)):
        return raw
    return git_executable if canonical in allowed and trusted else path if canonical in allowed else None

def _safe_git_operand(value: str) -> bool:
    if not value or value.startswith("-"):
        return False
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        return False
    separator_canonical = value.replace("\\", "/")
    if separator_canonical.startswith("/") or re.match(
        r"^[a-zA-Z]:", separator_canonical
    ):
        return False
    canonical = _win32_path_canonical(value)
    return ".." not in PurePosixPath(canonical).parts

def _safe_git_path(value: str) -> bool:
    return _safe_git_operand(value) and not value.startswith(":")

def _git_revision_path_payload(value: str) -> tuple[bool, str | None]:
    depth = 0
    escaped = False
    for index, char in enumerate(value):
        if depth:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
            continue
        if char == "{" and index and value[index - 1] in {"@", "^"}:
            depth = 1
        elif char == ":":
            return True, value[index + 1:]
    return depth == 0, None

def _strip_git_revision_selectors(value: str) -> str | None:
    outer: list[str] = []
    index = 0
    while index < len(value):
        if index + 1 < len(value) and value[index] in {"@", "^"} and value[index + 1] == "{":
            outer.append(value[index])
            index += 2
            depth = 1
            escaped = False
            while index < len(value) and depth:
                char = value[index]
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                index += 1
            if depth:
                return None
            continue
        outer.append(value[index])
        index += 1
    return "".join(outer)

def _safe_git_revision(value: str) -> bool:
    if not value or value.startswith("-") or any(
        ord(char) < 32 or ord(char) == 127 for char in value
    ):
        return False
    if value.startswith(":/"):
        return len(value) > 2
    if re.match(r"^[a-zA-Z]:", value.replace("\\", "/")):
        return False
    if value.startswith((":(", ":!", ":^")):
        return False
    stage = re.fullmatch(r":[0-3]:(.*)", value)
    if stage is not None:
        return _safe_git_path(stage.group(1))
    if value.startswith(":"):
        return _safe_git_path(value[1:])
    balanced, path = _git_revision_path_payload(value)
    if not balanced:
        return False
    prefix = value if path is None else value[:len(value) - len(path) - 1]
    outer = _strip_git_revision_selectors(prefix)
    return (
        outer is not None
        and _safe_git_operand(outer)
        and (path is None or path == "" or _safe_git_path(path))
    )

def valid_git_status(
    args: list[str], formats: Collection[str], branch_flag: str,
) -> bool:
    return (
        bool(args)
        and args[0] in formats
        and (len(args) == 1 or (len(args) == 2 and args[1] == branch_flag))
    )

def valid_git_diff(args: list[str], check_flag: str, separator_flag: str) -> bool:
    if not args or args[0] != check_flag:
        return False
    operands = args[1:]
    if separator_flag not in operands:
        return all(_safe_git_revision(value) for value in operands)
    if operands.count(separator_flag) != 1:
        return False
    separator = operands.index(separator_flag)
    revisions, paths = operands[:separator], operands[separator + 1:]
    return (
        bool(paths)
        and all(_safe_git_revision(value) for value in revisions)
        and all(_safe_git_path(value) for value in paths)
    )

def valid_git_rev_parse(
    args: list[str], allowed_args: Collection[tuple[str, ...]],
) -> bool:
    return tuple(args) in allowed_args

def valid_git_merge_base(args: list[str], ancestor_flag: str) -> bool:
    return (
        len(args) == 3
        and args[0] == ancestor_flag
        and all(_safe_git_revision(value) for value in args[1:])
    )

def valid_git_ls_files(
    args: list[str], prefix: tuple[str, ...], separator_flag: str,
) -> bool:
    if tuple(args) == prefix:
        return True
    return (
        len(args) > len(prefix) + 1
        and tuple(args[:len(prefix)]) == prefix
        and args[len(prefix)] == separator_flag
        and all(_safe_git_path(value) for value in args[len(prefix) + 1:])
    )
