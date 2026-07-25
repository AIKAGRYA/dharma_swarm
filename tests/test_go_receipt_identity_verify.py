"""Conformance and verify-on-ingest tests for the Go receipt identity chain.

Two guarantees:

1. Conformance. The Python port in dharma_swarm.operator_core.go_receipt_identity
   reproduces the Go SDK identity chain byte-for-byte. Golden vectors below were
   generated from tools/go_sdk/receipt (ContentHash / EventUID / ReceiptID) over
   the same fixed inputs used by tools/go_sdk/receipt/receipt_test.go. A
   go-guarded differential test regenerates them and asserts equality.

2. Verify-on-ingest. load_go_evidence_receipt admits a valid receipt and rejects
   any receipt whose event_uid or receipt_id has been tampered with.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from dharma_swarm.world_radar.go_invoke import go_toolchain_capable

from dharma_swarm.operator_core.go_evidence_bridge import (
    GoEvidenceBridgeError,
    load_go_evidence_receipt,
)
from dharma_swarm.operator_core.go_receipt_identity import (
    content_hash,
    derive_event_uid,
    derive_receipt_id,
    short_digest,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
GO_SDK_DIR = REPO_ROOT / "tools" / "go_sdk"

# Golden vectors generated from tools/go_sdk/receipt exported functions over the
# receipt_test.go fixture inputs. Do not hand-edit; regenerate with the Go SDK.
GOLDEN: tuple[dict[str, str], ...] = (
    {
        "name": "ok_true",
        "source": "agentops_fixture",
        "source_url": "fixture://agentops/success",
        "correlation_id": "corr_v0_test_001",
        "payload": '{"ok":true}',
        "content_hash": "sha256:4062edaf750fb8074e7e83e0c9028c94e32468a8b6f1614774328ef045150f93",
        "event_uid": "evt_ce2dd2612e8ed3a8ba85d312",
        "receipt_id": "goev_2f9865bcc6d6155bef9b3965",
    },
    {
        "name": "ok_false",
        "source": "agentops_fixture",
        "source_url": "fixture://agentops/success",
        "correlation_id": "corr_v0_test_001",
        "payload": '{"ok":false}',
        "content_hash": "sha256:38667e60226bf99701916900a2a265233dcc014e1206c173ade921d608824b53",
        "event_uid": "evt_344aebadd46a2727ef384387",
        "receipt_id": "goev_822cf96ec381c7cf055841fa",
    },
    {
        "name": "gate_all_green",
        "source": "agentops_fixture",
        "source_url": "fixture://agentops/success",
        "correlation_id": "corr_v0_test_001",
        "payload": '{"gate_state":"all_green","scope_state":"scope_clean"}',
        "content_hash": "sha256:a077ec27c5479b42eb11737dcb6cfdb68e2a9da31bc2ecb77965ba4fd43582b8",
        "event_uid": "evt_23559c5a04cae44ae54fbdb8",
        "receipt_id": "goev_7f52a6e9d47d48e0847986bf",
    },
    {
        "name": "diff_source",
        "source": "different_source",
        "source_url": "fixture://agentops/success",
        "correlation_id": "corr_v0_test_001",
        "payload": '{"ok":true}',
        "content_hash": "sha256:4062edaf750fb8074e7e83e0c9028c94e32468a8b6f1614774328ef045150f93",
        "event_uid": "evt_a9827548ddf375967df99327",
        "receipt_id": "goev_963db0dfd19cc1f7b382a391",
    },
    {
        "name": "diff_corr",
        "source": "agentops_fixture",
        "source_url": "fixture://agentops/success",
        "correlation_id": "corr_other_002",
        "payload": '{"ok":true}',
        "content_hash": "sha256:4062edaf750fb8074e7e83e0c9028c94e32468a8b6f1614774328ef045150f93",
        "event_uid": "evt_ce2dd2612e8ed3a8ba85d312",
        "receipt_id": "goev_bda7c6f7f1ad6de0190e7feb",
    },
)


def _write_receipt(path: Path, vec: dict[str, str], **overrides: str) -> Path:
    receipt = {
        "receipt_id": vec["receipt_id"],
        "correlation_id": vec["correlation_id"],
        "source": vec["source"],
        "source_url": vec["source_url"],
        "observed_at": "2026-05-09T00:00:00Z",
        "content_hash": vec["content_hash"],
        "event_uid": vec["event_uid"],
        "schema_version": "go_evidence_receipt.v0",
        "status": "accepted",
        "payload": {"status": "completed"},
    }
    receipt.update(overrides)
    path.write_text(json.dumps(receipt), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Conformance: Python port reproduces the Go identity chain
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("vec", GOLDEN, ids=[v["name"] for v in GOLDEN])
def test_python_identity_chain_matches_go_golden(vec: dict[str, str]) -> None:
    ch = content_hash(vec["payload"].encode("utf-8"))
    assert ch == vec["content_hash"]
    event_uid = derive_event_uid(vec["source"], vec["source_url"], ch)
    assert event_uid == vec["event_uid"]
    receipt_id = derive_receipt_id(vec["correlation_id"], event_uid)
    assert receipt_id == vec["receipt_id"]


def test_short_digest_is_hex12() -> None:
    digest = short_digest("a", "b")
    assert len(digest) == 24
    assert int(digest, 16) >= 0


def test_short_digest_nul_join_is_injective_on_boundaries() -> None:
    # NUL join must distinguish ("ab","c") from ("a","bc").
    assert short_digest("ab", "c") != short_digest("a", "bc")


# ---------------------------------------------------------------------------
# Verify-on-ingest
# ---------------------------------------------------------------------------


def test_valid_receipt_is_admitted(tmp_path: Path) -> None:
    path = _write_receipt(tmp_path / "valid.json", GOLDEN[0])
    receipt = load_go_evidence_receipt(path)
    assert receipt.event_uid == GOLDEN[0]["event_uid"]
    assert receipt.receipt_id == GOLDEN[0]["receipt_id"]


def test_flipped_event_uid_is_rejected(tmp_path: Path) -> None:
    tampered = GOLDEN[0]["event_uid"][:-1] + ("a" if GOLDEN[0]["event_uid"][-1] != "a" else "b")
    path = _write_receipt(tmp_path / "bad_event.json", GOLDEN[0], event_uid=tampered)
    with pytest.raises(GoEvidenceBridgeError, match="event_uid does not verify"):
        load_go_evidence_receipt(path)


def test_flipped_receipt_id_is_rejected(tmp_path: Path) -> None:
    tampered = GOLDEN[0]["receipt_id"][:-1] + ("a" if GOLDEN[0]["receipt_id"][-1] != "a" else "b")
    path = _write_receipt(tmp_path / "bad_receipt.json", GOLDEN[0], receipt_id=tampered)
    with pytest.raises(GoEvidenceBridgeError, match="receipt_id does not verify"):
        load_go_evidence_receipt(path)


def test_flipped_source_breaks_event_uid_chain(tmp_path: Path) -> None:
    # Changing source without recomputing event_uid must fail verification.
    path = _write_receipt(tmp_path / "bad_source.json", GOLDEN[0], source="attacker_source")
    with pytest.raises(GoEvidenceBridgeError, match="event_uid does not verify"):
        load_go_evidence_receipt(path)


def test_empty_source_url_is_rejected_even_when_identity_matches(tmp_path: Path) -> None:
    event_uid = derive_event_uid(GOLDEN[0]["source"], "", GOLDEN[0]["content_hash"])
    receipt_id = derive_receipt_id(GOLDEN[0]["correlation_id"], event_uid)
    path = _write_receipt(
        tmp_path / "missing_source_url.json",
        GOLDEN[0],
        source_url="",
        event_uid=event_uid,
        receipt_id=receipt_id,
    )
    with pytest.raises(GoEvidenceBridgeError, match="missing required identity fields"):
        load_go_evidence_receipt(path)


def test_cross_receipt_id_splice_is_rejected(tmp_path: Path) -> None:
    # Splice a receipt_id from a different correlation_id onto this event_uid.
    path = _write_receipt(
        tmp_path / "spliced.json",
        GOLDEN[0],
        receipt_id=GOLDEN[4]["receipt_id"],
    )
    with pytest.raises(GoEvidenceBridgeError, match="receipt_id does not verify"):
        load_go_evidence_receipt(path)


# ---------------------------------------------------------------------------
# Differential: regenerate golden vectors from the Go SDK and compare
# ---------------------------------------------------------------------------


_GO_GOLDEN_PROGRAM = """package main

