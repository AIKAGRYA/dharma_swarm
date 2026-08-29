"""Fail-closed isolation adapter for official SWE-bench grading containers.

SWE-bench 4.x creates an instance container on Docker's default network. That
is acceptable for its generic harness, but not for RSI evaluation: candidate
code must not have network access or inherit provider/control credentials.
This adapter keeps the official image build and report path, then recreates the
stopped instance container with a read-only root, bounded writable tmpfs mounts,
no network/capabilities/host environment, no-new-privileges, verified cleanup, and hard
PID/CPU/memory caps before the harness copies or executes the candidate patch.
"""

from __future__ import annotations

import contextlib
import threading
from collections.abc import Callable, Iterator
from typing import Any

_PATCH_LOCK = threading.Lock()
ISOLATION_PROOF_SCHEMA = "rsi_lab.grader_isolation_proof.v1"
PID_LIMIT = 256
NANO_CPU_LIMIT = 2_000_000_000
MEMORY_LIMIT_BYTES = 4 * 1024 * 1024 * 1024
WRITABLE_TESTBED = "/testbed"
WRITABLE_TMP = "/tmp"
_FORBIDDEN_EXACT = {
    "DHARMA_HOME",
    "RSI_LAB_BASE",
    "RSI_LAB_REPO",
    "RSI_LAB_STATE",
    "SSH_AUTH_SOCK",
}
_FORBIDDEN_SUFFIXES = (
    "_API_KEY",
    "_TOKEN",
    "_SECRET",
    "_PASSWORD",
    "_PRIVATE_KEY",
    "_CREDENTIALS",
)
_FORBIDDEN_PREFIXES = (
    "A2A_",
    "AWS_",
    "AZURE_",
    "CLAUDE_",
    "CODEX_",
    "DHARMA_",
    "GCP_",
    "GITHUB_TOKEN",
    "NATS_",
    "RSI_",
)


def forbidden_environment_names(entries: list[str] | None) -> list[str]:
    """Return secret/control-shaped variable names without exposing values."""

    names = {
        str(entry).split("=", 1)[0].strip().upper()
        for entry in (entries or [])
        if str(entry).split("=", 1)[0].strip()
    }
    return sorted(
        name
        for name in names
        if name in _FORBIDDEN_EXACT
        or name.endswith(_FORBIDDEN_SUFFIXES)
        or name.startswith(_FORBIDDEN_PREFIXES)
    )


def _is_not_found(exc: BaseException) -> bool:
    status = getattr(exc, "status_code", None)
    response = getattr(exc, "response", None)
    return bool(
        type(exc).__name__ == "NotFound"
        or status == 404
        or getattr(response, "status_code", None) == 404
    )


def _container_resource_identity(container: Any) -> dict[str, Any]:
    """Capture the exact container and Docker-volume identities from inspect."""

    attrs = getattr(container, "attrs", None)
    if not isinstance(attrs, dict):
        raise RuntimeError("candidate_container_resource_inspect_missing")
    identity = str(
        getattr(container, "id", None)
        or attrs.get("Id")
        or getattr(container, "name", None)
        or ""
    ).strip()
    if not identity:
        raise RuntimeError("candidate_container_cleanup_identity_missing")
    mounts = attrs.get("Mounts")
    if not isinstance(mounts, list):
        raise RuntimeError("candidate_container_mount_inventory_missing")
    volume_mounts: list[dict[str, str]] = []
    for mount in mounts:
        if not isinstance(mount, dict):
            raise RuntimeError("candidate_container_mount_inventory_invalid")
        if str(mount.get("Type") or "").casefold() != "volume":
            continue
        name = str(mount.get("Name") or "").strip()
        destination = str(mount.get("Destination") or "").strip()
        if not name or not destination:
            raise RuntimeError("candidate_container_cleanup_volume_identity_missing")
        volume_mounts.append({"name": name, "destination": destination})
    volume_mounts.sort(key=lambda row: (row["name"], row["destination"]))
    return {
        "container_identity": identity,
        "volume_mounts": volume_mounts,
        "volume_mount_names": sorted({row["name"] for row in volume_mounts}),
        "volume_mount_count": len(volume_mounts),
    }


