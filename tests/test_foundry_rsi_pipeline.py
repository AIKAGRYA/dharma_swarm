"""End-to-end shadow proof for the immutable RSI -> Foundry candidate lane."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from dharma_swarm.a2a.candidate_evaluator_deployment import SignedEvaluatorDeployment
from dharma_swarm.forge_lab.candidate_envelope import (
    CandidateEnvelope,
    EvidenceBinding,
    TerminalDisposition,
    TerminalState,
    sign_candidate_envelope,
)
from dharma_swarm.forge_lab.candidate_store import CandidateStore
from dharma_swarm.forge_lab.candidate_transport import (
    CandidateHandlingResult,
    CandidateJetStreamTransport,
    ConnectionSecurity,
)
from dharma_swarm.forge_lab.freeform_explore import FreeformExploreEnvelope, MEMBRANE_REQUIREMENTS
from dharma_swarm.forge_lab.promotion_controller import (
    CANARY_RESULT_EVIDENCE_SCHEMA,
    ROLLBACK_RESULT_EVIDENCE_SCHEMA,
    CanaryResult,
    IndependentEvaluation,
    LeaseVerification,
    PromotionController,
    RollbackResult,
    canary_result_evidence_content,
    rollback_result_evidence_content,
    sign_canary_result,
    sign_independent_evaluation,
    sign_rollback_result,
)
from dharma_swarm.forge_v1.forge_v2.signals import canonical_sha256


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _at(seconds: int = 0) -> str:
    return (
        datetime(2026, 8, 27, tzinfo=timezone.utc) + timedelta(seconds=seconds)
    ).isoformat().replace("+00:00", "Z")


def _evidence(name: str, seconds: int = 0) -> EvidenceBinding:
    return EvidenceBinding(
        schema=f"test.{name}.v1",
        receipt_id=f"receipt-{name}",
        sha256=_sha(name),
        issuer=f"issuer-{name}",
        created_at=_at(seconds),
    )


def _public(key: Ed25519PrivateKey) -> str:
    return key.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    ).hex()


_CANARY_KEY = Ed25519PrivateKey.generate()
_ROLLBACK_KEY = Ed25519PrivateKey.generate()


@dataclass
class _Ack:
    stream: str
    seq: int
    duplicate: bool = False


class _JetStream:
    def __init__(self) -> None:
        self.streams: dict[str, dict] = {}
        self.consumers: dict[tuple[str, str], dict] = {}
        self.published: list[tuple[str, bytes, dict]] = []
        self.ids: set[str] = set()

    async def stream_info(self, name):
        if name not in self.streams:
            raise RuntimeError("stream not found")
        return {"config": self.streams[name]}

    async def add_stream(self, *, config):
        payload = dict(config) if isinstance(config, dict) else {
            name: getattr(config, name) for name in config.__dataclass_fields__
        }
        self.streams[payload["name"]] = payload

    async def consumer_info(self, stream, consumer):
        if (stream, consumer) not in self.consumers:
            raise RuntimeError("consumer not found")
        return {"config": self.consumers[(stream, consumer)]}

    async def add_consumer(self, stream, *, config):
        payload = dict(config) if isinstance(config, dict) else {
            name: getattr(config, name) for name in config.__dataclass_fields__
        }
        self.consumers[(stream, payload["durable_name"])] = payload

    async def publish(self, subject, payload, *, headers=None, timeout=None):
        message_id = headers["Nats-Msg-Id"]
        duplicate = message_id in self.ids
        self.ids.add(message_id)
        self.published.append((subject, payload, headers))
        stream = "FOUNDRY_RSI_CANDIDATES_DLQ_V1" if subject.endswith("dlq.v1") else "FOUNDRY_RSI_CANDIDATES_V1"
        return _Ack(stream, len(self.published), duplicate)


class _Lease:
    def verify(self, **request):
        return LeaseVerification(
            allowed=True,
            reason_code="verified",
            authority_id=request["authority_id"],
            lease_id=request["lease_id"],
            candidate_id=request["candidate_id"],
            envelope_id=request["envelope_id"],
            fence=request["fence"],
            expires_at=request["lease_expires_at"],
            required_scope=request["required_scope"],
            verified_at=request["now"],
            verifier_receipt_sha256=_sha("operator-lease-verification"),
        )


class _Message:
    def __init__(self, subject: str, data: bytes, headers: dict[str, str]) -> None:
        self.subject, self.data, self.headers = subject, data, headers
        self.num_delivered = 1
        self.acked = 0

    async def ack(self):
        self.acked += 1

    async def nak(self, **kwargs):
        raise AssertionError("green pipeline must not NAK")


class _Canary:
    async def run(self, envelope, aggregate):
        performed_at = _at(50)
        body = canary_result_evidence_content(
            canary_id="shadow-canary",
            envelope_id=envelope.envelope_id,
            aggregate_id=aggregate.aggregate_id,
            healthy=True,
            rollback_ready=True,
            performed_at=performed_at,
        )
        return sign_canary_result(
            canary_id="shadow-canary",
            envelope_id=envelope.envelope_id,
            aggregate_id=aggregate.aggregate_id,
            healthy=True,
            rollback_ready=True,
            receipt=EvidenceBinding(
                CANARY_RESULT_EVIDENCE_SCHEMA,
                "receipt-canary",
                canonical_sha256(body),
                "shadow-canary-runner",
                performed_at,
            ),
            signing_key=_CANARY_KEY,
            authority_epoch_sha256=_sha("canary-epoch"),
        )


class _Rollback:
    async def rollback(self, envelope, *, reason_code):
        performed_at = _at(51)
        body = rollback_result_evidence_content(
            envelope_id=envelope.envelope_id,
            reason_code=reason_code,
            rolled_back=True,
            performed_at=performed_at,
        )
        return sign_rollback_result(
            envelope_id=envelope.envelope_id,
            reason_code=reason_code,
            rolled_back=True,
            receipt=EvidenceBinding(
                ROLLBACK_RESULT_EVIDENCE_SCHEMA,
                "receipt-rollback",
                canonical_sha256(body),
                "rollback-executor",
                performed_at,
            ),
            signing_key=_ROLLBACK_KEY,
            authority_epoch_sha256=_sha("rollback-epoch"),
        )


async def _source_candidate(tmp_path: Path):
    source_archive = tmp_path / "rsi-source.jsonl"
    store = CandidateStore(source_archive, experiment_id="rsi-run")
    await store.load()
    source = FreeformExploreEnvelope(
        candidate_id="cand_pipeline",
        parent_id=None,
        experiment_id="rsi-run",
        category="agent_evolution",
        artifacts={"patch_sha256": _sha("patch")},
        membrane={name: True for name in MEMBRANE_REQUIREMENTS},
    )
    await store.append_graded(
        candidate_id="cand_pipeline",
        genome={"arm_kind": "freeform_single", "instruction": "bounded-shadow-change"},
        parent_id=None,
        generation=1,
        loop_iteration=1,
        role="candidate",
        pass_rate=1.0,
        per_task=[{"task_id": "django-12209", "resolved": True}],
        budget={"spent_tokens": 10, "spent_usd": 0.01},
        tier="confirm-swebench-docker",
        executed_fields=("arm_kind", "instruction"),
        ignored_fields=(),
        envelope=source,
    )
    return source_archive, store, await store.export_candidate("cand_pipeline")


def _candidate(exported: dict) -> CandidateEnvelope:
    return CandidateEnvelope(
        candidate_id=exported["candidate_id"], revision=1, predecessor_envelope_id="",
        correlation_id="corr-pipeline", idempotency_key="idem-pipeline",
        source_run_id="rsi-run", source_task_id="rsi-task",
        source_sha="1" * 40, controller_sha="2" * 40, harness_sha="3" * 40,
        evaluator_sha="4" * 40, target_sha="5" * 40, base_sha="6" * 40,
        patch_sha256=_sha("patch"), dependencies_sha256=_sha("deps"),
        toolchain_sha256=_sha("toolchain"), artifact_sha256=exported["record_sha256"],
        configuration_sha256=_sha("config"), provider_attestation=_evidence("provider"),
        budget_receipt=_evidence("budget"), evaluation_receipt=_evidence("source-eval"),
        provenance_receipt=_evidence("provenance"), task_identity="swebench::django-12209",
        holdout_identity="holdout::django-12209::v1", parent_lineage=("seed",),
        evaluation_outcome="source_pass", evaluation_comparable=True,
        authority_id="rsi-controller", lease_id="lease-pipeline", lease_expires_at=_at(300),
        created_at=_at(), expires_at=_at(240), attempt=1, fence=17,
        terminal_disposition=TerminalDisposition(
            TerminalState.SUBMITTED, "submitted_for_foundry", "submit-pipeline", _at(),
        ),
    )


def _evaluation(envelope: CandidateEnvelope, evaluator: str, key: Ed25519PrivateKey, second: int):
    return sign_independent_evaluation(
        IndependentEvaluation(
            envelope_id=envelope.envelope_id,
            candidate_id=envelope.candidate_id,
            evaluator_id=evaluator,
            evaluator_sha=("7" if evaluator.endswith("a") else "8") * 40,
            evaluator_executable_sha256=_sha(f"executable-{evaluator}"),
            evaluator_release_tree_sha256=_sha(f"release-tree-{evaluator}"),
            target_sha=envelope.target_sha,
            outcome="pass",
            comparable=True,
            passed=True,
            score_micros=920_000,
            isolation_receipt=_evidence(f"isolation-{evaluator}", second - 1),
            evidence_receipt=_evidence(f"evidence-{evaluator}", second),
            created_at=_at(second),
        ),
        signing_key=key,
        authority_epoch_sha256=_sha(f"epoch-{evaluator}"),
    )


@pytest.mark.asyncio
async def test_rsi_to_foundry_to_shadow_promotion_and_rollback_is_end_to_end(tmp_path: Path) -> None:
    source_archive, _, exported = await _source_candidate(tmp_path)
    source_key = Ed25519PrivateKey.generate()
    evaluator_a, evaluator_b = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
    envelope = _candidate(exported)
    signed = sign_candidate_envelope(
        envelope, signing_key=source_key, authority_epoch_sha256=_sha("source-epoch")
    )
    source_before = source_archive.read_bytes()
    foundry_store = CandidateStore(tmp_path / "foundry-terminal.jsonl", experiment_id="foundry")
    await foundry_store.load()
    jetstream = _JetStream()
    transport = CandidateJetStreamTransport(
        trusted_source_public_keys=[_public(source_key)],
        terminal_store=foundry_store,
        lease_verifier=_Lease(),
        jetstream=jetstream,
        security=ConnectionSecurity(True, False, "foundry-fixture", "fixture-auth"),
    )
    desired = transport.desired_topology()
    jetstream.streams.update({name: dict(config) for name, config in desired["streams"].items()})
    jetstream.consumers[(transport.config.stream_name, transport.config.consumer_name)] = dict(
        desired["consumer"]
    )
    await transport.ensure_topology()
    await transport.publish(signed, now=_at(30))
    subject, wire, headers = jetstream.published[0]
    foundry_evaluation = _evaluation(envelope, "foundry-evaluator-a", evaluator_a, 40)

    async def evaluate(received):
        assert received.envelope.artifact_sha256 == exported["record_sha256"]
        return CandidateHandlingResult(
            TerminalDisposition(TerminalState.EVALUATED, "foundry_evaluated", "eval-a", _at(40)),
            "consume-pipeline",
            canonical_sha256(foundry_evaluation.to_dict()),
        )

    consumed = await transport.consume(_Message(subject, wire, headers), evaluate, now=_at(41))
    independent = _evaluation(envelope, "independent-evaluator-b", evaluator_b, 42)
    controller = PromotionController(
        trusted_source_public_keys=[_public(source_key)],
        trusted_evaluator_public_keys=[_public(evaluator_a), _public(evaluator_b)],
        trusted_canary_public_keys=[_public(_CANARY_KEY)],
        trusted_rollback_public_keys=[_public(_ROLLBACK_KEY)],
        decision_signing_key=Ed25519PrivateKey.generate(),
        decision_authority_epoch_sha256=_sha("decision-epoch"),
        canary_runner=_Canary(),
        rollback_executor=_Rollback(),
    )
    shadow = await controller.run(signed, [foundry_evaluation, independent], now=_at(60))
    rolled_back = await controller.run(
        signed, [foundry_evaluation, independent], now=_at(61), force_rollback=True
    )

    assert consumed.disposition == "evaluated"
    assert shadow.decision["outcome"] == "shadow_canary_passed"
    assert shadow.live_apply_allowed is False
    assert rolled_back.terminal_envelope.terminal_disposition.state is TerminalState.ROLLED_BACK
    assert source_archive.read_bytes() == source_before
    assert await foundry_store.latest_terminal(
        candidate_id=envelope.candidate_id,
        envelope_id=envelope.envelope_id,
    ) is not None


@pytest.mark.asyncio
async def test_prepare_cli_exports_actual_graded_candidate_without_mutating_source(tmp_path: Path) -> None:
    source_archive, _, exported = await _source_candidate(tmp_path)
    envelope = _candidate(exported)
    template = {
        "schema": "forge_lab.candidate_envelope_template.v1",
        "content": envelope.content_dict(),
    }
    template["content"]["candidate_id"] = "${CANDIDATE_ID}"
    template["content"]["digests"]["artifact"] = "${CANDIDATE_EXPORT_SHA256}"
    template_path = tmp_path / "template.json"
    template_path.write_text(json.dumps(template), encoding="utf-8")
    source_key = Ed25519PrivateKey.generate()
    key_path = tmp_path / "source-key.pem"
    key_path.write_bytes(
        source_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    key_path.chmod(0o600)
    output = tmp_path / "signed-envelope.json"
    before = source_archive.read_bytes()
    result = subprocess.run(
        [
            sys.executable,
            "scripts/forge_lab/candidate-foundry-rsi-publish-v1",
            "prepare",
            "--archive", str(source_archive),
            "--experiment-id", "rsi-run",
            "--candidate-id", "cand_pipeline",
            "--envelope-template", str(template_path),
            "--signing-key-file", str(key_path),
            "--authority-epoch-sha256", _sha("source-epoch"),
            "--output", str(output),
        ],
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    receipt = json.loads(result.stdout)
    assert receipt["candidate_export_sha256"] == exported["record_sha256"]
    assert receipt["source_archive_unchanged"] is True
    assert receipt["live_promotion_attempted"] is False
    assert source_archive.read_bytes() == before


@pytest.mark.asyncio
async def test_operational_consumer_binds_offline_evaluator_release_and_signed_sha(tmp_path: Path) -> None:
    import runpy

    functions = runpy.run_path("scripts/forge_lab/candidate-foundry-rsi-consume-v1")
    release = (tmp_path / "evaluator-release").resolve()
    release.mkdir(mode=0o755)
    executable = release / "evaluate"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    executable_sha = functions["_sha_file"](executable)
    tree_sha = functions["_release_tree_sha256"](release)
    assert functions["_verify_evaluator_release"](
        executable,
        release,
        expected_executable_sha256=executable_sha,
        expected_tree_sha256=tree_sha,
    )[1:] == (executable_sha, tree_sha)
    unsafe_directory = release / "group-writable"
    unsafe_directory.mkdir(mode=0o755)
    unsafe_directory.chmod(0o775)
    with pytest.raises(ValueError, match="unsafe entry"):
        functions["_release_tree_sha256"](release)
    unsafe_directory.chmod(0o755)
    executable.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="executable digest drifted"):
        functions["_verify_evaluator_release"](
            executable,
            release,
            expected_executable_sha256=executable_sha,
            expected_tree_sha256=tree_sha,
        )
    with pytest.raises(ValueError, match="offline"):
        functions["_evaluator_environment"](["PROVIDER_API_KEY"])

    binding_root = tmp_path / "binding"
    binding_root.mkdir()
    _, _, exported = await _source_candidate(binding_root)
    envelope = _candidate(exported)
    source_key = Ed25519PrivateKey.generate()
    evaluator_key = Ed25519PrivateKey.generate()
    signed = sign_candidate_envelope(
        envelope, signing_key=source_key, authority_epoch_sha256=_sha("source-epoch")
    )
    evaluation = _evaluation(envelope, "foundry-evaluator-a", evaluator_key, 40)
    functions["_validate_evaluation"](
        evaluation,
        signed,
        trusted_evaluator_keys=[_public(evaluator_key)],
        expected_evaluator_id="foundry-evaluator-a",
        expected_evaluator_sha="7" * 40,
        expected_executable_sha256=_sha("executable-foundry-evaluator-a"),
        expected_tree_sha256=_sha("release-tree-foundry-evaluator-a"),
        as_of=_at(41),
    )
    with pytest.raises(ValueError, match="identity or target binding"):
        functions["_validate_evaluation"](
            evaluation,
            signed,
            trusted_evaluator_keys=[_public(evaluator_key)],
            expected_evaluator_id="foundry-evaluator-a",
            expected_evaluator_sha="9" * 40,
            expected_executable_sha256=_sha("executable-foundry-evaluator-a"),
            expected_tree_sha256=_sha("release-tree-foundry-evaluator-a"),
            as_of=_at(41),
        )


@pytest.mark.asyncio
async def test_offline_evaluator_runs_nonroot_without_host_secret_and_binds_all_identities(
    tmp_path: Path,
) -> None:
    import runpy
    import shutil

    if shutil.which("bwrap") is None:
        pytest.skip("bubblewrap is unavailable")
    functions = runpy.run_path("scripts/forge_lab/candidate-foundry-rsi-consume-v1")
    candidate_root = tmp_path / "candidate"
    candidate_root.mkdir()
    source_archive, _, exported = await _source_candidate(candidate_root)
    assert source_archive.is_file()
    envelope = _candidate(exported)
    source_key = Ed25519PrivateKey.generate()
    signed = sign_candidate_envelope(
        envelope, signing_key=source_key, authority_epoch_sha256=_sha("source-epoch")
    )
    evaluator_key = Ed25519PrivateKey.generate()
    evaluator_private = evaluator_key.private_bytes(
        serialization.Encoding.Raw,
        serialization.PrivateFormat.Raw,
        serialization.NoEncryption(),
    ).hex()
    release_sha = "7" * 40
    secret = tmp_path / "host-provider-secret"
    secret_text = "PROVIDER_SECRET_MUST_NOT_CROSS_SANDBOX"
    secret.write_text(secret_text, encoding="utf-8")
    secret.chmod(0o600)
    release = (tmp_path / "offline-evaluator-release").resolve()
    release.mkdir(mode=0o755)
    executable = release / "evaluate"
    executable.write_text(
        """#!/usr/bin/python3
