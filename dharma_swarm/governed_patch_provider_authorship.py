"""Non-authorizing provider-authorship evidence for governed patches."""
from __future__ import annotations
import asyncio
import inspect
import os
import re
import stat
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Final, Protocol
from dharma_swarm.forge_v1.run_real_patch import (
    apply_edit_blocks,
    compute_unified_diff,
)
from dharma_swarm.foundry.patches import (
    PatchReplayError,
    scoped_regular_file,
    write_immutable_beneath,
)
from dharma_swarm.governed_patch_candidate_bundle import (
    CandidateBundle,
    build_candidate_bundle,
    candidate_bundle_sha256,
    load_candidate_bundle_artifact,
)
from dharma_swarm.governed_patch_evidence import (
    GOVERNED_PATCH_REQUEST_V2_SCHEMA,
    ExclusiveEvidenceWriteIndeterminateError,
    GovernedPatchEvidenceError,
    GovernedPatchRequest,
    NativePatchBindings,
    _RAW_SHA_RE,
    _canonical_json_bytes,
    _closed_shape,
    _create_owner_only_exclusive,
    _parse_json,
    _raw_sha256, _read_regular_bounded,
    _validate_bindings, _validate_token,
    canonical_semantic_intent_sha256,
)
from dharma_swarm.model_pool import default_for_provider, required_provider_model_id
from dharma_swarm.models import LLMRequest, LLMResponse, ProviderType
from dharma_swarm.ollama_config import OLLAMA_CLOUD_BASE_URL
from dharma_swarm.runtime_provider import RuntimeProviderConfig, runtime_provider_transport_identity
PROVIDER_AUTHORSHIP_SCHEMA: Final[str] = "dharma.governed_patch.provider_authorship.v1"
PROVIDER_CALL_LOCATOR_SCHEMA: Final[str] = "dharma.governed_patch.provider_call_locator.v1"
PROVIDER_CALL_CLAIM_SCHEMA: Final[str] = "dharma.governed_patch.provider_call_claim.v1"
PROVIDER_RESPONSE_SCHEMA: Final[str] = "dharma.governed_patch.provider_response_snapshot.v1"
REQUESTED_PROVIDER: Final[str] = ProviderType.OLLAMA.value
REQUESTED_WIRE_MODEL: Final[str] = default_for_provider(ProviderType.ZHIPU)
REQUESTED_MODEL: Final[str] = required_provider_model_id(REQUESTED_WIRE_MODEL, ProviderType.OLLAMA)
REQUESTED_TRANSPORT: Final[str] = "cloud_api"
SERVED_MODELS: Final[frozenset[str]] = frozenset((REQUESTED_WIRE_MODEL, REQUESTED_MODEL))
ACCEPTED_STOP_REASONS: Final[frozenset[str]] = frozenset({"completed", "end_turn", "stop"})
DEFAULT_PROVIDER_TIMEOUT_SECONDS: Final[float] = 600.0
MAX_PROVIDER_RESPONSE_BYTES: Final[int] = 2 * 1024 * 1024
_MAX_PROMPT_BYTES = 3 * 1024 * 1024
_RECEIPT_KEYS = frozenset("schema_version receipt_sha256 status reason_code reason_detail_sha256 provider_call_id native_bindings request_content_sha256 source_sha256 semantic_intent_sha256 task_snapshot_sha256 semantic_artifact_sha256 authorized_source_path requested_provider requested_model requested_transport endpoint_identity served_model prompt_sha256 response_sha256 diff_sha256 candidate_bundle_sha256 usage stop_reason provider_tools_allowed repository_effect_authorized repository_effect_performed mission_control_completion_authorized".split())
_LOCATOR_KEYS = frozenset("schema_version provider_call_id request_content_sha256 semantic_artifact_sha256 receipt_sha256 status candidate_bundle_sha256 repository_effect_authorized".split())
_USAGE_KEYS = frozenset({"prompt_tokens", "completion_tokens", "total_tokens"})
_RESPONSE_KEYS = frozenset("schema_version content served_model provider usage tool_calls stop_reason".split())
_RECEIPT_DATA_FIELDS = "receipt_sha256 status reason_code reason_detail_sha256 provider_call_id native_bindings request_content_sha256 source_sha256 semantic_intent_sha256 task_snapshot_sha256 semantic_artifact_sha256 authorized_source_path requested_provider requested_model requested_transport endpoint_identity served_model prompt_sha256 response_sha256 diff_sha256 candidate_bundle_sha256 usage stop_reason".split()
_FULL_EDIT_RE = re.compile(
    r"\A<<<<<<< SEARCH path=([^\s`]+)\n(.*?)\n=======\n(.*?)\n>>>>>>> REPLACE\n?\Z",
    re.DOTALL)
class _ProviderClient(Protocol):
    async def complete(self, request: LLMRequest) -> LLMResponse: ...
    async def close(self) -> None: ...
class ProviderCallIndeterminateError(GovernedPatchEvidenceError):
    """A call may have crossed the provider boundary without a terminal locator."""
class ProviderCallEvidenceState(str, Enum):
    ABSENT = "absent"
    CLAIMED = "claimed"
    TERMINAL = "terminal"
@dataclass(frozen=True, slots=True)
class ProviderUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    def to_dict(self) -> dict[str, int]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }
@dataclass(frozen=True, slots=True)
class ProviderSession:
    client: _ProviderClient
    endpoint_identity: str
