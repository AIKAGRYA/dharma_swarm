from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace

import pytest

from dharma_swarm.forge_lab import grader_isolation


class NotFound(RuntimeError):
    status_code = 404


class _Volumes:
    def __init__(self):
        self.present: set[str] = set()

    def get(self, name: str):
        if name not in self.present:
            raise NotFound(name)
        return SimpleNamespace(name=name)


class _Container:
    def __init__(
        self,
        identity: str,
        *,
        network_disabled: bool,
        env: list[str] | None = None,
        volume_names: tuple[str, ...] = (),
        host_overrides: dict[str, object] | None = None,
    ):
        host = {
            "CapDrop": ["ALL"],
            "CapAdd": [],
            "Privileged": False,
            "ReadonlyRootfs": True,
            "SecurityOpt": ["no-new-privileges:true"],
            "PidsLimit": grader_isolation.PID_LIMIT,
            "NanoCpus": grader_isolation.NANO_CPU_LIMIT,
            "Memory": grader_isolation.MEMORY_LIMIT_BYTES,
            "MemorySwap": grader_isolation.MEMORY_LIMIT_BYTES,
            "Tmpfs": {
                "/tmp": "rw,nosuid,nodev,noexec,size=512m",
                "/testbed": "rw,nosuid,nodev,size=3072m",
            },
        }
        host.update(host_overrides or {})
        mounts = [
            {"Type": "volume", "Name": name, "Destination": "/testbed", "RW": True}
            for name in volume_names
        ]
        if not mounts:
            mounts = [
                {"Type": "tmpfs", "Destination": "/tmp", "RW": True},
                {"Type": "tmpfs", "Destination": "/testbed", "RW": True},
            ]
        self.id = identity
        self.name = identity
        self.attrs = {
            "Id": identity,
            "Config": {
                "NetworkDisabled": network_disabled,
                "Env": env or ["PATH=/usr/bin", "LANG=C.UTF-8"],
                "Volumes": {},
            },
            "HostConfig": host,
            "NetworkSettings": {"Networks": {}},
            "Mounts": mounts,
        }
        self.volume_names = volume_names
        self.removed = False
        self.reloaded = False
        self.remove_fail = False
        self.leave_volumes = False
        self.owner = None
        self.volumes = None

    def reload(self) -> None:
        if self.removed:
            raise NotFound(self.id)
        self.reloaded = True

    def remove(self, *, force: bool, v: bool) -> None:
        assert force is True and v is True
        if self.remove_fail:
            raise RuntimeError("docker unavailable")
        self.removed = True
        if self.owner is not None:
            self.owner.present.pop(self.id, None)
        if v and not self.leave_volumes and self.volumes is not None:
            for name in self.volume_names:
                self.volumes.present.discard(name)


class _Containers:
    def __init__(self, result: _Container, volumes: _Volumes):
        self.result = result
        self.volumes = volumes
        self.present: dict[str, _Container] = {}
        self.kwargs: dict[str, object] | None = None
        self.add(result)

    def add(self, container: _Container) -> None:
        container.owner = self
        container.volumes = self.volumes
        self.present[container.id] = container
        self.volumes.present.update(container.volume_names)

    def create(self, **kwargs: object) -> _Container:
        self.kwargs = kwargs
        self.add(self.result)
        return self.result

    def get(self, identity: str) -> _Container:
        try:
            return self.present[identity]
        except KeyError as exc:
            raise NotFound(identity) from exc


def _client(original: _Container, isolated: _Container):
    volumes = _Volumes()
    containers = _Containers(isolated, volumes)
    containers.add(original)
    return SimpleNamespace(containers=containers, volumes=volumes)


def _spec() -> SimpleNamespace:
    return SimpleNamespace(
        instance_image_key="swebench/example:latest",
        platform="linux/amd64",
        get_instance_container_name=lambda run_id: f"candidate-{run_id}",
    )


def test_forbidden_environment_detection_returns_names_only() -> None:
    secret = "do-not-return-this-value"
    names = grader_isolation.forbidden_environment_names(
        [f"OPENAI_API_KEY={secret}", "DHARMA_HOME=/control", "PATH=/usr/bin"]
    )
    assert names == ["DHARMA_HOME", "OPENAI_API_KEY"]
    assert secret not in repr(names)