import argparse
import hashlib
import json
import stat
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

PRIVATE_HEX = %r
RELEASE_SHA = %r
HOST_SECRET = %r

def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def tree_hash(root):
    records = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        item = path.lstat()
        relative = path.relative_to(root).as_posix()
        if stat.S_ISDIR(item.st_mode):
            records.append({"path": relative + "/", "mode": stat.S_IMODE(item.st_mode)})
        else:
            records.append({
                "path": relative,
                "mode": stat.S_IMODE(item.st_mode),
                "size": item.st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            })
    return canonical({"schema": "forge_lab.offline_evaluator_release_tree.v1", "entries": records})

parser = argparse.ArgumentParser()
parser.add_argument("--signed-envelope", type=Path, required=True)
parser.add_argument("--evaluation-output", type=Path, required=True)
args = parser.parse_args()
signed = json.loads(args.signed_envelope.read_text())
candidate = signed["envelope"]
try:
    leaked = Path(HOST_SECRET).read_text()
except OSError:
    leaked = ""
created = candidate["created_at"]
def evidence(name):
    return {
        "schema": "fixture." + name + ".v1",
        "receipt_id": "fixture-" + name,
        "sha256": hashlib.sha256(name.encode()).hexdigest(),
        "issuer": "offline-evaluator",
        "created_at": created,
    }
