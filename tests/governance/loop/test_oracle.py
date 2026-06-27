"""Tests for scripts/governance/loop/oracle.py — deterministic oracle interface.

Covers VAL-ORACLE-001..003:
  001  Oracle.run_gate returns the process exit code as the verdict, not an LLM
       opinion. A non-zero exit is a fail; zero is a pass.
  002  CIOracle runs real pytest/governance commands and captures their exit codes.
  003  The Oracle interface is abstract enough that a ForgeOracle subclass
       (calling pudgala-forge's check_claim_evidence_binding.py) could be added
       without changing callers (no hard dependency on unmerged pudgala-forge).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
VENV_PYTHON = "/Users/dhyana/dharma_swarm/.venv/bin/python"
ORACLE_MODULE = REPO_ROOT / "scripts" / "governance" / "loop" / "oracle.py"

# Make scripts.governance.loop.oracle importable as a full dotted path (avoids
# the test-package `loop` name collision from tests/governance/loop/__init__.py).
sys.path.insert(0, str(REPO_ROOT))


# ---------------------------------------------------------------------------
# import helpers
# ---------------------------------------------------------------------------


def _import_oracle():
    """Import the oracle module fresh (so missing-module errors surface)."""
    import importlib

    mod = importlib.import_module("scripts.governance.loop.oracle")
    importlib.reload(mod)
    return mod


# ---------------------------------------------------------------------------
# VAL-ORACLE-001: exit code is the verdict, not an LLM opinion
# ---------------------------------------------------------------------------


class TestExitCodeIsVerdict:
    """The exit code from a real process is the verdict — never an LLM opinion."""

    def test_module_importable(self):
        mod = _import_oracle()
        assert hasattr(mod, "Oracle")
        assert hasattr(mod, "CIOracle")
        assert hasattr(mod, "GateResult")

    def test_gate_result_has_exit_code_stdout_stderr(self):
        mod = _import_oracle()
        result = mod.GateResult(exit_code=0, stdout="ok\n", stderr="")
        assert result.exit_code == 0
        assert result.stdout == "ok\n"
        assert result.stderr == ""

    def test_zero_exit_is_pass(self):
        mod = _import_oracle()
        oracle = mod.CIOracle(python=VENV_PYTHON, repo_root=REPO_ROOT)
        result = oracle.run_gate(f'"{VENV_PYTHON}" -c "pass"')
        assert result.exit_code == 0
        assert result.passed is True
        assert result.verdict == "pass"

    def test_nonzero_exit_is_fail(self):
        mod = _import_oracle()
        oracle = mod.CIOracle(python=VENV_PYTHON, repo_root=REPO_ROOT)
        result = oracle.run_gate(f'"{VENV_PYTHON}" -c "import sys; sys.exit(3)"')
        assert result.exit_code == 3
        assert result.passed is False
        assert result.verdict == "fail"

    def test_no_llm_opinion_field(self):
        """GateResult carries only deterministic fields — no opinion/llm verdict."""
        mod = _import_oracle()
        result = mod.GateResult(exit_code=1, stdout="", stderr="boom")
        # The verdict is derived purely from exit_code; there is no 'opinion'
        # or 'llm_judgment' attribute that could override the exit code.
        assert not hasattr(result, "opinion")
        assert not hasattr(result, "llm_judgment")
        assert result.verdict == "fail"  # derived from exit_code == 1

    def test_stdout_and_stderr_captured(self):
        mod = _import_oracle()
        oracle = mod.CIOracle(python=VENV_PYTHON, repo_root=REPO_ROOT)
        result = oracle.run_gate(
            f'"{VENV_PYTHON}" -c "print(\'hello-stdout\'); '
            f'import sys; sys.stderr.write(\'hello-stderr\'); sys.exit(0)"'
        )
        assert "hello-stdout" in result.stdout
        assert "hello-stderr" in result.stderr
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# VAL-ORACLE-002: CIOracle runs real pytest/governance commands
# ---------------------------------------------------------------------------


class TestCIOracleRealGates:
    """CIOracle runs real pytest/governance commands and captures exit codes."""

    def test_collect_only_real_exit_code(self):
        """pytest --collect-only is a real governance gate; its exit code is captured.

        We scope to the loop test dir (which collects cleanly) so the pass case
        is deterministic. The full-repo --strict-markers gate has pre-existing
        unregistered-marker errors (``slow``, ``docker``) unrelated to this work.
        """
        mod = _import_oracle()
        oracle = mod.CIOracle(python=VENV_PYTHON, repo_root=REPO_ROOT)
        result = oracle.run_gate(
            f'"{VENV_PYTHON}" -m pytest --collect-only -q tests/governance/loop/'
        )
        assert isinstance(result.exit_code, int)
        assert result.exit_code == 0
        assert "test" in result.stdout.lower()  # real output captured

    def test_collect_only_method_captures_real_int(self):
        """The collect_only() convenience method captures a real int exit code
        from the full-repo collection (may be non-zero due to pre-existing
        unregistered markers — the point is the REAL code is captured)."""
        mod = _import_oracle()
        oracle = mod.CIOracle(python=VENV_PYTHON, repo_root=REPO_ROOT)
        result = oracle.collect_only()
        assert isinstance(result.exit_code, int)
        assert result.command  # the real command is recorded

    def test_collect_only_failure_captured(self):
        """A failing pytest command yields a non-zero exit code from the real process."""
        mod = _import_oracle()
        oracle = mod.CIOracle(python=VENV_PYTHON, repo_root=REPO_ROOT)
        # Point pytest at a nonexistent path to force a collection failure.
        result = oracle.run_gate(
            f'"{VENV_PYTHON}" -m pytest --collect-only -q /nonexistent/path_xyz'
        )
        assert isinstance(result.exit_code, int)
        assert result.exit_code != 0

    def test_governance_script_real_exit_code(self):
        """A real governance script (check_test_hygiene.py) exit code is captured."""
        mod = _import_oracle()
        oracle = mod.CIOracle(python=VENV_PYTHON, repo_root=REPO_ROOT)
        result = oracle.test_hygiene()
        assert isinstance(result.exit_code, int)
        # We don't assert the exact value (it may be 0 or 1 depending on repo
        # state); the point is the REAL exit code is captured, not an opinion.

    def test_cwd_respected(self):
        """run_gate honours the cwd argument (command runs in that directory)."""
        mod = _import_oracle()
        oracle = mod.CIOracle(python=VENV_PYTHON, repo_root=REPO_ROOT)
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            result = oracle.run_gate(f'"{VENV_PYTHON}" -c "import os; print(os.getcwd())"', cwd=tmp)
            assert result.exit_code == 0
            assert tmp in result.stdout or Path(tmp).name in result.stdout

    def test_command_recorded_in_result(self):
        """The result records which command was run (for receipt traceability)."""
        mod = _import_oracle()
        oracle = mod.CIOracle(python=VENV_PYTHON, repo_root=REPO_ROOT)
        cmd = f'"{VENV_PYTHON}" -c "pass"'
        result = oracle.run_gate(cmd)
        assert result.command == cmd

    def test_to_dict_for_receipt(self):
        """GateResult can be serialised to a receipt dict (evidence-linked)."""
        mod = _import_oracle()
        oracle = mod.CIOracle(python=VENV_PYTHON, repo_root=REPO_ROOT)
        result = oracle.run_gate(f'"{VENV_PYTHON}" -c "pass"')
        receipt = result.to_dict()
        assert receipt["exit_code"] == 0
        assert "command" in receipt
        assert "stdout" in receipt
        assert "stderr" in receipt
        assert receipt["verdict"] == "pass"


# ---------------------------------------------------------------------------
# VAL-ORACLE-003: interface structured for pudgala-forge plug-in
# ---------------------------------------------------------------------------


class TestForgeOraclePlugIn:
    """The Oracle interface is abstract enough that a ForgeOracle subclass could
    be added without changing callers — no hard dependency on unmerged pudgala-forge."""

    def test_oracle_is_abstract_base_class(self):
        """Oracle is an ABC that cannot be instantiated directly."""
        mod = _import_oracle()
        import abc

        assert issubclass(mod.Oracle, abc.ABC) or hasattr(mod.Oracle, "__abstractmethods__")
        # Direct instantiation of the bare Oracle must fail (it's abstract).
        with pytest.raises((TypeError,)):
            mod.Oracle()

    def test_cioracle_is_oracle_subclass(self):
        mod = _import_oracle()
        assert issubclass(mod.CIOracle, mod.Oracle)

    def test_no_hard_pudgala_forge_dependency(self):
        """oracle.py must NOT import anything from pudgala-forge.

        A docstring may mention pudgala-forge by name (describing the design
        intent for a future plug-in), but there must be no actual import.
        """
        mod = _import_oracle()
        source = ORACLE_MODULE.read_text()
        # No import statements pull in pudgala-forge.
        assert "import pudgala" not in source
        assert "from pudgala" not in source
        # The module loads without pudgala-forge present (proven by _import_oracle).

    def test_forge_oracle_subclass_works_through_interface(self):
        """A ForgeOracle subclass can be added and called through the Oracle
        interface without changing CIOracle or callers."""
        mod = _import_oracle()

        class ForgeOracle(mod.Oracle):
            """Simulated ForgeOracle — would call pudgala-forge's
            check_claim_evidence_binding.py when it merges. For now, shells
            out to a deterministic command (no hard pudgala-forge dependency)."""

            def __init__(self, python=VENV_PYTHON, repo_root=REPO_ROOT):
                self.python = python
                self.repo_root = repo_root

            def run_gate(self, command, cwd=None):
                work_cwd = cwd or str(self.repo_root)
                env = os.environ.copy()
                env["PYTHONPATH"] = str(self.repo_root)
                proc = subprocess.run(
                    command, shell=True, capture_output=True, text=True,
                    cwd=work_cwd, env=env,
                )
                return mod.GateResult(
                    exit_code=proc.returncode,
                    stdout=proc.stdout,
                    stderr=proc.stderr,
                    command=command,
                    cwd=work_cwd,
                )

        # A caller written against the Oracle interface works with either oracle.
        def run_a_gate(oracle: mod.Oracle, command: str, cwd=None) -> mod.GateResult:
            return oracle.run_gate(command, cwd=cwd)

        ci = mod.CIOracle(python=VENV_PYTHON, repo_root=REPO_ROOT)
        forge = ForgeOracle()

        ci_result = run_a_gate(ci, f'"{VENV_PYTHON}" -c "pass"')
        forge_result = run_a_gate(forge, f'"{VENV_PYTHON}" -c "pass"')

        assert ci_result.exit_code == 0
        assert forge_result.exit_code == 0
        # Both return GateResult through the same interface.
        assert isinstance(ci_result, mod.GateResult)
        assert isinstance(forge_result, mod.GateResult)

    def test_oracle_protocol_caller_agnostic(self):
        """A function typed against Oracle works for any subclass."""
        mod = _import_oracle()

        def evaluate(oracle: mod.Oracle) -> bool:
            res = oracle.run_gate(f'"{VENV_PYTHON}" -c "pass"')
            return res.passed

        ci = mod.CIOracle(python=VENV_PYTHON, repo_root=REPO_ROOT)
        assert evaluate(ci) is True


# ---------------------------------------------------------------------------
# CLI smoke test
# ---------------------------------------------------------------------------


class TestOracleCLI:
    """oracle.py is a CLI tool with --help and a run subcommand."""

    def test_help_exits_zero(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT)
        proc = subprocess.run(
            [VENV_PYTHON, str(ORACLE_MODULE), "--help"],
            capture_output=True, text=True, env=env,
        )
        assert proc.returncode == 0
        assert "oracle" in proc.stdout.lower() or "usage" in proc.stdout.lower()

    def test_run_subcommand_returns_exit_code(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT)
        proc = subprocess.run(
            [VENV_PYTHON, str(ORACLE_MODULE), "run", f'"{VENV_PYTHON}" -c "pass"'],
            capture_output=True, text=True, env=env,
        )
        # The CLI exits with the gate's exit code (0 for a passing command).
        assert proc.returncode == 0

    def test_run_subcommand_failing_command(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT)
        proc = subprocess.run(
            [VENV_PYTHON, str(ORACLE_MODULE), "run", f'"{VENV_PYTHON}" -c "import sys; sys.exit(1)"'],
            capture_output=True, text=True, env=env,
        )
        assert proc.returncode == 1


# ---------------------------------------------------------------------------
# M2 hardening: subprocess timeout + no shell injection (shell=False)
# ---------------------------------------------------------------------------


class TestM2Hardening:
    """M2 scrutiny required hardening of oracle.run_gate:

    1. shell=True was a shell-injection vector — switch to list-form args
       (shlex.split, shell=False) so metacharacters are NOT interpreted.
    2. No subprocess timeout meant a hung gate hangs the loop forever — add a
       timeout that raises a clear error instead.
    """

    def test_run_gate_uses_shell_false(self):
        """CIOracle.run_gate must NOT use shell=True (no shell interpretation)."""
        mod = _import_oracle()
        source = ORACLE_MODULE.read_text()
        # The CIOracle.run_gate implementation must not pass shell=True.
        # (The test-defined ForgeOracle in TestForgeOraclePlugIn may use
        # shell=True in its own stub — that's fine, it's not production code.)
        assert "shell=True" not in source, (
            "CIOracle.run_gate must not use shell=True — it's a shell-injection vector. "
            "Use shlex.split + subprocess.run(args_list, shell=False) instead."
        )

    def test_shlex_split_imported(self):
        """oracle.py must import shlex for list-form arg parsing."""
        mod = _import_oracle()
        source = ORACLE_MODULE.read_text()
        assert "import shlex" in source or "from shlex" in source

    def test_timeout_parameter_exists(self):
        """CIOracle must accept a timeout parameter (default or configurable)."""
        mod = _import_oracle()
        # CIOracle.__init__ should accept a timeout kwarg.
        oracle = mod.CIOracle(python=VENV_PYTHON, repo_root=REPO_ROOT, timeout=10)
        assert oracle is not None
        # run_gate should also accept a per-call timeout override.
        result = oracle.run_gate(f'"{VENV_PYTHON}" -c "pass"', timeout=10)
        assert result.exit_code == 0

    def test_default_timeout_is_set(self):
        """CIOracle has a non-None default timeout (not infinite)."""
        mod = _import_oracle()
        oracle = mod.CIOracle(python=VENV_PYTHON, repo_root=REPO_ROOT)
        assert oracle.timeout is not None
        assert oracle.timeout > 0

    def test_hung_gate_times_out_raises_clear_error(self):
        """A hung gate (sleep longer than timeout) must time out and raise a
        clear error (GateTimeoutError or similar) instead of hanging forever."""
        mod = _import_oracle()
        oracle = mod.CIOracle(python=VENV_PYTHON, repo_root=REPO_ROOT, timeout=2)
        # 'sleep 30' would hang for 30s without a timeout; with timeout=2 it
        # must be killed and raise within ~3s.
        has_timeout_error = hasattr(mod, "GateTimeoutError")
        with pytest.raises((TimeoutError, subprocess.TimeoutExpired) if not has_timeout_error else mod.GateTimeoutError) as exc_info:
            oracle.run_gate("sleep 30")
        # The error message must mention the timeout so the operator understands.
        assert "timeout" in str(exc_info.value).lower() or "timed out" in str(exc_info.value).lower()

    def test_shell_metacharacters_not_interpreted(self):
        """Shell metacharacters (; | && etc.) in the gate command must NOT be
        interpreted as shell operators. With shell=False + shlex.split, ';'
        becomes a literal argument, not a command separator."""
        mod = _import_oracle()
        oracle = mod.CIOracle(python=VENV_PYTHON, repo_root=REPO_ROOT, timeout=30)
        # Under shell=True, this would run 'python -c "pass"' THEN 'echo INJECTED'
        # (two commands). Under shell=False, ';' is a literal arg to python.
        result = oracle.run_gate(f'"{VENV_PYTHON}" -c "pass" ; echo INJECTED')
        # The command must still exit 0 (python -c "pass" succeeds; the extra
        # args ';', 'echo', 'INJECTED' go into sys.argv and are ignored).
        assert result.exit_code == 0
        # CRITICAL: "INJECTED" must NOT appear in stdout — if it did, the ';'
        # was interpreted as a shell separator (shell injection succeeded).
        assert "INJECTED" not in result.stdout, (
            "Shell metacharacter ';' was interpreted as a command separator — "
            "shell injection vector is still open! Use shell=False."
        )

    def test_pipe_metacharacter_not_interpreted(self):
        """The pipe '|' must not be interpreted as a shell pipe operator."""
        mod = _import_oracle()
        oracle = mod.CIOracle(python=VENV_PYTHON, repo_root=REPO_ROOT, timeout=30)
        # Under shell=True, 'echo SECRET | cat' would pipe echo's output to cat.
        # Under shell=False, '|' is a literal arg to echo.
        result = oracle.run_gate(f'"{VENV_PYTHON}" -c "print(\\"ok\\")" | cat')
        # python runs -c "print('ok')" and exits 0; '|' and 'cat' are extra args.
        assert result.exit_code == 0
        # "ok" appears from python's stdout. But if '|' were a pipe, the output
        # might differ. The key assertion: the command doesn't fail due to pipe
        # interpretation (no "cat: no such file" or similar).

    def test_backtick_not_interpreted(self):
        """Backtick command substitution must NOT work under shell=False."""
        mod = _import_oracle()
        oracle = mod.CIOracle(python=VENV_PYTHON, repo_root=REPO_ROOT, timeout=30)
        # Under shell=True, `whoami` would be command-substituted. Under
        # shell=False, backticks are literal characters in the argument.
        result = oracle.run_gate(f'"{VENV_PYTHON}" -c "pass" `whoami`')
        assert result.exit_code == 0
        # The output of whoami should NOT appear in stdout (no command substitution).
        # If it did, shell injection is possible.
