"""Contract tests for the armed anti-slop Semgrep rules.

Rules `dharma.no-new-substrate` (Rule 2) and `dharma.providers-canonical`
(Rule 6) were promoted from WARNING to ERROR on 2026-07-09 so the strict
Semgrep gate (`semgrep --config .semgrep --error`) actually enforces them.

These assertions fail if either rule is silently demoted back to WARNING
(which would neuter the ERROR-only gate) or if the Rule 2 grandfather
allowlist for the three pre-existing canonical substrates is dropped
(which would retroactively fail landed code and pressure a re-demotion).
"""

from pathlib import Path

import yaml

_RULES_PATH = Path(__file__).resolve().parent.parent / ".semgrep" / "dharma-anti-slop.yml"

# Pre-existing legitimate substrates grandfathered when Rule 2 was armed.
# Each declares closure-layer role `canonical-store` in its file header.
_GRANDFATHERED_SUBSTRATES = {
    "dharma_swarm/bridge_registry.py",
    "dharma_swarm/graph_store.py",
    "dharma_swarm/knowledge_units.py",
}


def _load_rules():
    with _RULES_PATH.open() as fh:
        doc = yaml.safe_load(fh)
    return {rule["id"]: rule for rule in doc["rules"]}


def test_no_new_substrate_is_error():
    rules = _load_rules()
    assert "dharma.no-new-substrate" in rules
    assert rules["dharma.no-new-substrate"]["severity"] == "ERROR"


def test_providers_canonical_is_error():
    rules = _load_rules()
    assert "dharma.providers-canonical" in rules
    assert rules["dharma.providers-canonical"]["severity"] == "ERROR"


def test_no_new_substrate_grandfathers_existing_substrates():
    rules = _load_rules()
    excluded = set(rules["dharma.no-new-substrate"]["paths"]["exclude"])
    missing = _GRANDFATHERED_SUBSTRATES - excluded
    assert not missing, f"grandfathered substrates dropped from allowlist: {sorted(missing)}"


def test_no_new_substrate_still_polices_new_substrates():
    """Arming must not have collapsed the pattern — the metavariable-regex
    that scopes the rule to Store/Ledger/Registry/Substrate class names, and
    the sqlite/aiosqlite connect patterns, must still be present."""
    rules = _load_rules()
    rule = rules["dharma.no-new-substrate"]
    regexes = [
        mv["regex"]
        for clause in rule["patterns"]
        for mv in [clause.get("metavariable-regex", {})]
        if mv.get("metavariable") == "$NAME"
    ]
    assert any(
        all(tok in rx for tok in ("Store", "Ledger", "Registry", "Substrate"))
        for rx in regexes
    ), "Rule 2 lost its substrate-class-name scope"
    flat = yaml.safe_dump(rule)
    assert "sqlite3.connect" in flat and "aiosqlite.connect" in flat
