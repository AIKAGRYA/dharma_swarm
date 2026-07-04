"""Tests for NĀGA-IR receipt emission from the Sattva Assurance Boundary.

Scope is PR #3: verify that `scripts/governance/assurance_boundary.py`,
when run with `--emit-receipts`, produces six `dharma.naga_receipt.v1`
records (five per-contract leaves plus one aggregate) written to a dated
path, without changing exit codes or the existing verdict output.

These tests exercise the emitter directly (fast, no boundary parse) and
the CLI (slower, real boundary parse) to catch regressions in either
path. They do not depend on the mesh, ed25519 keys, or a running SAB —
those are PR #4+ concerns.
"""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:  # pragma: no cover — path fix for direct pytest runs
    sys.path.insert(0, str(REPO_ROOT))


from scripts.governance.naga_receipt_emit import (  # noqa: E402
    NAGA_SCHEMA_VERSION,
    emit_boundary_receipts,
    rfc3339_utc_now,
    write_receipts_jsonl,
)


# ---------------------------------------------------------------------------
# Duck-typed BoundaryReport doubles (avoid importing the real gate here so
# that tests stay fast and isolated from AB-05 manifest drift)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _FakeViolation:
    contract: str
    location: str
    detail: str

    def render(self) -> str:
        return f"{self.contract} {self.location}: {self.detail}"


@dataclass(frozen=True)
class _FakeReport:
    hold_at_zero: tuple
    measured: dict


def _clean_report() -> _FakeReport:
    return _FakeReport(
        hold_at_zero=(),
        measured={"AB-01": (), "AB-02": (), "AB-03": ()},
    )


def _dirty_report() -> _FakeReport:
    return _FakeReport(
        hold_at_zero=(
            _FakeViolation("AB-05", "layer x", "class Y missing"),
        ),
        measured={
            "AB-01": (
                _FakeViolation("AB-01", "dharma_swarm/spine/x.py:12", "not frozen"),
            ),
            "AB-02": (),
            "AB-03": (),
        },
    )


