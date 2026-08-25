#!/bin/sh
set -eu

usage() {
  echo "usage: $0 --repo ROOT --python PYTHON --user USER --expected-sha SHA [--state-root PATH] [--start]" >&2
  exit 2
}

repo=""
python_bin=""
service_user=""
expected_sha=""
state_root="/var/lib/sublimation-foundry"
start_service=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo) repo="$2"; shift 2 ;;
    --python) python_bin="$2"; shift 2 ;;
    --user) service_user="$2"; shift 2 ;;
    --expected-sha) expected_sha="$2"; shift 2 ;;
    --state-root) state_root="$2"; shift 2 ;;
    --start) start_service=1; shift ;;
    *) usage ;;
  esac
done

[ -n "$repo" ] && [ -n "$python_bin" ] && [ -n "$service_user" ] && [ -n "$expected_sha" ] || usage
[ "${#expected_sha}" -eq 40 ] || { echo "expected SHA must be exactly 40 lowercase hex characters" >&2; exit 2; }
case "$expected_sha" in
  *[!0-9a-f]*) echo "expected SHA must be exactly 40 lowercase hex characters" >&2; exit 2 ;;
esac
case "$repo:$python_bin:$state_root" in
  /*:/*:/*) ;;
  *) echo "repo, python, and state root must be absolute paths" >&2; exit 2 ;;
esac
[ -d "$repo/.git" ] || { echo "not a git checkout: $repo" >&2; exit 1; }
[ -x "$python_bin" ] || { echo "python is not executable: $python_bin" >&2; exit 1; }

for dependency in git patch docker systemctl systemd-analyze sed install grep; do
  command -v "$dependency" >/dev/null 2>&1 || {
    echo "missing runtime dependency: $dependency" >&2
    exit 1
  }
done
PYTHONPATH="$repo" "$python_bin" -c 'import sys; assert sys.version_info >= (3, 11); import dharma_swarm'
docker info >/dev/null 2>&1 || { echo "Docker daemon unavailable" >&2; exit 1; }
docker image inspect foundry/openevolve-cpu:1 >/dev/null 2>&1 || {
  echo "required offline oracle image missing: foundry/openevolve-cpu:1" >&2
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

if [ "$start_service" -eq 0 ] && systemctl is-active --quiet sublimation-foundry.service; then
  echo "refusing inert install while an existing Foundry service is active; stop it first or use --start" >&2
  exit 1
fi

if [ "$start_service" -eq 1 ]; then
  provider_env="/etc/dharma-foundry/foundry.env"
  [ -f "$provider_env" ] || {
    echo "refusing start: create root-owned $provider_env with provider keys first" >&2
    exit 1
  }
  for provider_key in MOONSHOT_API_KEY ZHIPU_API_KEY; do
    grep -Eq "^${provider_key}=.+$" "$provider_env" || {
      echo "refusing start: $provider_key is not configured" >&2
      exit 1
    }
  done
  [ ! -e "$state_root/KILL.json" ] && [ ! -e "$state_root/STOP" ] \
    && [ ! -e "$state_root/QUARANTINE.json" ] && [ ! -e "$state_root/QUARANTINE" ] || {
      echo "refusing start: persistent STOP/KILL/quarantine state requires operator resolution" >&2
      exit 1
    }
  PYTHONPATH="$repo" "$python_bin" -c \
    'import pathlib, sys; from dharma_swarm.foundry.receipts import audit_receipts; report = audit_receipts(pathlib.Path(sys.argv[1])); raise SystemExit(0 if report.ok else 1)' \
    "$state_root" || {
      echo "refusing start: receipt/artifact audit is not clean" >&2
      exit 1
    }
fi

template="$repo/scripts/foundry/systemd/sublimation-foundry.service.in"
[ -f "$template" ] || { echo "missing unit template: $template" >&2; exit 1; }
unit_tmp_dir="$(mktemp -d)"
unit_tmp="$unit_tmp_dir/sublimation-foundry.service"
trap 'rm -f "$unit_tmp"; rmdir "$unit_tmp_dir"' EXIT HUP INT TERM
sed \
  -e "s|@@REPO@@|$repo|g" \
  -e "s|@@PYTHON@@|$python_bin|g" \
  -e "s|@@STATE_ROOT@@|$state_root|g" \
  -e "s|@@USER@@|$service_user|g" \
  "$template" >"$unit_tmp"
systemd-analyze verify "$unit_tmp" || {
  echo "rendered systemd unit failed verification" >&2
  exit 1
}

install -d -m 0750 -o "$service_user" -g "$service_user" "$state_root"
install -d -m 0750 /etc/dharma-foundry
install -m 0644 "$unit_tmp" /etc/systemd/system/sublimation-foundry.service
ln -sfn "$repo/scripts/foundry/foundry-status.sh" /usr/local/bin/foundry-status.sh
printf '%s\n' \
  'FOUNDRY_REPO_ROOT='"$repo" \
  'FOUNDRY_STATE_ROOT='"$state_root" \
  'FOUNDRY_PYTHON='"$python_bin" \
  'FOUNDRY_EXPECTED_SHA='"$expected_sha" \
  > /etc/dharma-foundry/status.env
printf '%s\n' \
  '*/15 * * * * root . /etc/dharma-foundry/status.env && /usr/local/bin/foundry-status.sh --compact' \
  > /etc/cron.d/sublimation-foundry-status
chmod 0644 /etc/cron.d/sublimation-foundry-status

systemctl daemon-reload
if [ "$start_service" -eq 1 ]; then
  systemctl enable --now sublimation-foundry.service
fi
if [ "$start_service" -eq 1 ]; then
  echo "installed and started sublimation-foundry.service at $expected_sha"
else
  echo "installed sublimation-foundry.service inert at $expected_sha; rerun with --start only after reviewing all gates"
fi
