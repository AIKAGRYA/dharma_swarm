#!/usr/bin/env python3
"""NAGA-IR repo-grounding and cross-file consistency checker.

All repo object facts are checked through git against origin/main, not through
the working tree. The checker also enforces the mechanical consistency
relations among core.md, receipt_wire.md, and witness_mesh.md.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable, NamedTuple


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SPEC_DIR = REPO_ROOT / "specs" / "naga_ir"
EXIT_CLEAN = 0
EXIT_VIOLATED = 1
EXIT_BROKEN = 2

EXPECTED_RECEIPT_FIELDS = {
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
    "clock",
    "prev_receipt_hash",
    "signatures",
}
EXPECTED_AUTHORITY_KEY = ["subject_id", "claim_hash", "trust_base_id", "fragment_id", "fragment_version"]
EXPECTED_CLAIM_HASH = ["claim_id", "claim_class", "claim_strength", "statement", "scope", "fragment_id", "obligation_hash"]
EXPECTED_MODALITIES = {"Proven_by", "Tested_by", "Witnessed_by", "Challenged_by", "Attested_by"}
EXPECTED_CHALLENGE_STATES = {"open", "refuted", "accepted", "expired"}
EXPECTED_FAILURE_STATES = {
    "invalid_schema",
    "signature_failed",
    "ttl_stale",
    "clock_skew_unknown",
    "challenge_unresolved",
    "trust_base_mismatch",
}
EXPECTED_CANONICAL_CONJUNCTS = {
    "schema_valid",
    "signatures_valid",
    "ttl_live",
    "clock_within_skew",
    "no_unresolved_challenge",
    "authority_matches",
}

PATH_RE = re.compile(r"`?((?:scripts|dharma_swarm|docs|packages|specs)/[A-Za-z0-9_./-]+|titanium-verify)`?")
FUTURE_MARKERS = (
    "future",
    "planned",
    "later pr",
    "later ",
    "target",
    "absent",
    "missing",
    "does not contain",
    "does not currently contain",
    "not implemented",
)
PRESENT_MARKERS = ("exists", "contains", "emits", "exports", "implements", "provides", "current", "today", "already", "on main")
ABSENCE_MARKERS = ("does not contain", "does not currently contain", "does not exist", "absent", "missing", "not present", "no ")
ABSENT_OBJECTS = ("packages/telos-kernel/", "titanium-verify", "dharma_swarm/reconciler.py", "dharma_swarm/sab/")


class BrokenCheck(RuntimeError):
    pass


class Finding(NamedTuple):
    path: Path
    line: int
    code: str
    detail: str

    def render(self, root: Path) -> str:
        try:
            loc = self.path.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            loc = str(self.path)
        return f"{loc}:{self.line}:{self.code}: {self.detail}"


class GitResult(NamedTuple):
    returncode: int
    stdout: str
    stderr: str


def run_git(args: list[str], repo_root: Path) -> GitResult:
    result = subprocess.run(args, cwd=repo_root, check=False, capture_output=True, text=True)
    return GitResult(result.returncode, result.stdout, result.stderr)


def spec_paths(inputs: Iterable[Path]) -> list[Path]:
    paths: list[Path] = []
    for item in inputs:
        item = item.resolve()
        if item.is_dir():
            paths.extend(sorted(item.glob("*.md")))
        else:
            paths.append(item)
    if not paths:
        paths = sorted(DEFAULT_SPEC_DIR.glob("*.md"))
    if not paths:
        raise BrokenCheck(f"no markdown files found under {DEFAULT_SPEC_DIR}")
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise BrokenCheck(f"missing markdown file(s): {', '.join(missing)}")
    return paths


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise BrokenCheck(f"cannot read {path}: {exc}") from exc


def git_show(repo_root: Path, git_ref: str, path: str) -> str | None:
    result = run_git(["git", "show", f"{git_ref}:{path.strip('/')}"], repo_root)
    return result.stdout if result.returncode == 0 else None


def git_exists(repo_root: Path, git_ref: str, path: str) -> bool:
    clean = path.strip("/")
    if git_show(repo_root, git_ref, clean) is not None:
        return True
    result = run_git(["git", "ls-tree", git_ref, clean], repo_root)
    return result.returncode == 0 and bool(result.stdout.strip())


def line_context(line: str, token: str, radius: int = 90) -> str:
    lower = line.lower()
    idx = lower.find(token.lower())
    if idx < 0:
        return lower
    return lower[max(0, idx - radius): idx + len(token) + radius]


def has_marker(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def normalize_field(field: str) -> str:
    field = field.strip("` []").strip()
    field = field.replace("[]", "")
    field = field.replace("normalized ", "")
    field = field.replace("fragment id", "fragment_id")
    field = field.replace("obligation hash", "obligation_hash")
    field = field.replace("statement", "statement")
    field = field.replace(" ", "_")
    return field


def line_of(text: str, needle: str) -> int:
    idx = text.find(needle)
    return 1 if idx < 0 else text[:idx].count("\n") + 1


def paragraphs(text: str) -> list[str]:
    chunks: list[str] = []
    buf: list[str] = []
    in_fence = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if not stripped or stripped.startswith("#"):
            if buf:
                chunks.append(" ".join(buf))
                buf = []
            continue
        buf.append(stripped)
    if buf:
        chunks.append(" ".join(buf))
    return chunks


def check_repo_line(path: Path, line_no: int, line: str, repo_root: Path, git_ref: str) -> list[Finding]:
    findings: list[Finding] = []
    seen_paths: set[str] = set()
    for match in PATH_RE.finditer(line):
        prefix = line[: match.start()]
        last_break = max(prefix.rfind(" "), prefix.rfind("("), prefix.rfind("["))
        if "://" in prefix[last_break + 1 :]:
            continue
        repo_path = match.group(1)
        if repo_path in seen_paths:
            continue
        seen_paths.add(repo_path)
        context = line_context(line, repo_path)
        if repo_path == "dharma_swarm/sab_client.py":
            findings.append(Finding(path, line_no, "sab_client_path", "use dharma_swarm/connectors/sab_client.py"))
            continue
        if repo_path in ABSENT_OBJECTS or any(repo_path.startswith(obj) for obj in ABSENT_OBJECTS if obj.endswith("/")):
            if has_marker(context, PRESENT_MARKERS) and not has_marker(context, FUTURE_MARKERS) and not has_marker(context, ABSENCE_MARKERS):
                findings.append(Finding(path, line_no, "absent_object_present", f"{repo_path} is absent on origin/main"))
            continue
        before = line.lower()[: match.start()]
        before_context = before[max(0, len(before) - 70):]
        if repo_path == "scripts/governance/assurance_boundary.py" and has_marker(before_context, ABSENCE_MARKERS):
            findings.append(Finding(path, line_no, "assurance_boundary_exists", "assurance_boundary.py exists on origin/main"))
            continue
        if repo_path.startswith(("scripts/", "dharma_swarm/", "docs/", "packages/")):
            if not has_marker(context, FUTURE_MARKERS) and not git_exists(repo_root, git_ref, repo_path):
                findings.append(Finding(path, line_no, "repo_path_missing", f"{repo_path} does not resolve on {git_ref}"))
    if "Bisimilar(" in line or "Bisimilar()" in line:
        findings.append(Finding(path, line_no, "bisimilar_lowercase", "coalgebra.py exposes lowercase bisimilar(...)"))
    lower = line.lower()
    if "sab_client.py" in lower and "receipt" in lower and "future" not in lower and "not" not in lower and "packet" not in lower:
        findings.append(Finding(path, line_no, "sab_receipts_today", "sab_client.py exports SABContribution packets, not receipts"))
    return findings


def check_origin_facts(paths: list[Path], repo_root: Path, git_ref: str) -> list[Finding]:
    first = paths[0]
    findings: list[Finding] = []
    assurance = git_show(repo_root, git_ref, "scripts/governance/assurance_boundary.py")
    if assurance is None:
        findings.append(Finding(first, 1, "origin_fact_missing", "assurance_boundary.py missing on origin/main"))
    elif not all(token in assurance for token in ("assurance_boundary_report.v1", "AB-01", "AB-05", "EXIT_HOLDS", "EXIT_VIOLATED", "EXIT_BROKEN")):
        findings.append(Finding(first, 1, "assurance_boundary_properties", "origin/main assurance boundary lacks expected schema, contracts, or exits"))
    coalgebra = git_show(repo_root, git_ref, "dharma_swarm/coalgebra.py")
    if coalgebra is None or "def bisimilar" not in coalgebra:
        findings.append(Finding(first, 1, "coalgebra_bisimilar_origin", "origin/main coalgebra.py must expose def bisimilar"))
    sab = git_show(repo_root, git_ref, "dharma_swarm/connectors/sab_client.py")
    if sab is None:
        findings.append(Finding(first, 1, "sab_client_origin", "origin/main must contain dharma_swarm/connectors/sab_client.py"))
    return findings


def table_fields_after(text: str, heading: str) -> list[str]:
    lines = text.splitlines()
    start = next((idx for idx, line in enumerate(lines) if line.strip().lower() == heading.lower()), None)
    if start is None:
        return []
    fields: list[str] = []
    for line in lines[start + 1 :]:
        if line.startswith("## "):
            break
        match = re.match(r"\|\s*`([^`]+)`\s*\|", line)
        if match:
            fields.append(normalize_field(match.group(1)))
    return fields


def core_receipt_fields(text: str) -> set[str]:
    for para in paragraphs(text):
        lower = para.lower()
        if "wire object" in lower and "carr" in lower:
            return {normalize_field(item) for item in re.findall(r"`([^`]+)`", para)} & EXPECTED_RECEIPT_FIELDS
    return set()


def authority_key_fields(text: str) -> list[str] | None:
    for match in re.finditer(r"(?:authority_key|AuthorityKey)[\s\S]{0,300}?\{([^}]+)\}", text):
        fields = [normalize_field(part) for part in match.group(1).split(",")]
        if set(EXPECTED_AUTHORITY_KEY).issubset(fields):
            return fields
    return None


def claim_hash_fields(text: str) -> list[str] | None:
    for para in paragraphs(text):
        if "claim_hash" not in para:
            continue
        lower = para.lower()
        if "claim_id" not in lower or "obligation" not in lower:
            continue
        fields: list[str] = []
        for token in ("claim_id", "claim_class", "claim_strength", "statement", "scope", "fragment_id", "obligation_hash"):
            if token == "statement" and re.search(r"(?<![a-z_])statement(?![a-z_])", lower):
                fields.append(token)
            elif token == "scope" and re.search(r"(?<![a-z_])scope(?![a-z_])", lower):
                fields.append(token)
            elif token == "fragment_id" and ("fragment_id" in lower or "fragment id" in lower):
                fields.append(token)
            elif token == "obligation_hash" and ("obligation_hash" in lower or "obligation hash" in lower):
                fields.append(token)
            elif token not in {"statement", "scope", "fragment_id", "obligation_hash"} and token in lower:
                fields.append(token)
        return fields
    return None


def backtick_set_near(text: str, phrase: str) -> set[str]:
    for para in paragraphs(text):
        if phrase.lower() in para.lower():
            return set(re.findall(r"`([^`]+)`", para))
    return set()


def challenge_state_set(text: str, phrase: str) -> set[str]:
    known_extra_states = {"withdrawn", "closed", "reopened"}
    raw = {item.lower() for item in backtick_set_near(text, phrase)}
    return {item for item in raw if item in EXPECTED_CHALLENGE_STATES or item in known_extra_states}


def check_cross_file(docs: dict[str, tuple[Path, str]]) -> list[Finding]:
    if not {"core.md", "receipt_wire.md", "witness_mesh.md"}.issubset(docs):
        return []
    core_path, core = docs["core.md"]
    wire_path, wire = docs["receipt_wire.md"]
    witness_path, witness = docs["witness_mesh.md"]
    findings: list[Finding] = []
    core_fields = core_receipt_fields(core)
    wire_fields = set(table_fields_after(wire, "## Receipt object"))
    if core_fields != EXPECTED_RECEIPT_FIELDS or wire_fields != EXPECTED_RECEIPT_FIELDS:
        findings.append(Finding(core_path, line_of(core, "wire object"), "receipt_fields", "core and wire receipt field sets must both be the 15 required fields"))
    for path, text in ((core_path, core), (wire_path, wire), (witness_path, witness)):
        fields = authority_key_fields(text)
        if fields != EXPECTED_AUTHORITY_KEY:
            findings.append(Finding(path, line_of(text, "authority_key"), "authority_key_derivation", "authority_key field list must match across all files"))
    for path, text in ((core_path, core), (wire_path, wire)):
        fields = claim_hash_fields(text)
        if fields != EXPECTED_CLAIM_HASH:
            findings.append(Finding(path, line_of(text, "claim_hash"), "claim_hash_derivation", "claim_hash field list must match across core and wire"))
    for modality in EXPECTED_MODALITIES:
        if modality not in core or modality not in wire:
            findings.append(Finding(core_path, line_of(core, "Evidence modalities"), "evidence_modalities", "core and wire modality sets must match"))
            break
    witnessed_fields = set(table_fields_after(wire, "## Witnessed_by"))
    needed_witness = {"runtime_id", "identity", "observed_value_hash", "replay_hash", "ttl_expires_at"}
    if not needed_witness.issubset(witnessed_fields):
        findings.append(Finding(wire_path, line_of(wire, "Witnessed_by"), "witnessed_by_body_table", "Witnessed_by body field table is missing or incomplete"))
    if "canonical?(" not in core or "canonical_mesh_projection?" not in witness or "canonical?(" not in witness:
        findings.append(Finding(witness_path, line_of(witness, "canonical_mesh_projection"), "canonical_predicate", "mesh predicate must defer to core canonical?"))
    if not EXPECTED_CANONICAL_CONJUNCTS.issubset(set(re.findall(r"\b[a-z_]+\b", core))):
        findings.append(Finding(core_path, line_of(core, "canonical?"), "failure_states_bijection", "core canonical? must expose the six failure-state conjuncts"))
    witness_failures = set(re.findall(r"`([^`]+)`", witness[witness.find("## Failure states") :]))
    if witness_failures & EXPECTED_FAILURE_STATES != EXPECTED_FAILURE_STATES:
        findings.append(Finding(witness_path, line_of(witness, "Failure states"), "failure_states_bijection", "witness failure states must be the six canonical negations"))
    wire_states = challenge_state_set(wire, "resolution state")
    witness_states = challenge_state_set(witness, "Resolution states")
    if wire_states != EXPECTED_CHALLENGE_STATES or witness_states != EXPECTED_CHALLENGE_STATES:
        findings.append(Finding(witness_path, line_of(witness, "Resolution states"), "challenge_states", "challenge state set must be open, refuted, accepted, expired"))
    return findings


def run(inputs: Iterable[Path], *, repo_root: Path = REPO_ROOT, git_ref: str = "origin/main") -> list[Finding]:
    paths = spec_paths(inputs)
    findings: list[Finding] = []
    docs: dict[str, tuple[Path, str]] = {}
    for path in paths:
        text = read_text(path)
        docs[path.name] = (path, text)
        for line_no, line in enumerate(text.splitlines(), start=1):
            findings.extend(check_repo_line(path, line_no, line, repo_root, git_ref))
    findings.extend(check_origin_facts(paths, repo_root, git_ref))
    findings.extend(check_cross_file(docs))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check NAGA-IR repo claims against origin/main.")
    parser.add_argument("paths", nargs="*", type=Path, help="markdown files or directories; defaults to specs/naga_ir")
    parser.add_argument("--git-ref", default="origin/main", help="git ref for grounding")
    parser.add_argument("--json", action="store_true", help="emit JSON report")
    args = parser.parse_args(argv)
    try:
        findings = run(args.paths, repo_root=REPO_ROOT, git_ref=args.git_ref)
    except BrokenCheck as exc:
        print(f"broken: {exc}", file=sys.stderr)
        return EXIT_BROKEN
    if args.json:
        print(json.dumps({"ok": not findings, "findings": [f._asdict() for f in findings]}, default=str, indent=2))
    else:
        print(f"repo_grounding_findings: {len(findings)}")
        for finding in findings:
            print(finding.render(REPO_ROOT), file=sys.stderr)
    return EXIT_VIOLATED if findings else EXIT_CLEAN


if __name__ == "__main__":
    raise SystemExit(main())
