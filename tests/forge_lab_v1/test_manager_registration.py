from __future__ import annotations

import json
import re
from pathlib import Path

from dharma_swarm.a2a.agent_card import AGENT_UID_ALIASES
from dharma_swarm.a2a.agent_presence import REGISTERED_AGENT_UIDS


REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / "examples/agents/codex_rsi_lab_manager.registration.json"
SCRIPT_PATH = REPO_ROOT / "scripts/agents/register_codex_rsi_lab_manager.sh"

CANONICAL_PATHS = {
    "repo": "/root/rsi-lab/current/repo",
    "state": "/root/rsi-lab/current/state",
    "venv": "/root/rsi-lab/current/.venv",
    "pydeps": "/root/rsi-lab/current/pydeps",
}


def _manifest() -> dict[str, object]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _shell_assignment(source: str, name: str) -> str:
    match = re.search(rf'^{re.escape(name)}="([^"]+)"$', source, re.MULTILINE)
    assert match is not None, f"missing shell assignment for {name}"
    return match.group(1)


def test_manager_manifest_and_wrapper_use_canonical_lab_paths() -> None:
    manifest = _manifest()
    metadata = manifest["metadata"]
    workspace = manifest["workspace_policy"]
    assert isinstance(metadata, dict)
    assert isinstance(workspace, dict)

    assert manifest["endpoint"] == "ssh://meghadharma/root/rsi-lab/current/repo"
    assert workspace["sandbox_root"] == "/root/rsi-lab/current"
    assert workspace["isolated_dharma_home"] == "/root/rsi-lab/current/state/.dharma"
    assert metadata["lab_base"] == "/root/rsi-lab/current"
    assert metadata["primary_repo"] == CANONICAL_PATHS["repo"]
    assert metadata["isolated_state"] == "/root/rsi-lab/current/state/.dharma"

    script = SCRIPT_PATH.read_text(encoding="utf-8")
    assert _shell_assignment(script, "LAB_BASE") == "${RSI_LAB_BASE:-/root/rsi-lab/current}"
    assert _shell_assignment(script, "REPO_ROOT") == "${RSI_LAB_REPO:-${LAB_BASE}/repo}"
    assert _shell_assignment(script, "STATE_ROOT") == "${RSI_LAB_STATE:-${LAB_BASE}/state}"
    assert _shell_assignment(script, "VENV_ROOT") == "${RSI_LAB_VENV:-${LAB_BASE}/.venv}"
    assert _shell_assignment(script, "PYDEPS_ROOT") == "${RSI_LAB_PYDEPS:-${LAB_BASE}/pydeps}"
    assert _shell_assignment(script, "PYTHON_BIN") == "${RSI_LAB_PYTHON:-${VENV_ROOT}/bin/python}"
    assert 'export DHARMA_HOME="${DHARMA_HOME_RESOLVED}"' in script
    assert '--endpoint "ssh://meghadharma/root/rsi-lab/current/repo"' in script
    assert "/root/rsi-lab/current-main" not in script


def test_manager_uid_aliases_roster_and_git_seat_agree() -> None:
    manifest = _manifest()
    metadata = manifest["metadata"]
    assert isinstance(metadata, dict)

    uid = manifest["agent_uid"]
    callsign = manifest["callsign"]
    assert uid == "codex_rsi_lab_manager"
    assert callsign == "codex-rsi-lab-manager"
    assert uid in REGISTERED_AGENT_UIDS

    aliases = {callsign}
    aliases.update(alias.removeprefix("@") for alias in metadata["summon_aliases"])
    assert aliases
    assert all(AGENT_UID_ALIASES.get(alias) == uid for alias in aliases)

    seat = Path(metadata["git_seat"])
    assert seat == Path("inter_agent") / uid
    assert (REPO_ROOT / seat / "inbound" / "README.md").is_file()

    script = SCRIPT_PATH.read_text(encoding="utf-8")
    assert _shell_assignment(script, "AGENT_UID") == uid
    assert _shell_assignment(script, "CALLSIGN") == callsign


def test_manager_authority_remains_evidence_only() -> None:
    manifest = _manifest()
    policy = manifest["autonomy_policy"]
    assert isinstance(policy, dict)

    assert manifest["authority"] == "external_worker_evidence_only"
    assert policy["explicit_task_assignment_required"] is True
    assert policy["can_start_persistent_daemons"] is False
    assert policy["can_touch_global_daemon_state"] is False
    assert policy["can_claim_capability_lift"] is False
