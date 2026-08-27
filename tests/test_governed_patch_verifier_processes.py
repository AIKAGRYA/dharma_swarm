from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from dharma_swarm.forge_v1.forge_v2.signals import canonical_sha256
from dharma_swarm.governed_patch_evidence import (
    GOVERNED_PATCH_REQUEST_SCHEMA,
    NativePatchBindings,
    NoEffectOutcome,
    build_candidate_bundle,
    parse_governed_patch_request,
    record_no_effect_result,
    verify_no_effect_bundle,
)
from dharma_swarm.mission_control_verification import (
    PATCH_VIBE_SCHEMA,
    ExpectedPromotionBindings,
    InconclusiveCapability,
    PatchPromotionVerifier,
    PromotionRefusal,
    VerifierPrincipalBinding,
    evaluate_vibe_halt,
    expected_vibe_halt_binding,
)
from dharma_swarm.runtime_state import RuntimeStateStore
from dharma_swarm.spine.identity import ExecutionIdentity
from scripts.runtime.governed_patch_verifier_common import (
    process_separation_blockers,
    verify_signed_process_receipt,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = "pkg/example.py"
SOURCE = 'def value():\n    return "old"\n'
DIFF = """--- a/pkg/example.py
+++ b/pkg/example.py
@@ -1,2 +1,2 @@
 def value():
-    return "old"
+    return "new"
"""
DELIVERY_ID = "d" * 24


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def _write_key(path: Path) -> str:
    key = Ed25519PrivateKey.generate()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    path.chmod(0o600)
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    ).hex()


def _public_key(key: Ed25519PrivateKey) -> str:
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    ).hex()


def _promotion_bindings(
    bindings: NativePatchBindings,
    bundle,
    *,
    foundry_public: str,
    vibe_public: str,
) -> ExpectedPromotionBindings:
    placeholder = "sha256:" + "1" * 64
    return ExpectedPromotionBindings(
        mission_id=bindings.mission_id,
        task_id=bindings.task_id,
        attempt_id=bindings.attempt_id,
        lease_id=bindings.lease_id,
        packet_id=bindings.packet_id,
        correlation_id=bindings.correlation_id,
        delivery_id=bindings.delivery_id,
        proposal_id=bindings.proposal_id,
        candidate_digest=bundle.candidate_digest,
        diff_sha256=bundle.diff_sha256,
        base_sha=bindings.base_sha,
        artifact_sha256="1" * 64,
        lineage_digest=placeholder,
        command_digest=placeholder,
        output_digest=placeholder,
        isolation_digest=placeholder,
        authorized_source_files=(bundle.authorized_source_path,),
        executor_agent_uid=bindings.executor_agent_uid,
        executor_run_id=bindings.executor_run_id,
        foundry_verifier=VerifierPrincipalBinding(
            role="foundry",
            agent_uid="foundry-independent-verifier",
            run_id="foundry-run-1",
            signer_public_key=foundry_public,
        ),
        vibe_verifier=VerifierPrincipalBinding(
            role="vibe_halt",
            agent_uid="vibe-independent-verifier",
            run_id="vibe-run-1",
            signer_public_key=vibe_public,
        ),
    )


def _fixture(tmp_path: Path):
    release = tmp_path / "release"
    (release / "pkg").mkdir(parents=True)
    (release / SOURCE_PATH).write_text(SOURCE, encoding="utf-8", newline="")
    _git(release.parent, "init", "-b", "main", str(release))
    _git(release, "config", "user.email", "verifier@example.invalid")
    _git(release, "config", "user.name", "Verifier Test")
    _git(release, "add", SOURCE_PATH)
    _git(release, "commit", "-m", "fixture")
    base_sha = _git(release, "rev-parse", "HEAD")
    _git(release, "update-ref", "refs/remotes/origin/main", base_sha)
    bindings = NativePatchBindings(
        mission_id="mission-1",
        task_id="task-1",
        attempt_id="packet-1",
        lease_id=DELIVERY_ID,
        packet_id="packet-1",
        correlation_id="a2a_send:codex_composer:packet-1",
        delivery_id=DELIVERY_ID,
        proposal_id="proposal-1",
        base_sha=base_sha,
        executor_agent_uid="codex_composer",
        executor_run_id="executor-run-1",
        executor_process_boot_id="boot-executor-1",
    )
    request_payload = {
        "schema_version": GOVERNED_PATCH_REQUEST_SCHEMA,
        **bindings.to_dict(),
        "authorized_source_path": SOURCE_PATH,
        "oracle_argv": [
            "python3",
            "-c",
            (
                "from pathlib import Path; "
                "assert 'new' in Path('pkg/example.py').read_text()"
            ),
        ],
    }
    content = json.dumps(request_payload, sort_keys=True, separators=(",", ":"))
    request = parse_governed_patch_request(
        content,
        repo_root=release,
        expected=bindings,
        accepted_base_sha=base_sha,
        expected_content_sha256=hashlib.sha256(content.encode()).hexdigest(),
    )
    bundle_root = tmp_path / "candidate-bundles"
    bundle = build_candidate_bundle(request, DIFF, bundle_root=bundle_root)
    return release, bindings, bundle_root, bundle


