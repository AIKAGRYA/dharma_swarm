#!/usr/bin/env bash
#
# Image-local launch boundary for the source-only swarm container.
# The image build seals /app/dharma_swarm into a deterministic manifest; this
# runner re-verifies the exact file set before Python imports any project code.

set -euo pipefail

fail() {
    echo "container runner: $1" >&2
    exit 78
}

source_root="/app/dharma_swarm"
manifest="/app/.dharma-runtime-source.sha256"
runtime_python="/usr/local/bin/python"

[[ -d "${source_root}" ]] || fail "image source root is missing"
[[ -f "${manifest}" ]] || fail "image source manifest is missing"
[[ -x "${runtime_python}" ]] || fail "image interpreter is unavailable"

if [[ -n "$(find "${source_root}" -type l -print -quit)" ]]; then
    fail "image source tree contains a symlink"
fi

temp_root="${TMPDIR:-/tmp}"
[[ -d "${temp_root}" && -w "${temp_root}" ]] \
    || fail "temporary directory is unavailable"
observed_manifest="$(mktemp "${temp_root%/}/dharma-runtime-manifest.XXXXXX")" \
    || fail "temporary manifest is unavailable"
trap 'rm -f "${observed_manifest}"' EXIT
(
    cd "${source_root}"
    find . -type f -print0 \
        | LC_ALL=C sort -z \
        | xargs -0 sha256sum
) > "${observed_manifest}"

if ! cmp -s "${manifest}" "${observed_manifest}"; then
    fail "image source tree does not match its baked manifest"
fi

source_digest="$(sha256sum "${manifest}" | cut -d ' ' -f 1)"
[[ "${source_digest}" =~ ^[0-9a-f]{64}$ ]] \
    || fail "image source manifest digest is malformed"

if [[ "${1-}" == "--verify-only" ]]; then
    [[ "$#" -eq 1 ]] || fail "unsupported argument"
    echo "container runner: source manifest verified: ${source_digest}"
    exit 0
elif [[ "$#" -ne 0 ]]; then
    fail "unsupported argument"
fi

export DHARMA_RUNTIME_PROVENANCE_MODE="container-image"
export DHARMA_RUNTIME_SOURCE_ROOT="${source_root}"
export DHARMA_RUNTIME_SOURCE_MANIFEST="${manifest}"
export DHARMA_RUNTIME_SOURCE_DIGEST="${source_digest}"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONNOUSERSITE=1

exec "${runtime_python}" -B -I -m dharma_swarm.orchestrate_live
