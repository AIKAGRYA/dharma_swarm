#!/usr/bin/env bash
set -u

LOG=/root/trading_lab/trading_audit_2026-05-04.log
exec > >(tee -a "$LOG") 2>&1

echo "### TRADING-ZOOM AUDIT — AGNI — $(date -u)"
date -u

mask_secret_lines() {
  sed -E 's/(OPENROUTER_API_KEY|ANTHROPIC_API_KEY|CLAUDE_CODE_OAUTH|CODEX[^=[:space:]]*)=([^[:space:]]+)/\1=[REDACTED]/g'
}

echo "### PHASE 0.A: LLM AUTH FIX"
echo "--- which agents use which auth path? capture before any change ---"
grep -rn "OPENROUTER\|ANTHROPIC_API_KEY\|CLAUDE_CODE_OAUTH\|CODEX" /root/agni/ /root/trading_lab/ /root/agent/ --include="*.env" --include="*.json" --include="*.sh" --include="*.py" 2>/dev/null | grep -v ".git/" | head -50 | mask_secret_lines
echo "--- alpha_cycle's specific auth invocation ---"
grep -rn "OPENROUTER\|ANTHROPIC_API\|client.messages\|llm_call" /root/trading_lab/ --include="*.py" 2>/dev/null | head -20 | mask_secret_lines
echo "--- alpha_cycle cron line BEFORE ---"
crontab -l 2>/dev/null | grep -n "alpha_cycle.py\|run_alpha_cycle_env" || true
echo "--- attempt one alpha_cycle A1 LLM call manually with current inherited env, capture exit + stderr ---"
cd /root/trading_lab || exit 1
python3 - << 'PY'
import importlib.util, os, sys
path = "/root/trading_lab/autonomous/alpha_cycle.py"
spec = importlib.util.spec_from_file_location("alpha_cycle_audit", path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
print(f"inherited_OPENROUTER_present={bool(os.environ.get('OPENROUTER_API_KEY'))}")
try:
    out = mod.llm_call('Return exactly JSON: {"ok": true}', max_tokens=30, action="audit_A1_auth_probe_inherited")
    print("inherited_llm_result_present=", bool(out))
    print("inherited_llm_preview=", (out or "")[:160].replace("\n", " "))
    sys.exit(0 if out else 3)
except Exception as exc:
    print("inherited_llm_exception=", repr(exc), file=sys.stderr)
    sys.exit(2)
PY
INHERITED_RC=$?
echo "inherited A1 auth probe exit=$INHERITED_RC"

echo "--- attempt one alpha_cycle A1 LLM call manually after sourcing known env files ---"
set -a
[ -f /root/agni/.env ] && . /root/agni/.env
[ -f /root/trading_lab/.env.runtime ] && . /root/trading_lab/.env.runtime
[ -f /root/.keys/vault.env ] && . /root/.keys/vault.env
set +a
python3 - << 'PY'
import importlib.util, os, sys
path = "/root/trading_lab/autonomous/alpha_cycle.py"
spec = importlib.util.spec_from_file_location("alpha_cycle_audit_sourced", path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
print(f"sourced_OPENROUTER_present={bool(os.environ.get('OPENROUTER_API_KEY'))}")
try:
    out = mod.llm_call('Return exactly JSON: {"ok": true}', max_tokens=30, action="audit_A1_auth_probe_sourced")
    print("sourced_llm_result_present=", bool(out))
    print("sourced_llm_preview=", (out or "")[:160].replace("\n", " "))
    sys.exit(0 if out else 3)
except Exception as exc:
    print("sourced_llm_exception=", repr(exc), file=sys.stderr)
    sys.exit(2)
PY
SOURCED_RC=$?
echo "sourced A1 auth probe exit=$SOURCED_RC"

echo "--- codex re-login state ---"
codex auth status 2>&1 | head -20 || echo "codex CLI not on PATH or different command"

PHASE_0A_VERDICT="HALT — A1 LLM auth still failing"
if [ "$SOURCED_RC" -eq 0 ]; then
  echo "--- installing alpha_cycle env wrapper because sourced env succeeds ---"
  cat > /root/trading_lab/scripts/run_alpha_cycle_env.sh << 'EOF'
#!/usr/bin/env bash
set -euo pipefail
set -a
[ -f /root/agni/.env ] && . /root/agni/.env
[ -f /root/trading_lab/.env.runtime ] && . /root/trading_lab/.env.runtime
[ -f /root/.keys/vault.env ] && . /root/.keys/vault.env
set +a
exec /usr/bin/python3 /root/trading_lab/autonomous/alpha_cycle.py
EOF
  chmod +x /root/trading_lab/scripts/run_alpha_cycle_env.sh
  crontab -l 2>/dev/null > /tmp/agni_cron_before_alpha_auth_fix.txt
  python3 - << 'PY'
from pathlib import Path
before = Path("/tmp/agni_cron_before_alpha_auth_fix.txt")
after = Path("/tmp/agni_cron_after_alpha_auth_fix.txt")
text = before.read_text()
old = "*/30 * * * * /usr/bin/python3 /root/trading_lab/autonomous/alpha_cycle.py >> /root/trading_lab/data/logs/alpha_cycle.log 2>&1"
new = "*/30 * * * * /root/trading_lab/scripts/run_alpha_cycle_env.sh >> /root/trading_lab/data/logs/alpha_cycle.log 2>&1"
if old in text:
    text = text.replace(old, new)
after.write_text(text)
PY
  if ! cmp -s /tmp/agni_cron_before_alpha_auth_fix.txt /tmp/agni_cron_after_alpha_auth_fix.txt; then
    crontab /tmp/agni_cron_after_alpha_auth_fix.txt
  fi
  echo "--- alpha_cycle cron line AFTER ---"
  crontab -l 2>/dev/null | grep -n "alpha_cycle.py\|run_alpha_cycle_env" || true
  echo "--- wrapper content ---"
  sed -n '1,40p' /root/trading_lab/scripts/run_alpha_cycle_env.sh
  PHASE_0A_VERDICT="FIXED — alpha_cycle now uses /root/trading_lab/scripts/run_alpha_cycle_env.sh; A1 OpenRouter probe succeeds when env files are sourced; auth path mapped"
fi
echo "0.A VERDICT: $PHASE_0A_VERDICT"

echo "### PHASE 0.B: KILLED-ROUTE FLATTEN + LIFECYCLE GUARD (STAGED)"
echo "--- where does executor check lifecycle.state today? ---"
grep -rn "lifecycle\." /root/trading_lab/engine/ --include="*.py" 2>/dev/null | grep -E "state|killed|live" | head -20 || true
grep -rn "lifecycle.json\|lifecycle\[" /root/trading_lab/engine/ --include="*.py" 2>/dev/null | head -10 || true
echo "--- list of currently-killed routes holding open positions ---"
python3 << 'EOF'
import json, glob, os
lc = json.load(open('/root/trading_lab/state/lifecycle.json'))
killed_holding = []
for rid, v in lc.items():
    if not isinstance(v, dict) or v.get('state') != 'killed': continue
    cands = glob.glob(f'/root/trading_lab/data/routes/{rid}/') + glob.glob(f'/root/trading_lab/data/routes/{rid}_*/')
    if not cands: continue
    pj = os.path.join(cands[0], 'portfolio.json')
    if not os.path.exists(pj): continue
    p = json.load(open(pj))
    pos = p.get('positions', {}) or {}
    if pos:
        val = sum(abs((v.get('quantity',0) or 0) * (v.get('entry_price',0) or 0)) for v in pos.values() if isinstance(v, dict))
        killed_holding.append((rid, len(pos), val))
print(f'killed routes with open positions: {len(killed_holding)}')
print(f'total exposure: ${sum(x[2] for x in killed_holding):.2f}')
for rid, n, v in sorted(killed_holding, key=lambda x: -x[2])[:10]:
    print(f'  {rid}: {n} positions, ${v:.2f}')
EOF
echo "--- write the flatten script (do NOT execute yet) ---"
mkdir -p /root/trading_lab/proposals/staged
cat > /root/trading_lab/proposals/staged/2026-05-04_flatten_killed_routes.py << 'PY'
#!/usr/bin/env python3
"""Stage T2 market-close orders for killed routes still holding positions.

Default is dry-run. Actual order emission requires:
  --apply --meta-ack ACK-2026-05-04

Writes append-only rows to:
  /root/trading_lab/data/system/paper_mode_changes.jsonl
"""
from __future__ import annotations

import argparse
import glob
import json
import os
from datetime import datetime, timezone
from pathlib import Path

LAB = Path("/root/trading_lab")
LIFECYCLE = LAB / "state" / "lifecycle.json"
OUT = LAB / "data" / "system" / "paper_mode_changes.jsonl"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def route_dir(route_id: str) -> Path | None:
    cands = glob.glob(f"/root/trading_lab/data/routes/{route_id}/")
    cands += glob.glob(f"/root/trading_lab/data/routes/{route_id}_*/")
    return Path(cands[0]) if cands else None


def collect_orders() -> list[dict]:
    lc = json.loads(LIFECYCLE.read_text())
    orders: list[dict] = []
    for route_id, state in sorted(lc.items()):
        if not isinstance(state, dict) or state.get("state") != "killed":
            continue
        rdir = route_dir(route_id)
        if not rdir:
            continue
        pfile = rdir / "portfolio.json"
        if not pfile.exists():
            continue
        portfolio = json.loads(pfile.read_text())
        for pos_id, pos in (portfolio.get("positions") or {}).items():
            if not isinstance(pos, dict):
                continue
            qty = float(pos.get("quantity") or 0)
            entry = float(pos.get("entry_price") or 0)
            if qty == 0:
                continue
            orders.append({
                "ts": now(),
                "tier": "T2",
                "source": "meta_ack_pending",
                "action": "close_position_market",
                "route_id": route_id,
                "route_dir": str(rdir),
                "position_id": pos_id,
                "symbol": pos.get("symbol"),
                "direction": pos.get("direction"),
                "quantity": qty,
                "entry_price": entry,
                "notional_abs": abs(qty * entry),
                "reason": "flatten killed route still holding open paper position",
            })
    return orders


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--meta-ack", default="")
    args = ap.parse_args()
    orders = collect_orders()
    print(json.dumps({"orders": len(orders), "notional_abs": round(sum(o["notional_abs"] for o in orders), 4)}, indent=2))
    for order in orders[:20]:
        print(json.dumps(order, sort_keys=True))
    if not args.apply:
        print("DRY_RUN: no rows written")
        return
    if args.meta_ack != "ACK-2026-05-04":
        raise SystemExit("HALT: --meta-ack ACK-2026-05-04 required")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("a") as handle:
        for order in orders:
            order["source"] = "meta_ack_confirmed"
            order["meta_ack"] = args.meta_ack
            handle.write(json.dumps(order, sort_keys=True) + "\n")
    print(f"WROTE {len(orders)} rows to {OUT}")


if __name__ == "__main__":
    main()
PY
chmod +x /root/trading_lab/proposals/staged/2026-05-04_flatten_killed_routes.py

echo "--- write the lifecycle guard patch (do NOT apply yet) ---"
python3 << 'PY'
from pathlib import Path
import difflib

path = Path("/root/trading_lab/engine/executor.py")
orig = path.read_text()
new = orig
if "def _route_lifecycle_state(" not in new:
    marker = "# ── RouteExecutor"
    helper = '''def _route_lifecycle_state(route_id: str) -> str | None:
    """Return lifecycle.state for a route_id, or None when unavailable."""
    try:
        lifecycle_path = Path("/root/trading_lab/state/lifecycle.json")
        data = json.loads(lifecycle_path.read_text())
        row = data.get(route_id, {})
        if isinstance(row, dict):
            return row.get("state")
    except Exception:
        return None
    return None


'''
    new = new.replace(marker, helper + marker)

needle = '        strategy_name = route_config["strategy"]\n        assets = route_config["assets"]\n'
guard = '''        strategy_name = route_config["strategy"]
        assets = route_config["assets"]

        lifecycle_state = _route_lifecycle_state(route_id)
        if lifecycle_state in ("killed", "retired"):
            msg = f"[{route_id}] REFUSE_MANAGE_LIFECYCLE_STATE: {lifecycle_state}"
            print(f"  {msg}")
            try:
                Path("/root/trading_lab/data/logs/alerts.log").parent.mkdir(parents=True, exist_ok=True)
                with open("/root/trading_lab/data/logs/alerts.log", "a") as handle:
                    handle.write(f"{datetime.now(timezone.utc).isoformat()} {msg}\\n")
            except OSError:
                pass
            return []
'''
if "REFUSE_MANAGE_LIFECYCLE_STATE" not in new:
    new = new.replace(needle, guard)

diff = difflib.unified_diff(
    orig.splitlines(keepends=True),
    new.splitlines(keepends=True),
    fromfile="engine/executor.py",
    tofile="engine/executor.py.lifecycle_guard",
)
Path("/root/trading_lab/proposals/staged/2026-05-04_executor_lifecycle_guard.diff").write_text("".join(diff))
PY

echo "--- show both staged artifacts (paths + first 50 lines of each) ---"
ls -la /root/trading_lab/proposals/staged/2026-05-04_* 2>/dev/null
head -50 /root/trading_lab/proposals/staged/2026-05-04_flatten_killed_routes.py 2>/dev/null
echo "---"
head -50 /root/trading_lab/proposals/staged/2026-05-04_executor_lifecycle_guard.diff 2>/dev/null
echo "0.B VERDICT: STAGED — meta-layer ACK required"

echo "### PHASE 0.C: R01 EXECUTOR LOG GREP SINCE 4/20"
echo "--- which logs cover executor activity? ---"
ls -lat /root/trading_lab/data/logs/*.log 2>/dev/null | head -10
echo "--- R01-specific entries in all logs since 4/20 ---"
for f in /root/trading_lab/data/logs/*.log; do
  matches=$(grep -ic "R01[^v0-9]\| R01 \|^R01_" "$f" 2>/dev/null || true)
  [ "$matches" -gt 0 ] && echo "== $f: $matches matches ==" && grep -i "R01[^v0-9]\| R01 \|^R01_" "$f" 2>/dev/null | tail -10
done
echo "--- did R01's signal generator fire (signal proposed) but get gated, or did it never fire? ---"
grep -i "R01.*signal\|signal.*R01\|R01.*propose\|R01.*entry\|R01.*gate\|R01.*reject" /root/trading_lab/data/logs/*.log 2>/dev/null | tail -20 || true
echo "--- when did the executor last touch R01 portfolio.json or trades.csv? ---"
ls -la /root/trading_lab/data/routes/R01_vwap_btc/portfolio.json /root/trading_lab/data/routes/R01_vwap_btc/trades.csv
echo "--- R01 strategy state file if it exists ---"
find /root -name "*R01*state*" -o -name "*R01*strategy*" 2>/dev/null | head -5
python3 << 'PY'
from pathlib import Path
logs = list(Path("/root/trading_lab/data/logs").glob("*.log"))
hits = []
for p in logs:
    try:
        text = p.read_text(errors="ignore")
    except Exception:
        continue
    low = text.lower()
    if "r01" in low and ("gate" in low or "reject" in low):
        hits.append("gated")
    if "r01" in low and ("signal" in low or "entry" in low or "propose" in low):
        hits.append("signal")
portfolio = Path("/root/trading_lab/data/routes/R01_vwap_btc/portfolio.json")
trades = Path("/root/trading_lab/data/routes/R01_vwap_btc/trades.csv")
if "gated" in hits:
    v = "SIGNAL_FIRED_AND_GATED — gate/reject strings present in logs"
elif "signal" in hits:
    v = "SIGNAL_FIRED_NO_GATE_STRING — inspect tail above"
else:
    v = "SIGNAL_NEVER_FIRED_OR_NO_LOG_EVIDENCE — no R01 signal/gate strings in scanned logs"
print(f"0.C VERDICT: {v}; portfolio_mtime={portfolio.stat().st_mtime if portfolio.exists() else 'missing'} trades_mtime={trades.stat().st_mtime if trades.exists() else 'missing'}")
PY

echo "### PHASE 1: TRADING-ZOOM CRON TABLE"
crontab -l 2>/dev/null > /tmp/cron_lines.txt
ls /etc/cron.d/ /etc/cron.daily/ /etc/cron.hourly/ /etc/cron.weekly/ 2>/dev/null
python3 << 'PY'
from __future__ import annotations

import glob
import json
import os
import re
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

now = datetime.now(timezone.utc)
cron = Path("/tmp/cron_lines.txt").read_text(errors="ignore").splitlines()
active_cron = [l for l in cron if l.strip() and not l.lstrip().startswith("#")]

def dt_from_ts(ts: float | None) -> datetime | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, timezone.utc)

def iso(dt: datetime | None) -> str:
    return dt.isoformat(timespec="seconds") if dt else "NOT_FOUND"

def latest_path(patterns: list[str]) -> tuple[str, datetime | None]:
    files = []
    for pat in patterns:
        files.extend(glob.glob(pat))
    files = [f for f in files if os.path.exists(f)]
    if not files:
        return "NOT_FOUND", None
    f = max(files, key=lambda p: os.path.getmtime(p))
    return f, dt_from_ts(os.path.getmtime(f))

def cron_line(patterns: list[str]) -> str | None:
    pats = [p.lower() for p in patterns]
    for line in active_cron:
        low = line.lower()
        if all(p in low for p in pats):
            return line
    for line in active_cron:
        low = line.lower()
        if any(p in low for p in pats):
            return line
    return None

def schedule_of(line: str | None) -> str:
    if not line:
        return "?"
    parts = line.split()
    if len(parts) < 5:
        return "?"
    return " ".join(parts[:5])

def interval_minutes(schedule: str, default: int | None = None) -> int | None:
    if default:
        return default
    if schedule == "?":
        return None
    fields = schedule.split()
    if len(fields) != 5:
        return None
    minute, hour, dom, mon, dow = fields
    if minute.startswith("*/"):
        try: return int(minute[2:])
        except Exception: return None
    if "," in minute:
        return 60 // len(minute.split(","))
    if minute == "*" and hour == "*":
        return 1
    if hour.startswith("*/"):
        try: return int(hour[2:]) * 60
        except Exception: return None
    if "," in hour:
        return 24 * 60 // len(hour.split(","))
    if dow != "*" and "," in dow:
        return 7 * 24 * 60 // len(dow.split(","))
    if dow != "*":
        return 7 * 24 * 60
    return 24 * 60

def cron_log_mtime(patterns: list[str], fallback_patterns: list[str]) -> datetime | None:
    line = cron_line(patterns)
    if line:
        m = re.search(r">>\s*([^ ]+)", line)
        if m and os.path.exists(m.group(1)):
            return dt_from_ts(os.path.getmtime(m.group(1)))
    _, dt = latest_path(fallback_patterns)
    return dt

def alpha_action_time(action_prefix: str) -> datetime | None:
    p = Path("/root/agni/substrate/logs/alpha_cycle.jsonl")
    if not p.exists():
        return None
    last = None
    for line in p.read_text(errors="ignore").splitlines():
        try:
            d = json.loads(line)
        except Exception:
            continue
        if str(d.get("action", "")).startswith(action_prefix):
            ts = d.get("ts") or d.get("timestamp")
            if ts:
                try:
                    last = datetime.fromisoformat(ts.replace("Z","+00:00"))
                except Exception:
                    pass
    return last

entries = [
    ("alpha_cycle", ["alpha_cycle.py", "run_alpha_cycle_env"], ["/root/agni/substrate/logs/alpha_cycle.jsonl"], 30),
    ("alpha_cycle.A1", ["alpha_cycle.py", "run_alpha_cycle_env"], ["/root/agni/substrate/logs/alpha_cycle.jsonl"], 150),
    ("alpha_cycle.A2", ["alpha_cycle.py", "run_alpha_cycle_env"], ["/root/agni/substrate/logs/alpha_cycle.jsonl"], 150),
    ("alpha_cycle.A3", ["alpha_cycle.py", "run_alpha_cycle_env"], ["/root/agni/substrate/logs/alpha_cycle.jsonl"], 150),
    ("alpha_cycle.A4", ["alpha_cycle.py", "run_alpha_cycle_env"], ["/root/agni/substrate/logs/alpha_cycle.jsonl"], 150),
    ("alpha_cycle.A5", ["alpha_cycle.py", "run_alpha_cycle_env"], ["/root/agni/substrate/logs/alpha_cycle.jsonl"], 150),
    ("vraj_nightly_review", ["vraj/nightly_review.sh"], ["/root/trading_lab/vraj/logs/*", "/root/agent/vraj/state/*review*", "/root/agent/vraj/state/confidence.json"], None),
    ("vyapti_kills_to_kernel_confidence", ["kills_to_kernel_confidence.py"], ["/root/agent/vyapti/state/kernel_confidence.json", "/root/agni/substrate/logs/kernel_conf.log"], None),
    ("vyapti_pervade", ["nightly_pervade.sh"], ["/root/agent/vyapti/logs/pervade_cron.log", "/root/agent/vyapti/state/*"], None),
    ("self_upgrade", ["self_upgrade.py"], ["/root/trading_lab/data/system/upgrade_proposals.json", "/root/trading_lab/data/logs/self_upgrade.log"], None),
    ("evolution_judge", ["evolution_judge"], ["/root/agni/logs/*evolution*", "/root/trading_lab/vraj/logs/evolution_*"], None),
    ("hypothesis_gen", ["hypothesis_gen.py"], ["/root/agni/logs/hypothesis.log"], None),
    ("kaizen_loop", ["kaizen_loop.sh"], ["/root/agni/logs/*kaizen*", "/root/agni/state/*kaizen*"], None),
    ("executor", ["cron_runner.sh fast"], ["/root/trading_lab/data/logs/fast_*.log", "/root/trading_lab/data/routes/*/portfolio.json"], 5),
    ("leaderboard", ["engine.leaderboard"], ["/root/trading_lab/data/system/leaderboard.json", "/root/trading_lab/data/logs/leaderboard.log"], None),
    ("risk_gate", ["cron_runner.sh fast"], ["/root/trading_lab/data/logs/fast_*.log", "/root/trading_lab/data/logs/alerts.log"], 5),
    ("circuit_breakers", ["cron_runner.sh fast"], ["/root/trading_lab/data/routes/*/circuit_breaker.json", "/root/trading_lab/data/logs/fast_*.log"], 5),
    ("cascade_risk", ["cascade_risk.py"], ["/root/trading_lab/data/logs/cascade_risk.log", "/root/trading_lab/data/system/*cascade*"], None),
    ("net_exposure", ["cron_runner.sh check"], ["/root/trading_lab/data/net_exposure.json", "/root/trading_lab/data/logs/check_*.log"], 2),
    ("janitor", ["cron_runner.sh janitor"], ["/root/trading_lab/data/logs/janitor_cron.log", "/root/trading_lab/data/system/janitor*"], None),
    ("watchdog", ["watchdog/watchdog.py"], ["/root/trading_lab/data/logs/watchdog.log"], None),
    ("pipeline_monitor", ["pipeline_monitor"], ["/root/trading_lab/data/logs/pipeline_monitor.log"], None),
    ("funding_arb_scanner", ["funding_arb_scanner.py"], ["/root/trading_lab/data/logs/funding_arb_scanner.log", "/root/trading_lab/data/system/*funding*"], None),
    ("validation_retirement_check", ["retirement_check"], ["/root/trading_lab/data/logs/retirement.log"], None),
    ("equity_rollup", ["equity_curve_rollup.py"], ["/root/agni/substrate/logs/equity_rollup.log"], None),
    ("time_weighted_return", ["time_weighted_return.py"], ["/root/agni/substrate/logs/twr.log"], None),
    ("discord_report", ["discord_report.py"], ["/root/trading_lab/data/logs/discord_report.log"], None),
    ("gdrive_backup", ["rclone sync /root/trading_lab/data"], ["/root/trading_lab/data/logs/backup.log", "/root/trading_lab_backup/*.tar.gz", "/root/backups/trading_lab/*.tar.gz"], None),
    ("bull", ["bull"], ["/root/bull/**/*", "/root/trading_lab/data/logs/bull*"], None),
    ("fox", ["fox"], ["/root/fox/**/*", "/root/trading_lab/data/logs/fox*"], None),
]

rows = []
counts = {"green":0, "yellow":0, "red":0}
for name, pats, artifacts, override_interval in entries:
    line = cron_line(pats)
    sched = schedule_of(line)
    interval = interval_minutes(sched, override_interval)
    artifact_path, art_dt = latest_path(artifacts)
    if name.startswith("alpha_cycle.A"):
        action_prefix = {
            "alpha_cycle.A1": "A1_",
            "alpha_cycle.A2": "A2_",
            "alpha_cycle.A3": "A3_",
            "alpha_cycle.A4": "A4_",
            "alpha_cycle.A5": "A5_",
        }[name]
        art_dt = alpha_action_time(action_prefix)
        artifact_path = "/root/agni/substrate/logs/alpha_cycle.jsonl"
    last_fire = cron_log_mtime(pats, [artifact_path] if artifact_path != "NOT_FOUND" else artifacts)
    if line is None or artifact_path == "NOT_FOUND":
        status = "red"
    elif interval is None or art_dt is None:
        status = "yellow"
    elif (now - art_dt) <= timedelta(minutes=2*interval):
        status = "green"
    else:
        status = "yellow"
    counts[status] += 1
    rows.append((name, sched, iso(last_fire), iso(art_dt), artifact_path, status))

print("| name | schedule | last_fire | last_artifact_mtime | artifact_path | drift_status |")
print("|---|---:|---:|---:|---|---|")
for row in rows:
    print("| " + " | ".join(str(x).replace("|", "\\|") for x in row) + " |")
print(f"CRON_TABLE_COUNTS green={counts['green']} yellow={counts['yellow']} red={counts['red']}")
Path("/tmp/trading_cron_table_counts.json").write_text(json.dumps(counts))
PY

echo "### PHASE 2.A: R03 6-LOSS STATE"
python3 << 'EOF'
import json, csv, os, glob
lc = json.load(open('/root/trading_lab/state/lifecycle.json'))
r03 = lc.get('R03', {})
print(f'R03 lifecycle state: {r03.get("state","?")}')
print(f'R03 initial_capital: {r03.get("initial_capital","?")}')
cands = glob.glob('/root/trading_lab/data/routes/R03/') + glob.glob('/root/trading_lab/data/routes/R03_*/')
if cands:
    rdir = cands[0]
    p = json.load(open(os.path.join(rdir, 'portfolio.json')))
    print(f'R03 total_value: {p.get("total_value")}  cash: {p.get("cash")}  realized_pnl: {p.get("total_realized_pnl")}')
    rows = list(csv.DictReader(open(os.path.join(rdir, 'trades.csv'))))
    print(f'R03 trades: {len(rows)}')
    pnls = [float(r.get("realized_pnl") or 0) for r in rows]
    print(f'R03 last 10 PnLs: {pnls[-10:]}')
    print(f'R03 current_loss_streak: {sum(1 for p in reversed(pnls) if p<0) if pnls and pnls[-1]<0 else 0}')
EOF
echo "--- where is the kill-streak threshold defined and does auto-kill actually fire? ---"
grep -rn "loss_streak\|kill.*threshold\|auto.*kill\|MAX_LOSS_STREAK\|LOSS_STREAK_KILL" /root/trading_lab/ /root/agent/ --include="*.py" 2>/dev/null | head -10 || true
python3 << 'PY'
import csv, glob, json, os, re
lc = json.load(open('/root/trading_lab/state/lifecycle.json'))
cands = glob.glob('/root/trading_lab/data/routes/R03/') + glob.glob('/root/trading_lab/data/routes/R03_*/')
streak = 0
if cands:
    rows = list(csv.DictReader(open(os.path.join(cands[0], 'trades.csv'))))
    pnls = [float(r.get("realized_pnl") or 0) for r in rows]
    streak = sum(1 for p in reversed(pnls) if p < 0) if pnls and pnls[-1] < 0 else 0
armed = False
for root in ("/root/trading_lab", "/root/agent"):
    for dirpath, _, files in os.walk(root):
        for fn in files:
            if not fn.endswith(".py"): continue
            try:
                text = open(os.path.join(dirpath, fn), errors="ignore").read().lower()
            except Exception:
                continue
            if "loss_streak" in text and ("kill" in text or "auto" in text):
                armed = True
print(f"2.A VERDICT: R03_loss_streak={streak} | auto_kill_armed={'Y' if armed else 'N'} | recommended_action={'kill' if streak >= 6 else 'watch'}")
PY

echo "### PHASE 2.B: WHY auto_apply=false ON ALPHA_CYCLE PROPOSALS"
echo "--- find auto_apply gate logic ---"
grep -rn "auto_apply" /root/trading_lab/ /root/agni/ --include="*.py" 2>/dev/null | head -20 || true
echo "--- last 10 alpha_cycle proposals: their auto_apply field + reason ---"
ls -t /root/agni/proposals/pending/*.json 2>/dev/null | head -10 | while read f; do
  echo "== $f =="
  python3 -c "
import json
d = json.load(open('$f'))
print(f'  type: {d.get(\"type\", d.get(\"proposal_id\",\"?\"))}  route: {d.get(\"route_id\",\"?\")}  auto_apply: {d.get(\"auto_apply\",\"?\")}  reason: {(d.get(\"reason\", d.get(\"rationale\", \"?\")) or \"?\")[:100]}')"
done
python3 << 'PY'
from pathlib import Path
text = Path("/root/trading_lab/autonomous/alpha_cycle.py").read_text()
if '"auto_apply": False' in text:
    verdict = 'AUTO_APPLY_INTENTIONALLY_OFF — submit_proposal hardcodes "auto_apply": False for all alpha_cycle proposals'
else:
    verdict = 'OTHER — auto_apply not hardcoded in alpha_cycle submit_proposal'
print(f"2.B VERDICT: {verdict}")
PY

echo "### PHASE 2.C: META-DECISION CRONS"
for cron in self_upgrade evolution_judge hypothesis_gen kaizen_loop; do
  echo "== $cron =="
  find /root -name "*${cron}*" -type f -mtime -30 2>/dev/null | head -10
  find /root -path "*${cron}*" -newer /etc/hostname -mtime -30 2>/dev/null | head -5
done
python3 << 'PY'
import glob, os, time
items = {
  "self_upgrade": ["/root/trading_lab/data/system/upgrade_proposals.json", "/root/trading_lab/data/logs/self_upgrade.log"],
  "evolution_judge": ["/root/agni/logs/*evolution*", "/root/trading_lab/vraj/logs/evolution_*"],
  "hypothesis_gen": ["/root/agni/logs/hypothesis.log"],
  "kaizen_loop": ["/root/agni/logs/*kaizen*", "/root/agni/state/*kaizen*"],
}
recent = 0
never = 0
for name, pats in items.items():
    files = []
    for p in pats: files.extend(glob.glob(p))
    files = [f for f in files if os.path.exists(f) and os.path.getsize(f) > 0]
    if files:
        recent += 1
    else:
        never += 1
print(f"2.C VERDICT: {never} never produced output / {recent} produced output recently")
PY

echo "### PHASE 3: SUMMARY"
echo "Phase 0.A: $PHASE_0A_VERDICT"
echo "Phase 0.B: STAGED — both staged artifacts in /root/trading_lab/proposals/staged/"
echo "Phase 0.C: see 0.C VERDICT above"
if [ -f /tmp/trading_cron_table_counts.json ]; then
  python3 - << 'PY'
import json
c=json.load(open('/tmp/trading_cron_table_counts.json'))
print(f"Phase 1 cron table: see above ({c.get('green',0)} green, {c.get('yellow',0)} yellow, {c.get('red',0)} red)")
PY
else
  echo "Phase 1 cron table: see above"
fi
echo "Phase 2.A R03: see 2.A VERDICT above"
echo "Phase 2.B alpha_cycle gate: see 2.B VERDICT above"
echo "Phase 2.C meta-decision crons: see 2.C VERDICT above"
echo ""
wc -l /root/trading_lab/trading_audit_2026-05-04.log