def _command(
    role: str,
    *,
    bindings: NativePatchBindings,
    bundle_root: Path,
    bundle_sha256: str,
    runtime_db: Path,
    receipt_root: Path,
) -> list[str]:
    command = [
        sys.executable,
        "-B",
        "-m",
        f"scripts.runtime.governed_patch_{role}_verifier",
        "once",
        "--bundle-root",
        str(bundle_root),
        "--bundle-sha256",
        bundle_sha256,
        "--expected-bindings-json",
        json.dumps(bindings.to_dict(), sort_keys=True, separators=(",", ":")),
        "--runtime-db",
        str(runtime_db),
        "--receipt-root",
        str(receipt_root),
        "--verifier-agent-uid",
        f"{role}-independent-verifier",
        "--verifier-run-id",
        f"{role}-run-1",
    ]
    if role == "foundry":
        command.extend(
            ["--docker-image", "missing.invalid/dharma@sha256:" + "a" * 64]
        )
    return command


def _environment(release: Path, base_sha: str, role: str, key: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("DHARMA_FOUNDRY_VERIFIER_KEY_FILE", None)
    environment.pop("DHARMA_VIBE_VERIFIER_KEY_FILE", None)
    environment.update(
        {
            "DHARMA_RELEASE_ROOT": str(release),
            "DHARMA_RUNTIME_EXPECTED_COMMIT": base_sha,
            "PYTHONDONTWRITEBYTECODE": "1",
            (
                "DHARMA_FOUNDRY_VERIFIER_KEY_FILE"
                if role == "foundry"
                else "DHARMA_VIBE_VERIFIER_KEY_FILE"
            ): str(key),
        }
    )
    return environment


def _run(command: list[str], environment: dict[str, str]) -> dict:
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def _verify_vibe_signature(receipt: dict, public_key: str) -> None:
    signature = receipt["signature"]
    signed = {key: value for key, value in receipt.items() if key != "signature"}
    body = {key: value for key, value in signed.items() if key != "payload_sha256"}
    assert signed["payload_sha256"] == canonical_sha256(body)
    Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key)).verify(
        bytes.fromhex(signature["signature"]),
        json.dumps(signed, sort_keys=True, separators=(",", ":")).encode(),
    )


