#!/usr/bin/env bash
# Render/install systemd artifacts only after an exact-SHA, clean-tree check.
set -euo pipefail

repo=""
config=""
python=""
expected_sha=""
systemd_dir="/etc/systemd/system"
state_root="/var/lib/dharma/lab-supervisor"
service_user="dharma-lab-supervisor"
apply=0

usage() {
  printf '%s\n' \
    "usage: install_lab_supervisor.sh --repo PATH --config PATH --python PATH --expected-sha SHA [--state-root PATH] [--systemd-dir PATH] [--user NAME] [--install]" \
    "default: validate and print the install plan; --install writes unit files but never enables or starts them"
}

while (($#)); do
  case "$1" in
    --repo) repo="${2:?missing --repo value}"; shift 2 ;;
    --config) config="${2:?missing --config value}"; shift 2 ;;
    --python) python="${2:?missing --python value}"; shift 2 ;;
    --expected-sha) expected_sha="${2:?missing --expected-sha value}"; shift 2 ;;
    --systemd-dir) systemd_dir="${2:?missing --systemd-dir value}"; shift 2 ;;
    --state-root) state_root="${2:?missing --state-root value}"; shift 2 ;;
    --user) service_user="${2:?missing --user value}"; shift 2 ;;
    --install) apply=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'unknown argument: %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
done

for value in "$repo" "$config" "$python" "$expected_sha"; do
  if [[ -z "$value" ]]; then
    usage >&2
    exit 2
  fi
done
if [[ ! "$expected_sha" =~ ^[0-9a-f]{40}$ ]]; then
  printf 'expected SHA must be an exact 40-character lowercase commit id\n' >&2
  exit 2
fi
for path in "$repo" "$config" "$python" "$systemd_dir" "$state_root"; do
  if [[ ! "$path" =~ ^/[A-Za-z0-9._/@+-]+$ ]]; then
    printf 'all paths must be absolute and use only safe path characters: %s\n' "$path" >&2
    exit 2
  fi
done
if [[ ! "$service_user" =~ ^[a-z_][a-z0-9_-]{0,31}$ ]]; then
  printf 'service user is not a safe system account name: %s\n' "$service_user" >&2
  exit 2
fi
if ((apply == 1)) && ! id -u "$service_user" >/dev/null 2>&1; then
  printf 'service user does not exist; provision it before install: %s\n' "$service_user" >&2
  exit 3
fi
service_group="$service_user"
if ((apply == 1)); then
  service_group="$(id -gn "$service_user")"
fi

actual_sha="$(git -C "$repo" rev-parse HEAD)"
if [[ "$actual_sha" != "$expected_sha" ]]; then
  printf 'exact-SHA check failed: expected %s, observed %s\n' "$expected_sha" "$actual_sha" >&2
  exit 3
fi
if [[ -n "$(git -C "$repo" status --porcelain --untracked-files=normal)" ]]; then
  printf 'deployment source is not clean; refusing to render from mutable bytes\n' >&2
  exit 3
fi
if [[ ! -x "$python" || ! -f "$config" ]]; then
  printf 'python must be executable and config must be a regular file\n' >&2
  exit 3
fi

"$python" "$repo/scripts/runtime/lab_supervisor.py" validate-config --config "$config" >/dev/null
printf 'validated exact SHA: %s\n' "$actual_sha"
printf 'service target: %s/dharma-lab-supervisor.service\n' "$systemd_dir"
printf 'timer target:   %s/dharma-lab-supervisor.timer\n' "$systemd_dir"
printf 'mode:           safe dry-run (live actions require a reviewed unit override)\n'
printf 'service user:   %s (must already exist with least-privilege evidence access)\n' "$service_user"

if ((apply == 0)); then
  printf 'no files installed; rerun with --install after reviewing this plan\n'
  exit 0
fi

mkdir -p "$systemd_dir"
install -d -m 0700 -o "$service_user" -g "$service_group" "$state_root"
sed \
  -e "s|@@REPO@@|$repo|g" \
  -e "s|@@PYTHON@@|$python|g" \
  -e "s|@@CONFIG@@|$config|g" \
  -e "s|@@STATE_ROOT@@|$state_root|g" \
  -e "s|@@USER@@|$service_user|g" \
  -e "s|@@GROUP@@|$service_group|g" \
  "$repo/docs/ops/LAB_SUPERVISOR.service" >"$systemd_dir/dharma-lab-supervisor.service"
cp "$repo/docs/ops/LAB_SUPERVISOR.timer" "$systemd_dir/dharma-lab-supervisor.timer"
chmod 0644 "$systemd_dir/dharma-lab-supervisor.service" "$systemd_dir/dharma-lab-supervisor.timer"
printf 'installed inert units; run systemctl daemon-reload, enable, and start only under operator authority\n'
