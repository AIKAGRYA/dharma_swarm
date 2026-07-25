#!/usr/bin/env python3
"""trust_gate_status.py — measured scoreboard for the NORTH_STAR §8 trust gate.

Fact-owner: docs/vision_maps/NORTH_STAR.md §8 ("The trust gate — what the
operator must SEE before pushing outside") defines five conditions. This
script owns NO fact: it projects each condition onto evidence that already
exists in the repo (audit reports, the venture-cell portfolio, the broken
register, the context compiler source, git) and emits an honest
RED/AMBER/GREEN verdict per condition.

Outputs:
  - human table to stdout
  - reports/governance/trust_gate_status.json (machine readable)

Doctrine line that must hold (same as agent_onboard.py):
  Read models project truth from owners; they do not become authority.

A condition that cannot be measured scores 0.0 with the gap named in its
evidence — an unmeasured condition is RED, never silently green.

Exit code: always 0. This is a scoreboard, not a CI gate.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _load_broken_register_parser():
    path = REPO_ROOT / "dharma_swarm/operator_core/onboarding/broken_register.py"
    spec = importlib.util.spec_from_file_location("_dharma_broken_register_trust", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load canonical broken-register parser: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.parse_broken_register


parse_broken_register = _load_broken_register_parser()

REPORTS_DIR = REPO_ROOT / "reports/governance"
NORTH_STAR_REL = "docs/vision_maps/NORTH_STAR.md"
SCHEMA = "dharma_swarm.trust_gate_status.v1"

GREEN_AT = 0.8
AMBER_AT = 0.4

# Condensed from NORTH_STAR §8 (the fact-owner; read it for the full text).
CONDITIONS = {
    "C1": "Pointed audit reports a clean working repo, high-quality code, and deep flow understanding",
    "C2": "Swarm scores higher than single models on coding benchmarks (published bar: DGM 20%->50% SWE-bench)",
    "C3": "A full venture-cell build, end to end, verifiably competitive with the field",
    "C4": "All seeded parts wired in and functioning consistently",
    "C5": "Agents orient from the memory kernel first (first-token orientation: operator, system, telos, code, agents)",
}


@dataclass
class ConditionResult:
    id: str
    condition: str
    evidence: list[str]
    score: float
    verdict: str
    owner_of_truth: str


def verdict_for(score: float) -> str:
    if score >= GREEN_AT:
        return "GREEN"
    if score >= AMBER_AT:
        return "AMBER"
    return "RED"


def _result(cid: str, evidence: list[str], score: float, owner: str) -> ConditionResult:
    score = max(0.0, min(1.0, round(score, 3)))
    return ConditionResult(
        id=cid, condition=CONDITIONS[cid], evidence=evidence,
        score=score, verdict=verdict_for(score), owner_of_truth=owner,
    )


def _git_status_count(tree: Path) -> int | None:
    """Dirty-entry count from `git status --porcelain`. None if unreadable."""
    try:
        out = subprocess.check_output(
            ["git", "-C", str(tree), "status", "--porcelain"],
            text=True, stderr=subprocess.DEVNULL, timeout=20,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return None
    return len([ln for ln in out.splitlines() if ln.strip()])


def _latest_dated_dir(parent: Path, pattern: str) -> tuple[Path, date] | None:
    """Newest dir under parent matching pattern with a trailing YYYY-MM-DD."""
    best: tuple[Path, date] | None = None
    if not parent.is_dir():
        return None
    for p in sorted(parent.glob(pattern)):
        m = re.search(r"(\d{4}-\d{2}-\d{2})", p.name)
        if not m:
            continue
        try:
            when = datetime.strptime(m.group(1), "%Y-%m-%d").date()
        except ValueError:
            continue
        if best is None or when > best[1]:
            best = (p, when)
    return best


def score_c1(repo_root: Path, runtime_tree: Path | None) -> ConditionResult:
    """Repo cleanliness + freshness of the latest pointed audit."""
    evidence: list[str] = []
    tree = runtime_tree if runtime_tree and runtime_tree.is_dir() else repo_root
    if tree is repo_root and runtime_tree is not None:
        evidence.append(f"runtime tree {runtime_tree} not found — measured {repo_root} instead")
    dirty = _git_status_count(tree)
    if dirty is None:
        evidence.append(f"git status unreadable on {tree}")
        clean_component = 0.0
    else:
        evidence.append(f"git -C {tree} status --porcelain -> {dirty} dirty entries")
        clean_component = max(0.0, 1.0 - dirty / 20.0)

    audit = _latest_dated_dir(repo_root / "reports", "anatomy_*")
    if audit is None:
        evidence.append("no reports/anatomy_* audit found")
        audit_component = 0.0
    else:
        age = (date.today() - audit[1]).days
        evidence.append(f"latest pointed audit: {audit[0].relative_to(repo_root)} (dated {audit[1]}, {age}d old)")
        audit_component = 1.0 if age <= 14 else (0.5 if age <= 45 else 0.1)

    # "Deep flow understanding" is asserted by the audit, not re-derived here;
    # cap below GREEN until an audit explicitly verifies the full GO->ontology
    # flow chain named in §8.
    evidence.append("flow-chain verification (GO intake -> ... -> semantic ontology) not yet a measured artifact — capped at AMBER")
    score = min(0.79, 0.5 * clean_component + 0.5 * audit_component)
    return _result("C1", evidence, score,
                   "git status (runtime tree) + reports/anatomy_*/")


# Both ASCII hyphen-minus and U+2212 appear in audit prose.
_LIFT_RE = re.compile(r"(?:cost_normalized_lift|swarm_lift)\s*=\s*[`\s]*([−\-+]?\d+(?:\.\d+)?)")


def find_swarm_lift(repo_root: Path) -> tuple[float, str] | None:
    """Latest measured swarm-vs-single lift from the newest anatomy audit."""
    audit = _latest_dated_dir(repo_root / "reports", "anatomy_*")
    if audit is None:
        return None
    for path in sorted(audit[0].glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        m = _LIFT_RE.search(text)
        if m:
            value = float(m.group(1).replace("−", "-"))
            return value, str(path.relative_to(repo_root))
    return None


def score_c2(repo_root: Path) -> ConditionResult:
    """Swarm-vs-single benchmark lift, against the published DGM bar.

    ADMISSIBILITY (the commensurability rule, 2026-07-03): only live benchmark
    measurements under reports/anatomy_*/ feed this condition. The hermetic
    Arena Truth surface (reports/governance/arena/) is deliberately NOT read
    here and never will be: its fixture pool is constructed so that routing
    beats best-single (Krogh-Vedelsby is baked into the recorded data), which
    makes its positive lift a control-machinery existence proof — an object of
    a different kind than a benchmark result. A C2-admissible number requires:
    live (non-fixture) seats, >=2 model families, the same best-single +
    budget-parity + significance control arms the hermetic runner enforces.
    """
    evidence = ["published bar (NORTH_STAR §8): DGM self-improved 20%->50% SWE-bench (arXiv:2505.22954)"]
    evidence.append(
        "admissibility: hermetic arena lift (reports/governance/arena/, fixture-"
        "constructed routing win) is NOT commensurable with this condition and is "
        "never read here; C2 moves only on live runs with >=2 model families under "
        "the same budget-parity + significance controls")
    found = find_swarm_lift(repo_root)
    if found is None:
        evidence.append("no swarm-lift measurement found under reports/anatomy_*/ — condition unmeasured")
        score = 0.0
    else:
        lift, src = found
        evidence.append(f"latest measured lift = {lift} ({src})")
        if lift <= 0:
            evidence.append("swarm currently loses to its best single agent")
            score = 0.05
        else:
            score = min(1.0, 0.5 + lift)
    return _result("C2", evidence, score,
                   "reports/anatomy_*/ (forge arena measurement) + NORTH_STAR §8 bar")


_CELL_BLOCK_RE = re.compile(r"(?m)^  - id:\s*(\S+)")
_STATUS_RE = re.compile(r"(?m)^    status:\s*(\S+)")


def parse_cell_statuses(portfolio_path: Path) -> dict[str, str]:
    """{cell_id: STATUS} from VENTURE_CELL_PORTFOLIO.yaml (cells + envisioned)."""
    if not portfolio_path.exists():
        return {}
    text = portfolio_path.read_text(encoding="utf-8", errors="replace")
    out: dict[str, str] = {}
    ids = list(_CELL_BLOCK_RE.finditer(text))
    for i, m in enumerate(ids):
        block = text[m.end(): ids[i + 1].start() if i + 1 < len(ids) else len(text)]
        sm = _STATUS_RE.search(block)
        if sm:
            out[m.group(1)] = sm.group(1)
    return out


def score_c3(repo_root: Path) -> ConditionResult:
    """Venture-cell end-to-end: any cell ACTIVE with external receipts?"""
    portfolio = repo_root / "docs/governance/VENTURE_CELL_PORTFOLIO.yaml"
    statuses = parse_cell_statuses(portfolio)
    evidence: list[str] = []
    if not statuses:
        evidence.append(f"{portfolio.relative_to(repo_root)} missing or unparseable")
        return _result("C3", evidence, 0.0, str(portfolio.relative_to(repo_root)))
    active = sorted(c for c, s in statuses.items() if s.startswith("ACTIVE"))
    evidence.append(f"{len(statuses)} cells declared; ACTIVE-class: {active or 'none'}")
    text = portfolio.read_text(encoding="utf-8", errors="replace")
    rev = re.search(r"revenue_usd:\s*(\d+)", text)
    receipts = rev is not None and int(rev.group(1)) > 0
    if rev:
        evidence.append(f"recorded revenue_usd: {rev.group(1)}")
    gate_ev = re.search(r"gate_evidence:\s*(\S+)", text)
    if gate_ev and not (repo_root / gate_ev.group(1)).exists():
        evidence.append(f"gate_evidence file {gate_ev.group(1)} referenced but absent")
    if receipts and active:
        score = 0.85
    elif active:
        evidence.append("ACTIVE cells exist but no external receipts recorded — not end-to-end yet")
        score = 0.3
    else:
        score = 0.05
    return _result("C3", evidence, score, str(portfolio.relative_to(repo_root)))


def parse_broken_counts(register_path: Path) -> tuple[int, int, int] | None:
    """(total, open_like, closed_like) — same parse as agent_onboard.py."""
    result = parse_broken_register(register_path)
    if not result.present:
        return None
    return result.total, result.open_count, result.closed_count


def list_remote_heads(repo_root: Path) -> list[str] | None:
    """Remote branch names via `git ls-remote --heads origin`. None on failure."""
    try:
        out = subprocess.check_output(
            ["git", "-C", str(repo_root), "ls-remote", "--heads", "origin"],
            text=True, stderr=subprocess.DEVNULL, timeout=30,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return None
    return [ln.split("refs/heads/", 1)[1] for ln in out.splitlines() if "refs/heads/" in ln]


_SEED_PATTERN = re.compile(r"gold|vault|rescue|salvage|seed", re.IGNORECASE)


def score_c4(repo_root: Path, branches: list[str] | None) -> ConditionResult:
    """Seeded-parts-wired: unmerged seed/gold branches + broken-register state."""
    evidence: list[str] = []
    counts = parse_broken_counts(repo_root / "docs/state/BROKEN_REGISTER.md")
    if counts is None:
        evidence.append("docs/state/BROKEN_REGISTER.md missing")
        br_component = 0.0
    else:
        total, open_like, closed_like = counts
        evidence.append(f"BROKEN_REGISTER: total={total} open-like={open_like} closed-like={closed_like}")
        denom = total
        br_component = 1.0 if denom == 0 else closed_like / denom

    if branches is None:
        evidence.append("remote branch census unavailable (offline or git failure) — seed component unmeasured")
        seed_component = 0.0
    else:
        seeded = sorted(b for b in branches if _SEED_PATTERN.search(b))
        evidence.append(f"remote heads: {len(branches)} total; seed/gold/vault-pattern unmerged-to-main candidates: {len(seeded)}")
        if seeded:
            evidence.append(f"pattern branches: {seeded[:5]}")
        seed_component = 1.0 / (1.0 + len(seeded))

    score = 0.5 * br_component + 0.5 * seed_component
    return _result("C4", evidence, score,
                   "git ls-remote --heads origin + docs/state/BROKEN_REGISTER.md")


def memory_kernel_position(compiler_path: Path) -> tuple[bool, int] | None:
    """(wired, sections_appended_before_kernel) from context_compiler source.

    First-token orientation holds only when the memory-kernel section is the
    FIRST section appended in the bundle build. A static source scan is the
    honest measure available now; it flips the moment someone reorders.
    """
    if not compiler_path.exists():
        return None
    text = compiler_path.read_text(encoding="utf-8", errors="replace")
    # Scope to the bundle-build function so appends in unrelated helpers
    # (e.g. the canary projection) do not inflate the count.
    fn_at = text.find("def _build_sections")
    scope = text[fn_at:] if fn_at >= 0 else text
    kernel_at = scope.find("sections.append(memory_kernel_section)")
    if kernel_at < 0:
        return False, 0
    before = scope[:kernel_at].count("sections.append(")
    return True, before


def score_c5(repo_root: Path) -> ConditionResult:
    """Memory-kernel first-token adoption in dispatched agent context."""
    compiler = repo_root / "dharma_swarm/context_compiler.py"
    evidence: list[str] = []
    pos = memory_kernel_position(compiler)
    if pos is None:
        evidence.append(f"{compiler.relative_to(repo_root)} missing — unmeasured")
        score = 0.0
    else:
        wired, before = pos
        if not wired:
            evidence.append("memory-kernel section NOT appended in context bundle build")
            score = 0.0
        elif before == 0:
            evidence.append("memory-kernel section is the FIRST section in every dispatch bundle")
            score = 0.9
        else:
            evidence.append(
                f"memory-kernel section wired into dispatch bundles but {before} sections "
                f"render before it ({compiler.relative_to(repo_root)}) — not first-token default")
            score = 0.2
    genome = _latest_dated_dir(repo_root / "reports/swarm_genome", "*")
    if genome:
        synth = genome[0] / "SYNTHESIS.md"
        if synth.exists() and "first-token" in synth.read_text(encoding="utf-8", errors="replace"):
            evidence.append(f"cross-check: {synth.relative_to(repo_root)} §Organ Health (MemoryKernel row)")
    return _result("C5", evidence, score,
                   "dharma_swarm/context_compiler.py (section order) + reports/swarm_genome/")


def build_scoreboard(repo_root: Path, runtime_tree: Path | None,
                     branches: list[str] | None) -> dict:
    results = [
        score_c1(repo_root, runtime_tree),
        score_c2(repo_root),
        score_c3(repo_root),
        score_c4(repo_root, branches),
        score_c5(repo_root),
    ]
    return {
        "schema": SCHEMA,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0)
                        .isoformat().replace("+00:00", "Z"),
        "fact_owner": f"{NORTH_STAR_REL} §8",
        "authority": "projection_only",
        "gate_open": all(r.verdict == "GREEN" for r in results),
        "conditions": [asdict(r) for r in results],
    }


def render_table(payload: dict) -> str:
    lines = [
        f"TRUST GATE SCOREBOARD — fact-owner: {payload['fact_owner']}",
        f"generated: {payload['generated_at']}   gate_open: {payload['gate_open']}",
        "",
    ]
    for c in payload["conditions"]:
        lines.append(f"[{c['verdict']:>5}] {c['id']}  score={c['score']:.2f}  {c['condition']}")
        for ev in c["evidence"]:
            lines.append(f"         - {ev}")
        lines.append(f"         owner: {c['owner_of_truth']}")
        lines.append("")
    lines.append("Doctrine: this scoreboard projects existing owners; it is not authority.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Measured scoreboard for the NORTH_STAR §8 trust-gate conditions.")
    parser.add_argument("--no-net", action="store_true",
                        help="skip the git ls-remote branch census")
    parser.add_argument("--runtime-tree", default=os.getenv("DHARMA_RUNTIME_TREE", ""),
                        help="runtime tree to git-status for C1 (default: $DHARMA_RUNTIME_TREE, "
                             "else ~/dharma_swarm_live, else this repo)")
    parser.add_argument("--json-only", action="store_true",
                        help="print only the JSON payload to stdout")
    args = parser.parse_args(argv)

    runtime_tree = Path(args.runtime_tree).expanduser() if args.runtime_tree \
        else Path.home() / "dharma_swarm_live"
    branches = None if args.no_net else list_remote_heads(REPO_ROOT)
    payload = build_scoreboard(REPO_ROOT, runtime_tree, branches)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORTS_DIR / "trust_gate_status.json"
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    if args.json_only:
        print(json.dumps(payload, indent=2))
    else:
        print(render_table(payload))
        print(f"JSON: {out.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