def test_distinct_verifier_processes_close_signed_no_effect_canary(tmp_path: Path) -> None:
    release, bindings, bundle_root, bundle = _fixture(tmp_path)
    original = (release / SOURCE_PATH).read_bytes()
    runtime_db = tmp_path / "runtime" / "runtime.db"
    receipt_root = tmp_path / "receipts"
    foundry_key = tmp_path / "keys" / "foundry.key"
    vibe_key = tmp_path / "keys" / "vibe.key"
    foundry_public = _write_key(foundry_key)
    vibe_public = _write_key(vibe_key)

    outputs = {}
    for role, key in (("foundry", foundry_key), ("vibe", vibe_key)):
        outputs[role] = _run(
            _command(
                role,
                bindings=bindings,
                bundle_root=bundle_root,
                bundle_sha256=bundle.bundle_sha256,
                runtime_db=runtime_db,
                receipt_root=receipt_root,
            ),
            _environment(release, bindings.base_sha, role, key),
        )

    assert outputs["foundry"]["outcome"] == "foundry_inconclusive"
    assert outputs["vibe"]["outcome"] == "vibe_inconclusive"
    foundry_receipt = json.loads(
        Path(outputs["foundry"]["process_receipt_path"]).read_text()
    )
    vibe_process_receipt = json.loads(
        Path(outputs["vibe"]["process_receipt_path"]).read_text()
    )
    foundry_identity = ExecutionIdentity(**foundry_receipt["identity"])
    vibe_identity = ExecutionIdentity(**vibe_process_receipt["identity"])
    assert verify_signed_process_receipt(
        foundry_receipt,
        trusted_public_key=foundry_public,
        expected_role="foundry",
        expected_identity=foundry_identity,
        expected_bindings=bindings,
        expected_candidate_digest=bundle.candidate_digest,
        expected_diff_sha256=bundle.diff_sha256,
        expected_outcome="foundry_inconclusive",
    )
    assert verify_signed_process_receipt(
        vibe_process_receipt,
        trusted_public_key=vibe_public,
        expected_role="vibe_halt",
        expected_identity=vibe_identity,
        expected_bindings=bindings,
        expected_candidate_digest=bundle.candidate_digest,
        expected_diff_sha256=bundle.diff_sha256,
        expected_outcome="vibe_inconclusive",
    )
    assert process_separation_blockers(foundry_receipt, vibe_process_receipt) == (
        "exclusive_private_key_custody_unproven",
    )
    serialized_foundry = json.dumps(foundry_receipt, sort_keys=True)
    assert "bound_isolation_proof" not in serialized_foundry
    assert '"promotion_allowed"' not in serialized_foundry
    assert (
        foundry_receipt["evidence"]["process_observation"][
            "promotion_capability_emitted"
        ]
        is False
    )

    vibe_receipt = json.loads(Path(outputs["vibe"]["vibe_receipt_path"]).read_text())
    assert vibe_receipt["schema"] == PATCH_VIBE_SCHEMA
    assert vibe_receipt["ran"] is False
    assert vibe_receipt["reported_outcome"] == "unchecked"
    _verify_vibe_signature(vibe_receipt, vibe_public)
    expected = _promotion_bindings(
        bindings,
        bundle,
        foundry_public=foundry_public,
        vibe_public=vibe_public,
    )
    vibe_capability = evaluate_vibe_halt(
        vibe_receipt,
        expected=expected,
        signed_identity_coverage=expected_vibe_halt_binding(
            vibe_receipt,
            expected=expected,
        ),
    )
    assert isinstance(vibe_capability, InconclusiveCapability)
    assert vibe_capability.reason == "unchecked"

    judge_public = _public_key(Ed25519PrivateKey.generate())
    authority = PatchPromotionVerifier(
        trusted_judge_public_keys=(judge_public,),
        trusted_foundry_verifier_public_keys={
            "foundry-independent-verifier": (foundry_public,)
        },
        trusted_vibe_verifier_public_keys={
            "vibe-independent-verifier": (vibe_public,)
        },
    )
    promotion = authority.evaluate(
        foundry_receipt,
        expected=expected,
        vibe_halt_receipt=vibe_receipt,
    )
    assert isinstance(promotion, PromotionRefusal)
    assert not promotion
    no_effect = record_no_effect_result(
        bundle,
        outcome=NoEffectOutcome.VIBE_INCONCLUSIVE,
        foundry_evidence=foundry_receipt,
        vibe_evidence=vibe_process_receipt,
        reasons=("candidate_bound_vibe_capability_unavailable",),
    )
    assert verify_no_effect_bundle(no_effect) == no_effect
    assert (release / SOURCE_PATH).read_bytes() == original
    assert _git(release, "status", "--porcelain=v1", "--untracked-files=all") == ""

    restarted = RuntimeStateStore(runtime_db, include_memory_plane=False)
    assert restarted.get_execution_identity_sync("foundry-run-1") == foundry_identity
    assert restarted.get_execution_identity_sync("vibe-run-1") == vibe_identity

    replay = subprocess.run(
        _command(
            "vibe",
            bindings=bindings,
            bundle_root=bundle_root,
            bundle_sha256=bundle.bundle_sha256,
            runtime_db=runtime_db,
            receipt_root=receipt_root,
        ),
        cwd=REPO_ROOT,
        env=_environment(release, bindings.base_sha, "vibe", vibe_key),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert replay.returncode != 0
    assert (release / SOURCE_PATH).read_bytes() == original
