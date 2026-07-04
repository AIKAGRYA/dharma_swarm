from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "governance" / "check_naga_spec_repo_grounding.py"


def load_module():
    spec = importlib.util.spec_from_file_location("check_naga_spec_repo_grounding", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def core_doc() -> str:
    return """# Core

## Canonicality

```text
canonical?(receipt, mesh_state, current, t) =
  schema_valid(receipt)
  and signatures_valid(receipt)
  and ttl_live(receipt.ttl, receipt.evidence, t)
  and clock_within_skew(receipt.clock, t)
  and authority_matches(receipt.authority, receipt.epistemic_origin, receipt.evidence, current)
  and no_unresolved_challenge(mesh_state, receipt.challenge_base.authority_key, receipt.challenge_base, t)
```

`claim_hash(receipt)` is the SHA-256 hash over `claim_id`, `claim_class`, `claim_strength`, normalized statement, scope, fragment id, and obligation hash when present.
`authority_key(receipt)` is the SHA-256 hash over `{subject_id, claim_hash, trust_base_id, fragment_id, fragment_version}`.

## Wire reference

The wire object carries `schema_version`, `receipt_id`, `subject`, `claim`, `claim_hash`, `evidence[]`, `authority`, `causal_origin`, `epistemic_origin`, `ttl`, `challenge_base`, `challenge_state`, `clock`, `prev_receipt_hash`, and `signatures`.

## Evidence modalities

| Modality | Required fields |
|---|---|
| `Proven_by` | verifier |
| `Tested_by` | harness |
| `Witnessed_by` | runtime id, identity, observed value, replay hash, TTL |
| `Challenged_by` | counterexample |
| `Attested_by` | principal |

## Local integration

origin/main contains `scripts/governance/assurance_boundary.py`, `dharma_swarm/coalgebra.py`, and `dharma_swarm/connectors/sab_client.py`. The boundary emits `assurance_boundary_report.v1`, covers AB-01 through AB-05, exits with 0, 1, or 2, and is AST-static. `dharma_swarm/coalgebra.py` exposes lowercase `bisimilar(...)`. `packages/telos-kernel/` is future-only and absent today.
"""


def wire_doc() -> str:
    return """# Wire

## Receipt object

| Field | Type | Required |
|---|---|---:|
| `schema_version` | string | yes |
| `receipt_id` | string | yes |
| `subject` | object | yes |
| `claim` | object | yes |
| `claim_hash` | string | yes |
| `evidence` | array | yes |
| `authority` | object | yes |
| `causal_origin` | object | yes |
| `epistemic_origin` | object | yes |
| `ttl` | object | yes |
| `challenge_base` | object | yes |
| `challenge_state` | object | yes |
| `clock` | object | yes |
| `prev_receipt_hash` | string | yes |
| `signatures` | array | yes |

## Claim

`claim_hash` is derived from `claim_id`, `claim_class`, `claim_strength`, normalized `statement`, `scope`, `fragment_id`, and `obligation_hash` when present.

## Evidence record

Every evidence item uses one of `Proven_by`, `Tested_by`, `Witnessed_by`, `Challenged_by`, or `Attested_by`.

## Proven_by

Required body fields:

| Field | Threshold |
|---|---|
| `verifier` | non-empty |

## Tested_by

Required body fields:

| Field | Threshold |
|---|---|
| `harness` | non-empty |

## Witnessed_by

The threshold is runtime identity, observed value hash, replay or trace hash, TTL, observed time, and maximum clock skew.

Required body fields:

| Field | Threshold |
|---|---|
| `runtime_id` | non-empty |
| `identity` | signed |
| `observed_value_hash` | hash URI |
| `replay_hash` | hash URI |
| `observed_at` | UTC RFC 3339 |
| `max_clock_skew_ms` | integer |
| `ttl_expires_at` | UTC RFC 3339 |

## Challenged_by

The resolution state is one of `open`, `refuted`, `accepted`, or `expired`.

## Attested_by

Required body fields:

| Field | Threshold |
|---|---|
| `principal` | non-empty |

## Authority key

`authority_key` is SHA-256 over `{subject_id, claim_hash, trust_base_id, fragment_id, fragment_version}`.
"""


def witness_doc() -> str:
    return """# Mesh

## Merge state

AuthorityKey = "sha256:" + SHA256(JCS({subject_id, claim_hash, trust_base_id, fragment_id, fragment_version}))

```text
canonical_mesh_projection?(state, receipt, current, t) =
  canonical?(receipt, state, current, t)
```

## Challenge rule

Resolution states are exactly `open`, `refuted`, `accepted`, and `expired`.

## Failure states

The mesh must represent `invalid_schema`, `signature_failed`, `ttl_stale`, `clock_skew_unknown`, `challenge_unresolved`, and `trust_base_mismatch`.
"""


def write_triple(tmp_path: Path, *, core: str | None = None, wire: str | None = None, witness: str | None = None) -> Path:
    spec_dir = tmp_path / "specs" / "naga_ir"
    spec_dir.mkdir(parents=True)
    (spec_dir / "core.md").write_text(core if core is not None else core_doc(), encoding="utf-8")
    (spec_dir / "receipt_wire.md").write_text(wire if wire is not None else wire_doc(), encoding="utf-8")
    (spec_dir / "witness_mesh.md").write_text(witness if witness is not None else witness_doc(), encoding="utf-8")
    return spec_dir


def fake_origin(monkeypatch, module):
    files = {
        "scripts/governance/assurance_boundary.py": 'REPORT_SCHEMA_VERSION = "assurance_boundary_report.v1"\nAB-01 AB-02 AB-03 AB-04 AB-05\nEXIT_HOLDS = 0\nEXIT_VIOLATED = 1\nEXIT_BROKEN = 2\nimport ast\n',
        "dharma_swarm/coalgebra.py": "def bisimilar(sys1, sys2, initial1, initial2, depth=100):\n    return True\n",
        "dharma_swarm/connectors/sab_client.py": 'SCHEMA = "dharma_swarm.sab_contribution.v1"\nclass SABContribution: pass\n',
        "docs/telos-engine/01_SATTVA_VISION.md": "W = C x E x A x B x V x P\n",
    }

    def run_git(args, repo_root):
        if args[1] == "show":
            path = args[-1].split(":", 1)[1]
            return module.GitResult(0, files[path], "") if path in files else module.GitResult(1, "", "missing")
        if args[1] == "ls-tree":
            path = args[-1]
            exists = path in files or path == "packages/telos-gatekeeper"
            return module.GitResult(0 if exists else 1, path if exists else "", "missing")
        raise AssertionError(args)

    monkeypatch.setattr(module, "run_git", run_git)


def run_grounding(tmp_path: Path, monkeypatch, *, core: str | None = None, wire: str | None = None, witness: str | None = None):
    module = load_module()
    fake_origin(monkeypatch, module)
    return module.run([write_triple(tmp_path, core=core, wire=wire, witness=witness)], repo_root=tmp_path)


def test_grounded_triple_passes_against_origin_main(tmp_path, monkeypatch):
    assert run_grounding(tmp_path, monkeypatch) == []


@pytest.mark.parametrize(
    ("core", "code"),
    [
        (core_doc().replace("origin/main contains `scripts/governance/assurance_boundary.py`", "origin/main does not contain `scripts/governance/assurance_boundary.py`"), "assurance_boundary_exists"),
        (core_doc() + "\n`Bisimilar()` is available.\n", "bisimilar_lowercase"),
        (core_doc().replace("`dharma_swarm/connectors/sab_client.py`", "`dharma_swarm/sab_client.py`"), "sab_client_path"),
        (core_doc().replace("`schema_version`, `receipt_id`, ", "`schema_version`, "), "receipt_fields"),
        (core_doc() + "\nThe current `packages/telos-kernel/` exists today.\n", "absent_object_present"),
    ],
)
def test_known_false_repo_claims_are_caught(tmp_path, monkeypatch, core, code):
    findings = run_grounding(tmp_path, monkeypatch, core=core)
    assert any(finding.code == code for finding in findings)


def test_witnessed_by_body_table_required(tmp_path, monkeypatch):
    wire = wire_doc().replace("Required body fields:\n\n| Field | Threshold |\n|---|---|\n| `runtime_id` | non-empty |\n| `identity` | signed |\n| `observed_value_hash` | hash URI |\n| `replay_hash` | hash URI |\n| `observed_at` | UTC RFC 3339 |\n| `max_clock_skew_ms` | integer |\n| `ttl_expires_at` | UTC RFC 3339 |\n", "")
    findings = run_grounding(tmp_path, monkeypatch, wire=wire)
    assert any(finding.code == "witnessed_by_body_table" for finding in findings)


def test_challenge_state_consistency_required(tmp_path, monkeypatch):
    witness = witness_doc().replace("and `expired`", "`expired`, and `withdrawn`")
    findings = run_grounding(tmp_path, monkeypatch, witness=witness)
    assert any(finding.code == "challenge_states" for finding in findings)


def test_claim_hash_consistency_required(tmp_path, monkeypatch):
    wire = wire_doc().replace("`scope`, `fragment_id`", "`scope_id`, `fragment_id`")
    findings = run_grounding(tmp_path, monkeypatch, wire=wire)
    assert any(finding.code == "claim_hash_derivation" for finding in findings)


def test_authority_key_consistency_required(tmp_path, monkeypatch):
    witness = witness_doc().replace("claim_hash, trust_base_id", "claim_id, trust_base_id")
    findings = run_grounding(tmp_path, monkeypatch, witness=witness)
    assert any(finding.code == "authority_key_derivation" for finding in findings)


def test_origin_main_beats_stale_working_tree(tmp_path, monkeypatch):
    (tmp_path / "dharma_swarm").mkdir()
    (tmp_path / "dharma_swarm" / "sab_client.py").write_text("stale local file", encoding="utf-8")
    core = core_doc().replace("`dharma_swarm/connectors/sab_client.py`", "`dharma_swarm/sab_client.py`")
    findings = run_grounding(tmp_path, monkeypatch, core=core)
    assert any(finding.code == "sab_client_path" for finding in findings)
