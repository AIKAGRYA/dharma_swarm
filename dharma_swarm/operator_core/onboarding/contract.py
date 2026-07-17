"""Pure contract helpers for onboarding and the AgentOps packet runner."""

from __future__ import annotations

import copy
import os
import re
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping

from dharma_swarm.memory_kernel.write_receipts import canonical_json, stable_digest, utc_now

from . import _command_lexical as _lexical
from .models import (AUTHORITY_PRECEDENCE, SESSION_ENTRY_SCHEMA_V1, AgentOpsError,
                     ApprovalPolicy, CollisionRecord, CommitPolicy, ConfigError,
                     GateSpec, SessionEntry, WorkPacket)

DEFAULT_GATE_TIMEOUT_SECONDS = 900
DEFAULT_MAX_OUTPUT_CHARS = 30_000
CANONICAL_FIRST_READ: tuple[tuple[str, str], ...] = (
    ("command", "make onboard"), ("file", "CLAUDE.md"), ("file", "docs/governance/SWARM_GENOME.md"),
    ("file", "docs/governance/ACTIVE_TRACK.yaml"), ("file", "docs/governance/ANTI_SLOP_RULES.md"))
_HEX_40 = re.compile(r"^[0-9a-f]{40}$")
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_PLACEHOLDER = re.compile(r"<[^>\r\n]+>")
_GLOB_MAGIC = re.compile(r"[*?[]")
_BANNED_SHELL_TOKENS = {"&&", "||", ";", "|", ">", ">>", "<", "<<"}
_BANNED_SHELL_EXECUTABLES = {"bash", "cmd", "cmd.exe", "env", "fish", "nice", "nohup",
                             "powershell", "pwsh", "sh", "sudo", "timeout", "xargs", "zsh"}
_BANNED_LIVE_COMMAND_TOKENS = {"orchestrate-live", "live-swarm",
                               "autonomy-daemon", "autonomous-daemon"}
_GIT_EXECUTABLE = "git"
_ALLOWED_GIT_STATUS_FORMATS = {"--short", "--porcelain", "--porcelain=v1", "--porcelain=v2"}
_GIT_STATUS_BRANCH = "--branch"
_GIT_DIFF_CHECK = "--check"
_GIT_SEPARATOR = "--"
_ALLOWED_GIT_REV_PARSE_ARGS = {
    ("HEAD",), ("--verify", "HEAD"), ("--show-toplevel",), ("--abbrev-ref", "HEAD"),
}
_GIT_MERGE_BASE_ANCESTOR = "--is-ancestor"
_GIT_LS_FILES_PREFIX = ("--others", "--exclude-standard")

def canonical_first_read_manifest(repo_root: Path) -> list[dict[str, str]]:
    """Return the canonical ordered max-five with deterministic content hashes."""
    root = repo_root.resolve()
    manifest: list[dict[str, str]] = []
    for kind, source in CANONICAL_FIRST_READ:
        if kind == "command":
            content = source
        else:
            path = root / source
            if not path.is_file():
                raise ConfigError(f"canonical required reading is missing: {source}")
            content = path.read_text(encoding="utf-8")
        manifest.append({"kind": kind, "source": source, "sha256": stable_digest(content)})
    return manifest

canonical_packet_json = canonical_json
current_utc_time = utc_now

def _git_admin_dirs(repo_root: Path) -> set[Path]:
    marker = repo_root / ".git"
    roots: set[Path] = {marker.resolve(strict=False)}
    if not marker.is_file():
        return roots
    try:
        first = marker.read_text(encoding="utf-8").splitlines()[0]
        if not first.lower().startswith("gitdir:"):
            return roots
        raw = Path(first.split(":", 1)[1].strip()).expanduser()
        git_dir = (raw if raw.is_absolute() else marker.parent / raw).resolve(strict=False)
        roots.add(git_dir)
        common_file = git_dir / "commondir"
        if common_file.is_file():
            raw = Path(common_file.read_text(encoding="utf-8").strip())
            roots.add((raw if raw.is_absolute() else git_dir / raw).resolve(strict=False))
    except (OSError, IndexError):
        return roots
    return roots

