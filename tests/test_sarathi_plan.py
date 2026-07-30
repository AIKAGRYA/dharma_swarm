"""Sarathi planning organ (PR-S1): deterministic, injected, fail-closed."""

from __future__ import annotations

from dharma_swarm.holon_system.sarathi.plan import (
    BootPack,
    PlannedDelegation,
    build_plan,
    plan_dedup_key,
)

ROSTER = ("hermes-m5", "codex_composer")


def _pack(**overrides):
    base = dict(roster=ROSTER, open_items=(), ready_keys=frozenset())
    base.update(overrides)
    return BootPack(**base)


def test_empty_pack_plans_nothing() -> None:
    assert build_plan(_pack()) == []
    assert build_plan(BootPack(roster=())) == []


def test_valid_item_maps_to_mailbox_delegation() -> None:
    plan = build_plan(
        _pack(
            open_items=(
                {"kind": "experiment", "summary": "run chamber battery A"},
            )
        )
    )
    assert len(plan) == 1
    d = plan[0]
    assert isinstance(d, PlannedDelegation)
    assert d.action == "experiment: run chamber battery A"
    assert d.channel == "mailbox"
    assert d.recipient == "hermes-m5"  # roster default
    assert d.metadata["sarathi_kind"] == "experiment"


def test_invalid_items_are_skipped_never_repaired() -> None:
    plan = build_plan(
        _pack(
            open_items=(
                {"kind": "conquest", "summary": "not a valid kind"},
                {"kind": "build", "summary": ""},
                "not-a-mapping",
                {"kind": "build", "summary": "real work"},
            )
        )
    )
    assert [d.summary for d in plan] == ["real work"]


def test_mailbox_ready_set_is_the_dedup_surface() -> None:
    plan = build_plan(
        _pack(
            open_items=(
                {"kind": "review", "summary": "already queued"},
                {"kind": "review", "summary": "new work"},
            ),
            # No explicit body -> the planned body defaults to the summary, so
            # the dedup key is the fingerprint of (summary, summary).
            ready_keys=frozenset({plan_dedup_key("already queued", "already queued")}),
        )
    )
    assert [d.summary for d in plan] == ["new work"]


def test_revised_body_replans_despite_same_summary() -> None:
    """Greptile P1 line 209: a reopened backlog item with the SAME summary but
    CHANGED body must re-plan (its content fingerprint differs), while an
    unchanged item stays suppressed. Deduping on summary alone dropped the
    revision silently."""
    # The historical task recorded the ORIGINAL body.
    original_key = plan_dedup_key("audit the arena", "look at scoreboard v1")
    plan = build_plan(
        _pack(
            open_items=(
                # Same summary, unchanged body -> suppressed.
                {"kind": "review", "summary": "audit the arena",
                 "body": "look at scoreboard v1"},
                # Same summary, REVISED body -> re-planned.
                {"kind": "review", "summary": "audit the arena",
                 "body": "look at scoreboard v2 with the new metric"},
            ),
            ready_keys=frozenset({original_key}),
        )
    )
    assert len(plan) == 1
    assert plan[0].body == "look at scoreboard v2 with the new metric"


def test_merge_kind_becomes_label_intent_for_mikes_lane() -> None:
    plan = build_plan(
        _pack(open_items=({"kind": "merge", "summary": "land PR", "pr": 42},))
    )
    d = plan[0]
    assert d.channel == "merge_intent"
    assert d.recipient == "merge_master_mike"
    # The action string is the exact gate input: it must describe what
    # Sarathi actually does (queue a label request), not a merge verb.
    assert d.action == "queue unattended-lane label request for pull request #42"
    assert "merge" not in d.action


def test_explicit_recipient_outside_roster_is_kept_but_flagged() -> None:
    plan = build_plan(
        _pack(
            open_items=(
                {
                    "kind": "publication",
                    "summary": "draft darshan essay",
                    "recipient": "perplexity-computer",
                },
            )
        )
    )
    d = plan[0]
    assert d.recipient == "perplexity-computer"
    assert d.metadata["recipient_outside_roster"] is True


def test_plan_is_deterministic() -> None:
    pack = _pack(
        open_items=(
            {"kind": "build", "summary": "one"},
            {"kind": "review", "summary": "two", "channel": "invoke"},
        )
    )
    assert build_plan(pack) == build_plan(pack)
