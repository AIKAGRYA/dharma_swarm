"""Typed terminal observations for the governed patch no-effect lane."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dharma_swarm.governed_patch_candidate_bundle import (
    CandidateBundle,
    _decode_canonical_object,
    _read_beneath,
    _safe_external_bundle_root,
    _write_immutable,
    verify_candidate_bundle,
)
from dharma_swarm.governed_patch_evidence import (
    NO_EFFECT_RESULT_SCHEMA,
    MAX_VERIFIER_EVIDENCE_BYTES,
    GovernedPatchEvidenceError,
    NoEffectOutcome,
    _RAW_SHA_RE,
    _canonical_json_bytes,
    _closed_shape,
    _raw_sha256,
    _strict_json_value,
)

_RESULT_KEYS = frozenset(
    """schema_version result_bundle_sha256 outcome candidate_bundle_sha256
    candidate_digest diff_sha256 foundry_evidence_sha256 vibe_evidence_sha256
    reasons authority_semantics repository_effect_authorized
    repository_effect_performed evidence_storage_effects_performed""".split()
)


@dataclass(frozen=True, slots=True)
class NoEffectBundle:
    """Content-addressed observation whose effect capabilities are uninhabited."""

    bundle_root: Path
    relative_dir: str
    result_bundle_sha256: str
    outcome: NoEffectOutcome
    candidate_bundle_sha256: str
    candidate_digest: str
    diff_sha256: str
    foundry_evidence_sha256: str
    vibe_evidence_sha256: str
    reasons: tuple[str, ...]
    repository_effect_authorized: bool = field(default=False, init=False)
    repository_effect_performed: bool = field(default=False, init=False)
    evidence_storage_effects_performed: bool = field(default=True, init=False)

    @property
    def result_path(self) -> Path:
        return self.bundle_root / self.relative_dir / "result.json"

    @property
    def foundry_evidence_path(self) -> Path | None:
        if not self.foundry_evidence_sha256:
            return None
        return self.bundle_root / self.relative_dir / "foundry_evidence.json"

    @property
    def vibe_evidence_path(self) -> Path | None:
        if not self.vibe_evidence_sha256:
            return None
        return self.bundle_root / self.relative_dir / "vibe_evidence.json"


def _evidence_bytes(
    evidence: Mapping[str, Any] | None,
    *,
    role: str,
    candidate: CandidateBundle,
) -> bytes | None:
    if evidence is None:
        return None
    if not isinstance(evidence, Mapping):
        raise GovernedPatchEvidenceError(f"{role} evidence must be a JSON object")
    normalized = _strict_json_value(evidence, surface=f"{role} evidence")
    if type(normalized) is not dict:
        raise GovernedPatchEvidenceError(f"{role} evidence must be a JSON object")
    if (
        normalized.get("candidate_digest") != candidate.candidate_digest
        or normalized.get("diff_sha256") != candidate.diff_sha256
    ):
        raise GovernedPatchEvidenceError(f"{role} evidence is not candidate-bound")
    encoded = _canonical_json_bytes(normalized, surface=f"{role} evidence")
    if len(encoded) > MAX_VERIFIER_EVIDENCE_BYTES:
        raise GovernedPatchEvidenceError(f"{role} evidence exceeds the bounded size")
    return encoded


def _validate_result_inputs(
    outcome: NoEffectOutcome,
    foundry: bytes | None,
    vibe: bytes | None,
    reasons: tuple[str, ...],
) -> None:
    if type(outcome) is not NoEffectOutcome:
        raise GovernedPatchEvidenceError("outcome must be a NoEffectOutcome")
    if type(reasons) is not tuple or any(
        type(reason) is not str
        or not reason
        or len(reason) > 512
        or any(character in reason for character in ("\x00", "\r", "\n"))
        for reason in reasons
    ):
        raise GovernedPatchEvidenceError("reasons must be bounded non-empty strings")
    if len(set(reasons)) != len(reasons):
        raise GovernedPatchEvidenceError("result reasons must be unique")
    if outcome is NoEffectOutcome.CANDIDATE_PRODUCED:
        required = (False, False)
    elif outcome in {
        NoEffectOutcome.FOUNDRY_REJECTED,
        NoEffectOutcome.FOUNDRY_INCONCLUSIVE,
    }:
        required = (True, False)
    else:
        required = (True, True)
    if (foundry is not None, vibe is not None) != required:
        raise GovernedPatchEvidenceError(
            f"{outcome.value} has an invalid Foundry/Vibe evidence shape"
        )


def record_no_effect_result(
    candidate: CandidateBundle,
    *,
    outcome: NoEffectOutcome,
    bundle_root: Path | None = None,
    foundry_evidence: Mapping[str, Any] | None = None,
    vibe_evidence: Mapping[str, Any] | None = None,
    reasons: tuple[str, ...] = (),
) -> NoEffectBundle:
    """Record one caller classification without granting verification authority."""

    verify_candidate_bundle(candidate)
    foundry = _evidence_bytes(foundry_evidence, role="Foundry", candidate=candidate)
    vibe = _evidence_bytes(vibe_evidence, role="Vibe Halt", candidate=candidate)
    _validate_result_inputs(outcome, foundry, vibe, reasons)
    foundry_sha = _raw_sha256(foundry) if foundry is not None else ""
    vibe_sha = _raw_sha256(vibe) if vibe is not None else ""
    body = {
        "schema_version": NO_EFFECT_RESULT_SCHEMA,
        "outcome": outcome.value,
        "candidate_bundle_sha256": candidate.bundle_sha256,
        "candidate_digest": candidate.candidate_digest,
        "diff_sha256": candidate.diff_sha256,
        "foundry_evidence_sha256": foundry_sha,
        "vibe_evidence_sha256": vibe_sha,
        "reasons": list(reasons),
        "authority_semantics": "storage_only_unvalidated_signatures_no_warrant",
        "repository_effect_authorized": False,
        "repository_effect_performed": False,
        "evidence_storage_effects_performed": True,
    }
    result_sha = _raw_sha256(_canonical_json_bytes(body, surface="no-effect result"))
    result = _canonical_json_bytes(
        {**body, "result_bundle_sha256": result_sha},
        surface="no-effect result",
    )
    root = _safe_external_bundle_root(
        bundle_root if bundle_root is not None else candidate.bundle_root,
        candidate.repo_root,
    )
    relative_dir = f"results/sha256/{result_sha}"
    if foundry is not None:
        _write_immutable(root, f"{relative_dir}/foundry_evidence.json", foundry)
    if vibe is not None:
        _write_immutable(root, f"{relative_dir}/vibe_evidence.json", vibe)
    _write_immutable(root, f"{relative_dir}/result.json", result)
    bundle = NoEffectBundle(
        root,
        relative_dir,
        result_sha,
        outcome,
        candidate.bundle_sha256,
        candidate.candidate_digest,
        candidate.diff_sha256,
        foundry_sha,
        vibe_sha,
        reasons,
    )
    return verify_no_effect_bundle(bundle)


def verify_no_effect_bundle(bundle: NoEffectBundle) -> NoEffectBundle:
    """Re-read a result and reject content, link, or effect-flag drift."""

    if type(bundle) is not NoEffectBundle:
        raise GovernedPatchEvidenceError("no-effect bundle has the wrong type")
    if (
        not _RAW_SHA_RE.fullmatch(bundle.result_bundle_sha256)
        or bundle.relative_dir != f"results/sha256/{bundle.result_bundle_sha256}"
    ):
        raise GovernedPatchEvidenceError("no-effect bundle locator is malformed")
    payload = _decode_canonical_object(
        _read_beneath(
            bundle.bundle_root,
            f"{bundle.relative_dir}/result.json",
            field="no-effect result",
            max_bytes=128 * 1024,
        ),
        surface="no-effect result",
    )
    _closed_shape(payload, _RESULT_KEYS, "no-effect result")
    body = {
        key: value for key, value in payload.items() if key != "result_bundle_sha256"
    }
    if (
        payload.get("schema_version") != NO_EFFECT_RESULT_SCHEMA
        or payload.get("result_bundle_sha256") != bundle.result_bundle_sha256
        or _raw_sha256(_canonical_json_bytes(body, surface="no-effect result"))
        != bundle.result_bundle_sha256
        or payload.get("repository_effect_authorized") is not False
        or payload.get("repository_effect_performed") is not False
        or payload.get("evidence_storage_effects_performed") is not True
        or payload.get("authority_semantics")
        != "storage_only_unvalidated_signatures_no_warrant"
        or bundle.repository_effect_authorized
        or bundle.repository_effect_performed
        or not bundle.evidence_storage_effects_performed
    ):
        raise GovernedPatchEvidenceError("no-effect result digest/authority mismatch")
    expected = {
        "outcome": bundle.outcome.value,
        "candidate_bundle_sha256": bundle.candidate_bundle_sha256,
        "candidate_digest": bundle.candidate_digest,
        "diff_sha256": bundle.diff_sha256,
        "foundry_evidence_sha256": bundle.foundry_evidence_sha256,
        "vibe_evidence_sha256": bundle.vibe_evidence_sha256,
        "reasons": list(bundle.reasons),
    }
    if any(payload.get(key) != value for key, value in expected.items()):
        raise GovernedPatchEvidenceError("no-effect result binding mismatch")
    evidence: dict[str, bytes | None] = {"foundry": None, "vibe": None}
    for role, digest in (
        ("foundry", bundle.foundry_evidence_sha256),
        ("vibe", bundle.vibe_evidence_sha256),
    ):
        if not digest:
            continue
        raw = _read_beneath(
            bundle.bundle_root,
            f"{bundle.relative_dir}/{role}_evidence.json",
            field=f"{role} evidence",
            max_bytes=MAX_VERIFIER_EVIDENCE_BYTES,
        )
        evidence_payload = _decode_canonical_object(
            raw,
            surface=f"{role} evidence",
        )
        if _raw_sha256(raw) != digest:
            raise GovernedPatchEvidenceError(f"{role} evidence tampered")
        if (
            evidence_payload.get("candidate_digest") != bundle.candidate_digest
            or evidence_payload.get("diff_sha256") != bundle.diff_sha256
        ):
            raise GovernedPatchEvidenceError(
                f"{role} evidence is not candidate-bound"
            )
        evidence[role] = raw
    _validate_result_inputs(
        bundle.outcome, evidence["foundry"], evidence["vibe"], bundle.reasons
    )
    return bundle


__all__ = ["NoEffectBundle", "record_no_effect_result", "verify_no_effect_bundle"]