@dataclass(frozen=True, slots=True)
class ProviderAuthorshipReceipt:
    evidence_root: Path
    relative_dir: str
    receipt_sha256: str
    status: str
    reason_code: str | None
    reason_detail_sha256: str | None
    provider_call_id: str
    native_bindings: NativePatchBindings
    request_content_sha256: str
    source_sha256: str
    semantic_intent_sha256: str
    task_snapshot_sha256: str
    semantic_artifact_sha256: str
    authorized_source_path: str
    requested_provider: str
    requested_model: str
    requested_transport: str
    endpoint_identity: str
    served_model: str | None
    prompt_sha256: str
    response_sha256: str | None
    diff_sha256: str | None
    candidate_bundle_sha256: str | None
    usage: ProviderUsage
    stop_reason: str | None
    @property
    def receipt_path(self) -> Path:
        return self.evidence_root / self.relative_dir / "receipt.json"
    def to_dict(self) -> dict[str, Any]:
        payload = {name: getattr(self, name) for name in _RECEIPT_DATA_FIELDS}
        payload["native_bindings"] = self.native_bindings.to_dict()
        payload["usage"] = self.usage.to_dict()
        return {
            "schema_version": PROVIDER_AUTHORSHIP_SCHEMA,
            **payload,
            "provider_tools_allowed": False,
            "repository_effect_authorized": False,
            "repository_effect_performed": False,
            "mission_control_completion_authorized": False,
        }
@dataclass(frozen=True, slots=True)
class ProviderAuthorshipResult:
    receipt: ProviderAuthorshipReceipt
    candidate_bundle: CandidateBundle | None
    @property
    def authored(self) -> bool:
        return self.receipt.status == "authored"
    def to_dict(self) -> dict[str, Any]:
        return self.receipt.to_dict()
_REQUESTED_ENDPOINT_IDENTITY = runtime_provider_transport_identity(
    RuntimeProviderConfig(
        provider=ProviderType.OLLAMA,
        base_url=OLLAMA_CLOUD_BASE_URL,
        transport_mode=REQUESTED_TRANSPORT,
    )
)
_UNRESOLVED_ENDPOINT_IDENTITY = "unresolved:provider_session"
def _safe_evidence_root(evidence_root: Path, repo_root: Path) -> Path:
    root = Path(evidence_root).expanduser().resolve(strict=False)
    repo = Path(repo_root).resolve(strict=True)
    if root == repo or root.is_relative_to(repo) or repo.is_relative_to(root):
        raise GovernedPatchEvidenceError(
            "provider evidence root must be outside and disjoint from the canonical repository"
        )
    return root
def _write_immutable(root: Path, relative: str, data: bytes) -> Path:
    try:
        return write_immutable_beneath(root, relative, data)
    except PatchReplayError as exc:
        raise GovernedPatchEvidenceError(str(exc)) from exc
def _read_immutable(
    root: Path, relative: str, *, field: str, max_bytes: int,
) -> bytes:
    path = scoped_regular_file(
        root,
        relative,
        field=field,
        error_type=GovernedPatchEvidenceError,
    )
    return _read_regular_bounded(path, field=field, max_bytes=max_bytes)
def _write_blob(root: Path, data: bytes) -> str:
    digest = _raw_sha256(data)
    _write_immutable(root, f"provider_authorship/blobs/sha256/{digest}", data)
    return digest
def _read_blob(root: Path, digest: str, *, field: str, max_bytes: int) -> bytes:
    if type(digest) is not str or _RAW_SHA_RE.fullmatch(digest) is None:
        raise GovernedPatchEvidenceError(f"invalid {field} digest")
    data = _read_immutable(
        root,
        f"provider_authorship/blobs/sha256/{digest}",
        field=field,
        max_bytes=max_bytes,
    )
    if _raw_sha256(data) != digest:
        raise GovernedPatchEvidenceError(f"{field} digest mismatch")
    return data
def provider_call_id_for_request(request: GovernedPatchRequest) -> str:
    if type(request) is not GovernedPatchRequest:
        raise GovernedPatchEvidenceError("request must be a GovernedPatchRequest")
    return f"provider_call:{request.request_content_sha256}"
def _validate_request_and_artifact(
    request: GovernedPatchRequest,
    semantic_artifact_sha256: str,
) -> None:
    if type(request) is not GovernedPatchRequest:
        raise GovernedPatchEvidenceError("request must be a GovernedPatchRequest")
    _validate_bindings(request.bindings)
    if (
        request.schema_version != GOVERNED_PATCH_REQUEST_V2_SCHEMA
        or not request.semantic_intent
        or type(request.semantic_intent_sha256) is not str
        or _RAW_SHA_RE.fullmatch(request.semantic_intent_sha256) is None
        or type(request.task_snapshot_sha256) is not str
        or _RAW_SHA_RE.fullmatch(request.task_snapshot_sha256) is None
    ):
        raise GovernedPatchEvidenceError(
            "provider authorship requires a bound governed patch request v2"
        )
    if (
        _raw_sha256(request.request_bytes) != request.request_content_sha256
        or _raw_sha256(request.source_bytes) != request.source_sha256
        or canonical_semantic_intent_sha256(request.semantic_intent)
        != request.semantic_intent_sha256
    ):
        raise GovernedPatchEvidenceError(
            "provider request/source snapshot binding mismatch"
        )
    if (
        type(semantic_artifact_sha256) is not str
        or _RAW_SHA_RE.fullmatch(semantic_artifact_sha256) is None
    ):
        raise GovernedPatchEvidenceError("invalid semantic_artifact_sha256")
