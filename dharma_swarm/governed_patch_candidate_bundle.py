"""Content-addressed candidate bundle for the governed patch no-effect lane."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any

from dharma_swarm.foundry.evaluator import Candidate, candidate_digest
from dharma_swarm.foundry.patches import (
    PatchReplayError,
    _replay,
    parse_unified_diff,
    scoped_regular_file,
    write_immutable_beneath,
)
from dharma_swarm.governed_patch_evidence import (
    CANDIDATE_BUNDLE_SCHEMA,
    GOVERNED_PATCH_REQUEST_SCHEMA,
    GOVERNED_PATCH_TARGET_ID,
    MAX_SOURCE_BYTES,
    GovernedPatchEvidenceError,
    GovernedPatchRequest,
    NativePatchBindings,
    _FOUNDRY_SHA_RE,
    _MAX_DIFF_BYTES,
    _RAW_SHA_RE,
    _REQUEST_KEYS,
    _bindings_from_payload,
    _canonical_json_bytes,
    _closed_shape,
    _parse_json,
    _raw_sha256,
    _read_regular_bounded,
    _validate_bindings,
    _validate_oracle_argv,
    _validate_source_path,
)

_FILES = frozenset({"request.json", "source.utf8", "candidate.diff", "candidate.json"})
_MANIFEST_KEYS = frozenset(
    """schema_version bundle_sha256 native_bindings authorized_source_path
    oracle_argv request_content_sha256 source_sha256 diff_sha256
    candidate_digest target_id files repository_effect_authorized
    repository_effect_performed evidence_storage_effects_performed""".split()
)
_MAX_CANDIDATE_BYTES = _MAX_DIFF_BYTES + 256 * 1024


@dataclass(frozen=True, slots=True)
class CandidateBundle:
    """Verified locator, bindings, and exact in-memory component snapshots."""

    bundle_root: Path
    repo_root: Path
    relative_dir: str
    bundle_sha256: str
    candidate_digest: str
    diff_sha256: str
    request_content_sha256: str
    source_sha256: str
    authorized_source_path: str
    oracle_argv: tuple[str, ...]
    bindings: NativePatchBindings
    request_bytes: bytes = field(repr=False)
    source_bytes: bytes = field(repr=False)
    diff_bytes: bytes = field(repr=False)
    candidate_bytes: bytes = field(repr=False)

    @property
    def manifest_path(self) -> Path:
        return self.bundle_root / self.relative_dir / "manifest.json"

    @property
    def request_path(self) -> Path:
        return self.bundle_root / self.relative_dir / "request.json"

    @property
    def source_snapshot_path(self) -> Path:
        return self.bundle_root / self.relative_dir / "source.utf8"

    @property
    def diff_path(self) -> Path:
        return self.bundle_root / self.relative_dir / "candidate.diff"

    @property
    def candidate_path(self) -> Path:
        return self.bundle_root / self.relative_dir / "candidate.json"

    @property
    def executor_agent_uid(self) -> str:
        return self.bindings.executor_agent_uid

    @property
    def executor_run_id(self) -> str:
        return self.bindings.executor_run_id

    @property
    def executor_process_boot_id(self) -> str:
        return self.bindings.executor_process_boot_id


def _candidate_metadata(request: GovernedPatchRequest) -> dict[str, Any]:
    return {
        "schema_version": GOVERNED_PATCH_REQUEST_SCHEMA,
        **request.bindings.to_dict(),
        "authorized_source_path": request.authorized_source_path,
        "oracle_argv": list(request.oracle_argv),
        "request_content_sha256": request.request_content_sha256,
        "source_sha256": request.source_sha256,
        "repository_effect_authorized": False,
        "repository_effect_performed": False,
        "evidence_storage_effects_performed": True,
    }


def _write_immutable(root: Path, relative: str, data: bytes) -> Path:
    try:
        return write_immutable_beneath(root, relative, data)
    except PatchReplayError as exc:
        raise GovernedPatchEvidenceError(str(exc)) from exc


def _safe_external_bundle_root(bundle_root: Path, repo_root: Path) -> Path:
    root = Path(bundle_root).expanduser().resolve(strict=False)
    repo = Path(repo_root).resolve(strict=True)
    if root == repo or root.is_relative_to(repo):
        raise GovernedPatchEvidenceError(
            "evidence bundle root must be outside the canonical repository"
        )
    return root


def _read_beneath(
    root: Path,
    relative: str,
    *,
    field: str,
    max_bytes: int = _MAX_CANDIDATE_BYTES,
) -> bytes:
    path = scoped_regular_file(
        root,
        relative,
        field=field,
        error_type=GovernedPatchEvidenceError,
    )
    return _read_regular_bounded(path, field=field, max_bytes=max_bytes)


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


def build_candidate_bundle(
    request: GovernedPatchRequest,
    diff: str,
    *,
    bundle_root: Path,
) -> CandidateBundle:
    """Replay-check an exact diff and persist snapshots without applying it."""

    if type(request) is not GovernedPatchRequest:
        raise GovernedPatchEvidenceError("request must be a GovernedPatchRequest")
    _validate_bindings(request.bindings)
    if type(diff) is not str or not diff or "\x00" in diff:
        raise GovernedPatchEvidenceError("candidate diff must be a non-empty string")
    try:
        diff_bytes = diff.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise GovernedPatchEvidenceError("candidate diff is not valid UTF-8") from exc
    if len(diff_bytes) > _MAX_DIFF_BYTES:
        raise GovernedPatchEvidenceError("candidate diff exceeds the bounded size")
    try:
        parsed = parse_unified_diff(diff)
        if parsed.path != request.authorized_source_path:
            raise GovernedPatchEvidenceError(
                "candidate diff path does not match authorized source"
            )
        postimage = "".join(
            _replay(
                request.source_bytes.decode("utf-8").splitlines(keepends=True),
                parsed,
            )
        ).encode("utf-8")
        if postimage == request.source_bytes:
            raise GovernedPatchEvidenceError(
                "candidate diff must change the exact source bytes"
            )
    except PatchReplayError as exc:
        raise GovernedPatchEvidenceError(
            f"candidate diff is not replayable: {exc}"
        ) from exc
    source_path = scoped_regular_file(
        request.repo_root,
        request.authorized_source_path,
        field="authorized source",
        error_type=GovernedPatchEvidenceError,
    )
    current_source = _read_regular_bounded(
        source_path,
        field="authorized source",
        max_bytes=MAX_SOURCE_BYTES,
    )
    if current_source != request.source_bytes:
        raise GovernedPatchEvidenceError(
            "authorized source changed after request parsing"
        )

    candidate = Candidate(
        candidate_id=request.bindings.proposal_id,
        target_id=GOVERNED_PATCH_TARGET_ID,
        diff=diff,
        origin_model=request.bindings.executor_agent_uid,
        metadata=_candidate_metadata(request),
    )
    candidate_bytes = _canonical_json_bytes(
        asdict(candidate), surface="Foundry Candidate"
    )
    foundry_digest = candidate_digest(candidate)
    if not _FOUNDRY_SHA_RE.fullmatch(foundry_digest):
        raise GovernedPatchEvidenceError("Foundry Candidate digest is malformed")
    diff_sha = _raw_sha256(diff_bytes)
    files = {
        "request.json": request.request_bytes,
        "source.utf8": request.source_bytes,
        "candidate.diff": diff_bytes,
        "candidate.json": candidate_bytes,
    }
    body = {
        "schema_version": CANDIDATE_BUNDLE_SCHEMA,
        "native_bindings": request.bindings.to_dict(),
        "authorized_source_path": request.authorized_source_path,
        "oracle_argv": list(request.oracle_argv),
        "request_content_sha256": request.request_content_sha256,
        "source_sha256": request.source_sha256,
        "diff_sha256": diff_sha,
        "candidate_digest": foundry_digest,
        "target_id": GOVERNED_PATCH_TARGET_ID,
        "files": {name: _raw_sha256(data) for name, data in files.items()},
        "repository_effect_authorized": False,
        "repository_effect_performed": False,
        "evidence_storage_effects_performed": True,
    }
    bundle_sha = _raw_sha256(_canonical_json_bytes(body, surface="candidate manifest"))
    manifest = _canonical_json_bytes(
        {**body, "bundle_sha256": bundle_sha},
        surface="candidate manifest",
    )
    root = _safe_external_bundle_root(bundle_root, request.repo_root)
    relative_dir = f"candidates/sha256/{bundle_sha}"
    for name, data in files.items():
        _write_immutable(root, f"{relative_dir}/{name}", data)
    _write_immutable(root, f"{relative_dir}/manifest.json", manifest)
    bundle = CandidateBundle(
        root,
        request.repo_root,
        relative_dir,
        bundle_sha,
        foundry_digest,
        diff_sha,
        request.request_content_sha256,
        request.source_sha256,
        request.authorized_source_path,
        request.oracle_argv,
        request.bindings,
        request.request_bytes,
        request.source_bytes,
        diff_bytes,
        candidate_bytes,
    )
    return verify_candidate_bundle(bundle)


def verify_candidate_bundle(bundle: CandidateBundle) -> CandidateBundle:
    """Re-read all bundle and live-base bytes; reject links or tampering."""

    if type(bundle) is not CandidateBundle:
        raise GovernedPatchEvidenceError("candidate bundle has the wrong type")
    _validate_bindings(bundle.bindings)
    if _validate_source_path(bundle.authorized_source_path) != (
        bundle.authorized_source_path
    ):
        raise GovernedPatchEvidenceError("candidate source path is not canonical")
    if _validate_oracle_argv(list(bundle.oracle_argv)) != bundle.oracle_argv:
        raise GovernedPatchEvidenceError("candidate oracle argv is not canonical")
    if (
        not _RAW_SHA_RE.fullmatch(bundle.bundle_sha256)
        or bundle.relative_dir != f"candidates/sha256/{bundle.bundle_sha256}"
    ):
        raise GovernedPatchEvidenceError("candidate bundle locator is malformed")
    manifest = _decode_canonical_object(
        _read_beneath(
            bundle.bundle_root,
            f"{bundle.relative_dir}/manifest.json",
            field="candidate manifest",
            max_bytes=256 * 1024,
        ),
        surface="candidate manifest",
    )
    _closed_shape(manifest, _MANIFEST_KEYS, "candidate manifest")
    body = {key: value for key, value in manifest.items() if key != "bundle_sha256"}
    if (
        manifest.get("schema_version") != CANDIDATE_BUNDLE_SCHEMA
        or manifest.get("bundle_sha256") != bundle.bundle_sha256
        or _raw_sha256(_canonical_json_bytes(body, surface="candidate manifest"))
        != bundle.bundle_sha256
    ):
        raise GovernedPatchEvidenceError("candidate manifest digest mismatch")
    hashes = manifest.get("files")
    if type(hashes) is not dict or frozenset(hashes) != _FILES:
        raise GovernedPatchEvidenceError("candidate manifest file set is malformed")
    component_caps = {
        "request.json": 128 * 1024,
        "source.utf8": MAX_SOURCE_BYTES,
        "candidate.diff": _MAX_DIFF_BYTES,
        "candidate.json": _MAX_CANDIDATE_BYTES,
    }
    components = {
        name: _read_beneath(
            bundle.bundle_root,
            f"{bundle.relative_dir}/{name}",
            field=f"candidate component {name}",
            max_bytes=component_caps[name],
        )
        for name in sorted(_FILES)
    }
    for name, data in components.items():
        if type(hashes.get(name)) is not str or _raw_sha256(data) != hashes[name]:
            raise GovernedPatchEvidenceError(f"candidate component tampered: {name}")
    if (
        _raw_sha256(components["request.json"]) != bundle.request_content_sha256
        or _raw_sha256(components["source.utf8"]) != bundle.source_sha256
        or _raw_sha256(components["candidate.diff"]) != bundle.diff_sha256
    ):
        raise GovernedPatchEvidenceError("candidate component binding mismatch")

    try:
        request_text = components["request.json"].decode("utf-8")
        source_text = components["source.utf8"].decode("utf-8")
        diff_text = components["candidate.diff"].decode("utf-8")
    except UnicodeDecodeError as exc:
        raise GovernedPatchEvidenceError(
            "candidate components must be strict UTF-8"
        ) from exc
    request_payload = _parse_json(request_text, surface="candidate request")
    if type(request_payload) is not dict:
        raise GovernedPatchEvidenceError("candidate request must be an object")
    _closed_shape(request_payload, _REQUEST_KEYS, "candidate request")
    expected_request = {
        "schema_version": GOVERNED_PATCH_REQUEST_SCHEMA,
        **bundle.bindings.to_dict(),
        "authorized_source_path": bundle.authorized_source_path,
        "oracle_argv": list(bundle.oracle_argv),
    }
    if request_payload != expected_request:
        raise GovernedPatchEvidenceError("candidate request binding mismatch")
    try:
        parsed_diff = parse_unified_diff(diff_text)
        if parsed_diff.path != bundle.authorized_source_path:
            raise GovernedPatchEvidenceError(
                "candidate diff path does not match authorized source"
            )
        postimage = "".join(
            _replay(source_text.splitlines(keepends=True), parsed_diff)
        ).encode("utf-8")
        if postimage == components["source.utf8"]:
            raise GovernedPatchEvidenceError(
                "candidate diff must change the exact source bytes"
            )
    except PatchReplayError as exc:
        raise GovernedPatchEvidenceError(
            f"candidate diff is not replayable: {exc}"
        ) from exc
    candidate_payload = _decode_canonical_object(
        components["candidate.json"],
        surface="Foundry Candidate",
    )
    if frozenset(candidate_payload) != {
        "candidate_id",
        "target_id",
        "diff",
        "origin_model",
        "parent_id",
        "metadata",
    }:
        raise GovernedPatchEvidenceError("Foundry Candidate shape is malformed")
    try:
        candidate = Candidate(**candidate_payload)
    except TypeError as exc:
        raise GovernedPatchEvidenceError("Foundry Candidate is malformed") from exc
    expected_metadata = {
        "schema_version": GOVERNED_PATCH_REQUEST_SCHEMA,
        **bundle.bindings.to_dict(),
        "authorized_source_path": bundle.authorized_source_path,
        "oracle_argv": list(bundle.oracle_argv),
        "request_content_sha256": bundle.request_content_sha256,
        "source_sha256": bundle.source_sha256,
        "repository_effect_authorized": False,
        "repository_effect_performed": False,
        "evidence_storage_effects_performed": True,
    }
    if (
        candidate_digest(candidate) != bundle.candidate_digest
        or candidate.diff.encode("utf-8") != components["candidate.diff"]
        or candidate.candidate_id != bundle.bindings.proposal_id
        or candidate.target_id != GOVERNED_PATCH_TARGET_ID
        or candidate.origin_model != bundle.bindings.executor_agent_uid
        or candidate.parent_id is not None
        or candidate.metadata != expected_metadata
    ):
        raise GovernedPatchEvidenceError("Foundry Candidate binding mismatch")
    current_source = _read_beneath(
        bundle.repo_root,
        bundle.authorized_source_path,
        field="current authorized source",
        max_bytes=MAX_SOURCE_BYTES,
    )
    if current_source != components["source.utf8"]:
        raise GovernedPatchEvidenceError(
            "authorized source drifted from candidate base"
        )
    expected_manifest = {
        "native_bindings": bundle.bindings.to_dict(),
        "authorized_source_path": bundle.authorized_source_path,
        "oracle_argv": list(bundle.oracle_argv),
        "request_content_sha256": bundle.request_content_sha256,
        "source_sha256": bundle.source_sha256,
        "diff_sha256": bundle.diff_sha256,
        "candidate_digest": bundle.candidate_digest,
        "target_id": GOVERNED_PATCH_TARGET_ID,
        "repository_effect_authorized": False,
        "repository_effect_performed": False,
        "evidence_storage_effects_performed": True,
    }
    if any(manifest.get(key) != value for key, value in expected_manifest.items()):
        raise GovernedPatchEvidenceError("candidate manifest binding mismatch")
    return replace(
        bundle,
        request_bytes=components["request.json"],
        source_bytes=components["source.utf8"],
        diff_bytes=components["candidate.diff"],
        candidate_bytes=components["candidate.json"],
    )


def load_candidate_bundle(
    bundle_root: Path,
    bundle_sha256: str,
    *,
    repo_root: Path,
    expected: NativePatchBindings,
    accepted_base_sha: str,
) -> CandidateBundle:
    """Rehydrate after restart and revalidate native identity and live source."""

    _validate_bindings(expected)
    if type(bundle_sha256) is not str or not _RAW_SHA_RE.fullmatch(bundle_sha256):
        raise GovernedPatchEvidenceError("candidate bundle sha256 is malformed")
    repo = Path(repo_root).resolve(strict=True)
    root = _safe_external_bundle_root(bundle_root, repo)
    relative_dir = f"candidates/sha256/{bundle_sha256}"
    manifest = _decode_canonical_object(
        _read_beneath(
            root,
            f"{relative_dir}/manifest.json",
            field="candidate manifest",
            max_bytes=256 * 1024,
        ),
        surface="candidate manifest",
    )
    bindings_raw = manifest.get("native_bindings")
    if type(bindings_raw) is not dict:
        raise GovernedPatchEvidenceError("candidate manifest lacks native bindings")
    bindings = _bindings_from_payload(bindings_raw)
    if bindings != expected or bindings.base_sha != accepted_base_sha:
        raise GovernedPatchEvidenceError(
            "candidate bundle base/native binding mismatch"
        )
    argv = manifest.get("oracle_argv")
    bundle = CandidateBundle(
        root,
        repo,
        relative_dir,
        bundle_sha256,
        str(manifest.get("candidate_digest") or ""),
        str(manifest.get("diff_sha256") or ""),
        str(manifest.get("request_content_sha256") or ""),
        str(manifest.get("source_sha256") or ""),
        str(manifest.get("authorized_source_path") or ""),
        tuple(argv) if type(argv) is list else (),
        bindings,
        b"",
        b"",
        b"",
        b"",
    )
    return verify_candidate_bundle(bundle)


__all__ = [
    "CandidateBundle",
    "build_candidate_bundle",
    "load_candidate_bundle",
    "verify_candidate_bundle",
]