def test_official_builder_volume_and_container_are_removed_and_receipted() -> None:
    original = _Container(
        "original-1", network_disabled=False, volume_names=("anonymous-testbed-1",)
    )
    isolated = _Container("isolated-1", network_disabled=True)
    client = _client(original, isolated)
    result = grader_isolation.recreate_isolated_container(
        lambda *_args, **_kwargs: original,
        _spec(),
        client,
        "run-1",
        SimpleNamespace(),
        False,
        docker_user="root",
    )
    proof = result.rsi_isolation_proof
    assert original.removed is True
    assert "anonymous-testbed-1" not in client.volumes.present
    assert proof["upstream_builder_cleanup"] == {
        "resource_identity": {
            "container_identity": "original-1",
            "volume_mounts": [
                {"name": "anonymous-testbed-1", "destination": "/testbed"}
            ],
            "volume_mount_names": ["anonymous-testbed-1"],
            "volume_mount_count": 1,
        },
        "container_identity": "original-1",
        "container_absent_before_remove": False,
        "container_removed": True,
        "container_absence_verified": True,
        "volume_mount_names": ["anonymous-testbed-1"],
        "volume_mount_count": 1,
        "volume_absence_verified": True,
        "cleanup_verified": True,
    }
    assert proof["resource_identity"] == {
        "container_identity": "isolated-1",
        "volume_mounts": [],
        "volume_mount_names": [],
        "volume_mount_count": 0,
    }
    assert proof["promotion_eligible"] is True
    assert set(client.containers.kwargs["tmpfs"]) == {"/tmp", "/testbed"}
    assert "volumes" not in client.containers.kwargs


def test_cleanup_remove_failure_is_surfaced() -> None:
    original = _Container("original-fail", network_disabled=False)
    original.remove_fail = True
    isolated = _Container("isolated-fail", network_disabled=True)
    client = _client(original, isolated)
    with pytest.raises(RuntimeError, match="cleanup_remove_failed"):
        grader_isolation.recreate_isolated_container(
            lambda *_args, **_kwargs: original,
            _spec(), client, "run-fail", SimpleNamespace(), False, docker_user="root"
        )


def test_original_anonymous_volume_cleanup_must_be_verified() -> None:
    original = _Container(
        "original-volume", network_disabled=False, volume_names=("leaked-volume",)
    )
    original.leave_volumes = True
    isolated = _Container("isolated-volume", network_disabled=True)
    client = _client(original, isolated)
    with pytest.raises(RuntimeError, match="volume_still_present"):
        grader_isolation.recreate_isolated_container(
            lambda *_args, **_kwargs: original,
            _spec(), client, "run-volume", SimpleNamespace(), False, docker_user="root"
        )


def test_isolation_proof_checks_inspected_volume_mounts_not_only_config() -> None:
    isolated = _Container(
        "isolated-with-volume",
        network_disabled=True,
        volume_names=("unexpected-volume",),
    )
    isolated.attrs["Config"]["Volumes"] = {}
    proof = grader_isolation.isolation_proof(isolated)
    assert proof["controls"]["anonymous_volumes_absent"] is False
    assert proof["promotion_eligible"] is False


def test_isolation_failure_removes_candidate_and_surfaces_cleanup() -> None:
    original = _Container("original-bad", network_disabled=False)
    isolated = _Container("isolated-bad", network_disabled=False)
    client = _client(original, isolated)
    with pytest.raises(RuntimeError, match="network_disabled"):
        grader_isolation.recreate_isolated_container(
            lambda *_args, **_kwargs: original,
            _spec(), client, "run-bad", SimpleNamespace(), False, docker_user="root"
        )
    assert isolated.removed is True


def test_context_closeout_mutates_proof_and_cleanup_failure_is_not_swallowed(
    monkeypatch,
) -> None:
    original = _Container("original-context", network_disabled=False)
    isolated = _Container("isolated-context", network_disabled=True)
    client = _client(original, isolated)
    run_evaluation = SimpleNamespace(
        build_container=lambda *_args, **_kwargs: original
    )
    harness = ModuleType("swebench.harness")
    harness.run_evaluation = run_evaluation
    constants = ModuleType("swebench.harness.constants")
    constants.DOCKER_USER = "root"
    swebench = ModuleType("swebench")
    swebench.harness = harness
    monkeypatch.setitem(sys.modules, "swebench", swebench)
    monkeypatch.setitem(sys.modules, "swebench.harness", harness)
    monkeypatch.setitem(sys.modules, "swebench.harness.constants", constants)

    proofs = None
    with pytest.raises(RuntimeError, match="cleanup_unverified"):
        with grader_isolation.isolated_swebench_containers() as proofs:
            built = run_evaluation.build_container(
                _spec(), client, "run-context", SimpleNamespace(), False
            )
            built.remove_fail = True
            assert proofs[0]["promotion_eligible"] is True
    assert proofs is not None
    assert proofs[0]["cleanup"]["cleanup_verified"] is False
    assert proofs[0]["controls"]["cleanup_verified"] is False
    assert proofs[0]["promotion_eligible"] is False
