"""Fail-closed isolation adapter for official SWE-bench grading containers.

SWE-bench 4.x creates an instance container on Docker's default network. That
is acceptable for its generic harness, but not for RSI evaluation: candidate
code must not have network access or inherit provider/control credentials.
This adapter keeps the official image build and report path, then recreates the
stopped instance container with a read-only root, one bounded writable testbed
volume, no network/capabilities/host environment, no-new-privileges, and hard
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


def _remove_container(container: Any) -> None:
    try:
        container.remove(force=True)
    except Exception:
        # A Docker outage must not conceal the original isolation error.
        pass


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
        "testbed_volume_declared": WRITABLE_TESTBED in declared_volumes
        or WRITABLE_TESTBED in writable_mounts,
        "tmpfs_bounded": set(tmpfs) == {WRITABLE_TMP},
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
    _remove_container(original)
    try:
        isolated = client.containers.create(
            image=test_spec.instance_image_key,
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
            tmpfs={WRITABLE_TMP: "rw,nosuid,nodev,noexec,size=512m"},
            volumes=[WRITABLE_TESTBED],
            privileged=False,
        )
        isolated.reload()
        proof = isolation_proof(isolated)
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
            _remove_container(isolated)
        raise


@contextlib.contextmanager
def isolated_swebench_containers() -> Iterator[list[dict[str, Any]]]:
    """Patch the harness create seam for one serialized grade operation."""

    from swebench.harness import run_evaluation

    with _PATCH_LOCK:
        original = run_evaluation.build_container
        proofs: list[dict[str, Any]] = []

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
            )
            proofs.append(dict(container.rsi_isolation_proof))
            return container

        run_evaluation.build_container = isolated_builder
        try:
            yield proofs
        finally:
            run_evaluation.build_container = original


__all__ = [
    "forbidden_environment_names",
    "isolation_proof",
    "isolated_swebench_containers",
    "recreate_isolated_container",
]