def _build_prompt(request: GovernedPatchRequest) -> str:
    source = request.source_bytes.decode("utf-8")
    prompt = (
        "Produce the single minimal source edit that satisfies the semantic intent.\n"
        "Your whole response MUST be exactly one SEARCH/REPLACE block, with no "
        "prose, markdown fence, second block, or tool call.\n"
        f"Authorized path: {request.authorized_source_path}\n"
        f"Semantic intent:\n{request.semantic_intent}\n"
        f"Exact source (sha256={request.source_sha256}):\n{source}\n"
        "Required response shape:\n"
        f"<<<<<<< SEARCH path={request.authorized_source_path}\n"
        "<unique nonempty exact source text>\n"
        "=======\n"
        "<replacement text>\n"
        ">>>>>>> REPLACE\n"
    )
    if len(prompt.encode("utf-8")) > _MAX_PROMPT_BYTES:
        raise GovernedPatchEvidenceError("provider prompt exceeds bounded size")
    return prompt
def _normalize_usage(value: Any) -> ProviderUsage:
    raw = value if type(value) is dict else {}
    def token(name: str) -> int:
        item = raw.get(name, 0)
        return item if type(item) is int and item >= 0 else 0
    prompt = token("prompt_tokens")
    completion = token("completion_tokens")
    total = token("total_tokens")
    if total < max(prompt, completion):
        total = prompt + completion
    return ProviderUsage(prompt, completion, total)
def _failure_digest(exc: BaseException | str) -> str:
    detail = str(exc) if type(exc) is str else f"{type(exc).__name__}:{exc}"
    return _raw_sha256(detail.encode("utf-8", errors="replace"))
def _response_bytes(response: LLMResponse, usage: ProviderUsage) -> bytes:
    if type(response.content) is not str:
        raise GovernedPatchEvidenceError("provider response content is not a string")
    try:
        content = response.content.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise GovernedPatchEvidenceError(
            "provider response is not strict UTF-8"
        ) from exc
    if not content or len(content) > MAX_PROVIDER_RESPONSE_BYTES:
        raise GovernedPatchEvidenceError(
            "provider response is empty or exceeds bounded size"
        )
    data = _canonical_json_bytes(
        {
            "schema_version": PROVIDER_RESPONSE_SCHEMA,
            "content": response.content,
            "served_model": response.model,
            "provider": response.provider,
            "usage": usage.to_dict(),
            "tool_calls": response.tool_calls,
            "stop_reason": response.stop_reason,
        },
        surface="provider response snapshot",
    )
    if len(data) > MAX_PROVIDER_RESPONSE_BYTES:
        raise GovernedPatchEvidenceError(
            "provider response snapshot exceeds bounded size"
        )
    return data
def _parse_exact_edit(request: GovernedPatchRequest, response_text: str) -> str:
    if any(
        response_text.count(marker) != 1
        for marker in (
            "<<<<<<< SEARCH path=",
            "=======",
            ">>>>>>> REPLACE",
        )
    ):
        raise GovernedPatchEvidenceError(
            "provider response must contain exactly one edit marker set"
        )
    match = _FULL_EDIT_RE.fullmatch(response_text)
    if match is None:
        raise GovernedPatchEvidenceError(
            "provider response must be exactly one whole SEARCH/REPLACE block"
        )
    path, search, replacement = match.groups()
    if path != request.authorized_source_path:
        raise GovernedPatchEvidenceError(
            "provider edit path does not match authorized source"
        )
    if not search:
        raise GovernedPatchEvidenceError("provider SEARCH text must be nonempty")
    source = request.source_bytes.decode("utf-8")
    first = source.find(search)
    if first < 0 or source.find(search, first + 1) >= 0:
        raise GovernedPatchEvidenceError(
            "provider SEARCH text must occur exactly once"
        )
    if replacement == search:
        raise GovernedPatchEvidenceError("provider replacement is a no-op")
    changed, error = apply_edit_blocks(
        {request.authorized_source_path: source},
        [(path, search, replacement)],
    )
    if error is not None:
        raise GovernedPatchEvidenceError(error)
    diff = compute_unified_diff(
        {request.authorized_source_path: source},
        changed,
    )
    if not diff:
        raise GovernedPatchEvidenceError("provider edit produced no diff")
    return diff
def _bootstrap_provider() -> ProviderSession:
    from scripts.runtime.governed_patch_provider import (
        bootstrap_exact_ollama_provider,
    )
    return bootstrap_exact_ollama_provider()
async def _open_provider(factory: Any) -> ProviderSession:
    created = factory()
    if inspect.isawaitable(created):
        created = await created
    if not isinstance(created, ProviderSession):
        raise GovernedPatchEvidenceError(
            "provider factory must return an explicit ProviderSession"
        )
    if (
        not callable(getattr(created.client, "complete", None))
        or not callable(getattr(created.client, "close", None))
        or type(created.endpoint_identity) is not str
        or not created.endpoint_identity
        or len(created.endpoint_identity) > 2048
        or any(char in created.endpoint_identity for char in "\x00\r\n")
    ):
        raise GovernedPatchEvidenceError("provider factory returned invalid session")
    return created
def _receipt_from_body(root: Path, body: dict[str, Any]) -> ProviderAuthorshipReceipt:
    receipt_sha = _raw_sha256(
        _canonical_json_bytes(body, surface="provider authorship receipt")
    )
    payload = {**body, "receipt_sha256": receipt_sha}
    receipt_bytes = _canonical_json_bytes(
        payload,
        surface="provider authorship receipt",
    )
    relative_dir = f"provider_authorship/receipts/sha256/{receipt_sha}"
    _write_immutable(root, f"{relative_dir}/receipt.json", receipt_bytes)
    return _receipt_from_payload(root, relative_dir, payload)
