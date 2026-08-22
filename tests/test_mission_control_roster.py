"""Fail-closed tests for the SADHANA campaign model roster."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pytest

from dharma_swarm.mission_control_roster import (
    CampaignRosterError,
    ensure_campaign_agent_roster,
    load_campaign_agent_roster,
)
from dharma_swarm.models import AgentRole, AgentState, AgentStatus, ProviderType
from scripts.runtime import mission_control_campaign as campaign_cli


CAMPAIGN_ID = "sadhana-10-20260823"
OBJECTIVE_SHA = "1d4d2ad5f8a744212cb65ba46bdb4993eafc152c6837e3cf73cb7d080c370f2b"
NOW = datetime(2026, 8, 23, 0, 0, tzinfo=timezone.utc)
CATALOG = [
    "deepseek-v4-pro:0813",
    "glm-5.2",
    "kimi-k3",
    "minimax-m3",
    "mistral-large-3:675b",
    "nemotron-3-ultra",
    "qwen3.5:397b",
]
SEAT_ROWS = [
    ("sadhana-glm", "researcher", "glm-5.2:cloud", "glm"),
    ("sadhana-kimi", "cartographer", "kimi-k3:cloud", "kimi"),
    (
        "sadhana-deepseek",
        "surgeon",
        "deepseek-v4-pro:0813:cloud",
        "deepseek",
    ),
    ("sadhana-minimax", "architect", "minimax-m3:cloud", "minimax"),
    (
        "sadhana-nemotron",
        "validator",
        "nemotron-3-ultra:cloud",
        "nemotron",
    ),
    ("sadhana-qwen", "coder", "qwen3.5:397b:cloud", "qwen"),
    (
        "sadhana-mistral",
        "reviewer",
        "mistral-large-3:675b:cloud",
        "mistral",
    ),
]


def _payload() -> dict[str, object]:
    agents = []
    for name, role, model, family in SEAT_ROWS:
        agents.append(
            {
                "name": name,
                "role": role,
                "provider": "ollama",
                "model": model,
                "family": family,
                "thread": f"{family}-thread",
                "system_prompt": f"Perform bounded {family} work and preserve evidence.",
            }
        )
    return {
        "schema": "dharma.sadhana.agent_roster.v1",
        "campaign_id": CAMPAIGN_ID,
        "objective_sha256": OBJECTIVE_SHA,
        "activation_at": "2026-08-22T17:15:12Z",
        "expires_at": "2026-09-01T17:15:12Z",
        "cash_ceiling_usd": 0,
        "concurrency_ceiling": 7,
        "provider_catalog": {
            "provider": "ollama",
            "endpoint": "https://ollama.com/v1/models",
            "authentication": "account_authenticated",
            "observed_at": "2026-08-22T21:02:06Z",
            "models": list(CATALOG),
        },
        "agents": agents,
        "claims": {
            "proves": ["Seven catalog-backed requested seats."],
            "does_not_prove": ["No work, liveness, authority, or acceptance."],
        },
    }


def _write_manifest(tmp_path: Path, payload: dict[str, object]) -> tuple[Path, str]:
    path = tmp_path / "agent-roster.v1.json"
    content = json.dumps(payload, indent=2, sort_keys=True).encode() + b"\n"
    path.write_bytes(content)
    path.chmod(0o600)
    return path, hashlib.sha256(content).hexdigest()


def _load(path: Path, digest: str, *, now: datetime = NOW):
    return load_campaign_agent_roster(
        path,
        expected_sha256=digest,
        campaign_id=CAMPAIGN_ID,
        objective_sha256=OBJECTIVE_SHA,
        now=now,
    )


def _state(
    row: tuple[str, str, str, str],
    *,
    suffix: str = "existing",
    status: AgentStatus = AgentStatus.IDLE,
) -> AgentState:
    name, role, model, _family = row
    return AgentState(
        id=f"{suffix}-{name}",
        name=name,
        role=AgentRole(role),
        status=status,
        provider=ProviderType.OLLAMA.value,
        model=model,
    )


class FakeSwarm:
    def __init__(self, states: list[AgentState] | None = None) -> None:
        self.states = list(states or [])
        self.spawn_calls: list[dict[str, object]] = []

    async def list_agents(self) -> list[AgentState]:
        return list(self.states)

    async def spawn_agent(
        self,
        name: str,
        role: AgentRole = AgentRole.GENERAL,
        model: str = "claude-code",
        provider_type: ProviderType = ProviderType.CLAUDE_CODE,
        system_prompt: str = "",
        thread: str | None = None,
    ) -> AgentState:
        self.spawn_calls.append(
            {
                "name": name,
                "role": role,
                "model": model,
                "provider_type": provider_type,
                "system_prompt": system_prompt,
                "thread": thread,
            }
        )
        state = AgentState(
            id=f"spawned-{name}",
            name=name,
            role=role,
            status=AgentStatus.IDLE,
            provider=provider_type.value,
            model=model,
        )
        self.states.append(state)
        return state


def test_exact_manifest_loads_seven_distinct_catalog_backed_families(
    tmp_path: Path,
) -> None:
    path, digest = _write_manifest(tmp_path, _payload())

    roster = _load(path, digest)

    assert roster.manifest_sha256 == digest
    assert len(roster.seats) == 7
    assert len({seat.family for seat in roster.seats}) == 7
    assert all(seat.model[:-6] in roster.catalog_models for seat in roster.seats)


def test_wrong_digest_fails_before_parse(tmp_path: Path) -> None:
    path, _digest = _write_manifest(tmp_path, _payload())

    with pytest.raises(CampaignRosterError, match="SHA-256 does not match"):
        _load(path, "0" * 64)


def test_mode_and_symlink_custody_fail_closed(tmp_path: Path) -> None:
    path, digest = _write_manifest(tmp_path, _payload())
    path.chmod(0o644)
    with pytest.raises(CampaignRosterError, match="mode-0600"):
        _load(path, digest)
    path.chmod(0o600)
    link = tmp_path / "linked-roster.json"
    link.symlink_to(path)
    with pytest.raises(CampaignRosterError, match="mode-0600"):
        _load(link, digest)


def test_model_absent_from_catalog_fails_closed(tmp_path: Path) -> None:
    payload = _payload()
    payload["provider_catalog"]["models"].remove("kimi-k3")  # type: ignore[index,union-attr]
    path, digest = _write_manifest(tmp_path, payload)

    with pytest.raises(CampaignRosterError, match="absent from the observed catalog"):
        _load(path, digest)


def test_expired_manifest_fails_closed(tmp_path: Path) -> None:
    path, digest = _write_manifest(tmp_path, _payload())

    with pytest.raises(CampaignRosterError, match="exact campaign timebox"):
        _load(path, digest, now=datetime(2026, 9, 1, 17, 15, 12, tzinfo=timezone.utc))


def test_unknown_fields_and_duplicate_json_keys_fail_closed(tmp_path: Path) -> None:
    payload = _payload()
    payload["unexpected"] = True
    path, digest = _write_manifest(tmp_path, payload)
    with pytest.raises(CampaignRosterError, match="keys are not exact"):
        _load(path, digest)

    raw = b'{"schema":"one","schema":"two"}\n'
    path.write_bytes(raw)
    path.chmod(0o600)
    with pytest.raises(CampaignRosterError, match="duplicate key"):
        _load(path, hashlib.sha256(raw).hexdigest())


@pytest.mark.asyncio
async def test_duplicate_live_name_fails_before_any_spawn(tmp_path: Path) -> None:
    path, digest = _write_manifest(tmp_path, _payload())
    roster = _load(path, digest)
    duplicate = _state(SEAT_ROWS[0])
    swarm = FakeSwarm([duplicate, duplicate.model_copy(update={"id": "duplicate"})])

    with pytest.raises(CampaignRosterError, match="multiple live states"):
        await ensure_campaign_agent_roster(swarm, roster)

    assert swarm.spawn_calls == []


@pytest.mark.asyncio
async def test_mismatched_live_identity_fails_before_any_spawn(tmp_path: Path) -> None:
    path, digest = _write_manifest(tmp_path, _payload())
    roster = _load(path, digest)
    mismatch = _state(SEAT_ROWS[0]).model_copy(update={"model": "glm-5.1:cloud"})
    swarm = FakeSwarm([mismatch])

    with pytest.raises(CampaignRosterError, match="mismatched state"):
        await ensure_campaign_agent_roster(swarm, roster)

    assert swarm.spawn_calls == []


@pytest.mark.asyncio
async def test_partial_spawn_recovery_is_idempotent_and_returns_actual_ids(
    tmp_path: Path,
) -> None:
    path, digest = _write_manifest(tmp_path, deepcopy(_payload()))
    roster = _load(path, digest)
    swarm = FakeSwarm([_state(row) for row in SEAT_ROWS[:3]])

    first = await ensure_campaign_agent_roster(swarm, roster)
    second = await ensure_campaign_agent_roster(swarm, roster)

    assert len(swarm.spawn_calls) == 4
    assert [binding.name for binding in first.bindings] == [row[0] for row in SEAT_ROWS]
    assert [binding.agent_id for binding in first.bindings[:3]] == [
        f"existing-{row[0]}" for row in SEAT_ROWS[:3]
    ]
    assert {binding.disposition for binding in first.bindings[:3]} == {"existing"}
    assert {binding.disposition for binding in first.bindings[3:]} == {"spawned"}
    assert {binding.disposition for binding in second.bindings} == {"existing"}
    assert first.to_dict()["dispatch_ready"] is False
    assert first.to_dict()["authority_state"] == "unbound"


@pytest.mark.asyncio
async def test_dead_exact_name_is_a_conflict_not_a_spawn_hint(tmp_path: Path) -> None:
    path, digest = _write_manifest(tmp_path, _payload())
    roster = _load(path, digest)
    swarm = FakeSwarm([_state(SEAT_ROWS[0], status=AgentStatus.DEAD)])

    with pytest.raises(CampaignRosterError, match="mismatched state"):
        await ensure_campaign_agent_roster(swarm, roster)

    assert swarm.spawn_calls == []


def test_campaign_child_command_forwards_exact_roster_triplet(tmp_path: Path) -> None:
    path, digest = _write_manifest(tmp_path, _payload())
    args = campaign_cli.build_parser().parse_args(
        [
            "start",
            "--state-dir",
            str(tmp_path / "state"),
            "--mission-id",
            CAMPAIGN_ID,
            "--agent-roster",
            str(path),
            "--agent-roster-sha256",
            digest,
            "--objective-sha256",
            OBJECTIVE_SHA,
        ]
    )

    command = campaign_cli._run_child_command(  # noqa: SLF001 - CLI contract test
        args,
        campaign_cli._paths(args),  # noqa: SLF001 - CLI contract test
    )

    assert command[2] == "run"
    assert command[command.index("--agent-roster") + 1] == str(path.resolve())
    assert command[command.index("--agent-roster-sha256") + 1] == digest
    assert command[command.index("--objective-sha256") + 1] == OBJECTIVE_SHA


def test_campaign_child_command_rejects_partial_roster_configuration(
    tmp_path: Path,
) -> None:
    args = campaign_cli.build_parser().parse_args(
        [
            "start",
            "--state-dir",
            str(tmp_path / "state"),
            "--mission-id",
            CAMPAIGN_ID,
            "--agent-roster",
            str(tmp_path / "missing.json"),
        ]
    )

    with pytest.raises(CampaignRosterError, match="configuration is partial"):
        campaign_cli._run_child_command(  # noqa: SLF001 - CLI contract test
            args,
            campaign_cli._paths(args),  # noqa: SLF001 - CLI contract test
        )
