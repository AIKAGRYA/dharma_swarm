from __future__ import annotations

from types import SimpleNamespace

import pytest

from dharma_swarm.forge_lab import grader_isolation


class _Container:
    def __init__(
        self,
        *,
        network_disabled: bool,
        env: list[str] | None = None,
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
            "Tmpfs": {"/tmp": "rw,nosuid,nodev,noexec,size=512m"},
        }
        host.update(host_overrides or {})
        self.attrs = {
            "Config": {
                "NetworkDisabled": network_disabled,
                "Env": env or ["PATH=/usr/bin", "LANG=C.UTF-8"],
                "Volumes": {"/testbed": {}},
            },
            "HostConfig": host,
            "NetworkSettings": {"Networks": {}},
            "Mounts": [{"Destination": "/testbed", "RW": True}],
        }
        self.removed = False
        self.reloaded = False

    def reload(self) -> None:
        self.reloaded = True

    def remove(self, *, force: bool) -> None:
        assert force is True
        self.removed = True


class _Containers:
    def __init__(self, result: _Container):
        self.result = result
        self.kwargs: dict[str, object] | None = None

    def create(self, **kwargs: object) -> _Container:
        self.kwargs = kwargs
        return self.result


def _spec() -> SimpleNamespace:
    return SimpleNamespace(
        instance_image_key="swebench/example:latest",
        platform="linux/amd64",
        docker_specs={"run_args": {"cap_add": ["SYS_ADMIN"]}},
        get_instance_container_name=lambda run_id: f"candidate-{run_id}",
    )


def test_forbidden_environment_detection_returns_names_only() -> None:
    secret = "do-not-return-this-value"
    names = grader_isolation.forbidden_environment_names(
        [
            f"OPENAI_API_KEY={secret}",
            f"openrouter_api_key={secret}",
            "DHARMA_HOME=/control/state",
            "A2A_AGENT_UID=judge",
            "PATH=/usr/bin",
        ]
    )
    assert names == [
        "A2A_AGENT_UID",
        "DHARMA_HOME",
        "OPENAI_API_KEY",
        "OPENROUTER_API_KEY",
    ]
    assert secret not in repr(names)


def test_official_container_is_recreated_offline_with_empty_host_environment() -> None:
    original = _Container(network_disabled=False)
    isolated = _Container(network_disabled=True)
    containers = _Containers(isolated)
    client = SimpleNamespace(containers=containers)

    result = grader_isolation.recreate_isolated_container(
        lambda *_args, **_kwargs: original,
        _spec(),
        client,
        "run-1",
        SimpleNamespace(),
        False,
    )

    assert result is isolated
    assert original.removed is True
    assert isolated.reloaded is True
    assert containers.kwargs is not None
    assert containers.kwargs["network_disabled"] is True
    assert containers.kwargs["environment"] == {}
    assert containers.kwargs["image"] == "swebench/example:latest"
    assert containers.kwargs["cap_add"] == []
    assert containers.kwargs["cap_drop"] == ["ALL"]
    assert containers.kwargs["read_only"] is True
    assert containers.kwargs["security_opt"] == ["no-new-privileges:true"]
    assert containers.kwargs["pids_limit"] == grader_isolation.PID_LIMIT
    assert containers.kwargs["nano_cpus"] == grader_isolation.NANO_CPU_LIMIT
    assert containers.kwargs["mem_limit"] == grader_isolation.MEMORY_LIMIT_BYTES
    assert containers.kwargs["memswap_limit"] == grader_isolation.MEMORY_LIMIT_BYTES
    assert result.rsi_isolation_proof["promotion_eligible"] is True
    assert all(result.rsi_isolation_proof["controls"].values())


@pytest.mark.parametrize(
    ("container", "match"),
    [
        (_Container(network_disabled=False), "network_disabled"),
        (
            _Container(network_disabled=True, env=["KIMI_API_KEY=redacted"]),
            "forbidden_environment_names:KIMI_API_KEY",
        ),
    ],
)
def test_isolation_attestation_failure_removes_candidate_container(
    container: _Container,
    match: str,
) -> None:
    client = SimpleNamespace(containers=_Containers(container))
    with pytest.raises(RuntimeError, match=match):
        grader_isolation.recreate_isolated_container(
            lambda *_args, **_kwargs: _Container(network_disabled=False),
            _spec(),
            client,
            "run-2",
            SimpleNamespace(),
            False,
        )
    assert container.removed is True


def test_missing_resource_or_privilege_control_blocks_promotion() -> None:
    container = _Container(
        network_disabled=True,
        host_overrides={"CapAdd": ["SYS_ADMIN"], "PidsLimit": 0},
    )
    client = SimpleNamespace(containers=_Containers(container))
    with pytest.raises(RuntimeError, match="cap_add_none.*pid_limit"):
        grader_isolation.recreate_isolated_container(
            lambda *_args, **_kwargs: _Container(network_disabled=False),
            _spec(),
            client,
            "run-3",
            SimpleNamespace(),
            False,
        )
    assert container.removed is True
