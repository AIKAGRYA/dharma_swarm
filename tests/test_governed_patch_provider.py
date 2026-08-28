from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path

import pytest

from dharma_swarm import governed_patch_provider_authorship as authorship_module
from dharma_swarm.governed_patch_candidate_bundle import verify_candidate_bundle
from dharma_swarm.governed_patch_evidence import (
    GovernedPatchEvidenceError,
    NativePatchBindings,
    build_governed_patch_request_v2_content,
    governed_patch_task_snapshot_sha256,
    parse_governed_patch_request,
)
from dharma_swarm.governed_patch_provider_authorship import (
    ProviderCallEvidenceState,
    ProviderCallIndeterminateError,
    ProviderSession,
    author_governed_patch,
    inspect_provider_call_evidence,
    recover_provider_authorship_result,
    verify_provider_authorship_receipt,
)
from dharma_swarm.models import LLMRequest, LLMResponse, ProviderType
from dharma_swarm.runtime_provider import (
    RuntimeProviderConfig,
    runtime_provider_transport_identity,
)
from scripts.runtime import governed_patch_provider as provider_script

BASE_SHA = "a" * 40
DELIVERY_ID = "d" * 24
SOURCE_PATH = "pkg/example.py"
SOURCE = 'def value():\n    return "old"\n'
SEMANTIC_INTENT = "Change value() to return the new marker."
SEMANTIC_ARTIFACT_SHA = "f" * 64
EDIT = (
    "<<<<<<< SEARCH path=pkg/example.py\n"
    '    return "old"\n'
    "=======\n"
    '    return "new"\n'
    ">>>>>>> REPLACE\n"
)
CANONICAL_ENDPOINT = runtime_provider_transport_identity(
    RuntimeProviderConfig(
        provider=ProviderType.OLLAMA,
        base_url="https://ollama.com",
        transport_mode="cloud_api",
    )
)


def _bindings() -> NativePatchBindings:
    return NativePatchBindings(
        mission_id="mission-1",
        task_id="task-1",
        attempt_id="packet-1",
        lease_id=DELIVERY_ID,
        packet_id="packet-1",
        correlation_id="a2a_send:codex_composer:packet-1",
        delivery_id=DELIVERY_ID,
        proposal_id="proposal-1",
        base_sha=BASE_SHA,
        executor_agent_uid="codex_composer",
        executor_run_id="executor-run-1",
        executor_process_boot_id="boot-1",
    )


def _request(repo: Path):
    bindings = _bindings()
    task_snapshot = governed_patch_task_snapshot_sha256(
        mission_id=bindings.mission_id,
        task_id=bindings.task_id,
        title="Make the bounded change",
        description="Change only the authorized source file.",
        mission_task_creation_hash="e" * 64,
        completion_contract="governed_patch_effect_v1",
        status="pending",
        assigned_to=None,
        result=None,
    )
    content = build_governed_patch_request_v2_content(
        bindings,
        authorized_source_path=SOURCE_PATH,
        oracle_argv=["python3", "-m", "pytest", "tests/test_example.py", "-q"],
        semantic_intent=SEMANTIC_INTENT,
        task_snapshot_sha256=task_snapshot,
    )
    return parse_governed_patch_request(
        content,
        repo_root=repo,
        expected=bindings,
        accepted_base_sha=BASE_SHA,
        expected_content_sha256=hashlib.sha256(content.encode()).hexdigest(),
        expected_semantic_intent=SEMANTIC_INTENT,
        expected_task_snapshot_sha256=task_snapshot,
    )


