"""Tests for Phase 2 agent backends and role wrappers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.governance.loop.agent_backend import (
    ApiBackend,
    BackendInvocationError,
    BackendUnavailableError,
    DroidBackend,
    StubBackend,
    get_backend,
)
from scripts.governance.loop.prompt_audit_reaudit import DroidVerifier, build_falsification_prompt
from scripts.governance.loop.prompt_audit_remediate import DroidImplementer
from scripts.governance.loop.validate_audit import validate_audit_doc

REPO_ROOT = Path(__file__).resolve().parents[3]


def _write_fake_droid(tmp_path: Path, stdout_text: str = "fake droid ok\n") -> Path:
    fake = tmp_path / "droid"
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "import json\n"
        "import os\n"
        "import sys\n"
        "from pathlib import Path\n"
        "log_path = os.environ.get('DROID_FAKE_LOG')\n"
        "prompt_text = ''\n"
        "if '-f' in sys.argv:\n"
        "    prompt_text = Path(sys.argv[sys.argv.index('-f') + 1]).read_text()\n"
        "if log_path:\n"
        "    with open(log_path, 'a') as fh:\n"
        "        fh.write(json.dumps({'argv': sys.argv[1:], 'prompt': prompt_text}) + '\\n')\n"
        "sys.stdout.write(os.environ.get('DROID_FAKE_STDOUT', " + repr(stdout_text) + "))\n"
        "sys.exit(int(os.environ.get('DROID_FAKE_EXIT', '0')))\n"
    )
    fake.chmod(0o755)
    return fake


def test_stub_backend_produces_schema_valid_audit():
    audit = StubBackend().audit("TV-01", "testing_verification", "", {"run_id": "r1"})

    result = validate_audit_doc(audit, repo_root=REPO_ROOT)

    assert result.valid, result.errors
    assert audit["operator"] == "stub"


def test_droid_backend_invokes_droid_cli(tmp_path, monkeypatch):
    log = tmp_path / "droid.log"
    fake = _write_fake_droid(tmp_path)
    monkeypatch.setenv("DROID_FAKE_LOG", str(log))

    result = DroidBackend(droid_path=fake, cwd=REPO_ROOT).invoke(
        "implementer",
        "make a plan",
        {"finding_id": "F-1", "severity": "medium"},
    )

    assert result.return_code == 0
    assert result.role == "implementer"
    assert result.model == "glm-5.2"
    entry = json.loads(log.read_text().splitlines()[0])
    assert entry["argv"][:2] == ["exec", "--cwd"]
    assert "--model" in entry["argv"]
    assert "make a plan" in entry["prompt"]


def test_droid_backend_audit_parses_schema_json(tmp_path, monkeypatch):
    stub_doc = StubBackend().audit(
        "TV-01",
        "testing_verification",
        "",
        {"run_id": "r1", "repo_path": str(REPO_ROOT)},
    )
    fake = _write_fake_droid(tmp_path)
    monkeypatch.setenv("DROID_FAKE_STDOUT", json.dumps(stub_doc))

    audit = DroidBackend(droid_path=fake, cwd=REPO_ROOT).audit(
        "TV-01",
        "testing_verification",
        "",
        {"run_id": "r1", "repo_path": str(REPO_ROOT)},
    )

    assert audit["prompt_id"] == "TV-01"
    assert validate_audit_doc(audit, repo_root=REPO_ROOT).valid


def test_droid_backend_missing_cli_fails_clear_no_stub(tmp_path):
    backend = DroidBackend(droid_path=tmp_path / "missing-droid")

    with pytest.raises(BackendUnavailableError, match="no silent fallback to stub"):
        backend.invoke("auditor", "prompt", {})


def test_droid_backend_non_executable_file_fails_unavailable(tmp_path):
    fake = tmp_path / "droid"
    fake.write_text("#!/bin/sh\necho no\n")
    fake.chmod(0o644)
    backend = DroidBackend(droid_path=fake)

    with pytest.raises(BackendUnavailableError, match="executable"):
        backend.invoke("auditor", "prompt", {})


def test_droid_backend_oserror_wrapped(monkeypatch, tmp_path):
    fake = _write_fake_droid(tmp_path)
    backend = DroidBackend(droid_path=fake, cwd=REPO_ROOT)

    def boom(*args, **kwargs):
        raise PermissionError("cannot execute")

    monkeypatch.setattr("subprocess.run", boom)
    with pytest.raises(BackendInvocationError, match="could not launch"):
        backend.invoke("auditor", "prompt", {})


def test_backend_selection_env(monkeypatch):
    monkeypatch.setenv("LOOP_AGENT_BACKEND", "api")
    assert isinstance(get_backend(), ApiBackend)

    monkeypatch.setenv("LOOP_AGENT_BACKEND", "stub")
    assert isinstance(get_backend(), StubBackend)


def test_api_backend_keyless_degrades_without_crashing(monkeypatch):
    for name in ("OPENAI_API_KEY", "OPENROUTER_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(name, raising=False)

    result = ApiBackend(cwd=REPO_ROOT).invoke("auditor", "prompt", {"run_id": "r1"})
    audit = ApiBackend(cwd=REPO_ROOT).audit("TV-01", "testing_verification", "", {"run_id": "r1"})

    assert result.return_code == 0
    assert result.degraded is True
    assert audit["operator"] == "api-keyless-fallback"
    assert audit["model"] == "api-keyless"


def test_high_critical_verifier_uses_different_family_when_configured(tmp_path):
    fake = _write_fake_droid(tmp_path)
    backend = DroidBackend(
        droid_path=fake,
        cwd=REPO_ROOT,
        primary_model="glm-5.2",
        verifier_model="gpt-5.2",
    )

    result = backend.invoke("verifier", "verify", {"severity": "critical"})

    assert result.model == "gpt-5.2"
    assert result.model_independence == "proven"


def test_role_invocations_are_distinct_sessions(tmp_path):
    fake = _write_fake_droid(tmp_path)
    backend = DroidBackend(droid_path=fake, cwd=REPO_ROOT)

    auditor = backend.invoke("auditor", "audit", {})
    verifier = backend.invoke("verifier", "verify", {"severity": "medium"})

    assert auditor.invocation_id != verifier.invocation_id
    assert auditor.role == "auditor"
    assert verifier.role == "verifier"


def test_stage_wrappers_record_agent_invocation_receipts(tmp_path):
    fake = _write_fake_droid(tmp_path)
    implementer = DroidImplementer(droid_path=fake, cwd=REPO_ROOT)
    verifier = DroidVerifier(droid_path=fake, cwd=REPO_ROOT)

    plan = implementer.plan({"finding_id": "F-1", "severity": "medium"}, ["scripts/**"])
    verdict = verifier.verify(
        {"finding_id": "F-1", "severity": "critical"},
        {
            "finding_id": "F-1",
            "claim": {"finding_id": "F-1", "severity": "critical"},
            "evidence": {
                "red_before": {"exit_code": 1},
                "green_after": {"exit_code": 0},
                "proof_mode": "synthetic",
            },
        },
        build_falsification_prompt(),
    )

    impl_receipt = implementer.invocation_receipt()
    verifier_receipt = verifier.invocation_receipt()
    assert plan.proof_mode == "synthetic"
    assert impl_receipt and impl_receipt["role"] == "implementer"
    assert verdict.verifier_model
    assert verifier_receipt and verifier_receipt["role"] == "verifier"


def test_droid_verifier_parses_structured_output(tmp_path, monkeypatch):
    fake_output = json.dumps({
        "verdict": "refuted",
        "falsification_attempts": [
            {"attempt": "replay failing gate", "result": "fail", "evidence": "exit=1"}
        ],
        "verifier_model": "custom-verifier",
        "model_metadata": {"provider": "fake"},
    })
    fake = _write_fake_droid(tmp_path, stdout_text=fake_output)
    verifier = DroidVerifier(droid_path=fake, cwd=REPO_ROOT)

    result = verifier.verify(
        {"finding_id": "F-STRUCT", "severity": "critical"},
        {
            "finding_id": "F-STRUCT",
            "claim": {"finding_id": "F-STRUCT", "severity": "critical"},
            "evidence": {
                "red_before": {"exit_code": 1},
                "green_after": {"exit_code": 0},
                "proof_mode": "synthetic",
            },
        },
        build_falsification_prompt(),
    )

    assert result.verdict == "refuted"
    assert result.falsification_attempts[0]["attempt"] == "replay failing gate"
    assert result.verifier_model == "gpt-5.2"
    assert verifier.invocation_receipt()["stdout_excerpt"].startswith("{")
