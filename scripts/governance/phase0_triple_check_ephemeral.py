#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import asyncio
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--repo", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--target-sha", required=True)
    p.add_argument("--base-sha", required=True)
    return p.parse_args()


ARGS = parse_args()
REPO = Path(ARGS.repo).resolve()
OUT = Path(ARGS.out).resolve()
OUT.mkdir(parents=True, exist_ok=True)
CASES: list[dict[str, Any]] = []
BASE_ENV = os.environ.copy()
BASE_ENV.pop("PYTHONPATH", None)
BASE_ENV.update(
    {
        "OPENROUTER_API_KEY": "sk-or-stub",
        "ANTHROPIC_API_KEY": "sk-ant-stub",
        "TINY_ROUTER_BACKEND": "heuristic",
        "DHARMA_EVOLUTION_SHADOW": "1",
        "DGC_AUTONOMY_LEVEL": "0",
        "PYTHONHASHSEED": "0",
    }
)


def slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_")


def run_case(
    name: str,
    cmd: list[str] | str,
    *,
    cwd: Path = REPO,
    env: dict[str, str] | None = None,
    timeout: int = 1800,
    expectation: str = "zero",
) -> subprocess.CompletedProcess[str]:
    index = len(CASES) + 1
    path = OUT / f"{index:03d}_{slug(name)}.log"
    shell = isinstance(cmd, str)
    command_display = cmd if shell else " ".join(cmd)
    started = datetime.now(UTC).isoformat()
    t0 = time.monotonic()
    try:
        completed = subprocess.run(
            cmd,
            cwd=cwd,
            env=env or BASE_ENV,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            shell=shell,
            executable="/bin/bash" if shell else None,
            check=False,
        )
        rc = completed.returncode
        output = completed.stdout or ""
    except subprocess.TimeoutExpired as exc:
        rc = 124
        output = (exc.stdout or "") + "\nTIMEOUT\n"
        completed = subprocess.CompletedProcess(cmd, rc, output, "")
    elapsed = time.monotonic() - t0
    ok = (rc == 0) if expectation == "zero" else (rc != 0) if expectation == "nonzero" else True
    record = {
        "name": name,
        "command": command_display,
        "cwd": str(cwd),
        "started_at": started,
        "elapsed_seconds": round(elapsed, 3),
        "exit_code": rc,
        "expectation": expectation,
        "expectation_met": ok,
        "log": path.name,
    }
    CASES.append(record)
    path.write_text(
        "\n".join(
            [
                f"NAME: {name}",
                f"COMMAND: {command_display}",
                f"CWD: {cwd}",
                f"STARTED_AT: {started}",
                f"ELAPSED_SECONDS: {elapsed:.3f}",
                f"EXIT_CODE: {rc}",
                f"EXPECTATION: {expectation}",
                f"EXPECTATION_MET: {ok}",
                "--- OUTPUT ---",
                output,
            ]
        ),
        encoding="utf-8",
    )
    print(f"[{index:03d}] {name}: rc={rc} expected={expectation} met={ok}", flush=True)
    return completed


def write_probe(name: str, source: str) -> Path:
    path = OUT / f"probe_{slug(name)}.py"
    path.write_text(textwrap.dedent(source), encoding="utf-8")
    return path


def mutate_and_test(
    name: str,
    relative: str,
    mutator,
    test_cmd: list[str],
) -> None:
    path = REPO / relative
    original = path.read_text(encoding="utf-8")
    try:
        mutated = mutator(original)
        if mutated == original:
            raise RuntimeError(f"mutation did not change {relative}")
        path.write_text(mutated, encoding="utf-8")
        run_case(name, test_cmd, expectation="nonzero", timeout=1200)
    except Exception as exc:
        log = OUT / f"mutation_error_{slug(name)}.log"
        log.write_text(repr(exc), encoding="utf-8")
        CASES.append(
            {
                "name": name,
                "command": f"mutate {relative}",
                "cwd": str(REPO),
                "started_at": datetime.now(UTC).isoformat(),
                "elapsed_seconds": 0,
                "exit_code": 125,
                "expectation": "nonzero",
                "expectation_met": False,
                "log": log.name,
            }
        )
    finally:
        path.write_text(original, encoding="utf-8")


