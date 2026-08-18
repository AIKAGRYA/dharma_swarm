"""Public-boundary proofs for the repo-owned Sarathi composition root."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]

EXPECTED_PUBLIC_API = {
    "CognitionPort",
    "CognitionRequest",
    "CognitionResult",
    "DEFAULT_SARATHI_IDENTITY",
    "EffectIntent",
    "EffectReport",
    "EffectStatus",
    "SarathiIdentity",
    "SarathiShell",
    "SarathiTurnRequest",
    "SarathiTurnResult",
    "TurnStatus",
    "TurnStorePort",
    "build_sarathi_shell",
    "handle_turn",
}


def test_public_api_is_exact() -> None:
    import dharma_swarm.sarathi as sarathi

    assert len(sarathi.__all__) == len(EXPECTED_PUBLIC_API)
    assert set(sarathi.__all__) == EXPECTED_PUBLIC_API
    for name in EXPECTED_PUBLIC_API:
        assert getattr(sarathi, name) is not None


def test_public_import_is_lazy_and_does_not_touch_home(tmp_path: Path) -> None:
    """Even resolving every public symbol must not boot providers or state."""

    home = tmp_path / "empty-home"
    home.mkdir()
    probe = r"""
import json
from pathlib import Path
import sys

import dharma_swarm.sarathi as sarathi

for export in sarathi.__all__:
    getattr(sarathi, export)

heavy = {
    "anthropic",
    "openai",
    "dharma_swarm.agent_runner",
    "dharma_swarm.autonomous_agent",
    "dharma_swarm.persistent_agent",
    "dharma_swarm.runtime_provider",
    "dharma_swarm.runtime_state",
    "dharma_swarm.swarm",
}
loaded = sorted(heavy.intersection(sys.modules))
home = Path.home()
created = sorted(str(path.relative_to(home)) for path in home.rglob("*"))
print(json.dumps({"created": created, "loaded": loaded}, sort_keys=True))
raise SystemExit(1 if created or loaded else 0)
"""
    env = {
        **os.environ,
        "DHARMA_HOME": str(home),
        "DHARMA_STATE_DIR": str(home / "state"),
        "HOME": str(home),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    completed = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    payload = json.loads(completed.stdout.strip())
    assert payload == {"created": [], "loaded": []}


def test_default_identity_is_version_controlled_source_data() -> None:
    from dharma_swarm.sarathi import DEFAULT_SARATHI_IDENTITY, SarathiIdentity

    assert isinstance(DEFAULT_SARATHI_IDENTITY, SarathiIdentity)
    assert DEFAULT_SARATHI_IDENTITY.display_name == "Sarathi"
    assert DEFAULT_SARATHI_IDENTITY.version.strip()
    assert DEFAULT_SARATHI_IDENTITY.system_prompt.strip()


def test_persona_revision_cannot_silently_widen_identity_authority() -> None:
    from dharma_swarm.sarathi import DEFAULT_SARATHI_IDENTITY

    revised = DEFAULT_SARATHI_IDENTITY.with_persona_revision(
        version="dharma.sarathi.identity.test-revision",
        system_prompt="A revised, source-reviewable persona.",
    )

    assert revised.version != DEFAULT_SARATHI_IDENTITY.version
    assert revised.system_prompt != DEFAULT_SARATHI_IDENTITY.system_prompt
    assert revised.uid == DEFAULT_SARATHI_IDENTITY.uid
    assert revised.display_name == DEFAULT_SARATHI_IDENTITY.display_name
    assert revised.authority_ceiling == DEFAULT_SARATHI_IDENTITY.authority_ceiling