import (
\t"encoding/json"
\t"fmt"

\t"github.com/AmitabhainArunachala/dharma_swarm/tools/go_sdk/receipt"
)

func main() {
\ttype in struct{ name, src, url, corr, payload string }
\tins := []in{
{cases}
\t}
\ttype vec struct {
\t\tName        string `json:"name"`
\t\tContentHash string `json:"content_hash"`
\t\tEventUID    string `json:"event_uid"`
\t\tReceiptID   string `json:"receipt_id"`
\t}
\tvar out []vec
\tfor _, i := range ins {
\t\tch := receipt.ContentHash([]byte(i.payload))
\t\teu := receipt.EventUID(i.src, i.url, ch)
\t\trid := receipt.ReceiptID(i.corr, eu)
\t\tout = append(out, vec{i.name, ch, eu, rid})
\t}
\tb, _ := json.Marshal(out)
\tfmt.Println(string(b))
}
"""


def test_go_regenerates_identical_golden_vectors(tmp_path: Path) -> None:
    if not go_toolchain_capable(GO_SDK_DIR):
        pytest.skip("no Go toolchain satisfying go_sdk/go.mod")

    cases = "\n".join(
        "\t\t{%s, %s, %s, %s, %s},"
        % (
            json.dumps(v["name"]),
            json.dumps(v["source"]),
            json.dumps(v["source_url"]),
            json.dumps(v["correlation_id"]),
            json.dumps(v["payload"]),
        )
        for v in GOLDEN
    )
    program = _GO_GOLDEN_PROGRAM.replace("{cases}", cases)

    gen_dir = tmp_path / "goldgen"
    gen_dir.mkdir()
    (gen_dir / "main.go").write_text(program, encoding="utf-8")
    (gen_dir / "go.mod").write_text(
        "module goldgen\n\ngo 1.26\n\n"
        "require github.com/AmitabhainArunachala/dharma_swarm/tools/go_sdk v0.0.0\n\n"
        f"replace github.com/AmitabhainArunachala/dharma_swarm/tools/go_sdk => {GO_SDK_DIR}\n",
        encoding="utf-8",
    )

    env = dict(os.environ)
    env.setdefault("GOCACHE", "/tmp/dharma-swarm-go-build")
    env.setdefault("GOMODCACHE", "/tmp/dharma-swarm-go-mod")
    subprocess.run(["go", "mod", "tidy"], cwd=gen_dir, env=env, check=True, capture_output=True)
    result = subprocess.run(
        ["go", "run", "."], cwd=gen_dir, env=env, check=True, capture_output=True, text=True
    )
    regenerated = {v["name"]: v for v in json.loads(result.stdout)}

    for v in GOLDEN:
        got = regenerated[v["name"]]
        assert got["content_hash"] == v["content_hash"]
        assert got["event_uid"] == v["event_uid"]
        assert got["receipt_id"] == v["receipt_id"]