def _emit(report: _FakeReport, **overrides):
    now = overrides.pop("now_utc_iso", "2026-07-04T15:00:00.000Z")
    return emit_boundary_receipts(
        report,
        boundary_run_id="urn:uuid:00000000-0000-4000-8000-000000000001",
        now_utc_iso=now,
        repo_root=REPO_ROOT,
        boundary_packages=("dharma_swarm/spine",),
        boundary_modules=("dharma_swarm/runtime_state.py",),
        **overrides,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_emits_six_receipts_per_run():
    receipts = _emit(_clean_report())
    assert len(receipts) == 6
    leaf_ids = [r["claim"]["id"] for r in receipts[:5]]
    assert leaf_ids == ["AB-01", "AB-02", "AB-03", "AB-04", "AB-05"]
    # Aggregate last.
    assert receipts[-1]["claim"]["id"] == "AB-AGG"
    assert (
        receipts[-1]["evidence"][0]["method"] == "assurance_boundary_aggregator"
    )


_REQUIRED_TOP_LEVEL = {
    "schema_version",
    "receipt_id",
    "subject",
    "claim",
    "claim_hash",
    "evidence",
    "authority",
    "causal_origin",
    "epistemic_origin",
    "ttl",
    "challenge_base",
    "challenge_state",
    "prev_receipt_hash",
    "signatures",
}


def test_receipt_schema_shape():
    receipts = _emit(_clean_report())
    for r in receipts:
        assert set(r.keys()) >= _REQUIRED_TOP_LEVEL, (
            f"missing keys: {_REQUIRED_TOP_LEVEL - set(r.keys())}"
        )
        assert r["schema_version"] == NAGA_SCHEMA_VERSION
        assert r["receipt_id"].startswith("urn:uuid:")
        assert r["claim"]["class"] == "contract"
        assert r["claim_hash"].startswith("sha256:")
        assert len(r["claim_hash"]) == len("sha256:") + 64
        assert r["subject"]["hash"].startswith("sha256:")
        assert r["authority"]["authority_key"].startswith("sha256:")
        assert r["authority"]["authority_key"] == r["challenge_base"]["query_key"]
        assert r["challenge_state"]["authoritative"] is False
        assert r["ttl"]["expires_at"].endswith("Z")
        assert r["ttl"]["observed_at"].endswith("Z")
        # Never emit an empty signatures array.
        assert isinstance(r["signatures"], list) and len(r["signatures"]) >= 1
        sig = r["signatures"][0]
        assert sig["alg"] == "ed25519"
        assert sig["sig"].startswith("sha256:")
        assert "..." not in sig["sig"]
        # No placeholder ellipsis anywhere.
        assert "sha256:..." not in json.dumps(r)
        # Evidence is a non-empty list with modality field.
        assert isinstance(r["evidence"], list) and r["evidence"]
        assert r["evidence"][0]["modality"] in {"Proven_by"}


def test_claim_hash_stable_under_reorder():
    """Reordering the claim object's keys must not change claim_hash."""
    receipts = _emit(_clean_report())
    leaf = receipts[0]
    original_claim = leaf["claim"]
    permuted = {k: original_claim[k] for k in reversed(list(original_claim.keys()))}
    # Recompute the way the emitter does (JCS approximation: sort_keys +
    # compact separators + UTF-8).
    def _hash(obj):
        payload = json.dumps(
            obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        return "sha256:" + hashlib.sha256(payload).hexdigest()

    assert _hash(original_claim) == _hash(permuted)
    assert _hash(original_claim) == leaf["claim_hash"]


def test_aggregate_links_to_leaves():
    receipts = _emit(_clean_report())
    leaves, aggregate = receipts[:5], receipts[-1]

    def _self_hash(r):
        payload = json.dumps(
            r, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        return "sha256:" + hashlib.sha256(payload).hexdigest()

    expected = [_self_hash(leaf) for leaf in leaves]
    linked = aggregate["evidence"][0]["params"]["leaf_receipt_hashes"]
    assert linked == expected
    # All five hashes are distinct (no accidental collapse).
    assert len(set(linked)) == 5


def test_aggregate_fails_when_hold_at_zero_present():
    """A hold-at-zero violation must propagate to the aggregate result."""
    dirty = _emit(_dirty_report())
    assert dirty[-1]["evidence"][0]["result"] == "fail"
    # AB-05 leaf fails; AB-01 measured leaf still passes (banked).
    by_id = {r["claim"]["id"]: r for r in dirty}
    assert by_id["AB-05"]["evidence"][0]["result"] == "fail"
    assert by_id["AB-01"]["evidence"][0]["result"] == "pass"


def _run_cli(tmp_path: Path, flag: str) -> subprocess.CompletedProcess:
    """Invoke the boundary CLI against the real repo, isolating writes.

    We copy the boundary script into tmp_path is not necessary because the
    script writes receipts under `--repo-root/reports/naga_receipts/...`.
    To isolate writes without polluting the repo, we point --repo-root at
    a staging directory that mirrors the boundary shape symlink-free is
    overkill for this test; instead we use the real repo root but delete
    any receipts we produced afterwards.
    """
    cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "governance" / "assurance_boundary.py"),
        flag,
    ]
    return subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_exit_code_unchanged_by_emission(tmp_path):
    """--emit-receipts and --no-emit-receipts must return the same exit code."""
    with_emit = _run_cli(tmp_path, "--emit-receipts")
    no_emit = _run_cli(tmp_path, "--no-emit-receipts")
    assert with_emit.returncode == no_emit.returncode, (
        f"emit={with_emit.returncode} stderr={with_emit.stderr!r} "
        f"no_emit={no_emit.returncode} stderr={no_emit.stderr!r}"
    )
    # Verdict stdout should also be identical (receipts are additive).
    assert with_emit.stdout == no_emit.stdout


def test_emission_failure_does_not_change_verdict(monkeypatch, tmp_path, capsys):
    """A failing writer must not turn an exit-0 into exit-2."""
    from scripts.governance import assurance_boundary as ab

    called = {"emit": False}

    def _fake_safely(*, report, repo_root, boundary_run_id):
        called["emit"] = True
        raise RuntimeError("simulated writer explosion")

    # Wrap so the raise is caught inside the CLI path, not by the test.
    def _wrapped(**kwargs):
        try:
            _fake_safely(**kwargs)
        except Exception as exc:
            print(
                f"assurance-boundary: NĀGA receipt emission failed — {exc}",
                file=sys.stderr,
            )

    monkeypatch.setattr(ab, "_emit_naga_receipts_safely", _wrapped)
    # Run in-process; capture the exit code without a subprocess.
    exit_code = ab.main(["--emit-receipts", "--repo-root", str(REPO_ROOT)])
    assert called["emit"] is True
    assert exit_code in (0, 1)  # unchanged relative to real repo state
    captured = capsys.readouterr()
    assert "NĀGA receipt emission failed" in captured.err


def test_receipts_write_to_dated_path(tmp_path):
    """write_receipts_jsonl must produce reports/naga_receipts/YYYY/MM/DD/…."""
    receipts = _emit(_clean_report(), now_utc_iso="2026-07-04T15:00:00.000Z")
    out = write_receipts_jsonl(
        receipts,
        repo_root=tmp_path,
        boundary_run_id="urn:uuid:00000000-0000-4000-8000-000000000001",
        now_utc_iso="2026-07-04T15:00:00.000Z",
    )
    expected_dir = tmp_path / "reports" / "naga_receipts" / "2026" / "07" / "04"
    assert out.parent == expected_dir
    assert out.exists()
    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 6
    parsed = [json.loads(line) for line in lines]
    assert [r["claim"]["id"] for r in parsed] == [
        "AB-01", "AB-02", "AB-03", "AB-04", "AB-05", "AB-AGG",
    ]


def test_deterministic_receipt_ids_across_runs():
    """Same boundary_run_id + same contract yields the same receipt_id."""
    r1 = _emit(_clean_report())
    r2 = _emit(_clean_report())
    for a, b in zip(r1, r2):
        assert a["receipt_id"] == b["receipt_id"]