def _remove_container(
    container: Any,
    *,
    client: Any | None = None,
    expected_resource: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Remove one container and verify absence; never swallow cleanup failure."""

    absent_before_remove = False
    try:
        container.reload()
    except Exception as exc:
        if not _is_not_found(exc):
            raise RuntimeError("candidate_container_cleanup_inspect_failed") from exc
        absent_before_remove = True
    observed = _container_resource_identity(container)
    if expected_resource is not None and observed != expected_resource:
        raise RuntimeError("candidate_container_cleanup_resource_identity_changed")
    resource = expected_resource or observed
    identity = str(resource["container_identity"])
    volume_names = list(resource["volume_mount_names"])
    try:
        container.remove(force=True, v=True)
    except Exception as exc:
        if not _is_not_found(exc):
            raise RuntimeError("candidate_container_cleanup_remove_failed") from exc
    if client is None:
        raise RuntimeError("candidate_container_cleanup_verify_unavailable")
    getter = getattr(getattr(client, "containers", None), "get", None)
    if not callable(getter):
        raise RuntimeError("candidate_container_cleanup_verify_unavailable")
    try:
        getter(identity)
    except Exception as exc:
        if not _is_not_found(exc):
            raise RuntimeError("candidate_container_cleanup_verify_failed") from exc
    else:
        raise RuntimeError("candidate_container_cleanup_still_present")
    if volume_names:
        volume_getter = getattr(getattr(client, "volumes", None), "get", None)
        if not callable(volume_getter):
            raise RuntimeError("candidate_container_volume_verify_unavailable")
        for volume_name in volume_names:
            try:
                volume_getter(volume_name)
            except Exception as exc:
                if not _is_not_found(exc):
                    raise RuntimeError("candidate_container_volume_verify_failed") from exc
            else:
                raise RuntimeError("candidate_container_volume_still_present")
    return {
        "resource_identity": resource,
        "container_identity": identity,
        "container_absent_before_remove": absent_before_remove,
        "container_removed": True,
        "container_absence_verified": True,
        "volume_mount_names": volume_names,
        "volume_mount_count": resource["volume_mount_count"],
        "volume_absence_verified": True,
        "cleanup_verified": True,
    }


def isolation_proof(container: Any) -> dict[str, Any]:
    """Build a machine-checkable proof from Docker's inspected configuration."""

    attrs = container.attrs or {}
    config = attrs.get("Config") or {}
    host = attrs.get("HostConfig") or {}
    networks = ((attrs.get("NetworkSettings") or {}).get("Networks") or {})
    cap_drop = {str(item).upper() for item in (host.get("CapDrop") or [])}
    cap_add = [str(item) for item in (host.get("CapAdd") or [])]
    security_opt = {str(item).casefold() for item in (host.get("SecurityOpt") or [])}
    tmpfs = host.get("Tmpfs") or {}
    declared_volumes = config.get("Volumes") or {}
    volume_mounts = [
        mount
        for mount in (attrs.get("Mounts") or [])
        if str(mount.get("Type") or "").casefold() == "volume"
    ]
    writable_mounts = sorted(
        str(mount.get("Destination") or "")
        for mount in (attrs.get("Mounts") or [])
        if mount.get("RW") and str(mount.get("Destination") or "")
    )
    forbidden = forbidden_environment_names(config.get("Env"))
    fields = {
        "network_disabled": bool(config.get("NetworkDisabled")),
        "network_attachments_absent": not bool(networks),
        "forbidden_environment_absent": not bool(forbidden),
        "cap_drop_all": "ALL" in cap_drop,
        "cap_add_none": not bool(cap_add),
        "not_privileged": not bool(host.get("Privileged")),
        "read_only_rootfs": bool(host.get("ReadonlyRootfs")),
        "no_new_privileges": "no-new-privileges:true" in security_opt,
        "pid_limit": int(host.get("PidsLimit") or 0) == PID_LIMIT,
        "cpu_limit": int(host.get("NanoCpus") or 0) == NANO_CPU_LIMIT,
        "memory_limit": int(host.get("Memory") or 0) == MEMORY_LIMIT_BYTES,
        "memory_swap_disabled": int(host.get("MemorySwap") or 0)
        == MEMORY_LIMIT_BYTES,
        "anonymous_volumes_absent": not bool(declared_volumes)
        and not bool(volume_mounts),
        "testbed_tmpfs_declared": WRITABLE_TESTBED in tmpfs,
        "tmpfs_bounded": set(tmpfs) == {WRITABLE_TMP, WRITABLE_TESTBED},
        "writable_mounts_bounded": set(writable_mounts).issubset(
            {WRITABLE_TESTBED, WRITABLE_TMP}
        ),
    }
    return {
        "schema": ISOLATION_PROOF_SCHEMA,
        "controls": fields,
        "forbidden_environment_names": forbidden,
        "writable_mounts": writable_mounts,
        "limits": {
            "pids": PID_LIMIT,
            "nano_cpus": NANO_CPU_LIMIT,
            "memory_bytes": MEMORY_LIMIT_BYTES,
        },
        "promotion_eligible": all(fields.values()),
    }


def recreate_isolated_container(
    original_builder: Callable[..., Any],
    test_spec: Any,
    client: Any,
    run_id: str,
    logger: Any,
    nocache: bool,
    force_rebuild: bool = False,
    *,
    docker_user: str | None = None,
    expected_image: dict[str, Any] | None = None,
) -> Any:
    """Build/pull officially, then recreate the stopped container offline."""

    if docker_user is None:
        from swebench.harness.constants import DOCKER_USER

        docker_user = DOCKER_USER

    original = original_builder(
        test_spec,
        client,
        run_id,
        logger,
        nocache,
        force_rebuild,
    )
    immutable_ref = test_spec.instance_image_key
    image_identity: dict[str, Any] | None = None
    if expected_image is not None:
        image_key = str(expected_image.get("image_key") or "")
        expected_id = str(expected_image.get("local_image_id") or "")
        repo_digests = expected_image.get("local_image_repo_digests")
        if (
            test_spec.instance_image_key != image_key
            or not expected_id.startswith("sha256:")
            or not isinstance(repo_digests, list)
            or not repo_digests
            or not all(isinstance(value, str) and "@sha256:" in value for value in repo_digests)
        ):
            _remove_container(original, client=client)
            raise RuntimeError("candidate_container_image_attestation_invalid")
        try:
            local_image = client.images.get(image_key)
            observed_id = str(local_image.id)
            observed_digests = sorted(
                str(value) for value in ((local_image.attrs or {}).get("RepoDigests") or [])
            )
        except Exception as exc:
            _remove_container(original, client=client)
            raise RuntimeError("candidate_container_image_inspect_failed") from exc
        if observed_id != expected_id or observed_digests != sorted(repo_digests):
            _remove_container(original, client=client)
            raise RuntimeError("candidate_container_image_identity_mismatch")
        image_repository = image_key.rsplit(":", 1)[0]
        matching_digests = sorted(
            value
            for value in repo_digests
            if value.startswith(image_repository + "@sha256:")
        )
        if not matching_digests:
            _remove_container(original, client=client)
            raise RuntimeError("candidate_container_image_repository_digest_mismatch")
        immutable_ref = matching_digests[0]
        image_identity = {
            "image_key": image_key,
            "expected_local_image_id": expected_id,
            "observed_local_image_id": observed_id,
            "immutable_repo_digest": immutable_ref,
            "repo_digests": observed_digests,
        }
    original_resource = _container_resource_identity(original)
    original_cleanup = _remove_container(
        original, client=client, expected_resource=original_resource
    )
    try:
        isolated = client.containers.create(
            image=immutable_ref,
            name=test_spec.get_instance_container_name(run_id),
            user=docker_user,
            detach=True,
            command="tail -f /dev/null",
            platform=test_spec.platform,
            cap_add=[],
            cap_drop=["ALL"],
            network_disabled=True,
            environment={},
            read_only=True,
            security_opt=["no-new-privileges:true"],
            pids_limit=PID_LIMIT,
            nano_cpus=NANO_CPU_LIMIT,
            mem_limit=MEMORY_LIMIT_BYTES,
            memswap_limit=MEMORY_LIMIT_BYTES,
            tmpfs={
                WRITABLE_TMP: "rw,nosuid,nodev,noexec,size=512m",
                WRITABLE_TESTBED: "rw,nosuid,nodev,size=3072m",
            },
            privileged=False,
        )
        isolated.reload()
        proof = isolation_proof(isolated)
        proof["resource_identity"] = _container_resource_identity(isolated)
        if image_identity is not None:
            proof["image_identity"] = image_identity
            proof["controls"]["immutable_image_id_match"] = bool(
                image_identity["expected_local_image_id"]
                == image_identity["observed_local_image_id"]
            )
            proof["controls"]["immutable_repo_digest_used"] = bool(
                immutable_ref == image_identity["immutable_repo_digest"]
            )
            proof["promotion_eligible"] = all(proof["controls"].values())
        proof["upstream_builder_cleanup"] = original_cleanup
        proof["controls"]["upstream_builder_cleanup_verified"] = bool(
            original_cleanup.get("cleanup_verified")
            and original_cleanup.get("volume_absence_verified")
        )
        proof["promotion_eligible"] = all(proof["controls"].values())
        if not proof["promotion_eligible"]:
            failed = sorted(
                name for name, passed in proof["controls"].items() if not passed
            )
            suffix = ",".join(failed)
            if proof["forbidden_environment_names"]:
                suffix += ";forbidden_environment_names:" + ",".join(
                    proof["forbidden_environment_names"]
                )
            raise RuntimeError("candidate_container_isolation_incomplete:" + suffix)
        isolated.rsi_isolation_proof = proof
        if hasattr(logger, "info"):
            logger.info("RSI grader isolation proof passed: %s", proof["schema"])
        return isolated
    except Exception:
        if "isolated" in locals():
            _remove_container(
                isolated,
                client=client,
                expected_resource=(locals().get("proof") or {}).get(
                    "resource_identity"
                ),
            )
        raise


@contextlib.contextmanager
def isolated_swebench_containers(
    *, expected_image: dict[str, Any] | None = None
) -> Iterator[list[dict[str, Any]]]:
    """Patch the harness create seam for one serialized grade operation."""

    from swebench.harness import run_evaluation

    with _PATCH_LOCK:
        original = run_evaluation.build_container
        proofs: list[dict[str, Any]] = []
        resources: list[tuple[Any, Any, dict[str, Any]]] = []

        def isolated_builder(
            test_spec: Any,
            client: Any,
            run_id: str,
            logger: Any,
            nocache: bool,
            force_rebuild: bool = False,
        ) -> Any:
            container = recreate_isolated_container(
                original,
                test_spec,
                client,
                run_id,
                logger,
                nocache,
                force_rebuild,
                expected_image=expected_image,
            )
            proof = container.rsi_isolation_proof
            proofs.append(proof)
            resources.append((client, container, proof))
            return container

        run_evaluation.build_container = isolated_builder
        try:
            yield proofs
        finally:
            run_evaluation.build_container = original
            cleanup_error: BaseException | None = None
            for client, container, proof in resources:
                try:
                    cleanup = _remove_container(
                        container,
                        client=client,
                        expected_resource=proof.get("resource_identity"),
                    )
                except Exception as exc:
                    proof["cleanup"] = {
                        "container_identity": str(
                            getattr(container, "id", None)
                            or getattr(container, "name", None)
                            or ""
                        )
                        or None,
                        "container_removed": False,
                        "volume_mount_names": [],
                        "volume_mount_count": None,
                        "volume_absence_verified": False,
                        "cleanup_verified": False,
                        "error_class": type(exc).__name__,
                    }
                    proof["controls"]["cleanup_verified"] = False
                    proof["promotion_eligible"] = False
                    cleanup_error = cleanup_error or exc
                else:
                    proof["cleanup"] = cleanup
                    proof["controls"]["cleanup_verified"] = True
                    proof["promotion_eligible"] = all(proof["controls"].values())
            if cleanup_error is not None:
                raise RuntimeError("candidate_container_cleanup_unverified") from cleanup_error


__all__ = [
    "forbidden_environment_names",
    "isolation_proof",
    "isolated_swebench_containers",
    "recreate_isolated_container",
]
