#!/usr/bin/env python3
"""make debug-corral — one door for the whole self-debug system.

The repo grew ~150 debugging / health / anti-slop tools (ratchets, hygiene scans,
the DE_BUG_CORRAL findings register, the broken register, the interface-mismatch
and cybernetic-loop maps, the Pramāṇa Probe slop signals, governance gates). No
one can hold them in their head. This is the single front door — a sibling to
``make onboard`` / ``make orient``.

Doctrine (same as onboard/orient): **read models project truth from owners; they
do not become authority.** This command creates NO new truth store. It RENDERS,
projecting from the existing owners, and is honest about what it can reliably
compute vs. what it must defer to the owning map. Where a count is prose-embedded
and not safely parseable, it links the owner instead of asserting a number — the
anti-slop discipline, turned on the debug system itself.

  make debug-corral            # fast render (projection only; exit 0)
  make debug-corral-strict     # render + run the core gate battery; exit non-zero on RED
  python3 scripts/governance/debug_corral.py [--strict] [--deep] [--json] [--fast]

Modes:
  default : anti-slop signals (cheap AST) + known-debt maps + ratchet status
  --deep  : also run radon complexity (the named complexity instrument)
  --strict: also run the core gates and fail (exit 1) on any RED
  --probes: also run the read-only specialist probe battery
  --full  : deep + strict + probes (the maximal one-command view)
  --json  : machine-readable
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

REPO = Path(__file__).resolve().parents[2]
PKG = REPO / "dharma_swarm"
PYTHON = sys.executable


def _safe(fn, default):
    """A debug tool must never crash; degrade to a default instead."""
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 - intentional: never let a probe kill the corral
        return default if not isinstance(default, dict) else {**default, "error": str(exc)}


# --------------------------------------------------------------------------
# Anti-slop signals (self-computed, fast — the Pramāṇa Probe measurement layer)
# --------------------------------------------------------------------------
def _py_files(root: Path):
    return [p for p in root.rglob("*.py") if ".venv" not in p.parts]


def signal_god_objects() -> dict:
    files = [(p, len(p.read_text(errors="ignore").splitlines())) for p in _py_files(PKG)]
    over = sorted([(n, p) for p, n in files if n > 3000], reverse=True)
    return {"count": len(over), "max": over[0][0] if over else 0,
            "worst": str(over[0][1].relative_to(REPO)) if over else None,
            "grade": "RED" if over else "GREEN"}


def signal_wildcards() -> dict:
    n = sum(1 for p in _py_files(PKG) for ln in p.read_text(errors="ignore").splitlines()
            if ln.strip().startswith("from ") and ln.strip().endswith("import *"))
    return {"count": n, "grade": "RED" if n else "GREEN"}


def signal_load_time_cycles() -> dict:
    mods = {}
    for p in _py_files(PKG):
        # Derive the dotted module name RELATIVE TO REPO. Using parts.index() on an
        # absolute path matches the repo dir first (…/dharma_swarm/dharma_swarm/…),
        # producing `dharma_swarm.dharma_swarm.*` and silently MISSING the cycle
        # through the package root — a false-clean. relative_to(REPO) is correct.
        parts = list(p.relative_to(REPO).with_suffix("").parts)
        if parts[-1] == "__init__":
            parts = parts[:-1]
        mods[".".join(parts)] = p
    names = set(mods)

    def resolve(m, lvl, base):
        if lvl == 0:
            return m
        b = base[: len(base) - (lvl - 1)] if lvl > 1 else base
        return ".".join(b + ([m] if m else []))

    def is_tc(t):
        return (isinstance(t, ast.Name) and t.id == "TYPE_CHECKING") or (
            isinstance(t, ast.Attribute) and t.attr == "TYPE_CHECKING")

    edges: dict[str, set] = {}
    for m, p in mods.items():
        base = m.split(".")
        try:
            tree = ast.parse(p.read_text(errors="ignore"))
        except SyntaxError:
            continue

        class V(ast.NodeVisitor):
            def __init__(self):
                self.d = 0
            def _vf(self, n):
                self.d += 1
                self.generic_visit(n)
                self.d -= 1
            visit_FunctionDef = _vf
            visit_AsyncFunctionDef = _vf
            def visit_If(self, n):
                if is_tc(n.test):
                    for s in n.orelse:
                        self.visit(s)
                    return
                self.generic_visit(n)
            def _add(self, t):
                if t in names and t != m and self.d == 0:
                    edges.setdefault(m, set()).add(t)
            def visit_Import(self, n):
                for a in n.names:
                    self._add(a.name)
            def visit_ImportFrom(self, n):
                tgt = resolve(n.module or "", n.level, base)
                self._add(tgt)
                for a in n.names:
                    self._add(f"{tgt}.{a.name}")
        V().visit(tree)

    idx, low, on, stack, c, sccs = {}, {}, {}, [], [0], []
    sys.setrecursionlimit(50000)

    def sc(v):
        idx[v] = low[v] = c[0]
        c[0] += 1
        stack.append(v)
        on[v] = True
        for w in edges.get(v, ()):
            if w not in idx:
                sc(w)
                low[v] = min(low[v], low[w])
            elif on.get(w):
                low[v] = min(low[v], idx[w])
        if low[v] == idx[v]:
            comp = []
            while True:
                w = stack.pop()
                on[w] = False
                comp.append(w)
                if w == v:
                    break
            if len(comp) > 1:
                sccs.append(comp)
    for v in list(edges):
        if v not in idx:
            sc(v)
    worst = max(sccs, key=len) if sccs else []
    return {"count": len(sccs), "grade": "RED" if sccs else "GREEN",
            "worst": ", ".join(sorted(x.split(".")[-1] for x in worst)) if worst else None}


def signal_complexity_radon() -> dict:
    if shutil.which("radon") is None:
        return {"available": False, "note": "radon absent — `pip install radon`; NOT substituting a proxy"}
    out = subprocess.run(["radon", "cc", str(PKG), "-s", "-n", "D"],
                         capture_output=True, text=True, timeout=120).stdout
    worst_cc, worst_loc, cur, over = 0, None, "", 0
    for line in out.splitlines():
        if not line.startswith(" "):
            cur = line.strip()
            continue
        s = line.strip()
        if " - " in s and "(" in s:
            try:
                cc = int(s.rsplit("(", 1)[1].rstrip(")"))
            except ValueError:
                continue
            if cc > 20:
                over += 1
            if cc > worst_cc:
                worst_cc, worst_loc = cc, f"{cur}:{s.split(' - ')[0]}"
    return {"available": True, "over_cc20": over, "max_cc": worst_cc, "worst": worst_loc,
            "grade": "RED" if worst_cc > 50 else "AMBER" if worst_cc > 20 else "GREEN"}


# --------------------------------------------------------------------------
# Known-debt maps (project from owners; defer where prose isn't parseable)
# --------------------------------------------------------------------------
def map_broken_register() -> dict:
    f = REPO / "docs/state/BROKEN_REGISTER.md"
    if not f.exists():
        return {"present": False}
    txt = f.read_text(errors="ignore")
    return {"present": True, "open": len(re.findall(r"\*\*status:\*\*\s*OPEN", txt)),
            "owner": "docs/state/BROKEN_REGISTER.md"}


def map_interface_mismatch() -> dict:
    f = REPO / "INTERFACE_MISMATCH_MAP.md"
    # BLOCKER/DEGRADED appear in both live AND resolved entries → NOT safely
    # parseable. Defer to the owner rather than assert a wrong number.
    return {"present": f.exists(),
            "note": "live count is prose-embedded — see the map (do not trust a grep tally)",
            "owner": "INTERFACE_MISMATCH_MAP.md"}


def map_cybernetic_loops() -> dict:
    f = REPO / "CYBERNETIC_LOOP_MAP.md"
    return {"present": f.exists(), "owner": "CYBERNETIC_LOOP_MAP.md",
            "note": "closure status per loop — see the map"}


def map_corral_findings() -> dict:
    script = REPO / "scripts/governance/verify_corral_findings.py"
    corral = REPO / "DE_BUG_CORRAL"
    if not corral.exists():
        return {"present": False, "note": "DE_BUG_CORRAL/ has no findings on this branch"}
    r = subprocess.run([sys.executable, str(script), "--json"], capture_output=True, text=True, timeout=60)
    try:
        data = json.loads(r.stdout)
        return {"present": True, "owner": "DE_BUG_CORRAL/", "exit": r.returncode, **({"findings": len(data)} if isinstance(data, list) else {})}
    except Exception:
        return {"present": True, "owner": "DE_BUG_CORRAL/", "exit": r.returncode}


def ratchet_status() -> dict:
    script = REPO / "scripts/governance/hygiene/ratchet.py"
    if not script.exists():
        return {"available": False}
    r = subprocess.run([PYTHON, str(script), "--json"], capture_output=True, text=True, timeout=120)
    try:
        data = json.loads(r.stdout)
        regs = [c["name"] for c in data.get("comparisons", []) if c.get("verdict") == "REGRESSION"]
        return {"available": True, "green": data.get("green"), "regressions": regs,
                "grade": "GREEN" if data.get("green") else "RED"}
    except Exception:
        raw = (r.stderr or r.stdout or "").strip()
        return {"available": True, "green": False, "regressions": [],
                "grade": "RED", "exit": r.returncode,
                "error": "ratchet output was not parseable",
                "raw": _tail(raw) if raw else ""}


# --------------------------------------------------------------------------
# Gates (only with --strict): a curated high-value subset, not all 150
# --------------------------------------------------------------------------
CORE_GATES = [
    ("syntax-check", [PYTHON, "-m", "compileall", "-q", "dharma_swarm"]),
    ("quality-ratchet-check", [PYTHON, "scripts/governance/hygiene/ratchet.py"]),
    ("hygiene-integrity", [PYTHON, "scripts/governance/hygiene/check_hygiene_integrity.py"]),
    ("verify-corral-strict", [PYTHON, "scripts/governance/verify_corral_findings.py", "--strict"]),
]


def _gate_script(cmd: list[str]) -> Path | None:
    for arg in cmd[1:]:
        if arg.endswith(".py"):
            return REPO / arg
    return None


def _tail(text: str, limit: int = 360) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    compact = " | ".join(lines[-2:]) if lines else " ".join(text.strip().split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 4].rstrip() + " ..."


def _pytest(*paths: str) -> list[str]:
    return [PYTHON, "-m", "pytest", *paths, "-q"]


def run_gates() -> list[dict]:
    results = []
    for name, cmd in CORE_GATES:
        script = _gate_script(cmd)
        if script is not None and not script.exists():
            results.append({"gate": name, "status": "SKIP (absent)"})
            continue
        try:
            r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=300)
            detail = _tail(r.stderr or r.stdout) if r.returncode else ""
            results.append({"gate": name, "status": "PASS" if r.returncode == 0 else "FAIL",
                            "exit": r.returncode, **({"detail": detail} if detail else {})})
        except Exception as exc:  # noqa: BLE001
            results.append({"gate": name, "status": f"ERROR ({type(exc).__name__})"})
    return results


# --------------------------------------------------------------------------
# Specialist probes (only with --probes/--full): read-only local dimensions
# --------------------------------------------------------------------------
class Probe(NamedTuple):
    name: str
    lens: str
    cmd: list[str]
    timeout: int = 180
    warn_undergraded: bool = False


PROBE_BATTERY = [
    Probe(
        "pramana-epistemics",
        "five-mode claim validation: pratyaksha/anumana/agama/upamana/arthapatti",
        _pytest("tests/test_pramana.py"),
    ),
    Probe(
        "organism-invariants",
        "criticality, closure, information retention, diversity, runtime and spine invariants",
        _pytest(
            "tests/test_invariants.py",
            "tests/test_runtime_state_invariants.py",
            "tests/test_spine_persistence_invariant.py",
        ),
    ),
    Probe(
        "prompt-and-injection-discipline",
        "prompt builder, prompt evolution, and context-injection safety surfaces",
        _pytest(
            "tests/test_prompt_builder.py",
            "tests/test_injection_scanner.py",
            "tests/test_master_prompt_engineer.py",
        ),
    ),
    Probe(
        "council-decorrelation",
        "verify-not-judge council semantics, no dispatch authority, replayable receipts",
        [PYTHON, "scripts/governance/check_council_invariants.py"],
    ),
    Probe(
        "council-profiles-e2e",
        "profile and model-council orchestration checks",
        _pytest("tests/test_council_profiles.py", "tests/test_model_council_e2e.py"),
    ),
    Probe(
        "claim-evidence-binding",
        "graded anti-slop bar for active-track claims; advisory, no receipt writes",
        [PYTHON, "scripts/governance/check_claim_evidence_binding.py", "--warn-only"],
        timeout=240,
        warn_undergraded=True,
    ),
    Probe(
        "model-routing-discipline",
        "model status, routing keys, provider policy, and provider matrix integrity",
        _pytest(
            "tests/test_model_status_projection.py",
            "tests/test_model_key_routing_guard.py",
            "tests/test_provider_policy.py",
            "tests/test_provider_matrix.py",
        ),
        timeout=240,
    ),
    Probe(
        "semantic-ontology-discipline",
        "semantic acceptance, semantic governance, and ontology consistency",
        _pytest(
            "tests/test_agent_runner_semantic_acceptance.py",
            "tests/test_semantic_governance.py",
            "tests/test_ontology.py",
        ),
    ),
    Probe(
        "runtime-truth-evidence",
        "runtime truth, operating facts, and evidence surface invariants",
        _pytest(
            "tests/test_runtime_truth_spine_v2_evidence.py",
            "tests/test_operating_facts.py",
            "tests/test_runtime_state.py",
        ),
    ),
]


def _probe_summary(output: str) -> str:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines:
        return ""
    pytest_summary = [line for line in lines if " passed" in line or " failed" in line or " error" in line]
    if pytest_summary:
        return pytest_summary[-1]
    return _tail(output)


def _undergraded_count(output: str) -> int:
    m = re.search(r"(\d+)\s+undergraded", output)
    return int(m.group(1)) if m else 0


def run_probes() -> list[dict]:
    results = []
    for probe in PROBE_BATTERY:
        script = _gate_script(probe.cmd)
        if script is not None and not script.exists():
            results.append({
                "probe": probe.name,
                "lens": probe.lens,
                "status": "SKIP (absent)",
            })
            continue
        try:
            r = subprocess.run(
                probe.cmd,
                cwd=REPO,
                capture_output=True,
                text=True,
                timeout=probe.timeout,
            )
            combined = "\n".join(part for part in (r.stdout, r.stderr) if part)
            undergraded = _undergraded_count(combined) if probe.warn_undergraded else 0
            status = "PASS" if r.returncode == 0 else "FAIL"
            if status == "PASS" and undergraded:
                status = "WARN"
            results.append({
                "probe": probe.name,
                "lens": probe.lens,
                "status": status,
                "exit": r.returncode,
                "detail": _probe_summary(combined),
                **({"undergraded": undergraded} if undergraded else {}),
            })
        except Exception as exc:  # noqa: BLE001 - diagnostic surface must report, not crash
            results.append({
                "probe": probe.name,
                "lens": probe.lens,
                "status": f"ERROR ({type(exc).__name__})",
            })
    return results


# --------------------------------------------------------------------------
def gather(deep: bool, strict: bool, fast: bool, probes: bool) -> dict:
    slop = {
        "god_objects": _safe(signal_god_objects, {"grade": "?"}),
        "load_time_cycles": _safe(signal_load_time_cycles, {"grade": "?"}),
        "wildcard_imports": _safe(signal_wildcards, {"grade": "?"}),
    }
    if deep:
        slop["complexity"] = _safe(signal_complexity_radon, {"available": False})
    debt = {
        "broken_register": _safe(map_broken_register, {"present": False}),
        "interface_mismatch": _safe(map_interface_mismatch, {"present": False}),
        "cybernetic_loops": _safe(map_cybernetic_loops, {"present": False}),
        "corral_findings": _safe(map_corral_findings, {"present": False}),
    }
    out = {"slop": slop, "debt": debt}
    if not fast:
        out["ratchet"] = _safe(ratchet_status, {"available": False})
    if strict:
        out["gates"] = run_gates()
    if probes:
        out["probes"] = run_probes()
    reds = sum(1 for s in slop.values() if isinstance(s, dict) and s.get("grade") == "RED")
    if out.get("ratchet", {}).get("grade") == "RED":
        reds += 1  # a ratchet regression is a red signal too
    open_debt = debt["broken_register"].get("open", 0) if debt["broken_register"].get("present") else 0
    gate_fail = sum(1 for g in out.get("gates", []) if g.get("status") == "FAIL")
    probe_fail = sum(
        1 for p in out.get("probes", [])
        if p.get("status") == "FAIL" or str(p.get("status", "")).startswith("ERROR")
    )
    probe_warn = sum(1 for p in out.get("probes", []) if p.get("status") == "WARN")
    out["verdict"] = {
        "red_signals": reds,
        "open_debt": open_debt,
        "gate_failures": gate_fail,
        "probe_failures": probe_fail,
        "probe_warnings": probe_warn,
        "state": "CLEAN" if (
            reds == 0 and open_debt == 0 and gate_fail == 0 and probe_fail == 0 and probe_warn == 0
        ) else "ELEVATED",
    }
    return out


GRADE_ICON = {"RED": "🔴", "AMBER": "🟡", "GREEN": "🟢", "?": "❔"}


def render(d: dict) -> str:
    L = ["═══ DE-BUG CORRAL — system self-debug, one door ═══",
         "projects from existing owners; creates no new authority (like onboard/orient)", ""]
    s = d["slop"]
    L.append("ANTI-SLOP SIGNALS (Pramāṇa Probe — self-measured)")
    g = s["god_objects"]
    L.append(f"  {GRADE_ICON.get(g.get('grade'),'❔')} god objects >3000 ln … {g.get('count','?')}  (max {g.get('max','?')} — {g.get('worst') or '—'})")
    cy = s["load_time_cycles"]
    L.append(f"  {GRADE_ICON.get(cy.get('grade'),'❔')} load-time import cycles … {cy.get('count','?')}  ({cy.get('worst') or 'none'})")
    w = s["wildcard_imports"]
    L.append(f"  {GRADE_ICON.get(w.get('grade'),'❔')} wildcard imports … {w.get('count','?')}")
    if "complexity" in s:
        cx = s["complexity"]
        if cx.get("available"):
            L.append(f"  {GRADE_ICON.get(cx.get('grade'),'❔')} complexity (radon) … {cx.get('over_cc20','?')} fns cc>20; worst {cx.get('worst')} cc {cx.get('max_cc')}")
        else:
            L.append(f"  ❔ complexity … {cx.get('note','radon absent')}")
    if "ratchet" in d:
        r = d["ratchet"]
        if r.get("available") and "green" in r:
            if r["green"]:
                msg = "green"
            elif r.get("regressions"):
                msg = "REGRESSION: " + ", ".join(r.get("regressions", []))
            else:
                msg = "BROKEN: " + (r.get("raw") or r.get("error", "unknown ratchet failure"))
            L.append(f"  {GRADE_ICON.get(r.get('grade'),'❔')} quality ratchet … {msg}")
    L.append("")
    L.append("KNOWN DEBT (maps — owners; see each for the live count)")
    b = d["debt"]["broken_register"]
    L.append(f"  • BROKEN_REGISTER … {b.get('open','?')} OPEN" + (f"  [{b.get('owner')}]" if b.get("present") else "  (absent)"))
    L.append(f"  • INTERFACE_MISMATCH … {d['debt']['interface_mismatch'].get('note')}  [INTERFACE_MISMATCH_MAP.md]")
    L.append(f"  • CYBERNETIC_LOOPS … {d['debt']['cybernetic_loops'].get('note')}  [CYBERNETIC_LOOP_MAP.md]")
    cf = d["debt"]["corral_findings"]
    L.append(f"  • DE_BUG_CORRAL … {cf.get('note') or ('findings present; verify exit ' + str(cf.get('exit')))}")
    if "gates" in d:
        L.append("")
        L.append("CORE GATES (--strict)")
        for g in d["gates"]:
            mark = {"PASS": "✅", "FAIL": "❌"}.get(g["status"], "⚠️ ")
            detail = f" — {g['detail']}" if g.get("detail") else ""
            L.append(f"  {mark} {g['gate']} … {g['status']}{detail}")
    if "probes" in d:
        L.append("")
        L.append("SPECIALIST PROBES (--probes/--full)")
        for p in d["probes"]:
            mark = {"PASS": "✅", "FAIL": "❌", "WARN": "🟡"}.get(p["status"], "⚠️ ")
            detail = f" — {p['detail']}" if p.get("detail") else ""
            L.append(f"  {mark} {p['probe']} … {p['status']}{detail}")
            L.append(f"      lens: {p['lens']}")
    v = d["verdict"]
    L.append("")
    L.append(
        f"VERDICT: {v['state']} — {v['red_signals']} red anti-slop signal(s), "
        f"{v['open_debt']} open debt item(s)"
        + (f", {v['gate_failures']} gate failure(s)" if 'gates' in d else "")
        + (
            f", {v['probe_failures']} probe failure(s), {v['probe_warnings']} probe warning(s)"
            if 'probes' in d else ""
        )
    )
    L.append("more: make onboard · make orient · docs/stop-the-slop/runner/slop_probe.py · the maps above")
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="DE-BUG CORRAL — one door for system self-debug (projection, not authority).")
    ap.add_argument("--strict", action="store_true", help="run the core gate battery; exit non-zero on RED")
    ap.add_argument("--deep", action="store_true", help="also run radon complexity")
    ap.add_argument("--probes", action="store_true", help="run the read-only specialist probe battery")
    ap.add_argument("--full", action="store_true", help="maximal local view: --deep --strict --probes")
    ap.add_argument("--fast", action="store_true", help="skip the ratchet subprocess")
    ap.add_argument("--json", action="store_true", help="machine-readable")
    a = ap.parse_args(argv)
    deep = a.deep or a.full
    strict = a.strict or a.full
    probes = a.probes or a.full
    d = gather(deep=deep, strict=strict, fast=a.fast, probes=probes)
    print(json.dumps(d, indent=2) if a.json else render(d))
    # exit non-zero only in --strict and only on a real failure (gate fail or ratchet regression)
    if strict:
        if (
            d["verdict"]["gate_failures"]
            or d["verdict"].get("probe_failures")
            or (d.get("ratchet", {}).get("grade") == "RED")
        ):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