def _receipt_from_payload(
    root: Path, relative_dir: str, payload: dict[str, Any],
) -> ProviderAuthorshipReceipt:
    values = {name: payload[name] for name in _RECEIPT_DATA_FIELDS}
    values["native_bindings"] = NativePatchBindings(**payload["native_bindings"])
    values["usage"] = ProviderUsage(**payload["usage"])
    return ProviderAuthorshipReceipt(
        evidence_root=root, relative_dir=relative_dir, **values
    )
def _persist_locator(
    root: Path,
    receipt: ProviderAuthorshipReceipt,
) -> None:
    locator = {
        "schema_version": PROVIDER_CALL_LOCATOR_SCHEMA,
        "provider_call_id": receipt.provider_call_id,
        "request_content_sha256": receipt.request_content_sha256,
        "semantic_artifact_sha256": receipt.semantic_artifact_sha256,
        "receipt_sha256": receipt.receipt_sha256,
        "status": receipt.status,
        "candidate_bundle_sha256": receipt.candidate_bundle_sha256,
        "repository_effect_authorized": False,
    }
    _write_immutable(
        root,
        f"provider_authorship/calls/{receipt.provider_call_id}.json",
        _canonical_json_bytes(locator, surface="provider call locator"),
    )
def _persist_receipt(
    *,
    root: Path, request: GovernedPatchRequest, semantic_artifact_sha256: str,
    provider_call_id: str, prompt_sha256: str, status: str,
    reason_code: str | None, reason_detail_sha256: str | None,
    endpoint_identity: str, served_model: str | None,
    response_sha256: str | None, diff_sha256: str | None,
    candidate_bundle_sha256_value: str | None,
    usage: ProviderUsage, stop_reason: str | None,
) -> ProviderAuthorshipReceipt:
    body = {
        "schema_version": PROVIDER_AUTHORSHIP_SCHEMA, "status": status,
        "reason_code": reason_code, "reason_detail_sha256": reason_detail_sha256,
        "provider_call_id": provider_call_id,
        "native_bindings": request.bindings.to_dict(),
        "request_content_sha256": request.request_content_sha256,
        "source_sha256": request.source_sha256, "semantic_intent_sha256": request.semantic_intent_sha256,
        "task_snapshot_sha256": request.task_snapshot_sha256,
        "semantic_artifact_sha256": semantic_artifact_sha256,
        "authorized_source_path": request.authorized_source_path,
        "requested_provider": REQUESTED_PROVIDER, "requested_model": REQUESTED_MODEL,
        "requested_transport": REQUESTED_TRANSPORT, "endpoint_identity": endpoint_identity,
        "served_model": served_model, "prompt_sha256": prompt_sha256,
        "response_sha256": response_sha256, "diff_sha256": diff_sha256,
        "candidate_bundle_sha256": candidate_bundle_sha256_value,
        "usage": usage.to_dict(), "stop_reason": stop_reason,
        "provider_tools_allowed": False, "repository_effect_authorized": False,
        "repository_effect_performed": False,
        "mission_control_completion_authorized": False,
    }
    receipt = _receipt_from_body(root, body)
    _persist_locator(root, receipt)
    return receipt
def _read_optional_call_file(root: Path, branch: str, call_id: str) -> bytes | None:
    """Read one owner-only call file through no-follow directory handles."""
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        directory_fd = os.open(root, directory_flags)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise GovernedPatchEvidenceError("provider evidence root is unsafe") from exc
    try:
        for part in ("provider_authorship", branch):
            try:
                next_fd = os.open(part, directory_flags, dir_fd=directory_fd)
            except FileNotFoundError:
                return None
            except OSError as exc:
                raise GovernedPatchEvidenceError("provider call parent is unsafe") from exc
            metadata = os.fstat(next_fd)
            if metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) & 0o077:
                os.close(next_fd)
                raise GovernedPatchEvidenceError("provider call parent is not owner-only")
            os.close(directory_fd)
            directory_fd = next_fd
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        try:
            descriptor = os.open(f"{call_id}.json", flags, dir_fd=directory_fd)
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise GovernedPatchEvidenceError("provider call evidence is unsafe") from exc
        metadata = os.fstat(descriptor)
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid()
                or stat.S_IMODE(metadata.st_mode) != 0o600 or metadata.st_size > 64 * 1024):
            os.close(descriptor)
            raise GovernedPatchEvidenceError("provider call evidence is not owner-only bounded data")
        with os.fdopen(descriptor, "rb") as handle:
            return handle.read(64 * 1024 + 1)
    finally:
        os.close(directory_fd)
def _call_claim_bytes(
    request: GovernedPatchRequest, semantic_artifact_sha256: str,
    provider_call_id: str, prompt_sha256: str,
) -> bytes:
    return _canonical_json_bytes(
        {
            "schema_version": PROVIDER_CALL_CLAIM_SCHEMA, "provider_call_id": provider_call_id,
            "request_content_sha256": request.request_content_sha256,
            "semantic_artifact_sha256": semantic_artifact_sha256, "prompt_sha256": prompt_sha256,
            "requested_provider": REQUESTED_PROVIDER, "requested_model": REQUESTED_MODEL,
            "requested_transport": REQUESTED_TRANSPORT, "repository_effect_authorized": False,
            "mission_control_completion_authorized": False,
        },
        surface="provider call claim",
    )
def _create_call_claim(
    root: Path, *, request: GovernedPatchRequest, semantic_artifact_sha256: str,
    provider_call_id: str, prompt_sha256: str,
) -> bool:
    """Exclusively persist the irreversible pre-call ownership marker."""
    data = _call_claim_bytes(request, semantic_artifact_sha256, provider_call_id, prompt_sha256)
    try:
        return _create_owner_only_exclusive(
            root, f"provider_authorship/claims/{provider_call_id}.json", data,
        )
    except ExclusiveEvidenceWriteIndeterminateError as exc:
        raise ProviderCallIndeterminateError(str(exc)) from exc