def resolve_external_dir(
    candidate: Path | str, *, repo_root: Path, field: str = "external directory",
) -> Path:
    """Resolve an output root and fail closed if it touches source or git state."""
    root = repo_root.expanduser().resolve()
    raw = Path(candidate).expanduser()
    lexical = raw if raw.is_absolute() else Path(os.path.abspath(raw))
    resolved = raw.resolve(strict=False)
    forbidden = {root, *_git_admin_dirs(root)}
    for boundary in forbidden:
        boundary = boundary.resolve(strict=False)
        if lexical.is_relative_to(boundary) or resolved.is_relative_to(boundary):
            raise ConfigError(f"{field} resolves inside repository or .git: {candidate}")
    return resolved

def packet_digest(payload: Mapping[str, Any]) -> str:
    """Digest the full packet while omitting only its self-referential field."""
    canonical = copy.deepcopy(dict(payload))
    entry = canonical.get("session_entry")
    if not isinstance(entry, dict):
        raise AgentOpsError("session_entry is required to compute packet_digest")
    entry.pop("packet_digest", None)
    return stable_digest(canonical)

def normalize_repo_pattern(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AgentOpsError(f"{field} entries must be non-empty strings")
    candidate = value.strip().replace("\\", "/")
    if candidate.startswith("/"):
        raise AgentOpsError(f"{field} entries must be repo-relative: {value}")
    posix = PurePosixPath(candidate)
    if any(part == ".." for part in posix.parts):
        raise AgentOpsError(f"{field} entries must not traverse upward: {value}")
    normalized = posix.as_posix()
    if normalized in {"", "."}:
        raise AgentOpsError(f"{field} entries must name a file, directory, or glob")
    return normalized

def _glob_regex(pattern: str) -> re.Pattern[str]:
    result: list[str] = ["^"]
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if char == "*":
            if index + 1 < len(pattern) and pattern[index + 1] == "*":
                index += 2
                if index < len(pattern) and pattern[index] == "/":
                    result.append("(?:.*/)?")
                    index += 1
                else:
                    result.append(".*")
                continue
            result.append("[^/]*")
        elif char == "?":
            result.append("[^/]")
        elif char == "[":
            close = pattern.find("]", index + 1)
            if close == -1:
                result.append(r"\[")
            else:
                body = pattern[index + 1:close]
                if body.startswith("!"):
                    body = "^" + body[1:]
                result.append("[" + body.replace("\\", r"\\") + "]")
                index = close
        else:
            result.append(re.escape(char))
        index += 1
    result.append("$")
    return re.compile("".join(result))

def path_matches_pattern(path: str, pattern: str) -> bool:
    normalized = path.replace("\\", "/").removeprefix("./")
    normalized_pattern = pattern.replace("\\", "/").strip().removeprefix("./").rstrip("/")
    if not normalized_pattern:
        return False
    if _glob_regex(normalized_pattern).fullmatch(normalized):
        return True
    if not _GLOB_MAGIC.search(normalized_pattern):
        return normalized.startswith(normalized_pattern + "/")
    return False

def matching_patterns(path: str, patterns: Iterable[str]) -> list[str]:
    return [pattern for pattern in patterns if path_matches_pattern(path, pattern)]

def _validate_git_gate(argv: list[str], env: Mapping[str, str], command: str) -> None:
    identity = _lexical.git_executable_identity(argv[0], _GIT_EXECUTABLE)
    if identity is None:
        return
    if identity != _GIT_EXECUTABLE:
        raise AgentOpsError(f"gate command is not allowed to invoke direct {identity}: {command}")
    if env:
        raise AgentOpsError(f"gate command is not allowed to supply env to Git: {command}")
    if len(argv) < 2:
        raise AgentOpsError(f"gate command is not allowed by direct Git grammar: {command}")
    subcommand, args = argv[1], argv[2:]
    valid = (
        _lexical.valid_git_status(args, _ALLOWED_GIT_STATUS_FORMATS, _GIT_STATUS_BRANCH)
        if subcommand == "status"
        else _lexical.valid_git_diff(args, _GIT_DIFF_CHECK, _GIT_SEPARATOR) if subcommand == "diff"
        else _lexical.valid_git_rev_parse(args, _ALLOWED_GIT_REV_PARSE_ARGS) if subcommand == "rev-parse"
        else _lexical.valid_git_merge_base(args, _GIT_MERGE_BASE_ANCESTOR) if subcommand == "merge-base"
        else _lexical.valid_git_ls_files(args, _GIT_LS_FILES_PREFIX, _GIT_SEPARATOR)
        if subcommand == "ls-files" else False
    )
    if not valid:
        raise AgentOpsError(f"gate command is not allowed by direct Git grammar: {command}")

def _parse_command(command: str, *, env: Mapping[str, str] | None = None) -> list[str]:
    try:
        argv = _lexical.split_command(command)
    except ValueError as exc:
        raise AgentOpsError(f"invalid gate command {command!r}: {exc}") from exc
    if not argv:
        raise AgentOpsError("gate command must not be empty")
    if any(token in _BANNED_SHELL_TOKENS for token in argv):
        raise AgentOpsError(f"gate command uses unsupported shell control token: {command}")
    if _lexical.command_token_forms(argv[0]) & _BANNED_SHELL_EXECUTABLES:
        raise AgentOpsError(f"gate command may not invoke a shell/wrapper executable: {command}")
    if any(_lexical.command_token_forms(token) & _BANNED_LIVE_COMMAND_TOKENS for token in argv):
        raise AgentOpsError(f"gate command appears to invoke live swarm/autonomy: {command}")
    _validate_git_gate(argv, env or {}, command)
    return argv

def parse_gate(raw: Any, index: int, *, require_expected_exit: bool = False) -> GateSpec:
    if isinstance(raw, str):
        if require_expected_exit:
            raise AgentOpsError(f"negative_controls[{index}].expected_exit is required")
        command, name, env = raw.strip(), f"gate-{index + 1}", {}
        timeout, max_output, expected_exit = 900, 30_000, 0
    elif isinstance(raw, dict):
        command = _required_text(raw, "command", prefix=f"commands[{index}].")
        name = raw.get("name", f"gate-{index + 1}")
        if not isinstance(name, str) or not name.strip():
            raise AgentOpsError(f"commands[{index}].name must be a non-empty string")
        name = name.strip()
        env_value = raw.get("env", {})
        if not isinstance(env_value, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in env_value.items()
        ):
            raise AgentOpsError(f"commands[{index}].env must contain string values")
        env = dict(env_value)
        timeout = raw.get("timeout_seconds", DEFAULT_GATE_TIMEOUT_SECONDS)
        max_output = raw.get("max_output_chars", DEFAULT_MAX_OUTPUT_CHARS)
        if require_expected_exit and "expected_exit" not in raw:
            raise AgentOpsError(f"negative_controls[{index}].expected_exit is required")
        expected_exit = raw.get("expected_exit", 0)
    else:
        raise AgentOpsError(f"commands[{index}] must be a command string or object")
    for value, label in ((timeout, "timeout_seconds"), (max_output, "max_output_chars")):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise AgentOpsError(f"commands[{index}].{label} must be a positive integer")
    if isinstance(expected_exit, bool) or not isinstance(expected_exit, int) or not 0 <= expected_exit <= 255:
        raise AgentOpsError(f"commands[{index}].expected_exit must be an integer from 0 to 255")
    argv = _parse_command(command, env=env)
    return GateSpec(name, command, argv, env, expected_exit, timeout, max_output)

def build_gate_environment(gate: GateSpec, inherited: Mapping[str, str]) -> dict[str, str]:
    environment = dict(inherited)
    environment.update(gate.env)
    if _lexical.git_executable_identity(gate.argv[0], _GIT_EXECUTABLE) == _GIT_EXECUTABLE:
        environment = {key: value for key, value in environment.items()
                       if not key.casefold().startswith("git_")}
        environment["GIT_CONFIG_GLOBAL"] = os.devnull
        environment["GIT_CONFIG_NOSYSTEM"] = "1"
        environment["GIT_OPTIONAL_LOCKS"] = "0"
    return environment

def _required_text(data: Mapping[str, Any], field: str, *, prefix: str = "") -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise AgentOpsError(f"{prefix}{field} is required and must be a non-empty string")
    return value.strip()

def _required_bool(data: Mapping[str, Any], field: str) -> bool:
    value = data.get(field)
    if not isinstance(value, bool):
        raise AgentOpsError(f"{field} is required and must be a boolean")
    return value

def _pattern_list(data: Mapping[str, Any], field: str, *, non_empty: bool) -> list[str]:
    value = data.get(field)
    if not isinstance(value, list):
        raise AgentOpsError(f"{field} is required and must be a list")
    result = [normalize_repo_pattern(item, field=field) for item in value]
    if non_empty and not result:
        raise AgentOpsError(f"{field} must contain at least one entry")
    return result

def _list_field(data: Mapping[str, Any], field: str, *, non_empty: bool = False) -> list[Any]:
    value = data.get(field)
    if not isinstance(value, list) or (non_empty and not value):
        qualifier = "non-empty " if non_empty else ""
        raise AgentOpsError(f"{field} is required and must be a {qualifier}list")
    return list(value)

def _parse_session_entry(raw: Any, payload: Mapping[str, Any], packet_id: str) -> SessionEntry:
    if not isinstance(raw, dict):
        raise AgentOpsError("session_entry is required and must be an object")
    schema = _required_text(raw, "schema")
    if schema != SESSION_ENTRY_SCHEMA_V1:
        raise AgentOpsError(f"schema must equal {SESSION_ENTRY_SCHEMA_V1}")
    tools = raw.get("tool_versions")
    if not isinstance(tools, dict) or not tools or not all(
        isinstance(k, str) and k and isinstance(v, str) and v for k, v in tools.items()
    ):
        raise AgentOpsError("tool_versions is required and must contain string versions")
    precedence = _list_field(raw, "authority_precedence")
    if precedence != list(AUTHORITY_PRECEDENCE):
        raise AgentOpsError("authority_precedence must match the canonical order")
    collision_raw = raw.get("collision")
    if not isinstance(collision_raw, dict):
        raise AgentOpsError("collision is required and must be an object")
    collision_status = _required_text(collision_raw, "status", prefix="collision.")
    checked_sha = _required_text(collision_raw, "checked_at_sha", prefix="collision.")
    if not _HEX_40.fullmatch(checked_sha):
        raise AgentOpsError("collision.checked_at_sha must be a 40-character SHA")
    details = _list_field(collision_raw, "details")
    digest = _required_text(raw, "packet_digest")
    if not _HEX_64.fullmatch(digest):
        raise AgentOpsError("packet_digest must be a lowercase 64-character digest")
    if digest != packet_digest(payload):
        raise AgentOpsError("packet_digest does not match canonical packet content")
    closest = _list_field(raw, "closest_existing_implementation", non_empty=True)
    if not all(isinstance(item, str) and item for item in closest):
        raise AgentOpsError("closest_existing_implementation entries must be strings")
    work_packet = _required_text(raw, "work_packet")
    # Bind a conservative generic ``WP-*`` token to the packet id.
    if not re.fullmatch(r"WP-[A-Z0-9]+(?:-[A-Z0-9]+)*", work_packet) or not re.search(
        rf"(?:^|-){re.escape(work_packet)}(?:-|$)", packet_id
    ):
        raise AgentOpsError("session_entry.work_packet does not match packet id")
    return SessionEntry(
        schema=schema, tool_versions=dict(tools),
        authority_precedence=[str(item) for item in precedence],
        work_packet=work_packet,
        active_track=_required_text(raw, "active_track"),
        owner=_required_text(raw, "owner"),
        collision=CollisionRecord(collision_status, checked_sha, details),
        interface_mismatches=_list_field(raw, "interface_mismatches"),
        closest_existing_implementation=[str(item) for item in closest],
        honest_blockers=_list_field(raw, "honest_blockers"),
        rollback=_required_text(raw, "rollback"),
        packet_digest=digest,
    )

def parse_work_packet(data: Mapping[str, Any]) -> WorkPacket:
    packet_id = _required_text(data, "id")
    if not re.fullmatch(r"[A-Za-z0-9_.:-]+", packet_id):
        raise AgentOpsError("id may contain only letters, numbers, '_', '.', ':', and '-'")
    gates_raw = data.get("gates")
    if not isinstance(gates_raw, list):
        raise AgentOpsError("gates is required and must be a list")
    session_raw = data.get("session_entry")
    if session_raw is not None and not gates_raw:
        raise AgentOpsError("session_entry packets require at least one gate")
    if session_raw is not None and _PLACEHOLDER.search(canonical_json(data)):
        raise AgentOpsError("session_entry packet contains an angle-bracket placeholder")
    gates = [parse_gate(item, index) for index, item in enumerate(gates_raw)]
    controls_raw = data.get("negative_controls", [])
    if session_raw is not None and (not isinstance(controls_raw, list) or not controls_raw):
        raise AgentOpsError("negative_controls is required and must be a non-empty list")
    if not isinstance(controls_raw, list):
        raise AgentOpsError("negative_controls must be a list")
    controls = [parse_gate(item, index, require_expected_exit=True)
                for index, item in enumerate(controls_raw)]
    commit_raw, approval_raw = data.get("commit"), data.get("approval")
    if not isinstance(commit_raw, dict):
        raise AgentOpsError("commit is required and must be an object")
    if not isinstance(approval_raw, dict):
        raise AgentOpsError("approval is required and must be an object")
    commit = CommitPolicy(_required_bool(commit_raw, "allowed"),
                          _required_text(commit_raw, "message"))
    approval = ApprovalPolicy(_required_bool(approval_raw, "before_commit"),
                              _required_bool(approval_raw, "before_merge"))
    payload = dict(data)
    session = _parse_session_entry(session_raw, payload, packet_id) if session_raw is not None else None
    return WorkPacket(
        id=packet_id,
        base_ref=_required_text(data, "base_ref"),
        branch=_required_text(data, "branch"),
        worktree=Path(_required_text(data, "worktree")).expanduser(),
        intent=_required_text(data, "intent"),
        allowed_files=_pattern_list(data, "allowed_files", non_empty=True),
        forbidden_files=_pattern_list(data, "forbidden_files", non_empty=False),
        gates=gates, commit=commit, approval=approval,
        negative_controls=controls, session_entry=session,
        raw_payload=copy.deepcopy(payload),
    )

def _contains_pattern(container: str, contained: str) -> bool:
    if container == contained:
        return False
    if not _GLOB_MAGIC.search(container):
        return contained.startswith(container.rstrip("/") + "/")
    if not container.endswith("/**"):
        return False
    prefix = container[:-3].rstrip("/")
    literal_head = re.split(r"[*?[]", contained, maxsplit=1)[0]
    return literal_head.startswith(prefix + "/")

def _segment_tokens(pattern: str) -> list[str]:
    tokens = re.findall(r"\[[^]]*\]|\*|\?|.", pattern)
    return [token for index, token in enumerate(tokens)
            if token != "*" or not index or tokens[index - 1] != "*"]

def _token_accepts(token: str, char: str) -> bool:
    if token in {"*", "?"}:
        return char != "/"
    return (_glob_regex(token).fullmatch(char) is not None
            if token.startswith("[") else token == char)

def _segment_witness(left: str, right: str) -> str | None:
    lt, rt = _segment_tokens(left), _segment_tokens(right)
    alphabet = set("aA0._-x\ue000")
    alphabet.update(ch for ch in left + right if ch not in "*/?[]" and ch != "/")
    queue: list[tuple[int, int, str]] = [(0, 0, "")]
    seen: set[tuple[int, int, bool]] = set()
    while queue:
        li, ri, text = queue.pop(0)
        if (li, ri, bool(text)) in seen:
            continue
        seen.add((li, ri, bool(text)))
        if li == len(lt) and ri == len(rt) and text:
            return text
        if li < len(lt) and lt[li] == "*":
            queue.append((li + 1, ri, text))
        if ri < len(rt) and rt[ri] == "*":
            queue.append((li, ri + 1, text))
        if li == len(lt) or ri == len(rt):
            continue
        for char in sorted(alphabet):
            if _token_accepts(lt[li], char) and _token_accepts(rt[ri], char):
                queue.append((li if lt[li] == "*" else li + 1,
                              ri if rt[ri] == "*" else ri + 1, text + char))
                break
    return None

def _glob_witness(left: str, right: str) -> str | None:
    ls, rs = left.strip("/").split("/"), right.strip("/").split("/")
    queue: list[tuple[int, int, tuple[str, ...]]] = [(0, 0, ())]
    seen: set[tuple[int, int, int]] = set()
    max_parts = (len(ls) + 1) * (len(rs) + 1)
    while queue:
        li, ri, parts = queue.pop(0)
        state = (li, ri, len(parts))
        if state in seen or len(parts) > max_parts:
            continue
        seen.add(state)
        if li == len(ls) and ri == len(rs):
            witness = "/".join(parts)
            if (witness and path_matches_pattern(witness, left)
                    and path_matches_pattern(witness, right)):
                return witness
            continue
        if li < len(ls) and ls[li] == "**":
            queue.append((li + 1, ri, parts))
        if ri < len(rs) and rs[ri] == "**":
            queue.append((li, ri + 1, parts))
        if li == len(ls) or ri == len(rs):
            continue
        if ls[li] == "**" and rs[ri] == "**":
            queue.extend(((li + 1, ri, parts + ("x",)),
                          (li, ri + 1, parts + ("x",))))
            continue
        if ls[li] == "**":
            segment, next_state = _segment_witness("*", rs[ri]), (li, ri + 1)
        elif rs[ri] == "**":
            segment, next_state = _segment_witness(ls[li], "*"), (li + 1, ri)
        else:
            segment, next_state = _segment_witness(ls[li], rs[ri]), (li + 1, ri + 1)
        if segment is not None:
            queue.append((*next_state, parts + (segment,)))
    return None

def _glob_intersection_witness(left: str, right: str) -> str | None:
    lefts = (left, f"{left}/**") if not _GLOB_MAGIC.search(left) else (left,)
    rights = (right, f"{right}/**") if not _GLOB_MAGIC.search(right) else (right,)
    for left_language in lefts:
        for right_language in rights:
            witness = _glob_witness(left_language, right_language)
            if witness is not None:
                return witness
    return None

def detect_surface_collisions(
    allowed_patterns: Iterable[str], sibling_patterns: Mapping[str, Iterable[str]],
    actual_paths: Iterable[str],
) -> list[dict[str, str]]:
    """Return deterministic exact/containment/glob/actual overlap evidence."""
    allowed = sorted(set(allowed_patterns))
    actual = sorted(set(actual_paths))
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str, str]] = set()

    def add(kind: str, ours: str, track: str, theirs: str, path: str = "") -> None:
        key = (kind, ours, track, theirs, path)
        if key not in seen:
            seen.add(key)
            row = {"kind": kind, "allowed_pattern": ours,
                   "sibling_track": track, "sibling_pattern": theirs}
            if path:
                row["path"] = path
            rows.append(row)

    for track, patterns in sorted(sibling_patterns.items()):
        for ours in allowed:
            for theirs in sorted(set(patterns)):
                if ours == theirs:
                    add("exact", ours, track, theirs)
                elif _contains_pattern(ours, theirs) or _contains_pattern(theirs, ours):
                    add("containment", ours, track, theirs)
                elif _glob_intersection_witness(ours, theirs) is not None:
                    add("glob_intersection", ours, track, theirs)
                for path in actual:
                    if path_matches_pattern(path, ours) and path_matches_pattern(path, theirs):
                        add("actual_file_overlap", ours, track, theirs, path)
    return sorted(rows, key=lambda row: (row["kind"], row["sibling_track"],
        row["allowed_pattern"], row["sibling_pattern"], row.get("path", "")))
