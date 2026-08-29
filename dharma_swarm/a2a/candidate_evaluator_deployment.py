"""Signed authority binding for one immutable offline evaluator deployment."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from dharma_swarm.forge_v1.forge_v2.signals import canonical_sha256
from dharma_swarm.forge_v1.forge_v2.verify_promotion import (
    sign_receipt,
    verify_trusted_signed_receipt,
)

EVALUATOR_DEPLOYMENT_SCHEMA = "forge_lab.offline_evaluator_deployment.v1"
EVALUATOR_DEPLOYMENT_RECEIPT = "rsi_foundry_offline_evaluator_deployment"
_GIT_SHA = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_RELATIVE = re.compile(r"^[A-Za-z0-9._+/-]+$")


class EvaluatorDeploymentError(ValueError):
    """The evaluator deployment authority binding is incomplete or invalid."""


def _token(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text or len(text) > 512 or any(ord(character) < 32 for character in text):
        raise EvaluatorDeploymentError(f"{field} must be a non-empty printable token")
    return text


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise EvaluatorDeploymentError("deployment signature receipt is not JSON")


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


@dataclass(frozen=True)
class EvaluatorDeployment:
    evaluator_id: str
    evaluator_release_sha: str
    evaluator_executable_relative_path: str
    evaluator_executable_sha256: str
    evaluator_release_tree_sha256: str
    schema: str = EVALUATOR_DEPLOYMENT_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != EVALUATOR_DEPLOYMENT_SCHEMA:
            raise EvaluatorDeploymentError("evaluator deployment schema is invalid")
        object.__setattr__(self, "evaluator_id", _token(self.evaluator_id, "evaluator_id"))
        release_sha = str(self.evaluator_release_sha or "").lower()
        if not _GIT_SHA.fullmatch(release_sha):
            raise EvaluatorDeploymentError("evaluator_release_sha must be a full Git object id")
        object.__setattr__(self, "evaluator_release_sha", release_sha)
        relative = str(self.evaluator_executable_relative_path or "").strip()
        parts = relative.split("/")
        if (
            not _RELATIVE.fullmatch(relative)
            or relative.startswith("/")
            or any(part in {"", ".", ".."} for part in parts)
        ):
            raise EvaluatorDeploymentError(
                "evaluator executable path must be a normalized relative path"
            )
        object.__setattr__(self, "evaluator_executable_relative_path", relative)
        for field in ("evaluator_executable_sha256", "evaluator_release_tree_sha256"):
            digest = str(getattr(self, field) or "").lower()
            if not _SHA256.fullmatch(digest):
                raise EvaluatorDeploymentError(f"{field} must be a SHA-256 digest")
            object.__setattr__(self, field, digest)

    def content_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def deployment_id(self) -> str:
        return canonical_sha256(self.content_dict())

    def to_dict(self) -> dict[str, Any]:
        return {**self.content_dict(), "deployment_id": self.deployment_id}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "EvaluatorDeployment":
        expected = {
            "schema", "evaluator_id", "evaluator_release_sha",
            "evaluator_executable_relative_path", "evaluator_executable_sha256",
            "evaluator_release_tree_sha256", "deployment_id",
        }
        if set(payload) != expected:
            raise EvaluatorDeploymentError("evaluator deployment fields are invalid")
        deployment = cls(
            schema=str(payload.get("schema") or ""),
            evaluator_id=str(payload.get("evaluator_id") or ""),
            evaluator_release_sha=str(payload.get("evaluator_release_sha") or ""),
            evaluator_executable_relative_path=str(
                payload.get("evaluator_executable_relative_path") or ""
            ),
            evaluator_executable_sha256=str(
                payload.get("evaluator_executable_sha256") or ""
            ),
            evaluator_release_tree_sha256=str(
                payload.get("evaluator_release_tree_sha256") or ""
            ),
        )
        if payload.get("deployment_id") != deployment.deployment_id:
            raise EvaluatorDeploymentError("evaluator deployment content hash mismatch")
        return deployment


@dataclass(frozen=True)
class SignedEvaluatorDeployment:
    deployment: EvaluatorDeployment
    signature_receipt: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "signature_receipt", _freeze(self.signature_receipt))

    def to_dict(self) -> dict[str, Any]:
        return {
            "deployment": self.deployment.to_dict(),
            "signature_receipt": _thaw(self.signature_receipt),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "SignedEvaluatorDeployment":
        if set(payload) != {"deployment", "signature_receipt"}:
            raise EvaluatorDeploymentError("signed evaluator deployment fields are invalid")
        receipt = payload.get("signature_receipt")
        if not isinstance(receipt, Mapping):
            raise EvaluatorDeploymentError("evaluator deployment signature receipt is invalid")
        return cls(
            deployment=EvaluatorDeployment.from_dict(payload.get("deployment") or {}),
            signature_receipt=dict(receipt),
        )

    def verify(self, *, trusted_public_keys: Iterable[str | bytes]) -> bool:
        receipt = _thaw(self.signature_receipt)
        return bool(
            receipt.get("name") == EVALUATOR_DEPLOYMENT_RECEIPT
            and receipt.get("payload") == self.deployment.to_dict()
            and verify_trusted_signed_receipt(
                receipt, trusted_public_keys=trusted_public_keys,
            )
        )


def sign_evaluator_deployment(
    deployment: EvaluatorDeployment,
    *,
    signing_key: Any,
    authority_epoch_sha256: str,
    key_id: str = "",
) -> SignedEvaluatorDeployment:
    epoch = str(authority_epoch_sha256 or "").lower()
    if not _SHA256.fullmatch(epoch):
        raise EvaluatorDeploymentError("authority epoch must be a SHA-256 digest")
    return SignedEvaluatorDeployment(
        deployment=deployment,
        signature_receipt=sign_receipt(
            name=EVALUATOR_DEPLOYMENT_RECEIPT,
            payload=deployment.to_dict(),
            signing_key=signing_key,
            epoch_ruler_sha256=epoch,
            key_id=key_id,
        ),
    )


__all__ = [
    "EVALUATOR_DEPLOYMENT_RECEIPT",
    "EVALUATOR_DEPLOYMENT_SCHEMA",
    "EvaluatorDeployment",
    "EvaluatorDeploymentError",
    "SignedEvaluatorDeployment",
    "sign_evaluator_deployment",
]
