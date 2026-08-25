#!/usr/bin/env bash
# Safe, bounded SQLite backups for the Rushabdev host.
#
# Configuration (the directory paths must already exist):
#   RUSHABDEV_SQLITE_ROOT             source dir (default: /root/rushabdev)
#   RUSHABDEV_SQLITE_BACKUP_DIR       output (default: /root/rushabdev/backups/sqlite)
#   RUSHABDEV_SQLITE_RETENTION_DAYS   age threshold, in whole days
#   RUSHABDEV_SQLITE_RESERVE_BYTES    free bytes that must remain untouched
#
# Backward-compatible BACKUP_* aliases are accepted for deployment wrappers.
# This program deliberately does not source an env/secrets file.

set -Eeuo pipefail
umask 077
export LC_ALL=C

SOURCE_ROOT_RAW="${RUSHABDEV_SQLITE_ROOT:-${RUSHABDEV_BACKUP_SOURCE_ROOT:-/root/rushabdev}}"
OUTPUT_DIR_RAW="${RUSHABDEV_SQLITE_BACKUP_DIR:-${RUSHABDEV_BACKUP_OUTPUT_DIR:-/root/rushabdev/backups/sqlite}}"
RETENTION_DAYS_RAW="${RUSHABDEV_SQLITE_RETENTION_DAYS:-${RUSHABDEV_BACKUP_RETENTION_DAYS:-7}}"
RESERVE_BYTES_RAW="${RUSHABDEV_SQLITE_RESERVE_BYTES:-${RUSHABDEV_BACKUP_RESERVE_BYTES:-1073741824}}"
VERIFY_EXTRA_BYTES_RAW="${RUSHABDEV_SQLITE_VERIFY_EXTRA_BYTES:-67108864}"
BUSY_TIMEOUT_MS_RAW="${RUSHABDEV_SQLITE_BUSY_TIMEOUT_MS:-60000}"

SOURCE_ROOT=""
OUTPUT_DIR=""
RETENTION_DAYS=0
RESERVE_BYTES=0
VERIFY_EXTRA_BYTES=0
BUSY_TIMEOUT_MS=0
CURRENT_BINARY_PARTIAL=""
CURRENT_GZIP_PARTIAL=""
CURRENT_VERIFY_PARTIAL=""
RUN_STARTED=0

# This is an allowlist, not discovery. Adding a database is an operational
# change that should be reviewed alongside its restore path and storage cost.
BACKUP_MANIFEST=(
    "data/markets.db"
    "state/calibration.db"
    "state/paper_positions.db"
    "state/scoreboard.duckdb"
)

log_value() {
    # Log values are receipts, not a second command language. Keep each value a
    # single conservative token so paths cannot forge additional fields/lines.
    printf '%s' "$1" | tr -c 'A-Za-z0-9._:/@+=-' '_'
}

log_line() {
    local event="$1"
    local status="$2"
    shift 2
    printf 'ts=%s component=rushabdev_sqlite_backup event=%s status=%s' \
        "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" \
        "$(log_value "$event")" \
        "$(log_value "$status")"
    local field
    for field in "$@"; do
        printf ' %s' "$(log_value "$field")"
    done
    printf '\n'
}

die() {
    log_line preflight failed "reason=$1"
    exit 64
}

is_scoped_partial() {
    local path="$1"
    [[ -n "$OUTPUT_DIR" && "$path" == "$OUTPUT_DIR/"* && "$path" == *.partial ]]
}

cleanup() {
    local rc=$?
    trap - EXIT
    set +e
    local path
    for path in \
        "$CURRENT_BINARY_PARTIAL" \
        "$CURRENT_GZIP_PARTIAL" \
        "$CURRENT_VERIFY_PARTIAL"; do
        if [[ -n "$path" ]] && is_scoped_partial "$path"; then
            rm -f -- "$path"
        fi
    done
    if (( RUN_STARTED == 1 )); then
        if (( rc == 0 )); then
            log_line run ok
        else
            log_line run failed "exit_code=$rc"
        fi
    fi
    exit "$rc"
}

trap cleanup EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

