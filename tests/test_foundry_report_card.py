"""Tests for the verified report card renderer (pure function of a receipt)."""

from __future__ import annotations

import json

from dharma_swarm.foundry.receipts import (
    FoundryReceipt,
    benchmark_link,
    merge_event_link,
    pre_registration_link,
)
from dharma_swarm.foundry.report_card import card_from_receipt_file, render_report_card


def _receipt(confirmed: bool) -> dict:
    r = FoundryReceipt(
        receipt_id="rc1", target_id="openevolve-mlx", candidate_id="c1",
        pre_registration=pre_registration_link(
            target_id="openevolve-mlx", resolved_sha="abc", tree_digest="sha256:t",
            baseline_metric=1.0, oracle_cmd=["make", "bench"], seed=1,
        ),
        benchmark=benchmark_link(
            baseline_metric=1.0, candidate_metric=1.09, runs=5,
            coefficient_of_variation=0.02, repro_cmd=["make", "bench"],
            isolation_level="docker_nonet",
        ),
    )
    if confirmed:
        r.merge_event = merge_event_link(
            repo="x/y", pr_url="u", state="MERGED", author="bot",
            merged_by="maintainer", merge_commit_sha="abc", merged_at="t",
        )
    return r.to_dict()


def test_lab_local_card_does_not_overclaim():
    card = render_report_card(_receipt(confirmed=False))
    assert "LAB-LOCAL (UNVERIFIED)" in card
    assert "EXTERNALLY CONFIRMED" not in card


def test_confirmed_card_shows_ring3():
    card = render_report_card(_receipt(confirmed=True))
    assert "EXTERNALLY CONFIRMED" in card


def test_benchmark_delta_rendered():
    card = render_report_card(_receipt(confirmed=True))
    assert "Delta" in card
    assert "make bench" in card


def test_misses_section_always_present():
    card = render_report_card(_receipt(confirmed=False))
    assert "## Published misses" in card
    # empty misses still renders the mandatory section
    assert "mandatory" in card


def test_misses_are_listed_when_present():
    card = render_report_card(
        _receipt(confirmed=True),
        misses=[{"what": "kernel v2", "detail": "3.2% slower; discarded"}],
    )
    assert "kernel v2" in card
    assert "3.2% slower" in card


def test_card_from_file(tmp_path):
    receipt = _receipt(confirmed=True)
    receipt["sealed_digest"] = "sha256:deadbeef"
    path = tmp_path / "r.json"
    path.write_text(json.dumps(receipt))
    card = card_from_receipt_file(path)
    assert "sha256:deadbeef" in card
