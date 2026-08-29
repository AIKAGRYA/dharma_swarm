#!/bin/sh
set -eu

usage() {
  echo "usage: $0 --repo ROOT --python PYTHON --user USER --environment-file ABSOLUTE_PATH --trusted-resume-public-key ABSOLUTE_PATH --expected-sha SHA [--state-root PATH] [--start]" >&2
  exit 2
}

repo=""
python_bin=""
service_user=""
environment_file=""
trusted_resume_public_key=""
expected_sha=""
state_root="/var/lib/sublimation-foundry"
start_service=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo) repo="$2"; shift 2 ;;
    --python) python_bin="$2"; shift 2 ;;
    --user) service_user="$2"; shift 2 ;;
    --environment-file) environment_file="$2"; shift 2 ;;
    --trusted-resume-public-key) trusted_resume_public_key="$2"; shift 2 ;;
    --expected-sha) expected_sha="$2"; shift 2 ;;
    --state-root) state_root="$2"; shift 2 ;;
    --start) start_service=1; shift ;;
    *) usage ;;
  esac
done

[ -n "$repo" ] && [ -n "$python_bin" ] && [ -n "$service_user" ] \
  && [ -n "$environment_file" ] && [ -n "$trusted_resume_public_key" ] \
  && [ -n "$expected_sha" ] || usage
[ "${#expected_sha}" -eq 40 ] || { echo "expected SHA must be exactly 40 lowercase hex characters" >&2; exit 2; }
case "$expected_sha" in
  *[!0-9a-f]*) echo "expected SHA must be exactly 40 lowercase hex characters" >&2; exit 2 ;;