evaluation = {
    "schema": "forge_lab.independent_evaluation.v2",
    "envelope_id": candidate["envelope_id"],
    "candidate_id": candidate["candidate_id"],
    "evaluator_id": "offline-evaluator-a",
    "evaluator_sha": RELEASE_SHA,
    "evaluator_executable_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    "evaluator_release_tree_sha256": tree_hash(Path("/release")),
    "target_sha": candidate["target_sha"],
    "outcome": "host_secret_leaked:" + leaked if leaked else "pass_secret_denied",
    "comparable": True,
    "passed": not bool(leaked),
    "score_micros": 900000 if not leaked else 0,
    "isolation_receipt": evidence("isolation"),
    "evidence_receipt": evidence("evaluation"),
    "created_at": created,
}
evaluation["evaluation_id"] = canonical(evaluation)
epoch = hashlib.sha256(b"offline-evaluator-epoch").hexdigest()
body = {
    "name": "rsi_foundry_independent_evaluation_v2",
    "payload": evaluation,
    "epoch_ruler_sha256": epoch,
}
key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(PRIVATE_HEX))
receipt = dict(body)
receipt["signed_payload_sha256"] = canonical(body)
receipt["signature"] = {
    "scheme": "ed25519",
    "key_id": "offline-fixture",
    "public_key": key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    ).hex(),
    "signature": key.sign(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hex(),
}
args.evaluation_output.write_text(json.dumps({
    "evaluation": evaluation, "signature_receipt": receipt,
}, sort_keys=True))
""" % (evaluator_private, release_sha, str(secret)),
        encoding="utf-8",
    )
    executable.chmod(0o755)
    executable_sha = functions["_sha_file"](executable)
    tree_sha = functions["_release_tree_sha256"](release)
    deployment_key = Ed25519PrivateKey.generate()
    deployment_key_path = tmp_path / "deployment-key.pem"
    deployment_key_path.write_bytes(deployment_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ))
    deployment_key_path.chmod(0o600)
    deployment_manifest = tmp_path / "signed-evaluator-deployment.json"
    identity = subprocess.run(
        [
            sys.executable,
            "scripts/forge_lab/candidate-foundry-rsi-evaluator-identity-v1",
            "--evaluator-executable", str(executable),
            "--evaluator-release-root", str(release),
            "--evaluator-id", "offline-evaluator-a",
            "--evaluator-release-sha", release_sha,
            "--deployment-signing-key-file", str(deployment_key_path),
            "--authority-epoch-sha256", _sha("deployment-epoch"),
            "--output", str(deployment_manifest),
        ],
        text=True,
        capture_output=True,
    )
    assert identity.returncode == 0, identity.stderr
    identity_receipt = json.loads(identity.stdout)
    loaded_deployment = functions["_load_evaluator_deployment"](
        deployment_manifest,
        trusted_public_keys=[_public(deployment_key)],
    )
    assert isinstance(loaded_deployment, SignedEvaluatorDeployment)
    assert loaded_deployment.deployment.deployment_id == identity_receipt[
        "evaluator_deployment_id"
    ]
    assert loaded_deployment.deployment.evaluator_release_sha == release_sha
    assert loaded_deployment.deployment.evaluator_executable_sha256 == executable_sha
    assert loaded_deployment.deployment.evaluator_release_tree_sha256 == tree_sha

    tampered_payload = loaded_deployment.to_dict()
    tampered_payload["deployment"]["evaluator_release_sha"] = "8" * 40
    tampered_payload["deployment"]["deployment_id"] = functions["canonical_sha256"]({
        key: value
        for key, value in tampered_payload["deployment"].items()
        if key != "deployment_id"
    })
    tampered_manifest = tmp_path / "tampered-evaluator-deployment.json"
    tampered_manifest.write_text(json.dumps(tampered_payload), encoding="utf-8")
    tampered_manifest.chmod(0o644)
    with pytest.raises(ValueError, match="signature is untrusted or invalid"):
        functions["_load_evaluator_deployment"](
            tampered_manifest,
            trusted_public_keys=[_public(deployment_key)],
        )

    evaluated, observed_executable, observed_tree = functions["_run_evaluator"](
        executable,
        signed,
        timeout=15,
        environment_names=[],
        release_root=release,
        expected_executable_sha256=executable_sha,
        expected_tree_sha256=tree_sha,
    )
    functions["_validate_evaluation"](
        evaluated,
        signed,
        trusted_evaluator_keys=[_public(evaluator_key)],
        expected_evaluator_id="offline-evaluator-a",
        expected_evaluator_sha=release_sha,
        expected_executable_sha256=executable_sha,
        expected_tree_sha256=tree_sha,
        as_of=_at(1),
    )

    serialized = json.dumps(evaluated.to_dict(), sort_keys=True)
    assert evaluated.evaluation.outcome == "pass_secret_denied"
    assert evaluated.evaluation.evaluator_sha == release_sha
    assert evaluated.evaluation.evaluator_executable_sha256 == executable_sha
    assert evaluated.evaluation.evaluator_release_tree_sha256 == tree_sha
    assert (observed_executable, observed_tree) == (executable_sha, tree_sha)
    assert secret_text not in serialized
