#!/usr/bin/env python3
"""route_quality_findings.py — turn quality-tool output into governance signal.

Reads the raw output of vulture / radon / bandit / mypy / pyright / fallow
and routes findings into the canonical governance surfaces:

    BROKEN_REGISTER.md       — runtime-affecting issues (security, type errors)
    INTERFACE_MISMATCH_MAP.md — caller/callee signature drift
    ~/.dharma/audit/quality/<date>/  — full evidence (always written)

Discipline: this script PROPOSES; it does NOT mutate authority surfaces. It
writes proposed-row patches to ~/.dharma/audit/quality/<date>/proposals/ which
the user (or a future approval agent) reviews before applying.

Invocation:
    python3 scripts/governance/route_quality_findings.py --tool vulture --input quality-reports/vulture.txt
    python3 scripts/governance/route_quality_findings.py --all  # auto-discover and route all reports/

Generated 2026-05-09 as part of code-quality stack rollout.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dharma_swarm.runtime_state import (
    OperatorAction,
    RuntimeStateStore,
    operator_action_id_for_payload,
)
from dharma_swarm.slop.models import DetectorFamily, SlopFinding, SlopSeverity

QUALITY_REPORTS = REPO_ROOT / "quality-reports"
AUDIT_BASE = Path.home() / ".dharma" / "audit" / "quality"

JsonDict = dict[str, Any]


def today_dir() -> Path:
    """Return ~/.dharma/audit/quality/<YYYY-MM-DD>/ (created if missing)."""
    d = AUDIT_BASE / datetime.now(timezone.utc).strftime("%Y-%m-%d")
    d.mkdir(parents=True, exist_ok=True)
    (d / "proposals").mkdir(exist_ok=True)
    return d


def _json_ready(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {k: _json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_ready(v) for v in value]
    return value


def _severity(value: str | None, default: SlopSeverity = SlopSeverity.LOW) -> str:
    if not value:
        return default.value
    normalized = value.strip().lower()
    aliases = {
        "error": SlopSeverity.HIGH.value,
        "warning": SlopSeverity.MEDIUM.value,
        "notice": SlopSeverity.LOW.value,
        "information": SlopSeverity.INFO.value,
    }
    if normalized in aliases:
        return aliases[normalized]
    if normalized in {s.value for s in SlopSeverity}:
        return normalized
    return default.value


def _confidence(value: float | int | None, default: float = 0.5) -> float:
    if value is None:
        return default
    if value > 1:
        value = value / 100
    return max(0.0, min(1.0, float(value)))


def _make_finding(
    *,
    tool: str,
    detector_family: DetectorFamily,
    issue_type: str,
    path: str,
    line: int | None = None,
    symbol: str | None = None,
    severity: str | SlopSeverity = SlopSeverity.LOW,
    confidence: float = 0.5,
    evidence: str = "",
    suggested_action: str = "review",
    metadata: JsonDict | None = None,
    **legacy: Any,
) -> JsonDict:
    """Create a SlopFinding-valid row while preserving legacy proposal keys."""
    sev = severity.value if isinstance(severity, SlopSeverity) else _severity(severity)
    safe_line = line if isinstance(line, int) and line > 0 else None
    row = SlopFinding(
        tool=tool,
        detector_family=detector_family,
        issue_type=issue_type,
        path=path or "?",
        line=safe_line,
        symbol=symbol,
        severity=SlopSeverity(sev),
        confidence=_confidence(confidence),
        evidence=evidence,
        suggested_action=suggested_action,
        metadata=metadata or {},
    ).model_dump()
    row.update(_json_ready(legacy))
    if "raw" not in row:
        row["raw"] = evidence
    return _json_ready(row)


def _load_json(text: str) -> Any | None:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _line_from_range(value: Any) -> int | None:
    if isinstance(value, dict):
        start = value.get("start") or value.get("startLine") or value.get("start_line")
        if isinstance(start, dict):
            start = start.get("line")
        if isinstance(start, int):
            return start
        if isinstance(value.get("line"), int):
            return value["line"]
    return None


def parse_vulture(text: str) -> list[JsonDict]:
    """Vulture format: 'path:line: unused <kind> '<name>' (<confidence>%)'."""
    out: list[dict] = []
    for line in text.splitlines():
        if ":" not in line or "unused" not in line:
            continue
        try:
            path_line, rest = line.split(": unused ", 1)
            path, lineno = path_line.rsplit(":", 1)
            kind = rest.split(" ")[0]
            confidence = (
                int(rest.split("(")[-1].split("%")[0]) if "(" in rest else 0
            )
            out.append(
                {
                    **_make_finding(
                        tool="vulture",
                        detector_family=DetectorFamily.DEAD_CODE,
                        issue_type=f"unused_{kind}",
                        path=path,
                        line=int(lineno),
                        severity=SlopSeverity.LOW,
                        confidence=confidence,
                        evidence=line,
                        kind=kind,
                        raw=line,
                    ),
                    "confidence_percent": confidence,
                },
            )
        except (ValueError, IndexError):
            continue
    return out


def parse_radon_cc(text: str) -> list[JsonDict]:
    """Radon CC: 'path\n    L F line_no:col func_name - <grade>'."""
    out: list[dict] = []
    cur_path = ""
    for line in text.splitlines():
        if line and not line.startswith(" ") and ".py" in line:
            cur_path = line.strip()
            continue
        s = line.strip()
        if not s or len(s) < 5:
            continue
        # Format: "L F 123:0 func_name - C"
        parts = s.split()
        if len(parts) >= 5 and "-" in parts:
            try:
                line_col = next(part for part in parts if re.match(r"^\d+:\d+$", part))
                lineno = int(line_col.split(":")[0])
                grade = parts[-1]
                if grade in ("C", "D", "E", "F"):
                    out.append(
                        {
                            **_make_finding(
                                tool="radon-cc",
                                detector_family=DetectorFamily.COMPLEXITY,
                                issue_type="complexity",
                                path=cur_path,
                                line=lineno,
                                severity=(
                                    SlopSeverity.HIGH
                                    if grade in {"E", "F"}
                                    else SlopSeverity.MEDIUM
                                ),
                                confidence={"C": 0.55, "D": 0.65, "E": 0.80, "F": 0.90}[
                                    grade
                                ],
                                evidence=s,
                                kind="complexity",
                                raw=s,
                                grade=grade,
                            ),
                        },
                    )
            except (ValueError, IndexError, StopIteration):
                continue
    return out


def parse_bandit(text: str) -> list[JsonDict]:
    """Bandit txt: '>> Issue: [B###] ... Severity: ... Location: path:line'."""
    out: list[dict] = []
    cur: dict = {}
    for line in text.splitlines():
        ls = line.strip()
        if ls.startswith(">> Issue:"):
            cur = {"tool": "bandit", "raw": ls}
        elif ls.startswith("Severity:") and cur:
            cur["severity"] = ls.split(":", 1)[1].strip().split(" ")[0]
        elif ls.startswith("Location:") and cur:
            try:
                loc = ls.split(":", 1)[1].strip()
                path, lineno = loc.rsplit(":", 1)
                cur["path"] = path
                cur["line"] = int(lineno)
                severity = str(cur.get("severity", "LOW"))
                out.append(
                    _make_finding(
                        tool="bandit",
                        detector_family=DetectorFamily.SECURITY,
                        issue_type="security_issue",
                        path=path,
                        line=int(lineno),
                        severity=severity,
                        confidence={
                            "LOW": 0.45,
                            "MEDIUM": 0.70,
                            "HIGH": 0.90,
                        }.get(severity.upper(), 0.55),
                        evidence=str(cur.get("raw", "")),
                        metadata={"bandit": {"severity": severity}},
                        raw=cur.get("raw", ""),
                    )
                )
                cur = {}
            except (ValueError, IndexError):
                cur = {}
    return out


def parse_mypy(text: str) -> list[JsonDict]:
    """Parse mypy text lines like 'path:line: error: message [code]'."""
    out: list[JsonDict] = []
    pattern = re.compile(
        r"^(?P<path>.+?):(?P<line>\d+)(?::\d+)?: (?P<level>error|note|warning): "
        r"(?P<message>.*?)(?:\s+\[(?P<code>[^\]]+)\])?$"
    )
    for line in text.splitlines():
        match = pattern.match(line.strip())
        if not match or match.group("level") == "note":
            continue
        code = match.group("code") or match.group("level")
        out.append(
            _make_finding(
                tool="mypy",
                detector_family=DetectorFamily.TYPE_SAFETY,
                issue_type=code.replace("-", "_"),
                path=match.group("path"),
                line=int(match.group("line")),
                severity=(
                    SlopSeverity.HIGH
                    if match.group("level") == "error"
                    else SlopSeverity.MEDIUM
                ),
                confidence=0.85,
                evidence=line,
                metadata={"mypy": {"code": code, "level": match.group("level")}},
                raw=line,
            )
        )
    return out


def parse_pyright_json(text: str) -> list[JsonDict]:
    """Parse pyright --outputjson diagnostics."""
    data = _load_json(text)
    diagnostics = data.get("generalDiagnostics") if isinstance(data, dict) else None
    if not isinstance(diagnostics, list):
        return []
    out: list[JsonDict] = []
    for item in diagnostics:
        if not isinstance(item, dict):
            continue
        severity = _severity(item.get("severity"), SlopSeverity.MEDIUM)
        rule = str(item.get("rule") or item.get("category") or "type_diagnostic")
        message = str(item.get("message") or "")
        out.append(
            _make_finding(
                tool="pyright",
                detector_family=DetectorFamily.TYPE_SAFETY,
                issue_type=rule.replace("-", "_"),
                path=str(item.get("file") or "?"),
                line=_line_from_range(item.get("range")),
                severity=severity,
                confidence=0.90 if severity in {"error", "high"} else 0.70,
                evidence=message,
                metadata={"pyright": item},
                raw=message,
            )
        )
    return out


def parse_fallow(text: str) -> list[JsonDict]:
    """Parse fallow JSON when present, with a guarded text fallback.

    Fallow output formats are less stable across wrappers, so this accepts common
    keys only and stores the original item in metadata for reviewer audit.
    """
    data = _load_json(text)
    items: list[Any]
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        raw_items = data.get("findings") or data.get("issues") or data.get("results")
        items = raw_items if isinstance(raw_items, list) else []
    else:
        items = []
    out: list[JsonDict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or item.get("file") or "?")
        line = item.get("line") if isinstance(item.get("line"), int) else None
        message = str(item.get("message") or item.get("reason") or item)
        out.append(
            _make_finding(
                tool="fallow",
                detector_family=DetectorFamily.DEAD_CODE,
                issue_type=str(item.get("type") or "unused_code"),
                path=path,
                line=line,
                severity=SlopSeverity.LOW,
                confidence=0.65,
                evidence=message,
                metadata={"fallow": item},
                raw=message,
            )
        )
    if out:
        return out

    pattern = re.compile(r"^(?P<path>[^:\s]+\.py):(?P<line>\d+):?\s+(?P<msg>.+)$")
    for line in text.splitlines():
        match = pattern.match(line.strip())
        if not match:
            continue
        out.append(
            _make_finding(
                tool="fallow",
                detector_family=DetectorFamily.DEAD_CODE,
                issue_type="unused_code",
                path=match.group("path"),
                line=int(match.group("line")),
                severity=SlopSeverity.LOW,
                confidence=0.55,
                evidence=match.group("msg"),
                raw=line,
            )
        )
    return out


def parse_coverage(text: str) -> list[JsonDict]:
    """Parse coverage text summary and Cobertura-like XML package/class rows."""
    out: list[JsonDict] = []
    text_pattern = re.compile(
        r"^(?P<path>\S+\.py)\s+\d+\s+\d+\s+(?:\d+\s+)?(?P<cover>\d+(?:\.\d+)?)%"
    )
    for line in text.splitlines():
        match = text_pattern.match(line.strip())
        if not match or match.group("path") == "TOTAL":
            continue
        coverage = float(match.group("cover"))
        if coverage >= 80:
            continue
        out.append(
            _make_finding(
                tool="coverage",
                detector_family=DetectorFamily.COVERAGE,
                issue_type="low_coverage",
                path=match.group("path"),
                severity=SlopSeverity.MEDIUM if coverage < 60 else SlopSeverity.LOW,
                confidence=(100 - coverage) / 100,
                evidence=line.strip(),
                metadata={"coverage_percent": coverage},
                raw=line.strip(),
            )
        )
    if out or "<coverage" not in text:
        return out

    # XML parsing is intentionally regex-scoped to summary rows; detailed missed
    # line expansion belongs in the coverage tool, not this router.
    for match in re.finditer(
        r'<class[^>]*filename="(?P<path>[^"]+)"[^>]*line-rate="(?P<rate>[0-9.]+)"',
        text,
    ):
        coverage = float(match.group("rate")) * 100
        if coverage >= 80:
            continue
        out.append(
            _make_finding(
                tool="coverage",
                detector_family=DetectorFamily.COVERAGE,
                issue_type="low_coverage",
                path=match.group("path"),
                severity=SlopSeverity.MEDIUM if coverage < 60 else SlopSeverity.LOW,
                confidence=(100 - coverage) / 100,
                evidence=f"{match.group('path')} coverage {coverage:.1f}%",
                metadata={"coverage_percent": coverage},
            )
        )
    return out


def parse_deptry(text: str) -> list[JsonDict]:
    """Parse deptry JSON or text lines containing DEP00x dependency findings."""
    data = _load_json(text)
    out: list[JsonDict] = []
    items: list[Any] = []
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        raw_items = data.get("findings") or data.get("issues") or data.get("results")
        items = raw_items if isinstance(raw_items, list) else []
    for item in items:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code") or item.get("error_code") or "dependency_issue")
        message = str(item.get("message") or item)
        out.append(
            _make_finding(
                tool="deptry",
                detector_family=DetectorFamily.DEPENDENCY,
                issue_type=code.lower(),
                path=str(item.get("path") or item.get("file") or "pyproject.toml"),
                line=item.get("line") if isinstance(item.get("line"), int) else None,
                severity=SlopSeverity.MEDIUM,
                confidence=0.75,
                evidence=message,
                metadata={"deptry": item},
                raw=message,
            )
        )
    if out:
        return out

    pattern = re.compile(r"^(?:(?P<path>[^:\s]+):(?P<line>\d+):?\s+)?(?P<code>DEP\d+)\s+(?P<msg>.+)$")
    for line in text.splitlines():
        match = pattern.match(line.strip())
        if not match:
            continue
        out.append(
            _make_finding(
                tool="deptry",
                detector_family=DetectorFamily.DEPENDENCY,
                issue_type=match.group("code").lower(),
                path=match.group("path") or "pyproject.toml",
                line=int(match.group("line")) if match.group("line") else None,
                severity=SlopSeverity.MEDIUM,
                confidence=0.75,
                evidence=match.group("msg"),
                raw=line,
            )
        )
    return out


def parse_import_structure(text: str, tool: str = "import-linter") -> list[JsonDict]:
    """Parse import-linter/Tach/Grimp text or JSON violation summaries."""
    data = _load_json(text)
    out: list[JsonDict] = []
    items: list[Any] = []
    if isinstance(data, dict):
        raw_items = data.get("violations") or data.get("findings") or data.get("errors")
        items = raw_items if isinstance(raw_items, list) else []
    elif isinstance(data, list):
        items = data
    for item in items:
        if not isinstance(item, dict):
            continue
        importer = str(item.get("importer") or item.get("source") or item.get("module") or "?")
        message = str(item.get("message") or item)
        out.append(
            _make_finding(
                tool=tool,
                detector_family=DetectorFamily.STRUCTURE,
                issue_type=str(item.get("type") or "import_violation"),
                path=importer.replace(".", "/") + ".py" if "." in importer else importer,
                severity=SlopSeverity.MEDIUM,
                confidence=0.75,
                evidence=message,
                metadata={tool: item},
                raw=message,
            )
        )
    if out:
        return out

    pattern = re.compile(r"(?P<path>[\w./-]+\.py|[\w.]+)\s*[:\-]\s*(?P<msg>.*(?:violation|forbidden|contract|import).*)", re.I)
    for line in text.splitlines():
        match = pattern.search(line.strip())
        if not match:
            continue
        path = match.group("path")
        if ".py" not in path and "." in path:
            path = path.replace(".", "/") + ".py"
        out.append(
            _make_finding(
                tool=tool,
                detector_family=DetectorFamily.STRUCTURE,
                issue_type="import_violation",
                path=path,
                severity=SlopSeverity.MEDIUM,
                confidence=0.60,
                evidence=match.group("msg"),
                raw=line,
            )
        )
    return out


def parse_semgrep_json(text: str) -> list[JsonDict]:
    """Parse semgrep --json result rows."""
    data = _load_json(text)
    results = data.get("results") if isinstance(data, dict) else None
    if not isinstance(results, list):
        return []
    out: list[JsonDict] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        raw_extra = item.get("extra")
        extra: JsonDict = raw_extra if isinstance(raw_extra, dict) else {}
        raw_metadata = extra.get("metadata")
        metadata: JsonDict = raw_metadata if isinstance(raw_metadata, dict) else {}
        severity = _severity(extra.get("severity"), SlopSeverity.MEDIUM)
        category = str(metadata.get("category") or metadata.get("technology") or "")
        family = (
            DetectorFamily.SECURITY
            if "security" in category.lower() or severity in {"error", "high", "critical"}
            else DetectorFamily.SEMANTIC
        )
        check_id = str(item.get("check_id") or "semgrep_rule")
        out.append(
            _make_finding(
                tool="semgrep",
                detector_family=family,
                issue_type=check_id.replace(".", "_").replace("-", "_"),
                path=str(item.get("path") or "?"),
                line=_line_from_range(item.get("start")) or item.get("line"),
                severity=severity,
                confidence=0.80,
                evidence=str(extra.get("message") or check_id),
                metadata={"semgrep": item},
                raw=str(extra.get("message") or check_id),
            )
        )
    return out


def finding_key(finding: JsonDict) -> str:
    parts = [
        str(finding.get("tool") or ""),
        str(finding.get("issue_type") or finding.get("kind") or ""),
        str(finding.get("path") or ""),
        str(finding.get("line") or ""),
        str(finding.get("symbol") or ""),
        str(finding.get("metadata", {}).get("code") or ""),
        str(finding.get("raw") or finding.get("evidence") or ""),
    ]
    return hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()[:24]


def annotate_keys(findings: list[JsonDict]) -> list[JsonDict]:
    for finding in findings:
        metadata = finding.setdefault("metadata", {})
        if isinstance(metadata, dict):
            metadata.setdefault("stable_key", finding_key(finding))
    return findings


def load_finding_keys(path: Path) -> set[str]:
    if not path.exists():
        return set()
    keys: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            keys.add(str(row.get("metadata", {}).get("stable_key") or finding_key(row)))
    return keys


def previous_findings_files(out_dir: Path) -> list[Path]:
    candidates = sorted(AUDIT_BASE.glob("*/findings.jsonl"), reverse=True)
    current = out_dir / "findings.jsonl"
    existing_current = [current] if current.exists() else []
    return existing_current + [path for path in candidates if path != current]


def dedupe_since_last_run(findings: list[JsonDict], out_dir: Path) -> list[JsonDict]:
    seen: set[str] = set()
    for path in previous_findings_files(out_dir):
        seen.update(load_finding_keys(path))
        if seen:
            break
    if not seen:
        return findings
    return [
        finding
        for finding in findings
        if str(finding.get("metadata", {}).get("stable_key") or finding_key(finding))
        not in seen
    ]


def write_findings_jsonl(path: Path, findings: list[JsonDict], *, append: bool) -> None:
    payload = "\n".join(json.dumps(f, sort_keys=True) for f in findings)
    if payload:
        payload += "\n"
    if append and path.exists():
        with path.open("a", encoding="utf-8") as handle:
            handle.write(payload)
    else:
        path.write_text(payload, encoding="utf-8")


def proposal_for_br(findings: list[JsonDict]) -> str:
    """Generate a proposed BROKEN_REGISTER.md row for high-severity findings.

    Only emits proposals for findings that look runtime-affecting (bandit
    high/medium severity, radon F-grade complexity, vulture confidence ≥ 90).
    """
    high = [
        f
        for f in findings
        if (
            f.get("tool") == "bandit"
            and str(f.get("severity", "")).upper() in {"HIGH", "MEDIUM"}
        )
        or (f.get("tool") == "radon-cc" and f.get("grade") in {"E", "F"})
        or (
            f.get("tool") == "vulture"
            and (f.get("confidence_percent", 0) or f.get("confidence", 0)) >= 90
        )
        or (
            f.get("tool") in {"mypy", "pyright", "semgrep"}
            and str(f.get("severity", "")).lower() in {"high", "critical"}
        )
    ]
    if not high:
        return ""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines = [f"# Proposed BR rows from quality scan {today}\n"]
    for i, f in enumerate(high[:20], 1):  # cap at 20 to keep proposal sane
        br_id = f"BR-Q{today.replace('-', '')[-4:]}-{i:02d}"
        kind = f.get("tool", "?")
        lines.append(
            f"### {br_id} — {kind} flag at `{f.get('path', '?')}:{f.get('line', '?')}`\n"
        )
        lines.append(f"- **first_observed:** {today}")
        lines.append(f"- **source:** quality-stack ({kind})")
        lines.append(f"- **evidence:** `{f.get('raw', '')[:120]}`")
        lines.append(f"- **status:** PROPOSED — reviewer must triage")
        lines.append("")
    return "\n".join(lines)


def record_broken_register_triage_actions(
    proposals_path: Path,
    *,
    runtime_db_path: Path | None = None,
    actor: str = "operator",
) -> int:
    """Record reviewed BROKEN_REGISTER proposal rows in runtime operator_actions."""
    if not proposals_path.exists():
        return 0
    runtime = RuntimeStateStore(runtime_db_path)
    current: JsonDict = {}
    count = 0
    for raw in proposals_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        header = re.match(r"^###\s+(?P<br_id>BR-[^ ]+)\s+—\s+(?P<title>.+)$", raw)
        if header:
            current = {
                "br_id": header.group("br_id").strip(),
                "title": header.group("title").strip(),
            }
            continue
        status_line = re.match(
            r"^-\s+\*\*status:\*\*\s+(?P<status>[A-Za-z_ -]+?)(?:\s+—\s+(?P<reason>.*))?$",
            raw,
        )
        if not status_line or not current:
            continue
        status = status_line.group("status").strip().lower().replace(" ", "_")
        if status == "proposed":
            continue
        reason = (status_line.group("reason") or "").strip()
        action_name = f"broken_register_proposal_{status}"
        payload = {
            **current,
            "status": status,
            "proposals_path": str(proposals_path),
        }
        action = OperatorAction(
            action_id=operator_action_id_for_payload(
                action_name=action_name,
                actor=actor,
                reason=reason,
                payload=payload,
            ),
            action_name=action_name,
            actor=actor,
            reason=reason,
            payload=payload,
        )
        runtime.record_operator_action_sync(action)
        count += 1
    return count


def main() -> int:
    p = argparse.ArgumentParser()
    parser_by_tool = {
        "vulture": parse_vulture,
        "radon-cc": parse_radon_cc,
        "bandit": parse_bandit,
        "mypy": parse_mypy,
        "pyright": parse_pyright_json,
        "fallow": parse_fallow,
        "coverage": parse_coverage,
        "deptry": parse_deptry,
        "import-linter": lambda text: parse_import_structure(text, "import-linter"),
        "tach": lambda text: parse_import_structure(text, "tach"),
        "grimp": lambda text: parse_import_structure(text, "grimp"),
        "semgrep": parse_semgrep_json,
    }
    p.add_argument("--tool", choices=sorted(parser_by_tool))
    p.add_argument("--input", type=Path)
    p.add_argument("--all", action="store_true")
    p.add_argument(
        "--since-last-run",
        action="store_true",
        help="only emit findings whose stable key was absent from the previous findings.jsonl",
    )
    p.add_argument(
        "--record-triage-actions",
        action="store_true",
        help="record reviewed broken_register_proposals.md rows into runtime operator_actions",
    )
    p.add_argument(
        "--runtime-db",
        type=Path,
        default=None,
        help="runtime.db path for --record-triage-actions",
    )
    p.add_argument(
        "--operator-id",
        default="operator",
        help="actor name for recorded triage actions",
    )
    args = p.parse_args()

    out_dir = today_dir()
    findings: list[JsonDict] = []

    parsers = {
        "vulture.txt": ("vulture", parse_vulture),
        "radon-cc.txt": ("radon-cc", parse_radon_cc),
        "bandit.txt": ("bandit", parse_bandit),
        "mypy.txt": ("mypy", parse_mypy),
        "pyright.json": ("pyright", parse_pyright_json),
        "fallow.json": ("fallow", parse_fallow),
        "fallow.txt": ("fallow", parse_fallow),
        "coverage.txt": ("coverage", parse_coverage),
        "coverage.xml": ("coverage", parse_coverage),
        "deptry.json": ("deptry", parse_deptry),
        "deptry.txt": ("deptry", parse_deptry),
        "import-linter.txt": (
            "import-linter",
            lambda text: parse_import_structure(text, "import-linter"),
        ),
        "tach.txt": ("tach", lambda text: parse_import_structure(text, "tach")),
        "grimp.txt": ("grimp", lambda text: parse_import_structure(text, "grimp")),
        "semgrep.json": ("semgrep", parse_semgrep_json),
    }

    if args.all:
        for name, (tool, parser) in parsers.items():
            f = QUALITY_REPORTS / name
            if f.exists():
                findings.extend(parser(f.read_text(encoding="utf-8")))
    elif args.tool and args.input:
        text = args.input.read_text(encoding="utf-8") if args.input.exists() else ""
        findings = parser_by_tool[args.tool](text)
    else:
        print("usage: --all OR --tool <name> --input <path>", file=sys.stderr)
        return 2

    annotate_keys(findings)
    if args.since_last_run:
        findings = dedupe_since_last_run(findings, out_dir)

    # Always write structured findings (evidence). Incremental runs append only
    # new rows so hourly loop closure does not erase the daily ledger.
    write_findings_jsonl(
        out_dir / "findings.jsonl",
        findings,
        append=args.since_last_run,
    )

    # Write proposed BR rows for the high-severity subset
    proposal = proposal_for_br(findings)
    if proposal:
        (out_dir / "proposals" / "broken_register_proposals.md").write_text(proposal)
    if args.record_triage_actions:
        record_broken_register_triage_actions(
            out_dir / "proposals" / "broken_register_proposals.md",
            runtime_db_path=args.runtime_db,
            actor=args.operator_id,
        )

    print(f"Routed {len(findings)} findings → {out_dir}")
    print(
        f"  proposals → {out_dir}/proposals/broken_register_proposals.md"
        if proposal
        else "  no high-severity findings to propose"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