def _decode_canonical_object(raw: bytes, *, surface: str) -> dict[str, Any]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise GovernedPatchEvidenceError(f"{surface} is not UTF-8") from exc
    value = _parse_json(text, surface=surface)
    if type(value) is not dict:
        raise GovernedPatchEvidenceError(f"{surface} must be a JSON object")
    if raw != _canonical_json_bytes(value, surface=surface):
        raise GovernedPatchEvidenceError(f"{surface} is not canonical JSON")
    return value
def _decode_call_locator(
    raw: bytes, *, request: GovernedPatchRequest,
    semantic_artifact_sha256: str, call_id: str,
) -> dict[str, Any]:
    locator = _decode_canonical_object(raw, surface="provider call locator")
    _closed_shape(locator, _LOCATOR_KEYS, "provider call locator")
    candidate = locator["candidate_bundle_sha256"]
    if (
        locator["schema_version"] != PROVIDER_CALL_LOCATOR_SCHEMA
        or locator["provider_call_id"] != call_id
        or locator["request_content_sha256"] != request.request_content_sha256
        or locator["semantic_artifact_sha256"] != semantic_artifact_sha256
        or locator["repository_effect_authorized"] is not False
        or type(locator["receipt_sha256"]) is not str
        or _RAW_SHA_RE.fullmatch(locator["receipt_sha256"]) is None
        or type(locator["status"]) is not str or locator["status"] not in {"authored", "refused"}
        or (locator["status"] == "authored" and (type(candidate) is not str or _RAW_SHA_RE.fullmatch(candidate) is None))
        or (locator["status"] == "refused" and candidate is not None)
    ):
        raise GovernedPatchEvidenceError("provider call locator binding mismatch")
    return locator
def inspect_provider_call_evidence(
    request: GovernedPatchRequest, *, evidence_root: Path,
    semantic_artifact_sha256: str,
    provider_call_id: str | None = None,
) -> ProviderCallEvidenceState:
    """Classify exact, read-only provider evidence without granting authority."""
    _validate_request_and_artifact(request, semantic_artifact_sha256)
    call_id = provider_call_id or provider_call_id_for_request(request)
    _validate_token(call_id, "provider_call_id")
    root = _safe_evidence_root(evidence_root, request.repo_root)
    claim = _read_optional_call_file(root, "claims", call_id)
    locator = _read_optional_call_file(root, "calls", call_id)
    if claim is not None:
        prompt_sha = _raw_sha256(_build_prompt(request).encode("utf-8"))
        if claim != _call_claim_bytes(request, semantic_artifact_sha256, call_id, prompt_sha):
            raise GovernedPatchEvidenceError("provider call claim binding mismatch")
    if locator is not None:
        if claim is None:
            raise GovernedPatchEvidenceError("terminal locator lacks durable provider claim")
        _decode_call_locator(locator, request=request, semantic_artifact_sha256=semantic_artifact_sha256, call_id=call_id)
        return ProviderCallEvidenceState.TERMINAL
    if claim is not None:
        return ProviderCallEvidenceState.CLAIMED
    return ProviderCallEvidenceState.ABSENT
def load_provider_authorship_receipt(
    evidence_root: Path, receipt_sha256: str, *, request: GovernedPatchRequest,
    semantic_artifact_sha256: str,
) -> ProviderAuthorshipReceipt:
    _validate_request_and_artifact(request, semantic_artifact_sha256)
    if type(receipt_sha256) is not str or _RAW_SHA_RE.fullmatch(receipt_sha256) is None:
        raise GovernedPatchEvidenceError("provider receipt sha256 is malformed")
    root = _safe_evidence_root(evidence_root, request.repo_root)
    relative_dir = f"provider_authorship/receipts/sha256/{receipt_sha256}"
    raw = _read_immutable(
        root,
        f"{relative_dir}/receipt.json",
        field="provider authorship receipt",
        max_bytes=256 * 1024,
    )
    payload = _decode_canonical_object(raw, surface="provider authorship receipt")
    _closed_shape(payload, _RECEIPT_KEYS, "provider authorship receipt")
    native_payload = payload["native_bindings"]
    if (type(native_payload) is not dict
            or frozenset(native_payload) != frozenset(request.bindings.to_dict())
            or type(payload["usage"]) is not dict):
        raise GovernedPatchEvidenceError("provider receipt nested shape is malformed")
    _closed_shape(payload["usage"], _USAGE_KEYS, "provider usage")
    body = {key: value for key, value in payload.items() if key != "receipt_sha256"}
    if (
        payload.get("receipt_sha256") != receipt_sha256
        or _raw_sha256(
            _canonical_json_bytes(body, surface="provider authorship receipt")
        )
        != receipt_sha256
    ):
        raise GovernedPatchEvidenceError("provider receipt content address mismatch")
    receipt = _receipt_from_payload(root, relative_dir, payload)
    return verify_provider_authorship_receipt(
        receipt,
        request=request,
        semantic_artifact_sha256=semantic_artifact_sha256,
    )
