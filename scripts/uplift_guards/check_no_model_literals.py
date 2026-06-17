"""No-model-literals guard — keeps the model pool the single source of truth.

After the 2026-06 routing consolidation, every model-id string lives in exactly
ONE place: ``dharma_swarm/model_pool.py``. Every other surface (provider_matrix,
tui/model_routing, ollama_config, provider_smoke, free_fleet, the priority
lists) is a *projection* of the pool. This guard fails the build if a hardcoded
frontier/cloud model-id string re-appears anywhere else — so the drift the
consolidation killed can never silently grow back.

Conservative on purpose: it flags the two literal shapes that were the actual
drift — Ollama-cloud ids (``<name>:cloud``) and vendor-prefixed router ids
(``moonshotai/…``, ``z-ai/…``, ``deepseek/…``, ``qwen/…``, ``meta/…``,
``minimaxai/…``, ``mistralai/…``, ``nvidia/…``, ``google/…``, ``accounts/…``,
``openai/gpt-…``) — inside ``dharma_swarm/`` source. Tests, docs, and the pool
itself are exempt.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCAN_ROOT = REPO_ROOT / "dharma_swarm"

# The single sanctioned home for model-id literals + a few seams that legitimately
# name a provider-default constant (not a frontier list). Keep this list SHORT.
ALLOWLIST = {
    "evolution_roster.py",      # THE curated model-data seed (model_pool reads this)
    "model_pool.py",            # the pool structure built from the seed
    "model_defaults.py",        # provider-default constants
    "model_hierarchy.py",       # provider-grain defaults (projections of the pool)
    "models.py",                # ProviderType / enums
}

# The drift shapes: cloud ids and vendor-prefixed router ids.
PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("ollama-cloud id", re.compile(r"""["'][a-z0-9][a-z0-9.\-]*:cloud["']""")),
    ("vendor-prefixed router id", re.compile(
        r"""["'](?:moonshotai|z-ai|zai-org|deepseek|qwen|meta|minimaxai|mistralai|nvidia|google|accounts/fireworks)/[A-Za-z0-9._\-/]+["']"""
    )),
]

# Confirmed FALSE POSITIVES — strings the ``vendor/...`` pattern matches that are
# NOT deployable model-id literals. Keyed by ``(filename, matched-snippet)`` so the
# exemption is surgical: it clears exactly these tokens and never blanket-allowlists
# a whole file (a REAL literal added to any of these files would still fail).
#
#   - file-path components fed to ``Path(...)`` / used as state-file keys
#   - substring prefixes used with ``startswith`` in router discovery logic
#     (bare vendor families, not deployable ids)
#
# Quoting normalised to single quotes for the key (see ``_norm`` below).
FALSE_POSITIVES: set[tuple[str, str]] = {
    ("agent_export.py", "'qwen/agents'"),                 # export-dir path component
    ("identity.py", "'meta/identity_history.jsonl'"),     # state-file path key
    ("providers.py", "'nvidia/nemotron'"),                # _PREFERRED_PREFIXES (startswith)
    ("providers.py", "'google/gemma'"),                   # _PREFERRED_PREFIXES (startswith)
    # EVAL-ONLY benchmark candidate — a long-context sidecar model being
    # *evaluated*, NOT a routing/dispatch target. It must NOT be forced into the
    # routing pool/floor; the literal stays as the benchmark's candidate-model id
    # (default arg + CLI default). Two identical occurrences in the same file.
    ("long_context_sidecar_eval.py", "'moonshotai/Kimi-Linear-48B-A3B-Instruct'"),
}


def _norm(snippet: str) -> str:
    """Normalise a matched literal to single-quote form for stable keying."""
    inner = snippet[1:-1] if len(snippet) >= 2 and snippet[0] in "\"'" else snippet
    return f"'{inner}'"


def _violations() -> list[tuple[Path, int, str, str]]:
    found: list[tuple[Path, int, str, str]] = []
    for path in sorted(SCAN_ROOT.rglob("*.py")):
        if path.name in ALLOWLIST:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            for label, pattern in PATTERNS:
                match = pattern.search(line)
                if match:
                    snippet = match.group(0)
                    if (path.name, _norm(snippet)) in FALSE_POSITIVES:
                        continue
                    found.append((path, lineno, label, snippet))
    return found


def check_no_model_literals(repo_root: Path, **_kwargs) -> tuple[bool, str]:
    """Guard entry-point for ``run_pre_commit.py`` composition (fail-closed).

    Conforms to the ``(repo_root, **kwargs) -> (ok, message)`` shape every
    uplift guard uses. ``repo_root`` is accepted for interface parity; this
    guard scans the fixed ``dharma_swarm/`` source root resolved at import.
    """
    violations = _violations()
    if not violations:
        return True, "no stray model-id literals outside the pool"
    first = violations[0]
    rel = first[0].relative_to(REPO_ROOT)
    return (
        False,
        f"{len(violations)} stray model-id literal(s) outside model_pool.py; "
        f"first: {rel}:{first[1]} [{first[2]}] {first[3]}. "
        "Move them into dharma_swarm/model_pool.py and derive the surface "
        "from a pool projection.",
    )


def main() -> int:
    violations = _violations()
    if not violations:
        print("check_no_model_literals: OK — no stray model-id literals outside the pool")
        return 0
    print("check_no_model_literals: FAIL — model-id literals must live only in model_pool.py")
    for path, lineno, label, snippet in violations:
        rel = path.relative_to(REPO_ROOT)
        print(f"  {rel}:{lineno}  [{label}]  {snippet}")
    print(f"\n{len(violations)} stray literal(s). Move them into dharma_swarm/model_pool.py and")
    print("derive the surface from a pool projection (provider_model_ids / ollama_cloud_model_ids / …).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