run_case("git status initial", ["git", "status", "--short", "--branch"])
run_case("git target sha", ["git", "rev-parse", "HEAD"])
run_case("git merge base", ["git", "merge-base", ARGS.target_sha, ARGS.base_sha])
run_case("git non shallow", ["git", "rev-parse", "--is-shallow-repository"])
run_case("identity and umask", "id; printf 'umask='; umask; uname -a; env | sort | grep -E '^(PYTHONPATH|OPENROUTER_API_KEY|ANTHROPIC_API_KEY|TINY_ROUTER_BACKEND|DHARMA_EVOLUTION_SHADOW|DGC_AUTONOMY_LEVEL)=' || true")
run_case(
    "ci exact install",
    'python -m pip install --upgrade pip && pip install -e ".[dev]"',
    timeout=3600,
)
run_case(
    "tool versions",
    "python --version; python -m pip --version; git --version; make --version | head -1; python -m pytest --version; python -m ruff --version; uv --version || true",
)
try:
    import yaml

    active = yaml.safe_load((REPO / "docs/governance/ACTIVE_TRACK.yaml").read_text())
    track = next(
        t
        for t in active["active_tracks"]
        if t["id"] == "repository-titanium-hardening-2026-07"
    )
    criteria = [c for c in track["completion_criteria"] if c["kind"] == "command_passes"]
    (OUT / "completion_criteria_extracted.json").write_text(
        json.dumps(criteria, indent=2), encoding="utf-8"
    )
    for criterion in criteria:
        run_case(
            f"criterion {criterion['id']}",
            [str(part) for part in criterion["command"]],
            timeout=1800,
        )
except Exception as exc:
    (OUT / "completion_criteria_extraction_error.log").write_text(repr(exc), encoding="utf-8")
    CASES.append(
        {
            "name": "completion criteria extraction",
            "command": "parse ACTIVE_TRACK.yaml",
            "cwd": str(REPO),
            "started_at": datetime.now(UTC).isoformat(),
            "elapsed_seconds": 0,
            "exit_code": 125,
            "expectation": "zero",
            "expectation_met": False,
            "log": "completion_criteria_extraction_error.log",
        }
    )
