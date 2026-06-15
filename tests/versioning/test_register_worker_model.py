import importlib.util
import json
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "register_worker_model",
    Path(__file__).resolve().parents[2] / "scripts" / "governance" / "register_worker_model.py",
)
rwm = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(rwm)


def test_register_writes_valid_registration(tmp_path):
    path = rwm.register("qwen3-coder-480b", "ollama_cloud", "0.1.0+abc", root=tmp_path)
    payload = json.loads(Path(path).read_text())
    assert payload["agent_uid"] == "worker-qwen3-coder-480b"
    assert payload["role"] == "evolution_worker"
    assert payload["free_tier"] is True
    assert payload["daemon_version"] == "0.1.0+abc"
    assert payload["authority"] == "external_worker_evidence_only"
    assert payload["autonomy_policy"]["can_write_source"] is False


def test_slug_sanitizes_model_names():
    assert rwm._slug("GLM-5.1") == "glm-5.1"
    assert rwm._slug("nvidia/nim") == "nvidia-nim"


def test_register_all_seven_free_workers(tmp_path):
    written = [rwm.register(m, p, "0.1.0+x", root=tmp_path) for m, p in rwm.FREE_WORKERS]
    assert len(written) == 7
    for path in written:
        assert Path(path).exists()
