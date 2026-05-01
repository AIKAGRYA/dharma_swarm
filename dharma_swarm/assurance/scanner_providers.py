"""Provider contract scanner."""

from __future__ import annotations

import re
from pathlib import Path

from dharma_swarm.assurance.report_schema import Finding, ScanReport, Severity

PROVIDER_PATTERN = re.compile(r"""ProviderType\.(\w+)""", re.IGNORECASE)
ENUM_VALUE_PATTERN = re.compile(r"""^\s*\w+\s*=\s*["']([^"']+)["']\s*$""")
MODEL_STRING_PATTERN = re.compile(
    r"""(?<![A-Za-z0-9_])["']?model["']?\s*[:=]\s*["']([^"']+)["']"""
)
MODEL_PROVIDER_MAP = {
    "claude-": "anthropic",
    "anthropic/": "anthropic",
    "openai/": "openai",
    "gpt-": "openai",
    "llama-": "openrouter",
    "mistral": "openrouter",
    "deepseek": "openrouter",
    "qwen": "openrouter",
    "gemma": "openrouter",
    "nemotron": "nvidia_nim",
}


def _infer_provider_from_model(model_str: str) -> str | None:
    lower = model_str.lower()
    for prefix, provider in MODEL_PROVIDER_MAP.items():
        if lower.startswith(prefix):
            return provider
    return None


def _provider_matches_model(provider: str, expected: str) -> bool:
    if provider == expected:
        return True
    if {provider, expected}.issubset({"openrouter", "openrouter_free"}):
        return True
    if provider == "codex" and expected == "openai":
        return True
    if provider == "claude_code" and expected == "anthropic":
        return True
    if provider in {"local", "ollama"}:
        return True
    return False


def _pairs_from_lines(
    block_lines: list[tuple[int, str]],
) -> list[tuple[int, str, int, str]]:
    providers: list[tuple[int, str]] = []
    models: list[tuple[int, str]] = []
    for line_no, line in block_lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        for match in PROVIDER_PATTERN.finditer(line):
            providers.append((line_no, match.group(1).lower()))
        for match in MODEL_STRING_PATTERN.finditer(line):
            models.append((line_no, match.group(1)))
    if not providers or not models:
        return []
    return [
        (model_line, model_str, provider_line, provider)
        for provider_line, provider in providers
        for model_line, model_str in models
    ]


def _iter_provider_model_pairs(lines: list[str]) -> list[tuple[int, str, int, str]]:
    pairs: list[tuple[int, str, int, str]] = []
    block: list[tuple[int, str]] = []
    brace_depth = 0

    for line_no, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not block and stripped.startswith("#"):
            continue

        opens = line.count("{")
        closes = line.count("}")
        if block or opens:
            if not block:
                brace_depth = 0
            block.append((line_no, line))
            brace_depth += opens - closes
            if brace_depth <= 0:
                pairs.extend(_pairs_from_lines(block))
                block = []
                brace_depth = 0
            continue

        # Single-line call/config literals without braces.
        pairs.extend(_pairs_from_lines([(line_no, line)]))

    if block:
        pairs.extend(_pairs_from_lines(block))
    return pairs


def _resolve_target_files(
    *,
    repo_root: Path | None = None,
    changed_files: list[str] | None = None,
) -> tuple[Path, list[Path]]:
    root = repo_root or Path(__file__).resolve().parents[2]
    pkg_dir = root / "dharma_swarm"

    def _eligible(candidate: Path) -> bool:
        return (
            candidate.suffix == ".py"
            and "tests" not in candidate.parts
            and "assurance" not in candidate.parts
        )

    if changed_files:
        targets: list[Path] = []
        for raw in changed_files:
            candidate = Path(raw)
            if not candidate.is_absolute():
                candidate = root / candidate
            if _eligible(candidate):
                targets.append(candidate)
        return root, targets
    return root, [path for path in pkg_dir.rglob("*.py") if _eligible(path)]


def _load_known_providers(root: Path) -> set[str]:
    models_path = root / "dharma_swarm" / "models.py"
    if not models_path.exists():
        return {
            "anthropic",
            "openai",
            "openrouter",
            "nvidia_nim",
            "local",
            "claude_code",
            "codex",
            "openrouter_free",
            "ollama",
        }

    providers: set[str] = set()
    in_provider_enum = False
    for line in models_path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if stripped.startswith("class ProviderType("):
            in_provider_enum = True
            continue
        if in_provider_enum and stripped.startswith("class "):
            break
        if not in_provider_enum:
            continue
        match = ENUM_VALUE_PATTERN.match(line)
        if match:
            providers.add(match.group(1).lower())
    return providers


def scan(
    *,
    repo_root: Path | None = None,
    changed_files: list[str] | None = None,
) -> ScanReport:
    report = ScanReport(scanner="provider_contract")
    findings: list[Finding] = []
    fid = 0
    root, target_files = _resolve_target_files(repo_root=repo_root, changed_files=changed_files)
    known_providers = _load_known_providers(root)

    for pyfile in target_files:
        if not pyfile.exists():
            continue
        try:
            lines = pyfile.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue

        providers_in_file: list[tuple[int, str]] = []
        for i, line in enumerate(lines, start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            for match in PROVIDER_PATTERN.finditer(line):
                providers_in_file.append((i, match.group(1).lower()))

        for line_no, model_str, provider_line, provider in _iter_provider_model_pairs(lines):
            expected = _infer_provider_from_model(model_str)
            if expected is None:
                continue
            if _provider_matches_model(provider, expected):
                continue
            fid += 1
            findings.append(Finding(
                id=f"PC-{fid:03d}",
                severity=Severity.HIGH,
                category="provider_model_mismatch",
                file=str(pyfile.relative_to(root)),
                line=line_no,
                description=(
                    f"Model '{model_str}' implies provider '{expected}' "
                    f"but ProviderType.{provider.upper()} declared at line {provider_line}"
                ),
                evidence=lines[line_no - 1].strip(),
                proposed_fix=(
                    f"Change provider to ProviderType.{expected.upper()} or update the model string"
                ),
            ))

        for line_no, provider in providers_in_file:
            if provider not in known_providers:
                fid += 1
                findings.append(Finding(
                    id=f"PC-{fid:03d}",
                    severity=Severity.MEDIUM,
                    category="unknown_provider",
                    file=str(pyfile.relative_to(root)),
                    line=line_no,
                    description=f"Unknown ProviderType '{provider}'",
                    evidence=lines[line_no - 1].strip(),
                    proposed_fix="Add the provider to the enum or fix the typo",
                ))

        for idx, line in enumerate(lines, start=1):
            if "ProviderType.CODEX" not in line:
                continue
            window = "\n".join(lines[idx - 1: min(len(lines), idx + 4)])
            if 'return "codex"' in window:
                continue
            if 'return "anthropic"' not in window:
                continue
            fid += 1
            findings.append(Finding(
                id=f"PC-{fid:03d}",
                severity=Severity.HIGH,
                category="provider_alias_mismatch",
                file=str(pyfile.relative_to(root)),
                line=idx,
                description=(
                    "ProviderType.CODEX resolves to the anthropic provider string, "
                    "so CODEX-labeled agents do not run on a distinct Codex lane"
                ),
                evidence=window.strip(),
                proposed_fix=(
                    "Route ProviderType.CODEX to its own provider string or rename the config "
                    "so labels match runtime behavior"
                ),
            ))
            break

    report.findings = findings
    report.recompute_summary()
    return report