run_case("make test-fast run 1", ["make", "test-fast"], timeout=10800)
run_case("make test-fast run 2", ["make", "test-fast"], timeout=10800)
run_case(
    "full CI pytest lane",
    [
        "python",
        "-m",
        "pytest",
        "tests/",
        "-q",
        "--tb=short",
        "--timeout=30",
        "-m",
        "not slow and not docker and not network",
    ],
    timeout=10800,
)
run_case(
    "agentops packet scope",
    [
        "python3",
        "scripts/governance/check_agentops_packet_scope.py",
        "--event-name",
        "pull_request",
        "--event-base",
        ARGS.base_sha,
        "--event-head",
        ARGS.target_sha,
    ],
    timeout=1800,
)
digest_probe = write_probe(
    "packet_digest",
    """
    import json
    from pathlib import Path
    from dharma_swarm.operator_core.onboarding.contract import packet_digest
    p = Path('reports/agentops/work_packets/titanium-WP-PHASE0-INTEGRATION.json')
    payload = json.loads(p.read_text())
    observed = packet_digest(payload)
    declared = payload['session_entry']['packet_digest']
    print(json.dumps({'declared': declared, 'observed': observed, 'match': declared == observed}, sort_keys=True))
    raise SystemExit(0 if declared == observed else 1)
    """,
)
run_case("packet digest", ["python", str(digest_probe)])
base_worktree = Path(tempfile.mkdtemp(prefix="titanium-base-"))
shutil.rmtree(base_worktree)
run_case("create merge-base worktree", ["git", "worktree", "add", "--detach", str(base_worktree), ARGS.base_sha])
ingress_probe = write_probe(
    "ingress_missing_secret",
    f"""
    import asyncio, importlib.util, json, os, sys
    from pathlib import Path
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    def load(name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        assert spec and spec.loader
        spec.loader.exec_module(mod)
        return mod

    def probe(label, root):
        os.environ.pop('DHARMA_VERIFY_WEBHOOK_SECRET', None)
        gh = load(label + '_github_app', root / 'dharma_swarm/verify/github_app.py')
        vr = load(label + '_verify_router', root / 'api/routers/verify.py')
        handler = gh.VerifyWebhookHandler(webhook_secret='')
        body = b'{{}}'
        direct = handler.verify_signature(body, 'sha256=deadbeef')
        handled = asyncio.run(handler.handle_webhook(body, 'sha256=deadbeef', 'ping'))
        vr._webhook_handler = handler
        app = FastAPI()
        app.include_router(vr.router)
        response = TestClient(app).post(
            '/api/verify/webhook',
            content=body,
            headers={{'X-Hub-Signature-256': 'sha256=deadbeef', 'X-GitHub-Event': 'ping'}},
        )
        result = {{
            'label': label,
            'direct_accepts': direct,
            'handled_processed': handled.processed,
            'handled_error': handled.error,
            'http_status': response.status_code,
            'http_body': response.text,
        }}
        print(json.dumps(result, sort_keys=True))
        return result

    base = probe('base', Path({str(base_worktree)!r}))
    head = probe('head', Path({str(REPO)!r}))
    assert base['direct_accepts'] is True, base
    assert base['http_status'] != 401, base
    assert head['direct_accepts'] is False, head
    assert head['handled_error'] == 'Invalid webhook signature', head
    assert head['http_status'] == 401, head
    """,
)
run_case("missing-secret handler and HTTP boundary base vs head", ["python", str(ingress_probe)])
run_case(
    "ingress fail-open surface search",
    "rg -n --hidden -S 'webhook|verify_signature|X-Hub-Signature-256|DHARMA_VERIFY_WEBHOOK_SECRET|return True|continue-on-error|\\|\\| true' api dharma_swarm/verify .github/workflows | sed -n '1,1200p'",
    expectation="any",
)
mutate_and_test(
    "sabotage fast suite marker filter",
    "Makefile",
    lambda text: text.replace(
        '--timeout=10 -m "not slow and not docker and not network"',
        '--timeout=10',
        1,
    ),
    ["python", "-m", "pytest", "tests/test_fast_suite_isolation.py", "-q"],
)
mutate_and_test(
    "sabotage polyglot exact Go pin",
    ".github/workflows/tests.yml",
    lambda text: text.replace('go-version: "1.26.3"', 'go-version: "1.26"', 1),
    ["python", "-m", "pytest", "tests/test_polyglot_ci_contract.py", "-q"],
)
mutate_and_test(
    "sabotage hermetic false-green",
    ".github/workflows/hermetic.yml",
    lambda text: text.replace("uv lock --check", "uv lock --check || true", 1),
    ["python", "-m", "pytest", "tests/test_hermetic_supply_chain.py", "-q"],
)
mutate_and_test(
    "sabotage NATS live lane enters governance-all",
    "Makefile",
    lambda text: re.sub(
        r"^(governance-all\s*:[^\n]*)$",
        r"\1 nats-live-production-matrix",
        text,
        count=1,
        flags=re.MULTILINE,
    ),
    ["python", "-m", "pytest", "tests/test_nats_verification_split.py", "-q"],
)
mutate_and_test(
    "sabotage repo-scale timeout override",
    "tests/test_model_key_routing_guard.py",
    lambda text: re.sub(
        r"@pytest\.mark\.timeout\([^\n]+\)\n(?=def test_model_literals_do_not_escape_canonical_registries)",
        "",
        text,
        count=1,
    ),
    ["python", "-m", "pytest", "tests/test_fast_suite_isolation.py", "-q"],
)
run_case("checkout clean after sabotage", ["git", "status", "--short"])
bug_probe = write_probe(
    "bug_fix_repros",
    f"""
    import ast, importlib.util, json, os, subprocess, sys, tempfile
    from datetime import UTC, datetime
    from pathlib import Path

    BASE = Path({str(base_worktree)!r})
    HEAD = Path({str(REPO)!r})
    TRUSTED = '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'

    def load(name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        assert spec and spec.loader
        spec.loader.exec_module(mod)
        return mod

    def confinement_env_present(path):
        tree = ast.parse(path.read_text())
        fn = next(n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == '_negative_confinement')
        calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'run_command']
        relevant = []
        for call in calls:
            text = ast.unparse(call)
            if '--map-root-user' in text and 'true' in text:
                relevant.append((text, any(k.arg == 'env' for k in call.keywords)))
        assert relevant, 'probe call not found'
        return relevant

    results = {{}}
    results['confinement_ast_base'] = confinement_env_present(BASE / 'scripts/governance/run_agent_work_packet.py')
    results['confinement_ast_head'] = confinement_env_present(HEAD / 'scripts/governance/run_agent_work_packet.py')
    assert results['confinement_ast_base'][0][1] is False
    assert results['confinement_ast_head'][0][1] is True
    poison = Path(tempfile.mkdtemp(prefix='poison-path-'))
    fake_true = poison / 'true'
    fake_true.write_text('#!/bin/sh\nexit 97\n')
    fake_true.chmod(0o755)
    unshare = '/usr/bin/unshare'
    if Path(unshare).exists():
        ambient = subprocess.run([unshare, '--user', '--map-root-user', 'true'], env={{**os.environ, 'PATH': str(poison) + ':' + TRUSTED}}, text=True, capture_output=True)
        pinned = subprocess.run([unshare, '--user', '--map-root-user', 'true'], env={{'PATH': TRUSTED}}, text=True, capture_output=True)
        results['native_unshare'] = {{'ambient_rc': ambient.returncode, 'ambient_stderr': ambient.stderr, 'pinned_rc': pinned.returncode, 'pinned_stderr': pinned.stderr}}
    else:
        results['native_unshare'] = {{'unverifiable': 'unshare missing'}}

    def runner_observations(label, root):
        mod = load(label + '_runner', root / 'scripts/governance/run_nats_live_production_matrix.py')
        out = {{}}
        saved = os.environ.copy()
        try:
            os.environ['DHARMA_NATS_HOST_MODE'] = 'bogus'
            os.environ['DHARMA_MATRIX_MODEL_TIMEOUT'] = '90'
            try:
                args = mod.parse_args([])
                out['invalid_host_mode'] = {{'accepted': True, 'resolved': args.host_mode, 'branch': 'non-live' if args.host_mode == 'non-live' else 'live'}}
            except SystemExit as exc:
                out['invalid_host_mode'] = {{'accepted': False, 'exit': exc.code}}
            os.environ['DHARMA_NATS_HOST_MODE'] = 'non-live'
            os.environ['DHARMA_MATRIX_MODEL_TIMEOUT'] = 'not-a-number'
            try:
                args = mod.parse_args([])
                out['bad_timeout_non_live'] = {{'parsed': True, 'value': args.model_timeout}}
            except Exception as exc:
                out['bad_timeout_non_live'] = {{'parsed': False, 'type': type(exc).__name__, 'message': str(exc)}}
            os.environ['DHARMA_NATS_HOST_MODE'] = 'live'
            os.environ['DHARMA_MATRIX_MODEL_TIMEOUT'] = '90'
            args = mod.parse_args([])
            out['env_live_command_argv'] = list(args.command_argv)
        finally:
            os.environ.clear(); os.environ.update(saved)
        return out

    results['runner_base'] = runner_observations('base', BASE)
    results['runner_head'] = runner_observations('head', HEAD)
    assert results['runner_base']['invalid_host_mode']['accepted'] is True
    assert results['runner_base']['invalid_host_mode']['branch'] == 'live'
    assert results['runner_head']['invalid_host_mode']['accepted'] is False
    assert results['runner_base']['bad_timeout_non_live']['parsed'] is False
    assert results['runner_base']['bad_timeout_non_live']['type'] == 'ValueError'
    assert results['runner_head']['bad_timeout_non_live']['parsed'] is True
    assert '--host-mode' not in results['runner_base']['env_live_command_argv']
    assert results['runner_head']['env_live_command_argv'][-2:] == ['--host-mode', 'live']

    def checker_case(mod, command):
        mod.SOURCE_FRESHNESS_PATHS = []
        try:
            mod.validate_source_freshness({{'command': command}}, generated_at=datetime.now(UTC), source_grace_seconds=2, repo_root=Path('.'))
            return {{'accepted': True}}
        except Exception as exc:
            return {{'accepted': False, 'type': type(exc).__name__, 'message': str(exc)}}

    base_check = load('base_checker', BASE / 'scripts/governance/check_nats_live_production_evidence.py')
    head_check = load('head_checker', HEAD / 'scripts/governance/check_nats_live_production_evidence.py')
    commands = {{
        'repeated_last_live': ['python', 'run_nats_live_production_matrix.py', '--host-mode', 'non-live', '--host-mode', 'live'],
        'equals_live': ['python', 'run_nats_live_production_matrix.py', '--host-mode=live'],
        'repeated_last_non_live': ['python', 'run_nats_live_production_matrix.py', '--host-mode', 'live', '--host-mode', 'non-live'],
    }}
    results['checker_base'] = {{k: checker_case(base_check, v) for k, v in commands.items()}}
    results['checker_head'] = {{k: checker_case(head_check, v) for k, v in commands.items()}}
    assert results['checker_base']['repeated_last_live']['accepted'] is False
    assert results['checker_head']['repeated_last_live']['accepted'] is True
    assert results['checker_base']['equals_live']['accepted'] is False
    assert results['checker_head']['equals_live']['accepted'] is True
    assert results['checker_base']['repeated_last_non_live']['accepted'] is True
    assert results['checker_head']['repeated_last_non_live']['accepted'] is False
    print(json.dumps(results, indent=2, sort_keys=True))
    """,
)
run_case("five bug-fix base/head reproductions", ["python", str(bug_probe)])
honesty_probe = write_probe(
    "needs_host_honesty",
    f"""
    import importlib.util, json, sys, tempfile
    from datetime import UTC, datetime, timedelta
    from pathlib import Path
    import pytest

    test_path = Path({str(REPO)!r}) / 'tests/test_nats_live_production_evidence.py'
    spec = importlib.util.spec_from_file_location('honesty_test_helpers', test_path)
    helpers = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = helpers
    assert spec and spec.loader
    spec.loader.exec_module(helpers)
    mod = helpers._MODULE
    results = {{}}
    missing_root = Path(tempfile.mkdtemp(prefix='needs-host-missing-'))
    for host_mode in ('non-live', 'live'):
        a = mod.evaluate_evidence(missing_root / 'absent.json', host_mode=host_mode, max_age_hours=24, source_grace_seconds=2)
        results['absent_' + host_mode] = {{'verdict': a.verdict, 'exit_code': a.exit_code, 'reason': a.reason}}

    def evaluate(name, mutation):
        mp = pytest.MonkeyPatch()
        root = Path(tempfile.mkdtemp(prefix='needs-host-state-'))
        try:
            payload = helpers._full_valid_payload(root, mp)
            mutation(payload)
            path = root / (name + '.json')
            path.write_text(json.dumps(payload), encoding='utf-8')
            a = mod.evaluate_evidence(
                path,
                host_mode='live',
                max_age_hours=24,
                source_grace_seconds=2,
                expected_broker_url='nats://daemon.internal:4222',
                expected_broker_profile='daemon-production',
                repo_root=root,
            )
            results[name] = {{'verdict': a.verdict, 'exit_code': a.exit_code, 'reason': a.reason}}
        finally:
            mp.undo()

    evaluate('valid_control', lambda p: None)
    evaluate('stale', lambda p: p.__setitem__('generated_at', helpers._iso(datetime.now(UTC) - timedelta(days=3))))
    evaluate('non_live_payload', lambda p: p.__setitem__('host_mode', 'non-live'))
    evaluate('forged_command', lambda p: p.__setitem__('command', ['python', 'evil.py', '--host-mode', 'live']))
    def tamper(p):
        first = next(iter(p['source_fingerprints']))
        p['source_fingerprints'][first]['sha256'] = '0' * 64
    evaluate('tampered_fingerprint', tamper)
    assert results['absent_non-live']['verdict'] == mod.VERDICT_NEEDS_HOST
    assert results['absent_non-live']['exit_code'] != mod.EXIT_PASS
    assert results['absent_live']['verdict'] == mod.VERDICT_FAIL
    assert results['valid_control']['verdict'] == mod.VERDICT_PASS
    for key in ('stale', 'non_live_payload', 'forged_command', 'tampered_fingerprint'):
        assert results[key]['verdict'] != mod.VERDICT_PASS, (key, results[key])
        assert results[key]['exit_code'] != mod.EXIT_PASS, (key, results[key])
    print(json.dumps(results, indent=2, sort_keys=True))
    """,
)
run_case("NEEDS_HOST and forged evidence honesty battery", ["python", str(honesty_probe)])
run_case("changed files", ["git", "diff", "--name-status", f"{ARGS.base_sha}..{ARGS.target_sha}"])
run_case("workflow diff", ["git", "diff", "--unified=120", f"{ARGS.base_sha}..{ARGS.target_sha}", "--", ".github/workflows/"])
run_case("active track criteria unchanged", ["git", "diff", "--exit-code", f"{ARGS.base_sha}..{ARGS.target_sha}", "--", "docs/governance/ACTIVE_TRACK.yaml"])
run_case("reconciliation receipt unchanged", ["git", "diff", "--exit-code", f"{ARGS.base_sha}..{ARGS.target_sha}", "--", "reports/governance/titanium/phase0_reconciliation_2026-07-25.json"])
run_case("blocked operator diff search", f"git diff {ARGS.base_sha}..{ARGS.target_sha} | rg -n 'BLOCKED_OPERATOR|exposure verdict|NEEDS_HOST|completion_criteria' || true", expectation="any")
run_case("workflow false-green added-line scan", f"git diff --unified=0 {ARGS.base_sha}..{ARGS.target_sha} -- .github/workflows/ | rg -n '^\\+.*(continue-on-error|\\|\\| true)' && exit 1 || exit 0")
run_case("workflow removed-step scan", f"git diff --unified=0 {ARGS.base_sha}..{ARGS.target_sha} -- .github/workflows/ | rg -n '^-[[:space:]]*(- name:|uses:|run:|pull_request:|merge_group:)' || true", expectation="any")
run_case("git diff check", ["git", "diff", "--check", f"{ARGS.base_sha}..{ARGS.target_sha}"])
run_case("final worktree clean", ["git", "status", "--porcelain"])
run_case("remove merge-base worktree", ["git", "worktree", "remove", "--force", str(base_worktree)], expectation="any")
summary = {
    "schema": "dharma.titanium.phase0_premerge_triple_check.raw.v1",
    "observed_at": datetime.now(UTC).isoformat(),
    "target_sha": ARGS.target_sha,
    "base_sha": ARGS.base_sha,
    "reviewer": "OpenAI GPT-5.6 Pro via ephemeral GitHub Actions clean runner",
    "environment": {
        "uid": os.getuid(),
        "euid": os.geteuid(),
        "python": sys.version,
        "py_path_present": "PYTHONPATH" in BASE_ENV,
        "stubs": {k: BASE_ENV[k] for k in ("OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "TINY_ROUTER_BACKEND", "DHARMA_EVOLUTION_SHADOW", "DGC_AUTONOMY_LEVEL")},
    },
    "cases": CASES,
    "unexpected": [c for c in CASES if not c.get("expectation_met", True)],
}
(OUT / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
print(json.dumps({"total": len(CASES), "unexpected": len(summary["unexpected"])}, sort_keys=True))
raise SystemExit(1 if summary["unexpected"] else 0)
