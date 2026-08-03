"""The organism liveness sentinel must fail loudly, write receipts, and
stay silent on --dry-run."""

from __future__ import annotations

import json
from pathlib import Path

import scripts.runtime.organism_liveness_sentinel as sentinel
from scripts.runtime.organism_liveness_sentinel import CheckResult, run_sentinel


def _ok(name: str) -> CheckResult:
    return CheckResult(name=name, ok=True, detail="ok")


def _patch_healthy(monkeypatch) -> None:
    monkeypatch.setattr(
        sentinel, "check_launchd_service", lambda label=None: _ok("launchd_service")
    )
    monkeypatch.setattr(
        sentinel, "check_orchestrate_process", lambda pid: _ok("orchestrate_process")
    )


def test_all_green_writes_baseline_and_exits_zero(monkeypatch, tmp_path: Path) -> None:
    _patch_healthy(monkeypatch)
    err_log = tmp_path / "logs" / "swarm.err"
    err_log.parent.mkdir(parents=True)
    err_log.write_text("admission denied: x\n" * 3, encoding="utf-8")

    rc = run_sentinel(state_root=tmp_path, dry_run=False)

    assert rc == 0
    baseline = tmp_path / "witness" / "liveness_sentinel" / "denial_baseline.json"
    assert json.loads(baseline.read_text())["denial_count"] == 3
    receipts = list((tmp_path / "witness" / "liveness_sentinel").glob("ORGANISM_DOWN_*"))
    assert receipts == []


def test_denial_growth_fails_loudly_with_receipt(monkeypatch, tmp_path: Path) -> None:
    _patch_healthy(monkeypatch)
    sentinel_dir = tmp_path / "witness" / "liveness_sentinel"
    sentinel_dir.mkdir(parents=True)
    (sentinel_dir / "denial_baseline.json").write_text(
        json.dumps({"denial_count": 3}), encoding="utf-8"
    )
    err_log = tmp_path / "logs" / "swarm.err"
    err_log.parent.mkdir(parents=True)
    err_log.write_text("admission denied: x\n" * 588, encoding="utf-8")

    rc = run_sentinel(state_root=tmp_path, dry_run=False)

    assert rc == 1
    receipts = list(sentinel_dir.glob("ORGANISM_DOWN_*.json"))
    assert len(receipts) == 1
    payload = json.loads(receipts[0].read_text())
    assert payload["verdict"] == "ORGANISM_DOWN"
    denial_check = next(
        c for c in payload["checks"] if c["name"] == "admission_denials"
    )
    assert denial_check["ok"] is False
    assert denial_check["evidence"]["denial_count"] == 588


def test_dead_service_fails_and_writes_receipt(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        sentinel,
        "check_launchd_service",
        lambda label=None: CheckResult(
            name="launchd_service", ok=False, detail="service NOT loaded"
        ),
    )
    monkeypatch.setattr(
        sentinel,
        "check_orchestrate_process",
        lambda pid: CheckResult(
            name="orchestrate_process", ok=False, detail="no live process"
        ),
    )

    rc = run_sentinel(state_root=tmp_path, dry_run=False)

    assert rc == 1
    receipts = list(
        (tmp_path / "witness" / "liveness_sentinel").glob("ORGANISM_DOWN_*.json")
    )
    assert len(receipts) == 1


def test_denial_alarm_clears_once_the_count_stops_growing(
    monkeypatch, tmp_path: Path
) -> None:
    """The runaway-alarm regression: a failed run must still advance the
    baseline, so a handled burst does not re-fire forever."""
    _patch_healthy(monkeypatch)
    ticks = iter(f"2026-08-03T00:0{n}:00Z" for n in range(9))
    monkeypatch.setattr(sentinel, "_utc_now", lambda: next(ticks))
    err_log = tmp_path / "logs" / "swarm.err"
    err_log.parent.mkdir(parents=True)
    sentinel_dir = tmp_path / "witness" / "liveness_sentinel"
    baseline = sentinel_dir / "denial_baseline.json"

    # Run 1: healthy, records baseline 1.
    err_log.write_text("admission denied: x\n", encoding="utf-8")
    assert run_sentinel(state_root=tmp_path, dry_run=False) == 0
    assert json.loads(baseline.read_text())["denial_count"] == 1

    # Run 2: the burst. Fails loudly AND records what it saw.
    err_log.write_text("admission denied: x\n" * 588, encoding="utf-8")
    assert run_sentinel(state_root=tmp_path, dry_run=False) == 1
    assert len(list(sentinel_dir.glob("ORGANISM_DOWN_*.json"))) == 1
    recorded = json.loads(baseline.read_text())
    assert recorded["denial_count"] == 588
    assert recorded["observed_under_verdict"] == "ORGANISM_DOWN"

    # Run 3: nothing new appended. The sentinel must return to green rather
    # than scream at the same 588 forever.
    assert run_sentinel(state_root=tmp_path, dry_run=False) == 0
    assert len(list(sentinel_dir.glob("ORGANISM_DOWN_*.json"))) == 1

    # Run 4: growth resumes -> it fires again. Recovery must not deafen it.
    err_log.write_text("admission denied: x\n" * 600, encoding="utf-8")
    assert run_sentinel(state_root=tmp_path, dry_run=False) == 1
    assert len(list(sentinel_dir.glob("ORGANISM_DOWN_*.json"))) == 2


