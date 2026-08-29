"""Fail-closed isolation adapter for official SWE-bench grading containers.

SWE-bench 4.x creates an instance container on Docker's default network. That
is acceptable for its generic harness, but not for RSI evaluation: candidate
code must not have network access or inherit provider/control credentials.
This adapter keeps the official report path while requiring the release-bound
instance image to be present by exact image ID. It creates the stopped instance
container directly with a read-only root, one bounded writable testbed volume,
no network/capabilities/host environment, no-new-privileges, and hard
PID/CPU/memory caps before the harness copies or executes the candidate patch.
"""

from __future__ import annotations

import contextlib
import importlib
import os
import threading
from collections.abc import Callable, Iterator
from pathlib import PurePosixPath
from typing import Any

from dharma_swarm.forge_lab.unattended_context import (
    UnattendedContextError,
    admitted_task_image,
    load_admitted_judge_dataset,
    validate_admitted_judge_instance,
)

_PATCH_LOCK = threading.Lock()
ISOLATION_PROOF_SCHEMA = "rsi_lab.grader_isolation_proof.v1"
SUPPORTED_SWEBENCH_VERSION = "4.1.0"
SUPPORTED_LINUX_RUNTIME_RECORD_DIGESTS = {
    "swebench": "sha256:e684d666e693675081edd9dc7524709a3f1d4a3e1f2d048a7cb5fe445a88c917",
    "docker": "sha256:c9beb105488ec004823a2b52094168dcccaa6ead6703693d7df7028f35d7d7e8",
    "datasets": "sha256:3787afe735a680d984a0399d866cc511096587225e3d6abfea76c3e259cf793f",
    "huggingface_hub": "sha256:dcc4254beb2da14662208d9231f520184eb07afd21efe83c717b1f645479b15d",
    "pyarrow": "sha256:a03283f58c4d742daa152f4b259a62368b58f04e3eaad6e59e1818a0ca996b64",
}
PID_LIMIT = 256
NANO_CPU_LIMIT = 2_000_000_000
MEMORY_LIMIT_BYTES = 4 * 1024 * 1024 * 1024
WRITABLE_TESTBED = "/testbed"
WRITABLE_TMP = "/tmp"
UPSTREAM_EVAL_SCRIPT = PurePosixPath("/eval.sh")
ISOLATED_EVAL_SCRIPT = PurePosixPath("/tmp/rsi-swebench-eval.sh")
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
        container.remove(force=True, v=True)
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
    expected_image_id = getattr(container, "rsi_admitted_image_id", None)
    fields = {
        "image_identity_pinned": bool(
            expected_image_id and attrs.get("Image") == expected_image_id
        ),
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
        "image_identity": {
            "expected_id": expected_image_id,
            "actual_id": attrs.get("Image"),
        },
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
    """Create an isolated container, refusing all build/pull paths when pinned."""

    if docker_user is None:
        from swebench.harness.constants import DOCKER_USER

        docker_user = DOCKER_USER

    pinned_image_id = getattr(test_spec, "rsi_admitted_image_id", None)
    if os.environ.get("RSI_LAB_REQUIRE_PINNED_SWEBENCH_IMAGE") == "1":
        if force_rebuild or not pinned_image_id:
            raise RuntimeError("release_bound_image_cannot_be_rebuilt")
        try:
            cached_image = client.images.get(pinned_image_id)
        except Exception as exc:
            raise RuntimeError("release_bound_image_not_cached") from exc
        if getattr(cached_image, "id", None) != pinned_image_id:
            raise RuntimeError("release_bound_image_id_mismatch")
    else:
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
        isolated.rsi_admitted_image_id = getattr(
            test_spec,
            "rsi_admitted_image_id",
            None,
        )
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

    run_evaluation = _swebench_run_evaluation()

    with _PATCH_LOCK:
        original_builder = run_evaluation.build_container
        original_cleanup = run_evaluation.cleanup_container
        original_copy = run_evaluation.copy_to_container
        original_exec = run_evaluation.exec_run_with_timeout
        original_load_dataset = run_evaluation.load_swebench_dataset
        original_make_spec = run_evaluation.make_test_spec
        proofs: list[dict[str, Any]] = []

        class PinnedImageTestSpec:
            def __init__(
                self,
                delegate: Any,
                fixture: dict[str, Any],
                judge_proof: dict[str, Any],
            ) -> None:
                self._delegate = delegate
                self.rsi_admitted_image_id = fixture["image_id"]
                self.rsi_admitted_image_reference = fixture["image_reference"]
                self.rsi_admitted_judge_row_sha256 = judge_proof["row_sha256"]

            @property
            def instance_image_key(self) -> str:
                return str(self.rsi_admitted_image_id)

            def __getattr__(self, name: str) -> Any:
                return getattr(self._delegate, name)

        def pinned_make_test_spec(instance: Any, *args: Any, **kwargs: Any) -> Any:
            if os.environ.get("RSI_LAB_REQUIRE_PINNED_SWEBENCH_IMAGE") != "1":
                return original_make_spec(instance, *args, **kwargs)
            task_id = str(
                getattr(instance, "instance_id", "")
                or (instance.get("instance_id") if isinstance(instance, dict) else "")
            )
            fixture = admitted_task_image(task_id)
            try:
                judge_proof = validate_admitted_judge_instance(
                    instance,
                    task_id=task_id,
                )
            except UnattendedContextError as exc:
                raise RuntimeError(
                    f"swebench_instance_not_release_bound:{exc.code}"
                ) from exc
            module = importlib.import_module(original_make_spec.__module__)
            original_env_builder = module.make_env_script_list
            module.make_env_script_list = lambda *_args, **_kwargs: []
            try:
                spec = original_make_spec(instance, *args, **kwargs)
            finally:
                module.make_env_script_list = original_env_builder
            if (
                spec.instance_image_key != fixture["image_reference"]
                or spec.platform != "linux/x86_64"
            ):
                raise RuntimeError("swebench_image_reference_not_release_bound")
            return PinnedImageTestSpec(spec, fixture, judge_proof)

        def pinned_load_dataset(
            name: str,
            split: str,
            instance_ids: list[str] | None = None,
        ) -> Any:
            if os.environ.get("RSI_LAB_REQUIRE_PINNED_SWEBENCH_IMAGE") != "1":
                return original_load_dataset(name, split, instance_ids)
            try:
                return load_admitted_judge_dataset(name, split, instance_ids)
            except UnattendedContextError as exc:
                raise RuntimeError(
                    f"swebench_dataset_not_release_bound:{exc.code}"
                ) from exc

        def isolated_builder(
            test_spec: Any,
            client: Any,
            run_id: str,
            logger: Any,
            nocache: bool,
            force_rebuild: bool = False,
        ) -> Any:
            container = recreate_isolated_container(
                original_builder,
                test_spec,
                client,
                run_id,
                logger,
                nocache,
                force_rebuild,
            )
            proofs.append(dict(container.rsi_isolation_proof))
            return container

        def isolated_copy(
            container: Any,
            source: Any,
            destination: PurePosixPath,
        ) -> Any:
            target = (
                ISOLATED_EVAL_SCRIPT
                if PurePosixPath(destination) == UPSTREAM_EVAL_SCRIPT
                else destination
            )
            return original_copy(container, source, target)

        def isolated_exec(container: Any, command: str, timeout: int) -> Any:
            bounded_command = (
                f"/bin/bash {ISOLATED_EVAL_SCRIPT}"
                if command == f"/bin/bash {UPSTREAM_EVAL_SCRIPT}"
                else command
            )
            return original_exec(container, bounded_command, timeout)

        def isolated_cleanup(client: Any, container: Any, logger: Any) -> Any:
            if not getattr(container, "rsi_isolation_proof", None):
                return original_cleanup(client, container, logger)
            original_remove = container.remove

            def remove_with_volumes(*args: Any, **kwargs: Any) -> Any:
                kwargs["v"] = True
                return original_remove(*args, **kwargs)

            container.remove = remove_with_volumes
            try:
                return original_cleanup(client, container, logger)
            finally:
                container.remove = original_remove

        run_evaluation.build_container = isolated_builder
        run_evaluation.cleanup_container = isolated_cleanup
        run_evaluation.copy_to_container = isolated_copy
        run_evaluation.exec_run_with_timeout = isolated_exec
        run_evaluation.load_swebench_dataset = pinned_load_dataset
        run_evaluation.make_test_spec = pinned_make_test_spec
        try:
            yield proofs
        finally:
            run_evaluation.build_container = original_builder
            run_evaluation.cleanup_container = original_cleanup
            run_evaluation.copy_to_container = original_copy
            run_evaluation.exec_run_with_timeout = original_exec
            run_evaluation.load_swebench_dataset = original_load_dataset
            run_evaluation.make_test_spec = original_make_spec


def _swebench_run_evaluation() -> Any:
    from swebench.harness import run_evaluation

    return run_evaluation


__all__ = [
    "forbidden_environment_names",
    "isolation_proof",
    "isolated_swebench_containers",
    "recreate_isolated_container",
]