parse_uint() {
    local output_name="$1"
    local label="$2"
    local raw="$3"
    local maximum="$4"
    if [[ ! "$raw" =~ ^[0-9]+$ ]] || (( ${#raw} > 18 )); then
        die "invalid_${label}"
    fi
    local parsed=$((10#$raw))
    if (( parsed > maximum )); then
        die "invalid_${label}"
    fi
    printf -v "$output_name" '%d' "$parsed"
}

validate_path_text() {
    local label="$1"
    local path="$2"
    [[ "$path" == /* ]] || die "${label}_not_absolute"
    # %, ?, and # change SQLite file-URI semantics. Quotes, backslashes, and
    # controls change sqlite-shell dot-command parsing. Refuse all of them.
    case "$path" in
        *'%'*|*'?'*|*'#'*|*'"'*|*\\*|*$'\n'*|*$'\r'*|*$'\t'*)
            die "${label}_unsafe_characters"
            ;;
    esac
}

canonical_existing_dir() {
    local output_name="$1"
    local label="$2"
    local path="$3"
    validate_path_text "$label" "$path"
    [[ ! -L "$path" ]] || die "${label}_symlink"
    [[ -d "$path" ]] || die "${label}_missing"
    local canonical
    canonical="$(cd -P -- "$path" && pwd -P)" || die "${label}_unresolvable"
    [[ "$canonical" != "/" ]] || die "${label}_too_broad"
    validate_path_text "$label" "$canonical"
    printf -v "$output_name" '%s' "$canonical"
}

available_bytes() {
    local available_kib
    available_kib="$(df -Pk "$OUTPUT_DIR" | awk 'NR == 2 { print $4 }')"
    [[ "$available_kib" =~ ^[0-9]+$ ]] || return 1
    printf '%d\n' "$((10#$available_kib * 1024))"
}

file_bytes() {
    local size
    size="$(wc -c < "$1")"
    size="${size//[[:space:]]/}"
    [[ "$size" =~ ^[0-9]+$ ]] || return 1
    printf '%d\n' "$((10#$size))"
}

file_mtime() {
    local path="$1"
    local value
    if value="$(stat -c '%Y' "$path" 2>/dev/null)"; then
        :
    elif value="$(stat -f '%m' "$path" 2>/dev/null)"; then
        :
    else
        return 1
    fi
    [[ "$value" =~ ^[0-9]+$ ]] || return 1
    printf '%d\n' "$((10#$value))"
}

fsync_path() {
    # `sync -f` is GNU-specific; use the already-required Python runtime so the
    # same crash-durability primitive is exercised by Linux and macOS tests.
    python3 -c '
import os
import sys

path = sys.argv[1]
flags = os.O_RDONLY
if os.path.isdir(path):
    flags |= getattr(os, "O_DIRECTORY", 0)
descriptor = os.open(path, flags)
try:
    os.fsync(descriptor)
finally:
    os.close(descriptor)
' "$1" >/dev/null 2>&1
}

safe_remove_partial() {
    local path="$1"
    is_scoped_partial "$path" || return 1
    rm -f -- "$path"
}

cleanup_backup_partials() {
    local path
    for path in "$CURRENT_BINARY_PARTIAL" "$CURRENT_GZIP_PARTIAL" "$CURRENT_VERIFY_PARTIAL"; do
        if [[ -n "$path" ]] && is_scoped_partial "$path"; then
            rm -f -- "$path" || return 1
        fi
    done
    CURRENT_BINARY_PARTIAL=""
    CURRENT_GZIP_PARTIAL=""
    CURRENT_VERIFY_PARTIAL=""
}

prune_incomplete() {
    local path
    local partials=("$OUTPUT_DIR"/*.partial "$OUTPUT_DIR"/.*.partial)
    for path in "${partials[@]}"; do
        [[ -e "$path" || -L "$path" ]] || continue
        [[ ! -d "$path" ]] || {
            log_line prune failed "reason=partial_is_directory"
            return 1
        }
        if ! safe_remove_partial "$path"; then
            log_line prune failed "reason=partial_remove_failed"
            return 1
        fi
        log_line prune ok "kind=partial" "file=$(basename "$path")"
    done

    local finals=(
        "$OUTPUT_DIR"/*.gz
        "$OUTPUT_DIR"/*.db
        "$OUTPUT_DIR"/*.sqlite
        "$OUTPUT_DIR"/*.sqlite3
    )
    for path in "${finals[@]}"; do
        [[ -f "$path" ]] || continue
        if [[ ! -s "$path" ]]; then
            if ! rm -f -- "$path"; then
                log_line prune failed "reason=zero_remove_failed"
                return 1
            fi
            log_line prune ok "kind=zero_byte" "file=$(basename "$path")"
        fi
    done
}

database_id() {
    local source="$1"
    local relative="${source#"$SOURCE_ROOT"/}"
    local readable
    local checksum
    # Bound the destination filename component even when discovery encounters a
    # deeply nested source. The checksum still distinguishes equal basenames.
    readable="$(basename "$relative" | tr -c 'A-Za-z0-9._-' '_')"
    readable="${readable:0:96}"
    checksum="$(printf '%s' "$relative" | cksum | awk '{print $1}')"
    printf 'db_%s_%s' "$readable" "$checksum"
}

source_working_bytes() {
    local source="$1"
    local total
    local wal_size=0
    total="$(file_bytes "$source")" || return 1
    if [[ -f "${source}-wal" ]]; then
        wal_size="$(file_bytes "${source}-wal")" || return 1
    fi
    printf '%d\n' "$((total + wal_size))"
}

decompress_bounded() {
    local archive="$1"
    local destination="$2"
    local limit_bytes="$3"
    # Bash applies `ulimit -f` in KiB units. Round down so the child can never
    # consume bytes that belong to the filesystem reserve.
    local limit_kib=$((limit_bytes / 1024))
    (( limit_kib > 0 )) || return 1
    # ulimit is applied in a child shell, so a corrupt or hostile archive can
    # never expand without a configured bound in the backup filesystem.
    if ! (ulimit -f "$limit_kib" || exit 1; gzip -cd -- "$archive" > "$destination"); then
        return 1
    fi
    local restored_bytes
    restored_bytes="$(file_bytes "$destination")" || return 1
    (( restored_bytes <= limit_bytes )) || return 1
}

quick_check_file() {
    local database="$1"
    local result
    if ! result="$(sqlite3 -batch -readonly -noheader \
        "$database" \
        ".timeout $BUSY_TIMEOUT_MS" \
        'PRAGMA quick_check(1);' 2>&1)"; then
        return 1
    fi
    [[ "$result" == "ok" ]]
}

# Return 0 for verified, 1 for a corrupt/non-SQLite archive, and 2 when the
# environment could not complete verification. Retention must not delete on 2.
verify_archive() {
    local archive="$1"
    local free_bytes
    local limit_bytes
    local filesystem_margin_bytes=1048576
    if ! gzip -t -- "$archive" >/dev/null 2>&1; then
        return 1
    fi
    free_bytes="$(available_bytes)" || return 2
    if (( free_bytes <= RESERVE_BYTES + filesystem_margin_bytes )); then
        log_line retention failed "reason=insufficient_space_for_verification" \
            "free_bytes=$free_bytes" \
            "required_bytes=$((RESERVE_BYTES + filesystem_margin_bytes + 1))"
        return 2
    fi
    # An old, valid backup may be much larger than today's live database after
    # VACUUM or retention. Bound restoration by the space actually available
    # above the configured reserve, not by the current source size. This keeps
    # decompression fail-closed without making database shrinkage a permanent
    # backup outage.
    limit_bytes=$((free_bytes - RESERVE_BYTES - filesystem_margin_bytes))
    CURRENT_VERIFY_PARTIAL="$(mktemp "$OUTPUT_DIR/.retention-verify.XXXXXX.partial")" || return 2
    if ! decompress_bounded "$archive" "$CURRENT_VERIFY_PARTIAL" "$limit_bytes"; then
        safe_remove_partial "$CURRENT_VERIFY_PARTIAL" || true
        CURRENT_VERIFY_PARTIAL=""
        return 2
    fi
    if ! quick_check_file "$CURRENT_VERIFY_PARTIAL"; then
        safe_remove_partial "$CURRENT_VERIFY_PARTIAL" || true
        CURRENT_VERIFY_PARTIAL=""
        return 1
    fi
    safe_remove_partial "$CURRENT_VERIFY_PARTIAL" || return 2
    CURRENT_VERIFY_PARTIAL=""
    return 0
}

retention_prune() {
    local db_id="$1"
    local candidates=("$OUTPUT_DIR/${db_id}"--*.sqlite3.gz)
    [[ -f "${candidates[0]}" ]] || return 0

    local keeper=""
    local index
    local verify_rc
    # Shell glob order is lexical. Timestamped names therefore put the newest
    # candidate last; verify backwards until one successful backup is found.
    for ((index=${#candidates[@]} - 1; index >= 0; index--)); do
        if verify_archive "${candidates[$index]}"; then
            keeper="${candidates[$index]}"
            break
        else
            verify_rc=$?
            if (( verify_rc == 2 )); then
                log_line retention failed "db_id=$db_id" "reason=verification_unavailable"
                return 1
            fi
        fi
    done
    if [[ -z "$keeper" ]]; then
        # With no mechanically verified keeper, deletion would turn uncertainty
        # into data loss. Leave every final artifact in place and continue.
        log_line retention skipped "db_id=$db_id" "reason=no_verified_keeper"
        return 0
    fi

    local now
    local cutoff
    local mtime
    local candidate
    now="$(date +%s)"
    cutoff=$((now - RETENTION_DAYS * 86400))
    for candidate in "${candidates[@]}"; do
        [[ "$candidate" != "$keeper" ]] || continue
        mtime="$(file_mtime "$candidate")" || {
            log_line retention failed "db_id=$db_id" "reason=mtime_unavailable"
            return 1
        }
        if (( mtime < cutoff )); then
            if ! rm -f -- "$candidate"; then
                log_line retention failed "db_id=$db_id" "reason=remove_failed"
                return 1
            fi
            log_line retention ok "db_id=$db_id" "action=pruned" "file=$(basename "$candidate")"
        fi
    done
    log_line retention ok "db_id=$db_id" "action=keeper" "file=$(basename "$keeper")"
}

preflight_capacity() {
    local source="$1"
    local db_id="$2"
    local working_bytes="$3"
    local free_bytes
    local required_bytes
    free_bytes="$(available_bytes)" || {
        log_line capacity failed "db_id=$db_id" "reason=df_unavailable"
        return 1
    }
    # Peak staging can contain the uncompressed backup and compressed stream at
    # once. The extra allowance covers page/WAL normalization and verification.
    required_bytes=$((RESERVE_BYTES + working_bytes * 2 + VERIFY_EXTRA_BYTES))
    if (( free_bytes < required_bytes )); then
        log_line capacity failed "db_id=$db_id" "reason=insufficient_space" \
            "free_bytes=$free_bytes" "required_bytes=$required_bytes"
        return 1
    fi
    log_line capacity ok "db_id=$db_id" "free_bytes=$free_bytes" "required_bytes=$required_bytes"
}

backup_sqlite() {
    local source="$1"
    local db_id
    local working_bytes
    local verify_limit_bytes
    local timestamp
    local final_archive

    case "$source" in
        *'%'*|*'?'*|*'#'*|*'"'*|*\\*|*$'\n'*|*$'\r'*|*$'\t'*)
            log_line backup failed "reason=source_unsafe_characters"
            return 1
            ;;
    esac
    [[ -f "$source" && ! -L "$source" && -r "$source" ]] || {
        log_line backup failed "reason=source_not_safe_regular_file"
        return 1
    }
    [[ -s "$source" ]] || {
        log_line backup failed "reason=source_zero_byte"
        return 1
    }

    db_id="$(database_id "$source")"
    working_bytes="$(source_working_bytes "$source")" || {
        log_line backup failed "db_id=$db_id" "reason=size_unavailable"
        return 1
    }
    verify_limit_bytes=$((working_bytes + VERIFY_EXTRA_BYTES))

    # Retention is deliberately before capacity and creation. A failed new
    # backup can therefore never be the justification for deleting the keeper.
    retention_prune "$db_id" || return 1
    preflight_capacity "$source" "$db_id" "$working_bytes" || return 1

    timestamp="$(date -u '+%Y%m%dT%H%M%SZ')"
    final_archive="$OUTPUT_DIR/${db_id}--${timestamp}--$$.sqlite3.gz"
    CURRENT_BINARY_PARTIAL="${final_archive%.gz}.partial"
    CURRENT_GZIP_PARTIAL="${final_archive}.partial"
    [[ ! -e "$final_archive" && ! -e "$CURRENT_BINARY_PARTIAL" && ! -e "$CURRENT_GZIP_PARTIAL" ]] || {
        log_line backup failed "db_id=$db_id" "reason=destination_collision"
        return 1
    }

    if ! sqlite3 -batch -readonly "$source" \
        ".timeout $BUSY_TIMEOUT_MS" \
        ".backup \"$CURRENT_BINARY_PARTIAL\"" >/dev/null 2>&1; then
        log_line backup failed "db_id=$db_id" "reason=sqlite_backup_failed"
        return 1
    fi
    [[ -s "$CURRENT_BINARY_PARTIAL" ]] || {
        log_line backup failed "db_id=$db_id" "reason=sqlite_backup_empty"
        return 1
    }

    if ! gzip -c -- "$CURRENT_BINARY_PARTIAL" > "$CURRENT_GZIP_PARTIAL"; then
        log_line backup failed "db_id=$db_id" "reason=gzip_failed"
        return 1
    fi
    if ! gzip -t -- "$CURRENT_GZIP_PARTIAL" >/dev/null 2>&1; then
        log_line backup failed "db_id=$db_id" "reason=gzip_verify_failed"
        return 1
    fi
    if ! fsync_path "$CURRENT_GZIP_PARTIAL"; then
        log_line backup failed "db_id=$db_id" "reason=archive_fsync_failed"
        return 1
    fi
    if ! safe_remove_partial "$CURRENT_BINARY_PARTIAL"; then
        log_line backup failed "db_id=$db_id" "reason=staging_remove_failed"
        return 1
    fi
    CURRENT_BINARY_PARTIAL=""

    CURRENT_VERIFY_PARTIAL="$(mktemp "$OUTPUT_DIR/.restore-verify.XXXXXX.partial")" || {
        log_line backup failed "db_id=$db_id" "reason=restore_temp_failed"
        return 1
    }
    if ! decompress_bounded "$CURRENT_GZIP_PARTIAL" "$CURRENT_VERIFY_PARTIAL" "$verify_limit_bytes"; then
        log_line backup failed "db_id=$db_id" "reason=restore_decompress_failed"
        return 1
    fi
    if ! quick_check_file "$CURRENT_VERIFY_PARTIAL"; then
        log_line backup failed "db_id=$db_id" "reason=sqlite_quick_check_failed"
        return 1
    fi
    if ! safe_remove_partial "$CURRENT_VERIFY_PARTIAL"; then
        log_line backup failed "db_id=$db_id" "reason=restore_temp_remove_failed"
        return 1
    fi
    CURRENT_VERIFY_PARTIAL=""

    if ! mv -- "$CURRENT_GZIP_PARTIAL" "$final_archive"; then
        log_line backup failed "db_id=$db_id" "reason=atomic_promote_failed"
        return 1
    fi
    CURRENT_GZIP_PARTIAL=""
    if ! fsync_path "$OUTPUT_DIR"; then
        log_line backup failed "db_id=$db_id" "reason=publish_fsync_failed"
        return 1
    fi
    log_line backup ok "db_id=$db_id" "archive=$(basename "$final_archive")" \
        "source_bytes=$working_bytes"
}

main() {
    (( $# == 0 )) || die unexpected_arguments
    parse_uint RETENTION_DAYS retention_days "$RETENTION_DAYS_RAW" 36500
    parse_uint RESERVE_BYTES reserve_bytes "$RESERVE_BYTES_RAW" 900000000000000000
    parse_uint VERIFY_EXTRA_BYTES verify_extra_bytes "$VERIFY_EXTRA_BYTES_RAW" 900000000000000000
    parse_uint BUSY_TIMEOUT_MS busy_timeout_ms "$BUSY_TIMEOUT_MS_RAW" 3600000

    canonical_existing_dir SOURCE_ROOT source_root "$SOURCE_ROOT_RAW"
    canonical_existing_dir OUTPUT_DIR output_dir "$OUTPUT_DIR_RAW"
    [[ "$SOURCE_ROOT" != "$OUTPUT_DIR" ]] || die source_and_output_same
    [[ -r "$SOURCE_ROOT" && -x "$SOURCE_ROOT" ]] || die source_root_unreadable
    [[ -w "$OUTPUT_DIR" && -x "$OUTPUT_DIR" ]] || die output_dir_unwritable

    local command
    for command in awk basename cksum date df flock gzip mktemp mv python3 rm sqlite3 stat tr wc; do
        command -v "$command" >/dev/null 2>&1 || die "missing_command_${command}"
    done

    local lock_path="$OUTPUT_DIR/.rushabdev-sqlite-backup.lock"
    [[ ! -L "$lock_path" ]] || die lock_path_symlink
    [[ ! -e "$lock_path" || -f "$lock_path" ]] || die lock_path_not_regular
    # Append-open avoids truncating even a pre-existing regular lock inode.
    exec 9>>"$lock_path" || die lock_open_failed
    if ! flock -n 9; then
        log_line lock failed reason=already_running
        exit 75
    fi
    RUN_STARTED=1

    prune_incomplete || exit 1

    local overall_status=0
    local relative
    local source
    local present
    for relative in "${BACKUP_MANIFEST[@]}"; do
        source="$SOURCE_ROOT/$relative"
        case "$relative" in
            *.duckdb)
                present=0
                [[ -f "$source" && ! -L "$source" ]] && present=1
                log_line backup skipped kind=duckdb reason=unsupported_no_safe_cli \
                    "db_id=$(database_id "$source")" "present=$present"
                ;;
            *)
                if ! backup_sqlite "$source"; then
                    overall_status=1
                    if ! cleanup_backup_partials; then
                        log_line backup failed reason=partial_cleanup_failed
                        exit 1
                    fi
                fi
                ;;
        esac
    done

    log_line manifest ok "entries=${#BACKUP_MANIFEST[@]}"
    return "$overall_status"
}

main "$@"