def verify_provider_authorship_receipt(
    receipt: ProviderAuthorshipReceipt, *, request: GovernedPatchRequest,
    semantic_artifact_sha256: str,
) -> ProviderAuthorshipReceipt:
    _validate_request_and_artifact(request, semantic_artifact_sha256)
    if type(receipt) is not ProviderAuthorshipReceipt:
        raise GovernedPatchEvidenceError("provider receipt has the wrong type")
    payload = receipt.to_dict()
    _closed_shape(payload, _RECEIPT_KEYS, "provider authorship receipt")
    body = {key: value for key, value in payload.items() if key != "receipt_sha256"}
    if (
        payload["schema_version"] != PROVIDER_AUTHORSHIP_SCHEMA
        or _raw_sha256(
            _canonical_json_bytes(body, surface="provider authorship receipt")
        )
        != receipt.receipt_sha256
        or receipt.relative_dir
        != f"provider_authorship/receipts/sha256/{receipt.receipt_sha256}"
    ):
        raise GovernedPatchEvidenceError("provider receipt content address mismatch")
    raw = _read_immutable(
        receipt.evidence_root,
        f"{receipt.relative_dir}/receipt.json",
        field="provider authorship receipt",
        max_bytes=256 * 1024,
    )
    if raw != _canonical_json_bytes(payload, surface="provider authorship receipt"):
        raise GovernedPatchEvidenceError("provider authorship receipt tampered")
    _validate_bindings(receipt.native_bindings)
    if receipt.semantic_artifact_sha256 != semantic_artifact_sha256:
        raise GovernedPatchEvidenceError(
            "provider receipt semantic artifact binding mismatch"
        )
    if (
        receipt.native_bindings != request.bindings
        or receipt.request_content_sha256 != request.request_content_sha256
        or receipt.source_sha256 != request.source_sha256
        or receipt.semantic_intent_sha256 != request.semantic_intent_sha256
        or receipt.task_snapshot_sha256 != request.task_snapshot_sha256
        or receipt.authorized_source_path != request.authorized_source_path
        or receipt.requested_provider != REQUESTED_PROVIDER
        or receipt.requested_model != REQUESTED_MODEL
        or receipt.requested_transport != REQUESTED_TRANSPORT
        or type(receipt.endpoint_identity) is not str
        or not receipt.endpoint_identity
        or len(receipt.endpoint_identity) > 2048
        or any(char in receipt.endpoint_identity for char in "\x00\r\n")
    ):
        raise GovernedPatchEvidenceError("provider receipt request/route binding mismatch")
    _validate_token(receipt.provider_call_id, "provider_call_id")
    usage_payload = payload["usage"]
    if type(usage_payload) is not dict:
        raise GovernedPatchEvidenceError("provider usage is malformed")
    _closed_shape(usage_payload, _USAGE_KEYS, "provider usage")
    if any(type(value) is not int or value < 0 for value in usage_payload.values()):
        raise GovernedPatchEvidenceError("provider usage is malformed")
    prompt = _read_blob(
        receipt.evidence_root,
        receipt.prompt_sha256,
        field="provider prompt",
        max_bytes=_MAX_PROMPT_BYTES,
    )
    if prompt != _build_prompt(request).encode("utf-8"):
        raise GovernedPatchEvidenceError("provider prompt binding mismatch")
    response_payload: dict[str, Any] | None = None
    if receipt.response_sha256 is not None:
        response_raw = _read_blob(
            receipt.evidence_root,
            receipt.response_sha256,
            field="provider response",
            max_bytes=MAX_PROVIDER_RESPONSE_BYTES,
        )
        response_payload = _decode_canonical_object(
            response_raw,
            surface="provider response snapshot",
        )
        _closed_shape(
            response_payload,
            _RESPONSE_KEYS,
            "provider response snapshot",
        )
        if (
            response_payload["schema_version"] != PROVIDER_RESPONSE_SCHEMA
            or response_payload["served_model"] != receipt.served_model
            or type(response_payload["provider"]) is not str
            or response_payload["usage"] != receipt.usage.to_dict()
            or response_payload["stop_reason"] != receipt.stop_reason
        ):
            raise GovernedPatchEvidenceError(
                "provider response snapshot binding mismatch"
            )
    diff_data: bytes | None = None
    if receipt.diff_sha256 is not None:
        diff_data = _read_blob(
            receipt.evidence_root,
            receipt.diff_sha256,
            field="provider diff",
            max_bytes=MAX_PROVIDER_RESPONSE_BYTES,
        )
        if not diff_data:
            raise GovernedPatchEvidenceError("provider diff is empty")
    if any(
        payload[field] is not False
        for field in (
            "provider_tools_allowed",
            "repository_effect_authorized",
            "repository_effect_performed",
            "mission_control_completion_authorized",
        )
    ):
        raise GovernedPatchEvidenceError("provider receipt claims forbidden authority")
    if receipt.status == "authored":
        if (
            receipt.reason_code is not None
            or receipt.reason_detail_sha256 is not None
            or receipt.endpoint_identity != _REQUESTED_ENDPOINT_IDENTITY
            or receipt.served_model not in SERVED_MODELS
            or receipt.stop_reason not in ACCEPTED_STOP_REASONS
            or receipt.response_sha256 is None
            or receipt.diff_sha256 is None
            or type(receipt.candidate_bundle_sha256) is not str
            or _RAW_SHA_RE.fullmatch(receipt.candidate_bundle_sha256) is None
        ):
            raise GovernedPatchEvidenceError("authored provider receipt is malformed")
        if (
            response_payload is None
            or response_payload["provider"] != REQUESTED_PROVIDER
            or response_payload["tool_calls"] != []
            or type(response_payload["content"]) is not str
            or diff_data is None
        ):
            raise GovernedPatchEvidenceError(
                "authored provider response snapshot is malformed"
            )
        expected_diff = _parse_exact_edit(request, response_payload["content"])
        if expected_diff.encode("utf-8") != diff_data:
            raise GovernedPatchEvidenceError(
                "provider response/diff binding mismatch"
            )
    elif receipt.status == "refused":
        if (
            type(receipt.reason_code) is not str
            or not receipt.reason_code
            or type(receipt.reason_detail_sha256) is not str
            or _RAW_SHA_RE.fullmatch(receipt.reason_detail_sha256) is None
            or receipt.candidate_bundle_sha256 is not None
        ):
            raise GovernedPatchEvidenceError("provider refusal receipt is malformed")
        known_routes = {_REQUESTED_ENDPOINT_IDENTITY, _UNRESOLVED_ENDPOINT_IDENTITY}
        valid_route = receipt.endpoint_identity in known_routes
        if receipt.reason_code == "provider_route_mismatch":
            valid_route = not valid_route
        if not valid_route:
            raise GovernedPatchEvidenceError(
                "provider route-mismatch refusal is malformed"
            )
    else:
        raise GovernedPatchEvidenceError("unsupported provider receipt status")
    return receipt