def test_baseline_advance_never_launders_a_dead_service(
    monkeypatch, tmp_path: Path
) -> None:
    """Negative control: the denial baseline is independent of checks 1-2, so
    a stable denial count cannot turn a dead organism green."""
    monkeypatch.setattr(
        sentinel,
        "check_launchd_service",
        lambda label=None: CheckResult(
            name="launchd_service", ok=False, detail="service NOT loaded"
        ),
    )
    monkeypatch.setattr(
        sentinel, "check_orchestrate_process", lambda pid: _ok("orchestrate_process")
    )
    err_log = tmp_path / "logs" / "swarm.err"
    err_log.parent.mkdir(parents=True)
    err_log.write_text("admission denied: x\n" * 5, encoding="utf-8")

    assert run_sentinel(state_root=tmp_path, dry_run=False) == 1
    assert run_sentinel(state_root=tmp_path, dry_run=False) == 1
    receipts = list(
        (tmp_path / "witness" / "liveness_sentinel").glob("ORGANISM_DOWN_*.json")
    )
    assert len(receipts) >= 1


def test_scan_matches_console_script_launch_form(monkeypatch) -> None:
    """The plist spelling (`dgc orchestrate-live`) must be seen as alive."""
    ps_output = "\n".join(
        [
            "  501 /sbin/launchd",
            "  777 /Users/dhyana/dharma_swarm/.venv/bin/python "
            "/Users/dhyana/dharma_swarm/.venv/bin/dgc orchestrate-live",
            "  888 /usr/bin/vim notes.txt",
        ]
    )

    class FakeProc:
        returncode = 0
        stdout = ps_output
        stderr = ""

    monkeypatch.setattr(
        sentinel.subprocess, "run", lambda *a, **kw: FakeProc()
    )
    monkeypatch.setattr(sentinel, "_pid_alive", lambda pid: True)

    found, error = sentinel.scan_orchestrate_processes()
    assert error is None
    assert [pid for pid, _ in found] == [777]

    result = sentinel.check_orchestrate_process(777)
    assert result.ok is True
    assert result.evidence["live_pids"] == [777]