esac
case "$repo:$python_bin:$state_root:$environment_file:$trusted_resume_public_key" in
  /*:/*:/*:/*:/*) ;;
  *) echo "repo, python, state root, environment file, and trusted public key must be absolute paths" >&2; exit 2 ;;
esac
case "$repo:$python_bin:$state_root:$environment_file:$trusted_resume_public_key" in
  *[!A-Za-z0-9_./:-]*)
    echo "deployment paths may contain only letters, digits, dot, underscore, slash, colon, and hyphen" >&2
    exit 2
    ;;
esac
[ -d "$repo/.git" ] || { echo "not a git checkout: $repo" >&2; exit 1; }
[ -x "$python_bin" ] || { echo "python is not executable: $python_bin" >&2; exit 1; }

for dependency in git patch docker systemctl systemd-analyze sed grep stat ssh-keygen; do
  command -v "$dependency" >/dev/null 2>&1 || {
    echo "missing runtime dependency: $dependency" >&2
    exit 1
  }
done
[ -f "$environment_file" ] && [ ! -L "$environment_file" ] || {
  echo "provider environment source must be an existing non-symlink regular file" >&2
  exit 1
}
environment_owner="$(stat -c '%u' "$environment_file")"
environment_mode="$(stat -c '%a' "$environment_file")"
[ "$environment_owner" = "0" ] || {
  echo "provider environment source must remain root-owned" >&2
  exit 1
}
case "$environment_mode" in
  400|600) ;;
  *) echo "provider environment source must remain mode 0400 or 0600" >&2; exit 1 ;;
esac
[ "$service_user" = "root" ] || {
  echo "a root-owned private staged environment source requires --user root; no credential copy or permission relaxation is permitted" >&2
  exit 1
}
[ -d "$state_root" ] && [ ! -L "$state_root" ] || {
  echo "state root must be explicitly pre-created as a non-symlink directory" >&2
  exit 1
}
[ "$(stat -c '%u:%g' "$state_root")" = "0:0" ] || {
  echo "state root must be root-owned for this root service" >&2
  exit 1
}
case "$(stat -c '%a' "$state_root")" in
  700|750) ;;
  *) echo "state root must remain mode 0700 or 0750" >&2; exit 1 ;;
esac
[ -d /etc/dharma-foundry ] && [ ! -L /etc/dharma-foundry ] \
  && [ "$(stat -c '%u:%g' /etc/dharma-foundry)" = "0:0" ] || {
    echo "/etc/dharma-foundry must be explicitly pre-created and root-owned" >&2
    exit 1
  }
case "$(stat -c '%a' /etc/dharma-foundry)" in
  700|750) ;;
  *) echo "/etc/dharma-foundry must remain mode 0700 or 0750" >&2; exit 1 ;;
esac
[ -f "$trusted_resume_public_key" ] && [ ! -L "$trusted_resume_public_key" ] || {
  echo "trusted resume authority must be an existing non-symlink public-key file" >&2
  exit 1
}
[ "$(stat -c '%u' "$trusted_resume_public_key")" = "0" ] || {
  echo "trusted resume authority public key must be root-owned" >&2
  exit 1
}
case "$(stat -c '%a' "$trusted_resume_public_key")" in
  400|440|444|600|640|644) ;;
  *) echo "trusted resume authority public key permissions are unsafe" >&2; exit 1 ;;
esac
grep -Eq '^ssh-ed25519 [A-Za-z0-9+/=]+([[:space:]].*)?$' "$trusted_resume_public_key" \
  && ssh-keygen -l -f "$trusted_resume_public_key" >/dev/null 2>&1 || {
    echo "trusted resume authority must be a valid OpenSSH Ed25519 public key" >&2
    exit 1
  }
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$repo" "$python_bin" -B -c \
  'import sys; assert sys.version_info >= (3, 11); import dharma_swarm'
docker info >/dev/null 2>&1 || { echo "Docker daemon unavailable" >&2; exit 1; }
oracle_image='foundry/openevolve-cpu@sha256:13526567bc4d878d367ae2ad1d1f18a686b3cdad2be6c09942c92dd34db5ca53'
docker image inspect "$oracle_image" >/dev/null 2>&1 || {
  echo "required immutable offline oracle image missing: $oracle_image" >&2
  exit 1
}
git -C "$repo" diff --quiet --ignore-submodules -- || {
  echo "refusing modified checkout" >&2
  exit 1
}
actual_sha="$(git -C "$repo" rev-parse HEAD)"
[ "$actual_sha" = "$expected_sha" ] || {
  echo "refusing release SHA mismatch: expected $expected_sha, found $actual_sha" >&2
  exit 1
}
canonical_remote="https://github.com/AIKAGRYA/dharma_swarm.git"
actual_remote="$(git -C "$repo" remote get-url origin)"
[ "$actual_remote" = "$canonical_remote" ] || {
  echo "refusing noncanonical origin remote" >&2
  exit 1
}
[ -z "$(git -C "$repo" status --porcelain --untracked-files=normal)" ] || {
  echo "refusing checkout with modified, staged, or untracked files" >&2
  exit 1
}

if systemctl is-active --quiet sublimation-foundry.service; then
  echo "refusing deployment while an existing Foundry service is active; stop it first" >&2
  exit 1
fi
main_enabled_state="$(systemctl is-enabled sublimation-foundry.service 2>/dev/null || true)"
case "$main_enabled_state" in
  disabled|masked|not-found) ;;
  *)
    echo "refusing deployment: existing Foundry service must be durably disabled or masked first" >&2
    exit 1
    ;;
esac
for legacy_unit in foundry-campaign.service foundry-daemon.service; do
  if systemctl is-active --quiet "$legacy_unit"; then
    echo "refusing deployment: legacy writer remains active: $legacy_unit" >&2
    exit 1
  fi
  legacy_state="$(systemctl is-enabled "$legacy_unit" 2>/dev/null || true)"
  case "$legacy_state" in
    disabled|masked|not-found) ;;
    *)
      echo "refusing deployment: legacy writer is not durably disabled: $legacy_unit" >&2
      exit 1
      ;;
  esac
done

if [ "$start_service" -eq 1 ]; then
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$repo" "$python_bin" -B - \
    "$environment_file" <<'PY' || {
import pathlib
import re
import sys

from dharma_swarm.foundry.live import ProviderPool

values = {}
for raw in pathlib.Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    line = raw.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    key = key.strip()
    value = value.strip()
    if not re.fullmatch(r"[A-Z][A-Z0-9_]*", key):
        continue
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
    values[key] = value
raise SystemExit(0 if ProviderPool(env=values).routes else 1)
PY
    echo "refusing start: no credential with verified tariff provenance is configured" >&2
    exit 1
  }
  [ ! -e "$state_root/KILL.json" ] && [ ! -e "$state_root/STOP" ] \
    && [ ! -e "$state_root/HALT.json" ] && [ ! -e "$state_root/QUARANTINE.json" ] \
    && [ ! -e "$state_root/QUARANTINE" ] || {
      echo "refusing start: persistent STOP/HALT/KILL/quarantine state requires signed operator resolution" >&2
      exit 1
    }
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$repo" "$python_bin" -B -c \
    'import pathlib, sys; from dharma_swarm.foundry.killswitch import is_stopped; raise SystemExit(1 if is_stopped(state_root=pathlib.Path(sys.argv[1])) else 0)' \
    "$state_root" || {
      echo "refusing start: authoritative unresolved halt evidence requires signed operator resolution" >&2
      exit 1
    }
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$repo" "$python_bin" -B -c \
    'import pathlib, sys; from dharma_swarm.foundry.receipts import audit_receipts; report = audit_receipts(pathlib.Path(sys.argv[1])); raise SystemExit(0 if report.ok else 1)' \
    "$state_root" || {
      echo "refusing start: receipt/artifact audit is not clean" >&2
      exit 1
    }
fi

template="$repo/scripts/foundry/systemd/sublimation-foundry.service.in"
[ -f "$template" ] || { echo "missing unit template: $template" >&2; exit 1; }
alert_template="$repo/scripts/foundry/systemd/sublimation-foundry-alert@.service.in"
[ -f "$alert_template" ] || { echo "missing alert unit template: $alert_template" >&2; exit 1; }
status_template="$repo/scripts/foundry/systemd/status.env.in"
[ -f "$status_template" ] || { echo "missing status environment template: $status_template" >&2; exit 1; }
cron_template="$repo/scripts/foundry/systemd/sublimation-foundry-status.cron.in"
[ -f "$cron_template" ] || { echo "missing status cron template: $cron_template" >&2; exit 1; }
unit_tmp_dir="$(mktemp -d)"
unit_tmp="$unit_tmp_dir/sublimation-foundry.service"
alert_tmp="$unit_tmp_dir/sublimation-foundry-alert@.service"
status_tmp="$unit_tmp_dir/status.env"
cron_tmp="$unit_tmp_dir/sublimation-foundry-status"
manifest_tmp="$unit_tmp_dir/deployment.json"
transaction=""
rollback_needed=0
service_transition_attempted=0
cleanup() {
  exit_code="$?"
  trap - EXIT HUP INT TERM
  if [ "$service_transition_attempted" -eq 1 ]; then
    systemctl disable --now sublimation-foundry.service >/dev/null 2>&1 || true
  fi
  if [ "$rollback_needed" -eq 1 ] && [ -n "$transaction" ]; then
    "$python_bin" "$repo/scripts/foundry/deploy_transaction.py" rollback \
      --transaction "$transaction" >/dev/null 2>&1 || \
      echo "CRITICAL: Foundry deployment rollback failed closed; inspect transaction $transaction" >&2
    systemctl daemon-reload >/dev/null 2>&1 || true
  fi
  rm -f "$unit_tmp" "$alert_tmp" "$status_tmp" "$cron_tmp" "$manifest_tmp"
  rmdir "$unit_tmp_dir" >/dev/null 2>&1 || true
  exit "$exit_code"
}
trap cleanup EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM
sed \
  -e "s|@@REPO@@|$repo|g" \
  -e "s|@@PYTHON@@|$python_bin|g" \
  -e "s|@@STATE_ROOT@@|$state_root|g" \
  -e "s|@@USER@@|$service_user|g" \
  -e "s|@@ENVIRONMENT_FILE@@|$environment_file|g" \
  -e "s|@@EXPECTED_SHA@@|$expected_sha|g" \
  "$template" >"$unit_tmp"
sed \
  -e "s|@@REPO@@|$repo|g" \
  -e "s|@@PYTHON@@|$python_bin|g" \
  -e "s|@@STATE_ROOT@@|$state_root|g" \
  -e "s|@@USER@@|$service_user|g" \
  "$alert_template" >"$alert_tmp"
sed \
  -e "s|@@REPO@@|$repo|g" \
  -e "s|@@PYTHON@@|$python_bin|g" \
  -e "s|@@STATE_ROOT@@|$state_root|g" \
  -e "s|@@EXPECTED_SHA@@|$expected_sha|g" \
  "$status_template" >"$status_tmp"
sed -e "s|@@REPO@@|$repo|g" "$cron_template" >"$cron_tmp"
systemd-analyze verify "$unit_tmp" "$alert_tmp" || {
  echo "rendered systemd unit failed verification" >&2
  exit 1
}

transaction="$("$python_bin" "$repo/scripts/foundry/deploy_transaction.py" apply \
  --transaction-root /etc/dharma-foundry/deployment-transactions \
  --file "$unit_tmp=/etc/systemd/system/sublimation-foundry.service" \
  --file "$alert_tmp=/etc/systemd/system/sublimation-foundry-alert@.service" \
  --file "$repo/scripts/foundry/logrotate/sublimation-foundry=/etc/logrotate.d/sublimation-foundry" \
  --file "$status_tmp=/etc/dharma-foundry/status.env" \
  --file "$cron_tmp=/etc/cron.d/sublimation-foundry-status" \
  --file "$repo/scripts/foundry/verify_deployment.py=/usr/local/bin/sublimation-foundry-verify-deployment.py" \
  --file "$repo/scripts/foundry/foundry_alert.py=/usr/local/bin/sublimation-foundry-alert.py" \
  --file "$repo/scripts/foundry/foundry_status_job.py=/usr/local/bin/sublimation-foundry-status-job.py" \
  --symlink "/usr/local/bin/foundry-status.sh=$repo/scripts/foundry/foundry-status.sh")"
rollback_needed=1
"$python_bin" "$repo/scripts/foundry/verify_deployment.py" record \
  --repo "$repo" \
  --expected-sha "$expected_sha" \
  --manifest "$manifest_tmp" \
  --binding "$unit_tmp=/etc/systemd/system/sublimation-foundry.service" \
  --binding "$alert_tmp=/etc/systemd/system/sublimation-foundry-alert@.service" \
  --binding "$repo/scripts/foundry/logrotate/sublimation-foundry=/etc/logrotate.d/sublimation-foundry" \
  --binding "$status_tmp=/etc/dharma-foundry/status.env" \
  --binding "$cron_tmp=/etc/cron.d/sublimation-foundry-status" \
  --binding "$repo/scripts/foundry/verify_deployment.py=/usr/local/bin/sublimation-foundry-verify-deployment.py" \
  --binding "$repo/scripts/foundry/foundry_alert.py=/usr/local/bin/sublimation-foundry-alert.py" \
  --binding "$repo/scripts/foundry/foundry_status_job.py=/usr/local/bin/sublimation-foundry-status-job.py" \
  --symlink "/usr/local/bin/foundry-status.sh=$repo/scripts/foundry/foundry-status.sh" \
  --secret-file "$environment_file" \
  --public-file "$trusted_resume_public_key" \
  --runtime-executable "$python_bin" \
  --template "$template" \
  --template "$alert_template" \
  --template "$status_template" \
  --template "$cron_template" \
  --template "$repo/scripts/foundry/logrotate/sublimation-foundry" \
  --template "$repo/scripts/foundry/foundry-status.sh" \
  --template "$repo/scripts/foundry/foundry_status_job.py" \
  --template "$repo/scripts/foundry/foundry_daemon.py" \
  --template "$repo/scripts/foundry/foundry_alert.py" \
  --template "$repo/scripts/foundry/deploy_transaction.py"
"$python_bin" "$repo/scripts/foundry/deploy_transaction.py" add-file \
  --transaction "$transaction" \
  --file "$manifest_tmp=/etc/dharma-foundry/deployment.json"
"$python_bin" "$repo/scripts/foundry/verify_deployment.py" verify \
  --repo "$repo" \
  --expected-sha "$expected_sha" \
  --manifest /etc/dharma-foundry/deployment.json

systemctl daemon-reload
if [ "$start_service" -eq 1 ]; then
  # Recheck immediately before starting.  We never mutate legacy enablement;
  # an operator must make that transition explicitly and can therefore undo
  # it losslessly outside this deployment transaction.
  for legacy_unit in foundry-campaign.service foundry-daemon.service; do
    if systemctl is-active --quiet "$legacy_unit"; then
      echo "refusing start: legacy writer remains active: $legacy_unit" >&2
      exit 1
    fi
    legacy_state="$(systemctl is-enabled "$legacy_unit" 2>/dev/null || true)"
    case "$legacy_state" in
      disabled|masked|not-found) ;;
      *) echo "refusing start: legacy writer is not durably disabled: $legacy_unit" >&2; exit 1 ;;
    esac
  done
  service_transition_attempted=1
  systemctl enable --now sublimation-foundry.service
fi
"$python_bin" "$repo/scripts/foundry/deploy_transaction.py" commit \
  --transaction "$transaction"
rollback_needed=0
service_transition_attempted=0
if [ "$start_service" -eq 1 ]; then
  echo "installed and started sublimation-foundry.service at $expected_sha"
else
  echo "installed sublimation-foundry.service inert at $expected_sha; rerun with --start only after reviewing all gates"
fi