def recover_provider_authorship_result(
    request: GovernedPatchRequest, *, evidence_root: Path,
    semantic_artifact_sha256: str,
    provider_call_id: str | None = None,
) -> ProviderAuthorshipResult:
    _validate_request_and_artifact(request, semantic_artifact_sha256)
    call_id = provider_call_id or provider_call_id_for_request(request)
    _validate_token(call_id, "provider_call_id")
    root = _safe_evidence_root(evidence_root, request.repo_root)
    state = inspect_provider_call_evidence(
        request,
        evidence_root=root,
        semantic_artifact_sha256=semantic_artifact_sha256,
        provider_call_id=call_id,
    )
    if state is ProviderCallEvidenceState.CLAIMED:
        raise ProviderCallIndeterminateError(
            "provider call claim exists without a terminal locator; redrive forbidden"
        )
    if state is ProviderCallEvidenceState.ABSENT:
        raise GovernedPatchEvidenceError("provider call evidence is absent")
    locator_raw = _read_optional_call_file(root, "calls", call_id)
    if locator_raw is None:
        raise GovernedPatchEvidenceError("provider terminal locator disappeared")
    locator = _decode_call_locator(
        locator_raw,
        request=request,
        semantic_artifact_sha256=semantic_artifact_sha256,
        call_id=call_id,
    )
    receipt = load_provider_authorship_receipt(
        root,
        locator["receipt_sha256"],
        request=request,
        semantic_artifact_sha256=semantic_artifact_sha256,
    )
    if (
        locator["status"] != receipt.status
        or locator["candidate_bundle_sha256"]
        != receipt.candidate_bundle_sha256
        or receipt.provider_call_id != call_id
    ):
        raise GovernedPatchEvidenceError("provider call locator/receipt mismatch")
    if receipt.status == "refused":
        return ProviderAuthorshipResult(receipt, None)
    diff_bytes = _read_blob(
        root,
        receipt.diff_sha256 or "",
        field="provider diff",
        max_bytes=MAX_PROVIDER_RESPONSE_BYTES,
    )
    try:
        diff_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise GovernedPatchEvidenceError("provider diff is not UTF-8") from exc
    candidate = load_candidate_bundle_artifact(
        root,
        receipt.candidate_bundle_sha256 or "",
        repo_root=request.repo_root,
        expected=request.bindings,
        accepted_base_sha=request.bindings.base_sha,
    )
    if (
        candidate.request_content_sha256 != request.request_content_sha256
        or candidate.source_sha256 != request.source_sha256
        or candidate.authorized_source_path != request.authorized_source_path
        or candidate.semantic_intent_sha256 != request.semantic_intent_sha256
        or candidate.task_snapshot_sha256 != request.task_snapshot_sha256
        or candidate.semantic_artifact_sha256 != semantic_artifact_sha256
        or candidate.diff_sha256 != receipt.diff_sha256
        or candidate.diff_bytes != diff_bytes
    ):
        raise GovernedPatchEvidenceError("provider receipt/candidate binding mismatch")
    return ProviderAuthorshipResult(receipt, candidate)
