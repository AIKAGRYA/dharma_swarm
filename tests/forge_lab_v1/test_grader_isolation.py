from __future__ import annotations

from types import SimpleNamespace

import pytest

from dharma_swarm.forge_lab import grader_isolation

_IMAGE_ID = "sha256:" + "1" * 64


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
            "Image": _IMAGE_ID,
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
        self.removed_with_volumes = False
        self.reloaded = False

    def reload(self) -> None:
        self.reloaded = True

    def remove(self, *, force: bool, v: bool = False) -> None:
        assert force is True
        self.removed = True
        self.removed_with_volumes = v


class _Containers:
    def __init__(self, result: _Container):
        self.result = result
        self.kwargs: dict[str, object] | None = None

    def create(self, **kwargs: object) -> _Container:
        self.kwargs = kwargs
        return self.result


class _Images:
    def __init__(self, image_id: str = _IMAGE_ID, *, fail: bool = False):
        self.image_id = image_id
        self.fail = fail
        self.lookups: list[str] = []
        self.pull_calls: list[str] = []

    def get(self, image_id: str) -> SimpleNamespace:
        self.lookups.append(image_id)
        if self.fail:
            raise RuntimeError("image absent")
        return SimpleNamespace(id=self.image_id)

    def pull(self, image: str) -> None:
        self.pull_calls.append(image)
        raise AssertionError("pinned grading must never pull")


def _spec() -> SimpleNamespace:
    return SimpleNamespace(
        instance_image_key=_IMAGE_ID,
        rsi_admitted_image_id=_IMAGE_ID,
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
        docker_user="root",
    )

    assert result is isolated
    assert original.removed is True
    assert original.removed_with_volumes is True
    assert isolated.reloaded is True
    assert containers.kwargs is not None
    assert containers.kwargs["network_disabled"] is True
    assert containers.kwargs["environment"] == {}
    assert containers.kwargs["image"] == _IMAGE_ID
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
            docker_user="root",
        )
    assert container.removed is True
    assert container.removed_with_volumes is True


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
            docker_user="root",
        )
    assert container.removed is True
    assert container.removed_with_volumes is True