def test_scan_matches_module_launch_form(monkeypatch) -> None:
    """The release-runner spelling must keep working too."""
    ps_output = (
        "  901 /Users/dhyana/dharma_releases/x/.venv/bin/python -B -I "
        "-m dharma_swarm.dgc_cli orchestrate-live"
    )

    class FakeProc:
        returncode = 0
        stdout = ps_output
        stderr = ""

    monkeypatch.setattr(sentinel.subprocess, "run", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(sentinel, "_pid_alive", lambda pid: True)

    found, error = sentinel.scan_orchestrate_processes()
    assert error is None
    assert [pid for pid, _ in found] == [901]


def test_scan_reports_down_when_nothing_matches(monkeypatch) -> None:
    class FakeProc:
        returncode = 0
        stdout = "  888 /usr/bin/vim notes.txt"
        stderr = ""

    monkeypatch.setattr(sentinel.subprocess, "run", lambda *a, **kw: FakeProc())

    result = sentinel.check_orchestrate_process(None)
    assert result.ok is False
    assert "no live process matches" in result.detail


# --- three-state launchd probe: "could not run" != "service is absent" -----


class _FakeProc:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _launchctl_raises(exc: BaseException):
    def _run(*_a, **_kw):
        raise exc

    return _run


def test_missing_launchctl_is_not_evidence_of_death(monkeypatch) -> None:
    """Linux/container hosts have no launchctl. That is not a dead organism.

    `Dockerfile.swarm` runs `python -m dharma_swarm.orchestrate_live` — a form
    this sentinel explicitly claims to watch — on python:3.12-slim, where the
    launchctl binary does not exist.
    """
    monkeypatch.setattr(
        sentinel.subprocess,
        "run",
        _launchctl_raises(FileNotFoundError("No such file or directory: 'launchctl'")),
    )

    result = sentinel.check_launchd_service()

    assert result.ok is None
    assert result.evidence["state"] == "unknown"
    assert "could not run" in result.detail


def test_launchctl_timeout_is_not_evidence_of_death(monkeypatch) -> None:
    monkeypatch.setattr(
        sentinel.subprocess,
        "run",
        _launchctl_raises(sentinel.subprocess.TimeoutExpired(cmd="launchctl", timeout=15)),
    )

    result = sentinel.check_launchd_service()

    assert result.ok is None
    assert result.evidence["state"] == "unknown"


def test_launchctl_answering_not_loaded_is_still_a_loud_fail(monkeypatch) -> None:
    """Negative control: the 2026-07-28 bootout shape must stay ok=False.

    Verbatim from `launchctl print gui/501/com.dharma.swarm` on the hub Mac
    with the service booted out.
    """
    monkeypatch.setattr(
        sentinel.subprocess,
        "run",
        lambda *a, **kw: _FakeProc(
            113,
            stderr='Bad request.\nCould not find service "com.dharma.swarm" '
            "in domain for user gui: 501",
        ),
    )

    result = sentinel.check_launchd_service()

    assert result.ok is False
    assert result.evidence["state"] == "absent"


def test_missing_gui_domain_is_not_a_death_certificate(monkeypatch) -> None:
    """rc=112 answers about the DOMAIN, not the service.

    Verbatim from `launchctl print gui/99999/com.dharma.swarm`. A caller
    outside the GUI session (ssh, system-context daemon) gets this shape;
    reading it as "the service is gone" was a false ORGANISM_DOWN.
    """
    monkeypatch.setattr(
        sentinel.subprocess,
        "run",
        lambda *a, **kw: _FakeProc(
            112, stderr="Bad request.\nCould not find domain for user gui: 99999"
        ),
    )

    result = sentinel.check_launchd_service()

    assert result.ok is None
    assert result.evidence["state"] == "unknown"


def test_domain_error_still_screams_when_the_process_is_dead(
    monkeypatch, tmp_path: Path
) -> None:
    """Purpose guard for the rc=112 concession: check 2 remains the authority."""
    monkeypatch.setattr(
        sentinel,
        "check_launchd_service",
        lambda label=None: CheckResult(
            name="launchd_service",
            ok=None,
            detail="domain error",
            evidence={"state": "unknown"},
        ),
    )
    monkeypatch.setattr(
        sentinel,
        "check_orchestrate_process",
        lambda pid: CheckResult(
            name="orchestrate_process", ok=False, detail="no live process"
        ),
    )

    assert run_sentinel(state_root=tmp_path, dry_run=False) == 1


def test_unknown_launchd_probe_never_launders_a_dead_organism(
    monkeypatch, tmp_path: Path
) -> None:
    """THE purpose guard: no-launchctl + no process must still scream.

    Making check 1 non-evidence must not open a route back to the quiet PASS.
    With the launchd probe unable to run and nothing matching any
    orchestrate-live command form, the verdict is still ORGANISM_DOWN, the
    receipt is still written, and the exit code is still 1.
    """
    monkeypatch.setattr(
        sentinel,
        "check_launchd_service",
        lambda label=None: CheckResult(
            name="launchd_service",
            ok=None,
            detail="launchctl probe could not run",
            evidence={"state": "unknown"},
        ),
    )
    monkeypatch.setattr(
        sentinel,
        "check_orchestrate_process",
        lambda pid: CheckResult(
            name="orchestrate_process", ok=False, detail="no live process"
        ),
    )

    rc = run_sentinel(state_root=tmp_path, dry_run=False)

    assert rc == 1
    receipts = list(
        (tmp_path / "witness" / "liveness_sentinel").glob("ORGANISM_DOWN_*.json")
    )
    assert len(receipts) == 1
    payload = json.loads(receipts[0].read_text())
    assert payload["verdict"] == "ORGANISM_DOWN"
    assert payload["non_evidence_checks"] == ["launchd_service"]


def test_healthy_container_host_does_not_false_alarm(monkeypatch, tmp_path: Path) -> None:
    """The regression this fix closes: alive process, no launchctl -> quiet."""
    monkeypatch.setattr(
        sentinel,
        "check_launchd_service",
        lambda label=None: CheckResult(
            name="launchd_service",
            ok=None,
            detail="launchctl probe could not run",
            evidence={"state": "unknown"},
        ),
    )
    monkeypatch.setattr(
        sentinel, "check_orchestrate_process", lambda pid: _ok("orchestrate_process")
    )
    err_log = tmp_path / "logs" / "swarm.err"
    err_log.parent.mkdir(parents=True)
    err_log.write_text("", encoding="utf-8")

    rc = run_sentinel(state_root=tmp_path, dry_run=False, err_log=err_log)

    assert rc == 0
    assert list((tmp_path / "witness" / "liveness_sentinel").glob("ORGANISM_DOWN_*")) == []


def test_ps_probe_failure_is_fail_closed_not_unknown(monkeypatch) -> None:
    """The asymmetry is deliberate: no launchctl is 'unknown', no ps is DOWN.

    Verified with `docker run --rm python:3.12-slim`: that image ships
    neither `launchctl` nor `ps`. If an unreadable process table were also
    demoted to non-evidence, such a host would fall through to the denial
    counter alone — which passes on an empty log — and the sentinel would
    report OK while having established nothing. Blindness is not health.
    """
    monkeypatch.setattr(
        sentinel.subprocess,
        "run",
        _launchctl_raises(FileNotFoundError("No such file or directory: 'ps'")),
    )

    result = sentinel.check_orchestrate_process(None)

    assert result.ok is False
    assert "refusing to report health" in result.detail


def test_host_with_neither_launchctl_nor_ps_reports_down_not_ok(
    monkeypatch, tmp_path: Path
) -> None:
    """End state of the asymmetry above, through the real verdict path."""
    monkeypatch.setattr(
        sentinel.subprocess,
        "run",
        _launchctl_raises(FileNotFoundError("binary absent")),
    )
    err_log = tmp_path / "logs" / "swarm.err"
    err_log.parent.mkdir(parents=True)
    err_log.write_text("", encoding="utf-8")

    rc = run_sentinel(state_root=tmp_path, dry_run=False, err_log=err_log)

    assert rc == 1
    receipts = list(
        (tmp_path / "witness" / "liveness_sentinel").glob("ORGANISM_DOWN_*.json")
    )
    assert len(receipts) == 1
    payload = json.loads(receipts[0].read_text())
    # launchd is non-evidence; the unreadable process table is what convicts.
    assert payload["non_evidence_checks"] == ["launchd_service"]
    process_check = next(
        c for c in payload["checks"] if c["name"] == "orchestrate_process"
    )
    assert process_check["ok"] is False


def test_no_evidence_at_all_is_fail_closed() -> None:
    """Every probe unknown is silence, and silence is what this sentinel kills."""
    unknown = [
        CheckResult(name=n, ok=None, detail="probe could not run")
        for n in ("launchd_service", "orchestrate_process", "admission_denials")
    ]

    assert sentinel._verdict_ok(unknown) is False


def test_verdict_ignores_unknown_but_honours_every_real_answer() -> None:
    assert sentinel._verdict_ok(
        [CheckResult("a", None, ""), CheckResult("b", True, "")]
    ) is True
    assert sentinel._verdict_ok(
        [CheckResult("a", None, ""), CheckResult("b", False, "")]
    ) is False


def test_sentinel_and_doctor_agree_that_a_missing_probe_is_not_evidence(
    monkeypatch,
) -> None:
    """Pin the two liveness surfaces to one convention (they cannot import
    each other: the sentinel is stdlib-only by design)."""
    from dharma_swarm import doctor

    monkeypatch.setattr(
        sentinel.subprocess,
        "run",
        _launchctl_raises(FileNotFoundError("launchctl")),
    )
    monkeypatch.setattr(
        doctor.subprocess,
        "run",
        _launchctl_raises(FileNotFoundError("launchctl")),
    )

    assert sentinel.check_launchd_service().evidence["state"] == "unknown"
    assert doctor._launchd_service_state(5.0)[0] == "unknown"


def test_dry_run_writes_nothing_but_reports_failure(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        sentinel,
        "check_launchd_service",
        lambda label=None: CheckResult(
            name="launchd_service", ok=False, detail="service NOT loaded"
        ),
    )
    monkeypatch.setattr(
        sentinel,
        "check_orchestrate_process",
        lambda pid: CheckResult(
            name="orchestrate_process", ok=False, detail="no live process"
        ),
    )

    rc = run_sentinel(state_root=tmp_path, dry_run=True)

    assert rc == 1
    assert not (tmp_path / "witness").exists()
