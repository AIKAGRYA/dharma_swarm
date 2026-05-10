from scripts.governance.check_precommit_drift import (
    configured_hook_ids,
    missing_required_hooks,
    required_hook_ids,
)


def test_required_hook_ids_reads_fragment_list():
    fragment = """
tier_a_quality_hooks:
  policy:
    mode: advisory
  required_hook_ids:
    - dharma-vulture
    - dharma-radon-cc
    - dharma-bandit
"""

    assert required_hook_ids(fragment) == [
        "dharma-vulture",
        "dharma-radon-cc",
        "dharma-bandit",
    ]


def test_configured_hook_ids_reads_pre_commit_hooks():
    config = """
repos:
  - repo: local
    hooks:
      - id: dharma-vulture
        name: vulture
      - id: dharma-mypy
        name: mypy
"""

    assert configured_hook_ids(config) == {"dharma-vulture", "dharma-mypy"}


def test_missing_required_hooks_preserves_fragment_order():
    required = ["dharma-vulture", "dharma-radon-cc", "dharma-bandit"]
    configured = {"dharma-bandit"}

    assert missing_required_hooks(required, configured) == [
        "dharma-vulture",
        "dharma-radon-cc",
    ]