def test_pinned_container_uses_cached_exact_id_without_builder_or_pull(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    isolated = _Container(network_disabled=True)
    containers = _Containers(isolated)
    images = _Images()
    client = SimpleNamespace(containers=containers, images=images)
    builder_calls: list[object] = []

    def original_builder(*args: object, **_kwargs: object) -> object:
        builder_calls.extend(args)
        raise AssertionError("pinned grading must never invoke the builder")

    monkeypatch.setenv("RSI_LAB_REQUIRE_PINNED_SWEBENCH_IMAGE", "1")
    result = grader_isolation.recreate_isolated_container(
        original_builder,
        _spec(),
        client,
        "run-pinned",
        SimpleNamespace(),
        False,
        docker_user="root",
    )

    assert result is isolated
    assert builder_calls == []
    assert images.lookups == [_IMAGE_ID]
    assert images.pull_calls == []
    assert containers.kwargs is not None
    assert containers.kwargs["image"] == _IMAGE_ID


def test_pinned_container_fails_closed_when_exact_image_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    containers = _Containers(_Container(network_disabled=True))
    images = _Images(fail=True)
    client = SimpleNamespace(containers=containers, images=images)

    monkeypatch.setenv("RSI_LAB_REQUIRE_PINNED_SWEBENCH_IMAGE", "1")
    with pytest.raises(RuntimeError, match="release_bound_image_not_cached"):
        grader_isolation.recreate_isolated_container(
            lambda *_args, **_kwargs: pytest.fail("builder must not run"),
            _spec(),
            client,
            "run-missing",
            SimpleNamespace(),
            False,
            docker_user="root",
        )

    assert images.lookups == [_IMAGE_ID]
    assert images.pull_calls == []
    assert containers.kwargs is None


def test_eval_script_is_redirected_to_bounded_tmpfs_and_hooks_are_restored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    copied: list[object] = []
    executed: list[str] = []

    def original_builder(*_args: object, **_kwargs: object) -> object:
        return object()

    def original_copy(
        _container: object,
        _source: object,
        destination: object,
    ) -> None:
        copied.append(destination)

    def original_exec(
        _container: object,
        command: str,
        _timeout: int,
    ) -> tuple[str, bool, float]:
        executed.append(command)
        return "", False, 0.0

    def original_cleanup(_client: object, container: object, _logger: object) -> None:
        container.remove(force=True)

    def original_make(instance: object, *_args: object, **_kwargs: object) -> object:
        return instance

    harness = SimpleNamespace(
        build_container=original_builder,
        cleanup_container=original_cleanup,
        copy_to_container=original_copy,
        exec_run_with_timeout=original_exec,
        make_test_spec=original_make,
    )
    monkeypatch.setattr(grader_isolation, "_swebench_run_evaluation", lambda: harness)

    with grader_isolation.isolated_swebench_containers():
        harness.copy_to_container(object(), object(), grader_isolation.UPSTREAM_EVAL_SCRIPT)
        harness.copy_to_container(object(), object(), "/tmp/patch.diff")
        harness.exec_run_with_timeout(object(), "/bin/bash /eval.sh", 60)
        harness.exec_run_with_timeout(object(), "git status", 60)
        isolated = _Container(network_disabled=True)
        isolated.rsi_isolation_proof = {"promotion_eligible": True}
        harness.cleanup_container(object(), isolated, object())

    assert copied == [grader_isolation.ISOLATED_EVAL_SCRIPT, "/tmp/patch.diff"]
    assert executed == [
        f"/bin/bash {grader_isolation.ISOLATED_EVAL_SCRIPT}",
        "git status",
    ]
    assert isolated.removed_with_volumes is True
    assert harness.build_container is original_builder
    assert harness.cleanup_container is original_cleanup
    assert harness.copy_to_container is original_copy
    assert harness.exec_run_with_timeout is original_exec
    assert harness.make_test_spec is original_make


def test_pinned_test_spec_uses_cached_image_id_and_skips_env_network_builder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task_id = "django__django-12209"
    fixture = grader_isolation.admitted_task_image(task_id)

    def network_builder(*_args: object, **_kwargs: object) -> list[str]:
        return ["network"]

    spec_module = SimpleNamespace(make_env_script_list=network_builder)

    def make_spec(instance: dict[str, str], *_args: object, **_kwargs: object):
        assert spec_module.make_env_script_list(instance, {}, "testbed") == []
        return SimpleNamespace(
            instance_id=task_id,
            repo=fixture["repo"],
            base_commit=fixture["base_commit"],
            instance_image_key=fixture["image_reference"],
            platform="linux/x86_64",
        )

    harness = SimpleNamespace(
        build_container=lambda *_args, **_kwargs: None,
        cleanup_container=lambda *_args, **_kwargs: None,
        copy_to_container=lambda *_args, **_kwargs: None,
        exec_run_with_timeout=lambda *_args, **_kwargs: None,
        make_test_spec=make_spec,
    )
    monkeypatch.setenv("RSI_LAB_REQUIRE_PINNED_SWEBENCH_IMAGE", "1")
    monkeypatch.setattr(grader_isolation, "_swebench_run_evaluation", lambda: harness)
    monkeypatch.setattr(
        grader_isolation.importlib,
        "import_module",
        lambda _name: spec_module,
    )

    instance = {
        "instance_id": task_id,
        "repo": fixture["repo"],
        "base_commit": fixture["base_commit"],
    }
    with grader_isolation.isolated_swebench_containers():
        pinned = harness.make_test_spec(instance)
        assert pinned.instance_image_key == fixture["image_id"]
        assert pinned.rsi_admitted_image_reference == fixture["image_reference"]

    assert harness.make_test_spec is make_spec
    assert spec_module.make_env_script_list is network_builder