async def author_governed_patch(
    request: GovernedPatchRequest,
    *,
    evidence_root: Path,
    semantic_artifact_sha256: str,
    provider_call_id: str | None = None,
    provider_factory: Any | None = None,
    timeout_seconds: float = DEFAULT_PROVIDER_TIMEOUT_SECONDS,
) -> ProviderAuthorshipResult:
    _validate_request_and_artifact(request, semantic_artifact_sha256)
    call_id = provider_call_id or provider_call_id_for_request(request)
    _validate_token(call_id, "provider_call_id")
    if type(timeout_seconds) not in {int, float} or not 0 < float(timeout_seconds) < float("inf"):
        raise GovernedPatchEvidenceError("provider timeout must be positive and finite")
    root = _safe_evidence_root(evidence_root, request.repo_root)
    state = inspect_provider_call_evidence(
        request,
        evidence_root=root,
        semantic_artifact_sha256=semantic_artifact_sha256,
        provider_call_id=call_id,
    )
    if state is ProviderCallEvidenceState.TERMINAL:
        return recover_provider_authorship_result(
            request,
            evidence_root=root,
            semantic_artifact_sha256=semantic_artifact_sha256,
            provider_call_id=call_id,
        )
    if state is ProviderCallEvidenceState.CLAIMED:
        raise ProviderCallIndeterminateError(
            "provider call claim exists without a terminal locator; redrive forbidden"
        )
    prompt = _build_prompt(request)
    prompt_sha = _write_blob(root, prompt.encode("utf-8"))
    if not _create_call_claim(
        root,
        request=request,
        semantic_artifact_sha256=semantic_artifact_sha256,
        provider_call_id=call_id,
        prompt_sha256=prompt_sha,
    ):
        state = inspect_provider_call_evidence(
            request,
            evidence_root=root,
            semantic_artifact_sha256=semantic_artifact_sha256,
            provider_call_id=call_id,
        )
        if state is ProviderCallEvidenceState.TERMINAL:
            return recover_provider_authorship_result(
                request,
                evidence_root=root,
                semantic_artifact_sha256=semantic_artifact_sha256,
                provider_call_id=call_id,
            )
        raise ProviderCallIndeterminateError(
            "provider call claim exists without a terminal locator; redrive forbidden"
        )
    endpoint_identity = _UNRESOLVED_ENDPOINT_IDENTITY
    response: LLMResponse | None = None
    response_sha: str | None = None
    diff_sha: str | None = None
    usage = ProviderUsage()
    session: ProviderSession | None = None
    failure: tuple[str, BaseException | str] | None = None
    try:
        session = await _open_provider(provider_factory or _bootstrap_provider)
        endpoint_identity = session.endpoint_identity
        if endpoint_identity != _REQUESTED_ENDPOINT_IDENTITY:
            failure = (
                "provider_route_mismatch",
                "provider endpoint identity is not canonical Ollama cloud",
            )
        else:
            llm_request = LLMRequest(
                model=REQUESTED_MODEL,
                messages=[{"role": "user", "content": prompt}],
                system=(
                    "You are a constrained patch author. Return one exact edit "
                    "block and never call tools."
                ),
                max_tokens=8192,
                temperature=0.0,
                tools=[],
            )
            response = await asyncio.wait_for(
                session.client.complete(llm_request),
                timeout=float(timeout_seconds),
            )
            if not isinstance(response, LLMResponse):
                raise GovernedPatchEvidenceError(
                    "provider returned an invalid response type"
                )
            usage = _normalize_usage(response.usage)
            response_bytes = _response_bytes(response, usage)
            response_sha = _write_blob(root, response_bytes)
    except TimeoutError as exc:
        failure = ("provider_timeout", exc)
    except Exception as exc:
        failure = ("provider_error", exc)
    finally:
        if session is not None:
            try:
                await session.client.close()
            except Exception as exc:
                if failure is None:
                    failure = ("provider_close_failed", exc)
    served_model = response.model if response is not None else None
    stop_reason = response.stop_reason if response is not None else None
    def refuse(reason_code: str, detail: BaseException | str) -> ProviderAuthorshipResult:
        receipt = _persist_receipt(
            root=root,
            request=request,
            semantic_artifact_sha256=semantic_artifact_sha256,
            provider_call_id=call_id,
            prompt_sha256=prompt_sha,
            status="refused",
            reason_code=reason_code,
            reason_detail_sha256=_failure_digest(detail),
            endpoint_identity=endpoint_identity,
            served_model=served_model,
            response_sha256=response_sha,
            diff_sha256=diff_sha,
            candidate_bundle_sha256_value=None,
            usage=usage,
            stop_reason=stop_reason,
        )
        return ProviderAuthorshipResult(receipt, None)
    if failure is not None:
        return refuse(*failure)
    assert response is not None
    if response.provider != REQUESTED_PROVIDER:
        return refuse("served_provider_mismatch", response.provider or "missing")
    if response.tool_calls:
        return refuse("provider_tools_returned", "provider returned tool calls")
    if response.model not in SERVED_MODELS:
        return refuse("served_model_mismatch", response.model)
    if response.stop_reason not in ACCEPTED_STOP_REASONS:
        return refuse(
            "unacceptable_stop_reason",
            str(response.stop_reason or "missing"),
        )
    try:
        diff = _parse_exact_edit(request, response.content)
        diff_bytes = diff.encode("utf-8")
        diff_sha = _write_blob(root, diff_bytes)
        planned_bundle = candidate_bundle_sha256(
            request,
            diff,
            semantic_artifact_sha256=semantic_artifact_sha256,
        )
    except Exception as exc:
        return refuse("invalid_provider_edit", exc)
    candidate = build_candidate_bundle(
        request,
        diff,
        bundle_root=root,
        semantic_artifact_sha256=semantic_artifact_sha256,
    )
    if candidate.bundle_sha256 != planned_bundle:
        raise GovernedPatchEvidenceError("persisted candidate digest changed")
    receipt = _persist_receipt(
        root=root,
        request=request,
        semantic_artifact_sha256=semantic_artifact_sha256,
        provider_call_id=call_id,
        prompt_sha256=prompt_sha,
        status="authored",
        reason_code=None,
        reason_detail_sha256=None,
        endpoint_identity=endpoint_identity,
        served_model=response.model,
        response_sha256=response_sha,
        diff_sha256=diff_sha,
        candidate_bundle_sha256_value=planned_bundle,
        usage=usage,
        stop_reason=response.stop_reason,
    )
    return ProviderAuthorshipResult(receipt, candidate)
__all__ = "ACCEPTED_STOP_REASONS DEFAULT_PROVIDER_TIMEOUT_SECONDS PROVIDER_AUTHORSHIP_SCHEMA PROVIDER_CALL_CLAIM_SCHEMA PROVIDER_CALL_LOCATOR_SCHEMA ProviderCallEvidenceState ProviderCallIndeterminateError ProviderAuthorshipReceipt ProviderAuthorshipResult ProviderSession ProviderUsage REQUESTED_MODEL REQUESTED_PROVIDER REQUESTED_TRANSPORT REQUESTED_WIRE_MODEL SERVED_MODELS author_governed_patch inspect_provider_call_evidence load_provider_authorship_receipt provider_call_id_for_request recover_provider_authorship_result verify_provider_authorship_receipt".split()