@pytest.fixture
def roots(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    (repo / "pkg").mkdir(parents=True)
    (repo / SOURCE_PATH).write_text(SOURCE, encoding="utf-8", newline="")
    return repo, tmp_path / "evidence"


class FakeProvider:
    def __init__(
        self,
        response: LLMResponse | None = None,
        *,
        error: Exception | None = None,
        delay: float = 0,
        close_error: Exception | None = None,
    ) -> None:
        self.response = response or LLMResponse(
            content=EDIT,
            model=authorship_module.REQUESTED_WIRE_MODEL,
            provider=authorship_module.REQUESTED_PROVIDER,
            usage={
                "prompt_tokens": 11,
                "completion_tokens": 7,
                "total_tokens": 18,
            },
            stop_reason="stop",
        )
        self.error = error
        self.delay = delay
        self.close_error = close_error
        self.calls = 0
        self.closes = 0
        self.requests: list[LLMRequest] = []

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.calls += 1
        self.requests.append(request)
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error is not None:
            raise self.error
        return self.response

    async def close(self) -> None:
        self.closes += 1
        if self.close_error is not None:
            raise self.close_error


def _session(provider: FakeProvider) -> ProviderSession:
    return ProviderSession(provider, CANONICAL_ENDPOINT)


def _inspect(request, evidence: Path) -> ProviderCallEvidenceState:
    return inspect_provider_call_evidence(
        request,
        evidence_root=evidence,
        semantic_artifact_sha256=SEMANTIC_ARTIFACT_SHA,
    )


def test_governed_provider_model_ids_are_canonical_pool_projections() -> None:
    logical_id = authorship_module.default_for_provider(ProviderType.ZHIPU)
    assert authorship_module.REQUESTED_WIRE_MODEL == logical_id
    assert authorship_module.REQUESTED_MODEL == (
        authorship_module.required_provider_model_id(
            logical_id,
            ProviderType.OLLAMA,
        )
    )
    assert authorship_module.SERVED_MODELS == frozenset(
        (authorship_module.REQUESTED_WIRE_MODEL, authorship_module.REQUESTED_MODEL)
    )


@pytest.mark.asyncio
async def test_exact_ollama_client_uses_canonical_wire_model() -> None:
    observed: dict[str, object] = {}

    class HttpResponse:
        status_code = 200
        text = ""

        @staticmethod
        def json():
            return {
                "model": authorship_module.REQUESTED_WIRE_MODEL,
                "choices": [
                    {
                        "message": {"content": EDIT},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {},
            }

    class HttpClient:
        async def post(self, url, *, json, headers):
            observed.update(url=url, payload=json, headers=headers)
            return HttpResponse()

    class RuntimeOllama:
        def _get_client(self):
            return HttpClient()

        def _headers_or_raise(self):
            return {"Authorization": "not-recorded"}

        def _build_messages(self, request):
            return request.messages

        async def close(self):
            observed["closed"] = True

    client = provider_script._ExactOllamaCloudClient(RuntimeOllama())
    response = await client.complete(
        LLMRequest(
            model=authorship_module.REQUESTED_MODEL,
            messages=[{"role": "user", "content": "bounded"}],
            tools=[],
        )
    )
    await client.close()

    assert observed["payload"]["model"] == authorship_module.REQUESTED_WIRE_MODEL
    assert response.model == authorship_module.REQUESTED_WIRE_MODEL
    assert observed["closed"] is True


def test_canonical_provider_bootstraps_runtime_env_before_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    config = RuntimeProviderConfig(
        provider=ProviderType.OLLAMA,
        api_key="not-recorded",
        base_url="https://ollama.com",
        default_model=authorship_module.REQUESTED_MODEL,
        transport_mode="cloud_api",
        available=True,
    )
    inner = FakeProvider()
    monkeypatch.setattr(
        provider_script,
        "bootstrap_runtime_env",
        lambda: calls.append("bootstrap"),
    )

    def resolve(*_args, **_kwargs):
        calls.append("resolve")
        return config

    monkeypatch.setattr(provider_script, "resolve_runtime_provider_config", resolve)
    monkeypatch.setattr(provider_script, "create_runtime_provider", lambda _cfg: inner)

    session = provider_script.bootstrap_exact_ollama_provider()

    assert calls == ["bootstrap", "resolve"]
    assert session.client._provider is inner
    assert "not-recorded" not in session.endpoint_identity


@pytest.mark.asyncio
async def test_authorship_is_exact_non_authorizing_and_restart_recoverable(
    roots: tuple[Path, Path],
) -> None:
    repo, evidence = roots
    request = _request(repo)
    provider = FakeProvider()

    first = await author_governed_patch(
        request,
        evidence_root=evidence,
        semantic_artifact_sha256=SEMANTIC_ARTIFACT_SHA,
        provider_factory=lambda: _session(provider),
    )

    assert first.authored is True
    assert first.candidate_bundle is not None
    assert provider.calls == provider.closes == 1
    assert provider.requests[0].model == authorship_module.REQUESTED_MODEL
    assert provider.requests[0].tools == []
    receipt = first.receipt.to_dict()
    assert receipt["status"] == "authored"
    assert receipt["semantic_artifact_sha256"] == SEMANTIC_ARTIFACT_SHA
    assert receipt["candidate_bundle_sha256"] == (
        first.candidate_bundle.bundle_sha256
    )
    assert receipt["repository_effect_authorized"] is False
    assert receipt["repository_effect_performed"] is False
    assert receipt["mission_control_completion_authorized"] is False
    assert (repo / SOURCE_PATH).read_text(encoding="utf-8") == SOURCE
    candidate_payload = json.loads(
        first.candidate_bundle.candidate_path.read_text(encoding="utf-8")
    )
    assert (
        candidate_payload["metadata"]["semantic_artifact_sha256"]
        == SEMANTIC_ARTIFACT_SHA
    )
    from scripts.runtime.governed_patch_responder import (
        _normalize_outcome,
        _request_checkpoint,
    )

    normalized = _normalize_outcome(
        first,
        request=request,
        call_id=first.receipt.provider_call_id,
        semantic_artifact_sha256=SEMANTIC_ARTIFACT_SHA,
        request_checkpoint=_request_checkpoint(request),
    )
    assert normalized.receipt["receipt_sha256"] == first.receipt.receipt_sha256
    assert normalized.candidate is not None
    assert normalized.candidate["authorized_source_path"] == SOURCE_PATH

    recovered = recover_provider_authorship_result(
        request,
        evidence_root=evidence,
        semantic_artifact_sha256=SEMANTIC_ARTIFACT_SHA,
    )
    replay = await author_governed_patch(
        request,
        evidence_root=evidence,
        semantic_artifact_sha256=SEMANTIC_ARTIFACT_SHA,
        provider_factory=lambda: pytest.fail("provider must not be called again"),
    )
    assert recovered == replay == first


def test_provider_call_evidence_inspector_reports_absent_read_only(
    roots: tuple[Path, Path],
) -> None:
    repo, evidence = roots
    assert _inspect(_request(repo), evidence) is ProviderCallEvidenceState.ABSENT
    assert not evidence.exists()


@pytest.mark.asyncio
async def test_provider_call_evidence_claimed_before_provider_request(
    roots: tuple[Path, Path],
) -> None:
    repo, evidence = roots
    request = _request(repo)
    entered = asyncio.Event()
    release = asyncio.Event()
    provider = FakeProvider()

    async def delayed_factory() -> ProviderSession:
        entered.set()
        await release.wait()
        return _session(provider)

    task = asyncio.create_task(
        author_governed_patch(
            request,
            evidence_root=evidence,
            semantic_artifact_sha256=SEMANTIC_ARTIFACT_SHA,
            provider_factory=delayed_factory,
        )
    )
    await entered.wait()
    try:
        assert _inspect(request, evidence) is ProviderCallEvidenceState.CLAIMED
        assert provider.calls == 0
    finally:
        release.set()
    await task
    assert provider.calls == 1


@pytest.mark.asyncio
async def test_provider_call_evidence_terminal_requires_claim_and_exact_locator(
    roots: tuple[Path, Path],
) -> None:
    repo, evidence = roots
    request = _request(repo)
    await author_governed_patch(
        request,
        evidence_root=evidence,
        semantic_artifact_sha256=SEMANTIC_ARTIFACT_SHA,
        provider_factory=lambda: _session(FakeProvider()),
    )
    assert _inspect(request, evidence) is ProviderCallEvidenceState.TERMINAL

    claim = next((evidence / "provider_authorship" / "claims").iterdir())
    claim.unlink()
    with pytest.raises(GovernedPatchEvidenceError, match="lacks durable provider claim"):
        _inspect(request, evidence)


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", ("claim", "locator"))
async def test_provider_call_evidence_tamper_fails_closed(
    roots: tuple[Path, Path],
    surface: str,
) -> None:
    repo, evidence = roots
    request = _request(repo)
    await author_governed_patch(
        request,
        evidence_root=evidence,
        semantic_artifact_sha256=SEMANTIC_ARTIFACT_SHA,
        provider_factory=lambda: _session(FakeProvider()),
    )
    branch = "claims" if surface == "claim" else "calls"
    target = next((evidence / "provider_authorship" / branch).iterdir())
    target.write_text("{}", encoding="utf-8")
    with pytest.raises(GovernedPatchEvidenceError, match=f"provider call {surface}"):
        _inspect(request, evidence)


@pytest.mark.asyncio
async def test_same_call_claim_allows_at_most_one_provider_invocation(
    roots: tuple[Path, Path],
) -> None:
    repo, evidence = roots
    request = _request(repo)
    entered = asyncio.Event()
    release = asyncio.Event()

    class BlockingProvider(FakeProvider):
        async def complete(self, llm_request: LLMRequest) -> LLMResponse:
            self.calls += 1
            self.requests.append(llm_request)
            entered.set()
            await release.wait()
            return self.response

    provider = BlockingProvider()
    first_task = asyncio.create_task(
        author_governed_patch(
            request,
            evidence_root=evidence,
            semantic_artifact_sha256=SEMANTIC_ARTIFACT_SHA,
            provider_factory=lambda: _session(provider),
        )
    )
    await entered.wait()
    with pytest.raises(ProviderCallIndeterminateError, match="redrive forbidden"):
        await author_governed_patch(
            request,
            evidence_root=evidence,
            semantic_artifact_sha256=SEMANTIC_ARTIFACT_SHA,
            provider_factory=lambda: pytest.fail("second provider dispatch"),
        )
    assert provider.calls == 1
    claim = next((evidence / "provider_authorship" / "claims").iterdir())
    assert claim.stat().st_mode & 0o777 == 0o600

    release.set()
    first = await first_task
    replay = await author_governed_patch(
        request,
        evidence_root=evidence,
        semantic_artifact_sha256=SEMANTIC_ARTIFACT_SHA,
        provider_factory=lambda: pytest.fail("terminal provider redrive"),
    )
    assert replay == first
    assert provider.calls == provider.closes == 1


@pytest.mark.asyncio
async def test_candidate_precedes_terminal_and_orphan_is_indeterminate(
    roots: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, evidence = roots
    request = _request(repo)
    provider = FakeProvider()

    def crash_before_terminal(**kwargs):
        planned = kwargs["candidate_bundle_sha256_value"]
        assert (evidence / "candidates" / "sha256" / planned / "manifest.json").is_file()
        raise RuntimeError("simulated crash before terminal receipt")

    monkeypatch.setattr(authorship_module, "_persist_receipt", crash_before_terminal)
    with pytest.raises(RuntimeError, match="simulated crash"):
        await author_governed_patch(
            request,
            evidence_root=evidence,
            semantic_artifact_sha256=SEMANTIC_ARTIFACT_SHA,
            provider_factory=lambda: _session(provider),
        )
    assert provider.calls == provider.closes == 1
    assert not (evidence / "provider_authorship" / "calls").exists()
    with pytest.raises(ProviderCallIndeterminateError, match="redrive forbidden"):
        recover_provider_authorship_result(
            request,
            evidence_root=evidence,
            semantic_artifact_sha256=SEMANTIC_ARTIFACT_SHA,
        )
    with pytest.raises(ProviderCallIndeterminateError, match="redrive forbidden"):
        await author_governed_patch(
            request,
            evidence_root=evidence,
            semantic_artifact_sha256=SEMANTIC_ARTIFACT_SHA,
            provider_factory=lambda: pytest.fail("orphan must not redrive"),
        )


@pytest.mark.asyncio
async def test_terminal_authorship_recovers_after_drift_without_applicability(
    roots: tuple[Path, Path],
) -> None:
    repo, evidence = roots
    request = _request(repo)
    first = await author_governed_patch(
        request,
        evidence_root=evidence,
        semantic_artifact_sha256=SEMANTIC_ARTIFACT_SHA,
        provider_factory=lambda: _session(FakeProvider()),
    )
    (repo / SOURCE_PATH).write_text("# drifted after authorship\n", encoding="utf-8")

    recovered = recover_provider_authorship_result(
        request,
        evidence_root=evidence,
        semantic_artifact_sha256=SEMANTIC_ARTIFACT_SHA,
    )
    assert recovered == first
    assert recovered.receipt.to_dict()["repository_effect_authorized"] is False
    assert recovered.candidate_bundle is not None
    with pytest.raises(GovernedPatchEvidenceError, match="source drifted"):
        verify_candidate_bundle(recovered.candidate_bundle)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "reason"),
    (
        (
            LLMResponse(
                content=f"prose\n{EDIT}",
                model=authorship_module.REQUESTED_WIRE_MODEL,
                provider="ollama",
                stop_reason="stop",
            ),
            "invalid_provider_edit",
        ),
        (
            LLMResponse(
                content=EDIT + EDIT,
                model=authorship_module.REQUESTED_WIRE_MODEL,
                provider="ollama",
                stop_reason="stop",
            ),
            "invalid_provider_edit",
        ),
        (
            LLMResponse(
                content=EDIT.replace(SOURCE_PATH, "pkg/other.py"),
                model=authorship_module.REQUESTED_WIRE_MODEL,
                provider="ollama",
                stop_reason="stop",
            ),
            "invalid_provider_edit",
        ),
        (
            LLMResponse(
                content=EDIT,
                model="mistral:latest",
                provider="ollama",
                stop_reason="stop",
            ),
            "served_model_mismatch",
        ),
        (
            LLMResponse(
                content=EDIT,
                model=authorship_module.REQUESTED_WIRE_MODEL,
                provider="ollama",
                stop_reason="length",
            ),
            "unacceptable_stop_reason",
        ),
        (
            LLMResponse(
                content=EDIT,
                model=authorship_module.REQUESTED_WIRE_MODEL,
                provider="ollama",
                stop_reason="stop",
                tool_calls=[{"id": "tool-1", "name": "write", "parameters": {}}],
            ),
            "provider_tools_returned",
        ),
    ),
)
async def test_invalid_provider_outputs_persist_typed_refusal(
    roots: tuple[Path, Path],
    response: LLMResponse,
    reason: str,
) -> None:
    repo, evidence = roots
    request = _request(repo)
    provider = FakeProvider(response)

    result = await author_governed_patch(
        request,
        evidence_root=evidence,
        semantic_artifact_sha256=SEMANTIC_ARTIFACT_SHA,
        provider_factory=lambda: _session(provider),
    )

    assert result.authored is False
    assert result.candidate_bundle is None
    assert result.receipt.reason_code == reason
    assert result.receipt.candidate_bundle_sha256 is None
    assert provider.calls == provider.closes == 1
    recovered = recover_provider_authorship_result(
        request,
        evidence_root=evidence,
        semantic_artifact_sha256=SEMANTIC_ARTIFACT_SHA,
    )
    assert recovered == result


@pytest.mark.asyncio
async def test_unique_nonempty_non_noop_search_is_required(
    roots: tuple[Path, Path],
) -> None:
    repo, evidence = roots
    (repo / SOURCE_PATH).write_text(
        'def value():\n    marker = "old"\n    return "old"\n',
        encoding="utf-8",
        newline="",
    )
    request = _request(repo)
    ambiguous = EDIT.replace('    return "old"', '"old"')
    provider = FakeProvider(
        LLMResponse(
            content=ambiguous,
            model=authorship_module.REQUESTED_WIRE_MODEL,
            provider="ollama",
            stop_reason="stop",
        )
    )
    result = await author_governed_patch(
        request,
        evidence_root=evidence,
        semantic_artifact_sha256=SEMANTIC_ARTIFACT_SHA,
        provider_factory=lambda: _session(provider),
    )
    assert result.receipt.reason_code == "invalid_provider_edit"

    second_evidence = evidence.parent / "second-evidence"
    noop = EDIT.replace('    return "new"', '    return "old"')
    result = await author_governed_patch(
        request,
        evidence_root=second_evidence,
        semantic_artifact_sha256=SEMANTIC_ARTIFACT_SHA,
        provider_factory=lambda: _session(
            FakeProvider(
                LLMResponse(
                    content=noop,
                    model=authorship_module.REQUESTED_WIRE_MODEL,
                    provider="ollama",
                    stop_reason="stop",
                )
            )
        ),
    )
    assert result.receipt.reason_code == "invalid_provider_edit"


@pytest.mark.asyncio
async def test_overlapping_search_occurrences_are_ambiguous(
    roots: tuple[Path, Path],
) -> None:
    repo, evidence = roots
    (repo / SOURCE_PATH).write_text("aaa\n", encoding="utf-8", newline="")
    request = _request(repo)
    overlapping = (
        f"<<<<<<< SEARCH path={SOURCE_PATH}\n"
        "aa\n"
        "=======\n"
        "b\n"
        ">>>>>>> REPLACE\n"
    )
    result = await author_governed_patch(
        request,
        evidence_root=evidence,
        semantic_artifact_sha256=SEMANTIC_ARTIFACT_SHA,
        provider_factory=lambda: _session(
            FakeProvider(
                LLMResponse(
                    content=overlapping,
                    model=authorship_module.REQUESTED_WIRE_MODEL,
                    provider="ollama",
                    stop_reason="stop",
                )
            )
        ),
    )
    assert result.receipt.reason_code == "invalid_provider_edit"


@pytest.mark.asyncio
async def test_bare_injected_client_is_never_given_canonical_identity(
    roots: tuple[Path, Path],
) -> None:
    repo, evidence = roots
    request = _request(repo)
    provider = FakeProvider()
    result = await author_governed_patch(
        request,
        evidence_root=evidence,
        semantic_artifact_sha256=SEMANTIC_ARTIFACT_SHA,
        provider_factory=lambda: provider,
    )
    assert result.receipt.reason_code == "provider_error"
    assert result.receipt.endpoint_identity != CANONICAL_ENDPOINT
    assert provider.calls == provider.closes == 0
    assert recover_provider_authorship_result(
        request,
        evidence_root=evidence,
        semantic_artifact_sha256=SEMANTIC_ARTIFACT_SHA,
    ) == result


@pytest.mark.asyncio
async def test_anthropic_provider_forgery_is_persisted_as_refusal(
    roots: tuple[Path, Path],
) -> None:
    repo, evidence = roots
    request = _request(repo)
    provider = FakeProvider(
        LLMResponse(
            content=EDIT,
            model=authorship_module.REQUESTED_WIRE_MODEL,
            provider="anthropic",
            stop_reason="stop",
        )
    )
    result = await author_governed_patch(
        request,
        evidence_root=evidence,
        semantic_artifact_sha256=SEMANTIC_ARTIFACT_SHA,
        provider_factory=lambda: _session(provider),
    )
    assert result.authored is False
    assert result.receipt.reason_code == "served_provider_mismatch"
    response_path = (
        evidence
        / "provider_authorship"
        / "blobs"
        / "sha256"
        / str(result.receipt.response_sha256)
    )
    assert json.loads(response_path.read_text(encoding="utf-8"))["provider"] == (
        "anthropic"
    )
    assert recover_provider_authorship_result(
        request,
        evidence_root=evidence,
        semantic_artifact_sha256=SEMANTIC_ARTIFACT_SHA,
    ) == result

@pytest.mark.asyncio
async def test_provider_timeout_and_error_always_close_and_refuse(
    roots: tuple[Path, Path],
) -> None:
    repo, evidence = roots
    request = _request(repo)
    slow = FakeProvider(delay=0.1)
    timeout = await author_governed_patch(
        request,
        evidence_root=evidence,
        semantic_artifact_sha256=SEMANTIC_ARTIFACT_SHA,
        provider_factory=lambda: _session(slow),
        timeout_seconds=0.01,
    )
    assert timeout.receipt.reason_code == "provider_timeout"
    assert slow.calls == slow.closes == 1

    errored = FakeProvider(error=RuntimeError("unavailable"))
    result = await author_governed_patch(
        request,
        evidence_root=evidence.parent / "error-evidence",
        semantic_artifact_sha256=SEMANTIC_ARTIFACT_SHA,
        provider_factory=lambda: _session(errored),
    )
    assert result.receipt.reason_code == "provider_error"
    assert errored.calls == errored.closes == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("timeout", (0.0, -1.0, float("nan"), float("inf")))
async def test_nonfinite_or_nonpositive_timeout_refuses_before_claim(
    roots: tuple[Path, Path], timeout: float
) -> None:
    repo, evidence = roots
    provider = FakeProvider()
    with pytest.raises(GovernedPatchEvidenceError, match="positive and finite"):
        await author_governed_patch(
            _request(repo),
            evidence_root=evidence,
            semantic_artifact_sha256=SEMANTIC_ARTIFACT_SHA,
            provider_factory=lambda: _session(provider),
            timeout_seconds=timeout,
        )
    assert provider.calls == provider.closes == 0
    assert not evidence.exists()


@pytest.mark.asyncio
async def test_rejects_non_cloud_transport_without_provider_fallback(
    roots: tuple[Path, Path],
) -> None:
    repo, evidence = roots
    request = _request(repo)
    provider = FakeProvider()

    result = await author_governed_patch(
        request,
        evidence_root=evidence,
        semantic_artifact_sha256=SEMANTIC_ARTIFACT_SHA,
        provider_factory=lambda: ProviderSession(
            provider,
            "provider:http://localhost:11434",
        ),
    )

    assert result.authored is False
    assert result.receipt.reason_code == "provider_route_mismatch"
    assert provider.calls == 0
    assert provider.closes == 1
    recovered = recover_provider_authorship_result(
        request,
        evidence_root=evidence,
        semantic_artifact_sha256=SEMANTIC_ARTIFACT_SHA,
    )
    assert recovered == result
    assert recovered.receipt.to_dict()["repository_effect_authorized"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("root_kind", ("equal", "descendant", "ancestor", "root"))
async def test_provider_evidence_root_must_be_disjoint(
    roots: tuple[Path, Path],
    root_kind: str,
) -> None:
    repo, _ = roots
    request = _request(repo)
    unsafe = {
        "equal": repo,
        "descendant": repo / ".provider-evidence",
        "ancestor": repo.parent,
        "root": Path("/"),
    }[root_kind]
    with pytest.raises(GovernedPatchEvidenceError, match="disjoint"):
        await author_governed_patch(
            request,
            evidence_root=unsafe,
            semantic_artifact_sha256=SEMANTIC_ARTIFACT_SHA,
            provider_factory=lambda: pytest.fail("unsafe root reached provider"),
        )


@pytest.mark.asyncio
async def test_receipt_and_semantic_artifact_tamper_fail_closed(
    roots: tuple[Path, Path],
) -> None:
    repo, evidence = roots
    request = _request(repo)
    result = await author_governed_patch(
        request,
        evidence_root=evidence,
        semantic_artifact_sha256=SEMANTIC_ARTIFACT_SHA,
        provider_factory=lambda: _session(FakeProvider()),
    )
    with pytest.raises(GovernedPatchEvidenceError, match="artifact"):
        verify_provider_authorship_receipt(
            result.receipt,
            request=request,
            semantic_artifact_sha256="0" * 64,
        )

    payload = json.loads(result.receipt.receipt_path.read_text(encoding="utf-8"))
    payload["semantic_artifact_sha256"] = "0" * 64
    result.receipt.receipt_path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    with pytest.raises(GovernedPatchEvidenceError, match="tampered"):
        verify_provider_authorship_receipt(
            result.receipt,
            request=request,
            semantic_artifact_sha256=SEMANTIC_ARTIFACT_SHA,
        )
